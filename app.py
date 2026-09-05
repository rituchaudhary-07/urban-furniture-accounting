# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, make_response
import werkzeug.security as security
import datetime
import csv
import io
from database import (get_db, init_db, create_journal_entry, get_budget_report_data, 
                      get_profit_and_loss_report, get_balance_sheet_report, 
                      log_activity, get_audit_logs, get_smart_alerts)

app = Flask(__name__)
app.secret_key = 'urban_furniture_accounting_super_secret_key'


def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function


def role_required(allowed_roles):
    def decorator(f):
        def decorated_function(*args, **kwargs):
            if 'role' not in session or session['role'] not in allowed_roles:
                flash('Access denied: You do not have permission to view this page.', 'danger')
                if session.get('role') == 'portal_customer':
                    return redirect(url_for('portal'))
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        decorated_function.__name__ = f.__name__
        return decorated_function
    return decorator


@app.route('/login', methods=['GET', 'POST'])
def login():
    active_tab = request.args.get('tab', 'login')
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user and security.check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['partner_id'] = user['partner_id']

            log_activity(user['id'], user['username'], 'LOGIN', 'Authentication', f"User '{user['username']}' logged in successfully as {user['role']}")
            flash(f"Welcome back, {user['username']}!", 'success')

            if user['role'] == 'portal_customer':
                return redirect(url_for('portal'))
            return redirect(url_for('dashboard'))
        else:
            log_activity(None, username, 'LOGIN_FAILED', 'Authentication', f"Failed login attempt for username '{username}'")
            flash('Invalid username or password.', 'danger')
            active_tab = 'login'

    return render_template('login.html', active_tab=active_tab)


@app.route('/register', methods=['POST'])
def register():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')
    role = request.form.get('role', 'portal_customer')
    phone = request.form.get('phone', '').strip()

    if not username or not password or not confirm_password:
        flash('Username and Password fields are required.', 'danger')
        return redirect(url_for('login', tab='register'))

    if password != confirm_password:
        flash('Error: Password confirmation does not match.', 'danger')
        return redirect(url_for('login', tab='register'))

    conn = get_db()
    cursor = conn.cursor()

    # Check duplicate username
    existing_user = cursor.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
    if existing_user:
        conn.close()
        flash(f'Error: Username "{username}" is already registered.', 'danger')
        return redirect(url_for('login', tab='register'))

    # Check duplicate email if provided
    if email:
        existing_partner = cursor.execute('SELECT id FROM partners WHERE email = ?', (email,)).fetchone()
        if existing_partner:
            conn.close()
            flash(f'Error: Email "{email}" is already registered.', 'danger')
            return redirect(url_for('login', tab='register'))

    # Create partner record if name provided
    partner_id = None
    if name:
        partner_type = 'customer' if role == 'portal_customer' else 'both'
        cursor.execute('''
            INSERT INTO partners (name, email, partner_type, phone, address)
            VALUES (?, ?, ?, ?, '')
        ''', (name, email, partner_type, phone))
        partner_id = cursor.lastrowid

    # Create hashed password and insert user
    hashed_pwd = security.generate_password_hash(password)
    cursor.execute('''
        INSERT INTO users (username, password, role, partner_id)
        VALUES (?, ?, ?, ?)
    ''', (username, hashed_pwd, role, partner_id))
    new_user_id = cursor.lastrowid
    conn.commit()
    conn.close()

    log_activity(new_user_id, username, 'REGISTER', 'Authentication', f"New account '{username}' registered with role {role}")
    flash(f'Account "{username}" created successfully! Please sign in.', 'success')
    return redirect(url_for('login', tab='login'))


@app.template_filter('currency')
def currency_filter(val):
    if val is None:
        val = 0.0
    val = float(val)
    if val < 0:
        return f"-${abs(val):,.2f}"
    return f"${val:,.2f}"


@app.route('/logout')
def logout():
    if session.get('user_id'):
        log_activity(session.get('user_id'), session.get('username'), 'LOGOUT', 'Authentication', f"User '{session.get('username')}' logged out")
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/')
@login_required
def dashboard():
    if session.get('role') == 'portal_customer':
        return redirect(url_for('portal'))

    pnl = get_profit_and_loss_report()
    bs = get_balance_sheet_report()

    conn = get_db()
    cursor = conn.cursor()

    # Real database queries for KPIs
    open_invoices = cursor.execute("SELECT COUNT(*) FROM invoices WHERE state != 'paid'").fetchone()[0]
    open_customer_invoices_count = cursor.execute("SELECT COUNT(*) FROM invoices WHERE move_type = 'out_invoice' AND state != 'paid'").fetchone()[0]
    open_vendor_bills_count = cursor.execute("SELECT COUNT(*) FROM invoices WHERE move_type = 'in_invoice' AND state != 'paid'").fetchone()[0]

    total_pos = cursor.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
    total_sos = cursor.execute("SELECT COUNT(*) FROM sales_orders").fetchone()[0]

    # Outstanding Receivables (posted customer invoices with balance due)
    outstanding_receivables = cursor.execute('''
        SELECT COALESCE(SUM(amount_residual), 0.0) 
        FROM invoices 
        WHERE move_type = 'out_invoice' AND state = 'posted'
    ''').fetchone()[0]

    # Outstanding Payables (posted vendor bills with balance due)
    outstanding_payables = cursor.execute('''
        SELECT COALESCE(SUM(amount_residual), 0.0) 
        FROM invoices 
        WHERE move_type = 'in_invoice' AND state = 'posted'
    ''').fetchone()[0]

    # Recent Journal Entries with line totals and entry description
    recent_entries = cursor.execute('''
        SELECT je.*, 
               COALESCE(SUM(jl.debit), 0.0) as total_debit, 
               COALESCE(SUM(jl.credit), 0.0) as total_credit,
               COALESCE(MAX(jl.description), '') as entry_desc
        FROM journal_entries je
        LEFT JOIN journal_lines jl ON je.id = jl.entry_id
        GROUP BY je.id
        ORDER BY je.id DESC LIMIT 5
    ''').fetchall()

    conn.close()

    alerts = get_smart_alerts()

    return render_template('dashboard.html',
                           pnl=pnl,
                           bs=bs,
                           open_invoices=open_invoices,
                           open_customer_invoices_count=open_customer_invoices_count,
                           open_vendor_bills_count=open_vendor_bills_count,
                           total_pos=total_pos,
                           total_sos=total_sos,
                           outstanding_receivables=outstanding_receivables,
                           outstanding_payables=outstanding_payables,
                           recent_entries=recent_entries,
                           alerts=alerts)



@app.route('/master-data', methods=['GET', 'POST'])
@login_required
@role_required(['admin', 'accountant'])
def master_data():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        action_type = request.form.get('action_type')

        if action_type == 'create_partner':
            cursor.execute('''
                INSERT INTO partners (name, email, partner_type, phone, address)
                VALUES (?, ?, ?, ?, ?)
            ''', (request.form['name'], request.form['email'], request.form['partner_type'], request.form['phone'], request.form['address']))
            conn.commit()
            log_activity(session['user_id'], session['username'], 'CREATE', 'Master Data', f"Created partner '{request.form['name']}' ({request.form['partner_type']})")
            flash('Partner created successfully!', 'success')

        elif action_type == 'create_product':
            cursor.execute('''
                INSERT INTO products (name, type, sale_price, cost_price)
                VALUES (?, 'consu', ?, ?)
            ''', (request.form['name'], float(request.form['sale_price']), float(request.form['cost_price'])))
            conn.commit()
            log_activity(session['user_id'], session['username'], 'CREATE', 'Master Data', f"Created product '{request.form['name']}' (Price: ${float(request.form['sale_price']):.2f})")
            flash('Product created successfully!', 'success')

        elif action_type == 'create_budget':
            planned = float(request.form['planned_amount'])
            p_start = request.form['period_start']
            p_end = request.form['period_end']
            analytic_acc_id = int(request.form['analytic_account_id'])

            if p_end < p_start:
                flash('Error: Period End date must be after Period Start date.', 'danger')
            elif planned <= 0:
                flash('Error: Planned Amount must be strictly greater than zero.', 'danger')
            else:
                # Check for overlapping budgets on the same analytic account to prevent double counting
                overlapping = cursor.execute('''
                    SELECT id, budget_name, period_start, period_end 
                    FROM budgets
                    WHERE analytic_account_id = ?
                      AND period_start <= ?
                      AND period_end >= ?
                ''', (analytic_acc_id, p_end, p_start)).fetchone()

                if overlapping:
                    flash(f'Error: Budget "{overlapping["budget_name"]}" already covers this Analytic Account for an overlapping period ({overlapping["period_start"]} to {overlapping["period_end"]}). Please assign a unique Analytic Account or non-overlapping date range.', 'danger')
                else:
                    cursor.execute('''
                        INSERT INTO budgets (budget_name, period_start, period_end, responsible_user_id, analytic_account_id, planned_amount, state)
                        VALUES (?, ?, ?, ?, ?, ?, 'confirmed')
                    ''', (request.form['budget_name'], p_start, p_end, session['user_id'], analytic_acc_id, planned))
                    conn.commit()
                    log_activity(session['user_id'], session['username'], 'CREATE', 'Budgets', f"Created budget '{request.form['budget_name']}' (${planned:,.2f})")
                    flash('Budget record created successfully!', 'success')

        elif action_type == 'create_user':
            if session.get('role') != 'admin':
                flash('Access denied: Only Admin can create new users.', 'danger')
            else:
                username = request.form['username'].strip()
                raw_pwd = request.form['password']
                role = request.form['role']
                partner_id = request.form.get('partner_id')
                partner_id = int(partner_id) if partner_id and partner_id.isdigit() else None

                existing = cursor.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
                if existing:
                    flash(f'Error: Username "{username}" already exists.', 'danger')
                else:
                    hashed_pwd = security.generate_password_hash(raw_pwd)
                    cursor.execute('''
                        INSERT INTO users (username, password, role, partner_id)
                        VALUES (?, ?, ?, ?)
                    ''', (username, hashed_pwd, role, partner_id))
                    conn.commit()
                    log_activity(session['user_id'], session['username'], 'CREATE', 'User Management', f"Created system user '{username}' with role {role}")
                    flash(f'System User "{username}" created successfully with role {role}!', 'success')


    partners = cursor.execute("SELECT * FROM partners ORDER BY id DESC").fetchall()
    products = cursor.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    accounts = cursor.execute("SELECT * FROM accounts ORDER BY code").fetchall()
    journals = cursor.execute("SELECT * FROM journals ORDER BY code").fetchall()
    analytics = cursor.execute("SELECT * FROM analytic_accounts").fetchall()
    budgets = get_budget_report_data()
    users = cursor.execute("SELECT * FROM users").fetchall()
    conn.close()

    return render_template('master_data.html',
                           partners=partners,
                           products=products,
                           accounts=accounts,
                           journals=journals,
                           analytics=analytics,
                           budgets=budgets,
                           users=users)


@app.route('/purchase', methods=['GET', 'POST'])
@login_required
@role_required(['admin', 'accountant'])
def purchase():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'create_po':
            vendor_id = int(request.form['vendor_id'])
            product_id = int(request.form['product_id'])
            qty = int(request.form['qty'])
            unit_price = float(request.form['unit_price'])
            total_amount = qty * unit_price
            today = datetime.date.today().strftime('%Y-%m-%d')

            po_count = cursor.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0] + 1
            po_number = f"PO/{today[:4]}/{po_count:05d}"

            cursor.execute('''
                INSERT INTO purchase_orders (po_number, vendor_id, order_date, total_amount, state)
                VALUES (?, ?, ?, ?, 'draft')
            ''', (po_number, vendor_id, today, total_amount))
            po_id = cursor.lastrowid

            cursor.execute('''
                INSERT INTO purchase_order_lines (po_id, product_id, qty, unit_price, subtotal)
                VALUES (?, ?, ?, ?, ?)
            ''', (po_id, product_id, qty, unit_price, total_amount))
            conn.commit()
            log_activity(session['user_id'], session['username'], 'CREATE', 'Purchases', f"Created Purchase Order {po_number} (${total_amount:,.2f})")
            flash(f"Purchase Order {po_number} created in draft state.", 'success')

        elif action == 'confirm_po':
            po_id = int(request.form['po_id'])
            cursor.execute("UPDATE purchase_orders SET state = 'confirmed' WHERE id = ?", (po_id,))
            conn.commit()
            log_activity(session['user_id'], session['username'], 'CONFIRM', 'Purchases', f"Confirmed Purchase Order ID {po_id}")
            flash("Purchase Order confirmed!", 'success')

        elif action == 'create_bill':
            po_id = int(request.form['po_id'])
            po = cursor.execute("SELECT * FROM purchase_orders WHERE id = ?", (po_id,)).fetchone()
            po_lines = cursor.execute("SELECT * FROM purchase_order_lines WHERE po_id = ?", (po_id,)).fetchall()
            today = datetime.date.today().strftime('%Y-%m-%d')

            bill_count = cursor.execute("SELECT COUNT(*) FROM invoices WHERE move_type = 'in_invoice'").fetchone()[0] + 1
            bill_number = f"BILL/{today[:4]}/{bill_count:05d}"

            cursor.execute('''
                INSERT INTO invoices (number, move_type, partner_id, po_id, invoice_date, due_date, amount_total, amount_residual, state)
                VALUES (?, 'in_invoice', ?, ?, ?, ?, ?, ?, 'draft')
            ''', (bill_number, po['vendor_id'], po_id, today, today, po['total_amount'], po['total_amount']))
            bill_id = cursor.lastrowid

            # Get default analytic account
            an_acc = cursor.execute("SELECT id FROM analytic_accounts LIMIT 1").fetchone()
            analytic_id = an_acc['id'] if an_acc else None

            for line in po_lines:
                cursor.execute('''
                    INSERT INTO invoice_lines (invoice_id, product_id, qty, unit_price, subtotal, analytic_account_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (bill_id, line['product_id'], line['qty'], line['unit_price'], line['subtotal'], analytic_id))

            cursor.execute("UPDATE purchase_orders SET state = 'billed' WHERE id = ?", (po_id,))
            conn.commit()
            log_activity(session['user_id'], session['username'], 'CREATE', 'Vendor Bills', f"Created Vendor Bill {bill_number} from PO")
            flash(f"Vendor Bill {bill_number} generated from PO.", 'success')

        elif action == 'post_bill':
            bill_id = int(request.form['bill_id'])
            bill = cursor.execute("SELECT * FROM invoices WHERE id = ?", (bill_id,)).fetchone()
            bill_lines = cursor.execute("SELECT * FROM invoice_lines WHERE invoice_id = ?", (bill_id,)).fetchall()

            # Account lookup: Purchase Expense (600000) & Creditors (211000)
            exp_acc = cursor.execute("SELECT id FROM accounts WHERE code = '600000'").fetchone()['id']
            pay_acc = cursor.execute("SELECT id FROM accounts WHERE code = '211000'").fetchone()['id']

            lines = []
            for bl in bill_lines:
                lines.append({
                    'account_id': exp_acc,
                    'partner_id': bill['partner_id'],
                    'analytic_account_id': bl['analytic_account_id'],
                    'debit': bl['subtotal'],
                    'credit': 0.0,
                    'description': f"Purchase Expense for Bill {bill['number']}"
                })
            lines.append({
                'account_id': pay_acc,
                'partner_id': bill['partner_id'],
                'debit': 0.0,
                'credit': bill['amount_total'],
                'description': f"Accounts Payable for Bill {bill['number']}"
            })

            conn.close()
            create_journal_entry(
                date=bill['invoice_date'],
                ref=f"Vendor Bill {bill['number']}",
                move_type="in_invoice",
                invoice_id=bill_id,
                lines=lines
            )
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("UPDATE invoices SET state = 'posted' WHERE id = ?", (bill_id,))
            conn.commit()
            log_activity(session['user_id'], session['username'], 'POST', 'Vendor Bills', f"Posted Vendor Bill {bill['number']}")
            flash(f"Vendor Bill {bill['number']} posted and Journal Entry created!", 'success')

        elif action == 'pay_bill':
            bill_id = int(request.form['bill_id'])
            bill = cursor.execute("SELECT * FROM invoices WHERE id = ?", (bill_id,)).fetchone()
            today = datetime.date.today().strftime('%Y-%m-%d')

            pay_acc = cursor.execute("SELECT id FROM accounts WHERE code = '211000'").fetchone()['id']
            bank_acc = cursor.execute("SELECT id FROM accounts WHERE code = '102000'").fetchone()['id']
            bank_journal = cursor.execute("SELECT id FROM journals WHERE code = 'BNK1'").fetchone()['id']

            pay_count = cursor.execute("SELECT COUNT(*) FROM payments").fetchone()[0] + 1
            pay_number = f"PAY/{today[:4]}/{pay_count:05d}"

            cursor.execute('''
                INSERT INTO payments (payment_number, invoice_id, partner_id, payment_date, amount, journal_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (pay_number, bill_id, bill['partner_id'], today, bill['amount_total'], bank_journal))

            cursor.execute("UPDATE invoices SET state = 'paid', amount_residual = 0.0 WHERE id = ?", (bill_id,))
            conn.commit()
            conn.close()

            # Payment Journal Entry
            create_journal_entry(
                date=today,
                ref=f"Vendor Payment for {bill['number']}",
                move_type="out_payment",
                invoice_id=bill_id,
                lines=[
                    {'account_id': pay_acc, 'partner_id': bill['partner_id'], 'debit': bill['amount_total'], 'credit': 0.0, 'description': f"Pay Vendor Accounts Payable {bill['number']}"},
                    {'account_id': bank_acc, 'debit': 0.0, 'credit': bill['amount_total'], 'description': f"Bank Disbursement Payment {bill['number']}"}
                ]
            )
            conn = get_db()
            log_activity(session['user_id'], session['username'], 'PAYMENT', 'Vendor Payments', f"Paid Vendor Bill {bill['number']} (${bill['amount_total']:,.2f})")
            flash(f"Payment registered for Vendor Bill {bill['number']}. Bill fully PAID!", 'success')

    purchase_orders = cursor.execute('''
        SELECT po.*, p.name as vendor_name 
        FROM purchase_orders po 
        JOIN partners p ON po.vendor_id = p.id 
        ORDER BY po.id DESC
    ''').fetchall()

    vendor_bills = cursor.execute('''
        SELECT inv.*, p.name as vendor_name 
        FROM invoices inv 
        JOIN partners p ON inv.partner_id = p.id 
        WHERE inv.move_type = 'in_invoice' 
        ORDER BY inv.id DESC
    ''').fetchall()

    vendors = cursor.execute("SELECT * FROM partners WHERE partner_type IN ('vendor', 'both')").fetchall()
    products = cursor.execute("SELECT * FROM products").fetchall()
    conn.close()

    return render_template('purchase.html',
                           purchase_orders=purchase_orders,
                           vendor_bills=vendor_bills,
                           vendors=vendors,
                           products=products)


@app.route('/sales', methods=['GET', 'POST'])
@login_required
@role_required(['admin', 'accountant'])
def sales():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'create_so':
            customer_id = int(request.form['customer_id'])
            product_id = int(request.form['product_id'])
            qty = int(request.form['qty'])
            unit_price = float(request.form['unit_price'])
            total_amount = qty * unit_price
            today = datetime.date.today().strftime('%Y-%m-%d')

            so_count = cursor.execute("SELECT COUNT(*) FROM sales_orders").fetchone()[0] + 1
            so_number = f"SO/{today[:4]}/{so_count:05d}"

            cursor.execute('''
                INSERT INTO sales_orders (so_number, customer_id, order_date, total_amount, state)
                VALUES (?, ?, ?, ?, 'draft')
            ''', (so_number, customer_id, today, total_amount))
            so_id = cursor.lastrowid

            cursor.execute('''
                INSERT INTO sales_order_lines (so_id, product_id, qty, unit_price, subtotal)
                VALUES (?, ?, ?, ?, ?)
            ''', (so_id, product_id, qty, unit_price, total_amount))
            conn.commit()
            flash(f"Sales Order {so_number} created in draft state.", 'success')

        elif action == 'confirm_so':
            so_id = int(request.form['so_id'])
            cursor.execute("UPDATE sales_orders SET state = 'confirmed' WHERE id = ?", (so_id,))
            conn.commit()
            flash("Sales Order confirmed!", 'success')

        elif action == 'create_invoice':
            so_id = int(request.form['so_id'])
            so = cursor.execute("SELECT * FROM sales_orders WHERE id = ?", (so_id,)).fetchone()
            so_lines = cursor.execute("SELECT * FROM sales_order_lines WHERE so_id = ?", (so_id,)).fetchall()
            today = datetime.date.today().strftime('%Y-%m-%d')

            inv_count = cursor.execute("SELECT COUNT(*) FROM invoices WHERE move_type = 'out_invoice'").fetchone()[0] + 1
            inv_number = f"INV/{today[:4]}/{inv_count:05d}"

            cursor.execute('''
                INSERT INTO invoices (number, move_type, partner_id, so_id, invoice_date, due_date, amount_total, amount_residual, state)
                VALUES (?, 'out_invoice', ?, ?, ?, ?, ?, ?, 'draft')
            ''', (inv_number, so['customer_id'], so_id, today, today, so['total_amount'], so['total_amount']))
            inv_id = cursor.lastrowid

            an_acc = cursor.execute("SELECT id FROM analytic_accounts LIMIT 1").fetchone()
            analytic_id = an_acc['id'] if an_acc else None

            for line in so_lines:
                cursor.execute('''
                    INSERT INTO invoice_lines (invoice_id, product_id, qty, unit_price, subtotal, analytic_account_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (inv_id, line['product_id'], line['qty'], line['unit_price'], line['subtotal'], analytic_id))

            cursor.execute("UPDATE sales_orders SET state = 'invoiced' WHERE id = ?", (so_id,))
            conn.commit()
            flash(f"Customer Invoice {inv_number} generated from SO.", 'success')

        elif action == 'post_invoice':
            inv_id = int(request.form['inv_id'])
            inv = cursor.execute("SELECT * FROM invoices WHERE id = ?", (inv_id,)).fetchone()
            inv_lines = cursor.execute("SELECT * FROM invoice_lines WHERE invoice_id = ?", (inv_id,)).fetchall()

            # Accounts: Debtors (121000) & Sales Income (400000)
            rec_acc = cursor.execute("SELECT id FROM accounts WHERE code = '121000'").fetchone()['id']
            inc_acc = cursor.execute("SELECT id FROM accounts WHERE code = '400000'").fetchone()['id']

            lines = [{
                'account_id': rec_acc,
                'partner_id': inv['partner_id'],
                'debit': inv['amount_total'],
                'credit': 0.0,
                'description': f"Accounts Receivable for Invoice {inv['number']}"
            }]
            for il in inv_lines:
                lines.append({
                    'account_id': inc_acc,
                    'partner_id': inv['partner_id'],
                    'analytic_account_id': il['analytic_account_id'],
                    'debit': 0.0,
                    'credit': il['subtotal'],
                    'description': f"Sales Revenue for Invoice {inv['number']}"
                })

            conn.close()
            create_journal_entry(
                date=inv['invoice_date'],
                ref=f"Customer Invoice {inv['number']}",
                move_type="out_invoice",
                invoice_id=inv_id,
                lines=lines
            )
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("UPDATE invoices SET state = 'posted' WHERE id = ?", (inv_id,))
            conn.commit()
            flash(f"Customer Invoice {inv['number']} posted and Journal Entry created!", 'success')

        elif action == 'pay_invoice':
            inv_id = int(request.form['inv_id'])
            inv = cursor.execute("SELECT * FROM invoices WHERE id = ?", (inv_id,)).fetchone()
            today = datetime.date.today().strftime('%Y-%m-%d')

            rec_acc = cursor.execute("SELECT id FROM accounts WHERE code = '121000'").fetchone()['id']
            bank_acc = cursor.execute("SELECT id FROM accounts WHERE code = '102000'").fetchone()['id']
            bank_journal = cursor.execute("SELECT id FROM journals WHERE code = 'BNK1'").fetchone()['id']

            pay_count = cursor.execute("SELECT COUNT(*) FROM payments").fetchone()[0] + 1
            pay_number = f"PAY/{today[:4]}/{pay_count:05d}"

            cursor.execute('''
                INSERT INTO payments (payment_number, invoice_id, partner_id, payment_date, amount, journal_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (pay_number, inv_id, inv['partner_id'], today, inv['amount_total'], bank_journal))

            cursor.execute("UPDATE invoices SET state = 'paid', amount_residual = 0.0 WHERE id = ?", (inv_id,))
            conn.commit()
            conn.close()

            # Payment Journal Entry
            create_journal_entry(
                date=today,
                ref=f"Customer Payment for {inv['number']}",
                move_type="in_payment",
                invoice_id=inv_id,
                lines=[
                    {'account_id': bank_acc, 'debit': inv['amount_total'], 'credit': 0.0, 'description': f"Bank Receipt Customer Payment {inv['number']}"},
                    {'account_id': rec_acc, 'partner_id': inv['partner_id'], 'debit': 0.0, 'credit': inv['amount_total'], 'description': f"Clear Accounts Receivable"}
                ]
            )
            conn = get_db()
            cursor = conn.cursor()
            flash(f"Payment registered for Customer Invoice {inv['number']}. Invoice fully PAID!", 'success')

    sales_orders = cursor.execute('''
        SELECT so.*, p.name as customer_name 
        FROM sales_orders so 
        JOIN partners p ON so.customer_id = p.id 
        ORDER BY so.id DESC
    ''').fetchall()

    customer_invoices = cursor.execute('''
        SELECT inv.*, p.name as customer_name 
        FROM invoices inv 
        JOIN partners p ON inv.partner_id = p.id 
        WHERE inv.move_type = 'out_invoice' 
        ORDER BY inv.id DESC
    ''').fetchall()

    customers = cursor.execute("SELECT * FROM partners WHERE partner_type IN ('customer', 'both')").fetchall()
    products = cursor.execute("SELECT * FROM products").fetchall()
    conn.close()

    return render_template('sales.html',
                           sales_orders=sales_orders,
                           customer_invoices=customer_invoices,
                           customers=customers,
                           products=products)


@app.route('/accounting')
@login_required
@role_required(['admin', 'accountant'])
def accounting():
    conn = get_db()
    cursor = conn.cursor()

    entries = cursor.execute('''
        SELECT je.*, 
               COALESCE(SUM(jl.debit), 0.0) as total_debit, 
               COALESCE(SUM(jl.credit), 0.0) as total_credit
        FROM journal_entries je
        LEFT JOIN journal_lines jl ON je.id = jl.entry_id
        GROUP BY je.id
        ORDER BY je.id DESC
    ''').fetchall()

    journal_items = cursor.execute('''
        SELECT jl.*, je.entry_number, je.date, a.code as account_code, a.name as account_name, p.name as partner_name
        FROM journal_lines jl
        JOIN journal_entries je ON jl.entry_id = je.id
        JOIN accounts a ON jl.account_id = a.id
        LEFT JOIN partners p ON jl.partner_id = p.id
        ORDER BY jl.id DESC
    ''').fetchall()

    conn.close()
    return render_template('accounting.html', entries=entries, journal_items=journal_items)


@app.route('/reports')
@login_required
@role_required(['admin', 'accountant'])
def reports():
    pnl = get_profit_and_loss_report()
    bs = get_balance_sheet_report()
    budgets = get_budget_report_data()

    return render_template('reports.html', pnl=pnl, bs=bs, budgets=budgets)


@app.route('/portal', methods=['GET', 'POST'])
@login_required
def portal():
    if session.get('role') != 'portal_customer':
        flash('Redirected to main dashboard for backend user.', 'info')
        return redirect(url_for('dashboard'))

    partner_id = session.get('partner_id')
    conn = get_db()
    cursor = conn.cursor()
    today = datetime.date.today().strftime('%Y-%m-%d')

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'portal_pay':
            inv_id = int(request.form['inv_id'])
            inv = cursor.execute("SELECT * FROM invoices WHERE id = ? AND partner_id = ? AND move_type = 'out_invoice'", (inv_id, partner_id)).fetchone()

            if not inv:
                flash("Unauthorized or invoice not found.", "danger")
            elif inv['state'] == 'paid' or inv['amount_residual'] <= 0:
                flash("Invoice is already paid.", "warning")
            else:
                pay_amount = inv['amount_residual']
                rec_acc = cursor.execute("SELECT id FROM accounts WHERE code = '121000'").fetchone()['id']
                bank_acc = cursor.execute("SELECT id FROM accounts WHERE code = '102000'").fetchone()['id']
                bank_journal = cursor.execute("SELECT id FROM journals WHERE code = 'BNK1'").fetchone()['id']

                pay_count = cursor.execute("SELECT COUNT(*) FROM payments").fetchone()[0] + 1
                pay_number = f"PAY/{today[:4]}/{pay_count:05d}"

                cursor.execute('''
                    INSERT INTO payments (payment_number, invoice_id, partner_id, payment_date, amount, journal_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (pay_number, inv_id, partner_id, today, pay_amount, bank_journal))

                cursor.execute("UPDATE invoices SET state = 'paid', amount_residual = 0.0 WHERE id = ?", (inv_id,))
                conn.commit()
                conn.close()

                # Payment Journal Entry using standard accounting logic
                create_journal_entry(
                    date=today,
                    ref=f"Portal Online Payment for {inv['number']}",
                    move_type="in_payment",
                    invoice_id=inv_id,
                    lines=[
                        {'account_id': bank_acc, 'debit': pay_amount, 'credit': 0.0, 'description': f"Portal Bank Payment {inv['number']}"},
                        {'account_id': rec_acc, 'partner_id': partner_id, 'debit': 0.0, 'credit': pay_amount, 'description': f"Clear Accounts Receivable via Portal"}
                    ]
                )
                conn = get_db()
                cursor = conn.cursor()
                log_activity(session.get('user_id'), session.get('username'), 'PORTAL_PAYMENT', 'Customer Portal', f"Paid invoice {inv['number']} via Customer Portal (${pay_amount:.2f})")
                flash(f"Thank you! Payment of ${pay_amount:,.2f} for Invoice {inv['number']} was successfully processed.", 'success')

    # Fetch Customer Invoices
    my_invoices = cursor.execute('''
        SELECT *, (amount_total - amount_residual) as amount_paid
        FROM invoices 
        WHERE partner_id = ? AND move_type = 'out_invoice'
        ORDER BY id DESC
    ''', (partner_id,)).fetchall()

    # Calculate Customer Portal KPIs
    total_invoices_count = len(my_invoices)
    total_paid_amount = sum(inv['amount_paid'] for inv in my_invoices)
    outstanding_balance = sum(inv['amount_residual'] for inv in my_invoices if inv['state'] != 'paid')
    overdue_amount = sum(
        inv['amount_residual'] for inv in my_invoices 
        if inv['state'] != 'paid' and inv['due_date'] and inv['due_date'] < today
    )

    # Fetch Customer Payment History
    payment_history = cursor.execute('''
        SELECT p.*, i.number as invoice_number, j.name as journal_name
        FROM payments p
        LEFT JOIN invoices i ON p.invoice_id = i.id
        LEFT JOIN journals j ON p.journal_id = j.id
        WHERE p.partner_id = ?
        ORDER BY p.id DESC
    ''', (partner_id,)).fetchall()

    partner_info = cursor.execute("SELECT * FROM partners WHERE id = ?", (partner_id,)).fetchone()
    conn.close()

    summary_kpis = {
        'total_invoices': total_invoices_count,
        'total_paid': total_paid_amount,
        'outstanding_balance': outstanding_balance,
        'overdue_amount': overdue_amount
    }

    return render_template(
        'portal.html', 
        invoices=my_invoices, 
        partner=partner_info, 
        kpis=summary_kpis, 
        payments=payment_history,
        today=today
    )


@app.route('/portal/invoice/<int:inv_id>')
@login_required
def portal_invoice_detail(inv_id):
    if session.get('role') != 'portal_customer':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))

    partner_id = session.get('partner_id')
    conn = get_db()
    cursor = conn.cursor()

    # RESTRICTED QUERY: Verify invoice belongs strictly to logged-in partner!
    inv = cursor.execute('''
        SELECT i.*, p.name as customer_name, p.email as customer_email, p.phone as customer_phone, p.address as customer_address
        FROM invoices i
        JOIN partners p ON i.partner_id = p.id
        WHERE i.id = ? AND i.partner_id = ? AND i.move_type = 'out_invoice'
    ''', (inv_id, partner_id)).fetchone()

    if not inv:
        conn.close()
        log_activity(session.get('user_id'), session.get('username'), 'UNAUTHORIZED_ACCESS', 'Customer Portal', f"Unauthorized access attempt to invoice ID {inv_id}")
        flash('Access denied: Invoice not found or does not belong to your account.', 'danger')
        return redirect(url_for('portal'))

    lines = cursor.execute('''
        SELECT il.*, pr.name as product_name
        FROM invoice_lines il
        JOIN products pr ON il.product_id = pr.id
        WHERE il.invoice_id = ?
    ''', (inv_id,)).fetchall()

    payments = cursor.execute('''
        SELECT p.*, j.name as journal_name
        FROM payments p
        LEFT JOIN journals j ON p.journal_id = j.id
        WHERE p.invoice_id = ?
        ORDER BY p.id DESC
    ''', (inv_id,)).fetchall()

    conn.close()

    amount_paid = inv['amount_total'] - inv['amount_residual']

    return render_template(
        'portal_invoice_detail.html',
        inv=inv,
        lines=lines,
        payments=payments,
        amount_paid=amount_paid
    )


@app.route('/audit-trail')
@login_required
@role_required(['admin'])
def audit_trail():
    user_filter = request.args.get('user', '').strip()
    action_filter = request.args.get('action', '').strip()
    module_filter = request.args.get('module', '').strip()
    date_filter = request.args.get('date', '').strip()

    logs = get_audit_logs(user_filter, action_filter, module_filter, date_filter)
    return render_template('audit_trail.html', logs=logs)


@app.route('/reports/export/pnl')
@login_required
@role_required(['admin', 'accountant'])
def export_pnl():
    pnl = get_profit_and_loss_report()
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(['Profit & Loss Statement', f"Generated on {datetime.date.today()}"])
    writer.writerow([])
    writer.writerow(['INCOME ACCOUNTS', 'Account Code', 'Amount ($)'])
    for row in pnl['income_rows']:
        writer.writerow([row['name'], row['code'], f"{row['amount']:.2f}"])
    writer.writerow(['Total Income', '', f"{pnl['total_income']:.2f}"])
    writer.writerow([])
    writer.writerow(['EXPENSE ACCOUNTS', 'Account Code', 'Amount ($)'])
    for row in pnl['expense_rows']:
        writer.writerow([row['name'], row['code'], f"{row['amount']:.2f}"])
    writer.writerow(['Total Expense', '', f"{pnl['total_expense']:.2f}"])
    writer.writerow([])
    writer.writerow(['NET PROFIT / (LOSS)', '', f"{pnl['net_profit']:.2f}"])

    log_activity(session.get('user_id'), session.get('username'), 'EXPORT', 'Reports', 'Exported Profit & Loss Statement to CSV')
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=Profit_and_Loss_Report.csv"
    response.headers["Content-type"] = "text/csv"
    return response


@app.route('/reports/export/balance-sheet')
@login_required
@role_required(['admin', 'accountant'])
def export_balance_sheet():
    bs = get_balance_sheet_report()
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(['Balance Sheet Statement', f"Generated on {datetime.date.today()}"])
    writer.writerow([])
    writer.writerow(['ASSETS', 'Account Code', 'Balance ($)'])
    for row in bs['asset_rows']:
        writer.writerow([row['name'], row['code'], f"{row['balance']:.2f}"])
    writer.writerow(['Total Assets', '', f"{bs['total_assets']:.2f}"])
    writer.writerow([])
    writer.writerow(['LIABILITIES', 'Account Code', 'Balance ($)'])
    for row in bs['liability_rows']:
        writer.writerow([row['name'], row['code'], f"{row['balance']:.2f}"])
    writer.writerow(['Total Liabilities', '', f"{bs['total_liabilities']:.2f}"])
    writer.writerow([])
    writer.writerow(['EQUITY', 'Account Code', 'Balance ($)'])
    for row in bs['equity_rows']:
        writer.writerow([row['name'], row['code'], f"{row['balance']:.2f}"])
    writer.writerow(['Current Net Profit / (Loss)', '', f"{bs['net_profit']:.2f}"])
    writer.writerow(['Total Equity', '', f"{bs['total_equity']:.2f}"])
    writer.writerow([])
    writer.writerow(['Total Liabilities & Equity', '', f"{(bs['total_liabilities'] + bs['total_equity']):.2f}"])

    log_activity(session.get('user_id'), session.get('username'), 'EXPORT', 'Reports', 'Exported Balance Sheet Statement to CSV')
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=Balance_Sheet_Report.csv"
    response.headers["Content-type"] = "text/csv"
    return response


@app.route('/reports/export/budgets')
@login_required
@role_required(['admin', 'accountant'])
def export_budgets():
    budgets = get_budget_report_data()
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(['Budget Performance Report', f"Generated on {datetime.date.today()}"])
    writer.writerow([])
    writer.writerow(['Budget Name', 'Analytic Account', 'Responsible User', 'Start Date', 'End Date', 'Planned Amount ($)', 'Actual Amount ($)', 'Variance ($)', 'State'])
    for b in budgets:
        writer.writerow([b['budget_name'], b['analytic_name'], b['responsible_name'], b['period_start'], b['period_end'], f"{b['planned_amount']:.2f}", f"{b['actual_amount']:.2f}", f"{b['variance']:.2f}", b['state']])

    log_activity(session.get('user_id'), session.get('username'), 'EXPORT', 'Reports', 'Exported Budget Performance Report to CSV')
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=Budget_Performance_Report.csv"
    response.headers["Content-type"] = "text/csv"
    return response


@app.route('/search')
@login_required
@role_required(['admin', 'accountant'])
def search():
    q = request.args.get('q', '').strip()
    if not q:
        return redirect(url_for('dashboard'))

    conn = get_db()
    cursor = conn.cursor()
    search_term = f"%{q}%"

    results = {
        'query': q,
        'partners': cursor.execute("SELECT * FROM partners WHERE name LIKE ? OR email LIKE ? OR phone LIKE ?", (search_term, search_term, search_term)).fetchall(),
        'products': cursor.execute("SELECT * FROM products WHERE name LIKE ?", (search_term,)).fetchall(),
        'purchase_orders': cursor.execute("SELECT po.*, p.name as vendor_name FROM purchase_orders po JOIN partners p ON po.vendor_id = p.id WHERE po.po_number LIKE ?", (search_term,)).fetchall(),
        'sales_orders': cursor.execute("SELECT so.*, p.name as customer_name FROM sales_orders so JOIN partners p ON so.customer_id = p.id WHERE so.so_number LIKE ?", (search_term,)).fetchall(),
        'invoices': cursor.execute("SELECT i.*, p.name as partner_name FROM invoices i JOIN partners p ON i.partner_id = p.id WHERE i.number LIKE ?", (search_term,)).fetchall(),
        'journal_entries': cursor.execute("SELECT * FROM journal_entries WHERE entry_number LIKE ? OR ref LIKE ?", (search_term, search_term)).fetchall()
    }
    conn.close()

    log_activity(session.get('user_id'), session.get('username'), 'SEARCH', 'Global Search', f"Searched for query '{q}'")
    return render_template('search_results.html', results=results)


if __name__ == '__main__':
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
