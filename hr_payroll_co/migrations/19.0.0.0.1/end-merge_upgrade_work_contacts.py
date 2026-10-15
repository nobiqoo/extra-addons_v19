# -*- coding: utf-8 -*-
"""Fusiona los contactos de trabajo que crea el upgrade 16 -> 19.

Al eliminar ``hr.employee.address_home_id`` (paso 17.0), el upgrade crea un
contacto nuevo por empleado con el nombre y el correo corporativo, lo deja en
``work_contact_id`` y le mueve la cuenta bancaria de nomina por SQL. El contacto
original -- el que ``hr_payroll_co`` guarda en su propia columna ``partner_id``,
con la cedula, el historial contable y la direccion personal -- queda suelto, y
el usuario ve dos contactos por empleado.

Aqui se fusiona el nuevo hacia el viejo con el wizard estandar, que reapunta
todas las claves foraneas (cuenta bancaria incluida) y borra el nuevo. El par no
necesita ningun dato de la base 16: viejo = ``partner_id``, nuevo =
``work_contact_id``.

Corre en la etapa ``end`` a proposito: para entonces todos los modulos estan
actualizados y el registro esta completo, que es lo que necesita ``_merge`` para
reapuntar tambien los campos ``reference``.

Se puede desactivar creando el parametro de sistema
``hr_payroll_co.skip_work_contact_merge`` antes de lanzar el upgrade.
"""
import logging

from odoo import api, SUPERUSER_ID
from odoo.tools.parse_version import parse_version

_logger = logging.getLogger(__name__)

SKIP_PARAM = 'hr_payroll_co.skip_work_contact_merge'

# El duplicado solo nace al cruzar la 17.0, que es donde desaparece
# address_home_id y aparece work_contact_id. Viniendo de la 17 o la 18 los
# work_contact_id ya existian y son datos legitimos: no se tocan.
FIRST_SERIE_WITH_WORK_CONTACT = '17.0'

# Candidatos: empleados cuyo contacto de trabajo no es el contacto de
# hr_payroll_co. Se excluyen los ligados a un usuario (ese partner es anterior
# al upgrade y el wizard tampoco deja fusionarlo) y los archivados se incluyen
# adrede: los ex-empleados tienen el mismo duplicado.
CANDIDATES_SQL = """
    SELECT e.id, e.partner_id, e.work_contact_id,
           p.create_uid, p.vat, p.parent_id, p.name
      FROM hr_employee e
      JOIN res_partner p ON p.id = e.work_contact_id
     WHERE e.partner_id IS NOT NULL
       AND e.work_contact_id IS NOT NULL
       AND e.work_contact_id <> e.partner_id
       AND NOT EXISTS (SELECT 1 FROM res_users u WHERE u.partner_id = p.id)
     ORDER BY e.id
"""


def migrate(cr, version):
    if not version:
        return
    if parse_version(version) >= parse_version(FIRST_SERIE_WITH_WORK_CONTACT):
        _logger.info(
            "hr_payroll_co: version instalada %s, no se cruza el 17.0; "
            "no hay contactos de trabajo del upgrade que fusionar", version)
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    if env['ir.config_parameter'].sudo().get_param(SKIP_PARAM):
        _logger.warning(
            "hr_payroll_co: %s activo, se omite la fusion de contactos de "
            "trabajo del upgrade", SKIP_PARAM)
        return

    cr.execute(CANDIDATES_SQL)
    rows = cr.fetchall()
    if not rows:
        _logger.info("hr_payroll_co: sin contactos de trabajo duplicados que fusionar")
        return
    _logger.info("hr_payroll_co: %s empleados con contacto de trabajo distinto "
                 "del contacto de nomina", len(rows))

    Employee = env['hr.employee'].with_context(active_test=False).sudo()
    Partner = env['res.partner'].with_context(active_test=False).sudo()
    Wizard = env['base.partner.merge.automatic.wizard'].sudo()

    merged = skipped = errors = realigned = 0
    for emp_id, old_id, new_id, create_uid, vat, parent_id, name in rows:
        # Firma del contacto que crea el upgrade: lo escribe __system__ y nace
        # sin cedula y sin padre. Cualquier otra cosa es un contacto de trabajo
        # puesto a mano y no se toca.
        if create_uid != SUPERUSER_ID or vat or parent_id:
            skipped += 1
            _logger.info(
                "hr_payroll_co: empleado %s -- el contacto de trabajo %s (%s) no "
                "parece creado por el upgrade (create_uid=%s, vat=%s, parent_id=%s), "
                "se deja como esta", emp_id, new_id, name, create_uid, vat, parent_id)
            continue

        employee = Employee.browse(emp_id)
        old = Partner.browse(old_id).exists()
        new = Partner.browse(new_id).exists()
        if not employee or not old or not new:
            skipped += 1
            continue

        # El estado del empleado manda: hr_payroll_co relaciona
        # hr_employee.active con partner_id.active, asi que el contacto que
        # sobrevive tiene que quedar como estaba el empleado o se desarchivan
        # ex-empleados.
        employee_active = employee.active
        work_email = employee.work_email
        work_phone = employee.work_phone
        try:
            with cr.savepoint():
                Wizard._merge([new.id, old.id], dst_partner=old)
                if old.active != employee_active:
                    old.active = employee_active
                    realigned += 1
                # El inverse de work_email/work_phone no dispara con la fusion
                # (va por SQL), asi que se reescriben para que queden en el
                # contacto sobreviviente.
                vals = {}
                if work_email:
                    vals['work_email'] = work_email
                if work_phone:
                    vals['work_phone'] = work_phone
                if vals:
                    employee.write(vals)
            merged += 1
        except Exception as error:
            env.invalidate_all()
            errors += 1
            _logger.warning(
                "hr_payroll_co: no se pudo fusionar el contacto de trabajo %s "
                "en %s (empleado %s): %s", new_id, old_id, emp_id, error)

    _logger.info(
        "hr_payroll_co: fusion de contactos de trabajo del upgrade -- "
        "%s fusionados | %s omitidos | %s con error | %s contactos realineados "
        "al estado del empleado", merged, skipped, errors, realigned)

    cr.execute("""
        SELECT count(*) FROM hr_employee e
         WHERE e.bank_account_id IS NOT NULL
           AND e.work_contact_id IS NOT NULL
           AND NOT EXISTS (SELECT 1 FROM res_partner_bank b
                            WHERE b.id = e.bank_account_id
                              AND b.partner_id = e.work_contact_id)
    """)
    orphan_accounts = cr.fetchone()[0]
    if orphan_accounts:
        _logger.warning(
            "hr_payroll_co: %s empleados quedan con la cuenta bancaria en un "
            "contacto distinto del de trabajo, revisar antes de la primera nomina",
            orphan_accounts)
