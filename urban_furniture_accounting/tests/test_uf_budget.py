# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from odoo.fields import Date


class TestUfBudget(TransactionCase):

    def setUp(self):
        super(TestUfBudget, self).setUp()
        self.AnalyticAccount = self.env['account.analytic.account']
        self.UfBudget = self.env['uf.budget']
        
        self.analytic_account = self.AnalyticAccount.create({
            'name': 'Test Furniture Project',
        })

    def test_01_create_valid_budget(self):
        """Test creating a valid budget record and verifying variance calculation."""
        budget = self.UfBudget.create({
            'budget_name': 'Test Budget 2026',
            'period_start': '2026-01-01',
            'period_end': '2026-12-31',
            'responsible_user_id': self.env.user.id,
            'analytic_account_id': self.analytic_account.id,
            'planned_amount': 10000.00,
        })
        self.assertEqual(budget.state, 'draft')
        self.assertEqual(budget.planned_amount, 10000.00)
        self.assertEqual(budget.variance, 10000.00 - budget.actual_amount)

    def test_02_invalid_period_dates(self):
        """Test that period_end < period_start raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.UfBudget.create({
                'budget_name': 'Invalid Dates Budget',
                'period_start': '2026-12-31',
                'period_end': '2026-01-01',
                'responsible_user_id': self.env.user.id,
                'analytic_account_id': self.analytic_account.id,
                'planned_amount': 5000.00,
            })

    def test_03_invalid_planned_amount(self):
        """Test that planned_amount <= 0 raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.UfBudget.create({
                'budget_name': 'Zero Planned Budget',
                'period_start': '2026-01-01',
                'period_end': '2026-12-31',
                'responsible_user_id': self.env.user.id,
                'analytic_account_id': self.analytic_account.id,
                'planned_amount': 0.00,
            })

    def test_04_action_confirm(self):
        """Test confirming a budget changes its state to confirmed."""
        budget = self.UfBudget.create({
            'budget_name': 'Confirmable Budget',
            'period_start': '2026-01-01',
            'period_end': '2026-12-31',
            'responsible_user_id': self.env.user.id,
            'analytic_account_id': self.analytic_account.id,
            'planned_amount': 2000.00,
        })
        budget.action_confirm()
        self.assertEqual(budget.state, 'confirmed')
