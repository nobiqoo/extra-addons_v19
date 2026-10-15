# -*- coding: utf-8 -*-
from odoo import api, fields, models

class MaintenanceMileageLog(models.Model):
    _name = 'maintenance.mileage.log'
    _description = 'Histórico de Horómetro/Kilometraje'
    _order = 'create_date desc, id desc'

    product_maintenance_id = fields.Many2one(
        'product.maintenance',
        string='Equipo',
        required=True,
        index=True,
        ondelete='cascade',
    )

    date = fields.Datetime(string='Fecha', default=lambda self: fields.Datetime.now(), required=True, readonly=True)
    user_id = fields.Many2one('res.users', string='Usuario', default=lambda self: self.env.user, required=True, readonly=True)
    old_value = fields.Float(string='Valor anterior', digits='Product Unit of Measure', readonly=True)
    new_value = fields.Float(string='Valor nuevo', digits='Product Unit of Measure', readonly=True)
    delta = fields.Float(string='Diferencia', compute='_compute_delta', store=False)
    note = fields.Char(string='Nota')

    @api.depends('old_value', 'new_value')
    def _compute_delta(self):
        for rec in self:
            rec.delta = (rec.new_value or 0.0) - (rec.old_value or 0.0)
