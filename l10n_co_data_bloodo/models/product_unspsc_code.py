# -*- coding: utf-8 -*-

from os.path import join, dirname, realpath
from odoo import fields, models, api, tools
from odoo.fields import Domain


class ProductCode(models.Model):
    """
    Product and UoM codes defined by UNSPSC
    Used by Mexico, Peru and Colombia localizations
    """
    _name = 'product.unspsc.dian_code'
    _description = "Product and UOM Codes from UNSPSC"

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True)
    applies_to = fields.Selection([('product', 'Product'),
                                   ('uom', 'UoM'),],
                                  'Aplica a',
                                  required=True,
                                  help='Indicate if this code could'
                                  ' be used in products or in UoM',)
    active = fields.Boolean()

    @api.depends('code')
    def _compute_display_name(self):
        for record in self:
            record.display_name = '%s%s' % (record.code and '[%s] ' % record.code or '', record.name)

    @api.model
    def _name_search(self, name, domain=None, operator='ilike',
                     limit=None, order=None):
        domain = domain or []
        if operator != 'ilike' and not (name or '').strip():
            domain = Domain.AND([['|', ('name', 'ilike', name),
                                      ('code', 'ilike', name)], domain])
        return self._search(domain, limit=limit, order=order)

    def _load_unspsc_codes(self):
        """Import CSV data as it is faster than xml and because we can't use
        noupdate anymore with csv
        Even with the faster CSVs, it would take +30 seconds to load it with
        the regular ORM methods, while here, it is under 3 seconds
        """
        csv_path = join(dirname(dirname(realpath(__file__))), 'data',
                        'product.unspsc.code.csv')
        csv_file = open(csv_path, 'rb')
        csv_file.readline()  # Read the header, so we avoid copying it to the db
        self.env.cr.copy_expert(
            """COPY product_unspsc_dian_code (code, name, applies_to, active)
            FROM STDIN WITH DELIMITER '|'""", csv_file)
        # Create xml_id, to allow make reference to this data
        self.env.cr.execute(
            """INSERT INTO ir_model_data
            (name, res_id, module, model, noupdate)
            SELECT concat('unspsc_code_', code), id,
            'l10n_co_data_bloodo', 'product.unspsc.dian_code', 't'
            FROM product_unspsc_dian_code""")
        
    def _assign_codes_uom(self):
        """Assign the codes in UoM of each data, this is here because the data is
        created in the last method"""
        tools.convert.convert_file(
            self.env, 'l10n_co_data_bloodo', 'data/uom_data.xml', None, mode='init',
            kind='data')
