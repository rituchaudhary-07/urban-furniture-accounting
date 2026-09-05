# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class UfBudget(models.Model):
    _name = 'uf.budget'
    _description = 'Urban Furniture Budget'
    _order = 'period_start desc, id desc'

    budget_name = fields.Char(string='Budget Name', required=True)
    period_start = fields.Date(string='Period Start', required=True)
    period_end = fields.Date(string='Period End', required=True)
    responsible_user_id = fields.Many2one(
        'res.users',
        string='Responsible User',
        required=True,
        default=lambda self: self.env.user
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        required=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )
    planned_amount = fields.Monetary(
        string='Planned Amount',
        required=True,
        currency_field='currency_id'
    )
    actual_amount = fields.Monetary(
        string='Actual Amount',
        compute='_compute_actual_amount',
        store=False,
        currency_field='currency_id',
        help='Live sum of posted move line amounts linked to the analytic account within period start and end.'
    )
    variance = fields.Monetary(
        string='Variance',
        compute='_compute_variance',
        store=False,
        currency_field='currency_id',
        help='Planned Amount minus Actual Amount'
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
    ], string='State', default='draft', required=True)

    @api.constrains('period_start', 'period_end')
    def _check_period_dates(self):
        for record in self:
            if record.period_start and record.period_end and record.period_end < record.period_start:
                raise ValidationError(_("Period End date (%s) must be greater than or equal to Period Start date (%s).") % (record.period_end, record.period_start))

    @api.constrains('planned_amount')
    def _check_planned_amount(self):
        for record in self:
            if record.planned_amount is not None and record.planned_amount <= 0:
                raise ValidationError(_("Planned Amount must be strictly greater than zero."))

    @api.depends('analytic_account_id', 'period_start', 'period_end')
    def _compute_actual_amount(self):
        MoveLine = self.env['account.move.line']
        AnalyticLine = self.env['account.analytic.line']
        
        for record in self:
            actual = 0.0
            if record.analytic_account_id and record.period_start and record.period_end:
                # Method 1: Check account.analytic.line linked to analytic_account_id
                if 'account.analytic.line' in self.env:
                    analytic_lines = AnalyticLine.search([
                        ('account_id', '=', record.analytic_account_id.id),
                        ('date', '>=', record.period_start),
                        ('date', '<=', record.period_end),
                    ])
                    if analytic_lines:
                        # Analytic lines store amounts (debit as positive/negative depending on setup)
                        actual = sum(abs(line.amount) for line in analytic_lines)
                
                # Method 2: Fallback to posted account.move.line if analytic lines returned zero or not present
                if not actual:
                    # Filter posted move lines within date range
                    domain = [
                        ('parent_state', '=', 'posted'),
                        ('date', '>=', record.period_start),
                        ('date', '<=', record.period_end),
                    ]
                    
                    # Direct Many2one check if present on account.move.line
                    if hasattr(MoveLine, 'analytic_account_id'):
                        lines = MoveLine.search(domain + [('analytic_account_id', '=', record.analytic_account_id.id)])
                        actual = sum(line.debit or line.credit or abs(line.balance) for line in lines)
                    elif hasattr(MoveLine, 'analytic_distribution') and MoveLine._fields.get('analytic_distribution'):
                        # Odoo 16+ JSON distribution check
                        all_posted_lines = MoveLine.search(domain)
                        str_analytic_id = str(record.analytic_account_id.id)
                        matching_lines = [
                            line for line in all_posted_lines
                            if line.analytic_distribution and str_analytic_id in line.analytic_distribution
                        ]
                        actual = sum(line.debit or line.credit or abs(line.balance) for line in matching_lines)
            
            record.actual_amount = actual

    @api.depends('planned_amount', 'actual_amount')
    def _compute_variance(self):
        for record in self:
            record.variance = (record.planned_amount or 0.0) - (record.actual_amount or 0.0)

    def action_confirm(self):
        for record in self:
            record.state = 'confirmed'

    def action_reset_draft(self):
        for record in self:
            record.state = 'draft'
