# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from ..hr_payslip_period.hr_period import TYPE_PERIOD
from dateutil.relativedelta import relativedelta

TYPE_NOVELTY = [
    ('RECURRENT', 'Recurrente'),
    ('STATIC', 'Estatica')
]


class HrNovelty(models.Model):
    _name = 'hr.novelty'
    _inherit = 'model.basic.payslip.novelty'
    _description = 'Novedad'
    _order = 'name'

    type_novelty = fields.Selection(
        string='Tipo', selection=TYPE_NOVELTY, default='STATIC', required=True)
    novelty_type_id = fields.Many2one(
        comodel_name='hr.novelty.type', string='Categoría de Novedad', required=True)
    novelty_line_ids = fields.One2many(
        comodel_name='hr.novelty.line', inverse_name='novelty_id', readonly=True, string='Lineas de Novedad')
    loan_id = fields.Many2one(
        comodel_name='hr.loan', string='Préstamo')
    contract_novelty_id = fields.Many2one(
        comodel_name='hr.contract.novelty', string='Novedad de contrato',
        ondelete='set null', index=True, copy=False, readonly=True,
        help='Línea de la pestaña Novedades del contrato que generó '
             'automáticamente esta novedad.')
    contract_novelty_period_id = fields.Many2one(
        comodel_name='hr.period', string='Periodo de generación',
        copy=False, readonly=True)
    day31_generated = fields.Boolean(
        string='Generada día 31', copy=False, readonly=True,
        help='Novedad creada automáticamente por el beneficio día 31 del contrato.')
    payslip_id = fields.Many2one(
        'hr.payslip', string="Nómina", compute="_compute_payslip_id", store=True)

    @api.depends('novelty_line_ids.payslip_id')
    def _compute_payslip_id(self):
        for record in self:
            if record.novelty_line_ids:
                record.payslip_id = record.novelty_line_ids[0].payslip_id
            else:
                record.payslip_id = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'seq.hr.novelty') or ''
        return super(HrNovelty, self).create(vals_list)

    def to_validated(self):
        period = self.env['hr.period']
        for record in self:
            if record.state != 'confirm':
                continue
            periods = period.get_period(
                record.date_start,
                record.date_end if record.type_novelty == 'RECURRENT' else False, record.contract_id.schedule_pay)

            schedule_pay = [x for x in TYPE_PERIOD if x[0] == record.contract_id.schedule_pay]
            if not periods:
                raise ValidationError(
                    f"No se encontraron periodos para el tipo de pago {schedule_pay[0][1]} en las fechas de la novedad. Por favor, cree los periodos necesarios."
                )   
            if record.type_novelty == 'RECURRENT':
                # Calcular el rango de fechas que cubre toda la recurrencia
                date_start = record.date_start
                date_end = record.date_end or record.date_start
                months_to_create = (date_end.year - date_start.year) * 12 + date_end.month - date_start.month

                existing_periods = self.env['hr.period'].search([
                    ('start', '>=', date_start),
                    ('type_period', '=', record.contract_id.schedule_pay),
                    ('company_id', '=', self.env.company.id)
                ])

                for i in range(1, months_to_create + 1):
                    new_start_date = date_start + relativedelta(months=i)

                    # Verificar si ya existe un periodo para esa fecha
                    if not existing_periods.filtered(lambda p: p.start.month == new_start_date.month and p.start.year == new_start_date.year):
                        raise ValidationError(
                            f"No se encontraron periodos para el tipo de pago {schedule_pay[0][1]} en las fechas de la novedad. Por favor, cree los periodos necesarios."
                        )

            if record.novelty_type_id.single_biweekly_payment and record.contract_id.schedule_pay == 'BIWEEKLY':
                if not record.novelty_type_id.biweekly_type:
                    raise ValidationError(
                        'La novedad es de tipo pago único quincenal y no se ha configurado la quincena.')

                periods = periods.filtered(
                    lambda x: x.type_biweekly == record.novelty_type_id.biweekly_type)
            record.novelty_line_ids = record._prepare_novelty_line(periods.ids)
        return super(HrNovelty, self).to_validated()

    def to_draft(self):
        for record in self:
            if record.state == 'paid':
                raise ValidationError('No se puede pasar a borrador, ya tiene un pago registrado')
            if record.state != 'validated':
                continue
            record.novelty_line_ids.unlink()
        return super(HrNovelty, self).to_draft()

    def _prepare_novelty_line(self, periods):
        """funtion per record"""
        new_novelty_line = []
        for period in periods:
            new_novelty_line.append((0, 0, {
                'period_id': period,
                'state': 'validated',
                'amount': self.amount,
            }))
        return new_novelty_line

    def to_paid(self):
        for record in self:
            if all([l.state == 'paid' for l in record.novelty_line_ids]):
                record.state = 'paid'

    def to_cancel(self):
        return_super = True
        for record in self:
            if record.state == 'validated':
                if any([l.state == 'paid' for l in record.novelty_line_ids]):
                    record.novelty_line_ids.filtered(lambda x: x.state != 'paid').unlink()
                    record.state = 'paid'
                    return_super = False
                else:
                    record.novelty_line_ids.unlink()
        if return_super:
            return super(HrNovelty, self).to_cancel()
