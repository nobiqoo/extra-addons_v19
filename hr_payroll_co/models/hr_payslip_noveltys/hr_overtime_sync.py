# -*- coding: utf-8 -*-
from odoo import models, fields, api


class HrOvertimeSync(models.Model):
    _name = 'hr.overtime.sync'
    _description = 'Sincronización de Horas Extra'
    _inherit = ['mail.thread']
    _order = 'id desc'

    name = fields.Char(string='Nombre', readonly=True, tracking=True)
    send_date = fields.Datetime(string='Fecha de envío', required=True, readonly=True, tracking=True,
                                default=fields.Datetime.now)
    payload_json = fields.Text(string='JSON enviado', readonly=True)
    line_ids = fields.One2many(
        comodel_name='hr.overtime', inverse_name='overtime_sync_id', string='Horas extras')
    line_count = fields.Integer(string='Cantidad de líneas', compute='_compute_line_count')

    @api.depends('line_ids')
    def _compute_line_count(self):
        for record in self:
            record.line_count = len(record.line_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name'] = self.env['ir.sequence'].next_by_code('seq.hr.overtime.sync') or '/'
        return super(HrOvertimeSync, self).create(vals_list)
