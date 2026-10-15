from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare

class AccountAsset(models.Model):
    _inherit = 'account.move'

    ifrs_asset_id = fields.Many2one(
        'account.asset',
        string='Asset Iffrs'
    )

    @api.model
    def _prepare_move_for_asset_depreciation(self, vals):
        move_vals = super(
            AccountAsset, self)._prepare_move_for_asset_depreciation(vals)
        if vals['asset_id'].ifrs_type in ('local', 'both'):
            move_vals.update(ifrs_type='local')
        elif vals['asset_id'].ifrs_type == 'united':
            move_vals.update(ifrs_type='both')
        return move_vals

    @api.model
    def _prepare_move_for_asset_depreciation_ifrs(self, vals):
        missing_fields = {'ifrs_asset_id', 'amount', 'depreciation_beginning_date', 'date', 'asset_number_days'} - set(vals)
        if missing_fields:
            raise UserError(_('Some fields are missing %s', ', '.join(missing_fields)))
        asset = vals['ifrs_asset_id']
        analytic_distribution = asset.ifrs_analytic_distribution
        depreciation_date = vals.get('date', fields.Date.context_today(self))
        company_currency = asset.company_id.currency_id
        current_currency = asset.currency_id
        prec = company_currency.decimal_places
        amount_currency = vals['amount']
        amount = current_currency._convert(amount_currency, company_currency, asset.company_id, depreciation_date)
        # Keep the partner on the original invoice if there is only one
        partner = asset.original_move_line_ids.mapped('partner_id')
        partner = partner[:1] if len(partner) <= 1 else self.env['res.partner']
        move_line_1 = {
            'name': asset.name,
            'partner_id': partner.id,
            'account_id': asset.ifrs_account_depreciation_id.id,
            'debit': 0.0 if float_compare(amount, 0.0, precision_digits=prec) > 0 else -amount,
            'credit': amount if float_compare(amount, 0.0, precision_digits=prec) > 0 else 0.0,
            'currency_id': current_currency.id,
            'amount_currency': -amount_currency,
        }
        move_line_2 = {
            'name': asset.name,
            'partner_id': partner.id,
            'account_id': asset.ifrs_account_depreciation_expense_id.id,
            'credit': 0.0 if float_compare(amount, 0.0, precision_digits=prec) > 0 else -amount,
            'debit': amount if float_compare(amount, 0.0, precision_digits=prec) > 0 else 0.0,
            'currency_id': current_currency.id,
            'amount_currency': amount_currency,
        }
        # Only set the 'analytic_distribution' key if there is an analytic distribution on the asset.
        # Otherwise, it prevents the computation of the analytic distribution.
        if analytic_distribution:
            move_line_1['analytic_distribution'] = analytic_distribution
            move_line_2['analytic_distribution'] = analytic_distribution
        move_vals = {
            'partner_id': partner.id,
            'date': depreciation_date,
            'journal_id': asset.ifrs_journal_id.id,
            'line_ids': [(0, 0, move_line_1), (0, 0, move_line_2)],
            'ifrs_asset_id': asset.id,
            'ref': _("%s: depreciación", asset.name),
            'asset_depreciation_beginning_date': vals['depreciation_beginning_date'],
            'asset_number_days': vals['asset_number_days'],
            'name': '/',
            'asset_value_change': vals.get('asset_value_change', False),
            'move_type': 'entry',
            'currency_id': current_currency.id,
            'company_id': asset.company_id.id,
            'ifrs_type': vals['ifrs_type'],
        }
        return move_vals

    @api.depends('line_ids.balance', 'line_ids.ifrs_balance')
    def _compute_depreciation_value(self):
        for move in self:
            asset = (move.asset_id or move.ifrs_asset_id) or move.reversed_entry_id.asset_id  # reversed moves are created before being assigned to the asset
            if asset:
                if move.asset_id or move.reversed_entry_id.asset_id:
                    original_value = asset.original_value
                    salvage_value = asset.salvage_value
                    account_asset_id = asset.account_asset_id
                    account_depreciation_expense_id = asset.account_depreciation_expense_id
                    balance_field = 'balance'
                else:
                    original_value = asset.original_value_ifrs
                    salvage_value = asset.salvage_value_ifrs
                    account_asset_id = asset.ifrs_account_asset_id
                    account_depreciation_expense_id = asset.ifrs_account_depreciation_expense_id
                    balance_field = 'ifrs_balance'
                account_internal_group = 'expense'
                asset_depreciation = sum(
                    move.line_ids.filtered(lambda l: l.account_id.internal_group == account_internal_group or l.account_id == account_depreciation_expense_id).mapped(balance_field)
                )
                # Special case of closing entry - only disposed assets of type 'purchase' should match this condition
                # The condition on len(move.line_ids) is to avoid the case where there is only one depreciation move, and it is not a disposal move
                # The condition will be matched because a disposal move from a disposal move will always have more than 2 lines, unlike a normal depreciation move
                if any(
                    line.account_id == account_asset_id
                    and float_compare(-line.balance or -line.ifrs_balance, original_value, precision_rounding=asset.currency_id.rounding) == 0
                    for line in move.line_ids
                ) and len(move.line_ids) > 2:
                    asset_depreciation = (
                        original_value
                        - salvage_value
                        - (
                            move.line_ids[1].debit or move.line_ids[1].ifrs_debit if original_value > 0 else move.line_ids[1].credit or move.line_ids[1].ifrs_credit
                        ) * (-1 if original_value < 0 else 1)
                    )
            else:
                asset_depreciation = 0
            move.depreciation_value = asset_depreciation

    @api.depends('asset_id',
                 'ifrs_asset_id',
                 'depreciation_value',
                 'asset_id.total_depreciable_value',
                 'asset_id.already_depreciated_amount_import',
                 'state',
                 'ifrs_asset_id.total_depreciable_value_ifrs',
                 'ifrs_asset_id.already_depreciated_amount_import_ifrs',)
    def _compute_depreciation_cumulative_value(self):
        self.asset_depreciated_value = 0
        self.asset_remaining_value = 0

        # make sure to protect all the records being assigned, because the
        # assignments invoke method write() on non-protected records, which may
        # cause an infinite recursion in case method write() needs to read one
        # of these fields (like in case of a base automation)
        fields = [self._fields['asset_remaining_value'], self._fields['asset_depreciated_value']]
        with self.env.protecting(fields, self.asset_id.depreciation_move_ids):
            for asset in (self.asset_id + self.ifrs_asset_id):
                depreciated = 0
                if self.asset_id:
                    remaining = asset.total_depreciable_value - asset.already_depreciated_amount_import
                    moves = asset.depreciation_move_ids
                else:
                    remaining = asset.total_depreciable_value_ifrs - asset.already_depreciated_amount_import_ifrs
                    moves = asset.ifrs_depreciation_move_ids

                for move in moves.sorted(lambda mv: (mv.date, mv._origin.id)):
                    if move.state != 'cancel':
                        remaining -= move.depreciation_value
                        depreciated += move.depreciation_value
                    move.asset_remaining_value = remaining
                    move.asset_depreciated_value = depreciated
