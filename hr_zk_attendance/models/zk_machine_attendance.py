# -*- coding: utf-8 -*-
from odoo import api, fields, models
import hashlib


class ZkMachineAttendance(models.Model):
    _name = 'zk.machine.attendance'
    _description = 'Biometric Raw Attendance Log'
    _order = 'punching_time asc'

    # =====================================================
    # 🔹 Identidad del evento biométrico (RAW)
    # =====================================================

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        index=True
    )

    device_id_num = fields.Char(
        string='Biometric User ID',
        required=True,
        index=True
    )

    punching_time = fields.Datetime(
        string='Punching Time',
        required=True,
        index=True
    )

    # =====================================================
    # 🔹 Metadata del evento (ZK)
    # =====================================================

    punch_type = fields.Selection([
        ('0', 'Check In'),
        ('1', 'Check Out'),
        ('2', 'Break Out'),
        ('3', 'Break In'),
        ('4', 'Overtime In'),
        ('5', 'Overtime Out'),
        ('255', 'Duplicate'),
    ], string='Punching Type')

    attendance_type = fields.Selection([
        ('1', 'Finger'),
        ('15', 'Face'),
        ('2', 'Type 2'),
        ('3', 'Password'),
        ('4', 'Card'),
        ('255', 'Duplicate'),
    ], string='Category')

    address_id = fields.Many2one(
        'res.partner',
        string='Working Address',
        index=True
    )

    source_device_id = fields.Many2one(
        'biometric.device.details',
        string='Source Biometric Device',
        index=True,
        ondelete='restrict',
        help='Biometric device from which this punch was downloaded'
    )



    # =====================================================
    # 🔹 Idempotencia (clave dura)
    # =====================================================

    hash_key = fields.Char(
        string='Hash Key',
        required=True,
        readonly=True,
        index=True
    )

    _uniq_hash = models.Constraint(
        'unique(hash_key)',
        'Duplicate biometric punch detected.',
    )

    # =====================================================
    # 🔹 Helpers
    # =====================================================

    @api.model
    def compute_hash(self, employee_id, device_id_num, punching_time):
        """
        Hash idempotente y estable:

        - Multi-biometrico
        - Multi-cron
        - Seguro ante reintentos
        """
        base = f'{employee_id}|{device_id_num}|{punching_time.isoformat()}'
        return hashlib.sha1(base.encode('utf-8')).hexdigest()
