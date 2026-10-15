# Gestión Educativa — Centro Colombo Americano

## Qué es este documento

Explica, a nivel funcional (sin código), todo lo que se agregó o cambió en el módulo académico. Está pensado para que un consultor, tester o el propio cliente pueda seguir el flujo completo del proceso — Solicitud → Validación de duplicados → Inscripción → Estudiante → Clase Ofertada — y entender qué hace cada campo o pantalla nueva, sin ambigüedad.

Cubre, hasta ahora, **8 de las 10 subtareas** en las que se dividió el requerimiento general del Centro Colombo Americano:

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
- Generación de certificados para estudiantes Finalizados (ver sección 12.6) — la consulta de Promovidos/Finalizados deja la información lista, pero no genera ningún documento.

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
| Sede | Compañía (ver nota abajo) | Sí (ya lo era) |
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

> **Nota sobre "Sede":** el requerimiento pedía un campo configurable para "Norte" y "Centro". Se decidió **reutilizar el campo de Compañía** que Odoo ya usa para separar la información por sede en todo el módulo (Clases, Inscripciones, etc.), en vez de crear un catálogo nuevo aparte. Si en tu instalación solo existe una compañía, este campo no se ve — hay que crear "Norte" y "Centro" como compañías en Ajustes → Empresas para que aparezca el selector.

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
- Todos los campos nuevos de la Solicitud (Tipo de programa, municipios, tipo de persona, contacto, etc.) se copian al Estudiante.
- Los acudientes cargados en la Solicitud aparecen también en el Estudiante (es el mismo registro, no una copia).
- Si la Solicitud tenía un comentario, se convierte en la primera Observación del Estudiante.

### Opción B — Vincular a un estudiante que ya existe

Mismo comportamiento, con una diferencia importante: **solo se completan los campos que el estudiante todavía tenía vacíos**. Si el estudiante ya tenía, por ejemplo, el Estado civil diligenciado, ese dato **no se sobrescribe** con lo de la nueva solicitud — se respeta la información que el estudiante ya tenía. Los acudientes de la nueva solicitud sí se agregan siempre.

---

## 5. La ficha del Estudiante

**Dónde:** Gestión Educativa → Estudiantes.

### 5.1. Encabezado general

Todos los campos de la Solicitud llegan aquí (persistencia). Además:

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
- **Modalidad**: Sabatino / Diario / Vacacional (ver sección 9.1).
- **Assistant Teacher / Docente asistente**: es el mismo campo "Profesores de Secundaria" que el módulo ya traía, pero que una personalización anterior había ocultado. Ahora vuelve a ser visible, con este nuevo nombre. Permite seleccionar uno o varios docentes asistentes.
- **Libro**: el libro estándar asignado a esa clase (se propone automáticamente en las Inscripciones del mismo Grado/Sección).
- **Horario** y **Salón**: resúmenes de solo lectura, calculados a partir de las líneas cargadas en la pestaña "Horario semanal" — no hay que diligenciarlos aparte.
- **Fecha de inicio / Fecha de finalización**: mismos campos de siempre, solo se corrigió su nombre (antes decían, por una mala traducción de Odoo, "Empezar desde" / "Terminar hasta").
- **Sede**: el mismo campo de Compañía, ahora visible para todos los perfiles.

### 8.2. Pestaña Observaciones

Ver sección 7 — aquí es donde se registran las notas "durante la clase".

### 8.3. Lista de Clases Ofertadas

Columnas visibles por defecto: Fecha de inicio, Fecha de finalización, Clase ofertada, Sede, Nivel académico, Horario, Salón, Docente, Cupo, Total matriculados, Estado, Clase activa. Columnas activables (botón de engranaje al final de la tabla): Sección, Sesión, Materia, Assistant Teacher, Libro, Modalidad.

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

1. **Datos generales** (aplican a todas las clases que se van a crear en este proceso): Programación académica (Año académico), Modalidad (Sabatino/Diario/Vacacional), Sede, Periodo académico (Término).
2. **Clases a crear**: una tabla donde se agrega una línea por cada Clase ofertada que se quiere crear, con botón **"Agregar una línea"**. Cada línea tiene: Nivel, Módulo (filtrado al Nivel elegido y a las Asignaturas activas — ver 9.1), Docente principal, Docente asistente, **Día**, Horario, Salón, Cupo, Fecha de inicio, Fecha de finalización (precargadas con las del Periodo académico elegido, pero editables por línea), Libro, y un interruptor **Activa**.

   > Día, Horario y Salón de cada línea **sí se guardan como el Horario semanal real** de la clase que se crea (ver sección 10) — dejaron de ser solo de referencia en la subtarea de Validación de cruces, precisamente para poder detectar cruces reales antes de confirmar la creación masiva.

Al presionar **"Crear clases"**:

- El sistema valida **todas** las líneas antes de crear nada: cupo mayor a 0, fecha de inicio no posterior a la de finalización, campos obligatorios completos, y que ninguna línea se cruce en Docente o Salón —ni con otra línea del mismo proceso, ni con una Clase ofertada ya existente— (ver sección 10). Si algo falla, se muestra el mensaje identificando exactamente cuál línea y por qué, y **no se crea ningún registro** — se corrige y se vuelve a intentar.
- Si todo es válido, se crea **una Clase ofertada independiente por cada línea** (nunca un único registro que las agrupe), cada una con los datos generales del proceso, los propios de su línea, y su línea real de Horario semanal ya cargada — misma estructura que una clase creada individualmente.
- Al terminar, se abre la lista de Clases Ofertadas mostrando únicamente las recién creadas.

El formulario individual de creación (botón "Nuevo" en Poblar Clases) **sigue disponible sin cambios**, para cuando solo se necesita crear una clase.

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
| **Staff** (docentes) | Todo lo anterior, **excepto**: el check y motivo de restricción del estudiante; crear/editar/desactivar Tipos de programa (solo los puede leer/seleccionar); el menú de auditoría de Observaciones (pero sí puede crear observaciones desde Inscripción y Clase); confirmar "Ninguna coincidencia, crear nuevo" en la pantalla de posibles duplicados (sección 3) — sí puede elegir un registro existente de esa misma pantalla; activar/inactivar Asignaturas del nivel, activar/inactivar Clases Ofertadas (individual o masivamente), la creación masiva de Clases Ofertadas, y aplazar a un estudiante (sección 11.2); Promocionar ahora, Promover seleccionados y la consulta de Promovidos/Finalizados (sección 12) |
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
- **Class List**: nombre e identificación de los estudiantes de la clase, con tres botones de variante — Todos, Pass y Fail (para el cierre de curso).
- **Distribución por Desempeño**: agrupa a los estudiantes de la clase por Rango de desempeño (de mayor a menor Nota mínima, igual que en la Escala), con cantidad y porcentaje por rango, y el listado de estudiantes (con su Final Grade) dentro de cada uno. Los que aún no tienen un rango asignado (resultado pendiente) quedan en un grupo "Sin clasificar" al final.

Los tres reportes leen siempre la información ya consolidada (el histórico congelado si el corte está confirmado, el cálculo en vivo si no) — nunca piden un cálculo manual.

---

## Glosario rápido de decisiones (para no repreguntar)

- **¿Por qué "Sede" es la Compañía y no un catálogo nuevo?** Porque el módulo ya usa la Compañía para separar toda la información por sede (Clases, Inscripciones, reglas de acceso). Crear un catálogo aparte hubiera duplicado ese concepto.
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
- **¿Por qué el ranking y el Pass/Fail se recalculan con un botón "Actualizar" y no en vivo con cada clic?** El ranking depende de **todos** los compañeros de clase a la vez (no es un cálculo por estudiante aislado); encadenar ese tipo de cálculo de grupo a través de cómputos automáticos entre hermanos de una misma lista es frágil. Las notas de cada componente sí se recalculan solas; "Actualizar" (y la confirmación, que siempre refresca antes de congelar) garantiza que ranking, Pass/Fail y horas de ausencia queden al día.
- **¿Por qué el Consolidado no se ve como una grilla con una columna por cada componente?** Ver "No incluye" al inicio del documento: se priorizó que el cálculo fuera correcto y verificable (incluida la reproducción exacta de los ejemplos numéricos del requerimiento) sobre construir un widget de columnas dinámicas; el detalle por componente de cada estudiante existe y alimenta los reportes, pero se consulta por estudiante.
- **¿Por qué "Visible en portal" oculta la nota mostrándola en 0 en vez de quitar la fila de la Materia?** Es el mismo valor que ya usa el portal para una Materia que todavía no tiene calificación (no roto ningún comportamiento existente del portal), y evita construir una plantilla aparte solo para este caso.
