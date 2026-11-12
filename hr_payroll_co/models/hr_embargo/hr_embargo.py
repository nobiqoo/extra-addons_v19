# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

STATE = [
    ('draft', 'Draft'),
    ('confirm', 'Confirmed'),
    ('validated', 'In Progress'),
    ('paused', 'Paused'),
    ('cancel', 'Cancelled'),
    ('paid', 'Fully Paid'),
    ('closed', 'Closed'),
]

DISCOUNT_FREQUENCY = [
    ('BIWEEKLY', 'Biweekly'),
    ('MONTHLY', 'Monthly'),
]

SS_TREATMENT = [
    ('gross', 'Gross amount'),
    ('after_ss',
     'After social security deductions (health, pension, solidarity and subsistence funds, '
     'withholding tax)'),
    ('custom', 'Custom (configurable deductions)'),
]


class HrEmbargo(models.Model):
    _name = 'hr.embargo'
    _inherit = ['model.basic.payslip.novelty', 'mail.thread']
    _description = 'Garnishment'
    _order = 'name'

    # Re-declared with English labels (the shared abstract mixin keeps its
    # original Spanish labels because it is also used by hr.loan/hr.novelty).
    name = fields.Char(string='Name', readonly=True)
    state = fields.Selection(string='Status', selection=STATE, default='draft', tracking=True)
    contract_id = fields.Many2one(
        comodel_name='hr.contract', string='Contract', domain="[('state', '=', 'open')]",
        required=True)
    employee_id = fields.Many2one(comodel_name='hr.employee', string='Employee')
    date_start = fields.Date(string='Discount Start Date', required=True)
    date_end = fields.Date(string='Discount End Date')
    amount = fields.Float(string='Debt (Initial Amount)', tracking=True)
    company_id = fields.Many2one(
        comodel_name='res.company', string='Company', default=lambda self: self.env.company,
        readonly=True)

    claimant_id = fields.Many2one(
        comodel_name='res.partner', string='Claimant', required=True,
        help='Third party (person or entity) that filed the garnishment claim; credited in '
             'the accounting entry generated when the payslip is posted.')
    embargo_type_id = fields.Many2one(
        comodel_name='hr.embargo.type', string='Garnishment Type', required=True, tracking=True)
    calculation_type = fields.Selection(
        related='embargo_type_id.calculation_type', string='Calculation Type', readonly=True)
    case_number = fields.Char(string='Case Number')
    court_process_number = fields.Char(string='Court Process Number')
    court_id = fields.Many2one(comodel_name='hr.embargo.court', string='Court')
    judicial_account = fields.Char(string='Judicial Account')
    savings_account = fields.Char(string='Savings Account')
    act_date = fields.Date(
        string='Act Date', help='Date of the judicial order/act that originated the garnishment.')
    discount_frequency = fields.Selection(
        string='Discount Frequency', selection=DISCOUNT_FREQUENCY, required=True,
        default='MONTHLY')
    percentage_value = fields.Float(
        string='Percentage Value',
        help="Used when the garnishment type's calculation is Percentage of payment.", tracking=True)
    fixed_quota_value = fields.Float(
        string='Fixed Installment Value',
        help="Used when the garnishment type's calculation is Fixed installment.", tracking=True)
    skip_legal_ceiling = fields.Boolean(
        string='Ignore Minimum Wage Ceiling', tracking=True,
        help='Check it when the court order sets the amount to discount directly (e.g. an '
             'executive garnishment of 30% of the salary from a cooperative): the garnishment '
             'then discounts exactly what its percentage or fixed installment gives, before '
             'or after social security according to its configuration, without respecting '
             'the combined legal ceiling (a fifth of the amount exceeding the minimum wage, '
             'or 50% of the earnings for alimony), and does not consume that ceiling for the '
             'other garnishments of the employee.')
    paid_amount = fields.Float(
        string='Accumulated Paid Amount', compute='_compute_balance', store=True)
    pending_balance = fields.Float(
        string='Pending Balance', compute='_compute_balance', store=True)
    base_category_ids = fields.Many2many(
        comodel_name='hr.embargo.base.category',
        relation='hr_embargo_base_category_rel',
        string='Base Categories',
        help='Salary categories taken into account to build the garnishable base.')
    ss_treatment = fields.Selection(
        string='Social Security Treatment', selection=SS_TREATMENT, required=True,
        default='gross', tracking=True)
    ss_deduction_concept_ids = fields.Many2many(
        comodel_name='hr.concept',
        relation='hr_embargo_ss_concept_rel',
        string='Deductions Subtracted from the Base',
        help='Used when the treatment is Custom: concepts subtracted from the base, e.g. '
             'health, pension, solidarity fund, withholding tax.')
    excluded_concept_ids = fields.Many2many(
        comodel_name='hr.concept',
        relation='hr_embargo_excluded_concept_rel',
        string='Excluded Concepts',
        help='Concepts always excluded from the garnishable base, e.g. transportation '
             'allowance, non-salary bonuses, per diem, extralegal allowances.')
    applies_payroll = fields.Boolean(string='Applies to Monthly/Biweekly Payroll', default=True)
    applies_prima = fields.Boolean(
        string='Applies to Service Bonus (Prima)',
        help='The garnishment applies to the service bonus payslips, and the service bonus '
             '(also the one paid in the final settlement) is part of its base.')
    applies_severance = fields.Boolean(
        string='Applies to Severance (Cesantías)',
        help='The garnishment applies to the severance payslips, and the severance (also the '
             'one paid in the final settlement) is part of its base.')
    applies_severance_interest = fields.Boolean(
        string='Applies to Severance Interest',
        help='The garnishment applies to the severance interest payslips, and the severance '
             'interest (also the one paid in the final settlement) is part of its base.')
    applies_vacation = fields.Boolean(
        string='Applies to Vacation',
        help='The garnishment applies to the vacation payslips, and the vacation compensated '
             'in the final settlement is part of its base.')
    applies_settlement = fields.Boolean(string='Applies to Final Settlement')
    line_ids = fields.One2many(
        comodel_name='hr.embargo.line', inverse_name='embargo_id', string='Installments',
        readonly=True)

    @api.onchange('court_id')
    def _onchange_court_id(self):
        for record in self:
            if record.court_id:
                record.judicial_account = record.court_id.judicial_account

    @api.onchange('embargo_type_id')
    def _onchange_embargo_type_id_calculation(self):
        for record in self:
            if record.embargo_type_id.calculation_type == 'fifth_over_minimum_with_deductions':
                record.ss_treatment = 'after_ss'
            elif record.embargo_type_id.calculation_type in (
                    'fifth_over_minimum_without_deductions', 'fixed_quota', 'percentage'):
                record.ss_treatment = 'gross'

    def applies_to_payslip_type(self, payslip_type_category):
        self.ensure_one()
        mapping = {
            'NOM': self.applies_payroll,
            'PRI': self.applies_prima,
            'CES': self.applies_severance,
            'PART_CES': self.applies_severance,
            'INTE_CES': self.applies_severance_interest,
            'VAC': self.applies_vacation,
            'LIQ': self.applies_settlement,
        }
        return mapping.get(payslip_type_category, False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name'] = self.env['ir.sequence'].next_by_code('seq.hr.embargo') or ''
        return super(HrEmbargo, self).create(vals_list)

    @api.depends('line_ids.state', 'line_ids.amount', 'amount')
    def _compute_balance(self):
        for record in self:
            paid = sum(record.line_ids.filtered(lambda l: l.state == 'paid').mapped('amount'))
            record.paid_amount = paid
            # Without a total debt there is nothing pending: showing -paid is misleading.
            record.pending_balance = record.amount - paid if record.amount else 0.0
            # `amount` (the total debt) is optional: some garnishments have no known total and
            # are only bounded by `date_end`. Without a real debt, `pending_balance` is
            # meaningless and must never auto-close the garnishment.
            if record.amount and record.pending_balance <= 0 and record.state == 'validated':
                record.state = 'paid'

    def to_confirm(self):
        for record in self:
            if record.discount_frequency != record.contract_id.schedule_pay:
                raise UserError(_(
                    "The Discount Frequency doesn't match the contract's payroll "
                    "schedule."))
            if (record.embargo_type_id.calculation_type == 'percentage'
                    and record.percentage_value <= 0):
                raise UserError(_('Configure the percentage value for this garnishment.'))
            if (record.embargo_type_id.calculation_type == 'fixed_quota'
                    and record.fixed_quota_value <= 0):
                raise UserError(_('Configure the fixed installment value for this garnishment.'))
        return super(HrEmbargo, self).to_confirm()

    def to_cancel(self):
        for record in self:
            if record.line_ids.filtered(lambda l: l.state == 'paid'):
                raise UserError(
                    _('This garnishment cannot be cancelled, it already has paid installments.'))
        return super(HrEmbargo, self).to_cancel()

    def to_draft(self):
        for record in self:
            if record.line_ids.filtered(lambda l: l.state == 'paid'):
                raise UserError(_(
                    "This garnishment cannot go back to draft, it already has paid installments."))
        return super(HrEmbargo, self).to_draft()

    def get_effective_priority(self):
        self.ensure_one()
        priority_cfg = self.env['hr.embargo.priority'].search(
            [('contract_id', '=', self.contract_id.id)], limit=1)
        if priority_cfg:
            return priority_cfg.get_priority(self.embargo_type_id)
        return self.embargo_type_id.priority

    def to_pause(self):
        for record in self:
            if record.state != 'validated':
                raise UserError(_('Only a garnishment In Progress can be paused.'))
        self.write({'state': 'paused'})

    def to_resume(self):
        for record in self:
            if record.state != 'paused':
                raise UserError(_('Only a paused garnishment can be resumed.'))
        self.write({'state': 'validated'})

    def _close_if_date_end_reached(self):
        for record in self:
            # Force any pending balance recompute to resolve first: reading a compute
            # field always triggers it if dirty. This is called right after the last
            # installment of the run gets marked 'paid', which can also be the payment
            # that finishes off the debt — in that case _compute_balance may already
            # have flipped the state to 'paid' by the time we get here. Reading
            # pending_balance first (instead of relying on incidental recompute
            # ordering) makes that deterministic: "Fully Paid" always wins over
            # "Closed" when both conditions are met in the same run.
            record.pending_balance
            if record.state != 'validated' or not record.date_end:
                continue
            covered = record.line_ids.filtered(
                lambda l: l.state == 'paid' and l.period_id
                and l.period_id.start <= record.date_end <= l.period_id.end)
            if covered:
                record.state = 'closed'
