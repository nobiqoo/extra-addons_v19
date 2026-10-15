from odoo import _, api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    # pse_file_instructive = fields.Binary(
    #     string='Instructivo de Pago PSE',
    # )
    logo_1 = fields.Binary(string='Logo 1')
    logo_2 = fields.Binary(string='Logo 2')
    logo_3 = fields.Binary(string='Logo 3')
    logo_4 = fields.Binary(string='Logo 4')
    logo_5 = fields.Binary(string='Logo 5')
    logo_6 = fields.Binary(string='Logo 6')
