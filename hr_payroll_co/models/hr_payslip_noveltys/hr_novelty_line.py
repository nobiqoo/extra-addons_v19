# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

STATE = [
    ('validated', 'Validada'),
    ('paid', 'Pagada')
]


class HrNoveltyLine(models.Model):
    _name = 'hr.novelty.line'
    _description = 'Lineas de Novedad'

    novelty_id = fields.Many2one(
        comodel_name='hr.novelty', string='Novedad', required=True, index=True)
    payslip_id = fields.Many2one(
        comodel_name='hr.payslip', string='Nómina', index=True)
    contract_id = fields.Many2one(
        string="Contrato", related='novelty_id.contract_id')
    period_id = fields.Many2one(
        comodel_name='hr.period', string='Periodo', index=True)
    state = fields.Selection(string='Estado', selection=STATE)
    amount = fields.Float(string='Valor')

    def create_payslip_line(self, payslip_id, worked_days=0, max_working_days=0):
        novelty_type_id = self.novelty_id.novelty_type_id
        payslip_line = {
            'name': novelty_type_id.name,
            'payslip_id': payslip_id,
            'category': novelty_type_id.category,
            'value': self.amount,
            'qty': 1,
            'rate': 100 if max_working_days == 0 else (worked_days * 100 / max_working_days),
            'total': self.get_amount(worked_days, max_working_days),
            'origin': 'local',
            'concept_id': None,
            'leave_id': None,
            'novelty_id': self.novelty_id.id,
            'overtime_id': None,
        }
        for unique_key in ['rate', 'concept_id', 'leave_id', 'novelty_id', 'overtime_id']:
            if 'unique_key' in payslip_line:
                payslip_line['unique_key'] += str(payslip_line[unique_key])
            else:
                payslip_line['unique_key'] = str(payslip_line[unique_key])
        return payslip_line

    def belongs_category(self, categories):
        return self.novelty_id.novelty_type_id.id in categories

    def check_modality_rtefte(self, data_payslip, worked_days=0, max_working_days=0):
        novelty_type_id = self.novelty_id.novelty_type_id
        if novelty_type_id.category in ['earnings', 'o_earnings', 'o_salarial_earnings', 'comp_earnings', 'o_rights']:
            key = 'income'
        elif novelty_type_id.category == 'deductions':
            key = 'outcome'
        else:
            return
        if novelty_type_id.modality in ['EXT', 'AVP', 'AFC']:
            key += '_' + novelty_type_id.modality
            if key in data_payslip:
                data_payslip[key] += self.get_amount(
                    worked_days, max_working_days)
            else:
                data_payslip[key] = self.get_amount(
                    worked_days, max_working_days)

    def get_amount(self, worked_days, max_working_days):
        if self.novelty_id.novelty_type_id.dep_days_worked and max_working_days > 0:
            rate = worked_days / max_working_days
            return self.amount * rate
        return self.amount

    def create_payslip_line_dep_days_worked(self, data_payslip, worked_days, max_working_days):
        self.check_modality_rtefte(data_payslip, worked_days, max_working_days)
        payslip_line = self.create_payslip_line(
            data_payslip['payslip_id'], worked_days, max_working_days)
        if 'unique_key' in payslip_line:
            payslip_line.pop('unique_key')
        return payslip_line
