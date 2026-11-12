# Gestión Educativa — Centro Colombo Americano

## Qué es este documento

Explica, a nivel funcional (sin código), todo lo que se agregó o cambió en el módulo académico. Está pensado para que un consultor, tester o el propio cliente pueda seguir el flujo completo del proceso — Solicitud → Validación de duplicados → Inscripción → Estudiante → Clase Ofertada — y entender qué hace cada campo o pantalla nueva, sin ambigüedad.

Cubre, hasta ahora, **9 de las 10 subtareas** en las que se dividió el requerimiento general del Centro Colombo Americano:

1. **Creación, ajuste y parametrización de campos para la gestión académica.**
2. **Validación de duplicados de estudiante y contacto** (sección 3 de este documento).
3. **Gestión de la vista lista de Clases ofertadas y creación masiva** (sección 9 de este documento).
4. **Validación de cruces de Asignatura/Docente/Salón/Horario** (sección 10 de este documento).
5. **Estados académicos del estudiante** (sección 11 de este documento).
6. **Resultado académico, Promoción y Finalización** (sección 12 de este documento).
7. **Ajuste de la pestaña Inscripciones en la ficha del Estudiante** (sección 12.7 de este documento) — ya cubierta por el trabajo de la subtarea 6, sin desarrollo adicional.
8. **Estructura de calificación avanzada** (sección 14 de este documento): escala de calificación propia de la operación académica de Inglés, con componentes y ponderaciones por corte, Class Performance cualitativo, horas de ausencia, Consolidado de notas, confirmación/bloqueo/publicación en portal y reportes Midterm/Final/Class List.

**No incluye** (son subtareas aparte, ya identificadas pero no desarrolladas todavía):

- Lógica real de bloqueo/advertencia cuando un estudiante está restringido.
- Cálculo real de calificaciones, promedios, ponderaciones o ranking **para escalas que no usen la estructura avanzada** (sección 14). Una escala estándar (sin esa estructura) sigue sin calcular nada: el indicador mínimo "¿Aprueba?" de la sección 12 sigue siendo, para esas escalas, la única fuente del Resultado académico.
- Reglas de negocio adicionales que se disparen automáticamente al activar/inactivar una Clase ofertada o una Asignatura del nivel, más allá de dejar de poder seleccionarse para cosas nuevas (ver sección 9) y del cambio de Estado académico (ver sección 11).
- Facturación o venta automática del libro.
- Cualquier automatización contable real (reclasificación, movimientos, cartera, facturas, notas crédito) derivada de un aplazamiento — solo se crea una actividad pendiente; la gestión la hace el cliente manualmente (ver sección 11).
- La lógica de "ocultar calificaciones" para clases/estudiantes **sin** estructura avanzada aplicada: esos dos checks siguen siendo un interruptor sin efecto. Con estructura avanzada, sí tienen efecto real (ver sección 14.8).
- ~~Generación de certificados para estudiantes Finalizados~~ — construido en la tarea 12451 (sección 21): wizard de Certificados académicos en Gestión Educativa → Informes.

Todo lo de esta lista existe como campo o pantalla preparada, pero **sin comportamiento automático** — eso se construirá en su propia subtarea.

---

## Antes de probar: qué debe existir en la base de datos

El módulo no trae catálogos de ejemplo. Antes de poder crear una Solicitud hace falta tener configurado, al menos una vez:

| Dónde | Qué |
|---|---|
| Gestión Educativa → Clases → **Grados** | Un Grado (nivel académico), con una Escala de calificación y al menos una Sección |
| Gestión Educativa → Configuración → Académicos → **Sesiones** / **Años académicos** | Una Sesión y un Año académico (con al menos un Periodo) |
| Gestión Educativa → Clases → **Materias** | Una Materia asociada al Grado |
| Empleados | Al menos un empleado marcado como "Es docente" |
| Gestión Educativa → Configuración → Académicos → **Tipos de programa** | Uno o más tipos (ej. "Inglés", "Técnico") — catálogo nuevo de esta tarea, ver más abajo |
| Configuración → **Elementos de tarifa** / **Estructuras de tarifas** | Una estructura de tarifas para el Grado, si se va a probar la Inscripción hasta el final |

Si tu base ya tiene datos reales de la institución, probablemente todo esto ya existe y puedes saltar directo al flujo.

---

## 1. Catálogo "Tipo de programa"

**Dónde:** Gestión Educativa → Configuración → Académicos → **Tipos de programa**.

Es un catálogo simple (nombre + activo/inactivo), administrable sin necesidad de programación. Un Tipo de programa desactivado deja de aparecer para nuevas selecciones, pero **no afecta** las solicitudes o estudiantes que ya lo tengan asignado.

- **Quién puede crear/editar/desactivar:** solo el grupo **Officer** o **Admin**.
- **Quién puede solo consultarlo (para seleccionarlo en una solicitud):** también **Staff** (docentes).
- Elegir un Tipo de programa **no activa ningún comportamiento automático** — es un dato puramente descriptivo, tal como lo pide el requerimiento.

---

## 2. La Solicitud (Aplicación)

**Dónde:** Gestión Educativa → Aplicaciones → Nuevo.

### 2.1. Bloque general del formulario

| Campo | Tipo | Obligatorio |
|---|---|---|
| Tipo de programa | Catálogo de arriba | **Sí** |
| Sede | Catálogo configurable (ver nota abajo) | **Sí** |
| Tipo / Número de identificación | Los mismos de Contactos | Sí (ya lo era) |
| Fecha de nacimiento | Fecha | **Sí** |
| Edad | Se calcula sola a partir de la fecha de nacimiento | — (solo lectura) |
| Tipo de persona | Persona natural / Persona jurídica / Natural comerciante / Código interno | No |
| Estado civil | Soltero(a) / Casado(a) / Unión libre / Divorciado(a) / Viudo(a) | No |
| Nivel de formación | Ninguno → Doctorado | No |
| Ocupación actual | Estudiante / Empleado / Independiente / Desempleado / Hogar / Pensionado / Otro | No |
| Idioma nativo | Español / Inglés / Francés / Otro (con campo de texto libre si es "Otro") | No |
| Municipio de expedición del documento | Ciudad (catálogo DIAN) | No |
| Municipio / lugar de origen | Ciudad (catálogo DIAN) | No |
| Código DIAN lugar de origen | Solo lectura — se llena solo con el código DIAN del municipio elegido arriba | — (solo lectura) |
| Estrato | 1 a 6 | No |
| Jornada | Catálogo configurable (ver nota abajo) — semilla: Diurna / Nocturna / Fin de semana | No |
| Régimen de salud | Catálogo configurable (ver nota abajo) — semilla: SISBEN (niveles/rangos) y EPS, 44 opciones con sus códigos oficiales | No |

> **Nota sobre "Sede":** es un catálogo configurable propio (Gestión Educativa → Configuración → Académicos → **Sedes**, entre Ubicaciones y Franjas horarias), con dos registros semilla editables ("Norte" y "Centro") — administrable sin programación, igual que Tipo de programa y Modalidad. En una primera versión se había reutilizado el campo de Compañía de Odoo para esto, pero se revirtió: usar la Compañía real traía implicaciones de multi-compañía (contabilidad, almacenes, reglas de registro) que no aplican a un dato puramente descriptivo. El campo `company_id` sigue existiendo donde Odoo lo exige, pero ya no se le muestra al usuario como "Sede". Sede también aparece como campo en **Ubicaciones** y **Franjas horarias** (sección 9.6/9.7), para poder clasificar cada Salón/Franja por la sede a la que pertenece.

> **Nota sobre "Jornada" y "Régimen de salud":** son catálogos configurables propios (Gestión Educativa → Configuración → Académicos → **Jornadas** / **Regímenes de salud**, junto a Tipo de programa y Modalidad) — se puede agregar, editar o archivar opciones sin programación. "Régimen de salud" trae de semilla las 44 opciones oficiales (SISBEN + EPS) con su código tal como lo entrega la entidad; "Jornada" trae Diurna/Nocturna/Fin de semana. Ambos catálogos solo son administrables por Officer/Admin (Staff los puede ver y elegir, no crear/editar).

### 2.2. Pestaña **Ubicación**

Barrio/corregimiento (obligatorio), Dirección (obligatoria), Dirección 2, País, Departamento/Estado, Ciudad (catálogo DIAN), Código postal.

### 2.3. Pestaña **Contacto**

Celular del estudiante (obligatorio), Teléfono fijo, Teléfono adicional, Celular adicional, Correo electrónico (obligatorio), Correo electrónico DIAN (independiente del principal — se usa para facturación electrónica), Preferencia de contacto.

### 2.4. Pestaña **Acudiente**

Aquí sigue estando la información de Padre/Madre que ya traía el formulario base, y además se agregó una **lista** donde se pueden registrar uno o varios acudientes (no solo padre/madre): Nombre completo, Teléfono fijo, Celular, Parentesco (con "¿Cuál parentesco?" si se elige "Otro"), Correo electrónico. Se agregan filas con el botón "Agregar una línea".

### 2.5. Pestaña **Comentarios**

Un campo de texto libre para observaciones sobre el proceso de inscripción. **Este comentario se convierte automáticamente en la primera entrada del histórico de Observaciones del estudiante**, pero no de inmediato — ver la explicación en la sección de Observaciones más abajo.

### 2.6. Validaciones al Confirmar / Inscribir

Antes de poder confirmar la solicitud o inscribir al estudiante, el sistema exige: Primer nombre, Primer apellido, Tipo y Número de identificación, y Fecha de nacimiento. El Segundo nombre y Segundo apellido pueden quedar vacíos.

---

## 3. Validación de duplicados — antes de crear o vincular

Esta pantalla aparece **automáticamente**, antes que cualquier otra cosa, en el mismo momento en que se hace clic en **"Inscribir ahora"** desde la Solicitud. No es un paso que el usuario tenga que activar.

### 3.1. Cuándo aparece

El sistema busca, entre los Estudiantes y Contactos ya registrados (incluidos los archivados), a quién se parezca la persona de la Solicitud, usando **4 criterios independientes**:

| Criterio | Cómo se evalúa |
|---|---|
| **Nombre** | Se compara por palabras (sin tildes, sin mayúsculas, sin conectores como "de"/"la"/"y"): coincide si comparten al menos 2 palabras, o si un nombre más corto está contenido en uno más largo. |
| **Fecha de nacimiento** | Coincidencia exacta. |
| **Identificación** | Coincidencia exacta de Tipo **y** Número de documento. |
| **Nivel académico** | El Grado de la Solicitud coincide con el nivel actual del candidato, o con el de cualquiera de sus inscripciones anteriores. |

Un candidato solo se muestra si coincide en **2 o más** de esos 4 criterios — un solo dato en común (por ejemplo, solo el nombre) **no** se considera una posible coincidencia y no interrumpe el flujo. Si nadie supera ese umbral, el asistente pasa directo a la pantalla normal de inscripción, sin ningún paso adicional.

### 3.2. La pantalla de posibles coincidencias

Cuando sí hay candidatos, el asistente muestra una tabla en vez del formulario de inscripción habitual, con: Nombre completo, Fecha de nacimiento, Tipo/Número de identificación, Nivel académico, Correo, Celular, Estado (Activo / Archivado / estado de su inscripción actual), y en qué criterios coincidió cada fila.

- **Botón "Usar este registro"** (en cada fila): cierra la búsqueda y continúa la inscripción normal ya vinculada a ese estudiante (o a ese contacto, si es una fila del tipo "Contacto existente, sin estudiante" — ver 3.4). Disponible para **todos** los perfiles.
- **Botón "Ninguna coincidencia, crear nuevo"**: descarta todas las filas mostradas y continúa creando un estudiante nuevo. Visible **solo para Officer o Admin** — Staff puede revisar la tabla y elegir un registro existente, pero no puede decidir por su cuenta que ninguna coincidencia aplica; en ese caso necesita que un Officer/Admin lo confirme.

### 3.3. Esto no reemplaza el bloqueo por identificación exacta

Aunque un Officer/Admin elija "crear nuevo", si el Tipo+Número de identificación coincide **exactamente** con un estudiante ya activo, el sistema sigue bloqueando la creación (regla ya existente, ver sección 4) — la pantalla de coincidencias es una revisión humana previa, no un permiso para saltarse esa validación dura.

### 3.4. Caso especial: existe el Contacto pero no el Estudiante

Si la identificación coincide con un **Contacto** (`res.partner`) que todavía no tiene un Estudiante asociado, aparece como una fila más en la misma tabla. Al usar "Usar este registro" en esa fila, el Estudiante que se crea queda **vinculado a ese Contacto ya existente** en vez de crear uno nuevo — evita duplicar el contacto (con su historial, facturación, etc.) aunque el Estudiante en sí sea nuevo.

---

## 4. Inscribir: crear estudiante nuevo o vincular uno existente

Botón **"Inscribir ahora"** en la Solicitud confirmada → se abre un asistente con dos opciones:

### Opción A — Crear un estudiante nuevo

Se crea el registro de Estudiante y se abre (sin guardar todavía) el formulario de Inscripción, pre-cargado con los datos básicos. **Hay que guardar ese formulario de Inscripción** — es en ese momento, no antes, cuando:
- Todos los campos nuevos de la Solicitud (Tipo de programa, municipios, tipo de persona, contacto, Estrato, Jornada, Régimen de salud, etc.) se copian al Estudiante.
- Los acudientes cargados en la Solicitud aparecen también en el Estudiante (es el mismo registro, no una copia).
- Si la Solicitud tenía un comentario, se convierte en la primera Observación del Estudiante.

### Opción B — Vincular a un estudiante que ya existe

Mismo comportamiento, con una diferencia importante: **solo se completan los campos que el estudiante todavía tenía vacíos**. Si el estudiante ya tenía, por ejemplo, el Estado civil diligenciado, ese dato **no se sobrescribe** con lo de la nueva solicitud — se respeta la información que el estudiante ya tenía. Los acudientes de la nueva solicitud sí se agregan siempre.

---

## 5. La ficha del Estudiante

**Dónde:** Gestión Educativa → Estudiantes.

### 5.1. Encabezado general

Todos los campos de la Solicitud llegan aquí (persistencia). Además:

- **Contacto del estudiante**: estos mismos campos (estado civil, nivel de formación, idioma nativo, municipio de expedición/origen, teléfono fijo, barrio, tipo de persona, ocupación actual, estrato, jornada, régimen de salud, etc.), más los Nombres/Apellidos separados, también se sincronizan automáticamente hacia el **Contacto** (ficha de Contactos) del estudiante, no solo hacia esta ficha — si se editan aquí después de inscribir, el Contacto se actualiza solo.
- **Edad**: calculada, se actualiza sola.
- **Estudiante con restricción**: check, visible **solo para Officer/Admin**. Staff no lo ve en absoluto (no es que aparezca deshabilitado: directamente no está en su pantalla).
- **Ocultar calificaciones al estudiante**: interruptor visible para todos, sin ningún efecto todavía (ver aclaración al inicio del documento).

### 5.2. Pestaña **Información del acudiente**

Contiene dos cosas:
1. El bloque de información de Padre/Madre que el formulario base ya traía (se movió aquí desde el cuerpo principal).
2. La lista de Acudientes registrados (heredada de la Solicitud, o agregable directamente aquí).

### 5.3. Pestaña **Disciplina** (solo Officer/Admin)

Tiene dos partes, separadas por una línea divisoria, que **no son lo mismo**:

1. **Motivo / observación de la restricción** — el campo de texto asociado al check "Estudiante con restricción" del encabezado.
2. **Histórico de disciplina** — una tabla de solo lectura con los incidentes disciplinarios reales (`wk.student.discipline`, ya existente en el módulo base), registrados normalmente desde cada Inscripción. Aquí se agregan automáticamente los de **todas** las inscripciones del estudiante. Si está vacía, es porque no se ha registrado ningún incidente — no es un error.

### 5.4. Pestaña **Observaciones**

Tabla de solo lectura con **todas** las observaciones del estudiante, sin importar de qué Inscripción o Clase vinieron (ver sección 7).

---

## 6. La Inscripción

**Dónde:** Gestión Educativa → Inscripciones (o desde el botón "Inscribir ahora" de la Solicitud).

- **Libro**: se puede elegir manualmente, o se propone solo si la Clase Ofertada correspondiente a ese Grado/Sección ya tiene un libro asignado.
- **¿Examen de clasificación?**: check que, al activarse, muestra el campo **Resultado examen de clasificación** (texto libre).
- **Pestaña Observaciones**: ver sección 7.
- **Botón "Histórico"** (arriba a la derecha, junto a los demás botones inteligentes): solo aparece si el estudiante tiene **otras** Inscripciones — es decir, es un estudiante antiguo. Al hacer clic, abre la lista de esas Inscripciones anteriores sin salir de esta pantalla. Este botón vive únicamente aquí, en la Inscripción — no en la Solicitud/Aplicación.

---

## 7. Histórico de Observaciones — cómo funciona (importante)

Esta es la parte más fácil de malinterpretar, así que se explica con detalle.

### Regla central: toda observación pertenece a una Inscripción

No existe el concepto de "observación suelta" del estudiante. **Cada observación, sin importar de dónde se haya originado, queda ligada a una Inscripción concreta.** Esto significa:

- Si un estudiante tiene varias inscripciones a lo largo del tiempo, las observaciones de cada una se ven en la pestaña Observaciones de **esa** inscripción.
- La ficha del Estudiante (sección 5.4) junta las observaciones de **todas** sus inscripciones en una sola tabla, pero de solo lectura — para editar o agregar una observación hay que hacerlo desde la Inscripción, la Clase Ofertada, o el listado de auditoría (ver más abajo), no desde el Estudiante.

### Dónde se puede crear una observación

| Pantalla | Cómo se autocompleta | Qué elige el usuario |
|---|---|---|
| **Inscripción → pestaña Observaciones** | Origen = "Inscripción", queda ligada a esta misma inscripción | Tipo, Comentario, y (si aplica) la Factura relacionada |
| **Clase Ofertada → pestaña Observaciones** | Origen = "Clase" | El docente elige **a qué Inscripción** corresponde (el desplegable ya viene filtrado al Grado de esa clase), Tipo, Comentario |
| **Estudiantes → Observaciones** (menú aparte, solo Officer/Admin) | Nada se autocompleta | Todo: la Inscripción, el Origen, el Tipo, la Factura si aplica, el Comentario |
| **Pestaña Comentarios de la Solicitud** | Se convierte sola en una observación con Origen = "Comentario adicional", en el momento en que se guarda la primera Inscripción del estudiante (no antes — en ese momento todavía no existe ninguna inscripción a la cual ligarla) | Nada, es automático |

El sistema **nunca pide manualmente** el Origen o la Referencia cuando ya se pueden deducir del contexto (tal como exige el requerimiento) — por eso en Inscripción y Clase Ofertada esos datos no aparecen como algo que hay que llenar a mano.

### Cada observación guarda

- **Fecha y hora de registro** (automático).
- **Tipo** — categoría de negocio de la nota (Clase / Pago-Factura / Administrativo / Disciplina / Comentario general). *Los valores exactos de esta lista son una propuesta inicial; si el negocio quiere otra taxonomía, es un ajuste de una línea.*
- **Origen** — de qué proceso técnico vino (Inscripción / Clase / Facturación / Gestión administrativa / Comentario adicional). Es distinto de "Tipo": Origen es automático y técnico, Tipo es una clasificación de negocio que el usuario puede ajustar.
- **Referencia** — se calcula sola: muestra el nombre de la Clase si la observación viene de una clase, o el número de la Inscripción en cualquier otro caso.
- **Factura relacionada** — solo aparece/aplica cuando el Origen es "Facturación".
- **Usuario que registró** — automático.
- **Comentario** — el texto de la observación.

### Nada se reemplaza

Cada observación nueva es un registro independiente. El histórico nunca se sobrescribe ni se edita retroactivamente al agregar una nueva entrada.

### Auditoría cruzada

**Estudiantes → Observaciones** (solo visible para Officer/Admin) es un listado de **todas** las observaciones de **todos** los estudiantes, con filtros por estudiante, inscripción, origen y tipo. Sirve para revisar el histórico completo sin tener que entrar estudiante por estudiante. Staff no ve este menú, pero sí puede crear/consultar observaciones de sus propios estudiantes desde la Inscripción o la Clase.

---

## 8. Clases Ofertadas

**Dónde:** Gestión Educativa → Clases → Poblar Clases.

### 8.1. Formulario

- **Clase activa**: interruptor visual arriba a la derecha del título. **Es independiente del Estado** (Nuevo / Confirmado / Terminado) que ya traía el módulo base — una clase puede estar "Confirmada" y a la vez "inactiva", o viceversa. También se puede cambiar directamente desde la vista lista, sin entrar al formulario (ver sección 9.2). No tiene ningún efecto automático todavía (las reglas de negocio reales que dependan de este estado son otra subtarea).
- **Modalidad**: catálogo configurable (Configuración → Académicos → **Modalidades**, sección 9.5) — ya no es una lista fija en código.
- **Assistant Teacher / Docente asistente**: es el mismo campo "Profesores de Secundaria" que el módulo ya traía, pero que una personalización anterior había ocultado. Ahora vuelve a ser visible, con este nuevo nombre. Permite seleccionar uno o varios docentes asistentes.
- **Libro**: selector de Producto (solo ofrece los marcados como "¿Es libro?" en Ventas → Productos — ver 9.6), no el catálogo bibliotecario que trae el módulo base (no usado por la institución).
- **Examen de clasificación**: check junto a "Escala de calificación (avanzada)". Marca esta Clase ofertada como el examen de clasificación — ver sección 14.9.
- **Horario** y **Salón**: resúmenes de solo lectura, calculados a partir de las líneas cargadas en la pestaña "Horario semanal" — no hay que diligenciarlos aparte.
- **Fecha de inicio / Fecha de finalización**: mismos campos de siempre, solo se corrigió su nombre (antes decían, por una mala traducción de Odoo, "Empezar desde" / "Terminar hasta").
- **Sede**: catálogo configurable (sección 9.7), ya no es la Compañía.

### 8.2. Pestaña Observaciones

Ver sección 7 — aquí es donde se registran las notas "durante la clase".

### 8.3. Lista de Clases Ofertadas

Orden y columnas visibles por defecto: Fecha de inicio, Clase ofertada, Sede, Nivel académico, Horario, Salón, Fecha de finalización, Docente, Cupo, Total matriculados, Clase activa. Columnas activables (botón de engranaje al final de la tabla): Sección, Sesión, Materia, Assistant Teacher, Libro, Modalidad, **Estado** (visible por defecto antes, ahora opcional — sigue disponible con un clic, nada se eliminó).

---

## 9. Gestión de la vista lista de Clases ofertadas y creación masiva

### 9.1. Asignatura del nivel — activar/inactivar (requerimiento 2.1)

**Dónde:** Gestión Educativa → Configuración → Académicos → **Asignaturas**.

Cada Asignatura del nivel tiene un check **Activa**, editable con un clic directamente desde la lista (igual que "Clase activa" en Clases Ofertadas). Al desactivarla:

- **Deja de aparecer** como opción al elegir la Asignatura/Módulo de una Clase ofertada nueva (tanto en el formulario individual como en el asistente de creación masiva, sección 9.4).
- **No afecta** las Clases ofertadas que ya la tenían asignada: siguen intactas, con su Asignatura visible normalmente.
- **No se oculta de las búsquedas ni se archiva**: sigue apareciendo en listados, reportes e histórico, tal como exige el requerimiento ("debe conservarse para consulta histórica"). Es un campo propio (no el campo "Activo" que Odoo usa para archivar registros), justamente para evitar ese efecto.

Filtros rápidos disponibles: "Activas" / "Inactivas".

### 9.2. Clase activa — edición desde la lista (requerimiento 2.3)

En la lista de Clases Ofertadas, la columna **Clase activa** es un interruptor: un clic la cambia, sin necesidad de abrir el formulario de la clase. Inactivar una clase **no borra ni modifica** sus inscripciones, estudiantes, asistencias, calificaciones ni observaciones — solo cambia ese indicador (ver también 8.1).

Una Clase ofertada inactiva **deja de poder elegirse para cosas nuevas**: al registrar una Observación nueva (desde el menú de auditoría o cualquier otra pantalla donde se elige la clase manualmente), el selector de Clase solo muestra las activas. Una Observación **ya registrada** contra una clase que después se inactiva conserva esa clase sin ningún problema — el filtro solo aplica a selecciones nuevas, nunca borra ni oculta lo ya guardado.

### 9.3. Búsqueda, filtros y agrupaciones (requerimiento 2.4)

Desde el buscador de Clases Ofertadas:

- **Filtros rápidos**: Nuevo / Confirmado / Terminado (ya existían), más **Activas** / **Inactivas** (nuevos).
- **Agrupar por**: Materia, Nivel académico, Sesión, Docente (ya existían), más **Modalidad**, **Clase activa**, **Sede** y **Periodo académico** (nuevos).
- **Buscar por texto**: además del nombre, la materia y el nivel, ahora también busca coincidencias en el Horario y el Salón resumidos.
- **Acciones masivas**: seleccionando varias filas con el check de la izquierda, aparecen los botones **"Activar seleccionadas"** / **"Inactivar seleccionadas"** en la barra superior — cambian el estado de todas las clases seleccionadas de una vez, visibles solo para Officer/Admin.

### 9.4. Creación masiva de Clases ofertadas (requerimientos 2.5-2.9)

**Dónde:** Gestión Educativa → Clases → **Programación masiva** (junto a "Poblar Clases", visible solo para Officer/Admin).

Abre un asistente con dos partes:

1. **Datos generales** (aplican a todas las clases que se van a crear en este proceso): Programación académica (Año académico), Modalidad (catálogo configurable, sección 9.5), Sede, Periodo académico (Término).
2. **Clases a crear**: una tabla donde se agrega una línea por cada Clase ofertada que se quiere crear, con botón **"Agregar una línea"**. Cada línea tiene: Nivel, Módulo (filtrado al Nivel elegido y a las Asignaturas activas — ver 9.1), Docente principal, Docente asistente, **Día**, Horario, Salón, Cupo, Fecha de inicio, Fecha de finalización (precargadas con las del Periodo académico elegido, pero editables por línea), Libro (texto libre), **Escala de calificación (avanzada)** (opcional, por línea — si se elige, se aplica automáticamente a la clase recién creada, igual que el botón "Aplicar estructura de calificación" del formulario individual, sección 14.6), y un interruptor **Activa**.

   > Día, Horario y Salón de cada línea **sí se guardan como el Horario semanal real** de la clase que se crea (ver sección 10) — dejaron de ser solo de referencia en la subtarea de Validación de cruces, precisamente para poder detectar cruces reales antes de confirmar la creación masiva.

Al presionar **"Crear clases"**:

- El sistema valida **todas** las líneas antes de crear nada: cupo mayor a 0, fecha de inicio no posterior a la de finalización, campos obligatorios completos, y que ninguna línea se cruce en Docente o Salón —ni con otra línea del mismo proceso, ni con una Clase ofertada ya existente— (ver sección 10). Si algo falla, se muestra el mensaje identificando exactamente cuál línea y por qué, y **no se crea ningún registro** — se corrige y se vuelve a intentar.
- Si todo es válido, se crea **una Clase ofertada independiente por cada línea** (nunca un único registro que las agrupe), cada una con los datos generales del proceso, los propios de su línea, y su línea real de Horario semanal ya cargada — misma estructura que una clase creada individualmente.
- Al terminar, se abre la lista de Clases Ofertadas mostrando únicamente las recién creadas.

El formulario individual de creación (botón "Nuevo" en Poblar Clases) **sigue disponible sin cambios**, para cuando solo se necesita crear una clase.

### 9.5. Catálogo "Modalidad"

**Dónde:** Gestión Educativa → Configuración → Académicos → **Modalidades**.

Igual que "Tipo de programa" (sección 1): catálogo simple (nombre, orden, activo/inactivo), administrable sin programación. Reemplaza la lista fija que traía el código (Sabatino / Diario / Vacacional, que siguen existiendo como registros iniciales editables) para que la institución pueda agregar modalidades propias (p. ej. Híbrido, Presencial) sin necesidad de un desarrollo nuevo. Se usa tanto en la Clase ofertada y el asistente de creación masiva como en la Escala de calificación avanzada (sección 14.1). Desactivar una modalidad no afecta las Clases/Escalas que ya la tengan asignada.

- **Quién puede crear/editar/desactivar:** solo **Officer** o **Admin**.
- **Quién puede solo consultarla (para seleccionarla):** también **Staff**.

### 9.6. Marcar un Producto como "Libro"

**Dónde:** Ventas → Productos → (abrir el producto) → check **¿Es libro?**, junto a "Is Fee Element?"/"Is Library Element?".

El selector **Libro** de la Clase ofertada, la Inscripción y el asistente de creación masiva solo ofrece los productos con este check activo — así no aparecen mezclados certificados, exámenes ni otros productos de venta. Un producto sin el check simplemente no aparece en ese selector; no hace falta nada más para "convertirlo" en libro, basta con marcarlo.

### 9.7. Catálogo "Sede"

**Dónde:** Gestión Educativa → Configuración → Académicos → **Sedes** (entre Ubicaciones y Franjas horarias).

Igual que Tipo de programa y Modalidad: catálogo simple (nombre, orden, activo/inactivo), con dos registros semilla editables ("Norte" y "Centro"). Es el campo **Sede** que aparece en Aplicaciones, Estudiante, Clase ofertada e Inscripción — **ya no es la Compañía** (`company_id`) de Odoo, que sigue existiendo técnicamente pero dejó de mostrarse al usuario como "Sede" (ver nota de la sección 2.1).

Sede también se agregó como campo en:
- **Ubicaciones** (Gestión Educativa → Configuración → Académicos → Ubicaciones de clase): para clasificar cada Salón por la sede a la que pertenece.
- **Franjas horarias** (mismo menú, Franjas horarias): para clasificar cada franja por sede.

- **Quién puede crear/editar/desactivar el catálogo:** solo **Officer** o **Admin**.
- **Quién puede solo consultarlo (para seleccionarlo):** también **Staff**.

---

## 10. Validación de cruces — Docente y Salón

Se dispara **automáticamente**, sin ningún botón ni pantalla aparte, cada vez que se crea o modifica una línea del **Horario semanal** de una Clase ofertada (individual o masiva), o se cambia el **Docente principal** de una clase ya guardada.

### 10.1. Cuándo se considera que hay cruce

Dos Clases ofertadas **activas** entran en conflicto cuando, para la misma línea de Horario semanal:

- comparten el mismo **Día**;
- sus franjas horarias se **superponen** (si una termina exactamente cuando la otra empieza, **no** es cruce); y
- usan el **mismo Docente principal** o el **mismo Salón**.

La misma Asignatura, por sí sola, **nunca** genera un cruce — dos grupos distintos de la misma materia, con Docente y Salón diferentes, pueden coincidir en horario sin problema. El Docente **asistente** tampoco se valida (fuera de alcance).

### 10.2. Qué pasa cuando se detecta un cruce

Se bloquea el guardado (en la clase individual) o la confirmación (en el asistente masivo) con un mensaje que identifica: el tipo de cruce (Docente o Salón), el recurso involucrado, la Clase ofertada con la que choca, el día y el horario en conflicto. Por ejemplo:

> *Cruce de Docente: el docente Abigail Díaz ya se encuentra asignado a otra Clase ofertada (Inglés Básico-Sabatino A) el miércoles de 08:00 AM a 10:00 AM.*

### 10.3. Clases ofertadas inactivas

Una Clase ofertada **inactiva** (ver 8.1/9.2) **nunca bloquea** a otras — su Docente y Salón quedan libres para cualquier otra programación nueva, aunque la clase inactiva conserve su propio horario para consulta histórica.

### 10.4. En el asistente de creación masiva

Antes de crear nada, se valida dos veces: las líneas del propio proceso **entre sí** (dos líneas con mismo Docente o Salón, mismo día y horario superpuesto), y cada línea **contra las Clases ofertadas que ya existen** en la base. Cualquier cruce encontrado bloquea toda la creación hasta corregirlo — ver 9.4.

---

## 11. Estados académicos del estudiante

Cada Estudiante tiene un **Estado académico**, visible como una etiqueta de color en el encabezado del formulario y en la lista: **Nuevo**, **Activado**, **Liberado** o **Aplazado**. Tres de los cuatro cambian **solos**, sin que nadie los toque; el cuarto (Aplazado) es siempre una decisión manual.

### 11.1. Cómo se mueve entre Nuevo, Activado y Liberado (automático)

| Estado | Qué significa | Cuándo se asigna |
|---|---|---|
| **Nuevo** | Ya está inscrito, pero nunca ha estado en una Clase ofertada | Es el estado con el que nace todo Estudiante nuevo. |
| **Activado** | Está relacionado con al menos una Clase ofertada **activa** | Automático en cuanto alguien lo agrega a la pestaña "Enrolled Students" de una Clase ofertada activa — sin importar si antes estaba Nuevo, Liberado o incluso Aplazado. |
| **Liberado** | Estuvo Activado, pero ya no tiene ninguna Clase ofertada activa | Automático al quitarlo de su única Clase activa, o al **inactivar** esa Clase (si todavía le queda otra Clase activa, no cambia — sigue Activado). |

**Nuevo nunca "regresa"**: un estudiante que ya tuvo una primera asignación no vuelve a Nuevo aunque pierda todas sus clases — en ese caso pasa a Liberado, que es justamente la diferencia entre los dos estados (Nuevo = todavía no ha tenido su primera clase; Liberado = ya tuvo una y quedó disponible de nuevo).

**Para reactivar a un estudiante Liberado** (o Aplazado), basta con volver a agregarlo a una Clase ofertada activa — exactamente igual que una primera asignación; no hay ningún botón aparte. Esta acción ya está restringida a Officer/Admin desde la Subtarea de Clases ofertadas (Staff solo tiene lectura sobre las Clases).

### 11.2. Aplazar (manual)

**Dónde:** botón **"Aplazar"** en el encabezado del Estudiante, visible solo para **Officer/Admin**, y oculto si el estudiante ya está Aplazado.

Al presionar el botón se abre una ventana con un campo **Motivo (obligatorio)** y los botones **Confirmar**/**Cancelar** — esa ventana **es** la confirmación; cancelar no cambia nada.

Al confirmar:
- El Estado académico pasa a **Aplazado**.
- Se crea una **actividad pendiente** para el responsable configurado en **Ajustes → Estados académicos → Responsable de reclasificación contable**. Si no hay nadie configurado ahí, la actividad queda asignada a quien confirmó el aplazamiento, con una nota explicándolo.
- **No se ejecuta ningún proceso contable real** (no se generan movimientos, notas crédito, ajustes de cartera ni facturas) — la actividad es solo un recordatorio; la gestión contable la hace el cliente manualmente, fuera de Odoo o en el módulo de Contabilidad, según corresponda.
- La inscripción, las observaciones, el histórico de disciplina y toda la información académica previa **permanecen intactos**.

### 11.3. Histórico de estados

Pestaña **"Histórico de estados"** en el formulario del Estudiante (solo lectura): cada cambio, automático o manual, queda registrado con estado anterior, estado nuevo, **Clase ofertada relacionada**, fecha, usuario responsable, tipo de cambio (Automático/Manual) y motivo (cuando aplica, solo en los aplazamientos).

La Clase ofertada relacionada identifica cuál fue la clase que originó el cambio: en un paso a Activado, la clase a la que se (re)asignó al estudiante; en un paso a Liberado, la clase de la que quedó sin disponibilidad. Esto conserva la referencia a la Clase ofertada anterior aunque el estudiante ya no esté vinculado a ella.

### 11.4. Búsqueda, filtros y agrupación

En la lista de Estudiantes: filtros rápidos por cada estado, y agrupación por "Estado académico" en el buscador.

---

## 12. Resultado académico, Promoción y Finalización

Esta sección cierra el ciclo de vida académico: qué pasa con una Inscripción una vez que sus calificaciones están definidas — si el estudiante continúa a un nivel nuevo (Promoción) o termina su proceso en la institución (Finalización) — y deja trazabilidad completa de cada decisión.

### 12.1. Resultado académico de la Inscripción

Cada Inscripción tiene un campo **Resultado académico**, visible como una etiqueta de color en el formulario, en la lista y en el buscador de Inscripciones (con filtros rápidos y agrupación): **Pendiente**, **Aprobado** o **No aprobado**. Se calcula solo, nunca se escribe a mano:

- **Pendiente**: falta la nota final de al menos una Asignatura de la Inscripción (o todavía no tiene ninguna Asignatura).
- **Aprobado**: todas las Asignaturas tienen nota final y todas aprueban.
- **No aprobado**: todas las Asignaturas tienen nota final, pero al menos una reprueba — una sola Asignatura reprobada impide la promoción del nivel completo.

**De dónde sale "aprueba" o "reprueba":** la Escala de calificación (Configuración → Académicos → Grade Scale) tiene ahora, por cada tramo, un campo **"¿Aprueba?"** (activado por defecto). El Resultado académico de la Inscripción se deriva de ahí: si la nota final de una Asignatura cae en un tramo con "¿Aprueba?" desmarcado, esa Asignatura reprueba. Officer/Admin debe revisar cada Escala en uso y desmarcar el tramo que corresponda a la nota mínima reprobatoria — por defecto todos los tramos aprueban, para no romper las Escalas ya configuradas.

En el Estudiante también se muestra, de solo lectura, el Resultado académico de su Inscripción actual — es un dato que siempre se lee en vivo desde esa Inscripción, nunca un valor propio y guardado del Estudiante.

### 12.2. El "Estado" operativo y el "Estado del programa académico" ya no se muestran

La Inscripción conserva sus campos técnicos `state` (Borrador/En curso/Completada/Promovida/Terminada) y `session_status` (Estado del programa académico), pero dejan de mostrarse en el formulario y en la lista — se confundían con el Resultado académico, que es un concepto distinto. Los botones de acción siguen apareciendo exactamente igual que antes (su visibilidad depende del valor interno de `state`, no de que el campo esté dibujado en pantalla) y los filtros/agrupación por esos campos en el buscador se conservan, como herramientas operativas internas de Officer/Admin.

### 12.3. Promocionar ahora (individual)

**Dónde:** botón **"Promote Now"** en el encabezado de la Inscripción, visible solo cuando está Completada y restringido a **Officer/Admin** (antes no tenía ninguna restricción de perfil).

Antes de abrir el asistente, el sistema valida:
- Si la Inscripción ya fue promovida o finalizada antes: bloquea ("La inscripción seleccionada ya fue procesada previamente.").
- Si el Resultado académico es **No aprobado**: bloquea, identificando al estudiante y al nivel actual.
- Si el Resultado académico es **Pendiente**: bloquea igual, pidiendo completar la evaluación primero.

Si nada de eso bloquea, se abre el asistente de promoción con el **Nuevo nivel opcional** (antes era obligatorio):

- **Con Nuevo nivel** (también Programación académica y Año/periodo académico de destino, ya exigidos en esta rama): el botón **"Promover / Finalizar proceso"** abre el formulario de la nueva Inscripción, ya prellenado. Al guardarlo, la Inscripción de origen queda marcada **"Promovido"**, enlazada a la nueva Inscripción, y se registra la trazabilidad (ver 12.5).
- **Sin Nuevo nivel**: el mismo botón muestra una pantalla de confirmación ("No se ha seleccionado un nuevo nivel. ¿Desea finalizar el proceso académico del estudiante?"). Al confirmar, la Inscripción de origen queda marcada **"Finalizado"**, con fecha y usuario responsable — **no se crea ninguna Inscripción nueva**.

En ambos casos la Inscripción de origen conserva el resto de su información exactamente igual (notas, observaciones, fechas, etc.); lo único que cambia es la marca de continuidad.

### 12.4. Promover seleccionados (masivo)

**Dónde:** acción **"Promover seleccionados"** en la lista de Inscripciones (selección múltiple), restringida a **Officer/Admin** (reemplaza la acción "Promote Students" original, que aplicaba un único nivel a todo el lote y no tenía restricción de perfil).

Abre un asistente con una línea por cada Inscripción seleccionada, donde cada una se decide **de forma independiente**: Nuevo nivel (opcional, por línea), Programación académica de destino y Año/periodo académico de destino (exigidos solo si esa línea tiene Nuevo nivel). Cada línea muestra su propio Resultado académico y un mensaje de validación (Aprobado listo para promover/finalizar, No aprobado, Pendiente, Ya promovido, Ya finalizado, falta Programación o Año de destino).

Al presionar **"Procesar"**: cada línea válida se promueve o finaliza por separado -una línea inválida **no** cancela las demás, simplemente queda sin procesar-, y al final se muestra un resumen con cuántas se promovieron, cuántas se finalizaron y cuántas no se procesaron (con el motivo de cada una).

### 12.5. Trazabilidad y consulta de Promovidos/Finalizados

Cada Promoción o Finalización confirmada -individual o masiva- queda registrada en **Estudiantes → Reportes → Promovidos y Finalizados** (solo Officer/Admin): estudiante, Identificación, Programa, nivel de origen, Resultado académico, acción (Promovido/Finalizado), nivel nuevo, Programación/Año de destino, Inscripción de origen, nueva Inscripción, tipo de ejecución (Individual/Masiva) y usuario responsable. Con filtros y agrupación por acción, tipo de ejecución y usuario.

### 12.6. Qué no hace todavía

- No genera ningún certificado para los estudiantes Finalizados -la consulta de 12.5 deja toda la información lista (incluida la Inscripción de origen) para una futura subtarea de certificación-.
- No construye un cálculo de notas/promedios: el Resultado académico depende enteramente del indicador "¿Aprueba?" de la Escala de calificación (12.1).
- No hace falta ningún desarrollo aparte para la "Repetición académica": un estudiante No aprobado simplemente no puede promoverse por este medio; si debe repetir el mismo nivel, se inscribe de nuevo por el mecanismo normal y ya existente, que esta subtarea no modifica. **Importante (hallazgo verificado, no introducido por esta subtarea):** por defecto, el sistema **bloquea** crear una segunda Inscripción en el mismo Nivel académico para el mismo estudiante, sin importar que la anterior ya esté Terminada/No aprobada -es una validación de Webkul, independiente del Resultado académico-. Para poder repetir un nivel hay que activar primero **Ajustes → Estados académicos → "Permitir múltiples inscripciones activas"** (tarea 11293); con ese ajuste activo, repetir un nivel funciona exactamente como lo describe el ejemplo de la sección 12.7 (ambos intentos quedan visibles, cada uno con su propio Resultado académico, sin sobreescribirse).

### 12.7. Histórico académico en la ficha del Estudiante

La pestaña **"Inscripciones"** de la ficha del Estudiante (sección 5) ya funciona como consulta de histórico académico básico, sin ningún desarrollo adicional: muestra Matrícula, Programa académico, Nivel académico, **Resultado académico** (badge Pendiente/Aprobado/No aprobado) y Fecha de inscripción -**sin** la columna de Estado operativo-, con todas las Inscripciones del estudiante visibles como filas independientes (una inscripción nueva nunca sobreescribe el Resultado académico de una anterior) y acceso directo a la Inscripción original al hacer clic en una fila.

Esto funciona así porque esa pestaña no tiene una lista propia: reutiliza la misma vista de lista genérica de Inscripciones (`wk_school_management.student_enrollment_form_tree`) que ya se ajustó en la sección 12.2 -ocultar Estado, mostrar Resultado académico-, así que el cambio se hereda automáticamente ahí también.

**Verificado en vivo el escenario de "repetir un nivel"** (sección 3, escenario 6 del documento): con el ajuste **"Permitir múltiples inscripciones activas"** activo (ver la nota en 12.6), ambas Inscripciones del mismo Nivel académico quedan visibles en la pestaña, cada una con su propio Resultado académico sin sobreescribirse -exactamente como lo pide el ejemplo de la sección 2.5 de ese documento-. **Con ese ajuste desactivado (el valor por defecto)**, repetir el mismo nivel está bloqueado por una validación de Webkul ajena a esta subtarea (ver 12.6) -la pestaña en sí ya está lista para mostrar varios intentos en cuanto la institución decida habilitar esa opción-.

---

## 13. Permisos — resumen

| Perfil | Puede ver/editar |
|---|---|
| **Staff** (docentes) | Todo lo anterior, **excepto**: el check y motivo de restricción del estudiante; crear/editar/desactivar Tipos de programa, Jornadas y Regímenes de salud (solo los puede leer/seleccionar); el menú de auditoría de Observaciones (pero sí puede crear observaciones desde Inscripción y Clase); confirmar "Ninguna coincidencia, crear nuevo" en la pantalla de posibles duplicados (sección 3) — sí puede elegir un registro existente de esa misma pantalla; activar/inactivar Asignaturas del nivel, activar/inactivar Clases Ofertadas (individual o masivamente), la creación masiva de Clases Ofertadas, y aplazar a un estudiante (sección 11.2); Promocionar ahora, Promover seleccionados y la consulta de Promovidos/Finalizados (sección 12) |
| **Officer / Admin** | Todo, sin restricciones |

Si un usuario Staff entra a cualquiera de las pantallas descritas en este documento, no debería ver ningún error de permisos — simplemente no verá los elementos restringidos a Officer/Admin.

**Resumen de permisos propios de la sección 14** (estructura de calificación avanzada): Staff/docentes pueden registrar calificaciones y evaluar Class Performance de sus propias clases mientras la edición no esté bloqueada; solo consultan (no crean/editan) Componentes, Equivalencias cualitativas, Criterios de Class Performance y Rangos de desempeño de la Escala. Officer/Admin tienen control total: aplicar la estructura, habilitar/bloquear edición al docente, confirmar Midterm/Final, publicar/ocultar en portal y reabrir un corte confirmado (esto último, solo Admin).

---

## 14. Estructura de calificación avanzada

Esta sección cubre el ajuste integral de la forma en que se califica la operación académica de Inglés del Centro Colombo Americano: una estructura propia de componentes y ponderaciones (por uno o dos cortes), Class Performance cualitativo, horas de ausencia, un Consolidado de notas por clase con cálculo automático de Midterm/Final Grade, ranking y Pass/Fail, su confirmación y publicación en el portal del estudiante, e integración con los reportes Midterm, Final y Class List.

**Todo lo de esta sección es opcional y por Escala de calificación.** Mientras el check "Habilitar estructura de calificación avanzada" (14.1) permanezca desactivado —que es como queda cualquier Escala nueva o ya existente—, esa Escala sigue funcionando exactamente igual que antes de esta subtarea: nada de lo descrito aquí se activa ni se muestra.

### 14.1. Configuración de la Escala de calificación avanzada

**Dónde:** Configuración → Académicos → Escala de calificación.

Al activar el check **Habilitar estructura de calificación avanzada**:

- El check estándar **Habilitar cálculo del promedio académico** (GPA) queda oculto y se desactiva automáticamente — los dos mecanismos de cálculo nunca operan a la vez sobre la misma Escala.
- Se prellenan, solo la primera vez y solo si están vacías, las 5 valoraciones cualitativas, los 5 criterios de Class Performance y los 4 rangos de desempeño que usa hoy la institución (ver 14.2, 14.4 y 14.5) — como punto de partida editable, nunca como un valor fijo que el cálculo use directamente: el cálculo siempre lee lo que quede guardado en la base de datos.
- Aparecen los campos **Estructura activa** (si se desactiva, deja de poder aplicarse a Clases ofertadas nuevas; las que ya la tienen aplicada no se ven afectadas), **Tipo de programa**, **Programa o modalidad**, **Nota mínima de aprobación**, **Decimales** (con cuántos decimales se redondean, muestran y comparan el Midterm/Final Grade — para que lo que el usuario ve sea exactamente lo que se usó para clasificar Pass/Fail y el rango de desempeño) y **Número de cortes** (1 o 2).
- Aparecen 4 pestañas nuevas, descritas abajo: Equivalencias cualitativas, Componentes de calificación, Class Performance y Configuración adicional.

### 14.2. Equivalencias cualitativas

Lista editable de valoraciones (Excellent, Very Good, Good, Fair, Needs Improvement, u otras que se agreguen) con un **Valor cuantitativo** configurable para cada una. Es la tabla que usa Class Performance (14.4) para convertir una valoración elegida por el docente en un número; modificar el valor de una valoración más adelante no cambia ningún resultado ya consolidado (14.7).

### 14.3. Componentes de calificación

Lista editable de los componentes que conforman la nota (Quiz 1, Quiz 2, Final Exam, Class Performance, etc.), cada uno con:

- **Orden**, **Nombre**, **Tipo de actividad** (el mismo catálogo que ya existía).
- **Peso Midterm (%)**: con 1 corte, es el único peso del componente sobre el 100 %; con 2 cortes, es su peso dentro de Midterm.
- **Peso Final (%)**: solo aplica con 2 cortes. Un componente puede tener peso en ambos (por ejemplo, un Quiz de Midterm que también cuenta para Final) o en uno solo — 0 en el otro significa que no participa en ese corte, y reutiliza automáticamente la misma calificación registrada por el docente, sin pedirla dos veces.
- **Es Class Performance**: marca el componente que recibe el resultado de la evaluación cualitativa (14.4). Con 2 cortes, cada corte tiene su propio componente de Class Performance.
- **Incluir en Fin. Quiz Average**: solo afecta un indicador informativo (el promedio simple de los componentes marcados); no cambia la ponderación real, que siempre es la de los campos de peso.
- **Activo**.

El sistema valida automáticamente que la suma de los pesos sea 100 % en cada corte (considerando solo los componentes con un peso mayor que 0 en ese corte); con 0 componentes todavía no valida nada, para poder ir configurando por partes.

### 14.4. Class Performance

Lista editable de los criterios que se evalúan (Attendance/Promptness, Engagement, Listening Skill, Behavior, Preparation, u otros), cada uno con **Nombre**, **Orden** y **Activo**. Un criterio inactivo deja de aparecer en evaluaciones nuevas; las ya registradas no se modifican.

### 14.5. Configuración adicional

- **Regla de ausencias**: Horas mínimas y máximas del rango, Promedio exigido dentro del rango y si se reprueba automáticamente al superar las horas máximas (ver 14.9).
- **Rangos de desempeño**: lista editable con Código, Nombre, Nota mínima, Nota máxima y Activo (semilla sugerida: DS 90-100, DA 80-89.9, DBS 70-79.9, DBJ 0-69.9). La clasificación de una Final Grade usa el rango activo de mayor Nota mínima que sea menor o igual a la nota — un hueco entre dos rangos (p. ej. 89.9 y 90.0) no genera error, simplemente cae en el rango inferior.
- **Permitir edición de calificaciones confirmadas (solo usuarios autorizados)**: desactivado por defecto. Controla si el botón **Reabrir Final** (14.10) está disponible para las clases de esta Escala — desactivado, el corte Final confirmado queda bloqueado para siempre, sin excepción (ni para Admin).
- **Mostrar descriptivo del desempeño en la boleta de notas**: activado por defecto. Si se desactiva, el Reporte Final (14.11) deja de imprimir el nombre del rango de desempeño (p. ej. "Desempeño Alto") junto a la Final Grade.
- **Mensaje adicional en la boleta de notas**: texto libre que se imprime al final del Reporte Final de cualquier clase que use esta Escala (p. ej. una nota institucional).

### 14.6. Aplicar la estructura a la Clase ofertada

**Dónde:** formulario de la Clase ofertada (Gestión Educativa → Clases → Poblar Clases).

- Campo **Escala de calificación (avanzada)**: solo ofrece Escalas con la estructura avanzada activa.
- Botón **Aplicar estructura de calificación** (visible mientras la clase esté en "Nuevo", solo Officer/Admin): copia los Componentes de la Escala a la pestaña "Tipos de actividad" (con su peso Midterm/Final) y desactiva "¿Distribuir el porcentaje por partes iguales?", que no aplica con una estructura avanzada.
- Las filas de "Tipos de actividad" quedan de solo lectura: para cambiarlas hay que volver a presionar "Aplicar estructura de calificación", lo cual está bloqueado en cuanto existan calificaciones registradas para esa clase (evita dejar actividades o notas huérfanas de su Componente de origen).
- Al confirmar la clase (botón "Confirm"), se valida la misma suma de pesos por corte que en la Escala.
- Al aplicar la estructura se crea automáticamente el **Consolidado de notas** de la clase (14.7), con una línea por cada estudiante ya matriculado.

### 14.7. Asignar tarea y Evaluar

- **Asignar tarea** conserva su visual de siempre; en una clase con estructura avanzada, el campo que antes era "Actividad" pasa a ofrecer los **Componentes** de esa estructura. Al elegir uno, el sistema completa por debajo el tipo de actividad y crea o reutiliza la plantilla de actividad aprobada que necesita el asistente — el docente sigue diligenciando solo Título, Fechas y Puntaje máximo, como siempre.
- **Evaluar** conserva su flujo de siempre. Para un componente cuantitativo, el docente registra directamente la **Calificación**; no se muestran los campos de conversión de la Escala estándar (Calificación equivalente, % Obtenido), que no participan del cálculo en una estructura avanzada.
- Para el componente marcado **Es Class Performance**, en vez de un puntaje aparece el botón **Calificar Class Performance**: abre una pantalla con los criterios activos de la Escala, donde el docente elige una valoración por criterio. El sistema calcula solo el promedio de las valoraciones ya calificadas y lo traslada como la calificación de ese componente — el docente nunca lo calcula a mano.

### 14.8. Consolidado de notas

**Dónde:** Maestros → **Consolidado de notas**.

La lista inicial muestra, por defecto, solo las clases **activas** con estructura avanzada aplicada (filtro "Clase activa", activo de entrada — se puede quitar para ver también el Consolidado de clases ya inactivadas), con Módulo, Nivel, Programa, Docente, Periodo académico y el **Estado** general (Borrador / En proceso / Publicada — calculado desde si Midterm/Final están confirmados y si al menos un estudiante está "Visible en portal"; los estados de Midterm y Final por separado siguen disponibles como columnas ocultas).

Al entrar a una clase, la ficha se organiza así:

- **Datos generales** (solo lectura): Módulo, Modalidad, Docente, Periodo académico, Estructura, Nota mínima de aprobación y la Regla de ausencias resumida en una frase (p. ej. "Más de 10 y hasta 15 horas → aprobar con promedio > 85").
- **Controles administrativos**: dos checks — **Edición docente habilitada** (editable directamente por Officer/Admin; Staff solo puede leerlo, el modelo le bloquea cualquier escritura) y **Calificaciones confirmadas** (de solo lectura, refleja si Final ya está confirmado — para confirmar o reabrir se usan los botones del encabezado, nunca este check, porque saltarse esa validación rompería el histórico).
- **Ponderaciones por corte**: dos listas de solo lectura con el nombre de cada componente y su peso, una para Midterm y otra para Final (esta última oculta con 1 corte) — misma información que ya estaba en la pestaña "Tipos de actividad" de la Clase, pero visible aquí sin salir del Consolidado. Un componente que pese en ambos cortes aparece en las dos listas.
- Pestaña **Matriz**: cuadrícula de solo lectura con una **columna por cada componente** de la estructura (agrupadas "Midterm"/"Final" cuando hay 2 cortes, con el mismo componente repetido en ambos grupos si pesa en los dos), más Final Grade, ABS, Posición, Rango de desempeño y Pass/Fail al final — las columnas se generan dinámicamente según la estructura de la clase, sin que un cambio en la cantidad o el nombre de los componentes requiera ningún campo técnico nuevo (requerimiento 2.9, escenario 16).
- Pestaña **Resultados**: por estudiante, Estado de cursado, Midterm Grade (si hay 2 cortes), Final Grade, Fin. Quiz Average, ABS/Horas de ausencia, **Posición** (ranking con medalla 🥇🥈🥉 para los 3 primeros), Rango de desempeño, Pass/Fail (con la causa cuando Fail no es por nota), Comentarios y el check **Visible en portal**; debajo de la lista, un resumen rápido (Promedio general, % Aprobados, % Reprobados). Esta es la única pestaña editable (Comentarios, Visible en portal) — la Matriz es solo para consulta. Midterm/Final Grade, Fin. Quiz Average y el Promedio general se muestran siempre con la cantidad de **Decimales** configurada en la Escala (14.5), no fija en 2.
- Pestaña **Estadísticas**: los mismos indicadores completos (cantidades y porcentajes de Aprobados/Reprobados/Pendientes, cuántos superan las horas mínimas de ausencia) más la distribución de estudiantes por rango de desempeño (p. ej. "DS: 2 · DA: 5 · DBS: 3 · DBJ: 1").
- Pestaña **Ausencias**: el detalle de asistencia (fecha, estado, etiqueta, horas de ausencia, observaciones) de todas las sesiones de la clase, de solo lectura — antes solo se veía entrando sesión por sesión a "Marcar Asistencia".
- Pestaña **Comentarios**: la misma lista de estudiantes enfocada en editar **Comentarios** de corrido, sin el resto de columnas de notas.
- Pestaña **Histórico**: quién y cuándo confirmó Midterm/Final, y qué estudiantes ya tienen un snapshot histórico congelado.
- Botones **Ver estructura** (abre la Escala de calificación en una ventana aparte, de solo lectura) y **Exportar** (descarga un CSV con una fila por estudiante, listo para abrir en Excel).

El Consolidado se sigue alimentando solo: nunca se registra una calificación ahí directamente. El botón **Actualizar** agrega líneas de estudiantes matriculados después (nunca elimina una existente, para no perder histórico) y refresca notas, horas de ausencia, ranking y Pass/Fail.

- **Cálculo**: la nota de cada componente es la registrada por el docente (o el promedio de Class Performance); el aporte es nota × peso/100; Midterm/Final Grade es la suma de aportes del corte. Con 1 corte, el resultado único se muestra como Final Grade. El ranking ordena por Final Grade (y por Midterm Grade aparte, con 2 cortes), dejando la misma posición a los empates; solo participan los estudiantes con todos los componentes de peso mayor que 0 ya calificados.
- **Pass/Fail**: aprueba si la Final Grade alcanza la Nota mínima de aprobación, salvo la regla de ausencias (14.9).
- **Rango de desempeño**: el de mayor Nota mínima que sea ≤ la Final Grade, entre los rangos activos de la Escala.
- Las **Horas de ausencia** se acumulan automáticamente desde "Marcar Asistencia" (14.9); no se vuelven a registrar aquí.
- **Ocultar calificaciones**: con una estructura avanzada aplicada, los checks "Ocultar calificaciones del grupo" (Clase ofertada) y "Ocultar calificaciones al estudiante" (Estudiante) sí tienen efecto: cualquiera de los dos activo oculta la nota en el portal del estudiante, igual que desmarcar "Visible en portal" (no afecta la consulta interna ni el cálculo).

### 14.9. Horas de ausencia y Observaciones

Desde **Marcar Asistencia** de cada sesión se agregaron los campos **Horas de ausencia** y **Observaciones**. Al marcar a un estudiante como Ausente, el sistema sugiere las horas de duración de la sesión (editable); una llegada tarde se registra como Presente más la etiqueta correspondiente (semilla **"Llegada tarde"**, administrable como cualquier otra etiqueta de asistencia) y solo las horas reales de la demora — no hace falta marcarlo como Ausente para eso. Sin ninguna novedad, queda en 0.

**Regla de aprobación por ausencias:** si el acumulado de horas de ausencia de un estudiante en la clase supera las Horas mínimas configuradas (por defecto 10) sin pasar de las Horas máximas (por defecto 15), debe superar el Promedio exigido (por defecto 85) en la Final Grade para conservar la aprobación — si no lo supera, Fail con causa "Regla de ausencias", así la nota por sí sola alcanzara para aprobar. Al superar las Horas máximas, si "Reprobar automáticamente al superar las horas máximas" está activo (lo está por defecto), el resultado es Fail sin importar la nota. La regla nunca modifica las calificaciones registradas, solo la condición Pass/Fail.

### 14.10. Confirmación, bloqueo de edición y publicación en portal

- **Edición docente habilitada** (check de "Controles administrativos" en el Consolidado, solo Officer/Admin puede cambiarlo): mientras está desmarcado, el docente puede consultar sus calificaciones pero no modificarlas (ni los criterios de Class Performance); Officer/Admin nunca queda bloqueado.
- **Confirmar Midterm** / **Confirmar Final** (solo Officer/Admin): valida que los pesos sigan sumando 100 % por corte y que no falte ninguna calificación, y congela un histórico (estructura, componentes, ponderaciones, resultado, horas de ausencia y rango de desempeño del momento) que no se recalcula aunque después cambien la Escala, sus componentes o sus equivalencias. Con 1 corte solo existe "Confirmar Final". Una vez Final está confirmado, nadie más que Officer/Admin puede modificar esa clase, ni siquiera estando "Habilitada" la edición; reabrirla (**Reabrir Final**) queda reservado a Admin, y además solo aparece si la Escala tiene activo "Permitir edición de calificaciones confirmadas" (14.5) — sin ese check, ni siquiera Admin puede reabrirla.
- La confirmación de una clase con estructura avanzada también alimenta el **Resultado académico** de la Inscripción (sección 12.1): mientras no se confirme Final, ese resultado permanece "Pendiente".
- **Visible en portal**: check individual por estudiante en el Consolidado (solo Officer/Admin lo ve y lo puede escribir — un docente no puede publicar ni ocultar notas, ni desde la vista ni por API), más dos niveles de acción masiva: **Publicar/Ocultar notas en portal (todos)** en el encabezado del formulario, y **Publicar/Ocultar seleccionados** en el encabezado de la pestaña "Resultados" (marcando el checkbox de los estudiantes deseados, para publicar un subconjunto arbitrario sin afectar al resto). Después de cualquier acción masiva, el check individual de cada fila sigue permitiendo excepciones puntuales. Desmarcado, el estudiante ve su Materia como si todavía no tuviera nota (no se le oculta la fila, se le muestra en 0) — la nota real, el Pass/Fail y el histórico no se alteran. La vista individual de cada actividad (Quiz, Examen, etc.) en el portal del estudiante no muestra ningún dato de una estructura avanzada todavía — solo el resumen de calificaciones por Materia respeta "Visible en portal"; mostrar también el detalle de cada actividad en el portal queda para un ajuste posterior si la institución lo pide.
- **Reapertura de un corte confirmado**: además del check "Permitir edición de calificaciones confirmadas" de la Escala (14.5) y de restringirla a Admin, el Consolidado registra **quién y cuándo** reabrió el corte Final (pestaña Histórico). El histórico congelado de cada estudiante conserva **todas** las confirmaciones que se hayan hecho de un mismo corte (nunca se sobreescribe una confirmación anterior al reconfirmar después de reabrir): cada una guarda su propio usuario, fecha, resultado y componentes de ese momento.

### 14.11. Reportes Midterm, Final y Class List

Desde el Consolidado (menú Imprimir del formulario, o los botones de Class List en el encabezado):

- **Reporte Midterm**: solo disponible en estructuras de 2 cortes; por estudiante, los componentes de ese corte con su peso y nota, Midterm Grade, horas de ausencia, ranking y comentarios.
- **Reporte Final**: por estudiante, los componentes de Final con su peso y nota, Final Grade, horas de ausencia, ranking, Pass/Fail (con la causa), el rango de desempeño (si "Mostrar descriptivo del desempeño" está activo en la Escala) y comentarios. Al final del reporte se imprime el "Mensaje adicional en la boleta de notas" de la Escala, si tiene uno configurado.
- **Class List**: encabezado completo de la clase (Programa, Nivel, Módulo, Profesor, Assistant teacher, Libro, Horario, Salón, Fecha) y los estudiantes, con tres botones de variante — Todos, Pass y Fail (para el cierre de curso). Desde la tarea 12436 (sección 16) también se genera, con columnas adicionales a elección del usuario, desde **Informes → Hoja de calificaciones**.
- **Distribución por Desempeño**: agrupa a los estudiantes de la clase por Rango de desempeño (de mayor a menor Nota mínima, igual que en la Escala), con cantidad y porcentaje por rango, y el listado de estudiantes (con su Final Grade) dentro de cada uno. Los que aún no tienen un rango asignado (resultado pendiente) quedan en un grupo "Sin clasificar" al final. Existe además una versión en Excel, consolidada por Programa/Periodo/Sede (no por una sola clase) — ver sección 16.2.

Los reportes leen siempre la información ya consolidada (el histórico congelado si el corte está confirmado, el cálculo en vivo si no) — nunca piden un cálculo manual.

### 14.12. Examen de clasificación

**Dónde:** check **Examen de clasificación** en el formulario de la Clase ofertada (8.1), junto a "Escala de calificación (avanzada)".

El examen de clasificación se gestiona como una Clase ofertada más (con su propia Escala de calificación avanzada aplicada, normalmente de un único Componente al 100 %), pero su resultado real para la institución no es una nota numérica: es un nivel escrito a mano por quien califica (p. ej. "Nivel intermedio", "Avanzado"). Marcando **Examen de clasificación** en esa Clase, el texto que se escriba en **Comentarios** (pestaña Resultados o Comentarios del Consolidado, 14.8) para cada estudiante se copia automáticamente al campo **Resultado examen de clasificación** de su Inscripción (visible también desde el formulario de la Inscripción, 6), y activa ahí el check **¿Examen de clasificación?**.

- La copia es exclusiva de la Clase marcada: el Comentario de cualquier otra Clase (con o sin estructura avanzada) nunca toca ese campo, así el estudiante tenga varias Materias calificadas al mismo tiempo.
- El Pass/Fail del examen (aprobó / no aprobó el examen de clasificación como tal) sigue el mecanismo normal de la Escala aplicada a esa Clase (14.6-14.8) — la automatización de esta sección solo cubre el **resultado cualitativo** (el nivel), no reemplaza ni cambia el cálculo de Pass/Fail.
- Si se corrige el Comentario después (por un error de digitación, por ejemplo), el campo de la Inscripción se actualiza con el nuevo texto la próxima vez que se guarde.

### 14.13. "Consultar calificaciones" (Hoja de calificaciones) con estructura avanzada

**Importante:** el botón **Consultar calificaciones** de Informes → Hoja de calificaciones es una pantalla **anterior** a la Estructura de calificación avanzada (14.1-14.11), construida para el sistema de calificación estándar de Webkul. Con una Clase que tiene la estructura avanzada aplicada:

- Ya no se bloquea con un error (hasta la tarea 12436 producía "Expected singleton" cuando dos o más componentes compartían el mismo Tipo de actividad base, p. ej. "Quiz 1" y "Quiz 2" ambos bajo "Quiz").
- Pero **tampoco muestra las notas reales**: esta pantalla lee un campo (porcentaje obtenido por rangos) que la estructura avanzada no usa -ahí la nota se registra directa, sin conversión por rangos-, así que siempre va a mostrar 0% en una clase con estructura avanzada.

Para consultar o imprimir las notas reales de una clase con estructura avanzada, use el **Consolidado de notas** (14.8), la **Boleta de calificaciones** (16.2) o el **Class List** (14.11, 16.1) — todos leen directamente la información ya consolidada.

---

## 15. Pago por cuotas y tabla de amortización

Permite que un estudiante pague su obligación mediante una cuota inicial y uno o varios abonos, con **una única factura** por el valor total (nunca facturas por cuota) y una **tabla de amortización** que hace seguimiento a cada cuota (programado, pagado, saldo y estado), reutilizando siempre el flujo estándar de pagos de Odoo.

### 15.1. Configuración del acuerdo de pago

**Dónde:** botón **Generar recibos de tarifas**, dentro de Inscripción → Resumen de tarifas.

Al abrir el asistente, **Plazo de pago** y **Entrega** siguen funcionando igual que siempre. Al marcar el nuevo check **Pago por cuotas**, ambos campos se fijan solos en **Personalizado** y **1** (se ocultan, ya no hace falta tocarlos) y aparecen los campos del acuerdo:

- **Monto inicial**: lo escribe el usuario.
- **Valor pendiente**: se calcula solo, Monto total a pagar − Monto inicial.
- **Número de abonos**, **Fecha primer abono** y **Periodicidad** (Semanal/Quincenal/Mensual).
- **Vista previa de cuotas**: se recalcula automáticamente al cambiar cualquiera de los campos anteriores (una fila "Cuota inicial" + una fila "Abono N" por cada abono), y es **editable**: el usuario autorizado puede ajustar a mano la fecha y el valor de cualquier fila antes de confirmar.
- **Código de beneficio / cupón** (opcional, ver 15.8).

El sistema **no permite confirmar el acuerdo** cuando:
- el Monto inicial es mayor al Monto total a pagar;
- el Número de abonos es cero o negativo;
- las fechas de las cuotas no son estrictamente crecientes y distintas entre sí (dos cuotas no pueden vencer el mismo día);
- la suma de todas las filas de la vista previa no coincide exactamente con el Monto total a pagar (ajustada por el % Descuento, ver 15.7, y el beneficio aplicado, ver 15.8, si corresponde).

### 15.2. Generación de la tabla de amortización

Al confirmar (**Generate Now**), el sistema genera **un único recibo de tarifa y, a partir de él, una única factura** por el valor total de la obligación — el mismo flujo que ya existía, sin cambios. Encima de esa factura se construye un término de pago a la medida del acuerdo: la **Cuota inicial** y cada **Abono** quedan como líneas contables propias (vencimiento) dentro del **mismo asiento** de esa única factura, de modo que Cuentas por Cobrar refleja la antigüedad real de cada cuota.

Las cuotas de la tabla **no generan recibos ni facturas independientes**: son únicamente la programación y el seguimiento del acuerdo. El valor y la fecha de vencimiento originalmente programados de cada cuota quedan congelados para siempre, incluso después de pagos parciales o anticipados (15.5, 15.6).

### 15.3. Detalle y seguimiento

**Dónde:** Inscripción → Resumen de tarifas → **Plan de pagos / Tabla de amortización** (debajo del resumen de conceptos de cobro; solo aparece si la inscripción tiene un acuerdo de pago por cuotas).

Columnas: **Cuota** (Cuota inicial/Abono N), **Fecha de vencimiento**, **Valor programado**, **Valor pagado**, **Saldo**, **Estado**, **Factura** y una columna de **Acción**. Valor pagado, Saldo y Estado se calculan solos a partir de los pagos reales registrados — no son editables desde la tabla.

Estados: **Pendiente** (sin pagos, fecha aún no vencida), **Pago parcial** (hay un abono pero queda saldo, fecha aún no vencida), **Pagado** (saldo en cero) y **En mora** (queda saldo y la fecha de vencimiento ya pasó).

La misma tabla (resumida) está disponible desde **Gestión Educativa → Informes → Recibos de cobro** (15.9).

### 15.4. Registrar abono

Cada cuota con saldo pendiente muestra el botón **Registrar abono**; una cuota ya Pagada muestra **Ver pago** en su lugar. "Registrar abono" abre el **mismo asistente estándar "Registrar Pago" de Odoo** (el mismo que se usa desde cualquier factura) — no existe un asistente paralelo. El asistente queda vinculado a la factura total y sugiere como importe el saldo pendiente de la cuota elegida; el usuario completa diario, fecha, referencia y demás campos estándar, y al confirmar el pago se genera el movimiento contable real según la configuración del diario.

### 15.5. Pago parcial

Si el valor pagado es menor al valor programado de la cuota, el sistema **no crea una línea nueva**: la misma cuota conserva su Fecha de vencimiento y Valor programado originales, y solo actualiza Valor pagado, Saldo y Estado (Pago parcial, o En mora si ya venció). Las cuotas futuras no se tocan.

### 15.6. Pago anticipado (abono mayor al saldo de la cuota)

Si el abono registrado es mayor al saldo de la cuota elegida, el sistema cubre primero esa cuota (queda Pagada) y aplica automáticamente el excedente a las **siguientes cuotas pendientes**, en orden de vencimiento — sin generar líneas nuevas y **sin recalcular ni mover** las fechas o valores programados de ninguna cuota futura. Ejemplo: con tres abonos de $400.000 pendientes y un pago de $700.000 sobre el Abono 1, el sistema deja el Abono 1 en Pagado y aplica los $300.000 restantes al Abono 2 (Valor pagado $300.000, Saldo $100.000, Pago parcial); el Abono 3 no se altera.

### 15.7. % Descuento

**Dónde:** columna **% Descuento**, junto a cada concepto de cobro en Resumen de tarifas.

Un porcentaje de descuento por concepto reduce la tarifa (Monto total de la tarifa) de ese concepto; el monto ya ajustado es la base tanto para la factura como, si aplica, para la tabla de amortización. El valor original (antes de descuento) y el valor descontado quedan disponibles para consulta.

### 15.8. Beneficios / cupones (código de descuento)

**Dónde:** campo **Código de beneficio / cupón** en el asistente de generación (15.1).

Reutiliza el catálogo estándar de programas de fidelización/cupones de Odoo (Configuración), pero con una integración **deliberadamente simple** (decisión confirmada con el usuario): soporta únicamente recompensas de tipo **Descuento**, en modo **porcentaje** o **monto fijo por recibo**. El beneficio se aplica como una **línea independiente y negativa** dentro del recibo de tarifa (el mismo comportamiento estándar que ya usa, por ejemplo, la cuota de biblioteca), reduciendo el total sin modificar el precio de los conceptos de cobro. Queda registrado en un log de trazabilidad (programa, recompensa, código/cupón, usuario, fecha y valor descontado).

**No incluido en esta integración** (si la institución lo necesita, requiere ampliar el adaptador):
- Recompensas de tipo "Producto gratis" ni descuentos "por punto".
- Combinar varios beneficios sobre el mismo recibo.
- Acumulación/expiración automática de puntos más allá de debitar los puntos exigidos por la recompensa, cuando el programa es de tipo "Tarjetas de fidelización".

### 15.9. Recibos de cobro (ampliado)

La vista existente **Gestión Educativa → Informes → Recibos de cobro** ahora también muestra, cuando el recibo tiene un acuerdo de pago por cuotas: Pago por cuotas (Sí/No), N° de cuotas, Valor pagado, Saldo pendiente, Cuotas pagadas/pendientes, Próxima fecha de vencimiento, Valor del próximo abono, Estado del acuerdo y la Factura asociada. Incluye filtros por "Pago por cuotas", "Con saldo pendiente", "Con cuotas en mora" y "Con cuotas pendientes", y agrupación por Estado del acuerdo. Para un recibo sin pago por cuotas estas columnas quedan vacías — el comportamiento del reporte no cambia.

### 15.10. Tirilla de pago (tarea 12458)

Cada registro de pago (el mismo `account.payment` que genera "Registrar Pago"/"Registrar abono") se puede imprimir como una **tirilla de pago**, con el formato térmico angosto (80mm) del recibo físico histórico del Colombo — no se guarda en un modelo propio: el pago ya es la unidad de trazabilidad, así que generar e imprimir de nuevo la misma tirilla (reimpresión) no crea ningún pago, factura ni movimiento contable nuevo.

**Dónde:**
- En **Inscripción → Resumen de tarifas → Tabla de amortización**, botón **Imprimir Tirilla** junto a "Ver pago" en cada cuota pagada.
- En **Recibo de cobro** (pago único, sin acuerdo de cuotas), botón **Imprimir Tirilla** en el encabezado, junto a "Ver factura", visible cuando el recibo está en estado Pagado.
- También disponible desde el propio menú "Imprimir" del registro de pago (`account.payment`).

Si una cuota o un recibo llegara a tener más de un pago reconciliado, se genera una tirilla por cada uno (nunca una combinada), reutilizando siempre el mismo reporte.

**Contenido:** institución y NIT, número de comprobante (el mismo consecutivo de `account_journal_sequence`), fecha y hora, identificación y nombre del estudiante; cuando el concepto corresponde a una clase del estudiante (`wk.school.class`, buscada a través de su Inscripción): programa (Asignatura), nivel, fecha de inicio, horario, profesor, salón y libro — si el concepto no corresponde a ninguna clase (certificados, exámenes administrativos, etc.) ese bloque simplemente no aparece; concepto(s) y valor de la factura, total, forma de pago y valor pagado; cuotas pendientes de la tabla de amortización al momento de la impresión (cuando aplica); usuario que atendió (quien registró el pago) y **Observaciones** — campo de texto libre nuevo, capturable directamente en el wizard "Registrar Pago" y editable después desde el propio pago; y un texto legal/institucional configurable en **Ajustes → Gestión Educativa → Tirilla de pago** (exención de IVA, política de devoluciones, aviso de protección de datos, etc. — en blanco por defecto, cada institución lo redacta a su gusto).

### 15.11. No incluye (de esta subtarea)

- Recalcular o redistribuir automáticamente las cuotas futuras ante un pago parcial (15.5) — es un requisito explícito del documento, no una limitación.
- Intereses o recargos automáticos por mora: la mora es solo informativa (15.3).
- El adaptador de beneficios/cupones no reemplaza el motor completo de descuentos/lealtad de Odoo (ver límites en 15.8).
- La tirilla de pago (15.10) no distingue "impresión" de "reimpresión" (p. ej. con un sello "REIMPRESIÓN"): el requerimiento 12458 no lo exige, cualquier impresión posterior a la primera usa el mismo botón y el mismo contenido.

---

## 16. Ajuste y ampliación de Reportes Académicos (tarea 12436)

Expone desde **Informes** los reportes académicos que el Consolidado de notas (sección 14) ya construía, y agrega dos salidas nuevas en Excel para el análisis consolidado del Programa. Ningún reporte de esta sección recalcula notas, Pass/Fail ni rango de desempeño: todos leen la información que el Consolidado ya tiene calculada.

### 16.1. Class List / Listado del Módulo — desde Hoja de calificaciones

**Dónde:** Gestión Educativa → Informes → Hoja de calificaciones. Después de seleccionar Programación académica, Nivel académico y Clase ofertada, aparece el botón **Generar Class List** junto a "Fetch GradeSheet".

Al pulsarlo se abre un asistente con:
- **Calificación** (Midterm/Final): solo visible si la Escala de la clase maneja 2 cortes; con 1 corte, el Class List siempre usa el resultado Final.
- **Columnas adicionales**, cada una independiente: **Notas** (componentes académicos del corte elegido, más Fin. Quiz Average, Midterm/Final Grade, Rank, ABS y Pass/Fail), **Factura** (la más reciente de la Inscripción), **Teléfono**, **Celular** y **Correo electrónico**.

Sin ninguna columna adicional marcada, el PDF es la lista básica (Código, Estudiante, Firma) — el mismo comportamiento que ya tenían los botones "Class List (todos/Pass/Fail)" del Consolidado (14.11), que siguen funcionando igual y ahora también con el encabezado completo de la clase (Programa, Nivel, Módulo, Profesor, Assistant teacher, Libro, Horario, Salón, Fecha, Total de estudiantes).

### 16.2. Reporte Individual del Estudiante — desde Boleta de calificaciones

**Dónde:** Gestión Educativa → Informes → Boleta de calificaciones. Seleccionando uno o varios registros y usando el menú **Imprimir → Reporte Individual del Estudiante** (el mismo menú nativo de impresión de Odoo, sin botón aparte).

El PDF combina, **en un solo documento**, las secciones Midterm y Final cuando la Escala de la clase maneja 2 cortes (componentes con peso y nota, Midterm/Final Grade, ausencias, ranking de cada corte); con 1 corte, solo imprime la sección Final. Al final, si el Tipo de programa del estudiante tiene activo **"Mostrar equivalencia con el Marco Común Europeo"** (nuevo check en Configuración → Académicos → Tipos de programa), agrega la tabla de equivalencia entre los niveles del Colombo y el MCE (A1/A2/B1/B1-B2) — se activa por Programa, nunca por código, y queda desactivado por defecto en cualquier Tipo de programa nuevo o existente.

### 16.3. Reportes de Análisis Académico (Excel)

**Dónde:** nueva opción **Gestión Educativa → Informes → Reportes de Análisis Académico**.

El asistente pide: **Tipo de reporte** (Distribución por Desempeño / Retención, Promoción, Pérdida y Deserción), **Periodo académico**, **Programa** y, opcionalmente, **Sede**. El filtro Programa es el agrupador principal: incluye automáticamente todos los niveles, módulos, clases ofertadas y horarios del Programa dentro del Periodo (y la Sede, si se indica) seleccionados — no hace falta elegir uno por uno. El botón **Generar Excel** descarga el archivo.

- **Reporte de Distribución por Desempeño**: una fila por Rango de desempeño activo de las Escalas involucradas (Código, Desempeño, Rango de calificación, No. de estudiantes, Porcentaje de estudiantes) más el total de estudiantes evaluados. Los porcentajes se calculan sobre el total de estudiantes **evaluados** (con un rango asignado); un estudiante con resultado pendiente no cuenta en ningún rango ni en el total.
- **Reporte de Retención, Promoción, Pérdida y Deserción**: una fila por cada Clase ofertada dentro del alcance (Periodo, Nivel, Horario, Total estudiantes, Estudiantes retenidos, Promovidos, Perdidos, Estudiantes desertados), más una fila de totales y los cuatro indicadores: % Retención (Retenidos/Total), % Promoción (Promovidos/Retenidos), % Pérdida (Perdidos/Retenidos) y % Deserción (Desertados/Total). Reglas de clasificación: **Retenido** = matriculado que no está marcado como desertado; **Promovido**/**Perdido** = retenido con Pass/Fail consolidado; **Desertado** = estudiante con la etiqueta de asistencia **Deserción** (16.4) registrada en al menos una sesión de esa clase, sin importar sus horas de ausencia acumuladas.

**No incluido:** la columna "Rango establecido" (meta institucional por rango) que trae el formato de referencia del Colombo no se incluye — es una meta manual sin ningún dato equivalente en Odoo hoy, y los criterios de aceptación de la tarea no la piden; si la institución la necesita, se puede agregar como un campo configurable nuevo en el catálogo de Rangos de desempeño (14.5).

### 16.4. Etiqueta de asistencia "Deserción"

**Dónde:** Marcar Asistencia de la sesión correspondiente, campo de Etiquetas (igual que "Llegada tarde", sección 14).

Etiqueta nueva, sin ningún efecto sobre Pass/Fail, ranking ni rango de desempeño del Consolidado — su único efecto es que el Reporte de Retención (16.3) clasifica como "Desertado" a cualquier estudiante que la tenga marcada en al menos una sesión de la clase, en vez de usar sus horas de ausencia acumuladas (esas horas siguen usándose, sin cambios, para las reglas de aprobación/reprobación de la Escala, sección 14.8).

### 16.5. No incluye (de esta tarea)

- Un punto de acceso adicional a estos reportes desde el formulario del Consolidado de notas (más allá de los botones y el menú Imprimir que ya existían) — se evaluó un diagrama de referencia que sugería un menú "Acción" con las 4 salidas también ahí, pero se descartó por no estar en el texto del requerimiento; los 4 reportes siguen accesibles desde el Consolidado igual que antes (14.11).
- Guardar o versionar los Excel generados dentro de Odoo más allá de la descarga directa (igual que el resto de exportaciones del módulo, p. ej. 14.8).
- Reportes de Registros/Cursos, Financieros (Clientes/Beneficios/Formas de pago) e Histórico Académico ampliado — corresponden a otras subtareas del mismo requerimiento padre (tarea 12405). El Reporte de Consecutivos ya se cubrió aparte (sección 19).

---

## 17. Ajuste y ampliación del Histórico Académico del Estudiante (tarea 12438)

Amplía la funcionalidad existente **Gestión Educativa → Informes → Historial académico** para que muestre, de forma consolidada, **toda la trayectoria académica del estudiante** (todos los programas, periodos, niveles/módulos y clases cursadas), en vez de una sola Programación académica a la vez. No se creó ningún menú ni pantalla paralela: es la misma opción de Informes, ampliada. Toda la información se lee ya consolidada (Consolidado de notas, sección 14; Resultado académico y Promoción/Finalización, sección 12; Observaciones) — nada se recalcula.

### 17.1. Consulta de la trayectoria completa

**Dónde:** Gestión Educativa → Informes → Historial académico.

Los filtros existentes (Programación académica y Estudiante) se conservan en pantalla, pero la Programación académica ya no limita el resultado: al elegir un Estudiante y pulsar **Consultar historial académico**, el sistema trae siempre **toda** su trayectoria, sin importar el programa o periodo.

La tabla **Trayectoria académica** muestra, por cada Clase ofertada cursada: Programa, Periodo académico, Nivel/Módulo, Clase ofertada, Inscripción, Fecha inicio, Fecha fin, Resultado académico, Final Grade, Equivalencia cualitativa, Pass/Fail, Horas de ausencia, Estado académico, Acción realizada, Fecha de acción y Observaciones — más reciente primero.

Al hacer clic en una fila, debajo aparece el **Detalle de calificaciones** de esa clase (los mismos componentes con ponderación y nota del Consolidado, sección 14.8 — Midterm y Final cuando la Escala maneja 2 cortes, solo Final con 1 corte) y un panel de **Resumen de la clase** (Final Grade, Equivalencia cualitativa, Pass/Fail, Ranking, Horas de ausencia). Por defecto, al consultar, se selecciona la clase más reciente. Una clase sin Consolidado de notas (sin Estructura de calificación avanzada aplicada) muestra la fila igual, pero el detalle indica que no hay componentes disponibles.

### 17.2. Equivalencia cualitativa

Se reutiliza el **Rango de desempeño** ya existente (DS/DA/DBS/DBJ — Desempeño Superior/Alto/Básico/Bajo, sección 14.5): no se creó un catálogo nuevo de letras. La columna/campo "Equivalencia cualitativa" de la trayectoria y del detalle muestra ese mismo rango, calculado por el Consolidado de la clase.

### 17.3. Estado académico y Acción realizada

El **Estado académico** mostrado en cada fila es el estado **actual** del estudiante (Nuevo/Activado/Liberado/Aplazado, sección 11) — no existe (ni se reconstruye) un histórico de qué estado tenía exactamente en el momento de cursar cada clase, porque ese estado es un dato del Estudiante, no de cada Inscripción.

La **Acción realizada** (Promovido/Finalizado) y su Fecha vienen del registro de trazabilidad de Promoción/Finalización (sección 12.5) de la Inscripción de origen de cada fila; una fila sin ninguna acción registrada queda en blanco (en curso).

### 17.4. Observaciones

Las Observaciones de cada fila son las que están ligadas a esa Inscripción **y** esa Clase ofertada específicas (sección 7). Las observaciones que no están ligadas a ninguna clase en particular se agrupan aparte como "Observaciones generales del estudiante", solo en el PDF (17.5) — no se muestran en la pantalla, para no mezclarlas con el detalle de una clase concreta.

### 17.5. Descargar PDF

Botón **Descargar PDF** nuevo, junto a "Consultar historial académico". Genera un reporte propio (no el de transcripción estándar de Webkul, que sigue funcionando igual para quien lo necesite, portal del estudiante incluido) que agrupa la trayectoria por Programa, con el detalle de calificaciones de la clase más reciente y las observaciones generales del estudiante al final.

### 17.6. Permisos

La consulta y el PDF están disponibles únicamente para Officer/Admin — el mismo grupo que ya restringía este menú; se valida además explícitamente en el método que arma la información (no solo en la vista), para cubrir cualquier llamada que no pase por el menú.

### 17.7. No incluye (de esta tarea)

- Reconstruir un histórico real del Estado académico por clase/periodo — se usa el estado actual del estudiante (17.3).
- Un catálogo nuevo de Equivalencia cualitativa tipo letra (A/B+/C-) — se reutiliza el Rango de desempeño existente (17.2).
- Modificación de calificaciones, matrículas, asistencia u observaciones desde la vista de histórico: es únicamente de consulta.
- Certificados académicos y reportes financieros/operativos — corresponden a otras subtareas del mismo requerimiento padre (tarea 12405).

---

## 18. Reporte de Registros / Cursos desde Clases Ofertadas (tarea 12439)

Agrega la generación del **Reporte de Registros / Cursos** suministrado por el Colombo, reutilizando por completo la vista existente de **Clases ofertadas** (sección 9) como fuente de consulta y selección — no se crea ninguna pantalla ni proceso paralelo.

### 18.1. Cómo generarlo

**Dónde:** Gestión Educativa → Clases → **Clases ofertadas**.

El usuario consulta, filtra y agrupa con las herramientas estándar de Odoo (18.2), selecciona con el check de la izquierda uno, varios o todos los registros resultantes, y presiona el botón **Generar Reporte de Registros / Cursos** que aparece en la barra superior junto a "Activar seleccionadas" / "Inactivar seleccionadas" — visible solo para Officer/Admin. El archivo Excel se descarga de inmediato; la acción es de solo consulta/exportación y no modifica ningún registro.

### 18.2. Filtros y agrupaciones nuevos

Para que Sede, Programa, Fecha y Horario puedan usarse como criterio de búsqueda (no solo visualizarse en la lista), se agregaron al buscador de Clases ofertadas:

- **Sede** y **Programa** (18.3): ahora seleccionables directamente en el buscador, además de como agrupación.
- **Horario**: también disponible como campo de búsqueda propio, además de ya estar incluido en la búsqueda libre por texto (sección 9.3).
- **Fecha**: ya existían los filtros "Empezar desde" / "Terminar hasta" (rango de fechas) desde antes de esta tarea.
- **Agrupar por → Programa**: nueva opción, junto a las ya existentes (Materia, Nivel académico, Modalidad, Sede, etc.).

### 18.3. Campo nuevo "Programa"

**Dónde:** formulario de Clase ofertada, junto a Sede; también disponible como columna opcional en la lista.

Cada Clase ofertada puede indicar su Programa (mismo catálogo configurable "Tipo de programa" usado en la Solicitud y el Estudiante). Es independiente de si la clase tiene o no una Estructura de calificación avanzada aplicada (sección 14) — antes de esta tarea, el Programa solo podía conocerse para esas clases avanzadas (vía su Escala), dejando sin Programa a la mayoría. Si la clase sí tiene una Escala avanzada con Programa definido, se sugiere automáticamente ese valor al elegirla (sin sobreescribir una selección manual ya hecha); en cualquier otro caso se elige a mano.

### 18.4. Contenido del Excel

El archivo trae, antes de la tabla, un encabezado con Programa, Sede, Fecha (rango) y Horario (rango) de la selección — cuando los registros seleccionados corresponden a varios valores de un mismo dato (p. ej. dos Sedes), el encabezado los lista todos, separados por coma.

La tabla trae una fila por cada Clase ofertada seleccionada, agrupada por **Curso** (Nivel académico) con un renglón de subtotal (cantidad de clases, Cupos, Inscritos y Libres) al cerrar cada grupo, y un total general al final. Columnas: Curso, Horario, Fecha Ini, Fecha Fin, Profesor, Assistant Teacher, Libro, Salón, Cupos, Inscritos y Libres (**Libres = Cupos − Inscritos**). Toda la información se lee de la Clase ofertada y sus relaciones ya existentes (Nivel, Horario semanal, Docente, Docente asistente, Libro, matrícula) — nada se digita de nuevo. Un dato que no aplique a una clase (p. ej. sin Libro o sin Docente asistente) deja la celda vacía sin bloquear la generación del resto del archivo.

### 18.5. Permisos

Generar el reporte requiere **Officer o Admin** (mismo grupo que ya protege "Activar/Inactivar seleccionadas"); un usuario Staff no ve el botón y, aunque intente invocar la acción de otra forma, el sistema la rechaza igualmente.

### 18.6. No incluye (de esta tarea)

- Guardar o versionar los Excel generados dentro de Odoo más allá de la descarga directa (igual que el resto de exportaciones del módulo, p. ej. 16.3).
- Reportes Financieros (Clientes/Beneficios/Formas de pago) e Histórico Académico ampliado — corresponden a otras subtareas del mismo requerimiento padre (tarea 12405). El Reporte de Consecutivos ya se cubrió aparte (sección 19).

---

## 19. Reporte de Consecutivos desde Recibos de cobro (tarea 12447)

Agrega la generación del **Reporte de Consecutivos** suministrado por el Colombo, reutilizando por completo la vista existente de **Recibos de cobro** (sección 15.9) como fuente de consulta y selección — no se crea ninguna pantalla ni proceso paralelo. Es independiente del Libro, Folio y Consecutivo usados en certificados académicos (otra subtarea).

### 19.1. Cómo generarlo

**Dónde:** Gestión Educativa → Informes → **Recibos de cobro**.

El usuario consulta, filtra y agrupa con las herramientas estándar de Odoo, selecciona con el check de la izquierda uno, varios o todos los registros resultantes, abre el menú **Imprimir** (ícono de engranaje ⚙ junto al título de la lista, el mismo que trae Exportar/Eliminar registros) y elige **Imprimir Reporte de Consecutivos** — visible solo para Officer/Admin. El archivo Excel se descarga de inmediato; la acción es de solo consulta/exportación y no modifica ningún Recibo de cobro, factura, matrícula ni pago.

### 19.2. Contenido del Excel

El archivo trae, antes de la tabla, un encabezado con "REPORTE CONSECUTIVO", Fecha inicial y Fecha final (rango de fechas de creación de los recibos seleccionados), "Agrupamiento: Usuario" y la fecha/hora de generación.

Los registros se agrupan por **Usuario** (quien creó el Recibo de cobro), cada grupo con su propio renglón de encabezado de columnas, un **Subtotal** (Valor e Ingresos) al cerrar el grupo, y un **Total general** al final del archivo. Columnas por recibo: Factura (de la Factura asociada), Fecha (fecha y hora de creación del recibo), Estudiante (documento y nombre del Alumno), Cliente (contacto facturado en la Factura asociada), Fecha inicio / Fecha fin (del propio recibo), Cursos (Nivel académico más las Clases ofertadas cursadas en esa Inscripción), Beneficios (motivo y valor de cada registro de Beneficios/descuentos del recibo, sección 15.8), Observaciones (narración de la Factura asociada, si tiene), Valor (Valor total del recibo), Ingresos (Valor pagado) y Cuotas (N° de cuotas programadas, 0 si no es pago por cuotas). Un recibo sin Factura, sin Beneficios o sin Observaciones deja esas celdas vacías sin bloquear la generación del resto del archivo.

### 19.3. Permisos

Generar el reporte requiere **Officer o Admin** (mismo grupo que ya protege el menú de Recibos de cobro); un usuario Staff no ve la opción en el menú Imprimir y, aunque intente invocar la acción de otra forma, el sistema la rechaza igualmente.

### 19.4. No incluye (de esta tarea)

- Guardar o versionar los Excel generados dentro de Odoo más allá de la descarga directa (igual que el resto de exportaciones del módulo, p. ej. 18.6).
- Cualquier relación con Libro de Registro, Folio o Consecutivo de certificados académicos — es un reporte operativo/financiero independiente (otra subtarea).
- Reportes Financieros (Clientes/Beneficios/Formas de pago) e Histórico Académico ampliado — corresponden a otras subtareas del mismo requerimiento padre (tarea 12405).

---

## 20. Reportes Financieros de Matrículas desde Recibos de cobro (tarea 12450)

Agrega 3 reportes financieros suministrados por el Colombo, reutilizando por completo la misma vista de **Recibos de cobro** (sección 15.9 / 19) como fuente de consulta y selección — mismo patrón que el Reporte de Consecutivos (sección 19): sin vista ni asistente nuevos.

### 20.1. Cómo generarlos

**Dónde:** Gestión Educativa → Informes → **Recibos de cobro**.

El usuario consulta, filtra y agrupa con las herramientas estándar de Odoo, selecciona uno, varios o todos los registros, abre el menú **Imprimir** (ícono de engranaje ⚙ junto al título de la lista) y elige una de las 3 opciones nuevas (visibles solo para Officer/Admin, junto a la de Consecutivos):

- **Imprimir Reporte Clientes / Matrículas**
- **Imprimir Reporte Beneficios / Matrículas**
- **Imprimir Reporte Formas de Pago / Matrículas**

Cada una descarga de inmediato su propio Excel. Es de solo consulta/exportación: ninguna modifica Recibos de cobro, facturas, matrículas, beneficios ni pagos.

### 20.2. Encabezado común

Los 3 archivos comparten el mismo encabezado: "REPORTE FINANCIERO POR MATRICULAS", Programa, Sede, Fecha (rango) y Horario (rango) de las clases incluidas en la selección, y la fecha/hora de generación. Cuando la selección cubre un único Programa/Sede/Horario se muestra ese valor; si cubre varios, se listan todos separados por coma (mismo criterio que el Reporte de Registros/Cursos, sección 18).

### 20.3. Columnas comunes a los 3 reportes

Programa, Cursos, Fecha inicio, Fecha fin y Horario vienen de la Clase ofertada asociada al recibo (si el recibo no resuelve a ninguna clase, estas columnas quedan vacías sin bloquear la fila). No. de Identidad y Estudiante vienen del Alumno del recibo.

**Tipo** (Nuevos/Antiguos) y **Matrículas** no son campos que el usuario diligencia: se calculan solos.

- **Tipo**: "Nuevos" si ese recibo es el más antiguo de **todo** el historial del estudiante (sin importar cuáles recibos están seleccionados en este reporte); cualquier otro recibo del mismo estudiante aparece como "Antiguos".
- **Matrículas**: mes y año (en español) de la **fecha de inicio del propio recibo** — por eso dos estudiantes de la misma clase pueden mostrar un mes distinto en esta columna: cada uno refleja cuándo empezó a regir su propio recibo, no las fechas de la clase.

### 20.4. Reporte Financiero – Clientes / Matrículas

Una fila por Recibo de cobro seleccionado. Además de las columnas comunes: No. de Identidad y Cliente (del contacto facturado en la Factura asociada al recibo), Factura, Fecha (de la Factura) y Valor (Valor total del recibo). Al final, Subtotal y Total (suma de Valor sobre los registros incluidos).

### 20.5. Reporte Financiero – Beneficios / Matrículas

Una fila por cada beneficio o descuento aplicado al recibo (mismo registro de Beneficios/descuentos que ya trae el recibo, sección 15.8). Columnas propias: Nombre del beneficio y Valor (el monto descontado). Si el recibo no tiene ningún beneficio, aparece de todas formas con el nombre vacío y Valor en cero — la ausencia de beneficio no bloquea el reporte. Si tiene varios, aparece una fila por cada uno. Subtotal y Total suman solo la columna Valor de beneficios.

### 20.6. Reporte Financiero – Formas de Pago / Matrículas

Una fila por cada pago conciliado con la Factura del recibo. Columnas propias: Formas de pago (el medio usado en ese pago, p. ej. "Pago por WOMPI", "TJ. VISA Cr", o el nombre del diario cuando el pago se registró con un asiento manual de caja/banco), Factura, Fecha (del pago) y Valor (el monto de ese pago). Si la factura todavía no tiene ningún pago registrado, aparece de todas formas con Forma de pago vacía y Valor en cero. Si un mismo recibo se pagó con varios movimientos (p. ej. dos abonos con medios distintos), aparece una fila por cada uno. Subtotal y Total suman solo la columna Valor de pagos.

### 20.7. Permisos

Generar cualquiera de los 3 reportes requiere **Officer o Admin** (mismo grupo que ya protege el menú de Recibos de cobro y el Reporte de Consecutivos); un usuario Staff no ve las opciones en el menú Imprimir y, aunque intente invocar la acción de otra forma, el sistema la rechaza igualmente.

### 20.8. No incluye (de esta tarea)

- Un campo editable para "Tipo" o "Matrículas" — ambos se calculan siempre, no se pueden corregir a mano.
- Guardar o versionar los Excel generados dentro de Odoo más allá de la descarga directa.
- Cualquier cambio al Reporte de Consecutivos (sección 19) o al de Registros/Cursos (sección 18) — son reportes independientes que conviven en el mismo menú Imprimir.

---

## 21. Wizard de Generación de Certificados Académicos (tarea 12451)

Nueva funcionalidad dentro de **Gestión Educativa → Informes → Certificados**: un wizard que genera, en PDF, los certificados académicos del Colombo (Inglés Básico, Inglés Intermedio Adultos, Inglés Intermedio Adolescentes y Programa Avanzado), usando siempre la información académica ya registrada del estudiante.

### 21.1. Cómo generarlo

**Dónde:** Gestión Educativa → Informes → **Certificados** (única opción de menú, visible solo para Officer/Admin).

El wizard pide:

- **Programa / Módulo**, **Sede** — siempre.
- **Tipo de población** (Niños/Adolescentes/Adultos) y **Nivel** — solo si el Programa elegido **no** está marcado como "Programa Avanzado" (ver 21.5).
- **Clase ofertada** — solo si el Programa **sí** está marcado como Avanzado.
- **Modalidad de generación**: Individual o Grupal.
- **Estudiante(s)**: la lista se filtra sola a los que cumplen la combinación elegida (ver 21.2); no se puede escribir un estudiante que no aparezca ahí.
- **Intensidad horaria**, **Fecha de inicio/fin**, **Fecha de expedición**, **Lugar de expedición** — siempre manuales, el sistema nunca los calcula ni los asigna.
- **Libro, Folio y Consecutivo** — manuales, solo para los certificados que no son Programa Avanzado; en modalidad Grupal se puede elegir si son **comunes a todo el lote** o **individuales por estudiante** (tabla editable).

Al pulsar **Generar Certificado(s)** se descarga un único PDF (un certificado por estudiante seleccionado, en modalidad Grupal) y queda un registro de histórico por cada estudiante (ver 21.4).

### 21.2. Cómo se eligen los estudiantes

- **Certificados regulares** (no Avanzado): se listan los estudiantes con una Inscripción cuyo Programa, Tipo de población, Nivel y Sede coincidan exactamente con lo elegido en el wizard, y cuyo **Resultado académico sea Aprobado**.
- **Programa Avanzado**: se listan los estudiantes matriculados en la Clase ofertada elegida (sin filtrar por Resultado académico, porque este formato corresponde a cursos cortos independientes de la estructura de Nivel/Inscripción estándar).

### 21.3. Cómo se determina la plantilla (el usuario nunca la elige)

El tipo de certificado y su formato se infieren siempre de lo seleccionado, nunca de un campo propio:

| Elección en el wizard | Certificado |
|---|---|
| Programa normal + Tipo de población "Niños" | Inglés Básico |
| Programa normal + Tipo de población "Adultos" | Inglés Intermedio (texto "para Adultos") |
| Programa normal + Tipo de población "Adolescentes" | Inglés Intermedio (texto "para Adolescentes") |
| Programa marcado "Es Programa Avanzado" | Programa Avanzado (formato visual distinto, sin Libro/Folio/Consecutivo) |

En el certificado de Programa Avanzado, el **nombre del curso** es el campo "Título" de la Clase ofertada elegida, y el **Docente** que firma es el profesor asignado a esa misma clase — ninguno de los dos se vuelve a escribir a mano.

### 21.4. Consulta posterior (Libro, Folio, Consecutivo)

Cada certificado generado queda como un registro propio (no se pierde al cerrar el wizard):

- **Ficha del Estudiante → pestaña "Certificados"**: lista de solo lectura con todos los certificados de ese estudiante.
- Dentro del wizard, botón **"Ver histórico generado"**: abre la lista completa (todos los estudiantes).
- Cada registro tiene un botón **"Descargar PDF"** con su certificado (aunque se haya generado junto con otros en modalidad Grupal, cada estudiante conserva su propia copia descargable).

El Consecutivo queda guardado para consulta, pero **no se imprime** en el documento (ningún formato de referencia del Colombo lo muestra impreso); Libro y Folio sí se imprimen, en palabras y en número (p. ej. "Libro de Registro No. Uno (1)").

### 21.5. Configuración institucional por Sede

**Dónde:** Configuración → Académicos → **Configuración de Certificados** (Officer/Admin).

Un registro por Sede con: Lugar de expedición sugerido, el texto completo de Resolución institucional (uno para Básico/Intermedio, otro más corto para Avanzado) y el nombre/cargo de la Directora Ejecutiva y la Directora Académica que firman el certificado. Viene precargado con los datos ya usados en los formatos físicos de Norte y Centro; editable sin necesitar un desarrollo nuevo si cambia una resolución o una firma.

El catálogo "Programa" (Configuración → Académicos → Tipos de programa) tiene ahora un check **"Es Programa Avanzado (Certificados)"**: márquelo únicamente en el Programa que represente los cursos avanzados — es lo que activa el modo distinto del wizard (21.1).

### 21.6. Permisos

Igual que el resto de reportes de Informes: generar certificados, consultar el histórico y la Configuración de Certificados requiere **Officer o Admin**. Un usuario Staff no ve el menú "Certificados" ni "Configuración de Certificados".

### 21.7. No incluye (de esta tarea)

- Asignación o cálculo automático de Libro, Folio o Consecutivo — siempre son manuales, por diseño del requerimiento.
- Un catálogo editable de "Tipo de población": es una lista fija de 3 valores (Niños/Adolescentes/Adultos).
- Firma digital o códigos de verificación en el PDF.
- Reimpresión masiva de certificados ya generados — "Descargar PDF" reimprime uno a la vez, desde el histórico.

---

## Glosario rápido de decisiones (para no repreguntar)

- **¿Por qué "Sede" es un catálogo propio y no la Compañía?** En la primera versión se reutilizó `company_id` (la Compañía de Odoo), porque el módulo ya la usa para separar información en otros contextos. Se revirtió a pedido del cliente: usar la Compañía real trae implicaciones de multi-compañía (contabilidad, almacenes, reglas de registro) que no aplican a un dato puramente descriptivo como la sede de una clase o inscripción. `company_id` se conserva donde Odoo lo exige (es un campo técnico interno, p. ej. alimenta `observation_company_rule` en `security/ir_rule.xml`), pero ya no se le muestra al usuario — el nuevo catálogo `wk.school.colombo.sede` (sección 9.7) toma ese lugar en todas las vistas.
- **¿Por qué "Libro" es un Many2one a Productos filtrado por un check, y no el catálogo bibliotecario del módulo base?** El catálogo bibliotecario (`wk.books`) es de la funcionalidad de biblioteca, que la institución no usa, y nunca trae resultados reales. Atarlo directo a Productos sin filtro traería certificados, exámenes y demás ítems de venta mezclados; se agregó un Boolean nuevo ("¿Es libro?", `product.product.is_book_element`) como domain, siguiendo el mismo patrón ya usado en el módulo base para "Elementos de tarifa" (`is_fee_element`/`libray_element`), en vez de inventar un catálogo o campo de texto aparte.
- **¿Por qué la Escala básica no aparece en el selector "Escala de calificación (avanzada)" de la Clase?** Es intencional (14.6): ese campo es exclusivo de la estructura avanzada. Una Escala sin esa estructura se selecciona en el Nivel (`wk.school.grade`) o en la Materia (`wk.grade.subjects`), sin domain — no hace falta ningún cambio de código, solo usar el selector correcto.
- **¿Por qué los Nombres/Apellidos separados y los campos del aspirante no llegaban al Contacto?** Viajaban al Estudiante (`wizard/enroll_wizard.py`) desde el inicio, pero nunca se agregaron a `res.partner` ni al mapa de sincronización Estudiante→Contacto (`_SYNC_FIELD_MAP`). No es que "no se guardaran": se guardaban en el lugar equivocado para lo que el cliente necesitaba ver en Contactos.
- **¿Por qué el examen de clasificación se modela como una Clase más, con un check, en vez de un asistente o un modelo aparte?** Porque ya se calificaba como una Clase (con su propia Escala de un componente) antes de esta ronda de ajustes; la única pieza que faltaba era la propagación del nivel cualitativo (Comentarios) hacia la Inscripción, así que se amarró a esa misma Clase con un flag explícito en vez de duplicar el flujo de calificación.
- **¿Por qué "Deserción" es una etiqueta de asistencia y no un campo en la Inscripción?** El requerimiento de la tarea 12436 pide explícitamente que la condición se determine "a partir de la etiqueta registrada en el proceso de asistencia", y ese mecanismo (`wk.attendance.tag`, por sesión) ya existía y ya se usaba para "Llegada tarde" (14) — agregar un campo aparte en la Inscripción habría sido un segundo lugar para marcar lo mismo, sin que el requerimiento lo pidiera.
- **¿Por qué el Reporte de Distribución y el de Retención (Excel) filtran por Programa y no por Nivel académico directamente?** El campo "Programa" (`wk.school.colombo.program.type`) vive en la Escala de calificación aplicada a cada clase (`grading_scale_id.program_type_id`, 14.5), no en el Nivel académico — es el agrupador que ya usa el Consolidado (`program_type_id`, columna de la lista de Consolidados), y es el que permite incluir automáticamente "todos los niveles, módulos, clases y horarios" del Programa sin seleccionarlos uno por uno, tal como pide el requerimiento.
- **¿Por qué "Tipo" y "Origen" son campos distintos en Observaciones si parecen decir lo mismo?** Origen es técnico y automático (de qué pantalla vino la nota). Tipo es una clasificación de negocio, editable, independiente. El requerimiento los pide como dos datos separados.
- **¿Por qué toda observación necesita una Inscripción?** Porque así lo muestra la evidencia del cliente (la referencia de una observación es el número de la inscripción) y porque sin ese ancla no habría forma de saber a qué proceso académico pertenece cada nota.
- **¿Por qué el motivo de restricción está dentro de la pestaña Disciplina y no en un grupo aparte?** Porque el criterio de aceptación del requerimiento lo pide explícitamente así.
- **¿Los checks de "ocultar calificaciones" hacen algo?** Desde la sección 14, sí, pero solo para clases/estudiantes con una estructura de calificación avanzada aplicada: ocultan la nota en el portal igual que desmarcar "Visible en portal" del Consolidado. Para una Escala estándar (sin esa estructura), siguen sin ningún efecto.
- **¿Por qué el umbral de duplicados es "2 de 4 criterios" y no una coincidencia exacta o una IA de similitud?** Porque el requerimiento pide explícitamente que un solo dato en común no se asuma como duplicado (evita falsos positivos con nombres comunes), pero tampoco exige una coincidencia perfecta (que dejaría pasar errores de digitación). La comparación de nombre es por palabras normalizadas (sin tildes, sin conectores), no por similitud difusa tipo trigramas, para no depender de extensiones de PostgreSQL que pueden no estar habilitadas en todas las instalaciones.
- **¿Por qué solo Officer/Admin puede confirmar "crear nuevo" cuando hay coincidencias?** Es una decisión de negocio confirmada con el cliente: Staff puede vincular a un estudiante ya existente sin supervisión, pero crear un registro nuevo a pesar de una posible coincidencia requiere una segunda revisión.
- **¿Por qué el Resultado académico depende de un simple "¿Aprueba?" y no de un cálculo de notas?** Porque el módulo de calificaciones no produce hoy ningún resultado Pass/Fail -esa es una subtarea aparte, todavía sin construir (ver "No incluye")-. Sin un indicador mínimo ningún estudiante podría llegar nunca a "Aprobado", así que se construyó el más simple posible para no bloquear Promoción/Finalización mientras se desarrolla el cálculo real.
- **¿Por qué "No aprobado" se decide con que una sola Asignatura repruebe, y no con un promedio?** Es la interpretación más literal de "Pass/Fail" como resultado único consolidado, sin inventar una fórmula de promedio que el requerimiento no pide construir. Si no coincide con el criterio real de la institución, es un ajuste puntual sobre `_compute_academic_result` (student_enrollment.py).
- **¿Por qué "Promover seleccionados" quedó en la lista de Inscripciones y no en el dashboard de calificaciones?** El dashboard de calificaciones es una pantalla OWL personalizada sin selección múltiple nativa; la lista de Inscripciones ya la tenía, junto con la acción original "Promote Students" que se reemplazó.
- **¿Por qué la Finalización usa una pantalla de confirmación propia en vez del `confirm=` nativo de Odoo?** Para mantener la misma experiencia que el asistente de Aplazar (sección 11.2): un texto y botones controlados por el propio módulo, no el diálogo genérico de Odoo.
- **¿Por qué la estructura avanzada es un check en la Escala y no un modelo totalmente aparte?** Para reutilizar el mismo catálogo, el mismo selector y la misma relación Materia→Escala que ya existía, y para que una escala pueda alternar entre uno u otro mecanismo sin migrar datos. La condición es excluyente a propósito: con el check activo, el cálculo GPA estándar se desactiva solo para esa Escala.
- **¿Por qué un componente puede tener peso en Midterm y en Final a la vez, en vez de ser dos filas separadas?** Porque el documento del cliente pide explícitamente que una misma calificación (p. ej. Quiz 1) se reutilice en ambos cortes sin que el docente la registre dos veces. Una sola fila con dos columnas de peso (0 = no participa en ese corte) logra eso sin duplicar la actividad ni el dato.
- **¿Por qué la nota de un componente no se normaliza contra ningún "puntaje máximo" distinto de 100?** El requerimiento pide que la calificación registrada por el docente sea el "valor académico directo del componente, sin conversiones" — se usa tal cual, con 100 como puntaje máximo por defecto en las actividades de una estructura avanzada.
- **¿Qué pasa si falta la calificación de un componente con peso mayor que 0?** La línea queda marcada "Incompleto": no entra al ranking y bloquea la confirmación de ese corte. Evita confirmar (y dejar como histórico) un resultado calculado sobre información parcial.
- **¿Por qué "Programa" se agregó como campo propio y editable en la Clase ofertada (18.3), en vez de reutilizar `grading_scale_id.program_type_id` como hace el reporte de la sección 16?** Esa relación solo existe para clases con Estructura de calificación avanzada aplicada (una minoría); el Reporte de Registros/Cursos debe funcionar para **cualquier** Clase ofertada seleccionada, con o sin esa estructura. Un Many2one directo (mismo patrón que Sede/Modalidad/Libro) cubre el 100% de los casos; el onchange solo evita doble captura cuando la clase sí tiene la Escala avanzada.
- **¿Por qué el ranking y el Pass/Fail se recalculan con un botón "Actualizar" y no en vivo con cada clic?** El ranking depende de **todos** los compañeros de clase a la vez (no es un cálculo por estudiante aislado); encadenar ese tipo de cálculo de grupo a través de cómputos automáticos entre hermanos de una misma lista es frágil. Las notas de cada componente sí se recalculan solas; "Actualizar" (y la confirmación, que siempre refresca antes de congelar) garantiza que ranking, Pass/Fail y horas de ausencia queden al día.
- **¿Por qué el Consolidado no se ve como una grilla con una columna por cada componente?** Ver "No incluye" al inicio del documento: se priorizó que el cálculo fuera correcto y verificable (incluida la reproducción exacta de los ejemplos numéricos del requerimiento) sobre construir un widget de columnas dinámicas; el detalle por componente de cada estudiante existe y alimenta los reportes, pero se consulta por estudiante.
- **¿Por qué "Visible en portal" oculta la nota mostrándola en 0 en vez de quitar la fila de la Materia?** Es el mismo valor que ya usa el portal para una Materia que todavía no tiene calificación (no roto ningún comportamiento existente del portal), y evita construir una plantilla aparte solo para este caso.
- **¿Por qué el Reporte de Consecutivos y los 3 Reportes Financieros aparecen en el menú Imprimir nativo (icono ⚙, junto a Exportar/Eliminar registros) y no como botones propios en la barra?** Primera versión de ambas tareas (12447/12450) usó un botón en `<header>` (patrón de la tarea 12439), porque en ese momento se asumió que el menú Imprimir nativo no admitía una acción propia — una conclusión equivocada, corregida a pedido del cliente tras ver la captura de referencia. Sí se admite: un `ir.actions.report` con `report_type="xlsx"` (vía el módulo comunitario `report_xlsx`, ya vendido en `produccion/19.0` y usado por `account_report`/`stock_report`) y `binding_model_id`/`binding_type="report"` sobre `wk.fee.slip` lo agrega automáticamente a ese menú, igual que cualquier otro reporte de impresión de Odoo (mismo mecanismo ya usado en este módulo para PDF, p. ej. `report/academic_history_report.xml`). La generación del Excel (`_wk_build_*_workbook` en `models/fee_slip.py`) no cambió; solo cambió cómo se invoca — ver `report/fee_slip_financial_reports.py`/`.xml`.
- **¿Por qué "Valor" = Valor total e "Ingresos" = Valor pagado en el Reporte de Consecutivos, y no Saldo pendiente?** El documento no define estas dos columnas de forma explícita, solo dice que deben "construirse utilizando la información existente" (sección 2.11); confirmado con el usuario, es la lectura más directa: Valor es lo facturado y Ingresos es lo efectivamente recaudado hasta la fecha de generación.
- **¿De dónde sale la columna "Observaciones" del Reporte de Consecutivos si el Recibo de cobro no tiene un campo de notas propio?** Se usa la narración (`account.move.narration`) de la Factura asociada al recibo, confirmado con el usuario — es el único texto libre ya existente en Odoo ligado a esa operación. Un recibo sin factura o cuya factura no tenga narración deja la celda vacía.
- **¿De dónde salen "Tipo" (Nuevos/Antiguos) y "Matrículas" en los Reportes Financieros (sección 20) si no son campos de Odoo?** No existía ningún campo equivalente; confirmado con el usuario antes de codificar (mismo criterio que las ambigüedades de los reportes 18/19): "Tipo" se calcula comparando el recibo contra todo el historial del estudiante (el más antiguo = Nuevos), y "Matrículas" es el mes/año del propio `date_from` del recibo — no del período académico de la Clase, porque los 3 Excel de referencia del cliente muestran valores distintos de "Matrículas" para estudiantes de la misma clase con las mismas fechas.
- **¿Por qué los 3 Reportes Financieros (sección 20) usan como máximo 1 Clase por recibo, en vez de una fila por cada Clase cuando un recibo resuelve a varias?** El Reporte de Consecutivos (19) sí combina varias clases en una sola celda de texto porque "Cursos" ahí es un campo descriptivo; en los Reportes Financieros, Programa/Cursos/Horario son columnas propias por fila, así que repetir la fila por cada clase duplicaría también el Valor/Beneficios/Pagos de ese mismo recibo en el Subtotal y el Total — un error de dinero que el documento no pide ni ningún caso de los 3 Excel de referencia muestra (todos tienen una sola clase por fila).
- **¿Por qué "Matrículas" (mes/año) se genera siempre en español, sin importar el idioma del usuario que presiona el botón?** El formato es fijo, definido por el documento de referencia del cliente (siempre en español) — no es un texto de interfaz que deba traducirse según el idioma de cada usuario. La primera versión usaba el idioma del usuario actual y, al verificarlo con un usuario en inglés, el mes salió en inglés ("September" en vez de "Septiembre"); se corrigió para usar español de forma fija.
