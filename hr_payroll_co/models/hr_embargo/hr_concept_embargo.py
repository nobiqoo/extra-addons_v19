# -*- coding: utf-8 -*-
from odoo import models
from odoo.tools import float_round

GROSS_EARNINGS_CATEGORIES = (
    'earnings', 'o_salarial_earnings', 'comp_earnings', 'o_rights', 'o_earnings',
    'non_taxed_earnings',
)

# Combined ceilings for SIMULTANEOUS garnishments on the same contract, per the
# commonly-cited Colombian labor code (CST) framework: alimony garnishments
# (cuota alimentaria) have absolute precedence and together cannot exceed 50%
# of total earnings; every other type (ordinary, coercive, cooperative,
# judicial, other) shares a single ceiling of a fifth of whatever exceeds one
# SMMLV. This is a simplification (the two ceilings are treated as independent
# pools) and is NOT a substitute for legal advice — validate with
# payroll/legal counsel before relying on this in production, since the exact
# treatment (base used, interaction between both ceilings) is a matter of
# legal interpretation.
ALIMONY_CEILING_RATE = 0.5
NON_ALIMONY_CEILING_DIVISOR = 5
FIFTH_RATE = 100.0 / NON_ALIMONY_CEILING_DIVISOR

# Deductions subtracted from the base when a garnishment is applied after
# social security ('after_ss'): health, pension (any of its variants), the
# solidarity and subsistence pension funds, and withholding tax (also the one
# on the service bonus). All of them are computed before DED_EMBARGO (see
# CONCEPTS in hr_concept_base.py).
AFTER_SS_DEDUCTION_CODES = (
    'DED_PENS', 'DED_PENS_PUBLIC', 'DED_PENS_ACCAI', 'DED_EPS', 'FOND_SOL', 'FOND_SUB',
    'RTEFTE', 'RTF_PRIMA',
)

# Social benefits are part of the base according to the garnishment's
# "Applies to" checks, not to its base categories: severance (cesantías) and
# its interest are non-taxed earnings, a category that is never part of the
# base, while prima and compensated vacation are "other rights", which usually
# is. When the garnishment applies to a benefit its concepts are added to the
# base whatever their category, and when it does not they are left out.
BENEFIT_CONCEPT_CODES = {
    'applies_severance': ('CES', 'CES_LIQ', 'CES_PART', 'CESLY'),
    'applies_severance_interest': ('ICES', 'ICES_LIQ', 'ICES_PART', 'ICESLY'),
    'applies_prima': ('PRIMA', 'PRIMA_LIQ'),
    'applies_vacation': ('VAC_LIQ',),
}


class HrConcept(models.Model):
    _inherit = 'hr.concept'

    def _get_active_embargos(self, data_payslip):
        period = data_payslip['period']
        category = data_payslip['payslip_type_id'].category
        embargos = self.env['hr.embargo'].search([
            ('contract_id', '=', data_payslip['contract'].id),
            ('state', '=', 'validated'),
            ('date_start', '<=', period.end),
            '|', ('date_end', '=', False), ('date_end', '>=', period.start),
        ])
        embargos = embargos.filtered(lambda e: e.applies_to_payslip_type(category))
        return embargos.sorted(key=lambda e: e.get_effective_priority())

    def _get_month_previous_data(self, data_payslip):
        """What the paid payroll payslips of the same calendar month already
        contributed (i.e. the first fortnight, when computing the second one).

        On the second fortnight every garnishment is recomputed over the income
        of the WHOLE month (Q1 + Q2) and only the difference against what Q1
        already discounted is taken (monthly adjustment). For monthly payrolls,
        the first fortnight or any other payslip type (prima, vacation,
        settlement...) this is empty, so the computation only sees the current
        payslip, as before.
        """
        previous = data_payslip.get('_embargo_month_previous')
        if previous is not None:
            return previous
        previous = {
            'payslips': self.env['hr.payslip'],
            'categories': {},
            'concept_ids': {},
        }
        period = data_payslip['period']
        if (data_payslip['payslip_type_id'].category == 'NOM'
                and period.type_period == 'BIWEEKLY'
                and period.type_biweekly == 'SECOND'):
            payslips = self.env['hr.payslip'].search([
                ('id', '!=', data_payslip['payslip_id']),
                ('contract_id', '=', data_payslip['contract'].id),
                ('state', '=', 'paid'),
                ('payslip_type_id.category', '=', 'NOM'),
                ('period_id.start', '>=', period.start.replace(day=1)),
                ('period_id.end', '<', period.start),
            ])
            previous['payslips'] = payslips
            for line in payslips.payslip_line_ids:
                categories = previous['categories']
                categories[line.category] = categories.get(line.category, 0.0) + line.total
                if line.concept_id:
                    concept_ids = previous['concept_ids']
                    concept_ids[line.concept_id.id] = (
                        concept_ids.get(line.concept_id.id, 0.0) + line.total)
        data_payslip['_embargo_month_previous'] = previous
        return previous

    def _get_category_total(self, data_payslip, category):
        """Current payslip + previous paid payslips of the month (see
        _get_month_previous_data)."""
        previous = self._get_month_previous_data(data_payslip)['categories']
        return data_payslip.get(category, 0) + previous.get(category, 0)

    def _get_concepts_total(self, data_payslip, concepts):
        """Sum what the given hr.concept records already contributed to this
        payslip run (plus the previous paid payslips of the month, on the
        second fortnight).

        Reads the in-progress payslip lines (data_payslip['payslip_line_concept'])
        instead of data_payslip[code]: some concepts store something other than
        a plain float under their own code (e.g. BASICO stores a (wage, days)
        tuple), so that shortcut isn't safe for an arbitrary user-picked concept.
        """
        concept_ids = set(concepts.ids)
        if not concept_ids:
            return 0.0
        previous = self._get_month_previous_data(data_payslip)['concept_ids']
        current = sum(
            line.get('total', 0)
            for line in data_payslip.get('payslip_line_concept', [])
            if line.get('concept_id') in concept_ids
        )
        return current + sum(previous.get(concept_id, 0.0) for concept_id in concept_ids)

    def _get_embargo_raw_base(self, data_payslip, embargo):
        """Base before any social-security/exclusion subtraction (RN02)."""
        base = sum(
            self._get_category_total(data_payslip, category.code)
            for category in embargo.base_category_ids)
        # Social benefits follow the "Applies to" checks (see BENEFIT_CONCEPT_CODES):
        # take out the ones the base categories brought in, add the applicable ones.
        base_category_codes = embargo.base_category_ids.mapped('code')
        for flag, codes in BENEFIT_CONCEPT_CODES.items():
            concepts = self.env['hr.concept'].sudo().search([('code', 'in', codes)])
            base -= self._get_concepts_total(
                data_payslip, concepts.filtered(lambda c: c.category in base_category_codes))
            if embargo[flag]:
                base += self._get_concepts_total(data_payslip, concepts)
        return base

    def _get_embargo_base(self, data_payslip, embargo):
        base = self._get_embargo_raw_base(data_payslip, embargo)
        if embargo.ss_treatment == 'after_ss':
            after_ss_deductions = self.env['hr.concept'].sudo().search([
                ('code', 'in', AFTER_SS_DEDUCTION_CODES)])
            base -= self._get_concepts_total(data_payslip, after_ss_deductions)
        elif embargo.ss_treatment == 'custom':
            base -= self._get_concepts_total(data_payslip, embargo.ss_deduction_concept_ids)
        base -= self._get_concepts_total(data_payslip, embargo.excluded_concept_ids)
        return max(base, 0.0)

    def _get_month_paid_lines(self, data_payslip):
        """Garnishment installments already paid by the previous payslips of the
        month (empty unless computing a second fortnight)."""
        payslips = self._get_month_previous_data(data_payslip)['payslips']
        if not payslips:
            return self.env['hr.embargo.line']
        return self.env['hr.embargo.line'].search([
            ('payslip_id', 'in', payslips.ids),
            ('state', '=', 'paid'),
        ])

    def _compute_embargo_amount(self, data_payslip, embargo):
        """Amount this garnishment would take on its own, respecting only its
        own formula and its own pending balance — the combined
        ceiling across simultaneous garnishments (RN08) is applied afterwards,
        in _compute_all_embargo_lines, once every active garnishment's own
        amount is known.

        Returns (base, rate, amount): the base and rate are the ones shown on
        the payslip line, i.e. the value the discount was actually taken from
        (the garnishable base for a percentage, the excess over the minimum
        wage for the "fifth" types, the installment itself for a fixed
        installment) and the rate applied to it (0 for a fixed installment).

        On the second fortnight the formula runs over the whole month's base
        and the amount already discounted by the first fortnight is subtracted
        (monthly adjustment, discounted through the same concept). A fixed
        installment is a per-period value, so it is never adjusted.
        """
        embargo_type = embargo.embargo_type_id
        base = self._get_embargo_base(data_payslip, embargo)
        smmlv = data_payslip['economic_variables']['SMMLV'][data_payslip['current_year_month']]

        if embargo_type.calculation_type == 'fixed_quota':
            base = embargo.fixed_quota_value
            rate = 0.0
            amount = embargo.fixed_quota_value
        elif embargo_type.calculation_type == 'percentage':
            rate = embargo.percentage_value
            amount = base * embargo.percentage_value / 100
        elif embargo_type.calculation_type in (
                'fifth_over_minimum_with_deductions', 'fifth_over_minimum_without_deductions'):
            if embargo_type.calculation_type == 'fifth_over_minimum_without_deductions':
                base = self._get_embargo_raw_base(data_payslip, embargo)
            # The fifth is taken from the excess over the minimum wage, so that
            # excess is the base shown.
            base = max(base - smmlv, 0.0)
            rate = FIFTH_RATE
            amount = base / NON_ALIMONY_CEILING_DIVISOR
        else:
            rate = 0.0
            amount = 0.0

        if embargo_type.calculation_type != 'fixed_quota':
            month_paid = sum(self._get_month_paid_lines(data_payslip).filtered(
                lambda l: l.embargo_id == embargo).mapped('amount'))
            amount -= month_paid

        # Never collect more than what is still owed — but only when a total debt was
        # actually set: some garnishments have no known total and are only bounded by
        # date_end, in which case pending_balance (0 - paid) is meaningless (RN07/RN09).
        if embargo.amount:
            amount = min(amount, embargo.pending_balance)
        return round(base, 2), rate, max(amount, 0.0)

    def _get_gross_earnings(self, data_payslip):
        return sum(
            self._get_category_total(data_payslip, code) for code in GROSS_EARNINGS_CATEGORIES)

    def _get_shared_ceiling(self, data_payslip, is_alimony):
        """Room left under the combined ceiling of the group. On the second
        fortnight the ceiling is computed over the whole month's earnings and
        what the group already discounted in the first fortnight is subtracted.
        """
        gross = self._get_gross_earnings(data_payslip)
        if is_alimony:
            ceiling = gross * ALIMONY_CEILING_RATE
        else:
            smmlv = data_payslip['economic_variables']['SMMLV'][
                data_payslip['current_year_month']]
            ceiling = max(gross - smmlv, 0.0) / NON_ALIMONY_CEILING_DIVISOR
        month_paid = sum(self._get_month_paid_lines(data_payslip).filtered(
            lambda l: not l.embargo_id.skip_legal_ceiling
            and (l.embargo_id.embargo_type_id.legal_type == 'alimony') == is_alimony
        ).mapped('amount'))
        return max(ceiling - month_paid, 0.0)

    def _allocate_within_ceiling(self, embargos, desired, ceiling):
        """Fund garnishments in (already priority-sorted) order up to a shared
        ceiling. Once the ceiling is exhausted, lower-priority garnishments in
        the same group get nothing this period — their pending balance simply
        carries over to the next one (RN08).
        """
        allocated = {}
        remaining = ceiling
        for embargo in embargos:
            base, rate, amount = desired[embargo.id]
            funded = min(amount, remaining) if remaining > 0 else 0.0
            allocated[embargo.id] = (base, rate, funded)
            remaining -= funded
        return allocated

    def _get_net_pay_before_embargos(self, data_payslip):
        """Net pay of the payslip before any garnishment, computed the same way
        as NETO / NETO_LIQ (garnishments run right before them)."""
        net = sum(round(data_payslip.get(category, 0)) for category in GROSS_EARNINGS_CATEGORIES)
        net -= round(data_payslip.get('deductions', 0))
        net -= round(data_payslip.get('CES', 0))
        return net

    def _apply_settlement_debt(self, data_payslip, embargos, allocated):
        """Final settlement: the employee leaves the company, so every garnishment
        with a total debt also takes, on top of its own installment, whatever net
        pay is left after all the installments, up to its pending balance (in
        priority order). When the pending balance is bigger than the net pay, the
        settlement ends up paying 0.
        """
        if data_payslip['payslip_type_id'].category != 'LIQ':
            return
        net = self._get_net_pay_before_embargos(data_payslip)
        net -= sum(total for _base, _rate, total in allocated.values())
        for embargo in embargos.filtered('amount'):
            if net <= 0:
                break
            base, rate, total = allocated[embargo.id]
            extra = min(max(embargo.pending_balance - total, 0.0), net)
            allocated[embargo.id] = (base, rate, total + extra)
            net -= extra

    def _build_payslip_line_for_embargo(self, data_payslip, embargo, concept, base, rate, total):
        # 'value' is the base the discount was taken from and 'rate' the rate
        # applied to it (see _compute_embargo_amount). The total does not always
        # reconcile as value * rate: caps, the combined legal ceiling, the
        # monthly adjustment of the second fortnight...
        return {
            # Show the garnishment type, not this installment's own consecutive/name.
            'name': embargo.embargo_type_id.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': concept.category,
            'value': base,
            'qty': 1,
            'rate': rate,
            'total': total,
            'origin': 'local',
            'concept_id': concept.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
            'embargo_id': embargo.id,
        }

    def _compute_all_embargo_lines(self, data_payslip):
        """Compute every active garnishment of the contract at once (required so the
        combined ceilings — RN08 — are respected across ALL of them together, regardless
        of which hr.embargo.type/concept each belongs to), then group the resulting
        payslip lines by the concept configured on each garnishment's type.

        Garnishments flagged to ignore the legal ceiling (e.g. an executive
        garnishment ordered as a plain percentage of the salary) take exactly their
        own amount and do not consume the shared ceiling of the others.

        Recomputing a draft payslip must not accumulate duplicate installment
        records; only paid installments are kept (mirrors how hr.payslip.line
        itself is cleared and rebuilt on every compute_slip() run).
        """
        self.env['hr.embargo.line'].sudo().search([
            ('payslip_id', '=', data_payslip['payslip_id']),
            ('state', '!=', 'paid'),
        ]).unlink()

        embargos = self._get_active_embargos(data_payslip)
        desired = {embargo.id: self._compute_embargo_amount(data_payslip, embargo)
                   for embargo in embargos}

        uncapped = embargos.filtered(lambda e: e.skip_legal_ceiling)
        alimony = embargos.filtered(
            lambda e: e.embargo_type_id.legal_type == 'alimony') - uncapped
        others = embargos - alimony - uncapped

        allocated = {embargo.id: desired[embargo.id] for embargo in uncapped}
        allocated.update(self._allocate_within_ceiling(
            alimony, desired, self._get_shared_ceiling(data_payslip, True)))
        allocated.update(self._allocate_within_ceiling(
            others, desired, self._get_shared_ceiling(data_payslip, False)))
        # Round half up (like a spreadsheet) here: the payroll engine's round()
        # goes half to even (2.185.416,5 -> 2.185.416), and the installment must
        # store the same amount the payslip line shows.
        allocated = {
            embargo_id: (
                base, rate, float_round(total, precision_digits=0, rounding_method='HALF-UP'))
            for embargo_id, (base, rate, total) in allocated.items()}
        self._apply_settlement_debt(data_payslip, embargos, allocated)

        lines_by_concept = {}
        for embargo in embargos:
            base, rate, total = allocated[embargo.id]
            if total <= 0:
                continue
            self.env['hr.embargo.line'].sudo().create({
                'embargo_id': embargo.id,
                'payslip_id': data_payslip['payslip_id'],
                'period_id': data_payslip['period'].id,
                'state': 'validated',
                'base_amount': base,
                'amount': total,
            })
            concept = embargo.embargo_type_id.concept_id
            lines_by_concept.setdefault(concept.id, []).append(
                self._build_payslip_line_for_embargo(
                    data_payslip, embargo, concept, base, rate, total))
        return lines_by_concept

    def _compute_embargo_deduction(self, data_payslip):
        """Entry point invoked by the payroll engine for any hr.concept linked from at
        least one hr.embargo.type (see HrConcept.is_embargo_type_concept). Several such
        concepts can appear in the same payslip run (one per garnishment type, or shared
        across a few) — the actual computation only runs once per payslip (cached in
        data_payslip), and each call just returns its own slice of the result.
        """
        cache = data_payslip.get('_embargo_lines_by_concept')
        if cache is None:
            cache = data_payslip['_embargo_lines_by_concept'] = (
                self._compute_all_embargo_lines(data_payslip))
        return cache.get(self.id, [])
