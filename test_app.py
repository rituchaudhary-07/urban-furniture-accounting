# -*- coding: utf-8 -*-
import unittest
import os
import app
import database
import seed


class TestUrbanFurnitureAccountingApp(unittest.TestCase):

    def setUp(self):
        app.app.config['TESTING'] = True
        app.app.config['SECRET_KEY'] = 'test_secret_key'
        self.client = app.app.test_client()

        # Re-seed test database
        seed.seed_data()

    def test_01_db_seeding_and_master_data(self):
        """Verify seeded partners, products, accounts, journals, and budgets."""
        conn = database.get_db()
        cursor = conn.cursor()

        partners = cursor.execute("SELECT COUNT(*) FROM partners").fetchone()[0]
        products = cursor.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        accounts = cursor.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        journals = cursor.execute("SELECT COUNT(*) FROM journals").fetchone()[0]
        budgets = cursor.execute("SELECT COUNT(*) FROM budgets").fetchone()[0]
        conn.close()

        self.assertGreaterEqual(partners, 2)
        self.assertGreaterEqual(products, 2)
        self.assertEqual(accounts, 7)
        self.assertEqual(journals, 4)
        self.assertEqual(budgets, 3)

    def test_02_authentication_and_roles(self):
        """Verify valid login credentials and role assignments for Admin, Accountant, and Customer."""
        response = self.client.post('/login', data={'username': 'admin', 'password': 'password123'}, follow_redirects=True)
        self.assertIn(b'Financial Dashboard', response.data)

        response = self.client.post('/login', data={'username': 'accountant', 'password': 'password123'}, follow_redirects=True)
        self.assertIn(b'Financial Dashboard', response.data)

        response = self.client.post('/login', data={'username': 'nimesh_portal', 'password': 'password123'}, follow_redirects=True)
        self.assertIn(b'Customer Portal', response.data)

    def test_03_secure_password_hashing_and_auth_checks(self):
        """Verify passwords are NOT stored as plaintext and bad logins are rejected."""
        conn = database.get_db()
        users = conn.execute("SELECT username, password FROM users").fetchall()
        conn.close()

        for u in users:
            self.assertNotEqual(u['password'], 'password123', f"Plaintext password found for {u['username']}!")
            self.assertTrue(
                u['password'].startswith('scrypt:') or u['password'].startswith('pbkdf2:'),
                f"Password hash format invalid for {u['username']}"
            )

        # Invalid password rejection
        bad_response = self.client.post('/login', data={'username': 'admin', 'password': 'wrongpassword'}, follow_redirects=True)
        self.assertIn(b'Invalid username or password', bad_response.data)

    def test_04_double_entry_balance_enforcement(self):
        """Verify that every posted journal entry has sum(debit) == sum(credit)."""
        conn = database.get_db()
        cursor = conn.cursor()
        entries = cursor.execute('''
            SELECT je.id, je.entry_number, 
                   COALESCE(SUM(jl.debit), 0.0) as total_debit, 
                   COALESCE(SUM(jl.credit), 0.0) as total_credit
            FROM journal_entries je
            JOIN journal_lines jl ON je.id = jl.entry_id
            GROUP BY je.id
        ''').fetchall()
        conn.close()

        self.assertGreater(len(entries), 0)
        for entry in entries:
            self.assertEqual(
                round(entry['total_debit'], 2),
                round(entry['total_credit'], 2),
                f"Entry {entry['entry_number']} is unbalanced!"
            )

    def test_05_unbalanced_journal_entry_rejection(self):
        """Verify that create_journal_entry raises ValueError if debits != credits."""
        conn = database.get_db()
        ac_id = conn.execute("SELECT id FROM accounts LIMIT 1").fetchone()['id']
        conn.close()

        unbalanced_lines = [
            {'account_id': ac_id, 'debit': 500.0, 'credit': 0.0},
            {'account_id': ac_id, 'debit': 0.0, 'credit': 400.0} # 500 != 400
        ]
        with self.assertRaises(ValueError):
            database.create_journal_entry('2026-01-01', 'Test Bad Entry', 'entry', unbalanced_lines)

    def test_06_profit_and_loss_report(self):
        """Verify Profit & Loss calculation: Net Profit = Income - Expense."""
        pnl = database.get_profit_and_loss_report()
        self.assertEqual(pnl['total_income'], 1250.00)
        self.assertEqual(pnl['total_expense'], 800.00)
        self.assertEqual(pnl['net_profit'], 450.00)

    def test_07_balance_sheet_report(self):
        """Verify Balance Sheet equation: Assets = Liabilities + Equity."""
        bs = database.get_balance_sheet_report()
        self.assertEqual(bs['total_assets'], 10450.00)
        self.assertEqual(bs['total_liabilities'], 0.00)
        self.assertEqual(bs['total_equity'], 10450.00)
        self.assertTrue(bs['is_balanced'])

    def test_08_budget_live_actual_computation(self):
        """Verify live budget actual_amount compute and variance across seeded budgets."""
        budgets = database.get_budget_report_data()
        self.assertEqual(len(budgets), 3)

        b1 = [b for b in budgets if 'Operations' in b['budget_name']][0]
        self.assertEqual(b1['planned_amount'], 5000.00)
        self.assertEqual(b1['actual_amount'], 800.00)
        self.assertEqual(b1['variance'], 4200.00)

        b2 = [b for b in budgets if 'Marketing' in b['budget_name']][0]
        self.assertEqual(b2['planned_amount'], 3000.00)
        self.assertEqual(b2['actual_amount'], 0.00)
        self.assertEqual(b2['variance'], 3000.00)

        b3 = [b for b in budgets if 'Showroom' in b['budget_name']][0]
        self.assertEqual(b3['planned_amount'], 10000.00)
        self.assertEqual(b3['actual_amount'], 0.00)
        self.assertEqual(b3['variance'], 10000.00)

    def test_09_customer_portal_isolation(self):
        """Verify customer portal user sees only their own documents and cannot access backend."""
        with self.client as c:
            c.post('/login', data={'username': 'nimesh_portal', 'password': 'password123'})
            
            # Access portal
            resp = c.get('/portal')
            self.assertEqual(resp.status_code, 200)
            self.assertIn(b'INV/2026/00001', resp.data)

            # Try accessing backend accounting (should be redirected / denied)
            resp_acc = c.get('/accounting', follow_redirects=True)
            self.assertIn(b'Access denied', resp_acc.data)

            resp_md = c.get('/master-data', follow_redirects=True)
            self.assertIn(b'Access denied', resp_md.data)

    def test_10_user_registration_and_validation(self):
        """Verify user registration, password mismatch validation, duplicate check, and login with new user."""
        # 1. Password mismatch check
        resp_mismatch = self.client.post('/register', data={
            'name': 'Alice Smith',
            'email': 'alice@example.com',
            'username': 'alice_portal',
            'password': 'password123',
            'confirm_password': 'differentpassword',
            'role': 'portal_customer'
        }, follow_redirects=True)
        self.assertIn(b'Password confirmation does not match', resp_mismatch.data)

        # 2. Successful Registration
        resp_success = self.client.post('/register', data={
            'name': 'Alice Smith',
            'email': 'alice@example.com',
            'username': 'alice_portal',
            'password': 'password123',
            'confirm_password': 'password123',
            'role': 'portal_customer',
            'phone': '+91 9998887776'
        }, follow_redirects=True)
        self.assertIn(b'created successfully', resp_success.data)
        self.assertIn(b'alice_portal', resp_success.data)

        # 3. Duplicate username check
        resp_dup = self.client.post('/register', data={
            'name': 'Alice Copy',
            'email': 'alice2@example.com',
            'username': 'alice_portal',
            'password': 'password123',
            'confirm_password': 'password123',
            'role': 'portal_customer'
        }, follow_redirects=True)
        self.assertIn(b'already registered', resp_dup.data)

        # 4. Login with newly created user
        resp_login = self.client.post('/login', data={
            'username': 'alice_portal',
            'password': 'password123'
        }, follow_redirects=True)
        self.assertIn(b'Customer Portal', resp_login.data)

    def test_11_budget_scenarios_a_to_e(self):
        """Verify Scenarios A, B, C, D, E for Budget Actual Amount & Overlap Prevention."""
        conn = database.get_db()
        cursor = conn.cursor()

        # Create two new Analytic Accounts
        cursor.execute("INSERT INTO analytic_accounts (code, name) VALUES ('AA-SCEN-A', 'Analytic Account A')")
        aa_a = cursor.lastrowid
        cursor.execute("INSERT INTO analytic_accounts (code, name) VALUES ('AA-SCEN-B', 'Analytic Account B')")
        aa_b = cursor.lastrowid
        admin_id = cursor.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()['id']
        exp_account_id = cursor.execute("SELECT id FROM accounts WHERE code = '600000'").fetchone()['id']
        bank_account_id = cursor.execute("SELECT id FROM accounts WHERE code = '102000'").fetchone()['id']
        conn.commit()
        conn.close()

        # Scenario A: Create $5,000 budget for AA-SCEN-A. Post $800 expense.
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO budgets (budget_name, period_start, period_end, responsible_user_id, analytic_account_id, planned_amount, state)
            VALUES ('Scenario A Budget', '2026-01-01', '2026-12-31', ?, ?, 5000.00, 'confirmed')
        ''', (admin_id, aa_a))
        budget_a_id = cursor.lastrowid
        conn.commit()
        conn.close()

        database.create_journal_entry(
            date='2026-05-10',
            ref='Scenario A Expense 1',
            move_type='in_invoice',
            lines=[
                {'account_id': exp_account_id, 'analytic_account_id': aa_a, 'debit': 800.00, 'credit': 0.00, 'description': 'Scenario A $800'},
                {'account_id': bank_account_id, 'debit': 0.00, 'credit': 800.00, 'description': 'Bank Pay'}
            ]
        )

        # Verify Scenario A: Actual = $800, Variance = $4,200
        reports = database.get_budget_report_data()
        b_a = [b for b in reports if b['id'] == budget_a_id][0]
        self.assertEqual(b_a['actual_amount'], 800.00)
        self.assertEqual(b_a['variance'], 4200.00)

        # Scenario B: Post another $200 expense under AA-SCEN-A.
        database.create_journal_entry(
            date='2026-06-15',
            ref='Scenario B Expense 2',
            move_type='in_invoice',
            lines=[
                {'account_id': exp_account_id, 'analytic_account_id': aa_a, 'debit': 200.00, 'credit': 0.00, 'description': 'Scenario B $200'},
                {'account_id': bank_account_id, 'debit': 0.00, 'credit': 200.00, 'description': 'Bank Pay'}
            ]
        )

        # Verify Scenario B: Actual = $1,000, Variance = $4,000
        reports = database.get_budget_report_data()
        b_a = [b for b in reports if b['id'] == budget_a_id][0]
        self.assertEqual(b_a['actual_amount'], 1000.00)
        self.assertEqual(b_a['variance'], 4000.00)

        # Scenario C: Post an unrelated $500 expense under AA-SCEN-B.
        database.create_journal_entry(
            date='2026-07-20',
            ref='Scenario C Expense Unrelated',
            move_type='in_invoice',
            lines=[
                {'account_id': exp_account_id, 'analytic_account_id': aa_b, 'debit': 500.00, 'credit': 0.00, 'description': 'Scenario C $500'},
                {'account_id': bank_account_id, 'debit': 0.00, 'credit': 500.00, 'description': 'Bank Pay'}
            ]
        )

        # Verify Scenario C: Budget A Actual remains $1,000
        reports = database.get_budget_report_data()
        b_a = [b for b in reports if b['id'] == budget_a_id][0]
        self.assertEqual(b_a['actual_amount'], 1000.00)

        # Scenario D: Create another budget ($6,000) under AA-SCEN-B.
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO budgets (budget_name, period_start, period_end, responsible_user_id, analytic_account_id, planned_amount, state)
            VALUES ('Scenario D Budget', '2026-01-01', '2026-12-31', ?, ?, 6000.00, 'confirmed')
        ''', (admin_id, aa_b))
        budget_b_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Verify Scenario D: Budget B Actual is calculated independently ($500), Variance = $5,500
        reports = database.get_budget_report_data()
        b_b = [b for b in reports if b['id'] == budget_b_id][0]
        self.assertEqual(b_b['actual_amount'], 500.00)
        self.assertEqual(b_b['variance'], 5500.00)

        # Scenario E: Attempt to create an overlapping budget under AA-SCEN-A via HTTP POST /master-data
        with self.client as c:
            c.post('/login', data={'username': 'admin', 'password': 'password123'})
            resp_overlap = c.post('/master-data', data={
                'action_type': 'create_budget',
                'budget_name': 'Overlapping Budget Test',
                'analytic_account_id': str(aa_a),
                'period_start': '2026-03-01',
                'period_end': '2026-09-30',
                'planned_amount': '4000'
            }, follow_redirects=True)
            self.assertIn(b'already covers this Analytic Account', resp_overlap.data)

    def test_12_audit_trail_logging_and_admin_access(self):
        """Verify audit logs are recorded on login, exports, creation, and verify role-based access to /audit-trail."""
        with self.client as c:
            # 1. Admin login & access audit trail
            c.post('/login', data={'username': 'admin', 'password': 'password123'})
            resp_admin = c.get('/audit-trail')
            self.assertEqual(resp_admin.status_code, 200)
            self.assertIn(b'System Audit Trail', resp_admin.data)
            self.assertIn(b'LOGIN', resp_admin.data)

            # Check passwords are NOT logged in database
            logs = database.get_audit_logs()
            for l in logs:
                self.assertNotIn('password123', l['description'])

        # 2. Accountant access denied to /audit-trail
        with self.client as c_acc:
            c_acc.post('/login', data={'username': 'accountant', 'password': 'password123'})
            resp_acc = c_acc.get('/audit-trail', follow_redirects=True)
            self.assertIn(b'Access denied', resp_acc.data)

        # 3. Customer access denied to /audit-trail
        with self.client as c_cust:
            c_cust.post('/login', data={'username': 'nimesh_portal', 'password': 'password123'})
            resp_cust = c_cust.get('/audit-trail', follow_redirects=True)
            self.assertIn(b'Access denied', resp_cust.data)

    def test_13_report_csv_exports(self):
        """Verify CSV exports for P&L, Balance Sheet, and Budgets return HTTP 200 and text/csv headers."""
        with self.client as c:
            c.post('/login', data={'username': 'admin', 'password': 'password123'})

            # P&L CSV Export
            resp_pnl = c.get('/reports/export/pnl')
            self.assertEqual(resp_pnl.status_code, 200)
            self.assertEqual(resp_pnl.mimetype, 'text/csv')
            self.assertIn(b'Profit & Loss Statement', resp_pnl.data)
            self.assertIn(b'Total Income', resp_pnl.data)

            # Balance Sheet CSV Export
            resp_bs = c.get('/reports/export/balance-sheet')
            self.assertEqual(resp_bs.status_code, 200)
            self.assertEqual(resp_bs.mimetype, 'text/csv')
            self.assertIn(b'Balance Sheet Statement', resp_bs.data)
            self.assertIn(b'Total Assets', resp_bs.data)

            # Budgets CSV Export
            resp_b = c.get('/reports/export/budgets')
            self.assertEqual(resp_b.status_code, 200)
            self.assertEqual(resp_b.mimetype, 'text/csv')
            self.assertIn(b'Budget Performance Report', resp_b.data)
            self.assertIn(b'Planned Amount ($)', resp_b.data)

    def test_14_smart_accounting_alerts(self):
        """Verify get_smart_alerts() returns live database-driven alerts without hardcoded fake data."""
        alerts = database.get_smart_alerts()
        self.assertIsInstance(alerts, list)
        # Verify alert structure if any alerts exist
        for a in alerts:
            self.assertIn('type', a)
            self.assertIn('title', a)
            self.assertIn('message', a)

    def test_15_global_search(self):
        """Verify global search query returns matching categorized records across partners, products, and entries."""
        with self.client as c:
            c.post('/login', data={'username': 'admin', 'password': 'password123'})

            # Search product
            resp_prod = c.get('/search?q=Chair')
            self.assertEqual(resp_prod.status_code, 200)
            self.assertIn(b'Wooden Chair', resp_prod.data)

            # Search partner
            resp_part = c.get('/search?q=Rahul')
            self.assertEqual(resp_part.status_code, 200)
            self.assertIn(b'Rahul Sharma', resp_part.data)

    def test_16_customer_portal_kpis_and_security_isolation(self):
        """Verify Customer Portal dashboard KPIs, my invoices table, and server-side route security isolation."""
        with self.client as c:
            # Login as customer
            c.post('/login', data={'username': 'nimesh_portal', 'password': 'password123'}, follow_redirects=True)

            # Access Customer Portal
            resp_portal = c.get('/portal')
            self.assertEqual(resp_portal.status_code, 200)
            self.assertIn(b'Welcome, Nimesh Pathak', resp_portal.data)
            self.assertIn(b'Total Invoices', resp_portal.data)
            self.assertIn(b'Outstanding Balance', resp_portal.data)
            self.assertIn(b'INV/2026/00001', resp_portal.data)
            self.assertIn(b'INV/2026/00002', resp_portal.data)
            self.assertIn(b'Payment History', resp_portal.data)

            # Verify customer CANNOT access admin/accountant endpoints
            for restricted_url in ['/accounting', '/master-data', '/purchase', '/sales', '/reports', '/audit-trail', '/search?q=Chair']:
                resp = c.get(restricted_url, follow_redirects=True)
                self.assertIn(b'Access denied', resp.data, f"Customer was able to access restricted route {restricted_url}!")

    def test_17_customer_portal_invoice_detail_and_payment_flow(self):
        """Verify customer invoice details view, payment processing, DB updates, journal entries, and unauthorized invoice blocking."""
        conn = database.get_db()
        cursor = conn.cursor()
        inv_unpaid = cursor.execute("SELECT id FROM invoices WHERE number = 'INV/2026/00002'").fetchone()
        bill_vendor = cursor.execute("SELECT id FROM invoices WHERE number = 'BILL/2026/00001'").fetchone()
        conn.close()

        self.assertIsNotNone(inv_unpaid)
        self.assertIsNotNone(bill_vendor)
        inv2_id = inv_unpaid['id']
        bill_id = bill_vendor['id']

        with self.client as c:
            # Login as customer
            c.post('/login', data={'username': 'nimesh_portal', 'password': 'password123'}, follow_redirects=True)

            # 1. Attempt to view vendor bill belonging to another partner
            resp_unauth = c.get(f'/portal/invoice/{bill_id}', follow_redirects=True)
            self.assertIn(b'Access denied', resp_unauth.data)

            # 2. View own invoice details
            resp_detail = c.get(f'/portal/invoice/{inv2_id}')
            self.assertEqual(resp_detail.status_code, 200)
            self.assertIn(b'INV/2026/00002', resp_detail.data)
            self.assertIn(b'Office Chair', resp_detail.data)
            self.assertIn(b'500.00', resp_detail.data)

            # 3. Pay unpaid invoice via portal
            resp_pay = c.post('/portal', data={'action': 'portal_pay', 'inv_id': inv2_id}, follow_redirects=True)
            self.assertIn(b'successfully processed', resp_pay.data)

            # 4. Verify DB invoice state updated to paid
            conn = database.get_db()
            inv_updated = conn.execute("SELECT state, amount_residual FROM invoices WHERE id = ?", (inv2_id,)).fetchone()
            payment_rec = conn.execute("SELECT * FROM payments WHERE invoice_id = ?", (inv2_id,)).fetchone()
            conn.close()

            self.assertEqual(inv_updated['state'], 'paid')
            self.assertEqual(inv_updated['amount_residual'], 0.0)
            self.assertIsNotNone(payment_rec)
            self.assertEqual(payment_rec['amount'], 500.0)

            # 5. Verify payment history updated on portal
            resp_portal_after = c.get('/portal')
            self.assertIn(b'Completed', resp_portal_after.data)


if __name__ == '__main__':
    unittest.main()


