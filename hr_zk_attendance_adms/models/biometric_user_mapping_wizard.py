# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class BiometricUserMappingWizard(models.TransientModel):
    _name = 'biometric.user.mapping.wizard'
    _description = 'Asistente de Mapeo de Usuarios del Biométrico'

    device_id = fields.Many2one('biometric.device.details', string='Dispositivo', required=True, readonly=True)
    total_count = fields.Integer(string='Total Usuarios', compute='_compute_counts')
    mapped_count = fields.Integer(string='Mapeados', compute='_compute_counts')
    unmapped_count = fields.Integer(string='Sin Mapear', compute='_compute_counts')
    line_ids = fields.One2many('biometric.user.mapping.wizard.line', 'wizard_id', string='Usuarios en Reloj')

    @api.depends('line_ids', 'line_ids.status')
    def _compute_counts(self):
        for rec in self:
            rec.total_count = len(rec.line_ids)
            rec.mapped_count = len(rec.line_ids.filtered(lambda l: l.status == 'mapped'))
            rec.unmapped_count = len(rec.line_ids.filtered(lambda l: l.status == 'unmapped'))

    def action_create_all_unmapped(self):
        """Crea empleados en Odoo para todos los usuarios sin mapear en este biométrico."""
        self.ensure_one()
        unmapped_lines = self.line_ids.filtered(lambda l: l.status == 'unmapped')
        if not unmapped_lines:
            raise UserError(_("No hay usuarios pendientes por mapear."))

        Employee = self.env['hr.employee']
        MappingModel = self.env['biometric.user.mapping']
        count = 0

        for line in unmapped_lines:
            emp_name = line.device_user_name
            if not emp_name or emp_name.startswith("Usuario en Reloj") or emp_name == _("N/A"):
                emp_name = f"Empleado {line.device_user_id}"

            # Liberar PIN si estaba asignado por error a otro empleado
            conflicting = Employee.search([('device_id_num', '=', line.device_user_id)])
            for old_emp in conflicting:
                old_emp.with_context(skip_biometric_sync=True).write({'device_id_num': False})

            emp = Employee.with_context(skip_biometric_sync=True).create({
                'name': emp_name,
                'device_id_num': line.device_user_id,
            })

            line.write({
                'employee_id': emp.id,
                'status': 'mapped'
            })
            if line.mapping_id:
                line.mapping_id.write({
                    'employee_id': emp.id,
                    'status': 'mapped'
                })
            count += 1

        return self._reopen_wizard()

    def action_auto_map_by_biometric_id(self):
        """Busca empleados en Odoo con el mismo ID Biométrico (device_id_num) y los vincula automáticamente."""
        self.ensure_one()
        unmapped_lines = self.line_ids.filtered(lambda l: l.status == 'unmapped')
        Employee = self.env['hr.employee']
        count = 0

        for line in unmapped_lines:
            pin = (line.device_user_id or '').strip()
            if pin:
                emp = Employee.search([('device_id_num', '=', pin)], limit=1)
                if emp:
                    line.write({
                        'employee_id': emp.id,
                        'status': 'mapped'
                    })
                    if line.mapping_id:
                        line.mapping_id.write({
                            'employee_id': emp.id,
                            'status': 'mapped'
                        })
                    count += 1

        return self._reopen_wizard()

    def _reopen_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Mapeo de Usuarios: %s') % self.device_id.name,
            'res_model': 'biometric.user.mapping.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class BiometricUserMappingWizardLine(models.TransientModel):
    _name = 'biometric.user.mapping.wizard.line'
    _description = 'Línea de Mapeo de Usuario en Asistente'
    _order = 'status desc, cast_pin asc, id asc'

    wizard_id = fields.Many2one('biometric.user.mapping.wizard', required=True, ondelete='cascade')
    mapping_id = fields.Many2one('biometric.user.mapping', string='Registro Base', ondelete='cascade')
    device_user_id = fields.Char(string='ID / PIN', required=True)
    device_user_name = fields.Char(string='Nombre en Biométrico')
    employee_id = fields.Many2one('hr.employee', string='Empleado de Odoo')
    status = fields.Selection([
        ('mapped', 'Mapeado (OK)'),
        ('unmapped', 'Sin Mapear (FALTA)'),
    ], string='Estado', default='unmapped', required=True)
    cast_pin = fields.Integer(string='PIN Numérico', compute='_compute_cast_pin', store=True)

    @api.depends('device_user_id')
    def _compute_cast_pin(self):
        for rec in self:
            try:
                rec.cast_pin = int(rec.device_user_id) if rec.device_user_id and rec.device_user_id.isdigit() else 999999999
            except Exception:
                rec.cast_pin = 999999999

    def write(self, vals):
        res = super().write(vals)
        if 'employee_id' in vals:
            for rec in self:
                if rec.employee_id:
                    conflicting = self.env['hr.employee'].search([
                        ('device_id_num', '=', rec.device_user_id),
                        ('id', '!=', rec.employee_id.id)
                    ])
                    for old_emp in conflicting:
                        old_emp.with_context(skip_biometric_sync=True).write({'device_id_num': False})

                    rec.employee_id.with_context(skip_biometric_sync=True).write({'device_id_num': rec.device_user_id})
                    if rec.status != 'mapped':
                        super(BiometricUserMappingWizardLine, rec).write({'status': 'mapped'})
                    if rec.mapping_id:
                        rec.mapping_id.write({'employee_id': rec.employee_id.id, 'status': 'mapped'})
                else:
                    if rec.status != 'unmapped':
                        super(BiometricUserMappingWizardLine, rec).write({'status': 'unmapped'})
                    if rec.mapping_id:
                        rec.mapping_id.write({'employee_id': False, 'status': 'unmapped'})
        return res

    def action_create_employee(self):
        """Crea un empleado para esta fila individual."""
        self.ensure_one()
        if self.employee_id:
            raise UserError(_("Este usuario ya tiene un empleado asignado."))

        emp_name = self.device_user_name
        if not emp_name or emp_name.startswith("Usuario en Reloj") or emp_name == _("N/A"):
            emp_name = f"Empleado {self.device_user_id}"

        # Liberar PIN previo incompatible
        conflicting = self.env['hr.employee'].search([('device_id_num', '=', self.device_user_id)])
        for old_emp in conflicting:
            if not self.env['biometric.user.mapping'].is_name_compatible(emp_name, old_emp.name):
                old_emp.with_context(skip_biometric_sync=True).write({'device_id_num': False})

        emp = self.env['hr.employee'].with_context(skip_biometric_sync=True).create({
            'name': emp_name,
            'device_id_num': self.device_user_id,
        })
        self.write({
            'employee_id': emp.id,
            'status': 'mapped'
        })
        if self.mapping_id:
            self.mapping_id.write({
                'employee_id': emp.id,
                'status': 'mapped'
            })

        return self.wizard_id._reopen_wizard()

    def action_delete_user_from_device(self):
        """Elimina el usuario del biométrico y de la lista."""
        self.ensure_one()
        if self.mapping_id:
            self.mapping_id.action_delete_user_from_device()
        wizard = self.wizard_id
        self.unlink()
        return wizard._reopen_wizard()
