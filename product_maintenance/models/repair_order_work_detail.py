
# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class RepairOrderWorkDetail(models.Model):
    _name = 'repair.order.work.detail'
    _description = 'Detalle Trabajos Realizados en Reparacion'

    name = fields.Char(
        string='Nombre'
    )
    description = fields.Html(
        string='Descripción'
    )
    date = fields.Datetime(
        string='Fecha'
    )
    duration = fields.Float(
        string='Duración (h)'
    )
    repair_id = fields.Many2one(
        comodel_name='repair.order',
        string='Reparación'
    )
    activity_id = fields.Many2one(
        'maintenance.activity',
        string='Actividad',
        required=True,
        index=True,
        ondelete='restrict',
        help='Actividad del catálogo'
    )

    @api.constrains('duration')
    def _check_duration(self):
        for record in self:
            if record.duration <= 0:
                raise ValidationError('La duración debe ser superiror a cero horas.')

    def get_description(self):
        return self.env['helpdesk.ticket'].remove_p_tags(self.description)

    @api.onchange('activity_id')
    def _onchange_activity_id(self):
        for rec in self:
            if rec.activity_id:
                act = rec.activity_id
                # name visible
                rec.name = act.name
                # descripción si vacía
                if not rec.description:
                    rec.description = getattr(act, 'description', act.name)
                # duración sugerida
                default_time = (
                    getattr(act, 'default_duration', False)
                    or getattr(act, 'time_hours', False)
                    or getattr(act, 'estimated_time', False)
                    or 0.0
                )
                if default_time:
                    rec.duration = default_time

    @api.model_create_multi
    def create(self, vals_list):
        Act = self.env['maintenance.activity'].sudo()
        for vals in vals_list:
            # si viene activity_id y name vacío → autollenar
            if not vals.get('name') and vals.get('activity_id'):
                act = Act.browse(vals['activity_id'])
                vals['name'] = act.name or ''
        return super().create(vals_list)

    def write(self, vals):
        # primero escribe
        res = super().write(vals)
        # si cambiaron activity_id y name está vacío → autollenar
        if 'activity_id' in vals and not vals.get('name'):
            for rec in self:
                if rec.activity_id and (not rec.name or not rec.name.strip()):
                    rec.name = rec.activity_id.name or ''
        return res

