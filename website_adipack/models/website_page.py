from odoo import fields, models


class WebsitePage(models.Model):
    _inherit = 'website.page'

    adipack_english = fields.Boolean(
        string="Página en inglés",
        help="Muestra el menú en inglés del sitio en esta página, como en el sitio original de Adipack.",
    )
