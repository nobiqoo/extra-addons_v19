# -*- coding: utf-8 -*-
from odoo import models, fields, api
import pytz

class BiometricRawPunch(models.Model):
    _name = 'biometric.raw.punch'
    _description = 'Biometric Raw Punch'
    _order = 'punch_time desc'

    user_id = fields.Many2one(
        'res.partner',
        string='Usuario',
        required=False,
        index=True,
    )

    biometric_id = fields.Char(
        string='Biometric User ID',
        required=True,
        index=True,
    )

    punch_time = fields.Datetime(
        string='Hora de marcación',
        required=True,
        index=True,
    )

    device_id = fields.Many2one(
        'biometric.device.details',
        string='Dispositivo',
        required=True,
        index=True,
    )

    source = fields.Selection([
        ('zk', 'ZKTeco (ADMS/Push)'),
        ('api', 'API'),
        ('manual', 'Manual'),
    ], default='zk', string='Origen')

    active = fields.Boolean(default=True)

    punch_time_display = fields.Char(
        string='Hora Local',
        compute='_compute_punch_time_display',
        help="Hora convertida a la zona horaria del dispositivo o de la compañía."
    )

    @api.depends('punch_time', 'device_id')
    def _compute_punch_time_display(self):
        for rec in self:
            if not rec.punch_time:
                rec.punch_time_display = ''
                continue

            tz_name = 'America/Bogota'
            if rec.device_id and rec.device_id.device_timezone:
                tz_name = rec.device_id.device_timezone
            elif rec.user_id and rec.user_id.tz:
                tz_name = rec.user_id.tz
            elif self.env.user.company_id.partner_id.tz:
                tz_name = self.env.user.company_id.partner_id.tz

            try:
                user_tz = pytz.timezone(tz_name)
                utc_dt = pytz.utc.localize(rec.punch_time)
                local_dt = utc_dt.astimezone(user_tz)
                rec.punch_time_display = local_dt.strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                rec.punch_time_display = str(rec.punch_time)
