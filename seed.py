# -*- coding: utf-8 -*-
from database import init_db, get_db, create_journal_entry
import werkzeug.security as security
import datetime


def seed_data():
    init_db()
    conn = get_db()
    cursor = conn.cursor()

    # Clear existing data
    cursor.execute("PRAGMA foreign_keys = OFF;")
    tables = [
        'audit_logs', 'payments', 'journal_lines', 'journal_entries', 'invoice_lines', 'invoices',
        'sales_order_lines', 'sales_orders', 'purchase_order_lines', 'purchase_orders',
        'budgets', 'analytic_accounts', 'journals', 'accounts', 'products', 'users', 'partners'
    ]
    for table in tables:
        cursor.execute(f"DELETE FROM {table}")
        cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")
    cursor.execute("PRAGMA foreign_keys = ON;")

    print("Seeding Master Data...")

    # 1. Partners
    cursor.execute('''
        INSERT INTO partners (name, email, partner_type, phone, address)
        VALUES ('Rahul Sharma', 'rahul.sharma@vendor.com', 'vendor', '+91 9876543210', '123 Industrial Area, Mumbai')
    ''')
    vendor_id = cursor.lastrowid

    cursor.execute('''
        INSERT INTO partners (name, email, partner_type, phone, address)
        VALUES ('Nimesh Pathak', 'nimesh.pathak@customer.com', 'customer', '+91 9812345678', '456 Commerce Road, Ahmedabad')
    ''')
    customer_id = cursor.lastrowid

    # 2. Users
    pwd_hash = security.generate_password_hash('password123')
    cursor.execute('''
        INSERT INTO users (username, password, role, partner_id)
        VALUES ('admin', ?, 'admin', NULL)
    ''', (pwd_hash,))
    admin_id = cursor.lastrowid

    cursor.execute('''
        INSERT INTO users (username, password, role, partner_id)
        VALUES ('accountant', ?, 'accountant', NULL)
    ''', (pwd_hash,))

    cursor.execute('''
        INSERT INTO users (username, password, role, partner_id)
        VALUES ('nimesh_portal', ?, 'portal_customer', ?)
    ''', (pwd_hash, customer_id))

    # 3. Products
    cursor.execute('''
        INSERT INTO products (name, type, sale_price, cost_price)
        VALUES ('Wooden Chair', 'consu', 150.00, 80.00)
    ''')
    p_chair_id = cursor.lastrowid

    cursor.execute('''
        INSERT INTO products (name, type, sale_price, cost_price)
        VALUES ('Office Chair', 'consu', 250.00, 120.00)
    ''')
    p_office_id = cursor.lastrowid

    # 4. Accounts
    accounts_data = [
        ('101000', 'Cash', 'asset_cash'),
        ('102000', 'Bank', 'asset_cash'),
        ('121000', 'Debtors (Accounts Receivable)', 'asset_receivable'),
        ('211000', 'Creditors (Accounts Payable)', 'liability_payable'),
        ('400000', 'Sales Income', 'income'),
        ('600000', 'Purchase Expense', 'expense'),
        ('300000', 'Owner Capital / Equity', 'equity'),
    ]
    accounts_map = {}
    for code, name, ac_type in accounts_data:
        cursor.execute('''
            INSERT INTO accounts (code, name, account_type) VALUES (?, ?, ?)
        ''', (code, name, ac_type))
        accounts_map[code] = cursor.lastrowid

    # 5. Journals
    journals_data = [
        ('INV', 'Sales Journal', 'sale'),
        ('BILL', 'Purchase Journal', 'purchase'),
        ('BNK1', 'Bank Journal', 'bank'),
        ('CSH1', 'Cash Journal', 'cash'),
    ]
    journals_map = {}
    for code, name, j_type in journals_data:
        cursor.execute('''
            INSERT INTO journals (code, name, type) VALUES (?, ?, ?)
        ''', (code, name, j_type))
        journals_map[code] = cursor.lastrowid

    # 6. Analytic Accounts
    cursor.execute('''
        INSERT INTO analytic_accounts (code, name) VALUES ('UF-OPS', 'Urban Furniture Operations')
    ''')
    analytic_ops_id = cursor.lastrowid
    analytic_id = analytic_ops_id  # alias for purchase/sales invoice lines

    cursor.execute('''
        INSERT INTO analytic_accounts (code, name) VALUES ('UF-MKT', 'Marketing & Sales Promotion')
    ''')
    analytic_mkt_id = cursor.lastrowid

    cursor.execute('''
        INSERT INTO analytic_accounts (code, name) VALUES ('UF-EXP', 'Showroom Expansion & Equipment')
    ''')
    analytic_exp_id = cursor.lastrowid

    # 7. Budgets
    today = datetime.date.today().strftime('%Y-%m-%d')
    year_start = f"{today[:4]}-01-01"
    year_end = f"{today[:4]}-12-31"

    cursor.execute('''
        INSERT INTO budgets (budget_name, period_start, period_end, responsible_user_id, analytic_account_id, planned_amount, state)
        VALUES ('Q3 Furniture Operations Budget', ?, ?, ?, ?, 5000.00, 'confirmed')
    ''', (year_start, year_end, admin_id, analytic_ops_id))

    cursor.execute('''
        INSERT INTO budgets (budget_name, period_start, period_end, responsible_user_id, analytic_account_id, planned_amount, state)
        VALUES ('Marketing & Brand Promotion Budget', ?, ?, ?, ?, 3000.00, 'confirmed')
    ''', (year_start, year_end, admin_id, analytic_mkt_id))

    cursor.execute('''
        INSERT INTO budgets (budget_name, period_start, period_end, responsible_user_id, analytic_account_id, planned_amount, state)
        VALUES ('Showroom Expansion Budget', ?, ?, ?, ?, 10000.00, 'confirmed')
    ''', (year_start, year_end, admin_id, analytic_exp_id))

    conn.commit()
    conn.close()

    print("Seeding Initial Capital & Demo Transactions...")

    # 8. Seed Opening Capital ($10,000 into Bank)
    create_journal_entry(
        date=year_start,
        ref="Opening Capital Deposit",
        move_type="entry",
        lines=[
            {'account_id': accounts_map['102000'], 'debit': 10000.00, 'credit': 0.00, 'description': 'Owner Capital Deposit into Bank'},
            {'account_id': accounts_map['300000'], 'debit': 0.00, 'credit': 10000.00, 'description': 'Owner Equity'}
        ]
    )

    # 9. Seed Purchase Cycle (PO -> Bill -> Payment)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO purchase_orders (po_number, vendor_id, order_date, total_amount, state)
        VALUES ('PO/2026/00001', ?, ?, 800.00, 'billed')
    ''', (vendor_id, today))
    po_id = cursor.lastrowid

    cursor.execute('''
        INSERT INTO purchase_order_lines (po_id, product_id, qty, unit_price, subtotal)
        VALUES (?, ?, 10, 80.00, 800.00)
    ''', (po_id, p_chair_id))

    # Create Vendor Bill
    cursor.execute('''
        INSERT INTO invoices (number, move_type, partner_id, po_id, invoice_date, due_date, amount_total, amount_residual, state)
        VALUES ('BILL/2026/00001', 'in_invoice', ?, ?, ?, ?, 800.00, 0.00, 'paid')
    ''', (vendor_id, po_id, today, today))
    bill_id = cursor.lastrowid

    cursor.execute('''
        INSERT INTO invoice_lines (invoice_id, product_id, qty, unit_price, subtotal, analytic_account_id)
        VALUES (?, ?, 10, 80.00, 800.00, ?)
    ''', (bill_id, p_chair_id, analytic_id))
    conn.commit()
    conn.close()

    # Vendor Bill Journal Entry
    create_journal_entry(
        date=today,
        ref=f"Vendor Bill #BILL/2026/00001",
        move_type="in_invoice",
        invoice_id=bill_id,
        lines=[
            {'account_id': accounts_map['600000'], 'partner_id': vendor_id, 'analytic_account_id': analytic_id, 'debit': 800.00, 'credit': 0.00, 'description': 'Purchase 10x Wooden Chair'},
            {'account_id': accounts_map['211000'], 'partner_id': vendor_id, 'debit': 0.00, 'credit': 800.00, 'description': 'Accounts Payable Rahul Sharma'}
        ]
    )

    # Vendor Payment Journal Entry & Payment Record
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO payments (payment_number, invoice_id, partner_id, payment_date, amount, journal_id)
        VALUES ('PAY/2026/00001', ?, ?, ?, 800.00, ?)
    ''', (bill_id, vendor_id, today, journals_map['BNK1']))
    conn.commit()
    conn.close()

    create_journal_entry(
        date=today,
        ref=f"Vendor Payment for #BILL/2026/00001",
        move_type="out_payment",
        invoice_id=bill_id,
        lines=[
            {'account_id': accounts_map['211000'], 'partner_id': vendor_id, 'debit': 800.00, 'credit': 0.00, 'description': 'Pay Vendor Rahul Sharma'},
            {'account_id': accounts_map['102000'], 'debit': 0.00, 'credit': 800.00, 'description': 'Bank Disbursement'}
        ]
    )

    # 10. Seed Sales Cycle (SO -> Invoice -> Payment)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO sales_orders (so_number, customer_id, order_date, total_amount, state)
        VALUES ('SO/2026/00001', ?, ?, 750.00, 'invoiced')
    ''', (customer_id, today))
    so_id = cursor.lastrowid

    cursor.execute('''
        INSERT INTO sales_order_lines (so_id, product_id, qty, unit_price, subtotal)
        VALUES (?, ?, 5, 150.00, 750.00)
    ''', (so_id, p_chair_id))

    # Create Customer Invoice
    cursor.execute('''
        INSERT INTO invoices (number, move_type, partner_id, so_id, invoice_date, due_date, amount_total, amount_residual, state)
        VALUES ('INV/2026/00001', 'out_invoice', ?, ?, ?, ?, 750.00, 0.00, 'paid')
    ''', (customer_id, so_id, today, today))
    inv_id = cursor.lastrowid

    cursor.execute('''
        INSERT INTO invoice_lines (invoice_id, product_id, qty, unit_price, subtotal, analytic_account_id)
        VALUES (?, ?, 5, 150.00, 750.00, ?)
    ''', (inv_id, p_chair_id, analytic_id))
    conn.commit()
    conn.close()

    # Customer Invoice Journal Entry
    create_journal_entry(
        date=today,
        ref=f"Customer Invoice #INV/2026/00001",
        move_type="out_invoice",
        invoice_id=inv_id,
        lines=[
            {'account_id': accounts_map['121000'], 'partner_id': customer_id, 'debit': 750.00, 'credit': 0.00, 'description': 'Accounts Receivable Nimesh Pathak'},
            {'account_id': accounts_map['400000'], 'partner_id': customer_id, 'debit': 0.00, 'credit': 750.00, 'description': 'Sales Income 5x Wooden Chair'}
        ]
    )

    # Customer Payment Journal Entry & Payment Record
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO payments (payment_number, invoice_id, partner_id, payment_date, amount, journal_id)
        VALUES ('PAY/2026/00002', ?, ?, ?, 750.00, ?)
    ''', (inv_id, customer_id, today, journals_map['BNK1']))
    conn.commit()
    conn.close()

    create_journal_entry(
        date=today,
        ref=f"Customer Payment for #INV/2026/00001",
        move_type="in_payment",
        invoice_id=inv_id,
        lines=[
            {'account_id': accounts_map['102000'], 'debit': 750.00, 'credit': 0.00, 'description': 'Bank Receipt Customer Payment'},
            {'account_id': accounts_map['121000'], 'partner_id': customer_id, 'debit': 0.00, 'credit': 750.00, 'description': 'Clear Accounts Receivable Nimesh Pathak'}
        ]
    )

    # 11. Seed Unpaid Customer Sales Cycle (SO/2026/00002 -> INV/2026/00002)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO sales_orders (so_number, customer_id, order_date, total_amount, state)
        VALUES ('SO/2026/00002', ?, ?, 500.00, 'invoiced')
    ''', (customer_id, today))
    so2_id = cursor.lastrowid

    cursor.execute('''
        INSERT INTO sales_order_lines (so_id, product_id, qty, unit_price, subtotal)
        VALUES (?, ?, 2, 250.00, 500.00)
    ''', (so2_id, p_office_id))

    # Create Unpaid Customer Invoice
    cursor.execute('''
        INSERT INTO invoices (number, move_type, partner_id, so_id, invoice_date, due_date, amount_total, amount_residual, state)
        VALUES ('INV/2026/00002', 'out_invoice', ?, ?, ?, ?, 500.00, 500.00, 'posted')
    ''', (customer_id, so2_id, today, today))
    inv2_id = cursor.lastrowid

    cursor.execute('''
        INSERT INTO invoice_lines (invoice_id, product_id, qty, unit_price, subtotal, analytic_account_id)
        VALUES (?, ?, 2, 250.00, 500.00, ?)
    ''', (inv2_id, p_office_id, analytic_id))
    conn.commit()
    conn.close()

    # Customer Invoice Journal Entry for Unpaid Invoice
    create_journal_entry(
        date=today,
        ref=f"Customer Invoice #INV/2026/00002",
        move_type="out_invoice",
        invoice_id=inv2_id,
        lines=[
            {'account_id': accounts_map['121000'], 'partner_id': customer_id, 'debit': 500.00, 'credit': 0.00, 'description': 'Accounts Receivable Nimesh Pathak'},
            {'account_id': accounts_map['400000'], 'partner_id': customer_id, 'debit': 0.00, 'credit': 500.00, 'description': 'Sales Income 2x Office Chair'}
        ]
    )

    print("Demo Data Seeding Complete!")


if __name__ == '__main__':
    seed_data()
