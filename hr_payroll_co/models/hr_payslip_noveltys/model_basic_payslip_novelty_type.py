# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

CATEGORY_PAYSLIP = [
    ('earnings', 'DEVENGADO'),
    ('o_salarial_earnings', 'OTROS DEVENGOS SALARIALES'),
    ('comp_earnings', 'INGRESOS COMPLEMENTARIOS'),
    ('o_rights', 'OTROS DERECHOS'),
    ('o_earnings', 'OTROS DEVENGOS'),
    ('non_taxed_earnings', 'INGRESOS NO GRAVADOS'),
    ('deductions', 'DEDUCCIONES'),
    ('contributions', 'APORTES'),
    ('provisions', 'PROVISIONES'),
    ('subtotals', 'SUBTOTALES'),
]

PARTNER_TYPE = [
    ('EPS', 'EPS'),
    ('ARL', 'ARL'),
    ('CES', 'CESANTIAS'),
    ('PEN', 'PENSIONES'),
    ('CCF', 'CAJA DE COMPENSACION FAMILIAR'),
    ('OTHER', 'OTRO')
]


class ModelBasicPayslipNoveltyType(models.AbstractModel):
    _name = 'model.basic.payslip.novelty.type'
    _description = 'model.basic.payslip.novelty.type'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True)
    code = fields.Char(string='Código', required=True)
    category = fields.Selection(
        string="Categoría", selection=CATEGORY_PAYSLIP, required=True)
    partner_type = fields.Selection(
        string='Tipo de tercero', selection=PARTNER_TYPE)
    partner_id = fields.Many2one(comodel_name='res.partner', string='Tercero')
    company_id = fields.Many2one(comodel_name='res.company', string='Compañia',
                                 default=lambda self: self.env.company)

    reg_adm_debit = fields.Many2one(
        comodel_name='account.account', string='Debito Regular Administrativo')
    int_adm_debit = fields.Many2one(
        comodel_name='account.account', string='Debito Integral Administrativo')
    apr_adm_debit = fields.Many2one(
        comodel_name='account.account', string='Debito Aprendiz Administrativo')
    reg_com_debit = fields.Many2one(
        comodel_name='account.account', string='Debito Regular Comercial')
    int_com_debit = fields.Many2one(
        comodel_name='account.account', string='Debito Integral Comercial')
    apr_com_debit = fields.Many2one(
        comodel_name='account.account', string='Debito Aprendiz Comercial')
    reg_ope_debit = fields.Many2one(
        comodel_name='account.account', string='Debito Regular Operativa')
    int_ope_debit = fields.Many2one(
        comodel_name='account.account', string='Debito Integral Operativa')
    apr_ope_debit = fields.Many2one(
        comodel_name='account.account', string='Debito Aprendiz Operativa')
    reg_pro_debit = fields.Many2one(
        comodel_name='account.account', string='Debito Regular  Producción')
    int_pro_debit = fields.Many2one(
        comodel_name='account.account', string='Debito Integral Producción')
    apr_pro_debit = fields.Many2one(
        comodel_name='account.account', string='Debito Aprendiz Producción')

    reg_adm_credit = fields.Many2one(
        comodel_name='account.account', string='Credito Regular Administrativo')
    int_adm_credit = fields.Many2one(
        comodel_name='account.account', string='Credito Integral Administrativo')
    apr_adm_credit = fields.Many2one(
        comodel_name='account.account', string='Credito Aprendiz Administrativo')
    reg_com_credit = fields.Many2one(
        comodel_name='account.account', string='Credito Regular Comercial')
    int_com_credit = fields.Many2one(
        comodel_name='account.account', string='Credito Integral Comercial')
    apr_com_credit = fields.Many2one(
        comodel_name='account.account', string='Credito Aprendiz Comercial')
    reg_ope_credit = fields.Many2one(
        comodel_name='account.account', string='Credito Regular Operativa')
    int_ope_credit = fields.Many2one(
        comodel_name='account.account', string='Credito Integral Operativa')
    apr_ope_credit = fields.Many2one(
        comodel_name='account.account', string='Credito Aprendiz Operativa')
    reg_pro_credit = fields.Many2one(
        comodel_name='account.account', string='Credito Regular  Producción')
    int_pro_credit = fields.Many2one(
        comodel_name='account.account', string='Credito Integral Producción')
    apr_pro_credit = fields.Many2one(
        comodel_name='account.account', string='Credito Aprendiz Producción')

    _code_company_id_uniq = models.Constraint(
        'UNIQUE (code, company_id)',
        'El Código debe ser único por categoría y compañia',
    )

    def get_partner_id(self, contract):
        if self.partner_type == 'EPS':
            return contract.eps_id.id
        elif self.partner_type == 'ARL':
            return contract.arl_id.id
        elif self.partner_type == 'CES':
            return contract.afp_severance_id.id
        elif self.partner_type == 'PEN':
            if self.code in ['DED_PENS_PUBLIC', 'AP_PENS_PUBLIC']:
                public_pension_administrator = self.env['ir.config_parameter'].sudo(
                ).get_param('hr_payroll_co.public_pension_administrator')
                if not public_pension_administrator:
                    raise ValidationError(
                        "Configure el <Administrador público de pensiones>")
                return int(public_pension_administrator)
            return contract.afp_pension_id.id
        elif self.partner_type == 'CCF':
            return contract.ccf_id.id
        elif self.partner_type == 'OTHER':
            return self.partner_id.id
        else:
            return contract.employee_id.partner_id.id

    def get_debit_credit_accounts(self, prefix_account):
        """
        Retorna las cuentas contables a partir del prefijo de la cuenta 
        @params:
            prefix_account: str; ex: ref_ope_
        @return:
            tuple -> cuenta debito, cuenta credito
        """

        debit_account = getattr(
            self, prefix_account + 'debit')
        credit_account = getattr(
            self, prefix_account + 'credit')
        if not debit_account or not credit_account:
            raise ValidationError(
                f'Configure las cuentas del concepto {self.name}')

        return debit_account, credit_account
