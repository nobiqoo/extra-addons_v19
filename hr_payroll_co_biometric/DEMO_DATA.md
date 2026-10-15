# Datos de demostración cargados

Base: `biometric_migration19_check_20260924`.
Compañía: `My Company`.
Programación: **DEMO BIOMETRICO - Escenarios 24 al 27 septiembre 2026** (ID 21).

Datos persistentes creados mediante el ORM de Odoo:

- 10 empleados identificados con el prefijo `DEMO BIOMETRICO`.
- 10 contratos activos con histórico salarial ficticio de 2.400.000.
- 1 dispositivo ficticio, IP documental `192.0.2.10`, zona `America/Bogota`.
- 2 turnos: `DEMODIA` (08:00–16:00), `DEMONOC` (22:00–06:00).
- 10 asignaciones, 17 marcaciones crudas y 17 procesadas.
- 10 registros de asistencia y 10 novedades.
- 1 hora extra de nómina: 2 horas HED, valor de ejemplo 25.000.

Escenarios: asistencia normal, tardanza de 15/45 minutos, salida anticipada,
falta de salida, ausencia, extra diurna aplicada, nocturno en revisión,
extra diurna/nocturna en borrador y dominical aprobado.

Consultar en Control de Turnos → Programaciones / Registros de Asistencia /
Novedades, filtrando las fechas **24–27 de septiembre de 2026**.
Los descansos conservan el cálculo de Gallium.

Los cuatro crons biométricos de esta base se desactivaron para mantener el
escenario estable y evitar conexiones al dispositivo ficticio.

El script `scripts/seed_test_data.py` solo admite esta base, realiza un único
commit al terminar y guarda un marcador para evitar duplicar la carga.
Los importes, factores y horas mensuales son datos ficticios de demostración.

La base ahora contiene datos persistentes: para repetir la suite de regresión,
usar una base limpia o restaurar el estado previo a esta carga; las pruebas
crean sus propias categorías y variables económicas.
