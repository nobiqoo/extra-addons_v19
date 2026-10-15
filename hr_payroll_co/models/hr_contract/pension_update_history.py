# -*- coding: utf-8 -*-
from odoo import api, fields, models

LAST_ONE = -1


class PensionUpdateHistory(models.Model):
    _name = 'pension.update.history'
    _order = 'date desc'
    _rec_name = "date"
    _description = 'Histórico de Cambios de Fondo de Pension'

    contract_id = fields.Many2one(
        string='Contrato', comodel_name='hr.contract', required=True)
    afp_pension_id = fields.Many2one(
        string='Fondo de Pensiones', comodel_name='res.partner',
        domain="[('afp','=','True')]", required=True)
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
        res = super(PensionUpdateHistory, self).create(vals_list)
        for vals in vals_list:
            contract_id = vals.get('contract_id', False)
            histories = self.search([('contract_id', '=', contract_id)]).sorted(
                lambda hist: hist.date)
            afp_pension_id = (histories[LAST_ONE].afp_pension_id.id
                            if histories
                            else vals.get('afp_pension_id', False))
            self.env['hr.contract'].browse([contract_id]).write(
                {'afp_pension_id': afp_pension_id})
        return res
