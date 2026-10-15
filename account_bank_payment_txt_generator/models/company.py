from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ResCompany(models.Model):
    _inherit = 'res.company'

    hide_txt_in_draft = fields.Boolean(
        string='Ocultar TXT en borrador',
        help='Si está activo, no se mostrará el botón TXT cuando la orden de pago esté en borrador.'
    )

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    hide_txt_in_draft = fields.Boolean(
        string='Ocultar TXT en borrador',
        related='company_id.hide_txt_in_draft',
        readonly=False
    )