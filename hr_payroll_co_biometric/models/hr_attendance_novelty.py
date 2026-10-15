# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError

NOVELTY_TYPE = [
    ('absence', 'Ausencia Total'),
    ('delay', 'Tardanza'),
    ('partial_absence', 'Ausencia Parcial'),
    ('extra_hours', 'Horas Extras (Genérico)'),
    ('extra_day_hours', 'H.E. Diurnas (HED)'),
    ('extra_night_hours', 'H.E. Nocturnas (HEN)'),
    ('night_surcharge', 'Recargo Nocturno (RN)'),
    ('biometric_issue', 'Inconsistencia Biométrica'),
    ('compensatory', 'Festivo/Dominical (HEDF)'),
    ('correction', 'Corrección Biométrica'),
    ('permission', 'Permiso'),
    ('disability', 'Incapacidad'),
    ('shift_change', 'Cambio de Turno'),
]

NOVELTY_STATE = [
    ('draft', 'Borrador'),
    ('review', 'Revisión'),
    ('approved', 'Aprobado'),
    ('rejected', 'Rechazado'),
    ('applied', 'Aplicado'),
]

PAYROLL_OVERTIME_TYPES = (
    'extra_hours',
    'extra_day_hours',
    'extra_night_hours',
    'night_surcharge',
    'compensatory',
)

OVERTIME_TYPE_CODE_BY_NOVELTY = {
    'extra_day_hours': 'HED',
    'extra_night_hours': 'HEN',
    'night_surcharge': 'RN',
    'compensatory': 'HEDF',
    'extra_hours': 'HED',
}

APPLIED_OVERTIME_LOCKED_FIELDS = {
    'attendance_record_id',
    'employee_id',
    'work_date',
    'novelty_type',
    'description',
    'minutes',
    'extra_hours',
    'extra_day_qty',
    'extra_night_qty',
    'overtime_type_id',
    'overtime_id',
    'compensatory_date',
    'state',
}


class HrOvertime(models.Model):
    _inherit = 'hr.overtime'

    biometric_novelty_id = fields.Many2one(
        'hr.attendance.novelty',
        string='Novedad Biométrica',
        ondelete='set null',
        index=True,
        readonly=True,
    )


class HrAttendanceNovelty(models.Model):
    """Novedad de asistencia detectada automáticamente o registrada manualmente."""
    _name = 'hr.attendance.novelty'
    _description = 'Novedad de Asistencia'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'work_date desc, employee_id'

    name = fields.Char(string='Referencia', readonly=True, default='/')

    attendance_record_id = fields.Many2one(
        'hr.attendance.record',
        string='Registro de Asistencia',
        ondelete='cascade',
        index=True,
    )
    shift_id = fields.Many2one(
        'hr.shift',
        string='Turno',
        related='attendance_record_id.shift_id',
        store=True,
        readonly=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
        index=True,
        tracking=True,
    )
    work_date = fields.Date(string='Fecha', required=True, index=True)

    novelty_type = fields.Selection(
        selection=NOVELTY_TYPE,
        string='Tipo de Novedad',
        required=True,
        tracking=True,
    )
    description = fields.Text(string='Descripción', required=True)

    minutes = fields.Integer(string='Minutos', default=0)
    extra_hours = fields.Float(string='Horas Extras Total', default=0.0)
    extra_day_qty = fields.Float(string='H.E. Diurnas (HED)', default=0.0)
    extra_night_qty = fields.Float(string='H.E. Nocturnas (HEN)', default=0.0)

    # Cuando se aprueba la novedad de horas extras, se puede enlazar con hr.overtime
    overtime_type_id = fields.Many2one(
        'hr.overtime.type',
        string='Categoría H.E. (Nómina CO)',
        readonly=True,
        index=True,
        help='Categoría de hora extra de Nómina CO asignada automáticamente por las reglas '
             'de categorización al procesar la asistencia biométrica.',
    )
    overtime_id = fields.Many2one(
        'hr.overtime',
        string='Registro Hora Extra',
        readonly=True,
    )

    state = fields.Selection(
        selection=NOVELTY_STATE,
        string='Estado',
        default='draft',
        tracking=True,
    )

    approved_by = fields.Many2one(
        'res.users',
        string='Aprobado por',
        readonly=True,
    )
    approved_date = fields.Datetime(string='Fecha Aprobación', readonly=True)
    rejection_reason = fields.Text(string='Motivo de Rechazo')

    company_id = fields.Many2one(
        'res.company',
        related='employee_id.company_id',
        store=True,
    )

    department_id = fields.Many2one(
        'hr.department',
        related='employee_id.department_id',
        store=True,
    )

    # Para novedades de compensatorio
    compensatory_date = fields.Date(string='Fecha Compensatorio Sugerida')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'hr.attendance.novelty') or '/'
        return super().create(vals_list)

    def write(self, vals):
        locked = self.filtered(
            lambda novelty: novelty.state == 'applied'
            and novelty.novelty_type in PAYROLL_OVERTIME_TYPES
        )
        if locked and APPLIED_OVERTIME_LOCKED_FIELDS.intersection(vals):
            raise UserError(
                'No se puede editar una novedad de horas extras que ya fue aplicada.'
            )
        return super().write(vals)

    def unlink(self):
        locked = self.filtered(
            lambda novelty: novelty.state == 'applied'
            and novelty.novelty_type in PAYROLL_OVERTIME_TYPES
        )
        if locked:
            raise UserError(
                'No se puede eliminar una novedad de horas extras que ya fue aplicada.'
            )
        return super().unlink()

    def action_to_review(self):
        for rec in self:
            if rec.state == 'draft':
                rec.state = 'review'

    def action_approve(self):
        for rec in self:
            if rec.state not in ('draft', 'review'):
                continue
            rec.state = 'approved'
            rec.approved_by = self.env.user
            rec.approved_date = fields.Datetime.now()

    def action_reject(self):
        for rec in self:
            if rec.state not in ('draft', 'review'):
                continue
            rec.state = 'rejected'

    def action_apply(self):
        """Aplica la novedad: genera hr.overtime si corresponde."""
        for rec in self:
            if rec.state != 'approved':
                raise UserError('Solo se pueden aplicar novedades aprobadas.')
            if rec.novelty_type in PAYROLL_OVERTIME_TYPES:
                rec._create_overtime_record()
            rec.state = 'applied'

    def action_apply_mass(self):
        """Aplica en una sola transacción las novedades aprobadas seleccionadas."""
        if not self:
            raise UserError('Seleccione al menos una novedad para aplicar.')

        invalid_novelties = self.filtered(lambda novelty: novelty.state != 'approved')
        if invalid_novelties:
            invalid_names = ', '.join(invalid_novelties.mapped('name')[:10])
            if len(invalid_novelties) > 10:
                invalid_names += ', ...'
            raise UserError(
                'Todas las novedades seleccionadas deben estar aprobadas. '
                'Revise: %s' % invalid_names
            )

        applied_count = len(self)
        self.action_apply()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Aplicación masiva completada',
                'message': 'Se aplicaron %d novedades.' % applied_count,
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                },
            },
        }

    def _create_overtime_record(self):
        """Crea un registro de horas extras en hr.overtime usando el código correcto
        (HED, HEN o HEDF) según el tipo de novedad."""
        self.ensure_one()
        if self.overtime_id:
            return

        existing_overtime = self.env['hr.overtime'].search([
            ('biometric_novelty_id', '=', self.id),
        ], limit=1)
        if existing_overtime:
            self.overtime_id = existing_overtime
            return

        contract = self.env['hr.contract'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'open'),
            ('company_id', '=', self.company_id.id),
        ], order='date_start desc, id desc', limit=1)
        if not contract:
            raise UserError(
                'El empleado %s no tiene contrato activo para registrar las horas extras.'
                % self.employee_id.name
            )

        # Determinar el tipo de hora extra: primero usa el campo directo (de reglas),
        # si no, recurre al mapeo por código según novelty_type.
        if self.overtime_type_id:
            overtime_type = self.overtime_type_id
        else:
            code = OVERTIME_TYPE_CODE_BY_NOVELTY.get(self.novelty_type)
            if not code:
                raise UserError('La novedad %s no genera horas extra de nómina.' % self.display_name)
            overtime_type = self._get_overtime_type_by_code(code)
            if not overtime_type:
                raise UserError(
                    'No se encontró el tipo de hora extra con código «%s». '
                    'Verifique la configuración en Nómina CO.' % code
                )
        self._check_overtime_type_rate(overtime_type)

        qty = self._get_overtime_qty()
        if qty <= 0:
            raise UserError(
                'La novedad %s no tiene cantidad de horas extra para aplicar.' % self.display_name
            )

        overtime = self.env['hr.overtime'].create({
            'contract_id': contract.id,
            'employee_id': self.employee_id.id,
            'company_id': contract.company_id.id,
            'overtime_type_id': overtime_type.id,
            'date_start': self.work_date,
            'date_end': self.work_date,
            'qty': round(qty, 4),
            'biometric_novelty_id': self.id,
        })
        self.overtime_id = overtime

    def _get_overtime_qty(self):
        self.ensure_one()
        if self.novelty_type == 'extra_day_hours':
            return self.extra_day_qty
        if self.novelty_type == 'extra_night_hours':
            return self.extra_night_qty
        return self.extra_hours

    def _check_overtime_type_rate(self, overtime_type):
        if overtime_type.rate <= 0:
            raise UserError('Configure un factor positivo para el tipo de hora extra %s.' % overtime_type.code)
        if overtime_type.rate and overtime_type.rate > 10.0:
            raise UserError(
                'El tipo de hora extra %s tiene factor %s. '
                'El modelo hr.overtime de Nómina CO usa este valor como factor directo; '
                'configure el factor como decimal (por ejemplo, 2.0 para 200%%) antes de aplicar la novedad.'
                % (overtime_type.code, overtime_type.rate)
            )

    def _get_overtime_type_by_code(self, code):
        """Busca hr.overtime.type por código exacto en la compañía del empleado."""
        company_id = self.employee_id.company_id.id if self.employee_id.company_id else self.env.company.id
        ot = self.env['hr.overtime.type'].search([
            ('code', '=', code), ('company_id', '=', company_id),
        ], limit=1)
        if not ot:
            ot = self.env['hr.overtime.type'].search([
                ('code', '=', code), ('company_id', '=', False),
            ], limit=1)
        return ot
