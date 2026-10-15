from odoo import models

class AccountMove(models.Model):
    _inherit = 'account.move'

    def return_total_without_retentions(self):
        total = 0

        amounts = self.tax_totals
        subtotals = amounts['subtotals']
        for sub in subtotals:
            if ('tax_groups' in sub):
                for g in sub['tax_groups']:
                    if g['tax_amount_currency'] > 0:
                        total += g['tax_amount_currency']

            total += sub['base_amount_currency']

        return total