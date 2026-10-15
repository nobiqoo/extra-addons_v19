# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    import_type = fields.Selection(
        selection=[
            ('insurance', 'Seguro'),
            ('freight', 'Flete'),
            ('tariff', 'Arancel'),
            ('tax', 'Impuestos'),
            ('expense', 'Gasto'),
        ],
        string='Cost Type',
    )

    tariffes_ids = fields.Many2many(
        comodel_name='account.tax',
        relation='template_tax_rel',
        column1='template_id',
        column2='tax_id',
        string='Taxes'
    )

    tariff_ids = fields.One2many(
        comodel_name='product.template.tariff',
        inverse_name='template_id',
        string='Tariffes'
    )

    def get_tariff_ids(self, country):
        self.ensure_one()
        tariff_ids = self.tariff_ids.filtered(
            lambda t: t.country_id.id == country.id
        )
        return tariff_ids.taxes_ids


class ProductTemplateTariff(models.Model):
    _name = 'product.template.tariff'
    _description = 'Tariffes'

    country_id = fields.Many2one(
        comodel_name='res.country',
        required=True,
        copy=False,
    )

    template_id = fields.Many2one(
        comodel_name='product.template',
        required=True,
        copy=False,
    )

    taxes_ids = fields.Many2many('account.tax')
