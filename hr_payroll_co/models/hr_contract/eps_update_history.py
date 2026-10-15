# -*- coding: utf-8 -*-
from odoo import api, fields, models

LAST_ONE = -1


class EPSUpdateHistory(models.Model):
    _name = 'eps.update.history'
    _order = 'date desc'
    _rec_name = "date"
    _description = 'Historico de Cambios de EPS'

    contract_id = fields.Many2one(
        string='Contrato', comodel_name='hr.contract', required=True)
    eps_id = fields.Many2one(string='EPS', comodel_name='res.partner',
                             domain="[('eps','=','True')]", required=True)
    date = fields.Date(
        string='Fecha', default=fields.Date.today(), required=True)
    user_id = fields.Many2one(string='Responsable', comodel_name='res.users',
                              default=lambda self: self.env.user,
                              required=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', 'Company',
        default=lambda self: self.env.company,
        index=True, required=True)

    @api.model_create_multi
    def create(self, vals_list):
        res = super(EPSUpdateHistory, self).create(vals_list)
        for vals in vals_list:
            contract_id = vals.get('contract_id', False)
            histories = self.search([('contract_id', '=', contract_id)]).sorted(
                lambda hist: hist.date)
            eps_id = (histories[LAST_ONE].eps_id.id
                    if histories
                    else vals.get('eps_id', False))
            self.env['hr.contract'].browse([contract_id]).write(
                {'eps_id': eps_id})
        return res
