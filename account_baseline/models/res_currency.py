# -*- coding: utf-8 -*-

from odoo import _, models


class ResCurrency(models.Model):
    _inherit = "res.currency"

    # # TODO
    # def amount_to_text(self, amount):
    #     self.ensure_one()
    #     res = super(ResCurrency, self).amount_to_text(amount)
    #     formatted = "%.{0}f".format(self.decimal_places) % amount
    #     parts = formatted.partition('.')
    #     integer_value = int(parts[0])
    #     fractional_value = int(parts[2] or 0)

    #     currency_unit = {
    #         'Dollars': {
    #             '1': _('Dollar'),
    #             '2': _('Dollars'),
    #         },
    #         'Cents': {
    #             '1': _('Cent'),
    #             '2': _('Cents'),
    #         },
    #     }
    #     # units
    #     if currency_unit.get(self.currency_unit_label) and \
    #             self.currency_unit_label in res:
    #         if integer_value != 1:
    #             res = res.replace(self.currency_unit_label,
    #                               currency_unit[self.currency_unit_label]['2'])
    #         else:
    #             res = res.replace(self.currency_unit_label,
    #                               currency_unit[self.currency_unit_label]['1'])
    #     # subunits
    #     if currency_unit.get(self.currency_subunit_label) and \
    #             self.currency_subunit_label in res:
    #         if fractional_value != 1:
    #             res = res.replace(
    #                 self.currency_subunit_label,
    #                 currency_unit[self.currency_subunit_label]['2']
    #             )
    #         else:
    #             res = res.replace(
    #                 self.currency_subunit_label,
    #                 currency_unit[self.currency_subunit_label]['1']
    #             )

    #     return res
