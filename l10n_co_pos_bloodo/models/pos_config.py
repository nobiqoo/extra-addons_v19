# -*- coding: utf-8 -*-

from odoo import models, fields, api


class PosConfig(models.Model):
    _inherit = 'pos.config'

    def _default_einvoice_journal(self):
        return self.env['account.journal'].search([('type','=','sale'),
                                                   ('company_id','=',self.env.company.id),
                                                   ('is_einvoicing','=',True)],
                                                  limit=1)

    einvoicing = fields.Boolean('Electronic invoicing',
                              default=False)
    einvoice_journal_id = fields.Many2one('account.journal',
                                    'Electronic invoice journal',
                                    domain=[('type','=','sale'),
                                            ('is_einvoicing','=',True)],
                                    help='Journal used for the creation of electronic invoices')
    default_check_invoice = fields.Selection(
                                    [('invoice', 'Invoice'),
                                     ('einvoice', 'Electronic invoice')],
                                    'Create default invoice')

    @api.onchange('einvoicing')
    def _onchange_einvoicing(self):
        if self.einvoicing and not self.einvoice_journal_id:
            self.einvoice_journal_id = self._default_einvoice_journal()