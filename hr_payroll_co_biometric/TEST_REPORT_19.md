# Pruebas funcionales de biométricos — Odoo 19

Fecha: 24 de septiembre de 2026 (Colombia).
Origen: Gallium 17. Destino: `develop_geoflora` 19.
Base aislada: `biometric_migration19_check_20260924`.

**Resultado: 62 pruebas ejecutadas, 59 aprobadas y 3 fallidas por problemas de
permisos heredados. No se considera una aprobación completa para producción.**
Las pruebas fallidas permanecen en la suite como reproducciones de los problemas;
no están omitidas ni convertidas en resultados satisfactorios.

## Cobertura ejecutada

| Área | Verificaciones | Resultado |
|---|---|---|
| Instalación y actualización | Dependencias, XML, modelos, restricciones SQL y carga de vistas | Aprobado |
| Dispositivos ZK | Conexión correcta/fallida, desconexión, reloj y zona horaria, reinicio, borrado remoto, crons | Aprobado con dispositivo simulado |
| Descarga | Conversión Bogotá→UTC, ceros iniciales, descarga repetida, lista de dispositivos permitidos, recuperación tras error | Aprobado con dispositivo simulado |
| Usuarios del dispositivo | Mapeo, actualización del ID, carga, borrado, ID faltante, conexión fallida, menú de edición | Aprobado con dispositivo simulado |
| Marcaciones | Importación manual, empleado desconocido, deduplicación, vínculos compartidos y borrado | Aprobado |
| Análisis diario | Primera/última marca, marcas intermedias, consulta no eliminable y sincronización repetida a `hr.attendance` | Aprobado |
| Turnos | Código visible, unicidad, nocturnos, horarios por día, fechas inválidas y duplicidad de asignaciones | Aprobado |
| Programaciones | Confirmación, procesamiento, finalización, cancelación, regreso a borrador y acciones de consulta | Aprobado |
| Generación masiva | Turno general y por empleado, repetición, exclusión de domingos/festivos | Aprobado |
| Asistencias | Ausencia total/parcial, una sola marca, tardanza menor/mayor, salida anticipada y correcciones | Aprobado |
| Horas adicionales | HED/HEN, RN, dominical, separación diurna/nocturna, tolerancias y alertas diarias/semanales | Aprobado según configuración de prueba |
| Nómina | Contrato activo, salario histórico, variable económica, cantidad/factor/valor de `hr.overtime`, aprobación y aplicación | Aprobado |
| Novedades | Revisión, rechazo, aplicación individual/masiva, bloqueo después de aplicar y reprocesamiento sin duplicación | Aprobado |
| Crons de turnos | Procesamiento del día anterior | Aprobado |
| Excel | Plantilla, programación nueva/existente, fechas, filas erróneas, archivo inválido y duplicados internos/reimportación | Aprobado |
| Reportes | Filtros, filtro sin coincidencias, datos/totales, archivo XLSX, QWeb y PDF real generado por wkhtmltopdf | Aprobado funcionalmente; ver límite visual |
| Documentación | Conversión Markdown y peticiones HTTP autorizada, sin rol y anónima | Aprobado |
| Roles | Matriz de creación por rol, lectura/escritura e importación | ACL básicas aprobadas; tres fallos de autorización pendientes |
| Ciclo rotativo y alargue | Persistencia de parámetros | Aprobado únicamente como configuración; ver limitación |

## Fallos de permisos pendientes

1. **Alto: borrado global por un usuario interno.**
   `biometric.device.details.action_clear_attendance_odoo()` ejecuta SQL sin
   comprobar rol administrador ni limitar compañía/dispositivo. Un usuario
   `base.group_user` puede borrar los registros de `zk.machine.attendance`,
   `biometric.raw.punch` y `hr.attendance`.
   Reproducción: `test_known_issue_internal_user_can_clear_all_attendance`.
2. **Alto: lectura de asistencias ajenas.**
   El rol Usuario tiene ACL de lectura, pero no reglas de registros que limiten
   la consulta a su empleado, pese a la descripción del grupo en seguridad.
   Reproducción: `test_known_issue_employee_role_reads_other_employee_attendance`.
3. **Alto: supervisor puede aprobar novedades de RR. HH.**
   El permiso de escritura del supervisor permite invocar `action_approve()`;
   el método no exige el rol de RR. HH. Este resultado no equivale a probar
   que pueda completar la liquidación o aplicación a nómina con ese rol.
   Reproducción: `test_known_issue_supervisor_can_approve_hr_novelties`.

Estos hallazgos no se resolvieron cambiando la política de roles durante la
prueba. La suite conserva sus aserciones de denegación y reporta los tres fallos.
Las eliminaciones de prueba se ejecutaron únicamente sobre datos ficticios de
la base aislada y dentro de transacciones revertidas.

## Correcciones realizadas a partir de las pruebas

- Filtros vacíos de reportes: ya no devuelven empleados ajenos al filtro.
- Importación Excel: omite duplicados dentro del mismo archivo y conserva la
  referencia exacta de la programación recién creada al abrir el resultado.
- Importador biométrico: puede resolver el ID del empleado sin concederle
  acceso general a campos privados de RR. HH.
- Conexión de prueba: cierra la conexión al dispositivo.
- Descarga y lectura de usuarios: vuelve a habilitar el dispositivo y desconecta
  también cuando falla la lectura.
- Nombre visible de turnos: usa `_compute_display_name` y conserva el código.
- Reporte QWeb: define el documento por iteración y obtiene la función de
  formato horario desde los datos del reporte; se genera un PDF real.
- Menú de edición biométrica: ACL faltante del asistente.
- Novedades: reprocesar no vuelve a crear novedades ya revisadas/aprobadas/aplicadas.
- Tolerancia de la compañía: se utiliza el mínimo configurado, antes ignorado.
  Se mantiene la tolerancia propia del turno; el mínimo de compañía es inclusivo.
- Tolerancia de entrada/salida igual a cero: ya no se convierte implícitamente en cinco minutos.
- Aplicación a nómina: rechaza factores no positivos, además de factores en
  formato porcentual que ya rechazaba el módulo.

## Decisión sobre descansos

Por instrucción del usuario se conserva el comportamiento de Gallium:
`effective_hours` descuenta el descanso, mientras las horas de asistencia y el
recargo nocturno usan el intervalo completo entre entrada y salida. Ejemplo
probado: turno 22:00–06:00 con descanso de 0,5 horas → 7,5 horas efectivas del
turno y 8 horas nocturnas biométricas. No se cambió esta regla de negocio.

## Límites y funcionalidades no implementadas en el origen

- No se conectó un ZK físico: no se verificaron red, firmware, protocolo en un
  equipo real ni comandos efectivos de reloj, reinicio o borrado del dispositivo.
- Las llamadas `commit()` del conector se neutralizan en las pruebas para
  permitir rollback. No se probó concurrencia entre procesos/crons reales.
- El PDF se generó y su QWeb contiene el empleado esperado. wkhtmltopdf emitió
  `ConnectionRefusedError` al solicitar recursos del servidor configurado;
  no se afirma validación visual de fuentes, estilos o paginación.
- Las vistas se compilaron en servidor. No se realizó navegación visual en un
  navegador ni arrastre de bloques Gantt.
- El ciclo rotativo de 21 días y los alargues tienen campos/vistas, pero no se
  encontró lógica que use esos parámetros para alternar automáticamente turnos
  o extender horarios. La generación existente aplica el turno seleccionado.
- Se probó la creación y valoración de `hr.overtime`, no una liquidación completa,
  contabilización ni nómina electrónica. Los factores usados son datos de prueba,
  no una certificación de cumplimiento normativo.
- Persisten advertencias de la nómina base sobre empleados/tipos de contrato
  iniciales incompletos y APIs antiguas; no se modificaron registros reales.

## Reproducción

Desde `/home/jcerquera/desarrollo`, con PostgreSQL y los requisitos instalados:

```bash
venv/bin/python odoo/odoo-bin -c odoo.conf \
  -d biometric_migration19_check_20260924 \
  --addons-path=odoo/addons,enterprise,develop_geoflora \
  -u hr_zk_attendance,hr_payroll_co_biometric \
  --stop-after-init --http-interface=127.0.0.1 --http-port=18079 \
  --max-cron-threads=0 --test-enable \
  --test-tags=/hr_payroll_co_biometric \
  --logfile=/tmp/biometric_full_functional_final.log
```

El proceso devuelve código distinto de cero mientras existan los tres fallos
reproducidos de autorización. Usar exclusivamente una base de pruebas.
