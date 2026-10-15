# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from odoo.addons.utilities_collection import orm

STATE = [
    ('validated', 'Validada'),
    ('paid', 'Pagada')
]


class HrLeaveLine(models.Model):
    _name = 'hr.leave.line'
    _description = 'Lineas de Ausencia'

    leave_id = fields.Many2one(
        comodel_name='hr.leave', string='Ausencia', required=True, index=True)
    payslip_id = fields.Many2one(
        comodel_name='hr.payslip', string='Nómina', index=True)
    contract_id = fields.Many2one(
        string="Contrato", related='leave_id.contract_id')
    date = fields.Date(string='Fecha')
    period_id = fields.Many2one(
        comodel_name='hr.period', string='Periodo', index=True)
    state = fields.Selection(string='Estado', selection=STATE)
    amount = fields.Float(string='Valor')
    sequence = fields.Integer(string='Secuencia')
    is_rest_or_dayoff = fields.Boolean(string='Es día no habil')

    def create_payslip_line(self, payslip_id):
        leave_type_id = self.leave_id.leave_type_id
        rest_leave_type_id = self.leave_id.holidays_leave_type_id
        rate, concept_id, _ = leave_type_id.get_rate_concept_id(self.sequence)
        rest_rate, rest_concept_id, rest_ = rest_leave_type_id.get_rate_concept_id(self.sequence)
        concept = self.env['hr.concept'].browse(concept_id) if concept_id else None
        rest_concept = self.env['hr.concept'].browse(rest_concept_id) if rest_concept_id else None
        payslip_line = {
            'name': (rest_concept.name if rest_concept else rest_leave_type_id.name) if self.is_rest_or_dayoff else (concept.name if concept else leave_type_id.name),
            'payslip_id': payslip_id,
            'category': leave_type_id.category if not self.is_rest_or_dayoff else rest_leave_type_id.category,
            'value': self.amount,
            'qty': 1 if leave_type_id.category_type != 'VAC_MONEY' else self.leave_id.days_vac_money,
            'rate': rate if not self.is_rest_or_dayoff else rest_rate,
            'total': self.amount,
            'origin': 'local',
            'concept_id': concept_id if not self.is_rest_or_dayoff else rest_concept_id,
            'leave_id': self.leave_id.id,
            'novelty_id': None,
            'overtime_id': None,
            'is_rest_or_dayoff': self.is_rest_or_dayoff,
        }
        for unique_key in ['is_rest_or_dayoff', 'rate', 'concept_id', 'leave_id', 'novelty_id', 'overtime_id']:
            if 'unique_key' in payslip_line:
                payslip_line['unique_key'] += str(payslip_line[unique_key])
            else:
                payslip_line['unique_key'] = str(payslip_line[unique_key])
        return payslip_line

    def belongs_category(self, categories):
        return self.leave_id.leave_type_id.id in categories

    def get_info_from_leave_type(self, cr, data):
        """
        Obtiene el numero de dias de un tipo de ausencia y de un contrato
        @params:
        cr: cursor con el que se va a ejecutar la consulta
        data: diccionario con la siguiente estructura.
            {'contract':int, 'start':datetime, 'end':datetime,'type':tuple(string)}
        """
        query = """
        SELECT COUNT(*), SUM(HLL.amount)
        FROM hr_leave_line AS  HLL
        INNER JOIN hr_leave AS HL ON HL.id = HLL.leave_id
        INNER JOIN hr_leave_type AS HLT ON HLT.id = HL.leave_type_id
        WHERE
            HL.contract_id = %(contract)s AND
            HLL.date BETWEEN %(start)s AND %(end)s AND
            HLT.category_type in %(type)s
        """
        res = orm._fetchall(cr, query, data)
        return sum([x[0] for x in res if x[0]]), sum([x[1] for x in res if x[1]])

    def _get_no_pay_lines(self, contract_id, date_from, date_to, data_payslip, is_cesly):
        """
        Devuelve las líneas de ausencia NO_PAY (sin paga) consideradas como días no
        trabajados: las pagadas dentro del rango [date_from, date_to] más, salvo para
        cesantías de enero (is_cesly), las validadas del período actual.
        @return: lista de tuplas (leave_id, date)
        """
        query = """
        SELECT HL.id, HLL.date
        FROM hr_leave_line AS  HLL
        INNER JOIN hr_leave AS HL ON HL.id = HLL.leave_id
        INNER JOIN hr_leave_type AS HLT ON HLT.id = HL.leave_type_id
        WHERE
            HL.contract_id = %(contract_id)s AND
            HLL.date BETWEEN %(start)s AND %(end)s AND
            HLT.category_type = 'NO_PAY' AND
            HLL.state = 'paid'
        ORDER BY HL.id, HLL.date DESC
        """
        current_query = """
        SELECT HL.id, HLL.date
        FROM hr_leave_line AS  HLL
        INNER JOIN hr_leave AS HL ON HL.id = HLL.leave_id
        INNER JOIN hr_leave_type AS HLT ON HLT.id = HL.leave_type_id
        WHERE
            HL.contract_id = %(contract_id)s AND
            HLL.date BETWEEN %(start)s AND %(end)s AND
            HLT.category_type = 'NO_PAY' AND
            HLL.state = 'validated'
        ORDER BY HL.id, HLL.date DESC
        """
        params = {
            'contract_id': contract_id.id,
            'start': date_from,
            'end': date_to,
        }
        # 'period' puede ser un record hr.period, un SimpleNamespace o un dict
        # {'start', 'end'} (p.ej. desde el builder del CIR).
        period = data_payslip['period']
        current_params = {
            'contract_id': contract_id.id,
            'start': period['start'] if isinstance(period, dict) else period.start,
            'end': period['end'] if isinstance(period, dict) else period.end,
        }
        response = orm._fetchall(self._cr, query, params)
        response_current = orm._fetchall(self._cr, current_query, current_params)
        if not is_cesly:
            return response + response_current
        return response

    def get_days_not_worked(self, contract_id, date_from, date_to, ignore_rest_days, data_payslip, is_cesly):
        """
        Obtiene el numero de dias no trabajados, no cuenta el descuento de dias de descanso
        @params:
        contract_id -> hr.contract
        date_from -> datetime
        date_to -> datetime
        """
        return len(self._get_no_pay_lines(
            contract_id, date_from, date_to, data_payslip, is_cesly))

    def get_no_pay_dates(self, contract_id, date_from, date_to, data_payslip, is_cesly):
        """
        Devuelve las fechas de las ausencias NO_PAY consideradas como días no trabajados,
        para descontarlas también del salario al promediar (consistente con
        get_days_not_worked, que usa el mismo conjunto de líneas).
        @return: lista de date
        """
        return [line[1] for line in self._get_no_pay_lines(
            contract_id, date_from, date_to, data_payslip, is_cesly)]

    @api.model
    def is_rest_or_daysoff(self, contract, date):
        if contract.is_rest_day(date) or self.env['hr.days.off.year'].is_day_off(date):
            return True
        return False

    @api.model
    def _get_leaves_by_date(self, contract_id, date_from, date_to):
        """
        Obtiene las fechas de las ausencias de un contrato en un rango de fechas
        @params:
        contract_id -> hr.contract
        date_from -> datetime
        date_to -> datetime
        """
        query = """
        SELECT HLL.date
        FROM hr_leave_line AS  HLL
        INNER JOIN hr_leave AS HL ON HL.id = HLL.leave_id
        INNER JOIN hr_leave_type AS HLT ON HLT.id = HL.leave_type_id
        WHERE
            HL.contract_id = %(contract_id)s AND
            HLL.date BETWEEN %(start)s AND %(end)s AND
            HLT.category_type = 'NO_PAY' AND 
            HLL.state = 'paid'
        ORDER BY HL.id, HLL.date DESC
        """
        params = {
            'contract_id': contract_id.id,
            'start': date_from,
            'end': date_to,
        }
        response = orm._fetchall(self._cr, query, params)
        if response:
            return [x[0] for x in response if x[0]]
        return []
