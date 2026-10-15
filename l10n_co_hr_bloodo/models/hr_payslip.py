# -*- coding: utf-8 -*-

import datetime
import logging
from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.addons.utilities_collection.time import days360


_logger = logging.getLogger(__name__)

# ObJinja: Debe existir en el diccionario de renderizacion (Jinja)

CONTRACT_TYPE = {
    'fijo': '1',  # TERMINO FIJO
    'indefinido': '2',  # TERMINO INDEFINIDO
    'obra-labor': '3',  # OBRA O LABOR
    'aprendizaje': '4',  # APRENDIZAJE
    'practica': '5',  # PRACTICAS O PASANTIAS
}
PAYROLL_PERIOD = {
    'WEEKLY': '1',    # SEMANAL
    'DECENNIAL': '2',    # DECENAL
    'FOURTEENTH': '3',    # CATORCENAL
    'BIWEEKLY': '4',    # QUINCENAL
    'MONTHLY': '5',    # MENSUAL
    'OTHER': '6',    # OTRO
}
HEP = {
    'HED': '25.00',
    'HEN': '75.00',
    'HRN': '35.00',
    'HEDDF': '100.00',
    'HRDDF': '75.00',
    'HENDF': '150.00',
    'HRNDF': '110.00',
}


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    # edi_pdf_filename = fields.Char(string='Nombre Pdf', copy=False)
    # edi_pdf_file = fields.Binary(string='Archivo Pdf', copy=False)

    edi_doc_ids = fields.One2many('edi.hr.document',
                                  'payslip_id',
                                  'Dian document',
                                  copy=False)
    edi_hr_ids = fields.Many2many('edi.hr.document',
                                  'edi_doc_payslip_rel',
                                  'hr_id',
                                  'edi_id',
                                  'Documentos DIAN')
    
    # TOOLS
    def _get_salary_earning_categ(self):
        return ['earnings', 'o_salarial_earnings', 'comp_earnings', 'provisions', 'o_rights']
    
    def _get_no_salary_earning_categ(self):
        return ['o_earnings', 'non_taxed_earnings']
    
    def _is_salary_earning(self, line):
        category = '**'
        if line.novelty_id:
            category = line.novelty_id.novelty_type_id.category
        if line.concept_id:
            category = line.concept_id.category
        return category in self._get_salary_earning_categ()

    def _is_no_salary_earning(self, line):
        category = '**'
        if line.novelty_id:
            category = line.novelty_id.novelty_type_id.category
        if line.concept_id:
            category = line.concept_id.category
        return category in self._get_no_salary_earning_categ()

    # TODO cambiar nombre
    def _is_dian_concept(self, line, codes=[]):
        dian_code = '**'
        if line.novelty_id:
            dian_code = str(
                line.novelty_id.novelty_type_id.dian_concept_id.dian_code)
        if line.concept_id:
            dian_code = str(
                line.concept_id.dian_concept_id.dian_code)
        return dian_code in codes

    # BUILD
    def _build_period_ne(self):
        contract_id = self[0].contract_id
        type_period = list(set([n.period_id.type_period for n in self]))[0]
        period_start = min([n.period_id.start for n in self])
        period_end = max([n.period_id.end for n in self])
        # Validar Per_TiempoLaborado
        days_worked = days360(
            contract_id.date_start,
            # self.period_id.start,
            period_end)
        time_worked = relativedelta(
            period_end,
            contract_id.date_start)
        days_w = (time_worked.years*360) + \
                 (time_worked.months*30) + time_worked.days
        if days_worked != days_w:
            _logger.info(
                '********** TIEMPO LABORADO DIFERENTE '
                'days360() y relativedelta()')
        period_info = {
            'Per_FechaLiquidacionInicio': period_start,
            'Per_FechaLiquidacionFin': period_end,
            'Per_TiempoLaborado': days_w or 1,  # days_worked,
            'Per_FechaGen': datetime.date.today(),
            'IGe_PeriodoNomina': PAYROLL_PERIOD.get(type_period)
        }

        # if self.period_id.between(self.contract_id.date_start):
        # Inicio del contrato puede ser inferior a fecha de inicio
        # del periodo de nomina
        period_info['Per_FechaIngreso'] = contract_id.date_start

        if contract_id.settlement_date \
                and (period_start <= contract_id.settlement_date <= period_end):
            period_info['Per_FechaRetiro'] = contract_id.settlement_date

        return period_info

    def _build_employer_ne(self):
        # Ver tablas 5.4.1 a 5.4.3
        partner_id = self.company_id.partner_id
        employer_info = {
            'Emp_RazonSocial': partner_id.name,
            'Emp_PrimerApellido': '',
            'Emp_SegundoApellido': '',
            'Emp_PrimerNombre': '',
            'Emp_OtrosNombres': '',
            'Emp_NIT': partner_id.vat,
            'Emp_DV': partner_id.l10n_co_verification_code,
            'Emp_Pais': partner_id.country_id.code or '',
            'Emp_DepartamentoEstado':
                partner_id.state_id.dian_code or '',
            'Emp_MunicipioCiudad': partner_id.city_id.dian_code or '',
            'Emp_Direccion': partner_id.street,

        }
        return employer_info

    def _build_employee_ne(self):
        # Ver tabla 5.5.3 a 5.5.4
        # Crear un campo para alto riesgo
        # Ver tabla 5.2.1
        # Crear campo de salario integral
        contract = self.contract_id
        partner = contract.employee_id.partner_id
        work_city_id = contract.work_city_id
        name1 = ''
        name2 = ''
        lastname1 = ''
        lastname2 = ''
        if partner.name and not partner.name1 and not partner.lastname1:
            name = partner.name.strip().split(' ')
            name1 = name[0]
            if len(name) == 2:
                lastname1 = name[1]
            elif len(name) == 3:
                name2 = name[1]
                lastname1 = name[2]
            elif len(name) >= 4:
                name2 = name[1]
                lastname1 = name[2]
                lastname2 = name[3]
        employee_info = {
            'Tra_TipoTrabajador':
                contract.fiscal_type_id
                and contract.fiscal_type_id.code
                or '',
            'Tra_SubTipoTrabajador':
                contract.fiscal_subtype_id
                and contract.fiscal_subtype_id.code in ['00', '01']
                and contract.fiscal_subtype_id.code
                or '00',
            'Tra_AltoRiesgoPension':
                contract.high_risk
                and 'true'
                or 'false',  # TODO: Validar
            'Tra_TipoDocumento':
                partner.l10n_latam_identification_type_id.dian_code
                or '',
            'Tra_NumeroDocumento': (partner.vat or '').strip(),
            'Tra_partner_name': partner.name or '',
            'Tra_partner_id': partner.id or False,
            'Tra_PrimerApellido': partner.lastname1 or lastname1,
            'Tra_SegundoApellido': partner.lastname2 or lastname2,
            'Tra_PrimerNombre': partner.name1 or name1,
            'Tra_OtrosNombres': partner.name2 or name2,
            'Tra_LugarTrabajoPais': work_city_id.country_id.code or '',
            'Tra_LugarTrabajoDepartamentoEstado':
                work_city_id.state_id.dian_code
                or '',
            'Tra_LugarTrabajoMunicipioCiudad':
                work_city_id.dian_code
                or '',
            'Tra_LugarTrabajoDireccion': partner.street,
            'Tra_SalarioIntegral':
                'false',  # TODO: Es obligatorio definir 'true' o 'false'
            'Tra_TipoContrato': CONTRACT_TYPE.get(contract.term, ''),
            'Tra_Sueldo': contract.wage,
            'Tra_CodigoTrabajador': '',
        }

        return employee_info

    def _build_workplace(self):
        city = self.contract_id.contract_city_id
        state = city.state_id
        country = city.country_id
        workplace = {
            'LGX_Pais': country.code,
            'LGX_DepartamentoEstado': state.dian_code,
            'LGX_MunicipioCiudad': city.dian_code,
            'LGX_Idioma': "es"
        }
        return workplace

    def _build_basic_wage(self):
        # basic = self.env.ref('hr_payroll_co.hc_basico')
        concept_codes = ('BASICO')
        novelty_codes = ('BAS')
        basic_line = self.payslip_line_ids.filtered(
            lambda x: str(x.concept_id.code) in concept_codes \
                or self._is_dian_concept(x, novelty_codes))
            # [line for line in self.payslip_line_ids
            #  if line.concept_id.id == basic.id]
        # basic_lines = [n.payslip_line_ids.filtered(
        #         lambda x: x.concept_id.id == basic.id)[0] for n in self]
        if not basic_line:
            return {
                'Dev_Bas_DiasTrabajados': 0,
                'Dev_Bas_SueldoTrabajado': 0
            }
        return {
            'Dev_Bas_DiasTrabajados': sum(basic_line.filtered(lambda x: x.total).mapped('qty')),
            # basic_line[0].qty,
            'Dev_Bas_SueldoTrabajado': sum(basic_line.mapped('total')),
            # basic_line[0].total
        }

    def _build_sub_trans(self):
        # sub_trans = self.env.ref('hr_payroll_co.hc_sub_trans')
        concept_codes = ('SUB_TRANS')
        novelty_codes = ('TPT')
        aux_t = 0
        # TODO: Es la suma de los totales o solamente uno
        viat_nv_codes = ('VMA')
        viat_s = 0
        viat_ns = 0
        sub_trans_line = self.payslip_line_ids.filtered(
            lambda x: str(x.concept_id.code) in concept_codes \
                or self._is_dian_concept(x, novelty_codes))
        viat_lines = self.payslip_line_ids.filtered(lambda x:
                self._is_dian_concept(x, viat_nv_codes))
        if sub_trans_line:
            aux_t = sum(sub_trans_line.mapped('total'))
        if viat_lines:
            viat_s = sum(line.total for line in viat_lines 
                if self._is_salary_earning(line))
            viat_ns = sum(line.total for line in viat_lines
                if self._is_no_salary_earning(line))
        return {
            'AuxilioTransporte': '{:.2f}'.format(aux_t),
            'ViaticoManutAlojS': '{:.2f}'.format(viat_s),
            'ViaticoManutAlojNS': '{:.2f}'.format(viat_ns),
        }

    def _build_overtime(self, overtime):
        return {
            'HoraInicio': '',
            'HoraFin': '',
            'Cantidad': '{:.0f}'.format(overtime.qty),
            'Porcentaje': '{:.2f}'.format(overtime.overtime_type_id.dian_concept_id.percentage),
            # HEP.get(code, ''),
            # '{:.2f}'.format(overtime.overtime_type_id.rate),
            'Pago': '{:.2f}'.format(overtime.amount),
        }

    def _get_overtime_payslip_line_by_code(self, code):
        def equals_code(line, code):
            return line.overtime_id.overtime_type_id.dian_concept_id.dian_code == code

        def is_overtime(line):
            return line.overtime_id

        return [line for line in self.payslip_line_ids
                if is_overtime(line) and equals_code(line, code)]

    def _build_hed_overtimes(self):
        lines = self._get_overtime_payslip_line_by_code('HED')
        return [self._build_overtime(line.overtime_id) for line in lines]

    def _build_hen_overtimes(self):
        lines = self._get_overtime_payslip_line_by_code('HEN')
        return [self._build_overtime(line.overtime_id) for line in lines]

    def _build_hrn_overtimes(self):
        lines = self._get_overtime_payslip_line_by_code('HRN')
        return [self._build_overtime(line.overtime_id) for line in lines]

    def _build_heddf_overtimes(self):
        lines = self._get_overtime_payslip_line_by_code('HEDDF')
        return [self._build_overtime(line.overtime_id) for line in lines]

    def _build_hrddf_overtimes(self):
        lines = self._get_overtime_payslip_line_by_code('HRDDF')
        return [self._build_overtime(line.overtime_id) for line in lines]

    def _build_hendf_overtimes(self):
        lines = self._get_overtime_payslip_line_by_code('HENDF')
        return [self._build_overtime(line.overtime_id) for line in lines]

    def _build_hrndf_overtimes(self):
        lines = self._get_overtime_payslip_line_by_code('HRNDF')
        return [self._build_overtime(line.overtime_id) for line in lines]

    def _build_holidays(self):
        # vac_lic = self.env.ref('hr_payroll_co.hc_vac_liq')
        holidays = {}
        payslip_ids = self.env['hr.payslip']
        concept_codes = ('ZZZ')
        if self.company_id.hr_provisions_vac == 'no':
            return self._build_holiday_normal()
        elif self.company_id.hr_provisions_vac == 'monthly':
            concept_codes = ('PVAC')
            payslip_ids = self
        elif self.company_id.hr_provisions_vac == 'consolidated':
            period_end = max([n.period_id.end for n in self])
            if period_end.month == 12:
                concept_codes = ('PVAC')
                date_start = '%s/01/01' % period_end.year
                date_end = period_end
                payslip_ids = payslip_ids.search([('contract_id','=',self.contract_id.id),
                                                ('state','=','paid'),
                                                ('period_id.start','>=',date_start),
                                                ('period_id.end','<=',date_end)])
            else:
                concept_codes = ('VACL')
                payslip_ids = self
        vac_line = payslip_ids.payslip_line_ids.filtered(lambda x: 
            self._is_dian_concept(x, concept_codes))
        
        if vac_line:
            period_start = min([n.period_id.start for n in self])
            period_end = max([n.period_id.end for n in self])
            holidays['VacacionesComunes'] = [{
                'FechaInicio': period_start,
                'FechaFin': period_end,
                'Cantidad': '{:.0f}'.format(sum(vac_line.mapped('qty'))),
                'Pago': '{:.2f}'.format(sum(vac_line.mapped('total')))
            }]
        return holidays
    
    def _has_vacation_lines(self):
        vac_lic = ('VAC_LIQ')
        leave_cat_type = ('VAC', 'VAC_MONEY')
        vac_lines = self.payslip_line_ids.filtered(
            lambda x: x.leave_id and x.leave_id.leave_type_id.category_type in leave_cat_type
                or str(x.concept_id.code) in vac_lic)
        if vac_lines:
            return True
        return False
    
    def _build_holiday_normal(self):
        vac_lic = ('VAC_LIQ')
        dian_concepts = ('VACL', 'VAP')
        holidays = {}

        def is_holiday(line):
            return line.leave_id.leave_type_id.category_type == 'VAC'

        def is_holiday_money(line):
            return line.leave_id.leave_type_id.category_type == 'VAC_MONEY' \
                or self._is_dian_concept(line, dian_concepts) # str(line.concept_id.code) in vac_lic

        def is_leave(line):
            return line.leave_id or self._is_dian_concept(line, dian_concepts) # str(line.concept_id.code) in vac_lic

        def _build_holiday(holiday):
            return {
                'FechaInicio': holiday.leave_id.date_start,
                'FechaFin': holiday.leave_id.date_end,
                'Cantidad': '{:.0f}'.format(holiday.qty),
                'Pago': '{:.2f}'.format(holiday.total)
            }

        def _build_holiday_money(holiday_money):
            return {
                'Cantidad': '{:.0f}'.format(holiday_money.qty),
                'Pago': '{:.2f}'.format(holiday_money.total)
            }

        leave_lines = [line for line in self.payslip_line_ids
                       if is_leave(line)]
        holiday_lines = [_build_holiday(leave) for leave in leave_lines
                         if is_holiday(leave)]
        holiday_money_lines = \
            [_build_holiday_money(leave) for leave in leave_lines
             if is_holiday_money(leave)]

        if holiday_lines:
            holidays['VacacionesComunes'] = holiday_lines

        if holiday_money_lines:
            holidays['VacacionesCompensadas'] = holiday_money_lines

        return holidays

    def _build_prima(self):
        # prima = self.env.ref('hr_payroll_co.hc_prima')
        # prima_lic = self.env.ref('hr_payroll_co.hc_prima_liq')
        payslip_ids = self.env['hr.payslip']
        concept_codes = ('ZZZ')
        if self.company_id.hr_provisions_pri == 'no':
            concept_codes = ('PRI', 'PRIL') #('PRIMA', 'PRIMA_LIQ')
            payslip_ids = self
        elif self.company_id.hr_provisions_pri == 'monthly':
            concept_codes = ('PPRI')
            payslip_ids = self
        elif self.company_id.hr_provisions_pri == 'consolidated':
            period_end = max([n.period_id.end for n in self])
            if period_end.month == 12:
                concept_codes = ('PPRI')
                date_start = '%s/01/01' % period_end.year
                date_end = period_end
                payslip_ids = payslip_ids.search([('contract_id','=',self.contract_id.id),
                                                ('state','=','paid'),
                                                ('period_id.start','>=',date_start),
                                                ('period_id.end','<=',date_end)])
            else:
                concept_codes = ('PRIL')
                payslip_ids = self
        prima_line = payslip_ids.payslip_line_ids.filtered(lambda x: 
            self._is_dian_concept(x, concept_codes) \
                and self._is_salary_earning(x))
        prima_ns_line = payslip_ids.payslip_line_ids.filtered(lambda x: 
            self._is_dian_concept(x, concept_codes) \
                and self._is_no_salary_earning(x))
        return {
            'Dev_Pri_Cantidad': '{:.0f}'.format(
                sum(prima_line.mapped('qty'))),
            'Dev_Pri_Pago': '{:.2f}'.format(
                sum(prima_line.mapped('total'))),
            'Dev_Pri_PagoNS': '{:.2f}'.format(
                sum(prima_ns_line.mapped('total'))),
        }

    def _build_ces(self):
        # ces = self.env.ref('hr_payroll_co.hc_ces')
        # ces_liq = self.env.ref('hr_payroll_co.hc_ces_liq')
        payslip_ids = self.env['hr.payslip']
        ces_codes = ('ZZZ') #('CES', 'CES_LIQ')
        ices_codes = ('ZZZ')
        if self.company_id.hr_provisions_ces == 'no':
            ces_codes = ('CES', 'CESL') #('CES', 'CES_LIQ')
            ices_codes = ('ICE', 'ICEL')
            payslip_ids = self
        elif self.company_id.hr_provisions_ces == 'monthly':
            ces_codes = ('PCES')
            ices_codes = ('PICE')
            payslip_ids = self
        elif self.company_id.hr_provisions_ces == 'consolidated':
            period_end = max([n.period_id.end for n in self])
            if period_end.month == 12:
                ces_codes = ('PCES')
                ices_codes = ('PICE')
                date_start = '%s/01/01' % period_end.year
                date_end = period_end
                payslip_ids = payslip_ids.search([('contract_id','=',self.contract_id.id),
                                                ('state','=','paid'),
                                                ('period_id.start','>=',date_start),
                                                ('period_id.end','<=',date_end)])
            else:
                ces_codes = ('CESL')
                ices_codes = ('ICEL')
                payslip_ids = self
        ces_line = payslip_ids.payslip_line_ids.filtered(
            lambda x: self._is_dian_concept(x, ces_codes))
        ices_line = payslip_ids.payslip_line_ids.filtered(
            lambda x: self._is_dian_concept(x, ices_codes))
        # TODO: Falta tener en cuenta las novedades

        if not ces_line:
            return {
                'Dev_Ces_Pago': '0.00',
                'Dev_Ces_Porcentaje': '0.00',
                'Dev_Ces_PagoIntereses': '0.00',
            }
        pago = sum(ces_line.mapped('total'))
        ices_total = sum(ices_line.mapped('total'))
        rate = ices_total / pago # sum(ces_line.mapped('qty')) * 0.12 / 360
        return {
            'Dev_Ces_Pago': '{:.2f}'.format(pago),
            'Dev_Ces_Porcentaje': '{:.2f}'.format(rate),
            'Dev_Ces_PagoIntereses': '{:.2f}'.format(ices_total),
        }

    def _build_inabilitys(self):
        # TODO: se debe dividir la categoria
        #  "Accidente de trabajo - Enfermedad profesional"

        def is_sickness(line):
            return line.leave_id.leave_type_id.category_type == "SICKNESS"

        def is_at_ep(line):
            return line.leave_id.leave_type_id.category_type == "AT_EP"

        def is_leave(line):
            return line.leave_id

        def build_sickness(line):
            return {
                'FechaInicio': line.leave_id.date_start,
                'FechaFin': line.leave_id.date_end,
                'Cantidad': '{:.0f}'.format(line.qty),
                'Tipo': '1',
                'Pago': '{:.2f}'.format(line.total),
            }

        def build_at_ep(line):
            return {
                'FechaInicio': line.leave_id.date_start,
                'FechaFin': line.leave_id.date_end,
                'Cantidad': '{:.0f}'.format(line.qty),
                'Tipo': '2',
                'Pago': '{:.2f}'.format(line.total),
            }

        leaves = [line for line in self.payslip_line_ids if is_leave(line)]
        sicknesses = [build_sickness(leave) for leave in leaves
                      if is_sickness(leave)]
        at_ep = [build_at_ep(leave) for leave in leaves if is_at_ep(leave)]

        return sicknesses + at_ep

    def _build_licenses(self):

        def is_mat_pat(line):
            return line.leave_id.leave_type_id.category_type \
                in ('MAT_LIC', 'PAT_LIC')

        def is_pay(line):
            return line.leave_id.leave_type_id.category_type == "PAY"

        def is_no_pay(line):
            return line.leave_id.leave_type_id.category_type == "NO_PAY"

        def is_leave(line):
            return line.leave_id

        def build_mat_pat(line):
            return {
                'FechaInicio': line.leave_id.date_start,
                'FechaFin': line.leave_id.date_end,
                'Cantidad': '{:.0f}'.format(line.qty),
                'Pago': '{:.2f}'.format(line.total),
            }

        def build_pay(line):
            return {
                'FechaInicio': line.leave_id.date_start,
                'FechaFin': line.leave_id.date_end,
                'Cantidad': '{:.0f}'.format(line.qty),
                'Pago': '{:.2f}'.format(line.total),
            }

        def build_no_pay(line):
            return {
                'FechaInicio': line.leave_id.date_start,
                'FechaFin': line.leave_id.date_end,
                'Cantidad': '{:.0f}'.format(line.qty),
            }

        leaves = [line for line in self.payslip_line_ids if is_leave(line)]
        mat_pat = [build_mat_pat(leave) for leave in leaves
                   if is_mat_pat(leave)]
        pay = [build_pay(leave) for leave in leaves if is_pay(leave)]
        no_pay = [build_no_pay(leave) for leave in leaves if is_no_pay(leave)]

        return {
            'LicenciaMP': mat_pat,
            'LicenciaR': pay,
            'LicenciaNR': no_pay
        }

    def _build_bonds(self):
        novelty_codes = ('BON')
        noveltys = [line for line in self.payslip_line_ids 
                    if self._is_dian_concept(line, novelty_codes)]
        salary_bonds = sum(bond.total for bond in noveltys
                        if self._is_salary_earning(bond))
        no_salary_bonds = sum(bond.total for bond in noveltys
                           if self._is_no_salary_earning(bond))
        out = {}
        if no_salary_bonds:
            out['BonificacionNS'] = '{:.2f}'.format(float(no_salary_bonds))
        if salary_bonds:
            out['BonificacionS'] = '{:.2f}'.format(float(salary_bonds))
        return out and [out] or []
    
    def _build_aids(self):
        novelty_codes = ('AUX')
        noveltys = [line for line in self.payslip_line_ids
                    if self._is_dian_concept(line, novelty_codes)]
        salary_aids = sum(aid.total for aid in noveltys
                        if self._is_salary_earning(aid))
        no_salary_aids = sum(aid.total for aid in noveltys
                           if self._is_no_salary_earning(aid))
        out = {}
        if no_salary_aids:
            out['AuxilioNS'] = '{:.2f}'.format(float(no_salary_aids))
        if salary_aids:
            out['AuxilioS'] = '{:.2f}'.format(float(salary_aids))
        return out and [out] or []
    
    def _build_legal_strikes(self):
        # TODO: Se entiende como una ausencia
        novelty_codes = ('HGL')

        def build_strikes(line):
            return {
                # Fecha en la que el trabajador inicia la huelga
                'FechaInicio': '',
                # Fecha en la que el trabajador termina la huelga
			    'FechaFin': '',
                # Canridad de días que el trabajador estuvo inactivo por la huelga
			    'Cantidad': ''
            }
        noveltys = [line for line in self.payslip_line_ids
                    if self._is_dian_concept(line, novelty_codes)]
        
        out = [build_strikes(line) for line in noveltys]
        return out
    
    def _build_other_concepts(self):
        novelty_codes = ('OCP')
        
        def build_concept(lines, typec):
            out = {}
            for line in lines:
                if line.name not in out:
                    out[line.name] = {
                        'DescripcionConcepto': line.name or '-',
                    }
                    if typec == 'S':
                        out[line.name]['ConceptoS'] = line.total
                    else:
                        out[line.name]['ConceptoNS'] = line.total
                else:
                    if typec == 'S':
                        out[line.name]['ConceptoS'] += line.total
                    else:
                        out[line.name]['ConceptoNS'] += line.total
            out_list = []
            for v in out.values():
                if 'ConceptoS' in v:
                    v['ConceptoS'] = '{:.2f}'.format(v['ConceptoS'])
                if 'ConceptoNS' in v:
                    v['ConceptoNS'] = '{:.2f}'.format(v['ConceptoNS'])
                out_list.append(v)
            return out_list

        noveltys = self.payslip_line_ids.filtered(lambda line: self._is_dian_concept(line, novelty_codes))
        salary_concepts = build_concept(noveltys.filtered(lambda ln: self._is_salary_earning(ln)), 'S')
        no_salary_concepts = build_concept(noveltys.filtered(lambda ln: self._is_no_salary_earning(ln)), 'NS') 
        out = salary_concepts + no_salary_concepts
        return out
    
    def _build_compensations(self):
        ord_codes = ('COR')
        ext_codes = ('CEX')
        comp_ord = sum(line.total for line in self.payslip_line_ids 
                    if self._is_dian_concept(line, ord_codes))
        comp_ext = sum(line.total for line in self.payslip_line_ids 
                    if self._is_dian_concept(line, ext_codes))
        out = {}
        if comp_ord or comp_ext:
            out = {
                'CompensacionO': '{:.2f}'.format(float(comp_ord)),
                'CompensacionE': '{:.2f}'.format(float(comp_ext))
            }
        return out and [out] or []

    def _build_bonds_epctv(self):
        epctv_pay_codes = ('BEP')
        epctv_eat_codes = ('BEA')
        noveltys_pay = [line for line in self.payslip_line_ids 
                        if self._is_dian_concept(line, epctv_pay_codes)]
        nv_pay_s = sum(line.total for line in noveltys_pay
                       if self._is_salary_earning(line))
        nv_pay_ns = sum(line.total for line in noveltys_pay
                        if self._is_no_salary_earning(line))
        
        noveltys_eat = [line for line in self.payslip_line_ids 
                        if self._is_dian_concept(line, epctv_eat_codes)]
        nv_eat_s = sum(line.total for line in noveltys_eat
                       if self._is_salary_earning(line))
        nv_eat_ns = sum(line.total for line in noveltys_eat
                        if self._is_no_salary_earning(line))
        out = {}
        if nv_pay_s:
            out['PagoS'] = '{:.2f}'.format(float(nv_pay_s))
        if nv_pay_ns:
            out['PagoNS'] = '{:.2f}'.format(float(nv_pay_ns))
        if nv_eat_s:
            out['PagoAlimentacionS'] = '{:.2f}'.format(float(nv_eat_s))
        if nv_eat_ns:
            out['PagoAlimentacionNS'] = '{:.2f}'.format(float(nv_eat_ns))
        return out and [out] or []
    
    def _build_commissions(self):
        novelty_codes = ('COM')
        comm = sum(line.total for line in self.payslip_line_ids 
                    if self._is_dian_concept(line, novelty_codes))
        out = {}
        if comm:
            out['Comision'] = '{:.2f}'.format(float(comm))
        return out
    
    def _build_payment_partner(self):
        novelty_codes = ('PTP')
        comm = sum(line.total for line in self.payslip_line_ids 
                    if self._is_dian_concept(line, novelty_codes))
        out = {}
        if comm:
            out['PagoTercero'] = '{:.2f}'.format(float(comm))
        return out

    def _build_advances(self):
        novelty_codes = ('ANT')
        comm = sum(line.total for line in self.payslip_line_ids 
                    if self._is_dian_concept(line, novelty_codes))
        out = {}
        if comm:
            out['Anticipo'] = '{:.2f}'.format(float(comm))
        return out
    
    def _build_dotation(self):
        novelty_codes = ('DOT')
        comm = sum(line.total for line in self.payslip_line_ids 
                    if self._is_dian_concept(line, novelty_codes))
        out = '{:.2f}'.format(float(comm))
        return out
    
    def _build_sustenance_support(self):
        novelty_codes = ('ASO')
        comm = sum(line.total for line in self.payslip_line_ids 
                    if self._is_dian_concept(line, novelty_codes))
        out = '{:.2f}'.format(float(comm))
        return out
    
    def _build_teleworking(self):
        novelty_codes = ('TTR')
        comm = sum(line.total for line in self.payslip_line_ids 
                    if self._is_dian_concept(line, novelty_codes))
        out = '{:.2f}'.format(float(comm))
        return out
    
    def _build_retirement_bonus(self):
        novelty_codes = ('BRT')
        comm = sum(line.total for line in self.payslip_line_ids 
                    if self._is_dian_concept(line, novelty_codes))
        out = '{:.2f}'.format(float(comm))
        return out
    
    def _build_indemnification(self):
        novelty_codes = ('IND')
        comm = sum(line.total for line in self.payslip_line_ids 
                    if self._is_dian_concept(line, novelty_codes))
        out = '{:.2f}'.format(float(comm))
        return out
    
    def _build_return(self):
        novelty_codes = ('REI')
        comm = sum(line.total for line in self.payslip_line_ids 
                    if self._is_dian_concept(line, novelty_codes))
        out = '{:.2f}'.format(float(comm))
        return out
    
    # DEDUCTIONS

    def _build_deduction_health(self):
        # deduction_id = self.env.ref('hr_payroll_co.hc_ded_eps')
        concept_codes = ('DED_EPS')
        deduction_eps = self.payslip_line_ids.filtered(
            lambda x: str(x.concept_id.code) in concept_codes)
        # [line for line in self.payslip_line_ids
        #                  if line.concept_id.id == deduction_id.id]
        if not deduction_eps:
            return {
                'Ded_Salud_Porcentaje': '0.00',
                'Ded_Salud_Deduccion': '0.00'
            }
        return {
            'Ded_Salud_Porcentaje': '{:.2f}'.format(float(
                sum(deduction_eps.mapped('rate'))/len(deduction_eps))),
            'Ded_Salud_Deduccion': '{:.2f}'.format(float(
                sum(deduction_eps.mapped('total'))))
        }

    def _build_deduction_pension(self):
        # deduction_id = self.env.ref('hr_payroll_co.hc_ded_pens')
        concept_codes = ('DED_PENS')
        deduction_pension = self.payslip_line_ids.filtered(
            lambda x: str(x.concept_id.code) in concept_codes)
        # [line for line in self.payslip_line_ids
        #                      if line.concept_id.id == deduction_id.id]
        if not deduction_pension:
            return {
                'Ded_FoPen_Porcentaje': '0.00',
                'Ded_FoPen_Deduccion': '0.00'
            }
        return {
            'Ded_FoPen_Porcentaje': '{:.2f}'.format(float(
                sum(deduction_pension.mapped('rate'))/len(deduction_pension))),
            'Ded_FoPen_Deduccion': '{:.2f}'.format(float(
                sum(deduction_pension.mapped('total'))))
        }

    def _build_deduction_solidarity(self):
        # ded_id = self.env.ref('hr_payroll_co.hc_fond_sol')
        # TODO: Falta cuando viene de una novedad
        concept_codes = ('FOND_SOL')
        ded_solidarity = self.payslip_line_ids.filtered(
            lambda x: str(x.concept_id.code) in concept_codes)
        # [line for line in self.payslip_line_ids
        #                         if line.concept_id.id == ded_id.id]
        if not ded_solidarity:
            return {
                'Ded_FoSP_Porcentaje': '0.00',
                'Ded_FoSP_Deduccion': '0.00',
            }
        return {
            'Ded_FoSP_Porcentaje': '{:.2f}'.format(float(
                sum(ded_solidarity.mapped('rate'))/len(ded_solidarity))),
            'Ded_FoSP_Deduccion': '{:.2f}'.format(float(
                sum(ded_solidarity.mapped('total')))),
        }

    def _build_deduction_subsistence(self):
        # ded_id = self.env.ref('hr_payroll_co.hc_fond_sub')
        # TODO: Falta cuando viene de una novedad
        concept_codes = ('FOND_SUB')
        ded_subsistence = self.payslip_line_ids.filtered(
            lambda x: str(x.concept_id.code) in concept_codes)
        if not ded_subsistence:
            return {
                'Ded_FoSP_PorcentajeSub': '0.00',
                'Ded_FoSP_DeduccionSub': '0.00'
            }
        return {
            'Ded_FoSP_PorcentajeSub': '{:.2f}'.format(float(
                sum(ded_subsistence.mapped('rate'))/len(ded_subsistence))),
            'Ded_FoSP_DeduccionSub': '{:.2f}'.format(float(
                sum(ded_subsistence.mapped('total'))))
        }
    
    def _build_sanctions(self):
        spub_codes = ('SPU')
        spriv_codes = ('SPV')
        spub = sum(line.total for line in self.payslip_line_ids 
                   if self._is_dian_concept(line, spub_codes))
        spriv = sum(line for line in self.payslip_line_ids 
                    if self._is_dian_concept(line, spriv_codes))
        out = {}
        if spub or spriv:
            out['SancionPublic'] = '{:.2f}'.format(float(spub))
            out['SancionPriv'] = '{:.2f}'.format(float(spriv))
        return out and [out] or []
    
    def _build_promissory_notes(self):
        novelty_codes = ('LIB')

        def build_notes(line):
            return {
                'Descripcion': line.name or '**',
                'Deduccion': '{:.2f}'.format(line.total)
            }
        
        noveltys = [line for line in self.payslip_line_ids 
                if self._is_dian_concept(line, novelty_codes)]
        out = [build_notes(line) for line in noveltys]
        return out

    def _build_payment_partner_ded(self):
        novelty_codes = ('PTR')
        comm = sum(line.total for line in self.payslip_line_ids 
                   if self._is_dian_concept(line, novelty_codes))
        out = {}
        if comm:
            out['PagoTercero'] = '{:.2f}'.format(float(comm))
        return out
    
    def _build_advances_ded(self):
        novelty_codes = ('ADV')
        comm = sum(line.total for line in self.payslip_line_ids 
                    if self._is_dian_concept(line, novelty_codes))
        out = {}
        if comm:
            out['Anticipo'] = '{:.2f}'.format(float(comm))
        return out

    def _build_other_ded(self):
        novelty_codes = ('ODD')
        comm = sum(line.total for line in self.payslip_line_ids 
                    if self._is_dian_concept(line, novelty_codes))
        out = {}
        if comm:
            out['OtraDeduccion'] = '{:.2f}'.format(float(comm))
        return out

    def _build_voluntary_pension(self):
        novelty_codes = ('PVL')
        comm = sum(line.total for line in self.payslip_line_ids 
                    if self._is_dian_concept(line, novelty_codes))
        out = '{:.2f}'.format(float(comm))
        return out

    def _build_deduction_rtefte(self):
        # TODO puede ser por concepto y por novedad
        concept_codes = ('RTEFTE')
        novelty_codes = ('RFT')
        ded_rtefte = self.payslip_line_ids.filtered(
            lambda x: str(x.concept_id.code) in concept_codes \
                or self._is_dian_concept(x, novelty_codes))
        return '{:.2f}'.format(float(sum(ded_rtefte.mapped('total'))))
    
    def _build_afc(self):
        novelty_codes = ('AFC')
        comm = sum(line.total for line in self.payslip_line_ids 
                    if self._is_dian_concept(line, novelty_codes))
        out = '{:.2f}'.format(float(comm))
        return out
    
    def _build_cooperative(self):
        novelty_codes = ('COO')
        comm = sum(line.total for line in self.payslip_line_ids 
                    if self._is_dian_concept(line, novelty_codes))
        out = '{:.2f}'.format(float(comm))
        return out

    def _build_tax_embargo(self):
        novelty_codes = ('EMB')
        comm = sum(line.total for line in self.payslip_line_ids 
                    if self._is_dian_concept(line, novelty_codes))
        out = '{:.2f}'.format(float(comm))
        return out
    
    def _build_complementary_plan(self):
        novelty_codes = ('CPN')
        comm = sum(line.total for line in self.payslip_line_ids 
                    if self._is_dian_concept(line, novelty_codes))
        out = '{:.2f}'.format(float(comm))
        return out
    
    def _build_education(self):
        novelty_codes = ('EDU')
        comm = sum(line.total for line in self.payslip_line_ids 
                    if self._is_dian_concept(line, novelty_codes))
        out = '{:.2f}'.format(float(comm))
        return out
    
    def _build_return_ded(self):
        novelty_codes = ('RIN')
        comm = sum(line.total for line in self.payslip_line_ids 
                    if self._is_dian_concept(line, novelty_codes))
        out = '{:.2f}'.format(float(comm))
        return out
    
    def _build_debt(self):
        novelty_codes = ('DEU')
        comm = sum(line.total for line in self.payslip_line_ids 
                    if self._is_dian_concept(line, novelty_codes))
        out = '{:.2f}'.format(float(comm))
        return out

    def _get_total_earning(self):

        def is_earning(line):
            earning_categories = [
                'earnings',
                'o_salarial_earnings',
                'comp_earnings',
                'o_rights',
                'o_earnings',
                'non_taxed_earnings'
            ]
            return line.category in earning_categories

        earnings = [line.total for line in self.payslip_line_ids
                    if is_earning(line)]
        return sum(earnings)

    def _get_total_deductions(self):

        def is_deduction(line):
            return line.category == 'deductions'

        earnings = [line.total for line in self.payslip_line_ids
                    if is_deduction(line)]
        return sum(earnings)

    def _get_notes_edi_hr(self):
        '''
           INFO:    Texto libre, relativo al documento,
           Ejemplo: Información de Novedades de los trabajadores.
           Salida:
            out = {
                'Nota1': '',
                'Nota2': ''
            }
        '''
        out = {}
        # TODO: Falta definir como gestionar notas
        return out

