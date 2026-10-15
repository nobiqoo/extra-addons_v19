# -*- coding: utf-8 -*-
from contextlib import contextmanager

from odoo import models
from odoo.addons.hr_payroll_co.models.hr_concept.hr_concept_base import CONCEPTS
from odoo.addons.utilities_collection import orm
from odoo.addons.utilities_collection.time import days360

# Conceptos que liquidan la fracción de profesor. Se registran en la lista de
# conceptos calculables de la nómina colombiana, que es la que recorre
# hr.payslip para saber qué método invocar.
TEACHER_CONCEPTS = [
    'PRV_CES_PROF', 'PRV_ICES_PROF', 'PRV_PRIMA_PROF', 'PRV_VAC_PROF',
]
for _code in TEACHER_CONCEPTS:
    if _code not in CONCEPTS:
        CONCEPTS.append(_code)

# Porcentaje de provisión de la fracción de profesor por concepto.
TEACHER_RATE_PARAM = {
    'PRV_CES_PROF': 'hr_payroll_colombo.teacher_severance_percentage',
    'PRV_ICES_PROF': 'hr_payroll_colombo.'
                     'teacher_interest_severance_percentage',
    'PRV_PRIMA_PROF': 'hr_payroll_colombo.teacher_prima_percentage',
    'PRV_VAC_PROF': 'hr_payroll_colombo.teacher_holidays_percentage',
}

# Subtipos de profesor a los que se aplican los porcentajes de provisión de
# profesor, según lo marcado en Ajustes. Los que no estén marcados provisionan
# como cualquier empleado.
TEACHER_SUBTYPE_PARAM = {
    'type_10': 'hr_payroll_colombo.teacher_provisions_type_10',
    'type_12': 'hr_payroll_colombo.teacher_provisions_type_12',
    'mixed': 'hr_payroll_colombo.teacher_provisions_mixed',
}

# Categorías que la nómina colombiana consulta por defecto al sumar los
# devengos de nóminas anteriores.
DEFAULT_CATEGORIES = ('earnings', 'o_salarial_earnings', 'comp_earnings',
                      'o_rights', 'o_earnings')


class HrConcept(models.Model):
    _inherit = 'hr.concept'

    # ------------------------------------------------------------------
    # Horas del profesor
    # ------------------------------------------------------------------
    def get_teacher_hours_amount(self, data_payslip):
        """Valor de las horas aprobadas del profesor en el periodo.

        Sale de las líneas de la novedad de horas que corresponden al periodo
        liquidado, que es lo que el módulo académico consolidó para el mes.
        """
        if 'TEACHER_HOURS' in data_payslip:
            return data_payslip['TEACHER_HOURS']

        amount = 0.0
        if data_payslip['contract'].has_teacher_fraction():
            novelty_lines = self.env['hr.novelty.line'].search([
                ('contract_id', '=', data_payslip['contract'].id),
                ('period_id', '=', data_payslip['period'].id),
                ('novelty_id.is_teacher_hours', '=', True),
                ('state', 'in', ('validated', 'paid')),
            ])
            amount = sum(novelty_lines.mapped('amount'))

        data_payslip['TEACHER_HOURS'] = amount
        return amount

    def get_teacher_hours_with_minimum(self, data_payslip):
        """Valor de las horas del mes con el piso del salario mínimo.

        La seguridad social del profesor se cotiza sobre el valor de las horas
        y nunca por debajo del mínimo legal de los días cotizados.
        """
        amount = self.get_teacher_hours_amount(data_payslip)
        return max(amount, self.get_smmlv_floor(data_payslip))

    def get_smmlv_floor(self, data_payslip):
        """Salario mínimo proporcional a los días cotizados en el periodo.

        Sigue el mismo criterio de días de la nómina colombiana para el piso
        de las deducciones: descuenta los días anteriores al ingreso, los
        posteriores al retiro y las licencias no remuneradas.
        """
        contract = data_payslip['contract']
        period = data_payslip['period']
        smmlv = data_payslip['economic_variables']['SMMLV'][
            data_payslip['current_year_month']]
        is_biweekly = period.type_period == 'BIWEEKLY'
        is_q1 = is_biweekly and period.type_biweekly == 'FIRST'
        date_from = period.start
        date_to = period.end
        if is_biweekly and not is_q1:
            date_from = date_from.replace(day=1)
        if date_from < contract.date_start:
            date_from = contract.date_start
        if contract.settlement_date and date_to > contract.settlement_date:
            date_to = contract.settlement_date
        if data_payslip['payslip_type_id'].category == 'VAC':
            worked_days = len([d for d in data_payslip['payslip_days']
                               if d['day_type'] == 'A'])
        else:
            worked_days = days360(date_from, date_to)
        worked_days -= self.get_days_no_pay(data_payslip, {
            'contract': contract.id,
            'start': date_from,
            'end': date_to,
        })
        return smmlv / 30 * max(worked_days, 0)

    def apply_teacher_policy(self, data_payslip):
        """La política de cálculo por tipo de contrato está activa y el
        contrato liquida una fracción de profesor."""
        politics = data_payslip.get('politics', {})
        return (politics.get('hr_payroll_colombo.apply_contract_type_policy')
                and data_payslip['contract'].has_teacher_fraction())

    def apply_teacher_provisions(self, data_payslip):
        """La fracción de profesor del contrato se provisiona con los
        porcentajes de profesor: la opción está activa y el subtipo del
        contrato está marcado en Ajustes."""
        politics = data_payslip.get('politics', {})
        subtype_param = TEACHER_SUBTYPE_PARAM.get(
            data_payslip['contract'].teacher_subtype)
        return (self.apply_teacher_policy(data_payslip)
                and politics.get('hr_payroll_colombo.teacher_provisions')
                and subtype_param and politics.get(subtype_param))

    # ------------------------------------------------------------------
    # Salario básico
    # ------------------------------------------------------------------
    def _BASICO(self, data_payslip):
        """El profesor Tipo 10 o Tipo 12 no devenga salario básico.

        Su remuneración es el valor de las horas del mes, que llega como
        novedad. En el contrato de estos profesores el salario suele guardar
        el valor hora, que no debe liquidarse como sueldo mensual. La línea
        se conserva en cero con los días trabajados, porque de ella salen los
        días del auxilio de transporte, de las novedades que dependen de días
        trabajados y de la nómina electrónica.
        """
        res = super()._BASICO(data_payslip)
        if not (isinstance(res, dict)
                and self.apply_teacher_policy(data_payslip)
                and not data_payslip['contract'].has_administrative_fraction()):
            return res

        days = res['qty']
        data_payslip['BASICO'] = (0, days)
        data_payslip['wage'] = 0
        data_payslip['wage_no_base_ibc'] = 0
        res.update(value=0, total=0)
        return res

    # ------------------------------------------------------------------
    # IBC de seguridad social
    # ------------------------------------------------------------------
    def _compute_ibd(self, data_payslip):
        """El IBC del profesor no baja del salario mínimo.

        El valor de las horas ya entra al IBC como devengo salarial de la
        novedad, igual que el salario básico en el contrato mixto, así que
        aquí solo se aplica el piso legal, proporcional a los días cotizados
        para no inflar el IBC en un mes de ingreso, retiro o licencia.
        """
        res = super()._compute_ibd(data_payslip)
        if not self.apply_teacher_policy(data_payslip):
            return res

        smmlv = self.get_smmlv_floor(data_payslip)
        if data_payslip.get('IBD', 0) < smmlv:
            data_payslip['IBD'] = smmlv
        if 'IBD_DED' in data_payslip and data_payslip['IBD_DED'] < smmlv:
            data_payslip['IBD_DED'] = smmlv
        return res

    # ------------------------------------------------------------------
    # Auxilio de transporte
    # ------------------------------------------------------------------
    # El auxilio de transporte no necesita ajuste. La nómina colombiana ya
    # compara el tope de dos salarios mínimos contra los devengos del periodo,
    # que incluyen tanto el salario básico como el valor de las horas del
    # profesor —la novedad de horas es un devengo salarial—, y ya prorratea el
    # auxilio dividiendo el valor mensual entre 30 días y multiplicándolo por
    # los días trabajados.

    # ------------------------------------------------------------------
    # Provisiones de la fracción administrativa
    # ------------------------------------------------------------------
    def _teacher_skips_administrative_provision(self, data_payslip):
        """Un profesor que no es mixto no provisiona sobre salario básico."""
        return (self.apply_teacher_provisions(data_payslip)
                and not data_payslip['contract'].has_administrative_fraction())

    @contextmanager
    def _administrative_provision_context(self, data_payslip):
        """Concepto con el que se liquida la provisión administrativa.

        En el contrato mixto las horas del profesor se provisionan aparte con
        los conceptos de profesor, así que no pueden entrar también a la base
        de la provisión administrativa: ni como salario variable de las
        nóminas pagadas ni como devengo de la nómina en curso.
        """
        if not self.apply_teacher_provisions(data_payslip):
            yield self
            return

        current_hours = data_payslip.get('TEACHER_HOURS_CURRENT', {})
        for category, amount in current_hours.items():
            data_payslip[category] = data_payslip.get(category, 0) - amount
        try:
            yield self.with_context(exclude_teacher_hours=True)
        finally:
            for category, amount in current_hours.items():
                data_payslip[category] += amount

    @contextmanager
    def _teacher_wage_context(self, data_payslip):
        """Prestaciones del profesor Tipo 10 o Tipo 12 sobre sus horas.

        Su contrato guarda en el salario el valor hora. Mientras se liquida la
        prestación, el contrato se lee con salario cero y la base sale solo
        del promedio de las horas devengadas, que la nómina colombiana ya suma
        como salario variable.
        """
        if not (self.apply_teacher_policy(data_payslip)
                and not data_payslip['contract'].has_administrative_fraction()):
            yield
            return

        contract = data_payslip['contract']
        had_wage = 'wage' in data_payslip
        wage = data_payslip.get('wage')
        data_payslip['contract'] = contract.with_context(teacher_hours_wage=True)
        if had_wage:
            data_payslip['wage'] = (dict(wage, wage=0) if isinstance(wage, dict)
                                    else 0)
        try:
            yield
        finally:
            data_payslip['contract'] = contract
            if had_wage:
                data_payslip['wage'] = wage

    def _PRV_CES(self, data_payslip):
        if self._teacher_skips_administrative_provision(data_payslip):
            return
        with self._teacher_wage_context(data_payslip), \
                self._administrative_provision_context(data_payslip) as concept:
            return super(HrConcept, concept)._PRV_CES(data_payslip)

    def _PRV_ICES(self, data_payslip):
        if self._teacher_skips_administrative_provision(data_payslip):
            return
        with self._teacher_wage_context(data_payslip), \
                self._administrative_provision_context(data_payslip) as concept:
            return super(HrConcept, concept)._PRV_ICES(data_payslip)

    def _PRV_PRIMA(self, data_payslip):
        if self._teacher_skips_administrative_provision(data_payslip):
            return
        with self._teacher_wage_context(data_payslip), \
                self._administrative_provision_context(data_payslip) as concept:
            return super(HrConcept, concept)._PRV_PRIMA(data_payslip)

    def _PRV_VAC(self, data_payslip):
        if self._teacher_skips_administrative_provision(data_payslip):
            return
        with self._teacher_wage_context(data_payslip), \
                self._administrative_provision_context(data_payslip) as concept:
            return super(HrConcept, concept)._PRV_VAC(data_payslip)

    # ------------------------------------------------------------------
    # Pago y liquidación de prestaciones
    # ------------------------------------------------------------------
    # La base de días (360 o 330) la resuelve el contrato con
    # get_benefits_days_base; aquí solo se ajusta la base salarial del
    # profesor Tipo 10 o Tipo 12.
    def _PRIMA(self, data_payslip):
        with self._teacher_wage_context(data_payslip):
            return super()._PRIMA(data_payslip)

    def _PRIMA_LIQ(self, data_payslip):
        with self._teacher_wage_context(data_payslip):
            return super()._PRIMA_LIQ(data_payslip)

    def _CES(self, data_payslip):
        with self._teacher_wage_context(data_payslip):
            return super()._CES(data_payslip)

    def _ICES(self, data_payslip):
        with self._teacher_wage_context(data_payslip):
            return super()._ICES(data_payslip)

    def _CESLY(self, data_payslip):
        with self._teacher_wage_context(data_payslip):
            return super()._CESLY(data_payslip)

    def _ICESLY(self, data_payslip):
        with self._teacher_wage_context(data_payslip):
            return super()._ICESLY(data_payslip)

    def _CES_LIQ(self, data_payslip):
        with self._teacher_wage_context(data_payslip):
            return super()._CES_LIQ(data_payslip)

    def _ICES_LIQ(self, data_payslip):
        with self._teacher_wage_context(data_payslip):
            return super()._ICES_LIQ(data_payslip)

    def _CES_PART(self, data_payslip):
        with self._teacher_wage_context(data_payslip):
            return super()._CES_PART(data_payslip)

    def _ICES_PART(self, data_payslip):
        with self._teacher_wage_context(data_payslip):
            return super()._ICES_PART(data_payslip)

    def _VAC_LIQ(self, data_payslip):
        with self._teacher_wage_context(data_payslip):
            return super()._VAC_LIQ(data_payslip)

    def _get_total_concept_categories(self, cr, total_previous, period,
                                      contract, exclude=False,
                                      categories=False):
        """Descuenta las horas del profesor de los devengos de las nóminas
        pagadas cuando se liquida la provisión administrativa del mixto."""
        res = super()._get_total_concept_categories(
            cr, total_previous, period, contract, exclude=exclude,
            categories=categories)
        if not self.env.context.get('exclude_teacher_hours'):
            return res

        query = '''
        SELECT HPL.category, sum(HPL.total)
        FROM hr_payslip_line AS HPL
        INNER JOIN hr_payslip AS HP
            ON HP.id = HPL.payslip_id
        INNER JOIN hr_period AS PP
            ON PP.id = HP.period_id
        INNER JOIN hr_novelty AS HN
            ON HN.id = HPL.novelty_id
        WHERE
            HP.state = 'paid' AND
            HN.is_teacher_hours AND
            HPL.category IN %(categories)s AND
            PP.end >= %(start)s AND
            PP.start <= %(end)s AND
            HP.contract_id = %(contract)s
            AND HPL.total IS NOT NULL
        GROUP BY HPL.category
        '''
        param = {
            'categories': categories or DEFAULT_CATEGORIES,
            'contract': contract,
            'start': period.start if type(period) != dict else period['start'],
            'end': period.end if type(period) != dict else period['end'],
        }
        for category, amount in orm._fetchall(cr, query, param):
            total_previous[category] = total_previous.get(category, 0) - amount
        return res

    # ------------------------------------------------------------------
    # Provisiones de la fracción de profesor
    # ------------------------------------------------------------------
    def _compute_teacher_provision(self, data_payslip):
        """Provisión sobre el valor de las horas del mes.

        Los porcentajes de profesor se configuran en Ajustes y se aplican tal
        cual, sin reescalar por la base de días del subtipo: el cliente los
        define ya ajustados a su política de 330 días. Los intereses de
        cesantías, igual que en las provisiones simples de los
        administrativos, son un porcentaje de la provisión de cesantías.
        """
        if not self.apply_teacher_provisions(data_payslip):
            return

        politics = data_payslip['politics']
        rate = politics.get(TEACHER_RATE_PARAM[self.code], 0.0) / 100
        if not rate:
            return

        hours_amount = self.get_teacher_hours_amount(data_payslip)
        if not hours_amount:
            return

        base = hours_amount
        if self.code == 'PRV_ICES_PROF':
            severance_rate = politics.get(
                TEACHER_RATE_PARAM['PRV_CES_PROF'], 0.0) / 100
            base = hours_amount * severance_rate
            if not base:
                return

        logs = self._initialize_logs(data_payslip)

        payment_period = {
            'start': data_payslip['period'].end.replace(day=1),
            'end': data_payslip['period'].end,
        }
        total_previous = {}
        self._get_total_concepts(
            data_payslip['cr'], total_previous, payment_period,
            data_payslip['contract'].id, (self.code,))
        already_provisioned = total_previous.get(self.code, 0)

        total = (base * rate) - already_provisioned

        logs['ibd'] = hours_amount
        logs['rate'] = rate * 100
        logs['total_base'] = base
        logs['days_base'] = data_payslip['contract'].benefits_days_base
        logs['total'] = total

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': base,
            'qty': 1,
            'rate': rate * 100,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
            'log_ids': logs,
        }

    def _PRV_CES_PROF(self, data_payslip):
        return self._compute_teacher_provision(data_payslip)

    def _PRV_ICES_PROF(self, data_payslip):
        return self._compute_teacher_provision(data_payslip)

    def _PRV_PRIMA_PROF(self, data_payslip):
        return self._compute_teacher_provision(data_payslip)

    def _PRV_VAC_PROF(self, data_payslip):
        return self._compute_teacher_provision(data_payslip)
