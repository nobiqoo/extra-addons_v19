
from odoo import models, fields, api
from datetime import timedelta
from odoo.exceptions import ValidationError
from collections import defaultdict
from dateutil.relativedelta import relativedelta
from math import ceil

class MaintenanceContract(models.Model):
    _name = 'maintenance.contract'
    _description = 'Contrato de Mantenimiento'

    contract_name = fields.Char('Nombre del Contrato')
    contract_number = fields.Char('Número del Contrato')
    contract_partner_id = fields.Many2one('res.partner', string='Cliente')
    contract_period = fields.Selection([
        ('monthly', 'Mensual'),
        ('quarterly', 'Trimestral'),
        ('annual', 'Anual')
    ], string='Periodo del Contrato')
    contract_start_date = fields.Date('Fecha Inicial del Contrato')
    contract_end_date = fields.Date('Fecha Final del Contrato')
    maintenance_type = fields.Selection([
        ('pre_inst', 'Pre-Instalación'),
        ('correctives', 'Correctivos'),
        ('precentive', 'Preventivos'),
        ('instalaciones', 'Instalaciones'),
        ('consultaciones', 'Consultaciones'),
        ('diagnosis', 'Diagnóstico'),
        ('inicial_review', 'Revisión Inicial'),
    ], string='Tipo de Mantenimiento')
    strategy_type = fields.Selection([
        ('period', 'Periodo'),
        ('tempario', 'Tempario')
    ], string='Tipo de Estrategia')

    period_start_date = fields.Date('Fecha de inicio del periodo')
    period_end_date = fields.Date('Fecha de fin del periodo')
    tempario_start_date = fields.Date('Fecha de inicio del tempario')
    tempario_end_date = fields.Date('Fecha de fin del tempario')
    period_frequency = fields.Selection([
        ('day', 'Día'),
        ('month', 'Mes'),
        ('year', 'Año')
    ], string='Frecuencia')
    period_interval = fields.Integer('Cada Cuánto')
    period_tempario_ids = fields.Many2many('maintenance.tempario', string='Temparios Aplicados')
    contract_equipment_ids = fields.Many2many(
        comodel_name='product.maintenance',
        relation='maintenance_contract_equipment_rel',
        column1='contract_id',
        column2='equipment_id',
        string='Equipos del Contrato'
    )
    active = fields.Boolean(default=True)
    assigned_employee_ids = fields.Many2many(
        'hr.employee',
        string='Empleados Asignados'
    )
    is_weekend = fields.Boolean(
        string='Fin de semana',
        help='La fecha cae en sábado o domingo.'
    )

    @api.onchange('product_maintenance_id')
    def _onchange_equipment(self):
        if self.product_maintenance_id and self.product_maintenance_id.product_id:
            self.tempario_aplicado_ids = self.product_maintenance_id.product_id.product_tmpl_id.tempario_ids

    # ---------- HELPER: filtra temparios válidos para un equipo ----------
    def _get_temparios_for_equipment(self, equipment):
        temparios_contrato = self.period_tempario_ids
        if not temparios_contrato:
            return temparios_contrato
        return temparios_contrato & getattr(equipment, 'tempario_ids', self.env['maintenance.tempario'])

    # ---------- PERIODO (respetando temparios por equipo) ----------
    def action_create_maintenance_detailed_period(self):
        for record in self:
            if not record.period_start_date or not record.period_end_date:
                raise ValidationError("Debes completar la Fecha de Inicio y Fecha Final del periodo.")
            if not record.period_frequency or record.period_interval <= 0:
                raise ValidationError("Debes completar la Frecuencia y el Intervalo (Cada cuánto).")
            if record.period_end_date < record.period_start_date:
                raise ValidationError("La fecha final debe ser posterior a la fecha inicial.")
            if not record.contract_equipment_ids:
                raise ValidationError("El contrato no tiene equipos asignados.")

            # Arrancar en el PRIMER salto (no incluye period_start_date)
            if record.period_frequency == 'day':
                current_date = record.period_start_date + timedelta(days=record.period_interval)
            elif record.period_frequency == 'month':
                current_date = record.period_start_date + relativedelta(months=record.period_interval)
            elif record.period_frequency == 'year':
                current_date = record.period_start_date + relativedelta(years=record.period_interval)
            else:
                raise ValidationError('Frecuencia no válida.')

            fechas = []
            while current_date <= record.period_end_date:
                fechas.append(current_date)
                if record.period_frequency == 'day':
                    current_date += timedelta(days=record.period_interval)
                elif record.period_frequency == 'month':
                    current_date += relativedelta(months=record.period_interval)
                else:  # year
                    current_date += relativedelta(years=record.period_interval)

            Detail = self.env['product.template.maintenance.detail']
            for equipment in record.contract_equipment_ids:
                temparios_equipo = record._get_temparios_for_equipment(equipment)
                if not temparios_equipo:
                    raise ValidationError(
                        f"El equipo '{equipment.display_name}' no tiene temparios aplicables en este contrato."
                    )
                for fecha in fechas:
                    Detail.create({
                        'repair_date': fecha,
                        'contract_id': record.id,
                        'product_maintenance_id': equipment.id,
                        'period_tempario_ids': [(6, 0, temparios_equipo.ids)],  # <-- solo sus temparios
                        'maintenance_type': record.maintenance_type,
                        'is_weekend': fecha.weekday() >= 5,
                    })
        return True

    # ---------- TEMPARIO (alineado a odómetro y respetando temparios por equipo) ----------
    def action_create_maintenance_detailed_tempario(self):
        for record in self:
            if not record.tempario_start_date or not record.tempario_end_date:
                raise ValidationError("Debes completar la Fecha de Inicio y Fin del Tempario.")
            if not record.period_tempario_ids:
                raise ValidationError("No hay temparios asignados.")
            if not record.contract_equipment_ids:
                raise ValidationError("El contrato no tiene equipos asignados.")

            fechas_dict = defaultdict(list)  # {(fecha, equipment_id): [tempario_id,...]}

            for equipment in record.contract_equipment_ids:
                if not equipment.daily_use or equipment.daily_use <= 0:
                    raise ValidationError(f"El equipo '{equipment.display_name}' no tiene una utilización diaria válida (> 0).")
                if equipment.utilization_type not in ('km', 'hour'):
                    raise ValidationError(
                        f"El equipo '{equipment.display_name}' tiene utilización '{equipment.utilization_type}'. "
                        f"Sólo se soporta 'km' u 'hour' para generar por horómetro/odómetro."
                    )

                # Temparios solo de este equipo
                temparios_equipo = record._get_temparios_for_equipment(equipment)
                if not temparios_equipo:
                    raise ValidationError(
                        f"El equipo '{equipment.display_name}' no tiene temparios aplicables en este contrato."
                    )

                current_units = equipment.current_mileage or 0.0

                for tempario in temparios_equipo:
                    if not tempario.frequency or tempario.frequency <= 0:
                        raise ValidationError(f"Frecuencia inválida en tempario {tempario.display_name or tempario.name}")

                    interval_units = tempario.frequency
                    # Próximo múltiplo > actual
                    if current_units <= 0:
                        next_due_units = interval_units
                    else:
                        multiples = ceil(current_units / interval_units)
                        if multiples * interval_units <= current_units + 1e-9:
                            multiples += 1
                        next_due_units = multiples * interval_units

                    remaining_units = max(0.0, next_due_units - current_units)
                    days_until_next = ceil(remaining_units / equipment.daily_use) if remaining_units > 0 else ceil(interval_units / equipment.daily_use)
                    days_step = max(1, ceil(interval_units / equipment.daily_use))

                    fecha = record.tempario_start_date + timedelta(days=days_until_next)
                    while fecha < record.tempario_start_date:
                        fecha += timedelta(days=days_step)

                    while fecha <= record.tempario_end_date:
                        fechas_dict[(fecha, equipment.id)].append(tempario.id)
                        fecha += timedelta(days=days_step)

            # Crear detalles agrupando por (fecha, equipo)
            Detail = self.env['product.template.maintenance.detail']
            for (fecha, equipment_id), tempario_ids in sorted(fechas_dict.items(), key=lambda x: (x[0][0], x[0][1])):
                Detail.create({
                    'repair_date': fecha,
                    'contract_id': record.id,
                    'product_maintenance_id': equipment_id,
                    'period_tempario_ids': [(6, 0, list(set(tempario_ids)))],  # <-- solo los del equipo
                    'maintenance_type': record.maintenance_type,
                    'is_weekend': fecha.weekday() >= 5,
                })
        return True
    
    def _regenerate_tempario_for_equipment(self, equipment):
        for record in self:
            if not record.tempario_start_date or not record.tempario_end_date:
                raise ValidationError("Debes completar la Fecha de Inicio y Fin del Tempario.")

            # Temparios aplicables a este equipo (usa tu helper existente)
            temparios_equipo = record._get_temparios_for_equipment(equipment)
            if not temparios_equipo:
                raise ValidationError(f"El equipo '{equipment.display_name}' no tiene temparios aplicables en este contrato.")

            if not equipment.daily_use or equipment.daily_use <= 0:
                raise ValidationError(f"El equipo '{equipment.display_name}' no tiene una utilización diaria válida (> 0).")
            if equipment.utilization_type not in ('km', 'hour'):
                raise ValidationError(
                    f"El equipo '{equipment.display_name}' tiene utilización '{equipment.utilization_type}'. "
                    f"Sólo se soporta 'km' u 'hour'."
                )

            fechas_dict = defaultdict(list)
            current_units = equipment.current_mileage or 0.0

            for tempario in temparios_equipo:
                if not tempario.frequency or tempario.frequency <= 0:
                    raise ValidationError(f"Frecuencia inválida en tempario {tempario.display_name or tempario.name}")

                interval_units = tempario.frequency
                # próximo múltiplo estrictamente mayor
                if current_units <= 0:
                    next_due_units = interval_units
                else:
                    multiples = ceil(current_units / interval_units)
                    if multiples * interval_units <= current_units + 1e-9:
                        multiples += 1
                    next_due_units = multiples * interval_units

                remaining_units = max(0.0, next_due_units - current_units)
                days_until_next = ceil(remaining_units / equipment.daily_use) if remaining_units > 0 else ceil(interval_units / equipment.daily_use)
                days_step = max(1, ceil(interval_units / equipment.daily_use))

                fecha = record.tempario_start_date + timedelta(days=days_until_next)
                while fecha < record.tempario_start_date:
                    fecha += timedelta(days=days_step)

                while fecha <= record.tempario_end_date:
                    fechas_dict[(fecha, equipment.id)].append(tempario.id)
                    fecha += timedelta(days=days_step)

            Detail = self.env['product.template.maintenance.detail']
            for (fecha, equipment_id), tempario_ids in sorted(fechas_dict.items(), key=lambda x: (x[0][0], x[0][1])):
                Detail.create({
                    'repair_date': fecha,
                    'contract_id': record.id,
                    'product_maintenance_id': equipment_id,
                    'period_tempario_ids': [(6, 0, list(set(tempario_ids)))],
                    'maintenance_type': record.maintenance_type,
                    'is_weekend': fecha.weekday() >= 5,  # no movemos fechas; solo marcamos
                })

    @api.onchange('contract_equipment_ids')
    def _onchange_contract_equipment_ids_fill_temparios(self):
        Tempario = self.env['maintenance.tempario']
        for rec in self:
            if not rec.contract_equipment_ids:
                continue

            union_ids = set()
            for equip in rec.contract_equipment_ids:
                # ajusta si tu M2M se llama distinto
                if getattr(equip, 'tempario_ids', False):
                    union_ids.update(equip.tempario_ids.ids)

            if not union_ids:
                continue

            actuales = set(rec.period_tempario_ids.ids)
            faltantes = union_ids - actuales
            if faltantes:
                rec.period_tempario_ids = [(4, tid) for tid in faltantes]
