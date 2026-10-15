# -*- coding: utf-8 -*-
from odoo import models, fields, api

EMPLOYEE_EMERGENCY_HELP = "Empleado al que este contacto le sirve para alguna emergencia"


class ResPartner(models.Model):
    _inherit = "res.partner"

    employee = fields.Boolean(
        help="Check this box if this contact is an Employee.", readonly=True)
    employee2emergency_id = fields.Many2one(
        'hr.employee', string="Es contacto de emergencia de", help=EMPLOYEE_EMERGENCY_HELP)
    eps = fields.Boolean(string='Es EPS', default=False,
                         help='Entidad Promotora Salud')
    arl = fields.Boolean(string='Es ARL', default=False,
                         help='Administradora de Riesgos Laborales')
    afp = fields.Boolean(string='Es AFP', default=False,
                         help='Administradora Fondos Pensiones y Cesantías')
    ccf = fields.Boolean(string='Es CCF', default=False,
                         help='Caja Compensación Familiar')
    eps_code = fields.Char(string='Código de EPS')
    arl_code = fields.Char(string='Código de ARL')
    afp_code = fields.Char(string='Código de AFP')
    ccf_code = fields.Char(string='Código de CCF')
    main_bank_id = fields.Many2one('res.partner.bank',
                                   string='Banco Principal',
                                   compute='_compute_main_bank_id',
                                   store=True)
    active_contract_id = fields.Many2one(
        comodel_name='hr.contract',
        string='Contrato Activo',
        compute='_compute_active_contract_id',
        help=(
            "Contrato activo del empleado vinculado a este contacto. "
            "Si no tiene contrato activo, muestra el último contrato registrado."
        ),
    )

    @api.onchange('eps', 'arl', 'afp', 'ccf')
    def _onchange_eps_arl_afp_ccf(self):
        fields_eval = ['eps', 'arl', 'afp', 'ccf']
        for record in self:
            for fe in fields_eval:
                if not getattr(record, fe):
                    setattr(record, fe+'_code', '')

    def _compute_active_contract_id(self):
        HrEmployee = self.env['hr.employee'].sudo()
        HrContract = self.env['hr.contract'].sudo()
        for partner in self:
            employee = HrEmployee.search(
                [('partner_id', '=', partner.id)], limit=1
            )
            if not employee:
                partner.active_contract_id = False
                continue
            contract = HrContract.search(
                [('employee_id', '=', employee.id), ('state', '=', 'open')],
                limit=1,
                order='date_start desc',
            )
            if not contract:
                contract = HrContract.search(
                    [('employee_id', '=', employee.id)],
                    limit=1,
                    order='date_start desc',
                )
            partner.active_contract_id = contract

    @api.depends('employee', 'bank_ids')
    def _compute_main_bank_id(self):
        for record in self.filtered(lambda x: x.employee):
            if record.bank_ids:
                record.main_bank_id = record.bank_ids[0]
            else:
                record.main_bank_id = False

    def write(self, vals):
        if vals.get('name') and vals.get('name') == 'NOMBRE':
            vals.pop('name')
        return super().write(vals)