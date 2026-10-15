from odoo import fields, models, _, api, Command
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta
from odoo.tools import float_compare, float_is_zero
from odoo.tools.date_utils import end_of
import calendar
from datetime import date
import datetime


DAYS_PER_MONTH = 30
DAYS_PER_YEAR = DAYS_PER_MONTH * 12


class AccountAsset(models.Model):
    _inherit = 'account.asset'

    ifrs_type = fields.Selection(
        selection=[
            ('both', 'Both'),
            ('united', 'United'),
            ('local', 'Local'),
            ('ifrs', 'IFRS'),
        ],
        string='IFRS Type',
        default='both',
    )
    original_value_ifrs = fields.Monetary(
        string="Original Value Ifrs",
        compute='_compute_value_ifrs',
        store=True,
        readonly=False
    )
    acquisition_date_ifrs = fields.Date(
        compute='_compute_acquisition_date_ifrs', store=True, precompute=True,
        readonly=False,
        copy=True,
    )
    ifrs_model_id = fields.Many2one(
        'account.asset',
        string='Model Ifrs',
        change_default=True,
        domain="[('company_id', '=', company_id)]"
    )
    salvage_value_ifrs = fields.Monetary(
        string='Not Depreciable Value Ifrs',
        help="It is the amount you plan to have that you cannot depreciate."
    )
    book_value_ifrs = fields.Monetary(
        string='Book Value Ifrs',
        readonly=True,
        compute='_compute_book_value_ifrs',
        recursive=True,
        store=True,
        help="Sum of the depreciable value, the salvage value and the book value of all value increase items"
    )
    value_residual_ifrs = fields.Monetary(
        string='Depreciable Value Ifrs',
        compute='_compute_value_residual_ifrs'
    )
    already_depreciated_amount_import_ifrs = fields.Monetary(
        help="In case of an import from another software, you might need to use this field to have the right "
             "depreciation table report. This is the value that was already depreciated with entries not computed from this model",
    )
    ifrs_depreciation_move_ids = fields.One2many(
        'account.move',
        'ifrs_asset_id',
        string='Ifrs Depreciation Lines'
    )
    method_ifrs = fields.Selection(
        selection=[
            ('linear', 'Straight Line'),
            ('degressive', 'Declining'),
            ('degressive_then_linear', 'Declining then Straight Line')
        ],
        string='Method Ifrs',
        default='linear',
        help="Choose the method to use to compute the amount of depreciation lines.\n"
             "  * Straight Line: Calculated on basis of: Gross Value / Duration\n"
             "  * Declining: Calculated on basis of: Residual Value * Declining Factor\n"
             "  * Declining then Straight Line: Like Declining but with a minimum depreciation value equal to the straight line value."
    )
    method_number_ifrs = fields.Integer(
        string='Duration Ifrs',
        default=5,
        help="The number of depreciations needed to depreciate your asset"
    )
    method_period_ifrs = fields.Selection(
        [('1', 'Months'), ('12', 'Years')],
        string='Number of Months in a Period Ifrs',
        default='12',
        help="The amount of time between two depreciations"
    )
    method_progress_factor_ifrs = fields.Float(string='Declining Factor', default=0.3)
    prorata_computation_type_ifrs = fields.Selection(
        selection=[
            ('none', 'No Prorata'),
            ('constant_periods', 'Constant Periods'),
            ('daily_computation', 'Based on days per period'),
        ],
        string="Computation Ifrs",
        default='constant_periods',
    )
    prorata_date_ifrs = fields.Date(
        string='Prorata Date Ifrs',
        compute='_compute_prorata_date_ifrs', store=True, readonly=False,
        help='Starting date of the period used in the prorata calculation of the first depreciation',
        precompute=True,
        copy=True,
    )
    paused_prorata_date_ifrs = fields.Date(
        compute='_compute_paused_prorata_date_ifrs'
    )
    asset_paused_days_ifrs = fields.Float(
        copy=False
    )
    ifrs_account_asset_id = fields.Many2one(
        'account.account',
        string='Fixed Asset Account Ifrs',
        compute='_compute_account_asset_id',
        help="Account used to record the purchase of the asset at its original price.",
        store=True, readonly=False,
        check_company=True,
        domain="[('account_type', '!=', 'off_balance')]",
    )
    ifrs_account_depreciation_id = fields.Many2one(
        comodel_name='account.account',
        string='Depreciation Account Ifrs',
        check_company=True,
        domain="[('account_type', 'not in', ('asset_receivable', 'liability_payable', 'asset_cash', 'liability_credit_card', 'off_balance')), ('active', '=', True)]",
        help="Account used in the depreciation entries, to decrease the asset value."
    )
    ifrs_account_depreciation_expense_id = fields.Many2one(
        comodel_name='account.account',
        string='Expense Account Ifrs',
        check_company=True,
        domain="[('account_type', 'not in', ('asset_receivable', 'liability_payable', 'asset_cash', 'liability_credit_card', 'off_balance')), ('active', '=', True)]",
        help="Account used in the periodical entries, to record a part of the asset as expense.",
    )
    ifrs_journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        check_company=True,
        domain="[('type', '=', 'general')]",
        compute='_compute_ifrs_journal_id', store=True, readonly=False,
    )
    ifrs_analytic_distribution = fields.Json(
        'Analytic Distribution Ifrs',
        compute="_compute_ifrs_analytic_distribution", store=True, copy=True, readonly=False,
    )
    already_depreciated_amount_import_ifrs = fields.Monetary(
        help="In case of an import from another software, you might need to use this field to have the right "
             "depreciation table report. This is the value that was already depreciated with entries not computed from this model",
    )
    gross_increase_value_ifrs = fields.Monetary(
        string="Gross Increase Value",
        compute="_compute_gross_increase_value_ifrs",
        compute_sudo=True
    )
    depreciation_entries_count_ifrs = fields.Integer(
        compute='_compute_counts_ifrs',
        string='# Posted Depreciation Entries Ifrs'
    )
    total_depreciation_entries_count_ifrs = fields.Integer(
        compute='_compute_counts_ifrs', string='# Depreciation Entries',
        help="Number of depreciation entries (posted or not)"
    )
    asset_lifetime_days_ifrs = fields.Float(
        compute="_compute_lifetime_days_ifrs",
        recursive=True
    )
    total_depreciable_value_ifrs = fields.Monetary(
        compute='_compute_total_depreciable_value_ifrs'
    )

    # Other info
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Responsible',
        tracking=True
    )
    serail = fields.Char(
        string='Serial',
        tracking=True
    )
    plate = fields.Char(
        string='Plate',
        tracking=True
    )
    model_asset = fields.Char(
        string='Model',
        tracking=True
    )
    brand = fields.Char(
        string='Brand',
        tracking=True
    )
    job_id = fields.Many2one(
        comodel_name='hr.job',
        string='Job',
        tracking=True
    )
    location_id = fields.Many2one(
        comodel_name='asset.location',
        string='Location',
        tracking=True
    )
    active_number = fields.Char(
        string='Active Number',
    )
    provider_id = fields.Many2one(
        comodel_name='res.partner',
        string='Provider',
        tracking=True
    )
    description = fields.Char(
        string='Description'
    )
    discharge_date = fields.Date(
        string='Discharge Date'
    )
    

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    @api.depends('original_move_line_ids', 'original_move_line_ids.account_id', 'non_deductible_tax_value')
    def _compute_value_ifrs(self):
        for record in self:
            if not record.original_move_line_ids:
                record.original_value_ifrs = record.original_value_ifrs or False
                continue
            if any(line.move_id.state == 'draft' for line in record.original_move_line_ids):
                raise UserError(_("All the lines should be posted"))
            record.original_value_ifrs = record.related_purchase_value
            if record.non_deductible_tax_value:
                record.original_value_ifrs += record.non_deductible_tax_value

    @api.depends('original_move_line_ids')
    def _compute_acquisition_date_ifrs(self):
        for asset in self:
            asset.acquisition_date_ifrs = asset.acquisition_date_ifrs or min(
                [(aml.invoice_date or aml.date) for aml in asset.original_move_line_ids] + [fields.Date.today()]
            )

    @api.depends('value_residual_ifrs', 'salvage_value_ifrs', 'children_ids.book_value')
    def _compute_book_value_ifrs(self):
        for record in self:
            record.book_value_ifrs = record.value_residual_ifrs + record.salvage_value_ifrs + sum(record.children_ids.mapped('book_value'))
            if record.state == 'close' and all(move.state == 'posted' for move in record.depreciation_move_ids):
                record.book_value_ifrs -= record.salvage_value_ifrs

    @api.depends(
        'original_value_ifrs', 'salvage_value_ifrs', 'already_depreciated_amount_import_ifrs',
        'ifrs_depreciation_move_ids.state',
        'ifrs_depreciation_move_ids.depreciation_value',
        'ifrs_depreciation_move_ids.reversal_move_ids'
    )
    def _compute_value_residual_ifrs(self):
        for record in self:
            ifrs_posted_depreciation_moves = record.ifrs_depreciation_move_ids.filtered(lambda mv: mv.state == 'posted')
            record.value_residual_ifrs = (
                record.original_value_ifrs
                - record.salvage_value_ifrs
                - record.already_depreciated_amount_import_ifrs
                - sum(ifrs_posted_depreciation_moves.mapped('depreciation_value'))
            )

    @api.depends('prorata_date_ifrs', 'prorata_computation_type_ifrs', 'asset_paused_days_ifrs')
    def _compute_paused_prorata_date_ifrs(self):
        for asset in self:
            if asset.prorata_computation_type_ifrs == 'daily_computation':
                asset.paused_prorata_date_ifrs = asset.prorata_date_ifrs + relativedelta(days=asset.asset_paused_days_ifrs)
            else:
                asset.paused_prorata_date_ifrs = asset.prorata_date_ifrs + relativedelta(
                    months=int(asset.asset_paused_days_ifrs / DAYS_PER_MONTH),
                    days=asset.asset_paused_days_ifrs % DAYS_PER_MONTH
                )

    @api.depends('ifrs_account_depreciation_id', 'ifrs_account_depreciation_expense_id', 'original_move_line_ids')
    def _compute_ifrs_account_asset_id(self):
        for record in self:
            if record.original_move_line_ids:
                if len(record.original_move_line_ids.account_id) > 1:
                    raise UserError(_("All the lines should be from the same account"))
                record.ifrs_account_asset_id = record.original_move_line_ids.account_id
            if not record.ifrs_account_asset_id:
                # Only set a default value, do not erase user inputs
                record._onchange_ifrs_account_depreciation_id()

    @api.depends('company_id')
    def _compute_ifrs_journal_id(self):
        for asset in self:
            if asset.ifrs_journal_id and asset.ifrs_journal_id.company_id == asset.company_id:
                asset.ifrs_journal_id = asset.ifrs_journal_id
            else:
                asset.ifrs_journal_id = self.env['account.journal'].search([
                    *self.env['account.journal']._check_company_domain(asset.company_id),
                    ('type', '=', 'general'),
                ], limit=1)

    @api.depends('original_move_line_ids')
    def _compute_ifrs_analytic_distribution(self):
        for asset in self:
            distribution_asset = {}
            amount_total = sum(asset.original_move_line_ids.mapped("balance"))
            if not float_is_zero(amount_total, precision_rounding=asset.currency_id.rounding):
                for line in asset.original_move_line_ids._origin:
                    if line.analytic_distribution:
                        for account, distribution in line.analytic_distribution.items():
                            distribution_asset[account] = distribution_asset.get(account, 0) + distribution * line.balance
                for account, distribution_amount in distribution_asset.items():
                    distribution_asset[account] = distribution_amount / amount_total
            asset.ifrs_analytic_distribution = distribution_asset if distribution_asset else asset.ifrs_analytic_distribution

    @api.depends('children_ids.original_value')
    def _compute_gross_increase_value_ifrs(self):
        for record in self:
            record.gross_increase_value_ifrs = sum(record.children_ids.mapped('original_value'))

    @api.depends('ifrs_depreciation_move_ids.state')
    def _compute_counts_ifrs(self):
        for asset in self:
            asset.depreciation_entries_count_ifrs = len(asset.ifrs_depreciation_move_ids.filtered(lambda x: x.state == 'posted'))
            asset.total_depreciation_entries_count_ifrs = len(asset.ifrs_depreciation_move_ids)

    @api.depends('method_number_ifrs', 'method_period_ifrs', 'prorata_computation_type_ifrs')
    def _compute_lifetime_days_ifrs(self):
        for asset in self:
            if not asset.parent_id:
                if asset.prorata_computation_type_ifrs == 'daily_computation':
                    asset.asset_lifetime_days_ifrs = (asset.prorata_date_ifrs + relativedelta(months=int(asset.method_period_ifrs) * asset.method_number_ifrs) - asset.prorata_date_ifrs).days
                else:
                    asset.asset_lifetime_days_ifrs = int(asset.method_period_ifrs) * asset.method_number_ifrs * DAYS_PER_MONTH
            else:
                # if it has a parent, we want the asset to only depreciate on the remaining days left of the parent
                if asset.prorata_computation_type_ifrs == 'daily_computation':
                    parent_end_date = asset.parent_id.paused_prorata_date_ifrs + relativedelta(days=int(asset.parent_id.asset_lifetime_days_ifrs - 1))
                else:
                    parent_end_date = asset.parent_id.paused_prorata_date_ifrs + relativedelta(
                        months=int(asset.parent_id.asset_lifetime_days_ifrs / DAYS_PER_MONTH),
                        days=int(asset.parent_id.asset_lifetime_days_ifrs % DAYS_PER_MONTH) - 1
                    )
                asset.asset_lifetime_days_ifrs = asset._get_delta_days_ifrs(asset.prorata_date_ifrs, parent_end_date)

    @api.depends('salvage_value_ifrs', 'original_value_ifrs')
    def _compute_total_depreciable_value_ifrs(self):
        for asset in self:
            asset.total_depreciable_value_ifrs = asset.original_value_ifrs - asset.salvage_value_ifrs

    @api.depends('acquisition_date_ifrs', 'company_id', 'prorata_computation_type_ifrs')
    def _compute_prorata_date_ifrs(self):
        for asset in self:
            if asset.prorata_computation_type_ifrs == 'none' and asset.acquisition_date_ifrs:
                fiscalyear_date = asset.company_id.compute_fiscalyear_dates(asset.acquisition_date_ifrs).get('date_from')
                asset.prorata_date_ifrs = fiscalyear_date
            else:
                asset.prorata_date_ifrs = asset.acquisition_date_ifrs

    # -------------------------------------------------------------------------
    # ONCHANGE METHODS
    # -------------------------------------------------------------------------
    @api.onchange('ifrs_account_depreciation_id')
    def _onchange_ifrs_account_depreciation_id(self):
        if not self.original_move_line_ids:
            if not self.ifrs_account_asset_id and self.state != 'model':
                # Only set a default value since it is visible in the form
                self.ifrs_account_asset_id = self.ifrs_account_depreciation_id

    @api.onchange('original_value_ifrs', 'salvage_value_ifrs', 'acquisition_date_ifrs', 'method_ifrs', 'method_progress_factor_ifrs', 'method_period_ifrs',
                 'method_number_ifrs', 'prorata_computation_type_ifrs', 'already_depreciated_amount_import_ifrs', 'prorata_date_ifrs',)
    def onchange_consistent_board_ifrs(self):
        """ When changing the fields that should change the values of the entries, we unlink the entries, so the
         depreciation board is not inconsistent with the values of the asset"""
        self.write(
            {'ifrs_depreciation_move_ids': [Command.set([])]}
        )

    @api.onchange('original_value')
    def _onchange_original_value(self):
        for record in self:
            record.original_value_ifrs = record.original_value

    @api.onchange('method_number')
    def _onchange_method_number(self):
        for record in self:
            record.method_number_ifrs = record.method_number

    @api.onchange('method_period')
    def _onchange_method_period(self):
        for record in self:
            record.method_period_ifrs = record.method_period

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        # La herencia del modelo de activo (model_id) y el espejo del libro
        # local en el NIIF son onchange del formulario web; en un create por
        # RPC esos campos llegarían vacíos. Se completan
        # aquí, sin pisar valores enviados explícitamente.
        for vals in vals_list:
            if vals.get('state') == 'model':
                continue
            model = self.browse(vals['model_id']) if vals.get('model_id') else self.env['account.asset']
            local_defaults = {
                'method': model.method,
                'method_number': model.method_number,
                'method_period': model.method_period,
                'method_progress_factor': model.method_progress_factor,
                'prorata_computation_type': model.prorata_computation_type,
                'analytic_distribution': model.analytic_distribution,
                'account_asset_id': model.account_asset_id.id,
                'account_depreciation_id': model.account_depreciation_id.id,
                'account_depreciation_expense_id': model.account_depreciation_expense_id.id,
                'journal_id': model.journal_id.id,
            }
            for field, value in local_defaults.items():
                if field not in vals and value:
                    vals[field] = value

            ifrs_model = self.browse(vals['ifrs_model_id']) if vals.get('ifrs_model_id') else model
            # El modelo aporta la parametrización NIIF solo si la tiene
            # configurada; si no, se espeja el libro local del propio activo.
            if not (ifrs_model.ifrs_account_depreciation_id and ifrs_model.ifrs_account_depreciation_expense_id):
                ifrs_model = self.env['account.asset']
            ifrs_defaults = {
                'ifrs_type': ifrs_model.ifrs_type,
                'method_ifrs': ifrs_model.method_ifrs or vals.get('method'),
                'method_number_ifrs': ifrs_model.method_number_ifrs if ifrs_model else vals.get('method_number'),
                'method_period_ifrs': ifrs_model.method_period_ifrs if ifrs_model else vals.get('method_period'),
                'method_progress_factor_ifrs': ifrs_model.method_progress_factor_ifrs,
                'prorata_computation_type_ifrs': ifrs_model.prorata_computation_type_ifrs,
                'ifrs_account_asset_id': ifrs_model.ifrs_account_asset_id.id,
                'ifrs_account_depreciation_id': ifrs_model.ifrs_account_depreciation_id.id,
                'ifrs_account_depreciation_expense_id': ifrs_model.ifrs_account_depreciation_expense_id.id,
                'ifrs_journal_id': ifrs_model.ifrs_journal_id.id,
                'ifrs_analytic_distribution': ifrs_model.ifrs_analytic_distribution or vals.get('analytic_distribution'),
                'original_value_ifrs': vals.get('original_value'),
                'acquisition_date_ifrs': vals.get('acquisition_date'),
                'salvage_value_ifrs': vals.get('salvage_value'),
            }
            for field, value in ifrs_defaults.items():
                if field not in vals and value:
                    vals[field] = value
        return super().create(vals_list)

    # -------------------------------------------------------------------------
    # PUBLIC ACTIONS
    # -------------------------------------------------------------------------

    def validate(self):
        res = super().validate()
        for record in self.filtered(lambda x: x.ifrs_type == 'both'):
            today = date.today()
            moves_to_post = record.ifrs_depreciation_move_ids.filtered(lambda x: x.date <= today and x.state != 'posted')
            moves_to_post._post()
            move_future = record.ifrs_depreciation_move_ids.filtered(lambda x: x.date >= today and x.state != 'posted')
            for move in move_future:
                move.auto_post = 'at_date'
        return res

    def open_entries_ifrs(self):
        return {
            'name': _('Journal Entries Ifrs'),
            'view_mode': 'list,form',
            'res_model': 'account.move',
            'search_view_id': [self.env.ref('account.view_account_move_filter').id, 'search'],
            'views': [(self.env.ref('account.view_move_tree').id, 'tree'), (False, 'form')],
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', self.ifrs_depreciation_move_ids.ids)],
            'context': dict(self._context, create=False),
        }

    def compute_depreciation_board(self, date=False):
        if self.ifrs_type == 'both':
            super().compute_depreciation_board(date=date)
            self.compute_depreciation_board_ifrs(date=date)
        elif self.ifrs_type in ('local', 'united'):
            self.ifrs_depreciation_move_ids.filtered(lambda mv: mv.state == 'draft').unlink()
            super().compute_depreciation_board(date=date)
        else:
            self.depreciation_move_ids.filtered(lambda mv: mv.state == 'draft').unlink()
            self.compute_depreciation_board_ifrs(date=date)

    def compute_depreciation_board_ifrs(self, date=False):
        self.ifrs_depreciation_move_ids.filtered(lambda mv: mv.state == 'draft' and (mv.date >= date if date else True)).unlink()

        new_depreciation_moves_data = []
        for asset in self:
            new_depreciation_moves_data.extend(asset._recompute_board_ifrs(date))

        new_depreciation_moves = self.env['account.move'].create(new_depreciation_moves_data)
        new_depreciation_moves_to_post = new_depreciation_moves.filtered(lambda move: move.ifrs_asset_id.state == 'open')
        # In case of the asset is in running mode, we post in the past and set to auto post move in the future
        new_depreciation_moves_to_post._post()

    # -------------------------------------------------------------------------
    # BOARD COMPUTATION
    # -------------------------------------------------------------------------
    def _recompute_board_ifrs(self, start_depreciation_date=False):
        self.ensure_one()
        # All depreciation moves that are posted
        posted_depreciation_move_ids = self.ifrs_depreciation_move_ids.filtered(
            lambda mv: mv.state == 'posted' and not mv.asset_value_change
        ).sorted(key=lambda mv: (mv.date, mv.id))

        imported_amount = self.already_depreciated_amount_import_ifrs
        residual_amount = self.value_residual_ifrs - sum(self.ifrs_depreciation_move_ids.filtered(lambda mv: mv.state == 'draft').mapped('depreciation_value'))
        if not posted_depreciation_move_ids:
            residual_amount += imported_amount
        residual_declining = residual_at_compute = residual_amount
        # start_yearly_period is needed in the 'degressive' and 'degressive_then_linear' methods to compute the amount when the period is monthly
        start_recompute_date = start_depreciation_date = start_yearly_period = start_depreciation_date or self.paused_prorata_date_ifrs

        last_day_asset = self._get_last_day_asset_ifrs()
        final_depreciation_date = self._get_end_period_date_ifrs(last_day_asset)
        total_lifetime_left = self._get_delta_days_ifrs(start_depreciation_date, last_day_asset)

        depreciation_move_values = []
        if not float_is_zero(self.value_residual_ifrs, precision_rounding=self.currency_id.rounding):
            while not self.currency_id.is_zero(residual_amount) and start_depreciation_date < final_depreciation_date:
                period_end_depreciation_date = self._get_end_period_date_ifrs(start_depreciation_date)
                period_end_fiscalyear_date = self.company_id.compute_fiscalyear_dates(period_end_depreciation_date).get('date_to')
                lifetime_left = self._get_delta_days_ifrs(start_depreciation_date, last_day_asset)

                days, amount = self._compute_board_amount_ifrs(residual_amount, start_depreciation_date, period_end_depreciation_date, False, lifetime_left, residual_declining, start_yearly_period, total_lifetime_left, residual_at_compute, start_recompute_date)
                residual_amount -= amount

                if not posted_depreciation_move_ids:
                    # self.already_depreciated_amount_import management.
                    # Subtracts the imported amount from the first depreciation moves until we reach it
                    # (might skip several depreciation entries)
                    if abs(imported_amount) <= abs(amount):
                        amount -= imported_amount
                        imported_amount = 0
                    else:
                        imported_amount -= amount
                        amount = 0

                if self.method_ifrs == 'degressive_then_linear' and final_depreciation_date < period_end_depreciation_date:
                    period_end_depreciation_date = final_depreciation_date

                if not float_is_zero(amount, precision_rounding=self.currency_id.rounding):
                    # For deferred revenues, we should invert the amounts.
                    depreciation_move_values.append(self.env['account.move']._prepare_move_for_asset_depreciation_ifrs({
                        'amount': amount,
                        'ifrs_asset_id': self,
                        'depreciation_beginning_date': start_depreciation_date,
                        'date': period_end_depreciation_date,
                        'asset_number_days': days,
                        'ifrs_type': 'ifrs',
                    }))

                if period_end_depreciation_date == period_end_fiscalyear_date:
                    start_yearly_period = self.company_id.compute_fiscalyear_dates(period_end_depreciation_date).get('date_from') + relativedelta(years=1)
                    residual_declining = residual_amount

                start_depreciation_date = period_end_depreciation_date + relativedelta(days=1)

        return depreciation_move_values

    def _get_last_day_asset_ifrs(self):
        this = self.parent_id if self.parent_id else self
        return this.paused_prorata_date_ifrs + relativedelta(months=int(this.method_period_ifrs) * this.method_number_ifrs, days=-1)

    def _get_end_period_date_ifrs(self, start_depreciation_date):
        """Get the end of the period in which the depreciation is posted.

        Can be the end of the month if the asset is depreciated monthly, or the end of the fiscal year is it is depreciated yearly.
        """
        self.ensure_one()
        fiscalyear_date = self.company_id.compute_fiscalyear_dates(start_depreciation_date).get('date_to')
        period_end_depreciation_date = fiscalyear_date if start_depreciation_date <= fiscalyear_date else fiscalyear_date + relativedelta(years=1)

        if self.method_period_ifrs == '1':  # If method period is set to monthly computation
            max_day_in_month = end_of(datetime.date(start_depreciation_date.year, start_depreciation_date.month, 1), 'month').day
            period_end_depreciation_date = min(start_depreciation_date.replace(day=max_day_in_month), period_end_depreciation_date)
        return period_end_depreciation_date

    def _get_delta_days_ifrs(self, start_date, end_date):
        """Compute how many days there are between 2 dates.

        The computation is different if the asset is in daily_computation or not.
        """
        self.ensure_one()
        if self.prorata_computation_type_ifrs == 'daily_computation':
            # Compute how many days there are between 2 dates using a daily_computation method
            return (end_date - start_date).days + 1
        else:
            # Compute how many days there are between 2 dates counting 30 days per month
            # Get how many days there are in the start date month
            start_date_days_month = end_of(start_date, 'month').day
            # Get how many days there are in the start date month (e.g: June 20th: (30 * (30 - 20 + 1)) / 30 = 11)
            start_prorata = (start_date_days_month - start_date.day + 1) / start_date_days_month
            # Get how many days there are in the end date month (e.g: You're the August 14th: (14 * 30) / 31 = 13.548387096774194)
            end_prorata = end_date.day / end_of(end_date, 'month').day
            # Compute how many days there are between these 2 dates
            # e.g: 13.548387096774194 + 11 + 360 * (2020 - 2020) + 30 * (8 - 6 - 1) = 24.548387096774194 + 360 * 0 + 30 * 1 = 54.548387096774194 day
            return sum((
                start_prorata * DAYS_PER_MONTH,
                end_prorata * DAYS_PER_MONTH,
                (end_date.year - start_date.year) * DAYS_PER_YEAR,
                (end_date.month - start_date.month - 1) * DAYS_PER_MONTH
            ))

    def _compute_board_amount_ifrs(self, residual_amount, period_start_date, period_end_date, days_already_depreciated,
                              days_left_to_depreciated, residual_declining, start_yearly_period=None, total_lifetime_left=None,
                              residual_at_compute=None, start_recompute_date=None):

        def _get_max_between_linear_and_degressive(linear_amount):
            """
            Compute the degressive amount that could be depreciated and returns the biggest between it and linear_amount
            The degressive amount corresponds to the difference between what should have been depreciated at the end of
            the period and the residual_amount (to deal with rounding issues at the end of each month)
            """
            fiscalyear_dates = self.company_id.compute_fiscalyear_dates(period_end_date)
            days_in_fiscalyear = self._get_delta_days_ifrs(fiscalyear_dates['date_from'], fiscalyear_dates['date_to'])

            degressive_total_value = residual_declining * (1 - self.method_progress_factor_ifrs * self._get_delta_days_ifrs(start_yearly_period, period_end_date) / days_in_fiscalyear)
            degressive_amount = residual_amount - degressive_total_value
            return self._degressive_linear_amount(residual_amount, degressive_amount, linear_amount)

        if float_is_zero(self.asset_lifetime_days_ifrs, 2) or float_is_zero(residual_amount, 2):
            return 0, 0

        days_until_period_end = self._get_delta_days_ifrs(self.paused_prorata_date_ifrs, period_end_date)
        days_before_period = self._get_delta_days_ifrs(self.paused_prorata_date_ifrs, period_start_date + relativedelta(days=-1))
        days_before_period = max(days_before_period, 0)  # if disposed before the beginning of the asset for example
        number_days = days_until_period_end - days_before_period

        # The amount to depreciate are computed by computing how much the asset should be depreciated at the end of the
        # period minus how much it is actually depreciated. It is done that way to avoid having the last move to take
        # every single small difference that could appear over the time with the classic computation method.
        if self.method_ifrs == 'linear':
            if total_lifetime_left and float_compare(total_lifetime_left, 0, 2) > 0:
                computed_linear_amount = residual_amount - residual_at_compute * (1 - self._get_delta_days_ifrs(start_recompute_date, period_end_date) / total_lifetime_left)
            else:
                computed_linear_amount = self._get_linear_amount_ifrs(days_before_period, days_until_period_end, self.total_depreciable_value_ifrs)
            amount = min(computed_linear_amount, residual_amount, key=abs)
        elif self.method_ifrs == 'degressive':
            # Linear amount
            # We first calculate the total linear amount for the period left from the beginning of the year
            # to get the linear amount for the period in order to avoid big delta at the end of the period
            days_left_from_beginning_of_year = self._get_delta_days_ifrs(start_yearly_period, period_start_date - relativedelta(days=1)) + days_left_to_depreciated
            expected_remaining_value_with_linear = residual_declining - residual_declining * self._get_delta_days_ifrs(start_yearly_period, period_end_date) / days_left_from_beginning_of_year
            linear_amount = residual_amount - expected_remaining_value_with_linear

            amount = _get_max_between_linear_and_degressive(linear_amount)
        elif self.method_ifrs == 'degressive_then_linear':
            if not self.parent_id:
                linear_amount = self._get_linear_amount_ifrs(days_before_period, days_until_period_end, self.total_depreciable_value_ifrs)
            else:
                # we want to know the amount before the reeval for the parent so the child can follow the same curve,
                # so it transitions from degressive to linear at the same moment
                parent_moves = self.parent_id.ifrs_depreciation_move_ids.filtered(lambda mv: mv.date <= self.prorata_date).sorted(key=lambda mv: (mv.date, mv.id))
                parent_cumulative_depreciation = parent_moves[-1].asset_depreciated_value if parent_moves else self.parent_id.already_depreciated_amount_import_ifrs
                parent_depreciable_value = parent_moves[-1].asset_remaining_value if parent_moves else self.parent_id.total_depreciable_value_ifrs
                if self.currency_id.is_zero(parent_depreciable_value):
                    linear_amount = self._get_linear_amount_ifrs(days_before_period, days_until_period_end, self.total_depreciable_value_ifrs)
                else:
                    # To have the same curve as the parent, we need to have the equivalent amount before the reeval.
                    # The child's depreciable value corresponds to the amount that is left to depreciate for the parent.
                    # So, we use the proportion between them to compute the equivalent child's total to depreciate.
                    # We use it then with the duration of the parent to compute the depreciation amount
                    depreciable_value = self.total_depreciable_value_ifrs * (1 + parent_cumulative_depreciation/parent_depreciable_value)
                    linear_amount = self._get_linear_amount_ifrs(days_before_period, days_until_period_end, depreciable_value) * self.asset_lifetime_days_ifrs / self.parent_id.asset_lifetime_days_ifrs

            amount = _get_max_between_linear_and_degressive(linear_amount)

        amount = max(amount, 0) if self.currency_id.compare_amounts(residual_amount, 0) > 0 else min(amount, 0)
        amount = self._get_depreciation_amount_end_of_lifetime_ifrs(residual_amount, amount, days_until_period_end)

        return number_days, self.currency_id.round(amount)

    def _get_linear_amount_ifrs(self, days_before_period, days_until_period_end, total_depreciable_value):

        amount_expected_previous_period = total_depreciable_value * days_before_period / self.asset_lifetime_days_ifrs
        amount_after_expected = total_depreciable_value * days_until_period_end / self.asset_lifetime_days_ifrs
        number_days_for_period = days_until_period_end - days_before_period
        # In case of a decrease, we need to lower the amount of the depreciation with the amount of the decrease
        # spread over the remaining lifetime
        amount_of_decrease_spread_over_period = [
            number_days_for_period * mv.depreciation_value / (self.asset_lifetime_days_ifrs - self._get_delta_days_ifrs(self.paused_prorata_date_ifrs, mv.asset_depreciation_beginning_date))
            for mv in self.ifrs_depreciation_move_ids.filtered(lambda mv: mv.asset_value_change)
        ]
        computed_linear_amount = self.currency_id.round(amount_after_expected - self.currency_id.round(amount_expected_previous_period) - sum(amount_of_decrease_spread_over_period))
        return computed_linear_amount

    def _get_depreciation_amount_end_of_lifetime_ifrs(self, residual_amount, amount, days_until_period_end):
        if abs(residual_amount) < abs(amount) or days_until_period_end >= self.asset_lifetime_days_ifrs:
            # If the residual amount is less than the computed amount, we keep the residual amount
            # If total_days is greater or equals to asset lifetime days, it should mean that
            # the asset will finish in this period and the value for this period is equal to the residual amount.
            amount = residual_amount
        return amount

    def set_to_cancelled(self):
        for record in self:
            record.ifrs_depreciation_move_ids.filtered(lambda m: m.state == 'draft').with_context(force_delete=True).unlink()
            record.asset_paused_days_ifrs = 0
        return super().set_to_cancelled()

    # REPORT
    def _get_name_invoices(self):
        names = ''
        for move in self.original_move_line_ids:
            if not names:
                names = move.move_id.name
            else:
                names += ', ' +  move.move_id.name
        return names

    def _get_month_purchase(self):
        months = [
            'ENERO',
            'FEBRERO',
            'MARZO',
            'ABRIL',
            'MAYO',
            'JUNIO',
            'JULIO',
            'AGOSTO',
            'SEPTIEMBRE',
            'OCTUBRE',
            'NOVIEMBRE',
            'DICIEMBRE'
        ]
        return months[self.acquisition_date.month - 1]

    def _get_year_purchase(self):
        return self.acquisition_date.year

    def get_depretiation_last_year(self):
        today = date.today()
        last_date_year = today.replace(day=31, month=12, year=today.year-1)
        moves = self.depreciation_move_ids.filtered(lambda x: x.date <= last_date_year and x.state == 'posted')
        return sum([x.depreciation_value for x in moves])

    def get_depretiation_current_year(self):
        today = date.today()
        date_from = today.replace(day=1, month=1)
        date_to = today.replace(day=31, month=12)
        moves = self.depreciation_move_ids.filtered(lambda x: x.date >= date_from and x.date <= date_to and x.state == 'posted')
        return sum([x.depreciation_value for x in moves])

    def get_depretiation_in_month(self, month):
        if not 1 <= month <= 12:
            raise ValueError("El mes debe estar entre 1 y 12.")
        
        current_year = datetime.datetime.now().year
        _, last_day = calendar.monthrange(current_year, month)
        
        date_from = date(current_year, month, 1)
        date_to = date(current_year, month, last_day)

        moves = self.depreciation_move_ids.filtered(lambda x: x.date >= date_from and x.date <= date_to and x.state == 'posted')
        return sum([x.depreciation_value for x in moves])

    def get_depretiation_residual(self):
        return self.original_value - self.get_depretiation_current_year()
