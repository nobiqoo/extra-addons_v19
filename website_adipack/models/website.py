from odoo import fields, models
from odoo.http import request


class Website(models.Model):
    _inherit = 'website'

    adipack_menu_en_id = fields.Many2one(
        'website.menu',
        string="Menú en inglés",
        help="Menú principal que se muestra en las páginas marcadas como 'Página en inglés'.",
    )

    def _compute_menu(self):
        super()._compute_menu()
        if not request or not getattr(request, 'httprequest', None):
            return
        path = request.httprequest.path.rstrip('/') or '/'
        for website in self.filtered('adipack_menu_en_id'):
            is_english = self.env['website.page'].sudo().search_count([
                ('url', '=', path),
                ('adipack_english', '=', True),
                ('website_id', 'in', (False, website.id)),
            ], limit=1)
            if is_english:
                website.menu_id = website.adipack_menu_en_id
