# -*- coding: utf-8 -*-
import sqlite3
import os
import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'urban_furniture.db')


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Users Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL, -- admin, accountant, portal_customer
            partner_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (partner_id) REFERENCES partners (id)
        )
    ''')

    # Partners Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS partners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            partner_type TEXT NOT NULL, -- customer, vendor, both
            phone TEXT,
            address TEXT
        )
    ''')

    # Products Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT DEFAULT 'consu',
            sale_price REAL NOT NULL,
            cost_price REAL NOT NULL
        )
    ''')

    # Accounts Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            account_type TEXT NOT NULL -- asset_cash, asset_receivable, liability_payable, income, expense, equity
        )
    ''')

    # Journals Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS journals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL -- sale, purchase, bank, cash
        )
    ''')

    # Analytic Accounts Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analytic_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL
        )
    ''')

    # Purchase Orders Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            po_number TEXT UNIQUE NOT NULL,
            vendor_id INTEGER NOT NULL,
            order_date DATE NOT NULL,
            total_amount REAL NOT NULL,
            state TEXT NOT NULL DEFAULT 'draft', -- draft, confirmed, billed
            FOREIGN KEY (vendor_id) REFERENCES partners (id)
        )
    ''')

    # Purchase Order Lines Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchase_order_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            po_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            qty INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            subtotal REAL NOT NULL,
            FOREIGN KEY (po_id) REFERENCES purchase_orders (id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    ''')

    # Sales Orders Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            so_number TEXT UNIQUE NOT NULL,
            customer_id INTEGER NOT NULL,
            order_date DATE NOT NULL,
            total_amount REAL NOT NULL,
            state TEXT NOT NULL DEFAULT 'draft', -- draft, confirmed, invoiced
            FOREIGN KEY (customer_id) REFERENCES partners (id)
        )
    ''')

    # Sales Order Lines Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales_order_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            so_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            qty INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            subtotal REAL NOT NULL,
            FOREIGN KEY (so_id) REFERENCES sales_orders (id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    ''')

    # Invoices / Vendor Bills Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT UNIQUE NOT NULL,
            move_type TEXT NOT NULL, -- out_invoice (customer), in_invoice (vendor)
            partner_id INTEGER NOT NULL,
            po_id INTEGER,
            so_id INTEGER,
            invoice_date DATE NOT NULL,
            due_date DATE NOT NULL,
            amount_total REAL NOT NULL,
            amount_residual REAL NOT NULL,
            state TEXT NOT NULL DEFAULT 'draft', -- draft, posted, paid
            FOREIGN KEY (partner_id) REFERENCES partners (id),
            FOREIGN KEY (po_id) REFERENCES purchase_orders (id),
            FOREIGN KEY (so_id) REFERENCES sales_orders (id)
        )
    ''')

    # Invoice Lines Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invoice_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            qty INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            subtotal REAL NOT NULL,
            analytic_account_id INTEGER,
            FOREIGN KEY (invoice_id) REFERENCES invoices (id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products (id),
            FOREIGN KEY (analytic_account_id) REFERENCES analytic_accounts (id)
        )
    ''')

    # Journal Entries Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS journal_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_number TEXT UNIQUE NOT NULL,
            date DATE NOT NULL,
            ref TEXT,
            move_type TEXT NOT NULL, -- entry, out_invoice, in_invoice, out_payment, in_payment
            invoice_id INTEGER,
            state TEXT NOT NULL DEFAULT 'posted',
            FOREIGN KEY (invoice_id) REFERENCES invoices (id)
        )
    ''')

    # Journal Lines (Items) Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS journal_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id INTEGER NOT NULL,
            account_id INTEGER NOT NULL,
            partner_id INTEGER,
            analytic_account_id INTEGER,
            debit REAL NOT NULL DEFAULT 0.0,
            credit REAL NOT NULL DEFAULT 0.0,
            description TEXT,
            FOREIGN KEY (entry_id) REFERENCES journal_entries (id) ON DELETE CASCADE,
            FOREIGN KEY (account_id) REFERENCES accounts (id),
            FOREIGN KEY (partner_id) REFERENCES partners (id),
            FOREIGN KEY (analytic_account_id) REFERENCES analytic_accounts (id)
        )
    ''')

    # Payments Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_number TEXT UNIQUE NOT NULL,
            invoice_id INTEGER NOT NULL,
            partner_id INTEGER NOT NULL,
            payment_date DATE NOT NULL,
            amount REAL NOT NULL,
            journal_id INTEGER NOT NULL,
            FOREIGN KEY (invoice_id) REFERENCES invoices (id),
            FOREIGN KEY (partner_id) REFERENCES partners (id),
            FOREIGN KEY (journal_id) REFERENCES journals (id)
        )
    ''')

    # Budgets Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            budget_name TEXT NOT NULL,
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            responsible_user_id INTEGER NOT NULL,
            analytic_account_id INTEGER NOT NULL,
            planned_amount REAL NOT NULL,
            state TEXT NOT NULL DEFAULT 'draft', -- draft, confirmed
            FOREIGN KEY (responsible_user_id) REFERENCES users (id),
            FOREIGN KEY (analytic_account_id) REFERENCES analytic_accounts (id)
        )
    ''')

    # Audit Logs Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT NOT NULL,
            action TEXT NOT NULL,
            module TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    conn.commit()
    conn.close()


def log_activity(user_id, username, action, module, description):
    """
    Logs an audit activity record into SQLite database.
    Does NOT record sensitive info such as passwords.
    """
    if not username:
        username = 'System'
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO audit_logs (user_id, username, action, module, description)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, username, action, module, description))
    conn.commit()
    conn.close()


def get_audit_logs(user_filter=None, action_filter=None, module_filter=None, date_filter=None):
    """
    Retrieves audit logs matching optional filters for Admin audit trail.
    """
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT * FROM audit_logs WHERE 1=1"
    params = []

    if user_filter:
        query += " AND username LIKE ?"
        params.append(f"%{user_filter}%")
    if action_filter:
        query += " AND action = ?"
        params.append(action_filter)
    if module_filter:
        query += " AND module = ?"
        params.append(module_filter)
    if date_filter:
        query += " AND date(created_at) = ?"
        params.append(date_filter)

    query += " ORDER BY id DESC LIMIT 100"
    logs = cursor.execute(query, params).fetchall()
    conn.close()
    return logs


def get_smart_alerts():
    """
    Computes real database-driven alerts:
    - Overdue customer invoices
    - Pending vendor bills needing payment
    - Exceeded budgets
    - High usage budgets (>= 85%)
    """
    conn = get_db()
    cursor = conn.cursor()
    today = datetime.date.today().strftime('%Y-%m-%d')
    alerts = []

    # 1. Overdue Customer Invoices
    overdue_invoices = cursor.execute('''
        SELECT i.number, i.due_date, i.amount_residual, p.name as customer_name
        FROM invoices i
        JOIN partners p ON i.partner_id = p.id
        WHERE i.move_type = 'out_invoice'
          AND i.state = 'posted'
          AND i.due_date < ?
          AND i.amount_residual > 0
    ''', (today,)).fetchall()

    for inv in overdue_invoices:
        alerts.append({
            'type': 'danger',
            'icon': 'fa-triangle-exclamation',
            'title': 'Payment Overdue',
            'message': f"Invoice {inv['number']} for {inv['customer_name']} (Due: {inv['due_date']}) is overdue with residual balance ${inv['amount_residual']:,.2f}."
        })

    # 2. Pending Vendor Bills Needing Payment
    pending_bills = cursor.execute('''
        SELECT i.number, i.due_date, i.amount_residual, p.name as vendor_name
        FROM invoices i
        JOIN partners p ON i.partner_id = p.id
        WHERE i.move_type = 'in_invoice'
          AND i.state = 'posted'
          AND i.amount_residual > 0
    ''').fetchall()

    for bill in pending_bills:
        alerts.append({
            'type': 'warning',
            'icon': 'fa-clock',
            'title': 'Vendor Bill Pending',
            'message': f"Vendor Bill {bill['number']} from {bill['vendor_name']} has a pending payable balance of ${bill['amount_residual']:,.2f}."
        })

    # 3. Budget Alerts (Exceeded or Near Capacity >= 85%)
    budgets = get_budget_report_data()
    for b in budgets:
        planned = b['planned_amount']
        actual = b['actual_amount']
        if actual > planned:
            excess = actual - planned
            alerts.append({
                'type': 'danger',
                'icon': 'fa-circle-exclamation',
                'title': 'Budget Exceeded',
                'message': f"Budget '{b['budget_name']}' has exceeded its planned limit of ${planned:,.2f} by ${excess:,.2f} (Actual: ${actual:,.2f})."
            })
        elif actual >= (0.85 * planned) and planned > 0:
            pct = (actual / planned) * 100
            alerts.append({
                'type': 'warning',
                'icon': 'fa-triangle-exclamation',
                'title': 'Budget Near Capacity',
                'message': f"Budget '{b['budget_name']}' is at {pct:.1f}% capacity (Actual: ${actual:,.2f} / Planned: ${planned:,.2f})."
            })

    conn.close()
    return alerts


def create_journal_entry(date, ref, move_type, lines, invoice_id=None):
    """
    Creates a double-entry journal entry.
    Validates strictly that sum(debit) == sum(credit).
    """
    total_debit = round(sum(l.get('debit', 0.0) for l in lines), 2)
    total_credit = round(sum(l.get('credit', 0.0) for l in lines), 2)

    if total_debit != total_credit:
        raise ValueError(f"Unbalanced Journal Entry! Total Debit (${total_debit}) does not equal Total Credit (${total_credit}).")

    conn = get_db()
    cursor = conn.cursor()

    # Generate Entry Number
    count = cursor.execute("SELECT COUNT(*) FROM journal_entries").fetchone()[0] + 1
    entry_number = f"MISC/{date[:4]}/{count:05d}"
    if move_type == 'out_invoice':
        entry_number = f"INV/{date[:4]}/{count:05d}"
    elif move_type == 'in_invoice':
        entry_number = f"BILL/{date[:4]}/{count:05d}"
    elif move_type in ('in_payment', 'out_payment'):
        entry_number = f"PAY/{date[:4]}/{count:05d}"

    cursor.execute('''
        INSERT INTO journal_entries (entry_number, date, ref, move_type, invoice_id, state)
        VALUES (?, ?, ?, ?, ?, 'posted')
    ''', (entry_number, date, ref, move_type, invoice_id))
    entry_id = cursor.lastrowid

    for line in lines:
        cursor.execute('''
            INSERT INTO journal_lines (entry_id, account_id, partner_id, analytic_account_id, debit, credit, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            entry_id,
            line['account_id'],
            line.get('partner_id'),
            line.get('analytic_account_id'),
            line.get('debit', 0.0),
            line.get('credit', 0.0),
            line.get('description', '')
        ))

    conn.commit()
    conn.close()
    return entry_id, entry_number


def get_budget_report_data():
    """
    Computes live actual amounts and variance for all budgets based on posted journal lines.
    Calculates actual expense amounts from posted transactions matching analytic account and date range.
    """
    conn = get_db()
    cursor = conn.cursor()

    budgets = cursor.execute('''
        SELECT b.*, u.username as responsible_name, a.name as analytic_name
        FROM budgets b
        JOIN users u ON b.responsible_user_id = u.id
        JOIN analytic_accounts a ON b.analytic_account_id = a.id
        ORDER BY b.id ASC
    ''').fetchall()

    report = []
    for b in budgets:
        # Sum debits (expenses) minus credits for expense account lines matching analytic account and date range
        actual_row = cursor.execute('''
            SELECT COALESCE(SUM(jl.debit - jl.credit), 0.0) as actual
            FROM journal_lines jl
            JOIN journal_entries je ON jl.entry_id = je.id
            JOIN accounts acc ON jl.account_id = acc.id
            WHERE jl.analytic_account_id = ?
              AND je.date >= ?
              AND je.date <= ?
              AND je.state = 'posted'
              AND acc.account_type = 'expense'
        ''', (b['analytic_account_id'], b['period_start'], b['period_end'])).fetchone()

        actual_amount = max(0.0, float(actual_row['actual'])) if actual_row else 0.0
        planned_amount = float(b['planned_amount'])
        variance = planned_amount - actual_amount

        report.append({
            'id': b['id'],
            'budget_name': b['budget_name'],
            'analytic_name': b['analytic_name'],
            'responsible_name': b['responsible_name'],
            'period_start': b['period_start'],
            'period_end': b['period_end'],
            'planned_amount': planned_amount,
            'actual_amount': actual_amount,
            'variance': variance,
            'state': b['state']
        })

    conn.close()
    return report


def get_profit_and_loss_report():
    """
    Generates Profit & Loss Statement based on posted journal lines.
    Income = sum(credit - debit) for income accounts
    Expense = sum(debit - credit) for expense accounts
    Net Profit = Income - Expense
    """
    conn = get_db()
    cursor = conn.cursor()

    income_rows = cursor.execute('''
        SELECT a.name, a.code, COALESCE(SUM(jl.credit - jl.debit), 0.0) as amount
        FROM journal_lines jl
        JOIN accounts a ON jl.account_id = a.id
        JOIN journal_entries je ON jl.entry_id = je.id
        WHERE a.account_type = 'income' AND je.state = 'posted'
        GROUP BY a.id
    ''').fetchall()

    expense_rows = cursor.execute('''
        SELECT a.name, a.code, COALESCE(SUM(jl.debit - jl.credit), 0.0) as amount
        FROM journal_lines jl
        JOIN accounts a ON jl.account_id = a.id
        JOIN journal_entries je ON jl.entry_id = je.id
        WHERE a.account_type = 'expense' AND je.state = 'posted'
        GROUP BY a.id
    ''').fetchall()

    total_income = sum(r['amount'] for r in income_rows)
    total_expense = sum(r['amount'] for r in expense_rows)
    net_profit = total_income - total_expense

    conn.close()
    return {
        'income_rows': [dict(r) for r in income_rows],
        'expense_rows': [dict(r) for r in expense_rows],
        'total_income': total_income,
        'total_expense': total_expense,
        'net_profit': net_profit
    }


def get_balance_sheet_report():
    """
    Generates Balance Sheet Statement based on posted journal lines.
    Assets = Cash/Bank + Debtors
    Liabilities = Creditors
    Equity = Capital + Net Profit
    Enforces Assets = Liabilities + Equity
    """
    conn = get_db()
    cursor = conn.cursor()

    asset_rows = cursor.execute('''
        SELECT a.name, a.code, a.account_type, COALESCE(SUM(jl.debit - jl.credit), 0.0) as balance
        FROM accounts a
        LEFT JOIN journal_lines jl ON jl.account_id = a.id
        LEFT JOIN journal_entries je ON jl.entry_id = je.id AND je.state = 'posted'
        WHERE a.account_type IN ('asset_cash', 'asset_receivable')
        GROUP BY a.id
    ''').fetchall()

    liability_rows = cursor.execute('''
        SELECT a.name, a.code, a.account_type, COALESCE(SUM(jl.credit - jl.debit), 0.0) as balance
        FROM accounts a
        LEFT JOIN journal_lines jl ON jl.account_id = a.id
        LEFT JOIN journal_entries je ON jl.entry_id = je.id AND je.state = 'posted'
        WHERE a.account_type = 'liability_payable'
        GROUP BY a.id
    ''').fetchall()

    equity_rows = cursor.execute('''
        SELECT a.name, a.code, a.account_type, COALESCE(SUM(jl.credit - jl.debit), 0.0) as balance
        FROM accounts a
        LEFT JOIN journal_lines jl ON jl.account_id = a.id
        LEFT JOIN journal_entries je ON jl.entry_id = je.id AND je.state = 'posted'
        WHERE a.account_type = 'equity'
        GROUP BY a.id
    ''').fetchall()

    pnl = get_profit_and_loss_report()
    net_profit = pnl['net_profit']

    total_assets = sum(r['balance'] for r in asset_rows)
    total_liabilities = sum(r['balance'] for r in liability_rows)
    total_equity_base = sum(r['balance'] for r in equity_rows)
    total_equity_final = total_equity_base + net_profit

    conn.close()
    return {
        'asset_rows': [dict(r) for r in asset_rows],
        'liability_rows': [dict(r) for r in liability_rows],
        'equity_rows': [dict(r) for r in equity_rows],
        'total_assets': total_assets,
        'total_liabilities': total_liabilities,
        'net_profit': net_profit,
        'total_equity': total_equity_final,
        'is_balanced': round(total_assets, 2) == round(total_liabilities + total_equity_final, 2)
    }
