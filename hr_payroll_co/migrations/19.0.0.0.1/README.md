# Fusión de contactos duplicados del upgrade 16 → 19

Al eliminar `hr.employee.address_home_id` (paso 17.0), el upgrade crea un contacto
de trabajo nuevo por empleado y le mueve la cuenta bancaria de nómina por SQL. El
contacto original —el de `hr_payroll_co.partner_id`, con la cédula, la dirección
personal y el historial contable— queda suelto y el usuario ve **dos contactos por
empleado** (en IPM: 466 contactos creados, 326 de empleados, 314 cuentas movidas).

`end-merge_upgrade_work_contacts.py` los fusiona **nuevo → viejo** con el wizard
estándar `base.partner.merge.automatic.wizard._merge`, que reapunta todas las FKs
(cuenta bancaria incluida) y borra el nuevo. Al terminar,
`work_contact_id == partner_id` para cada empleado.

## Por qué está así

- **Etapa `end-`**, no `post-`: corre cuando todos los módulos ya se actualizaron y
  el registro está completo, que es lo que `_merge` necesita para reapuntar también
  los campos `reference`.
- **Carpeta `19.0.0.0.1`** = la versión del manifiesto: viniendo de `16.0.x` el
  script califica sin tener que subir la versión del módulo. Si algún día se sube,
  hay que renombrar la carpeta o el script deja de correr.
- **Sin `commit()`**: cada par va en un savepoint, y si uno falla se registra y se
  sigue. El upgrade conserva su atomicidad.
- **No usa datos de la base 16**: el par sale de la propia base migrada
  (`partner_id` = viejo, `work_contact_id` = nuevo), porque `partner_id` es columna
  propia de `hr_payroll_co` y sobrevive al upgrade.

## Qué NO toca

- Bases que vengan de la 17 o la 18: ahí `work_contact_id` ya existía y es un dato
  legítimo.
- Contactos de trabajo que no lleven la firma del upgrade (`create_uid = 1`, sin
  cédula, sin padre) o que estén ligados a un usuario: se registran en el log y se
  dejan como están.

## Cómo desactivarlo

Crear el parámetro de sistema `hr_payroll_co.skip_work_contact_merge` (cualquier
valor) **antes** de lanzar el upgrade.

## Validado

Sobre una copia de `safra_07` (Odoo 19 con `hr_payroll_co`), simulando lo que hace
el upgrade: 4 empleados activos fusionados conservando cédula, `work_email` y
cuenta bancaria; contacto de trabajo legítimo intacto; guard de la 18 y segunda
pasada sin efecto; y el caso del ex-empleado, donde la fusión desarchivaba el
contacto (pasó en IPM con 6) y el script lo devuelve al estado del empleado.
