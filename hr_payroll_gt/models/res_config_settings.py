# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    percentage_igss = fields.Float(
        string='Porcentaje IGSS',
        config_parameter='hr_payroll_gt.percentage_igss',
        default=4.83
    )
    assumed_disability_february_gt = fields.Boolean(
        string='Incapacidad asumida en febrero',
        config_parameter="hr_payroll_gt.assumed_disability_february_gt"
    )
    pay_advance_vacation_gt = fields.Boolean(
        string='Pagar vacaciones de forma anticipada',
        config_parameter="hr_payroll_gt.pay_advance_vacation_gt"
    )
    does_not_allow_ibd_less_than_smmlv_gt = fields.Boolean(
        string='No permite IBD menor al SMMLV',
        config_parameter="hr_payroll_gt.does_not_allow_ibd_less_than_smmlv_gt"
    )
    deductions_with_previous_ibc_gt = fields.Boolean(
        string='Calcular pension y EPS con IBC mes anterior en vacaciones',
        config_parameter="hr_payroll_gt.deductions_with_previous_ibc_gt"
    )

    rate_prv_agu_gt = fields.Float(
        string='% Provision Aguinalddo',
        config_parameter="hr_payroll_gt.rate_prv_agu_gt",
        default=8.33)
    rate_prv_bon_14 = fields.Float(
        string='% Provision Bono 14',
        config_parameter="hr_payroll_gt.rate_prv_bon_14",
        default=8.33)
    rate_prv_vac_gt = fields.Float(
        string='% Provision Vacaciones',
        config_parameter="hr_payroll_gt.rate_prv_vac_gt",
        default=5.83)
    rate_prv_ind_gt = fields.Float(
        string='% Provision Indemnización',
        config_parameter="hr_payroll_gt.rate_prv_ind_gt",
        default=9.82)
    rate_prv_cuo_pat = fields.Float(
        string='% Cuota Patronal',
        config_parameter="hr_payroll_gt.rate_prv_cuo_pat",
        default=12.67)
