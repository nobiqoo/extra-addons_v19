# -*- coding: utf-8 -*-
"""
Hooks de instalación del módulo hr_payroll_co_biometric.
"""
import logging

_logger = logging.getLogger(__name__)

# Definición de las reglas por defecto para Colombia (Ley 2101/2021).
# Formato: (code, name, apply_on, is_overtime, hour_from, hour_to, sequence, novelty_type)
_DEFAULT_OVERTIME_RULES = [
    ('HED',  'Hora Extra Diurna (HED)',              'normal',         True,  6.0,  19.0, 10, 'extra_day_hours'),
    ('HEN',  'Hora Extra Nocturna (HEN)',             'normal',         True,  19.0,  6.0, 20, 'extra_night_hours'),
    ('RN',   'Recargo Nocturno (RN)',                 'normal',         False, 19.0,  6.0, 25, 'night_surcharge'),
    ('HEDF', 'Hora Extra Festivo / Dominical (HEDF)', 'holiday_sunday', True,  0.0,  24.0, 30, 'compensatory'),
]


def post_init_hook(env):
    """Crea las reglas de categorización de horas extras por defecto si no existen."""
    Rule = env['hr.overtime.rule']
    OTType = env['hr.overtime.type']
    company = env.company

    created = 0
    for code, name, apply_on, is_overtime, hour_from, hour_to, sequence, novelty_type in _DEFAULT_OVERTIME_RULES:
        ot_type = OTType.search([('code', '=', code)], limit=1)
        if not ot_type:
            _logger.warning(
                'hr_payroll_co_biometric: no se encontró hr.overtime.type con código "%s". '
                'Cree el tipo de hora extra en Nómina CO y luego configure la regla manualmente '
                'en Control de Turnos → Configuración → Reglas de Horas Extras.',
                code,
            )
            continue

        existing = Rule.search([
            ('overtime_type_id', '=', ot_type.id),
            ('company_id', '=', company.id),
        ], limit=1)
        if existing:
            # Actualizar novelty_type si aún no está configurado
            if not existing.novelty_type or existing.novelty_type == 'extra_hours' and novelty_type != 'extra_hours':
                existing.novelty_type = novelty_type
                _logger.info(
                    'hr_payroll_co_biometric: regla "%s" actualizada con novelty_type=%s.',
                    existing.name, novelty_type,
                )
            continue

        Rule.create({
            'name': name,
            'overtime_type_id': ot_type.id,
            'novelty_type': novelty_type,
            'apply_on': apply_on,
            'is_overtime': is_overtime,
            'hour_from': hour_from,
            'hour_to': hour_to,
            'sequence': sequence,
            'company_id': company.id,
        })
        created += 1
        _logger.info(
            'hr_payroll_co_biometric: regla creada → %s (compañía: %s)', name, company.name)

    if created:
        _logger.info(
            'hr_payroll_co_biometric: %d regla(s) de horas extras creadas correctamente.', created)
