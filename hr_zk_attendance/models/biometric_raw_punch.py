# -*- coding: utf-8 -*-
import logging

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


_logger = logging.getLogger(__name__)

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

    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
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

    zk_attendance_id = fields.Many2one(
        'zk.machine.attendance',
        string='Marcación procesada',
        readonly=True,
        index=True,
        ondelete='set null',
        help='Marcación generada en zk.machine.attendance al procesar este registro.',
    )

    source = fields.Selection([
        ('zk', 'ZKTeco'),
        ('api', 'API'),
        ('manual', 'Manual'),
    ], default='zk', string='Origen')

    active = fields.Boolean(default=True)

    punch_time_display = fields.Char(
        string='Hora Local',
        compute='_compute_punch_time_display',
        help="Hora convertida a la zona horaria de la compañía, independiente del navegador."
    )

    @api.depends('punch_time')
    def _compute_punch_time_display(self):
        for rec in self:
            if not rec.punch_time:
                rec.punch_time_display = ''
                continue

            # Obtener TZ de la compañia (via user/employee logic o default UTC)
            # Como esto es raw punch, intentamos ir al user_id -> company -> partner
            # Si no, usamos UTC.
            tz_name = 'UTC'
            if rec.user_id and rec.user_id.tz:
                tz_name = rec.user_id.tz
            elif self.env.user.company_id.partner_id.tz:
                tz_name = self.env.user.company_id.partner_id.tz

            try:
                user_tz = pytz.timezone(tz_name)
                # Odoo Datetime is naive UTC in database
                utc_dt = pytz.utc.localize(rec.punch_time)
                local_dt = utc_dt.astimezone(user_tz)
                rec.punch_time_display = local_dt.strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                rec.punch_time_display = str(rec.punch_time)

    def _find_employee_for_processing(self):
        """Return the employee explicitly assigned or matched by biometric ID."""
        self.ensure_one()
        if self.employee_id:
            return self.employee_id.sudo()

        biometric_id = (self.biometric_id or '').strip()
        if not biometric_id:
            return self.env['hr.employee']

        Employee = self.env['hr.employee'].sudo().with_context(active_test=False)
        employees = Employee.search([('device_id_num', '=', biometric_id)], limit=2)
        if not employees:
            normalized_id = biometric_id.lstrip('0') or '0'
            if normalized_id != biometric_id:
                employees = Employee.search(
                    [('device_id_num', '=', normalized_id)],
                    limit=2,
                )
        return employees if len(employees) == 1 else self.env['hr.employee']

    def _find_processed_attendance(self):
        """Busca la marcación procesada, incluyendo registros anteriores al vínculo."""
        self.ensure_one()
        if self.zk_attendance_id:
            return self.zk_attendance_id

        employee = self._find_employee_for_processing()
        if not employee or not self.punch_time:
            return self.env['zk.machine.attendance']

        biometric_id = (employee.device_id_num or self.biometric_id or '').strip()
        if not biometric_id:
            return self.env['zk.machine.attendance']

        ZKAttendance = self.env['zk.machine.attendance'].sudo()
        hash_key = ZKAttendance.compute_hash(
            employee.id,
            biometric_id,
            self.punch_time,
        )
        return ZKAttendance.search([
            '|',
            ('hash_key', '=', hash_key),
            '&',
            ('employee_id', '=', employee.id),
            ('punching_time', '=', self.punch_time),
        ], limit=1)

    def action_process_imported_punches(self):
        """Transfer selected raw punches to zk.machine.attendance safely."""
        if not self.env.su and not self.env.user.has_group(
            'hr_zk_attendance.group_biometric_raw_punch_importer'
        ):
            raise AccessError(
                _('No tiene permisos para procesar marcaciones importadas.')
            )
        if not self:
            raise UserError(_('Seleccione al menos una marcación para procesar.'))

        ZKAttendance = self.env['zk.machine.attendance'].sudo()
        created = 0
        duplicates = 0
        missing_employee = 0
        missing_biometric_id = 0
        corrected_ids = 0
        errors = 0

        for raw in self.exists():
            employee = raw._find_employee_for_processing()
            if not employee:
                missing_employee += 1
                continue

            biometric_id = (employee.device_id_num or '').strip()
            if not biometric_id:
                missing_biometric_id += 1
                continue

            hash_key = ZKAttendance.compute_hash(
                employee.id,
                biometric_id,
                raw.punch_time,
            )
            update_vals = {}
            if raw.employee_id != employee:
                update_vals['employee_id'] = employee.id
            corrects_biometric_id = raw.biometric_id != biometric_id
            if corrects_biometric_id:
                update_vals['biometric_id'] = biometric_id

            existing = ZKAttendance.search([
                '|',
                ('hash_key', '=', hash_key),
                '&',
                ('employee_id', '=', employee.id),
                ('punching_time', '=', raw.punch_time),
            ], limit=1)
            if existing:
                if raw.zk_attendance_id != existing:
                    update_vals['zk_attendance_id'] = existing.id
                if update_vals:
                    try:
                        with self.env.cr.savepoint():
                            raw.sudo().write(update_vals)
                        corrected_ids += int(corrects_biometric_id)
                    except Exception:
                        errors += 1
                        _logger.exception(
                            'No fue posible actualizar biometric.raw.punch ID %s',
                            raw.id,
                        )
                duplicates += 1
                continue

            try:
                with self.env.cr.savepoint():
                    created_attendance = ZKAttendance.create({
                        'employee_id': employee.id,
                        'device_id_num': biometric_id,
                        'punching_time': raw.punch_time,
                        'address_id': raw.device_id.address_id.id,
                        'source_device_id': raw.device_id.id,
                        'hash_key': hash_key,
                    })
                    update_vals['zk_attendance_id'] = created_attendance.id
                    if update_vals:
                        raw.sudo().write(update_vals)
                    created += 1
                    corrected_ids += int(corrects_biometric_id)
            except Exception:
                errors += 1
                _logger.exception(
                    'No fue posible procesar biometric.raw.punch ID %s',
                    raw.id,
                )

        message = _(
            'Resultado del procesamiento:\n'
            '• Creadas: %(created)s\n'
            '• Duplicadas: %(duplicates)s\n'
            '• Sin empleado relacionado: %(missing_employee)s\n'
            '• Empleado sin ID biométrico: %(missing_biometric_id)s\n'
            '• IDs biométricos corregidos: %(corrected_ids)s\n'
            '• Errores: %(errors)s',
            created=created,
            duplicates=duplicates,
            missing_employee=missing_employee,
            missing_biometric_id=missing_biometric_id,
            corrected_ids=corrected_ids,
            errors=errors,
        )
        has_issues = bool(missing_employee or missing_biometric_id or errors)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Marcaciones importadas'),
                'message': message,
                'type': 'warning' if has_issues else 'success',
                'sticky': has_issues,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

    def unlink(self):
        """Elimina también la marcación procesada que corresponde al registro crudo."""
        raw_records = self.exists()
        processed_attendances = self.env['zk.machine.attendance']
        for raw in raw_records:
            processed_attendances |= raw._find_processed_attendance()

        result = super().unlink()

        RawPunch = self.env['biometric.raw.punch'].sudo()
        for attendance in processed_attendances.exists():
            still_linked = RawPunch.search_count([
                '|',
                ('zk_attendance_id', '=', attendance.id),
                '&',
                ('punch_time', '=', attendance.punching_time),
                '|',
                ('employee_id', '=', attendance.employee_id.id),
                ('biometric_id', '=', attendance.device_id_num),
            ])
            if not still_linked:
                attendance.sudo().unlink()

        return result
