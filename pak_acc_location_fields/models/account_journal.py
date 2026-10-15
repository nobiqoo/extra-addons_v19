from odoo import models, fields, api


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    is_guatemala_localization = fields.Boolean(
        string="Es localización Guatemala",
        compute="_compute_is_guatemala_localization",
        store=False  # No se debe almacenar porque depende del contexto del usuario
    )


    def _compute_is_guatemala_localization(self):
        active_company = self.env.company  # la compañía actualmente seleccionada
        for journal in self:
            journal.is_guatemala_localization = active_company.chart_template == 'gt'
