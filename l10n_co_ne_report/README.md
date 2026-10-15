# l10n_co_ne_report — Informe Previo Nómina Electrónica (Colombia)

Módulo Odoo 19 que genera un reporte Excel con toda la información de Nómina Electrónica (NE) **antes o después** del envío a la DIAN, partiendo directamente de las nóminas liquidadas (`hr.payslip`).

---

## Propósito

El cliente necesita revisar y validar la información antes de enviarla a la DIAN. Este módulo permite generar el informe en cualquier etapa del proceso:

| Momento | Resultado |
|---------|-----------|
| Solo nóminas liquidadas, sin NE creada | Informe completo con columnas NE vacías ("Pendiente / Sin enviar") |
| NE creada pero no enviada (estado `neu`) | Informe completo + número NE provisional |
| NE enviada o aprobada por la DIAN | Informe completo + número NE, CUNE y estado DIAN real |

---

## Instalación

```bash
python3 odoo-bin -d <base_de_datos> -i l10n_co_ne_report --stop-after-init
```

**Dependencias:** `l10n_co_hr_bloodo`, `hr_payroll_co`, `utilities_collection`

---

## Acceso

**Menú:** Nómina → **Informe Previo NE**

---

## Uso

1. Abrir el asistente desde el menú.
2. Seleccionar la **compañía**.
3. Escribir cualquier **fecha dentro del mes** a reportar (ej: `15/03/2026` → toma todo marzo 2026).
4. Opcionalmente filtrar por **Tipo NE** (NIE, NIAE-R, NIAE-E) y **Estado** (Correcto, Enviado, etc.).
5. Si se desea restringir a un procesamiento específico, seleccionar en **Procesamiento(s)** — en ese caso la fecha es ignorada.
6. Hacer clic en **Generar Excel**.

---

## Lógica de filtrado

```
Si se seleccionan Procesamiento(s):
    → nóminas de esos procesamientos (estado done/paid)

Si no:
    → busca todos los hr.period cuyo start cae dentro del mes
    → busca hr.payslip con period_id en esos períodos y state in (done, paid)
    → agrupa por empleado
```

Esto permite que empresas con pago **quincenal** (dos períodos por mes) pero reporte **mensual** a la DIAN vean un único renglón por empleado consolidando ambas quincenas.

---

## Estructura del Excel

El archivo generado tiene **3 filas de encabezado** y una **fila de totales** al final.

### Bloque A–AH (34 columnas) — Empleado / Contrato / NE

| Col | Campo | Fuente |
|-----|-------|--------|
| A | Período (ej: "Marzo 2026") | Calculado |
| B | Inicio liquidación | `hr.payslip._build_period_ne()` |
| C | Fin liquidación | `hr.payslip._build_period_ne()` |
| D | Tipo período DIAN | `hr.period.type_period` → código DIAN |
| E | NIT Empleador | `res.company.partner_id.vat` |
| F | DV Empleador | `res.company.partner_id.l10n_co_verification_code` |
| G | Razón Social | `res.company.name` |
| H | Tipo documento empleado | `res.partner.l10n_latam_identification_type_id.dian_code` |
| I | Número documento | `res.partner.vat` |
| J | Primer Apellido | `res.partner.lastname1` |
| K | Segundo Apellido | `res.partner.lastname2` |
| L | Primer Nombre | `res.partner.name1` |
| M | Otros Nombres | `res.partner.name2` |
| N | Tipo Trabajador | `hr.contract.fiscal_type_id.code` |
| O | Subtipo Trabajador | `hr.contract.fiscal_subtype_id.code` |
| P | Alto Riesgo Pensión | `hr.contract.high_risk` |
| Q | Tipo Contrato | `hr.contract.term` → código DIAN |
| R | Salario Integral | `hr.contract` (true/false) |
| S | Sueldo | `hr.contract.wage` |
| T | Fecha Ingreso | `hr.contract.date_start` |
| U | Fecha Retiro | `hr.contract.settlement_date` (si aplica) |
| V | Inicio Liquidación | Calculado de nóminas del grupo |
| W | Fin Liquidación | Calculado de nóminas del grupo |
| X | **Días Trabajados (days360)** | Calculado (ver sección abajo) |
| Y | País Trabajo | `hr.contract.contract_city_id.country_id.code` |
| Z | Depto. Trabajo | `hr.contract.contract_city_id.state_id.dian_code` |
| AA | Ciudad Trabajo | `hr.contract.contract_city_id.dian_code` |
| AB | Número NE | `edi.hr.document.edi_zahl` (o "Pendiente") |
| AC | CUNE | `edi.hr.document.edi_cune` |
| AD | Estado DIAN | `edi.hr.document.hr_edi_state` (o "Sin enviar") |
| AE | Tipo NE | `edi.hr.document.edi_type` |
| AF | Fecha Generación NE | `edi.hr.document.edi_datum` |
| AG | Ambiente | `res.company.hr_target_environment` (Producción/Habilitación) |
| AH | Período Nómina DIAN | Código de período según tabla DIAN |

### Bloque AI en adelante — Devengos DIAN

Contiene todos los conceptos de devengos tal como se calculan para el XML de la DIAN:

- **BAS** — Días trabajados y sueldo trabajado
- **TPT** — Auxilio de transporte
- **VMA** — Viáticos (salarial y no salarial)
- **HED / HEN / HRN** — Horas extra/recargo diurnas, nocturnas (cantidad y valor)
- **HEDDF / HRDDF / HENDF / HRNDF** — Horas extra/recargo en días de descanso (cantidad y valor)
- **VAC / VAP** — Vacaciones comunes y compensadas (días y valor)
- **PRI** — Prima (cantidad en días, salarial, no salarial)
- **CES** — Cesantías (valor, porcentaje, intereses)
- **INC-ENF / INC-ATEP** — Incapacidades por enfermedad y AT/EP (días y valor)
- **LIC-MP / LIC-R / LIC-NR** — Licencias maternidad/paternidad, remuneradas, no remuneradas
- **BON** — Bonificaciones (salarial y no salarial)
- **AUX** — Auxilios (salarial y no salarial)
- **OCP** — Otros conceptos (salarial y no salarial)
- **COMP** — Compensaciones (ordinaria y extraordinaria)
- **BEP / BEA** — Bonos EPCTV pago y alimentación (salarial y no salarial)
- **COM** — Comisiones
- **PTP** — Pagos a terceros (devengos)
- **ANT** — Anticipos (devengos)
- **DOT** — Dotación
- **ASO** — Apoyo de sostenimiento
- **TTR** — Teletrabajo
- **BRT** — Bonificación por retiro
- **IND** — Indemnización
- **REI** — Reintegro (devengos)

### Bloque siguiente — Deducciones DIAN

- **EPS** — Salud (porcentaje y valor)
- **PEN** — Pensión (porcentaje y valor)
- **FSL** — Fondo de Solidaridad Pensional (porcentaje y valor)
- **FSB** — Fondo de Subsistencia (porcentaje y valor)
- **SPU / SPV** — Sanciones pública y privada
- **LIB** — Libranzas
- **PTR** — Pagos a terceros (deducciones)
- **ADV** — Anticipos (deducciones)
- **ODD** — Otras deducciones
- **PVL** — Pensión voluntaria
- **RFT** — Retención en la fuente
- **AFC** — AFC
- **COO** — Cooperativa
- **EMB** — Embargo fiscal
- **CPN** — Plan complementarios
- **EDU** — Educación
- **RIN** — Reintegro (deducciones)
- **DEU** — Deuda

### Columnas finales — Totales

| Col | Campo |
|-----|-------|
| Penúltima-2 | **Total Devengado** |
| Penúltima-1 | **Total Deducciones** |
| Última | **Total Neto** (Devengado − Deducciones) |

---

## Cálculo de días trabajados (days360)

El informe aplica la función `days360` (regla bancaria europea, igual a la que usa la DIAN) con la siguiente lógica:

```
fecha_inicio = max(fecha_inicio_contrato, primer_día_del_mes)
               ├─ Empleado antiguo  → 1 del mes         (ej: 2026-03-01)
               └─ Empleado nuevo    → fecha de ingreso  (ej: 2026-03-15)

fecha_fin    = settlement_date  si cae dentro del mes seleccionado
             = último_día_del_mes  en caso contrario    (ej: 2026-03-31)
               └─ Empleado retirado en el mes → fecha de liquidación

días = days360(fecha_inicio, fecha_fin)
       ├─ Empleado mes completo   → 30
       ├─ Ingresó el 15 de marzo  → ~15
       └─ Liquidado el 20 de marzo → days360(01/03, 20/03) ≈ 19
```

---

## Garantía de consistencia con el XML enviado a la DIAN

El informe **reutiliza exactamente los mismos métodos** `_build_*` de `hr.payslip` que utiliza el módulo `l10n_co_hr_bloodo` al generar el XML para la DIAN:

```python
payslips._build_basic_wage()
payslips._build_sub_trans()
payslips._build_hed_overtimes()
payslips._build_holidays()
payslips._build_prima()
payslips._build_ces()
# ... todos los demás _build_*
```

Esto garantiza que los valores del informe coinciden exactamente con los del XML, sin recálculo independiente.

---

## Archivos del módulo

```
l10n_co_ne_report/
├── __manifest__.py                         Manifest del módulo
├── __init__.py                             Init del paquete
├── README.md                               Esta documentación
├── models/
│   ├── __init__.py
│   └── edi_hr_report_wizard.py             Wizard TransientModel principal
├── security/
│   └── ir.model.access.csv                 Permisos de acceso
└── views/
    └── edi_hr_report_wizard_views.xml      Vista del wizard y menú
```

---

## Modelo principal: `edi.hr.report.wizard`

### Campos del wizard

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `fecha_informe` | Date | Cualquier día del mes a reportar (default: hoy) |
| `company_id` | Many2one | Compañía (default: compañía activa) |
| `edi_processing_ids` | Many2many | Filtrar por procesamientos específicos (opcional) |
| `edi_type` | Selection | Tipo NE: Todos / NIE / NIAE-R / NIAE-E |
| `state_filter` | Selection | Estado: Todos / Nuevo / Enviado / Correcto / Rechazado / Error |

### Métodos principales

| Método | Descripción |
|--------|-------------|
| `action_generate_report()` | Acción principal — orquesta la generación y devuelve URL de descarga |
| `_mes_rango()` | Calcula `(primer_dia, ultimo_dia)` del mes de `fecha_informe` |
| `_get_payslip_groups()` | Obtiene nóminas `paid/done` del mes, agrupadas por empleado, con su `edi.hr.document` si existe |
| `_generate_xlsx(groups)` | Construye el workbook xlsxwriter con formatos y retorna bytes |
| `_build_report_row(payslips, edi_doc)` | Construye el dict de una fila llamando todos los `_build_*` |
