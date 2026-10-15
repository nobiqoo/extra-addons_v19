# Migración Gallium 17 → Geoflora 19

Se portaron `gallium/hr_zk_attendance` y `gallium/hr_payroll_co_biometric`
a `develop_geoflora`, versión `19.0.1.0.0`. Este cambio migra código;
no copia empleados, dispositivos, marcaciones ni históricos de la base de Gallium.

## Cambios

- Vistas `list`, acciones y sublistas compatibles con Odoo 19.
- Grupos mediante `res.groups.privilege`, `user_ids` y `group_ids` en acciones.
- Crons sin `numbercall` ni `doall`, retirados del framework.
- Restricciones de unicidad con `models.Constraint`, conservando los nombres SQL.
  Referencia: https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html
- Adaptación de la vista del empleado a la estructura de Odoo 19.
- Dependencia explícita de `web_gantt` (Enterprise), ya usado por la vista original.
  Se retiró `progress="state"`: un estado textual no es un porcentaje de avance.
- Se conserva `hr.contract`: Geoflora lo define en su propia nómina colombiana.
- `hr_payroll_co` declara `account_voucher`, que provee el modelo `account.loans`
  utilizado por sus préstamos. Sin esta dependencia falla una instalación limpia.
- Se agregaron `pyzk`, `openpyxl` y `xlsxwriter` a `requirements.txt`.

## Instalación

Instalar los requisitos Python del repositorio y configurar el `addons_path`
con Odoo 19, Enterprise 19 y `develop_geoflora`. Instalar
`hr_payroll_co_biometric`; el conector biométrico se instala como dependencia.

Configurar dispositivos, zona horaria, identificadores biométricos y permisos.
La conexión física requiere acceso de red a los dispositivos.
Los tipos de horas extra HED, HEN, RN y HEDF deben existir en Nómina CO para
que el hook cree sus reglas. Si se crean después de instalar, configurar las
reglas desde Control de Turnos → Configuración → Reglas de Horas Extras.
Se conservaron los parámetros de cálculo del origen; revisar la configuración
propia de Geoflora antes de aplicar novedades a nómina.

## Verificación

La verificación ampliada está en [TEST_REPORT_19.md](TEST_REPORT_19.md):
62 pruebas, con tres fallos de permisos pendientes. Lo siguiente describe
únicamente la primera batería de migración.

Instalación y pruebas en una base local aislada con Odoo 19 y las dependencias
reales de `develop_geoflora`. Tres pruebas de regresión:

1. Importación repetida de marcaciones sin duplicados, normalización del ID y
   rechazo de hashes duplicados por PostgreSQL.
2. Turno nocturno de 22:00 a 06:00 en Bogotá, conversión a UTC, lectura de sus
   marcaciones y reprocesamiento sin duplicar registros de asistencia.
3. Rechazo de horarios repetidos para el mismo día de un turno por PostgreSQL.

Ejemplo de ejecución sobre una base de pruebas:

```bash
python odoo/odoo-bin -c CONFIG_PRUEBAS -d BASE_PRUEBAS \
  --addons-path=odoo/addons,enterprise,develop_geoflora \
  -i hr_payroll_co_biometric --without-demo \
  --test-enable --test-tags=/hr_payroll_co_biometric \
  --stop-after-init --no-http --max-cron-threads=0
```

Las pruebas no conectan dispositivos físicos ni ejecutan una liquidación real.
La nómina existente emite advertencias por registros iniciales sin
`hr.employee.partner_id` y campos de `hr.contract.type` sin completar, además
de APIs antiguas en dependencias. No impidieron instalar ni ejecutar las pruebas;
no constituyen una validación completa de la nómina de Geoflora.
