# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

STATE = [
    ('draft', 'Borrador'),
    ('validated', 'Validada'),
]

PROTECTED_FIELDS_VALIDATED = {'contract_id', 'novelty_type_id', 'date_start'}


class HrContractNovelty(models.Model):
    _name = 'hr.contract.novelty'
    _description = 'Novedad recurrente de contrato'
    _order = 'date_start desc, id desc'

    contract_id = fields.Many2one(
        comodel_name='hr.contract', string='Contrato', required=True,
        ondelete='cascade', index=True)
    employee_id = fields.Many2one(
        related='contract_id.employee_id', string='Empleado', store=True)
    company_id = fields.Many2one(
        related='contract_id.company_id', string='Compañia', store=True)
    novelty_type_id = fields.Many2one(
        comodel_name='hr.novelty.type', string='Concepto', required=True)
    amount = fields.Float(string='Valor', required=True)
    date_start = fields.Date(string='Fecha inicio', required=True)
    date_end = fields.Date(
        string='Fecha final',
        help='Si se deja vacía, la novedad se genera indefinidamente '
             'mientras la línea esté validada, cada vez que se calcule '
             'una nómina del contrato.')
    state = fields.Selection(
        string='Estado', selection=STATE, default='draft', required=True, copy=False)
    novelty_ids = fields.One2many(
        comodel_name='hr.novelty', inverse_name='contract_novelty_id',
        string='Novedades generadas')
    novelty_count = fields.Integer(
        string='Validadas', compute='_compute_novelty_count')

    @api.depends('novelty_ids.state')
    def _compute_novelty_count(self):
        for record in self:
            record.novelty_count = len(record.novelty_ids.filtered(
                lambda n: n.state == 'validated'))

    @api.constrains('amount')
    def _check_amount(self):
        for record in self:
            if record.amount <= 0:
                raise ValidationError(
                    'El valor de la novedad del contrato debe ser mayor a cero.')

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for record in self:
            if record.date_end and record.date_end < record.date_start:
                raise ValidationError(
                    'La fecha final de la novedad del contrato no puede ser '
                    'anterior a la fecha inicio.')

    def _check_validation_group(self):
        if not self.env.user.has_group('hr_payroll_co.group_contract_novelty_validate'):
            raise UserError(
                'No tiene permisos para validar o pasar a borrador novedades '
                'del contrato. Solicite el permiso "Nómina: Validar novedades '
                'de contrato".')

    def action_validate(self):
        self._check_validation_group()
        for record in self:
            if record.state != 'draft':
                continue
            record.with_context(
                contract_novelty_state_change=True).state = 'validated'
            if not record.novelty_type_id.dep_days_worked:
                record.contract_id.message_post(body=(
                    'La novedad de contrato "%s" fue validada, pero la categoría '
                    'no tiene activo "Depende de días trabajados": el valor se '
                    'pagará completo sin prorratear por ausencias no remuneradas '
                    'o días sin contrato en el periodo.'
                ) % record.novelty_type_id.name)

    def action_draft(self):
        self._check_validation_group()
        for record in self:
            if record.state != 'validated':
                continue
            record._remove_generated_novelties(record.novelty_ids)
            record.with_context(
                contract_novelty_state_change=True).state = 'draft'

    def write(self, vals):
        if 'state' in vals and not self.env.context.get(
                'contract_novelty_state_change'):
            raise UserError(
                'El estado de la novedad del contrato solo se cambia con los '
                'botones Validar y A borrador.')
        if not self.env.context.get('skip_contract_novelty_check'):
            protected = PROTECTED_FIELDS_VALIDATED & set(vals)
            if protected and any(r.state == 'validated' for r in self):
                raise UserError(
                    'La novedad del contrato está validada: únicamente puede '
                    'modificar el Valor y la Fecha final. Pásela a borrador '
                    'para modificar los demás campos.')
        res = super(HrContractNovelty, self).write(vals)
        if 'amount' in vals:
            self.filtered(lambda r: r.state == 'validated')._propagate_amount()
        if 'date_end' in vals:
            self.filtered(
                lambda r: r.state == 'validated'
            )._cancel_out_of_range_novelties()
        return res

    def unlink(self):
        if any(r.state != 'draft' for r in self):
            raise UserError(
                'No se puede eliminar una novedad de contrato validada. '
                'Pásela a borrador primero.')
        return super(HrContractNovelty, self).unlink()

    def _propagate_amount(self):
        """Aplica el nuevo valor a las novedades generadas no pagadas y sus
        líneas pendientes de pago."""
        for record in self:
            novelties = record.novelty_ids.filtered(
                lambda n: n.state == 'validated')
            novelties.write({'amount': record.amount})
            novelties.mapped('novelty_line_ids').filtered(
                lambda l: l.state != 'paid').write({'amount': record.amount})

    def _cancel_out_of_range_novelties(self):
        """Elimina novedades generadas (no pagadas) cuyo periodo quedó fuera
        de la nueva vigencia."""
        for record in self:
            if not record.date_end:
                continue
            record._remove_generated_novelties(record.novelty_ids.filtered(
                lambda n: n.contract_novelty_period_id
                and n.contract_novelty_period_id.start > record.date_end))

    def _remove_generated_novelties(self, novelties):
        """Borra las novedades generadas que aún no entraron a nómina; las
        pagadas (total o parcialmente) no se tocan."""
        removable = novelties.filtered(
            lambda n: n.state != 'paid'
            and not n.novelty_line_ids.filtered(lambda l: l.state == 'paid'))
        removable.mapped('novelty_line_ids').unlink()
        removable.unlink()

    def _generate_for_payslip(self, payslip):
        """Crea las novedades de las líneas validadas del contrato para el
        periodo de la nómina en cálculo. Solo genera las categorías asociadas
        al tipo de nómina (novelty_types_ids)."""
        period = payslip.period_id
        allowed_type_ids = payslip.payslip_type_id.novelty_types_ids.ids
        generated = self.env['hr.novelty']
        if not allowed_type_ids:
            return generated
        for record in self:
            if record.state != 'validated':
                continue
            if record.novelty_type_id.id not in allowed_type_ids:
                continue
            if record.date_start > period.end:
                continue
            if record.date_end and record.date_end < period.start:
                continue
            novelty_type = record.novelty_type_id
            if period.type_period == 'BIWEEKLY' and \
                    novelty_type.single_biweekly_payment:
                if not novelty_type.biweekly_type:
                    raise ValidationError(
                        'La categoría "%s" es de pago único quincenal y no '
                        'tiene configurado el tipo de quincena.'
                        % novelty_type.name)
                if period.type_biweekly != novelty_type.biweekly_type:
                    continue
            if record.novelty_ids.filtered(
                    lambda n: n.contract_novelty_period_id == period):
                continue
            generated |= record._create_novelty_for_period(period)
        return generated

    def _create_novelty_for_period(self, period):
        self.ensure_one()
        company = self.company_id or self.contract_id.company_id
        novelty = self.env['hr.novelty'].with_company(company).create({
            'contract_id': self.contract_id.id,
            'employee_id': self.contract_id.employee_id.id,
            'novelty_type_id': self.novelty_type_id.id,
            'type_novelty': 'STATIC',
            'date_start': max(period.start, self.date_start),
            'amount': self.amount,
            'contract_novelty_id': self.id,
            'contract_novelty_period_id': period.id,
        })
        novelty.to_confirm()
        novelty.to_validated()
        return novelty
