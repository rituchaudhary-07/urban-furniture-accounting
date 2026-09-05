# Implementation Plan — Standalone Urban Furniture Accounting Web Application

Convert the Urban Furniture Accounting System into a **standalone, self-contained web application** built from scratch without Odoo.

---

## 1. Technology Stack & Rationale

- **Backend Framework**: **Python + Flask**
  - *Why*: Python 3.13 is already installed on the machine. Flask is fast, lightweight, standard, and requires no heavy configuration.
- **Database Engine**: **SQLite** (`urban_furniture.db`)
  - *Why*: Native to Python (`import sqlite3`). Zero database server installation or setup required. Guarantees 100% reliable local database persistence.
- **Frontend & UI Aesthetics**: **HTML5 + Vanilla CSS + JavaScript (Modern Dark/Glassmorphism Design System)**
  - *Why*: Stunning, responsive, premium UI with clean cards, data tables, status badges, dynamic modals, and Chart.js financial visualizers.
- **Authentication & Security**: Session-based auth with Role-Based Access Control (**Admin / Business Owner**, **Accountant**, **Customer Portal User**).

---

## 2. Directory & Architecture Plan

We will clean up the old Odoo folder and establish the standalone application structure:

```
Urban Furniture Accounting System/
├── app.py                      # Flask server application & route handlers
├── database.py                 # SQLite connection, schema initialization & helper methods
├── seed.py                     # Demo data seeder script
├── requirements.txt            # Python dependencies (flask)
├── static/
│   ├── css/
│   │   └── style.css           # Premium design system tokens & glassmorphic styling
│   └── js/
│       └── app.js              # Interactivity, modal handlers, chart visualizers
└── templates/
    ├── base.html               # Master layout with navigation bar & flash alerts
    ├── login.html              # Role-selection & login screen
    ├── dashboard.html          # Key metrics, overview graphs & quick actions
    ├── master_data.html        # Contacts, Products, Accounts, Journals, Budgets
    ├── purchase.html           # Purchase Orders & Vendor Bills workflow
    ├── sales.html              # Sales Orders & Customer Invoices workflow
    ├── accounting.html         # Journal Entries & Ledger balance audit
    ├── reports.html            # P&L Report, Balance Sheet, Budget Report (Pivot)
    └── portal.html             # Customer Portal (restricted invoice view & payment)
```

---

## 3. Database Schema (SQLite)

1. `users` (`id`, `username`, `password`, `role`, `partner_id`)
2. `partners` (`id`, `name`, `email`, `partner_type`, `phone`, `address`)
3. `products` (`id`, `name`, `type`, `sale_price`, `cost_price`)
4. `accounts` (`id`, `code`, `name`, `account_type`)
5. `journals` (`id`, `code`, `name`, `type`)
6. `analytic_accounts` (`id`, `code`, `name`)
7. `purchase_orders` (`id`, `vendor_id`, `order_date`, `total_amount`, `state`)
8. `purchase_order_lines` (`id`, `po_id`, `product_id`, `qty`, `unit_price`, `subtotal`)
9. `sales_orders` (`id`, `customer_id`, `order_date`, `total_amount`, `state`)
10. `sales_order_lines` (`id`, `so_id`, `product_id`, `qty`, `unit_price`, `subtotal`)
11. `invoices` (`id`, `move_type`, `partner_id`, `po_id`, `so_id`, `invoice_date`, `due_date`, `amount_total`, `amount_residual`, `state`)
12. `invoice_lines` (`id`, `invoice_id`, `product_id`, `qty`, `unit_price`, `subtotal`, `analytic_account_id`)
13. `journal_entries` (`id`, `entry_number`, `date`, `ref`, `move_type`, `invoice_id`, `state`)
14. `journal_lines` (`id`, `entry_id`, `account_id`, `partner_id`, `analytic_account_id`, `debit`, `credit`, `description`)
15. `payments` (`id`, `invoice_id`, `partner_id`, `payment_date`, `amount`, `journal_id`)
16. `budgets` (`id`, `budget_name`, `period_start`, `period_end`, `responsible_user_id`, `analytic_account_id`, `planned_amount`, `state`)

---

## 4. Key Workflows & Business Logic

1. **Purchase Workflow**:
   - Create PO $\rightarrow$ Confirm PO $\rightarrow$ Convert to Vendor Bill $\rightarrow$ Post Bill (Auto Journal Entry: Debit Purchase Expense, Credit Creditors) $\rightarrow$ Pay Bill via Bank (Auto Journal Entry: Debit Creditors, Credit Bank).
2. **Sales Workflow**:
   - Create SO $\rightarrow$ Confirm SO $\rightarrow$ Generate Customer Invoice $\rightarrow$ Post Invoice (Auto Journal Entry: Debit Debtors, Credit Sales Income) $\rightarrow$ Pay Invoice via Cash/Bank (Auto Journal Entry: Debit Cash/Bank, Credit Debtors).
3. **Double-Entry Bookkeeping Engine**:
   - Guarantees `sum(debit) == sum(credit)` for every posted entry.
4. **Real Financial Reports**:
   - **Profit & Loss**: `Sales Income - Purchase Expense = Net Profit`.
   - **Balance Sheet**: `Total Assets (Cash/Bank + Debtors) = Total Liabilities (Creditors) + Total Equity (Capital + Net Profit)`.
   - **Budget Report**: Live computed `actual_amount` from posted entries tagged with the analytic account within date range, `variance = planned_amount - actual_amount`.
5. **Customer Portal**:
   - Portal login for Nimesh Pathak (`customer_portal`).
   - Displays ONLY invoices linked to customer's `partner_id`.
   - Interactive payment registration directly against open invoice.
   - Strictly blocks access to backend accounting, chart of accounts, budgets, and other customers' documents.

---

## 5. Verification Plan

### Automated Verification
- Python test suite (`test_app.py`) verifying all endpoints, DB persistence, double-entry validation, and portal security restrictions.

### Live UI Verification
- Launch server via `python app.py`.
- Open browser at `http://localhost:5000` to test full end-to-end hackathon workflow across Admin, Accountant, and Customer Portal logins.
