# Implementation Plan — Urban Furniture Accounting System (`urban_furniture_accounting`)

Build a custom Odoo module `urban_furniture_accounting` for the "Urban Furniture: Accounting System" hackathon specification. The solution prioritizes **CORRECTNESS > COMPLETENESS > RELIABILITY > DEMOABILITY > UI POLISH**.

---

## Environment & Requirements Inspection Summary (Step 1)

1. **Environment State**:
   - Python: 3.13.5
   - Workspace: `d:\Urban Furniture Accounting System`
   - Odoo Core: Module targeting Odoo 17.0 / 18.0 API & data structure standard.
2. **Mapped Native Models (Step 2)**:
   - Contact Master: `res.partner`
   - Product Master: `product.template` / `product.product`
   - Chart of Accounts: `account.account`
   - Journals: `account.journal`
   - Journal Entries / Items: `account.move` / `account.move.line`
   - Analytic Accounts: `account.analytic.account` / `account.analytic.line`
   - Purchase Orders: `purchase.order`
   - Sales Orders: `sale.order`
   - Invoices / Vendor Bills: `account.move` (`out_invoice` / `in_invoice`)
   - Payments: `account.payment`
   - Portal Access: `base.group_portal` with native `account.move` record rule
3. **Only Custom Model**: `uf.budget`

---

## User Review Required

> [!NOTE]
> Environment inspection confirmed clean machine setup with Python 3.13. We will build the full, standard Odoo module structure for `urban_furniture_accounting` alongside a standalone end-to-end verification engine that executes the complete 17-step acceptance test suite against Odoo ORM business logic.

---

## Proposed Changes

### `urban_furniture_accounting` Module Core

#### [NEW] [__manifest__.py](file:///d:/Urban Furniture Accounting System/urban_furniture_accounting/__manifest__.py)
- Module descriptor depending on `base`, `contacts`, `sale`, `purchase`, `account`.
- Includes data files, view files, and security access rules.

#### [NEW] [__init__.py](file:///d:/Urban Furniture Accounting System/urban_furniture_accounting/__init__.py)
- Imports `models`.

#### [NEW] [models/__init__.py](file:///d:/Urban Furniture Accounting System/urban_furniture_accounting/models/__init__.py)
- Imports `uf_budget`.

#### [NEW] [models/uf_budget.py](file:///d:/Urban Furniture Accounting System/urban_furniture_accounting/models/uf_budget.py)
- Defines model `uf.budget`:
  - `budget_name` (Char, required)
  - `period_start` (Date, required)
  - `period_end` (Date, required)
  - `responsible_user_id` (Many2one `res.users`, required)
  - `analytic_account_id` (Many2one `account.analytic.account`, required)
  - `planned_amount` (Monetary, required)
  - `actual_amount` (Monetary, compute method, live calculation from posted `account.move.line` / `account.analytic.line` within `period_start` and `period_end`)
  - `variance` (Monetary, compute `planned_amount - actual_amount`)
  - `currency_id` (Many2one `res.currency`, default company currency)
  - `state` (Selection: `draft`, `confirmed`, default `draft`)
  - Python constraints: `@api.constrains('period_start', 'period_end')` enforcing `period_end >= period_start`, and `@api.constrains('planned_amount')` enforcing `planned_amount > 0`.

#### [NEW] [security/ir.model.access.csv](file:///d:/Urban Furniture Accounting System/urban_furniture_accounting/security/ir.model.access.csv)
- Grants full read/write/create/unlink access on `uf.budget` to `account.group_account_manager` (Admin).
- Grants read/write/create access (no unlink) on `uf.budget` to `account.group_account_user` (Accountant).

#### [NEW] [views/uf_budget_views.xml](file:///d:/Urban Furniture Accounting System/urban_furniture_accounting/views/uf_budget_views.xml)
- Tree View: list of budgets with columns for Name, Analytic Account, Period Start, Period End, Planned Amount, Actual Amount, Variance, Responsible User, State.
- Form View: organized form with budget details, header status bar (`draft`/`confirmed`), and financial metrics.
- Pivot View ("Budget Report"): Pivot/Graph view groupable by Analytic Account, Period, Responsible Person showing Planned, Actual, and Variance metrics.
- Search View: search and filter options.

#### [NEW] [views/menu_views.xml](file:///d:/Urban Furniture Accounting System/urban_furniture_accounting/views/menu_views.xml)
- Main menu: `Urban Furniture Accounting`.
- Submenus: `Budgets` (tree/form view) and `Budget Report` (pivot view).

#### [NEW] [data/demo_data.xml](file:///d:/Urban Furniture Accounting System/urban_furniture_accounting/data/demo_data.xml)
- Seed data for:
  - Vendor: "Rahul Sharma" / "Azure Furniture"
  - Customer: "Nimesh Pathak"
  - Products: "Wooden Chair", "Office Chair"
  - Chart of Accounts & Journals (Sales, Purchase, Cash, Bank)
  - Analytic Account & `uf.budget` record
  - Complete Purchase Cycle (PO → Vendor Bill → Payment)
  - Complete Sales Cycle (SO → Customer Invoice → Payment)

---

### Verification & Testing Harness

#### [NEW] [tests/test_acceptance_flow.py](file:///d:/Urban Furniture Accounting System/urban_furniture_accounting/tests/test_acceptance_flow.py)
- Complete automated end-to-end acceptance test runner executing all 17 step-by-step acceptance criteria listed in the problem statement prompt.

---

## Verification Plan

### Automated Tests
1. Run the python acceptance test suite verifying all 17 steps:
   - Product, Customer, Vendor creation
   - PO creation, bill posting, payment registration, journal entry debit/credit verification
   - SO creation, invoice posting, payment registration, journal entry debit/credit verification
   - Financial report verification (Profit & Loss net profit, Balance Sheet asset/liability/equity balancing)
   - Live `uf.budget` computation (Planned vs Actual vs Variance)
   - Portal access restriction verification

### Manual Verification
1. Inspect generated module manifest, XML views, security rules, and models to confirm clean Odoo syntax and zero errors.
