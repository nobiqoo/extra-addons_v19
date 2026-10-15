# -*- coding: utf-8 -*-

import pytz
from dateutil import tz
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)


class IrSequence(models.Model):
    _inherit = 'ir.sequence'

    fiscal_position_local = fields.Boolean(
        'Posición Fiscal Local',
        related = 'company_id.fiscal_position_local',)

    edi_resolution_control = fields.Boolean(
        '¿Usar el control de resoluciones DIAN?', default=False)

    @api.model_create_multi
    def create(self, vals_list):
        rec = super(IrSequence, self).create(vals_list)
        for record in rec:
            if record.edi_resolution_control:
                record.check_active_resolution()
            record.check_date_range_ids()
        return rec

    def write(self, vals):
        res = super(IrSequence, self).write(vals)

        for record in self:
            if record.edi_resolution_control:
                record.check_active_resolution()
            record.check_date_range_ids()
        return res

    @api.onchange('edi_resolution_control')
    def onchange_edi_resolution_control(self):
        for record in self:
            if record.edi_resolution_control:
                record.use_date_range = True
                record.implementation = 'no_gap'

    def check_active_resolution(self):
        self.ensure_one()

        if self.edi_resolution_control:
            if self.padding != 0:
                self.padding = 0
            if self.implementation != 'no_gap':
                self.implementation = 'no_gap'
            if not self.use_date_range:
                self.use_date_range = True
            if self.suffix:
                self.suffix = False
            if self.number_increment != 1:
                self.number_increment = 1

            timezone = pytz.timezone(self.env.user.tz or 'America/Bogota')
            from_zone = tz.gettz('UTC')
            to_zone = tz.gettz(timezone.zone)
            current_date = datetime.now().replace(tzinfo=from_zone)
            current_date = current_date.astimezone(
                to_zone).strftime('%Y-%m-%d')

            for dr_id in self.date_range_ids:
                number_next_actual = dr_id.number_next_actual

                if (number_next_actual >= dr_id.number_from \
                    and number_next_actual <= dr_id.number_to \
                        and current_date >= str(dr_id.date_from) \
                            and current_date <= str(dr_id.date_to)):
                    if not dr_id.active_resolution:
                        dr_id.active_resolution = True
                    if dr_id.prefix != self.prefix:
                        dr_id.prefix = self.prefix
                else:
                    dr_id.active_resolution = False
                if not dr_id.prefix:
                    dr_id.prefix = self.prefix
        return True

    def check_date_range_ids(self):
        msg1 = _('La fecha final debe ser mayor o'
                 ' igual que la fecha inicial.')
        msg2 = _('El número final debe ser mayor o'
                 ' igual que el número inicial.')
        msg3 = _('El Número siguiente debe ser mayor en uno al número final,'
                 ' para representar una secuencia terminada o Número'
                 ' siguiente debe incluirse en el Rango de números.')
        msg4 = _('El intervalo de fechas debe ser único o no se debe incluir'
                 ' una fecha en otro intervalo de fechas.')
        msg5 = _('El sistema solo necesita una resolución DIAN activa.')
        msg6 = _('El sistema necesita al menos una resolución DIAN activa.')
        date_ranges = []
        _active_resolution = 0
        for dr_id in self.date_range_ids:
            if dr_id.date_from and dr_id.date_to:
                if dr_id.date_from > dr_id.date_to:
                    raise ValidationError(msg1)
                date_ranges.append(
                    (dr_id.date_from, dr_id.date_to))
            if dr_id.number_from and dr_id.number_to:
                if dr_id.number_from > dr_id.number_to:
                    raise ValidationError(msg2)
                elif (dr_id.number_next_actual > (dr_id.number_to + 1) \
                        or dr_id.number_from > dr_id.number_next_actual):
                    raise ValidationError(msg3)
            if dr_id.active_resolution and self.edi_resolution_control:
                _active_resolution += 1

        date_ranges.sort(key=lambda date_range: date_range[0])
        date_from = False
        date_to = False
        for date_range in date_ranges:
            if not date_from and not date_to:
                date_from = date_range[0]
                date_to = date_range[1]
                continue
            if date_to < date_range[0]:
                date_from = date_range[0]
                date_to = date_range[1]
            else:
                raise ValidationError(msg4)
        if self.edi_resolution_control:
            if _active_resolution > 1:
                raise ValidationError(msg5)
            if _active_resolution == 0:
                raise ValidationError(msg6)

    # def _next(self, sequence_date=None):
    #     msg = _('No existe una resolución de facturación autorizada activa.')
    #     date_ranges = self.date_range_ids.search(
    #         [('active_resolution', '=', True),
    #          ('sequence_id', '=', self.id)])
    #     if self.edi_resolution_control and not date_ranges:
    #         raise ValidationError(msg)
    #     # if self.edi_resolution_control:
    #     #     self.sudo().check_active_resolution()
    #     return super(IrSequence, self)._next(sequence_date=sequence_date)
