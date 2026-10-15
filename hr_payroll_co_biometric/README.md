# Gestión de Turnos y Control Biométrico

**Versión:** 19.0.1.0.0  
**Autor:** OdOne S.A.S  
**Licencia:** LGPL-3  

Módulo de gestión integral de turnos laborales, asistencia biométrica y detección automática de novedades, integrado con la nómina colombiana.

---

## Tabla de contenido

1. [Descripción general](#1-descripción-general)
2. [Dependencias](#2-dependencias)
3. [Modelos implementados](#3-modelos-implementados)
4. [Reglas de categorización de horas extras](#4-reglas-de-categorización-de-horas-extras)
5. [Tolerancia de horas extras](#5-tolerancia-de-horas-extras)
6. [Flujo de trabajo](#6-flujo-de-trabajo)
7. [Configuración inicial](#7-configuración-inicial)
8. [Cómo usar el módulo](#8-cómo-usar-el-módulo)
9. [Automatización (Cron)](#9-automatización-cron)
10. [Seguridad y roles](#10-seguridad-y-roles)
11. [Integración con nómina](#11-integración-con-nómina)
12. [Datos precargados](#12-datos-precargados)
13. [Estructura de archivos](#13-estructura-de-archivos)
14. [Historial de cambios](#14-historial-de-cambios)

---

## 1. Descripción general

El módulo conecta tres sistemas:

```
Dispositivos ZKTeco  →  Marcaciones biométricas  →  hr_zk_attendance (daily.attendance)
          ↓
Programaciones de turno  →  Comparación planificado vs. real
          ↓                       ↓
Breakdown horas día/noche    Detección festivos (hr.day.off)
          ↓
Reglas de categorización (hr.overtime.rule)
          ↓
Novedades HED/HEN/HEDF  →  hr_payroll_co (nómina colombiana)
```

Permite:
- Definir **turnos laborales** con horarios, tolerancias y tipos (diurno, nocturno, rotativo, etc.)
- Crear **programaciones** de turno por período, sede o departamento
- **Importar programaciones desde Excel** (wizard con plantilla descargable)
- **Visualizar turnos** en vistas de Calendario y Gantt
- **Comparar** automáticamente las marcaciones biométricas contra el turno programado
- **Detectar y clasificar novedades** con reglas configurables: tardanzas, ausencias, horas extras diurnas/nocturnas, inconsistencias biométricas
- **Calcular el desglose** de horas regulares diurnas/nocturnas y horas extras HED/HEN/HEDF según legislación colombiana
- **Valorar económicamente** las horas extras usando variables económicas por mes/año
- **Aplicar tolerancia** configurable para no pagar H.E. menores a N minutos
- **Aplicar las novedades** al módulo de nómina (`hr.overtime`)
- **Generar reportes consolidados** de horas extras en PDF y Excel

---

## 2. Dependencias

| Módulo | Propósito |
|--------|-----------|
| `hr_payroll_co` | Nómina colombiana propia (OdOne). Provee `hr.overtime`, `hr.overtime.type`, `hr.novelty`, `hr.contract`, `hr.period`, `economic.variable`, `hr.days.off.year`, `hr.day.off` |
| `hr_zk_attendance` | Integración con dispositivos biométricos ZKTeco. Provee `daily.attendance` (vista agregada de marcaciones por empleado/día) |

**Dependencia de sistema (opcional):**
- `openpyxl`: requerido para importación de Excel y exportación de reporte. Instalar con `pip install openpyxl`.

---

## 3. Modelos implementados

### 3.1 `hr.shift` — Turno Laboral

Define la configuración de un tipo de turno.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | Char | Nombre descriptivo del turno |
| `code` | Char(10) | Código único por compañía (ej. `TA`, `TB`, `ADM`) |
| `shift_type` | Selection | Tipo: `day`, `night`, `mixed`, `rotating`, `admin`, `special`, `sunday`, `holiday`, `extended`, `twelve` |
| `hour_from` | Float | Hora de inicio (ej. `6.0` = 06:00) |
| `hour_to` | Float | Hora de fin (ej. `14.0` = 14:00) |
| `crosses_midnight` | Boolean | Calculado: `True` si `hour_to < hour_from` |
| `effective_hours` | Float | Calculado: `(hour_to - hour_from) - rest_time` con manejo de medianoche |
| `rest_time` | Float | Tiempo de descanso a descontar (horas) |
| `tolerance_in` | Integer | Minutos de gracia para llegada tardía |
| `tolerance_out` | Integer | Minutos de gracia para salida anticipada |
| `is_rotating_cycle` | Boolean | Indica si es un turno rotativo con ciclo |
| `cycle_work_days` | Integer | Días de trabajo en el ciclo rotativo |
| `cycle_rest_days` | Integer | Días de descanso en el ciclo rotativo |

**Lógica especial:**
- Un turno que cruza medianoche (ej. `22:00 → 06:00`) se detecta automáticamente cuando `hour_to < hour_from`.
- Las horas efectivas suman 24h automáticamente para turnos que cruzan medianoche.

---

### 3.2 `hr.shift.schedule` — Programación de Turnos

Cabecera de una programación de turnos para un período/sede.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | Char | Referencia de la programación |
| `state` | Selection | `draft` → `confirmed` → `done` / `cancel` |
| `date_start` | Date | Inicio del período |
| `date_end` | Date | Fin del período |
| `address_id` | Many2one | Sede / Lugar de trabajo |
| `department_id` | Many2one | Departamento (opcional, para filtrar) |
| `line_ids` | One2many | Líneas de asignación empleado-turno-fecha |
| `line_count` | Integer | Calculado: total de líneas |

**Estados:**
```
Borrador (draft) → Confirmado (confirmed) → Ejecutado (done)
                                          ↘ Cancelado (cancel)
```

---

### 3.3 `hr.shift.schedule.line` — Línea de Programación

Una asignación concreta: un empleado, un turno, una fecha.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `schedule_id` | Many2one | Cabecera de programación |
| `employee_id` | Many2one | Empleado asignado |
| `shift_id` | Many2one | Turno asignado |
| `work_date` | Date | Fecha de trabajo |
| `planned_start` | Datetime | Hora UTC calculada de inicio del turno |
| `planned_end` | Datetime | Hora UTC calculada de fin del turno |
| `is_sunday` | Boolean | `True` si la fecha es domingo |
| `is_holiday` | Boolean | `True` si existe un registro `hr.day.off` para esa fecha |
| `state` | Selection | `scheduled` / `processed` / `novelty` / `absent` |
| `attendance_record_id` | Many2one | Enlace al registro de asistencia generado |

**Lógica de cálculo de horas (`_compute_planned_times`):**
1. Lee la zona horaria de la compañía del empleado (por defecto `America/Bogota`)
2. Convierte `hour_from`/`hour_to` del turno a `datetime` local
3. Si el turno cruza medianoche, suma un día a la fecha fin
4. Convierte ambos a UTC (sin tzinfo) para almacenamiento en Odoo

**Detección de festivos:** Usa `hr.day.off` (módulo `hr_payroll_co`) por campo `date`.

**Validación:** Un empleado no puede tener dos turnos en la misma fecha en programaciones no canceladas.

**Vistas disponibles:** Lista, Calendario (por `planned_start`/`planned_end`, color por turno) y Gantt (agrupado por empleado).

---

### 3.4 `hr.attendance.record` — Registro de Asistencia

Resultado de comparar el turno programado con la marcación biométrica real.

#### Campos principales

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `employee_id` | Many2one | Empleado |
| `schedule_line_id` | Many2one | Línea de programación de origen |
| `shift_id` | Many2one | Turno programado |
| `work_date` | Date | Fecha |
| `planned_start` / `planned_end` | Datetime | Turno programado (UTC) |
| `actual_check_in` / `actual_check_out` | Datetime | Marcaciones biométricas reales (UTC) |
| `worked_hours` | Float | `actual_check_out - actual_check_in` en horas |
| `planned_hours` | Float | Horas del turno programado |
| `extra_hours` | Float | Horas trabajadas **después del fin del turno** (`actual_check_out - planned_end`) |
| `biometric_punch_count` | Integer | Número total de marcaciones del día |
| `attendance_result` | Selection | Clasificación del resultado |
| `delay_minutes` | Integer | Minutos de llegada tardía |
| `early_out_minutes` | Integer | Minutos de salida anticipada |
| `is_sunday` | Boolean | Domingo |
| `is_holiday` | Boolean | Festivo |
| `correction_state` | Selection | Estado de solicitud de corrección biométrica |

#### Campos de desglose de horas

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `day_hours` | Float | Horas regulares en jornada diurna (06:00–19:00) |
| `night_hours` | Float | Horas regulares en jornada nocturna (19:00–06:00) |
| `extra_day_hours` | Float | H.E. Diurnas (HED) |
| `extra_night_hours` | Float | H.E. Nocturnas (HEN) |
| `holiday_work_hours` | Float | Horas trabajadas en festivo/dominical (HEDF) |

#### Campos de valoración económica

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `hour_base_value` | Float | Valor de la hora diurna base (variable `HD`) |
| `night_surcharge_value` | Float | Valor del recargo nocturno |
| `extra_day_value` | Float | Valor total H.E. Diurnas |
| `extra_night_value` | Float | Valor total H.E. Nocturnas |
| `holiday_extra_value` | Float | Valor total H.E. Festivo/Dominical |
| `total_overtime_value` | Float | Suma total de todos los valores de horas extras |

**Resultados posibles (`attendance_result`):**

| Código | Descripción | Condición |
|--------|-------------|-----------|
| `ok` | Asistencia Correcta | Sin tardanza significativa ni ausencia |
| `late_minor` | Retardo Leve | Tardanza ≤ tolerancia × 3 |
| `late_major` | Retardo Grave | Tardanza > tolerancia × 3 |
| `partial_absence` | Ausencia Parcial | Trabajó < 50% de las horas programadas |
| `total_absence` | Ausencia Total | Sin marcaciones |
| `biometric_issue` | Inconsistencia Biométrica | Solo una marcación (sin entrada o sin salida) |
| `extra_hours` | Horas Adicionales | Trabajó más del 110% de las horas programadas |

> **Nota:** El campo `extra_hours` refleja únicamente el tiempo posterior al fin del turno (`actual_check_out - planned_end`). La llegada anticipada no infla este valor.

---

### 3.5 `hr.attendance.novelty` — Novedad de Asistencia

Novedad detectada automáticamente o registrada manualmente.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | Char | Secuencia automática `NOV/YYYY/NNNNN` |
| `employee_id` | Many2one | Empleado |
| `work_date` | Date | Fecha de la novedad |
| `novelty_type` | Selection | Tipo de novedad (viene de la regla que la generó) |
| `overtime_type_id` | Many2one `hr.overtime.type` | Categoría de H.E. asignada por la regla |
| `state` | Selection | `draft` → `review` → `approved` → `applied` / `rejected` |
| `minutes` | Integer | Minutos (tardanzas, ausencias parciales) |
| `extra_hours` | Float | Horas extras totales |
| `extra_day_qty` | Float | Horas Extras Diurnas (HED) |
| `extra_night_qty` | Float | Horas Extras Nocturnas (HEN) |
| `overtime_id` | Many2one `hr.overtime` | Registro creado al aplicar |
| `approved_by` | Many2one | Usuario que aprobó |
| `compensatory_date` | Date | Fecha de compensatorio (festivo/dominical) |

**Tipos de novedad:**

| Tipo | Generación | Descripción |
|------|-----------|-------------|
| `absence` | Automática | Ausencia total (sin marcaciones) |
| `delay` | Automática | Tardanza leve o grave |
| `partial_absence` | Automática | Trabajó menos del 50% del turno |
| `extra_day_hours` | Automática | H.E. Diurnas (+25%) — desde regla HED |
| `extra_night_hours` | Automática | H.E. Nocturnas (+75%) — desde regla HEN |
| `compensatory` | Automática | Trabajo en festivo/dominical (+200%) — desde regla HEDF |
| `extra_hours` | Automática | H.E. Genérico (si la regla usa este tipo) |
| `biometric_issue` | Automática | Solo entrada o solo salida registrada |
| `correction` | Manual | Corrección de marcación biométrica |
| `permission` | Manual | Permiso registrado por RRHH |
| `disability` | Manual | Incapacidad |
| `shift_change` | Manual | Cambio de turno |

**Flujo de aprobación:**
```
draft → review → approved → applied
              ↘ rejected
```

**Al aplicar (`action_apply`):** el sistema usa `overtime_type_id` de la novedad (asignado por la regla que la generó) para crear el `hr.overtime`. Si ese campo está vacío, recurre al mapeo por código según `novelty_type`.

---

### 3.6 `hr.overtime.rule` — Regla de Categorización de H.E.

Define las condiciones bajo las cuales un tramo horario genera un determinado tipo de novedad/hora extra. Reemplaza toda la lógica hardcodeada de clasificación.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | Char | Nombre descriptivo de la regla |
| `overtime_type_id` | Many2one `hr.overtime.type` | Categoría de H.E. en nómina CO |
| `economic_variable_id` | Many2one `economic.variable` | Variable para valoración (ej. `HD`) |
| `novelty_type` | Selection | Tipo de novedad que genera esta regla |
| `apply_on` | Selection | `normal` (Lun–Sáb) o `holiday_sunday` (Dom/Festivo) |
| `is_overtime` | Boolean | `True` = horas DESPUÉS del turno; `False` = recargo dentro del turno |
| `hour_from` | Float | Inicio del rango horario (0–24) |
| `hour_to` | Float | Fin del rango horario (0–24); si < `hour_from`, cruza medianoche |
| `sequence` | Integer | Orden de evaluación |
| `active` | Boolean | Activa/Inactiva |
| `company_id` | Many2one | Compañía |

**Reglas creadas por defecto al instalar:**

| Nombre | `apply_on` | `novelty_type` | Rango | Cód. nómina |
|--------|-----------|----------------|-------|-------------|
| Hora Extra Diurna (HED) | normal | `extra_day_hours` | 06:00–19:00 | HED |
| Hora Extra Nocturna (HEN) | normal | `extra_night_hours` | 19:00–06:00 | HEN |
| Hora Extra Festivo/Dom. (HEDF) | holiday_sunday | `compensatory` | 00:00–24:00 | HEDF |

**Cómo funciona:** Al procesar un período de tiempo post-turno, el sistema itera las reglas en orden de `sequence` y calcula la intersección de cada tramo con cada regla. El `novelty_type` y el `overtime_type_id` de la regla se transfieren directamente a la novedad generada.

---

### 3.7 Extensión `hr.employee`

- `default_shift_id` (Many2one `hr.shift`): Turno por defecto del empleado
- `attendance_record_ids` (One2many): Acceso a sus registros de asistencia
- Botón estadístico con conteo de registros de asistencia

---

### 3.8 `res.company` / `res.config.settings` — Configuración de Compañía

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `overtime_tolerance_minutes` | Integer | Minutos mínimos post-turno para generar H.E. |

Ver sección [5 — Tolerancia de horas extras](#5-tolerancia-de-horas-extras).

---

### 3.9 `hr.process.attendance.wizard` — Procesamiento Masivo

| Acción | Descripción |
|--------|-------------|
| `process` | Procesa marcaciones biométricas para las líneas confirmadas en el rango |
| `generate` | Genera líneas de programación masivamente para empleados en el rango |

**Opciones de generación:** sede, departamento, empleados específicos, excluir domingos/festivos, turno por defecto.

---

### 3.10 `hr.import.shifts.excel.wizard` — Importación Excel

Carga programaciones de turnos desde un archivo `.xlsx`.

| Columna | Campo | Descripción |
|---------|-------|-------------|
| A | Cédula/ID Empleado | `hr.employee.identification_id` |
| B | Código Turno | `hr.shift.code` (ej. `TA`, `ADM`) |
| C | Fecha | Formato `YYYY-MM-DD` o `DD/MM/YYYY` |

**Funcionalidades:** plantilla descargable, destino flexible (programación existente o nueva), validación por fila, resultado HTML con errores detallados.

---

### 3.11 `hr.biometric.overtime.report.wizard` — Reporte Consolidado

Genera reporte consolidado de horas extras biométricas.

**Filtros:** período, empleados, departamento, sede, resultado de asistencia.

**Formatos:** PDF (QWeb horizontal) y Excel (openpyxl con estilos corporativos).

**Columnas:** Fecha · Empleado · Cédula · Turno · Sede · Departamento · Entrada/Salida Planificada · Entrada/Salida Real · H. Regulares Diurnas · H. Regulares Nocturnas · H.E. Diurnas (HED) · H.E. Nocturnas (HEN) · H.E. Festivo (HEDF) · Festivo S/N · Dominical S/N · Valor Total ($)

---

## 4. Reglas de categorización de horas extras

Las reglas (`hr.overtime.rule`) son la fuente de verdad para determinar qué tipo de novedad y qué categoría de nómina corresponde a cada tramo horario trabajado fuera del turno.

**Configuración:** Control de Turnos › Configuración › Reglas de Horas Extras

Cada regla define:
- **`novelty_type`**: qué tipo de novedad de asistencia se genera (`extra_day_hours`, `extra_night_hours`, `compensatory`, `extra_hours`)
- **`overtime_type_id`**: el `hr.overtime.type` de nómina CO que se usará al aplicar la novedad
- **`economic_variable_id`**: variable económica para el cálculo del valor monetario
- **Rango horario** (`hour_from` → `hour_to`): el tramo del día al que aplica
- **Tipo de día** (`apply_on`): día normal o festivo/dominical

**Flexibilidad:** se pueden agregar reglas adicionales para casos especiales (turnos especiales, jornadas extendidas, etc.) sin tocar código.

---

## 5. Tolerancia de horas extras

Configurable en **Ajustes › Empleados › Control de Turnos y Biométrico**.

| Valor | Comportamiento |
|-------|----------------|
| `0` (defecto) | Sin tolerancia: cualquier minuto post-turno genera H.E. |
| `30` | Solo se genera H.E. si el empleado sale ≥ 30 min después del fin del turno |
| `N` | El umbral es N minutos; si se supera, se pagan **todas** las horas extras (no solo el excedente) |

**Ejemplo con 30 min de tolerancia:**

| Salida real | Fin turno | Minutos extra | ¿Genera H.E.? |
|------------|-----------|---------------|---------------|
| 18:15 | 18:00 | 15 min | ❌ No |
| 18:29 | 18:00 | 29 min | ❌ No |
| 18:30 | 18:00 | 30 min | ✅ Sí — paga 0.50h |
| 20:36 | 18:00 | 156 min | ✅ Sí — paga 2.60h |

---

## 6. Flujo de trabajo

```
1. CONFIGURACIÓN
   └── Turnos: Control de Turnos › Configuración › Turnos Laborales
   └── Reglas H.E.: Control de Turnos › Configuración › Reglas de Horas Extras
   └── Tolerancia: Ajustes › Empleados › Control de Turnos y Biométrico
   └── Variables económicas: Nómina CO → configurar líneas HD/HN por mes/año

2. PROGRAMACIÓN
   ├── Opción A: Líneas manuales en la programación
   ├── Opción B: Generar Turnos Masivamente (wizard)
   └── Opción C: Importar desde Excel
   └── Confirmar la programación

3. PROCESAMIENTO BIOMÉTRICO
   ├── Manual: botón "Procesar Asistencias" en la programación
   ├── Masivo: wizard Procesar/Generar Masivamente
   └── Automático: cron diario (procesa el día anterior)
   → Fuente: daily.attendance (vista de hr_zk_attendance)

4. REVISIÓN DE NOVEDADES
   └── Control de Turnos › Asistencia › Novedades Pendientes
       ├── Revisar cada novedad (tipo ya clasificado por las reglas)
       ├── Aprobar o rechazar
       └── Aplicar → genera hr.overtime con el tipo correcto

5. REPORTES
   └── Control de Turnos › Asistencia › Reporte Horas Extras

6. NÓMINA
   └── Los hr.overtime generados quedan disponibles para el liquidador de hr_payroll_co
```

---

## 7. Configuración inicial

### 7.1 Requisitos previos

1. **`hr_payroll_co`** con tipos de hora extra de códigos exactos: **HED**, **HEN**, **HEDF**
2. **`hr_zk_attendance`** con marcaciones en `daily.attendance`
3. Contratos activos (`state = 'open'`) para los empleados
4. Festivos colombianos en `hr.days.off.year` / `hr.day.off`

### 7.2 Instalar el módulo

```bash
./odoo-bin -d <nombre_bd> -u hr_payroll_co_biometric
```

El `post_init_hook` crea automáticamente las tres reglas de H.E. por defecto (HED, HEN, HEDF) vinculadas a la variable económica `HD`.

### 7.3 Zona horaria de la compañía

**Configuración › Compañías** → campo **Zona Horaria** = `America/Bogota`.

### 7.4 Tipos de hora extra requeridos

| Código | Descripción | Tasa |
|--------|-------------|------|
| `HED` | Hora Extra Diurna | 1.25 |
| `HEN` | Hora Extra Nocturna | 1.75 |
| `HEDF` | Hora Extra Festivo/Dominical | 3.00 |

### 7.5 Variables económicas

| Código | Variable | Uso |
|--------|----------|-----|
| `HD` | Valor Hora Diurna Ordinaria | Base HED/HEN/HEDF |
| `HN` | Valor Hora Nocturna Ordinaria | Recargo nocturno |
| `RN` | Recargo Nocturno | Diferencial nocturno |

Fallback si no se configuran: `SMMLV / MAX_HOURS_WORK` → `salario_contrato / 240`.

### 7.6 Turnos precargados

| Código | Horario | Tipo |
|--------|---------|------|
| `TA` | 06:00–14:00 | Diurno |
| `TB` | 14:00–22:00 | Diurno |
| `TC` | 22:00–06:00 | Nocturno (cruza medianoche) |
| `ADM` | 08:00–18:00 | Administrativo |
| `T12D` | 06:00–18:00 | 12 Horas |
| `T12N` | 18:00–06:00 | 12 Horas (cruza medianoche) |

---

## 8. Cómo usar el módulo

### 8.1 Crear y procesar una programación

1. **Control de Turnos › Programación › Programaciones de Turnos** → Nuevo
2. Completar: Referencia, Fecha Inicio/Fin, Sede, Departamento
3. Agregar líneas (manual, wizard masivo o importación Excel)
4. **Confirmar** la programación
5. **Procesar Asistencias** → genera registros y novedades

### 8.2 Gestionar novedades

1. **Control de Turnos › Asistencia › Novedades Pendientes**
2. El tipo de novedad ya viene clasificado por las reglas (`extra_day_hours`, `extra_night_hours`, `compensatory`)
3. Aprobar → Aplicar → crea `hr.overtime` con el tipo correcto

### 8.3 Configurar reglas de H.E.

1. **Control de Turnos › Configuración › Reglas de Horas Extras**
2. Las tres reglas colombianas ya existen (HED/HEN/HEDF)
3. Se pueden agregar reglas adicionales para casos especiales
4. Cada regla define: `novelty_type`, `overtime_type_id`, `economic_variable_id`, rango horario y tipo de día

### 8.4 Configurar tolerancia de H.E.

1. **Ajustes › Empleados › Control de Turnos y Biométrico**
2. Campo **Tolerancia Horas Extras (min)**
3. Ejemplo: `30` → solo se paga H.E. si el empleado sale ≥ 30 min después del turno

### 8.5 Generar reporte

1. **Control de Turnos › Asistencia › Reporte Horas Extras**
2. Configurar filtros y elegir PDF o Excel

---

## 9. Automatización (Cron)

El cron **"Control Biométrico: Procesar Asistencias Diarias"** se ejecuta diariamente y procesa todas las líneas de programación del día anterior con estado `scheduled`.

**Modificar:** Configuración › Técnico › Automatización › Acciones Programadas.

---

## 10. Seguridad y roles

| Rol | Permisos |
|-----|----------|
| **Usuario** | Lectura de sus propios registros |
| **Supervisor** | Crea y gestiona programaciones, importa Excel, genera reportes |
| **RRHH** | Aprueba novedades, acceso completo |
| **Administrador** | Configuración total |
| **Auditor** | Solo lectura en todos los modelos |

### Matriz de permisos por modelo

| Modelo | Usuario | Supervisor | RRHH | Administrador |
|--------|---------|------------|------|---------------|
| `hr.shift` | R | R | R | CRUD |
| `hr.shift.schedule` | R | CRUD | CRUD | CRUD |
| `hr.shift.schedule.line` | R | CRUD | CRUD | CRUD |
| `hr.attendance.record` | R | RW | CRUD | CRUD |
| `hr.attendance.novelty` | R | RC | CRUD | CRUD |
| `hr.overtime.rule` | R | R | RW | CRUD |
| `hr.import.shifts.excel.wizard` | — | CRUD | CRUD | CRUD |
| `hr.biometric.overtime.report.wizard` | — | CRUD | CRUD | CRUD |

*(R=Read, C=Create, U=Update, D=Delete)*

---

## 11. Integración con nómina

### Búsqueda del valor hora base

```
1. economic.variable.line con code='HD' para el mes/año del registro
   └── Si no existe →
2. SMMLV / MAX_HOURS_WORK (variables económicas estándar)
   └── Si no existen →
3. hr.contract.wage / 240 (salario mensual ÷ 240 horas)
```

### Creación de `hr.overtime` al aplicar novedades

1. Busca contrato activo del empleado (`hr.contract.state = 'open'`)
2. Toma `overtime_type_id` directamente de la novedad (asignado por la regla)
3. Fallback: busca `hr.overtime.type` por código según `OVERTIME_TYPE_CODE_BY_NOVELTY`
4. Crea `hr.overtime` con: empleado, contrato, fecha, tipo, cantidad

### Novedades manuales

Las novedades `permission`, `disability` y `shift_change` no crean registros en nómina automáticamente; RRHH las gestiona directamente en `hr_payroll_co`.

---

## 12. Datos precargados

| Archivo | Contenido |
|---------|-----------|
| `hr_shift_type_data.xml` | 6 turnos base (TA, TB, TC, ADM, T12D, T12N) — `noupdate=1` |
| `hr_overtime_rules_data.xml` | Referenciado en manifest; las reglas se crean via `post_init_hook` |
| `economic_variables_data.xml` | Registros `economic.variable` HD, HN, RN — `noupdate=1` |
| `ir_cron_data.xml` | Cron diario de procesamiento |

**Secuencia de novedades:** `NOV/YYYY/NNNNN` (ej. `NOV/2026/00042`)

---

## 13. Estructura de archivos

```
hr_payroll_co_biometric/
│
├── __manifest__.py
├── __init__.py
├── hooks.py                           # post_init_hook: crea reglas HED/HEN/HEDF
│
├── models/
│   ├── hr_shift.py                    # hr.shift
│   ├── hr_shift_schedule.py           # hr.shift.schedule + hr.shift.schedule.line
│   ├── hr_attendance_record.py        # hr.attendance.record (procesamiento biométrico)
│   ├── hr_attendance_novelty.py       # hr.attendance.novelty (novedades + hr.overtime)
│   ├── hr_overtime_rule.py            # hr.overtime.rule (reglas configurables)
│   ├── hr_employee.py                 # Extensión hr.employee
│   └── res_config_settings.py        # overtime_tolerance_minutes en res.company
│
├── wizards/
│   ├── hr_process_attendance_wizard.py
│   ├── hr_import_shifts_excel_wizard.py
│   └── *_views.xml
│
├── reports/
│   ├── hr_overtime_report.py
│   ├── hr_overtime_report_views.xml
│   └── hr_overtime_report_template.xml
│
├── views/
│   ├── hr_shift_views.xml
│   ├── hr_shift_schedule_views.xml
│   ├── hr_attendance_record_views.xml
│   ├── hr_attendance_novelty_views.xml
│   ├── hr_overtime_rule_views.xml
│   ├── res_config_settings_views.xml  # Bloque en Ajustes › Empleados
│   └── menus.xml
│
├── security/
│   ├── security.xml
│   └── ir.model.access.csv
│
└── data/
    ├── hr_shift_type_data.xml
    ├── hr_overtime_rules_data.xml
    ├── economic_variables_data.xml
    └── ir_cron_data.xml
```

---

## Menú de navegación

```
Control de Turnos
├── Programación
│   ├── Programaciones de Turnos
│   ├── Calendario de Turnos              (vista Calendario / Gantt / Lista)
│   ├── Procesar/Generar Masivamente
│   └── Importar Turnos desde Excel
├── Asistencia
│   ├── Registros de Asistencia
│   ├── Novedades
│   ├── Novedades Pendientes
│   └── Reporte Horas Extras
└── Configuración
    ├── Turnos Laborales
    └── Reglas de Horas Extras
```

*(Tolerancia de H.E. en Ajustes › Empleados › Control de Turnos y Biométrico)*

---

## 14. Historial de cambios

### v17.0.2.0.0 — Mayo–Junio 2026

**Nuevas funcionalidades:**
- `hr.overtime.rule`: modelo configurable de reglas de categorización de H.E. Reemplaza toda la lógica hardcodeada de HED/HEN/HEDF. Cada regla define `novelty_type`, `overtime_type_id`, `economic_variable_id`, rango horario y tipo de día
- Campo `novelty_type` en `hr.overtime.rule`: el tipo de novedad ahora viene de la regla, no del código
- Campo `overtime_tolerance_minutes` en `res.company`: tolerancia configurable en Ajustes para no generar H.E. menores a N minutos
- Vistas Calendario y Gantt para líneas de programación
- Wizard de importación de turnos desde Excel
- Reporte consolidado de H.E. con exportación PDF y Excel

**Correcciones:**
- `extra_hours` en `hr.attendance.record` ahora refleja solo el tiempo posterior al fin del turno (`actual_check_out - planned_end`), sin incluir llegadas anticipadas
- Límite diurno/nocturno corregido a 19:00 (legislación colombiana vigente, Ley 2101/2021)

### v17.0.1.0.0 — Versión inicial
- Implementación base: turnos, programaciones, procesamiento biométrico, novedades, integración con `hr_payroll_co`

---

*Desarrollado por OdOne S.A.S — Soluciones Odoo para Colombia*


---

## Tabla de contenido

1. [Descripción general](#1-descripción-general)
2. [Dependencias](#2-dependencias)
3. [Modelos implementados](#3-modelos-implementados)
4. [Flujo de trabajo](#4-flujo-de-trabajo)
5. [Configuración inicial](#5-configuración-inicial)
6. [Cómo usar el módulo](#6-cómo-usar-el-módulo)
7. [Automatización (Cron)](#7-automatización-cron)
8. [Seguridad y roles](#8-seguridad-y-roles)
9. [Integración con nómina](#9-integración-con-nómina)
10. [Datos precargados](#10-datos-precargados)
11. [Estructura de archivos](#11-estructura-de-archivos)
12. [Historial de cambios](#12-historial-de-cambios)

---

## 1. Descripción general

El módulo conecta tres sistemas:

```
Dispositivos ZKTeco  →  Marcaciones biométricas  →  hr_zk_attendance (daily.attendance)
          ↓
Programaciones de turno  →  Comparación planificado vs. real
          ↓                       ↓
Breakdown horas día/noche    Detección festivos (hr.day.off)
          ↓
Novedades HED/HEN/HEDF  →  hr_payroll_co (nómina colombiana)
```

Permite:
- Definir **turnos laborales** con horarios, tolerancias y tipos (diurno, nocturno, rotativo, etc.)
- Crear **programaciones** de turno por período, sede o departamento
- **Importar programaciones desde Excel** (wizard con plantilla descargable)
- **Visualizar turnos** en vistas de Calendario y Gantt
- **Comparar** automáticamente las marcaciones biométricas contra el turno programado
- **Detectar y clasificar novedades**: tardanzas, ausencias, horas extras diurnas/nocturnas, inconsistencias biométricas
- **Calcular el desglose** de horas regulares diurnas/nocturnas y horas extras HED/HEN/HEDF según legislación colombiana
- **Valorar económicamente** las horas extras usando variables económicas HD/HN
- **Aplicar las novedades** al módulo de nómina (`hr.overtime`, `hr.novelty`)
- **Generar reportes consolidados** de horas extras en PDF y Excel

---

## 2. Dependencias

| Módulo | Propósito |
|--------|-----------|
| `hr_payroll_co` | Nómina colombiana propia (OdOne). Provee `hr.overtime`, `hr.overtime.type`, `hr.novelty`, `hr.contract`, `hr.period`, `economic.variable`, `hr.days.off.year`, `hr.day.off` |
| `hr_zk_attendance` | Integración con dispositivos biométricos ZKTeco. Provee `daily.attendance` (vista agregada de marcaciones por empleado/día) |

**Dependencia de sistema (opcional):**
- `openpyxl`: requerido para importación de Excel y exportación de reporte. Instalar con `pip install openpyxl`.

---

## 3. Modelos implementados

### 3.1 `hr.shift` — Turno Laboral

Define la configuración de un tipo de turno.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | Char | Nombre descriptivo del turno |
| `code` | Char(10) | Código único por compañía (ej. `TA`, `TB`, `ADM`) |
| `shift_type` | Selection | Tipo: `day`, `night`, `mixed`, `rotating`, `admin`, `special`, `sunday`, `holiday`, `extended`, `twelve` |
| `hour_from` | Float | Hora de inicio (ej. `6.0` = 06:00) |
| `hour_to` | Float | Hora de fin (ej. `14.0` = 14:00) |
| `crosses_midnight` | Boolean | Calculado: `True` si `hour_to < hour_from` |
| `effective_hours` | Float | Calculado: `(hour_to - hour_from) - rest_time` con manejo de medianoche |
| `rest_time` | Float | Tiempo de descanso a descontar (horas) |
| `tolerance_in` | Integer | Minutos de gracia para llegada tardía |
| `tolerance_out` | Integer | Minutos de gracia para salida anticipada |
| `is_rotating_cycle` | Boolean | Indica si es un turno rotativo con ciclo |
| `cycle_work_days` | Integer | Días de trabajo en el ciclo rotativo |
| `cycle_rest_days` | Integer | Días de descanso en el ciclo rotativo |

**Lógica especial:**
- Un turno que cruza medianoche (ej. `22:00 → 06:00`) se detecta automáticamente comparando `hour_to < hour_from`.
- Las horas efectivas se calculan sumando 24h cuando el turno cruza medianoche.

---

### 3.2 `hr.shift.schedule` — Programación de Turnos

Cabecera de una programación de turnos para un período/sede.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | Char | Referencia de la programación |
| `state` | Selection | `draft` → `confirmed` → `done` / `cancel` |
| `date_start` | Date | Inicio del período |
| `date_end` | Date | Fin del período |
| `address_id` | Many2one | Sede / Lugar de trabajo |
| `department_id` | Many2one | Departamento (opcional, para filtrar) |
| `line_ids` | One2many | Líneas de asignación empleado-turno-fecha |
| `line_count` | Integer | Calculado: total de líneas |

**Estados:**

```
Borrador (draft) → Confirmado (confirmed) → Ejecutado (done)
                                          ↘ Cancelado (cancel)
```

---

### 3.3 `hr.shift.schedule.line` — Línea de Programación

Una asignación concreta: un empleado, un turno, una fecha.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `schedule_id` | Many2one | Cabecera de programación |
| `employee_id` | Many2one | Empleado asignado |
| `shift_id` | Many2one | Turno asignado |
| `work_date` | Date | Fecha de trabajo |
| `planned_start` | Datetime | Hora UTC calculada de inicio del turno |
| `planned_end` | Datetime | Hora UTC calculada de fin del turno |
| `is_sunday` | Boolean | `True` si la fecha es domingo |
| `is_holiday` | Boolean | `True` si existe un registro `hr.day.off` para esa fecha (festivos nómina CO) |
| `state` | Selection | `scheduled` / `processed` / `novelty` / `absent` |
| `attendance_record_id` | Many2one | Enlace al registro de asistencia generado |

**Lógica de cálculo de horas (`_compute_planned_times`):**
1. Lee la zona horaria de la compañía del empleado (por defecto `America/Bogota`)
2. Convierte `hour_from`/`hour_to` del turno a `datetime` local
3. Si el turno cruza medianoche, suma un día a la fecha fin
4. Convierte ambos a UTC (sin tzinfo) para almacenamiento

**Detección de festivos:** Busca en `hr.day.off` (módulo `hr_payroll_co`) por campo `date`. Este modelo es el registro oficial de festivos de la nómina colombiana, reemplazando `resource.calendar.leaves`.

**Validación:** Un empleado no puede tener dos turnos asignados en la misma fecha en programaciones no canceladas.

**Vistas disponibles:** Lista, Calendario (por `planned_start`/`planned_end`, color por turno) y Gantt (agrupado por empleado).

---

### 3.4 `hr.attendance.record` — Registro de Asistencia

Resultado de comparar el turno programado con la marcación biométrica real.

#### Campos principales

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `employee_id` | Many2one | Empleado |
| `schedule_line_id` | Many2one | Línea de programación de origen |
| `shift_id` | Many2one | Turno programado |
| `work_date` | Date | Fecha |
| `planned_start` / `planned_end` | Datetime | Turno programado (UTC) |
| `actual_check_in` / `actual_check_out` | Datetime | Marcaciones biométricas reales (UTC) |
| `worked_hours` | Float | `actual_check_out - actual_check_in` en horas |
| `biometric_punch_count` | Integer | Número total de marcaciones del día |
| `attendance_result` | Selection | Clasificación del resultado |
| `delay_minutes` | Integer | Minutos de llegada tardía |
| `early_out_minutes` | Integer | Minutos de salida anticipada |
| `extra_hours` | Float | Horas adicionales trabajadas sobre el turno (total) |
| `is_sunday` | Boolean | Domingo |
| `is_holiday` | Boolean | Festivo |
| `correction_state` | Selection | Estado de solicitud de corrección biométrica |

#### Campos de desglose de horas (HU-TH-024)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `day_hours` | Float | Horas regulares en jornada diurna (06:00–21:00) |
| `night_hours` | Float | Horas regulares en jornada nocturna (21:00–06:00) |
| `extra_day_hours` | Float | H.E. Diurnas (HED) — sobre el turno, en horario diurno |
| `extra_night_hours` | Float | H.E. Nocturnas (HEN) — sobre el turno, en horario nocturno |
| `holiday_work_hours` | Float | Horas trabajadas en festivo/dominical (HEDF) |

#### Campos de valoración económica (HU-TH-024)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `hour_base_value` | Float | Valor de la hora diurna base (desde variable económica `HD`) |
| `night_surcharge_value` | Float | Valor del recargo nocturno |
| `extra_day_value` | Float | Valor total H.E. Diurnas (HED × qty × tasa) |
| `extra_night_value` | Float | Valor total H.E. Nocturnas (HEN × qty × tasa) |
| `holiday_extra_value` | Float | Valor total H.E. Festivo/Dominical (HEDF × qty × tasa) |
| `total_overtime_value` | Float | Suma total de todos los valores de horas extras |

**Clasificación de jornadas (legislación colombiana):**
- Jornada **diurna**: 06:00 – 21:00
- Jornada **nocturna**: 21:00 – 06:00
- Recargo nocturno (RN): +35% sobre hora base
- H.E. Diurna (HED): +25% (tasa 1.25×)
- H.E. Nocturna (HEN): +75% (tasa 1.75×)
- H.E. Festivo/Dominical (HEDF): +200% (tasa 3.00×)

**Resultados posibles (`attendance_result`):**

| Código | Descripción | Condición |
|--------|-------------|-----------|
| `ok` | Asistencia Correcta | Sin tardanza significativa ni ausencia |
| `late_minor` | Retardo Leve | Tardanza ≤ tolerancia × 3 |
| `late_major` | Retardo Grave | Tardanza > tolerancia × 3 |
| `partial_absence` | Ausencia Parcial | Trabajó < 50% de las horas programadas |
| `total_absence` | Ausencia Total | Sin marcaciones |
| `biometric_issue` | Inconsistencia Biométrica | Solo una marcación (sin entrada o sin salida) |
| `extra_hours` | Horas Adicionales | Trabajó más del 110% de las horas programadas |

**Búsqueda biométrica (`action_compute_from_biometric`):**
- Busca en `daily.attendance` (vista agregada de `hr_zk_attendance`) filtrando por `employee_id` y `punching_day`
- `check_in` del registro diario → `actual_check_in`
- `check_out` del registro diario → `actual_check_out`
- `punch_count` → `biometric_punch_count`
- Si `check_in == check_out` (solo 1 punch) se registra como `biometric_issue`

---

### 3.5 `hr.attendance.novelty` — Novedad de Asistencia

Novedad detectada automáticamente o registrada manualmente.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | Char | Secuencia automática `NOV/YYYY/NNNNN` |
| `employee_id` | Many2one | Empleado |
| `work_date` | Date | Fecha de la novedad |
| `novelty_type` | Selection | Tipo de novedad |
| `state` | Selection | `draft` → `review` → `approved` → `applied` / `rejected` |
| `minutes` | Integer | Minutos de la novedad (tardanzas, ausencias parciales) |
| `extra_hours` | Float | Horas extras totales detectadas (legacy) |
| `extra_day_qty` | Float | Horas Extras Diurnas (HED) |
| `extra_night_qty` | Float | Horas Extras Nocturnas (HEN) |
| `overtime_id` | Many2one | `hr.overtime` creado al aplicar horas extras |
| `approved_by` | Many2one | Usuario que aprobó |
| `compensatory_date` | Date | Fecha de compensatorio (para domingo/festivo) |

**Tipos de novedad:**

| Tipo | Código nómina | Generación | Descripción |
|------|--------------|-----------|-------------|
| `absence` | — | Automática | Ausencia total (sin marcaciones) |
| `delay` | — | Automática | Tardanza leve o grave |
| `partial_absence` | — | Automática | Trabajó menos del 50% |
| `extra_day_hours` | HED | Automática | H.E. Diurnas (+25%) |
| `extra_night_hours` | HEN | Automática | H.E. Nocturnas (+75%) |
| `compensatory` | HEDF | Automática | Trabajo en festivo/dominical (+200%) |
| `biometric_issue` | — | Automática | Solo entrada o solo salida registrada |
| `correction` | — | Manual | Corrección de marcación biométrica |
| `permission` | — | Manual | Permiso registrado por RRHH |
| `disability` | — | Manual | Incapacidad |
| `shift_change` | — | Manual | Cambio de turno |

**Flujo de aprobación:**

```
draft → review → approved → applied
              ↘ rejected
```

Al hacer `action_apply()` en novedades de horas extras, el sistema llama a `_get_overtime_type_by_code(code)` que busca el `hr.overtime.type` por código exacto (HED, HEN o HEDF) y crea el registro `hr.overtime` correspondiente.

---

### 3.6 Extensión `hr.employee`

Se agrega al empleado:
- `default_shift_id` (Many2one `hr.shift`): Turno por defecto del empleado
- `attendance_record_ids` (One2many): Acceso a sus registros de asistencia
- Botón estadístico con conteo de registros de asistencia

---

### 3.7 `hr.process.attendance.wizard` — Wizard de Procesamiento Masivo

Permite procesar o generar turnos para múltiples empleados a la vez.

**Acciones disponibles:**

| Acción | Descripción |
|--------|-------------|
| `process` | Procesa las marcaciones biométricas para las líneas confirmadas en el rango de fechas |
| `generate` | Genera líneas de programación masivamente para empleados en el rango de fechas |

**Opciones de generación:**
- Filtrar por sede, departamento, empleados específicos
- Excluir domingos y/o festivos
- Asignar un turno por defecto (o usar el turno por defecto del empleado)

---

### 3.8 `hr.import.shifts.excel.wizard` — Wizard de Importación Excel (HU-TH-024)

Permite cargar programaciones de turnos desde un archivo `.xlsx`.

**Formato de la plantilla:**

| Columna | Campo | Descripción |
|---------|-------|-------------|
| A | Cédula/ID Empleado | `hr.employee.identification_id` |
| B | Código Turno | `hr.shift.code` (ej. `TA`, `TB`, `ADM`) |
| C | Fecha | Formato `YYYY-MM-DD` o `DD/MM/YYYY` |

**Funcionalidades:**
- **Descarga de plantilla**: genera un `.xlsx` con encabezados y una segunda hoja con los turnos disponibles
- **Destino flexible**: agregar a una programación existente (debe estar en borrador) o crear una nueva
- **Validación**: cédula existente, código de turno válido, formato de fecha correcto, duplicados por programación
- **Resultado HTML**: muestra líneas creadas, duplicados omitidos y lista de errores por fila

---

### 3.9 `hr.biometric.overtime.report.wizard` — Reporte Consolidado (HU-TH-024)

Wizard para generar el reporte consolidado de horas extras biométricas.

**Filtros disponibles:**

| Filtro | Descripción |
|--------|-------------|
| Fecha Inicio / Fin | Período del reporte (requerido) |
| Empleados | Selección múltiple (vacío = todos) |
| Departamento | Filtro por departamento |
| Sede | Filtro por centro de trabajo |
| Resultado asistencia | ok, extra_hours, tardanzas, ausencias, etc. |

**Formatos de salida:**

| Formato | Descripción |
|---------|-------------|
| PDF | QWeb, orientación horizontal, tabla con totales y resumen |
| Excel (.xlsx) | Estilizado con colores corporativos, fila de totales, freeze panes en fila 5 |

**Columnas del reporte:**
Fecha · Empleado · Cédula · Turno · Sede · Departamento · Entrada/Salida Planificada · Entrada/Salida Real · H. Regulares Diurnas · H. Regulares Nocturnas · H.E. Diurnas (HED) · H.E. Nocturnas (HEN) · H.E. Festivo (HEDF) · Festivo S/N · Dominical S/N · Valor Total ($)

---

## 4. Flujo de trabajo

### Flujo completo resumido

```
1. CONFIGURACIÓN
   └── Crear/revisar turnos en: Control de Turnos › Configuración › Turnos Laborales
   └── Configurar variables económicas HD/HN/RN para valoración de horas

2. PROGRAMACIÓN
   └── Crear programación: Control de Turnos › Programación › Programaciones de Turnos
       ├── Opción A: Agregar líneas manualmente (empleado + turno + fecha)
       ├── Opción B: Usar "Generar Turnos Masivamente" (wizard)
       └── Opción C: Importar desde Excel (Control de Turnos › Programación › Importar Turnos)
   └── Visualizar en Calendario o Gantt: Control de Turnos › Programación › Calendario de Turnos
   └── Confirmar la programación (botón "Confirmar")

3. PROCESAMIENTO
   └── Opción A: Manual → botón "Procesar Asistencias" en la programación
   └── Opción B: Masivo → Control de Turnos › Programación › Procesar/Generar Masivamente
   └── Opción C: Automático → Cron diario (procesa el día anterior)
   → Fuente biométrica: daily.attendance (vista agregada hr_zk_attendance)

4. REVISIÓN DE NOVEDADES
   └── Control de Turnos › Asistencia › Novedades Pendientes
       ├── Revisar cada novedad (HED, HEN, HEDF según hora del día)
       ├── Aprobar o rechazar
       └── Aplicar (genera hr.overtime con código HED/HEN/HEDF)

5. REPORTES
   └── Control de Turnos › Asistencia › Reporte Horas Extras
       ├── Filtrar por período, empleado, departamento, sede
       ├── Exportar PDF
       └── Exportar Excel

6. NÓMINA
   └── Las horas extras aplicadas quedan en hr.overtime (HED/HEN/HEDF)
   └── El liquidador de nómina las incluye en el proceso de hr_payroll_co
```

---

## 5. Configuración inicial

### 5.1 Requisitos previos

1. **Módulo `hr_payroll_co`** instalado y configurado con:
   - Tipos de hora extra (`hr.overtime.type`) con códigos exactos: **HED**, **HEN**, **HEDF**
   - Contratos de empleados activos (`state = 'open'`)
   - Festivos colombianos cargados en `hr.days.off.year` / `hr.day.off`

2. **Módulo `hr_zk_attendance`** instalado con:
   - Marcaciones importadas (disponibles en vista `daily.attendance`)

3. **Variables económicas** (`economic.variable`): El módulo crea automáticamente los registros HD, HN y RN al instalar. Las **líneas de valor** por mes/año deben ser configuradas por el administrador de nómina.

4. **openpyxl** instalado en el entorno Python para importación/exportación Excel:
   ```bash
   pip install openpyxl
   ```

### 5.2 Instalar el módulo

```bash
./odoo-bin -d <nombre_bd> -u hr_payroll_co_biometric
```

### 5.3 Configurar zona horaria de la compañía

Ir a **Configuración > Compañías** y verificar que el campo **Zona Horaria** esté en `America/Bogota`.

### 5.4 Configurar tipos de hora extra

En `hr_payroll_co`, verificar que existan los tipos con estos códigos exactos:

| Código | Descripción | Tasa |
|--------|-------------|------|
| `HED` | Hora Extra Diurna | 1.25 (+25%) |
| `HEN` | Hora Extra Nocturna | 1.75 (+75%) |
| `HEDF` | Hora Extra Festivo/Dominical | 3.00 (+200%) |

### 5.5 Configurar variables económicas

Ir a la configuración de nómina y configurar líneas mensuales para:

| Código | Variable | Uso |
|--------|----------|-----|
| `HD` | Valor Hora Diurna Ordinaria | Base para cálculo de HED/HEN/HEDF |
| `HN` | Valor Hora Nocturna Ordinaria | Recargo nocturno base |
| `RN` | Recargo Nocturno | Diferencial nocturno |

Si no se configuran, el sistema usa como fallback: `SMMLV / MAX_HOURS_WORK` o `salario_contrato / 240`.

### 5.6 Verificar turnos precargados

Al instalar, se crean automáticamente estos turnos base:

| Código | Nombre | Horario | Tipo |
|--------|--------|---------|------|
| `TA` | Turno A - Mañana | 06:00–14:00 | Diurno |
| `TB` | Turno B - Tarde | 14:00–22:00 | Diurno |
| `TC` | Turno C - Noche | 22:00–06:00 | Nocturno (cruza medianoche) |
| `ADM` | Administrativo | 08:00–18:00 | Administrativo |
| `T12D` | Turno 12h Día | 06:00–18:00 | 12 Horas |
| `T12N` | Turno 12h Noche | 18:00–06:00 | 12 Horas (cruza medianoche) |

---

## 6. Cómo usar el módulo

### 6.1 Crear una programación de turnos

1. Ir a **Control de Turnos › Programación › Programaciones de Turnos**
2. Clic en **Nuevo**
3. Completar: Referencia, Fecha Inicio/Fin, Sede, Departamento
4. **Agregar líneas** de una de estas formas:

#### Opción A: Manualmente
En la pestaña de líneas, clic en **Agregar línea**.

#### Opción B: Generación masiva (recomendada)
Clic en **Generar Turnos Masivamente** y configurar el wizard.

#### Opción C: Importación desde Excel
1. Ir a **Control de Turnos › Programación › Importar Turnos desde Excel**
2. Descargar la plantilla con **Descargar Plantilla**
3. Completar el archivo con: Cédula, Código Turno, Fecha
4. Cargar el archivo y clic en **Importar**
5. Revisar el resultado (líneas creadas, errores por fila)

### 6.2 Visualizar turnos en Calendario o Gantt

1. Ir a **Control de Turnos › Programación › Calendario de Turnos**
2. Cambiar la vista con los botones de la parte superior derecha:
   - **Calendario**: vista mensual por fecha, color por tipo de turno
   - **Gantt**: vista por empleado, barras de duración del turno
   - **Lista**: vista tabular completa

### 6.3 Procesar asistencias biométricas

El sistema consulta `daily.attendance` (una fila por empleado/día con primer punch como `check_in` y último como `check_out`).

#### Desde la programación (manual)
Clic en **Procesar Asistencias** en una programación confirmada.

#### Masivamente
**Control de Turnos › Programación › Procesar/Generar Masivamente** → acción **Procesar**.

### 6.4 Revisar registros de asistencia

1. **Control de Turnos › Asistencia › Registros de Asistencia**
2. Pestaña **Breakdown Horas**: muestra el desglose día/noche y la valoración económica calculada
3. Colores: Verde (ok), Amarillo (tardanza), Rojo (ausencia), Azul (horas extras)

### 6.5 Gestionar novedades

1. **Control de Turnos › Asistencia › Novedades Pendientes**
2. Las horas extras ahora se dividen en:
   - **H.E. Diurnas (HED)**: horas extra trabajadas entre 06:00–21:00
   - **H.E. Nocturnas (HEN)**: horas extra trabajadas entre 21:00–06:00
   - **Festivo/Dominical (HEDF)**: horas trabajadas en día no laborable
3. Al **Aplicar** se crea el `hr.overtime` con el código correcto (HED/HEN/HEDF)

### 6.6 Generar reporte consolidado de horas extras

1. **Control de Turnos › Asistencia › Reporte Horas Extras**
2. Configurar filtros: período, empleados, departamento, sede, resultado
3. Clic en **Imprimir PDF** o **Exportar Excel**

### 6.7 Correcciones biométricas

1. Abrir el **Registro de Asistencia** del empleado
2. Pestaña **Corrección** → **Solicitar Corrección**
3. RRHH aprueba; al aprobar se recalcula el desglose de horas y se regeneran las novedades

---

## 7. Automatización (Cron)

El módulo instala un **cron job diario** que:

- Se ejecuta todos los días
- Busca líneas de programación del **día anterior** con estado `scheduled` y programación `confirmed`
- Ejecuta `action_process_attendance()` en todas ellas (consultando `daily.attendance`)
- Genera registros de asistencia con desglose de horas y novedades automáticamente

**Verificar/modificar el cron:**
> "Control Biométrico: Procesar Asistencias Diarias" en Configuración > Técnico > Automatización

---

## 8. Seguridad y roles

| Rol | Permisos | Hereda de |
|-----|----------|-----------|
| **Usuario** | Lee sus propios registros | — |
| **Supervisor** | Crea y gestiona programaciones, importa Excel, genera reportes | Usuario |
| **RRHH** | Aprueba novedades, acceso completo | Supervisor |
| **Administrador** | Configuración total | RRHH |
| **Auditor** | Solo lectura en todos los modelos | Usuario |

### Matriz de permisos por modelo

| Modelo | Usuario | Supervisor | RRHH | Administrador |
|--------|---------|------------|------|---------------|
| `hr.shift` | R | R | R | CRUD |
| `hr.shift.schedule` | R | CRUD | CRUD | CRUD |
| `hr.shift.schedule.line` | R | CRUD | CRUD | CRUD |
| `hr.attendance.record` | R | RW | CRUD | CRUD |
| `hr.attendance.novelty` | R | RC | CRUD | CRUD |
| `hr.import.shifts.excel.wizard` | — | CRUD | CRUD | CRUD |
| `hr.biometric.overtime.report.wizard` | — | CRUD | CRUD | CRUD |

*(R=Read, C=Create, U=Update, D=Delete)*

---

## 9. Integración con nómina

### Búsqueda del valor hora base

El método `_get_hour_base_value()` en `hr.attendance.record` busca el valor hora en esta cadena de fallback:

```
1. economic.variable.line con code='HD' para el mes/año del registro
   └── Si no existe →
2. SMMLV / MAX_HOURS_WORK (variables económicas estándar)
   └── Si no existen →
3. hr.contract.wage / 240 (salario mensual ÷ 240 horas)
```

### Creación de hr.overtime al aplicar novedades

Cuando se **aplica** una novedad de horas extras, el sistema:

1. Busca el contrato activo del empleado (`hr.contract` con `state='open'`)
2. Llama a `_get_overtime_type_by_code(code)` con el código exacto (HED, HEN o HEDF)
3. Crea un registro `hr.overtime` con: empleado, contrato, fecha, tipo de hora extra, cantidad, estado `draft`

### Novedades manuales

Las novedades de tipo `permission`, `disability` y `shift_change` **no** crean automáticamente registros en nómina. El área de RRHH debe gestionarlas directamente en `hr_payroll_co`.

---

## 10. Datos precargados

### Turnos (`hr_shift_type_data.xml`, `noupdate=1`)
Los 6 turnos base descritos en la sección 5.6.

### Variables económicas (`economic_variables_data.xml`, `noupdate=1`)
Crea los registros de `economic.variable` para HD, HN y RN. Las líneas de valor por mes/año deben ser configuradas manualmente.

### Secuencia de novedades
```
Prefijo: NOV/ | Año: %(year)s/ | Padding: 5 dígitos
Ejemplo: NOV/2026/00042
```

### Cron diario
Activo, intervalo de 1 día, ejecutado por el usuario administrador del sistema.

---

## 11. Estructura de archivos

```
hr_payroll_co_biometric/
│
├── __manifest__.py                    # Declaración del módulo (v19.0.1.0.0)
├── __init__.py                        # Imports: models, wizards, reports
│
├── models/
│   ├── __init__.py
│   ├── hr_shift.py                    # Modelo hr.shift (turnos)
│   ├── hr_shift_schedule.py           # hr.shift.schedule y hr.shift.schedule.line
│   │                                  #   → festivos via hr.day.off
│   ├── hr_attendance_record.py        # hr.attendance.record
│   │                                  #   → fuente: daily.attendance
│   │                                  #   → desglose día/noche + valoración HD/HN
│   ├── hr_attendance_novelty.py       # hr.attendance.novelty
│   │                                  #   → tipos HED/HEN/HEDF
│   │                                  #   → _get_overtime_type_by_code(code)
│   └── hr_employee.py                 # Extensión hr.employee
│
├── wizards/
│   ├── __init__.py
│   ├── hr_process_attendance_wizard.py
│   ├── hr_process_attendance_wizard_views.xml
│   ├── hr_import_shifts_excel_wizard.py        # ★ NUEVO — importación Excel
│   └── hr_import_shifts_excel_wizard_views.xml # ★ NUEVO
│
├── reports/                                    # ★ NUEVA CARPETA
│   ├── __init__.py
│   ├── hr_overtime_report.py                   # ★ NUEVO — reporte consolidado
│   ├── hr_overtime_report_views.xml            # ★ NUEVO — wizard + ir.actions.report
│   └── hr_overtime_report_template.xml         # ★ NUEVO — template QWeb PDF
│
├── views/
│   ├── hr_shift_views.xml
│   ├── hr_shift_schedule_views.xml             # ★ ACTUALIZADO — vistas Calendario + Gantt
│   ├── hr_attendance_record_views.xml          # ★ ACTUALIZADO — tab Breakdown Horas
│   ├── hr_attendance_novelty_views.xml
│   └── menus.xml                               # ★ ACTUALIZADO — nuevos menús
│
├── security/
│   ├── security.xml
│   └── ir.model.access.csv                     # ★ ACTUALIZADO — nuevos wizards/report
│
├── data/
│   ├── hr_shift_type_data.xml
│   ├── ir_cron_data.xml
│   └── economic_variables_data.xml             # ★ NUEVO — variables HD, HN, RN
│
└── static/description/
    └── icon.png
```

---

## Menú de navegación

```
Control de Turnos (menú raíz, secuencia 85)
├── Programación
│   ├── Programaciones de Turnos          → hr.shift.schedule (lista + form)
│   ├── Calendario de Turnos              → hr.shift.schedule.line (calendario/gantt/lista) ★
│   ├── Procesar/Generar Masivamente      → wizard hr.process.attendance.wizard
│   └── Importar Turnos desde Excel       → wizard hr.import.shifts.excel.wizard ★
├── Asistencia
│   ├── Registros de Asistencia           → hr.attendance.record
│   ├── Novedades                         → hr.attendance.novelty (todas)
│   ├── Novedades Pendientes              → hr.attendance.novelty (filtro: draft/review)
│   └── Reporte Horas Extras              → wizard hr.biometric.overtime.report.wizard ★
└── Configuración
    └── Turnos Laborales                  → hr.shift
```

*(★ = agregado en HU-TH-024)*

---

## 12. Historial de cambios

### v17.0.2.0.0 — Mayo 2026 (HU-TH-024)

**Cambios en modelos existentes:**
- `hr.attendance.record`: fuente biométrica cambiada de `zk.machine.attendance` a `daily.attendance`; agregados campos de desglose de horas (diurnas/nocturnas/extras) y valoración económica (HD/HN/HEDF); `biometric_punch_count` reemplaza a `biometric_device_in/out`
- `hr.shift.schedule.line`: detección de festivos migrada de `resource.calendar.leaves` a `hr.day.off`
- `hr.attendance.novelty`: tipos de horas extras separados en HED/HEN/HEDF con campos `extra_day_qty`/`extra_night_qty`; búsqueda de `hr.overtime.type` por código exacto

**Nuevas funcionalidades:**
- Vistas Calendario y Gantt para líneas de programación de turnos
- Wizard de importación de turnos desde Excel (con plantilla descargable y validación por fila)
- Reporte consolidado de horas extras con exportación PDF (QWeb) y Excel (openpyxl)
- Variables económicas HD, HN, RN creadas automáticamente al instalar

### v17.0.1.0.0 — Versión inicial
- Implementación base: turnos, programaciones, procesamiento biométrico, novedades, integración con `hr_payroll_co`

---

*Desarrollado por OdOne S.A.S — Soluciones Odoo para Colombia*
