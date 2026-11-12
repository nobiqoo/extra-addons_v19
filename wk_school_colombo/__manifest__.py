# -*- coding: utf-8 -*-
{
    "name": "Gestión Educativa - Colombo Americano",
    "summary": "Personalizaciones de Gestión Educativa para el Centro Colombo Americano",
    "description": """
        Personalizaciones del módulo Education Management System (Webkul)
        para el Centro Colombo Americano:
        - Oculta el menú de Transporte y sus submenús.
        - Oculta los botones de transporte y el grupo de detalles de
          transporte en el formulario del estudiante.
        - Permite marcar la clase como hecha el mismo día en que finaliza,
          controlado por un parámetro en Ajustes (tarea 11140).
        - Captura nombres, apellidos y documento en la solicitud de inscripción
          y valida la duplicidad de contactos y estudiantes por tipo y número
          de identificación al inscribir (tarea 11151).
        - Retira la obligatoriedad de la fotografía en la solicitud de
          inscripción y en el estudiante (tarea 11152).
        - Ajusta las etiquetas y traducciones del módulo académico al lenguaje
          de la institución (i18n/es_CO.po, tarea 11155).
        - Permite evaluar actividades sin entrega digital previa (exámenes
          orales, presentaciones, participación en clase), controlado por un
          interruptor en cada actividad (tarea 11156).
        - Oculta el campo "Profesores de Secundaria" en el formulario y en el
          buscador de la clase académica, conservándolo en el modelo y en las
          reglas de registro que lo usan (tarea 11174). Las reglas de
          wk.school.class, wk.class.assignment, wk.student.assignment y
          wk.class.timetable evalúan ese campo dentro de un OR junto a
          teacher_id, por lo que ocultarlo no altera el acceso del profesor
          titular; solo deja de poder asignarse profesores secundarios desde
          la interfaz, que es el comportamiento solicitado.
        - Permite asignar actividades cuya fecha de inicio y fecha límite son
          iguales, es decir, programadas para un solo día (tarea 11238). Se
          admite "No. de días" igual a 0 y se conserva el bloqueo cuando la
          fecha límite es anterior a la de inicio.
        - Agrega el submenú "Tarifas de cursos" dentro del menú Clases, con un
          acceso de solo consulta a los mismos elementos de tarifa de
          Configuración (tarea 11243). La acción filtra por elemento de tarifa
          y desactiva crear, editar, eliminar, duplicar e importar; el menú
          original de Configuración conserva su comportamiento y permisos.
        - Simplifica la interfaz del módulo académico ocultando lo que no
          aplica a la institución (tarea 11292): la pestaña "Library Fine" del
          estudiante, los menús "Quiosco de asistencia", "Tiempo libre",
          "Perfil" (dentro de Mi perfil) y "Tarifas de cursos" —este último
          agregado por la tarea 11243—, y la columna "Valor para calcular el
          promedio" en las líneas de la actividad asignada y en el asistente de
          evaluación. Los menús se desactivan para todos los perfiles; sus
          acciones y campos se conservan y se siguen usando en los cálculos,
          los reportes y las rutas de origen. Tras las pruebas funcionales, el
          menú "Tarifas de cursos" vuelve a estar activo y se restringe al
          grupo Officer: el administrador lo conserva por implicación de
          grupos y los maestros, que solo pertenecen a Staff, dejan de verlo.
        - Traduce al español la etiqueta "Exento" y los términos de pago
          "Anual" y "Personalizado" —en la inscripción y en el asistente de
          generación de tarifas—, y reescribe tres mensajes de validación de
          Webkul que no eran traducibles por usar f-strings dentro de _()
          (tarea 11292): solape de ubicación en el horario semanal, inscripción
          duplicada por nivel y falta de acceso al portal al confirmar el
          recibo de tarifas. En los tres casos se conserva la lógica original
          de la validación y solo cambia el texto del mensaje.
        - Flexibiliza inscripción, evaluación y facturación (tarea 11293), con
          el comportamiento estándar como valor por defecto:
          * "Permitir múltiples inscripciones activas" (Ajustes, inactivo):
            deja que un estudiante tenga varias inscripciones en curso a la
            vez, bloqueando solo la segunda en el mismo nivel académico. Como
            "Matrícula actual" y "Nivel actual" son campos de un solo valor,
            se recalculan con la inscripción en curso más reciente; el cálculo
            original de Webkul les asignaba todas y la segunda inscripción no
            se podía guardar.
          * Numeración de la inscripción: al confirmar se asigna el
            consecutivo de la secuencia "enrollment.form" en cualquier idioma.
            El original comparaba el nombre contra el literal "New" mientras
            el valor por omisión del campo es la traducción de esa palabra,
            así que en español la inscripción se quedaba llamándose "Nuevo" y
            nunca recibía número. Las inscripciones confirmadas antes de este
            ajuste conservan el nombre que tengan.
          * "Permitir facturación sin usuario portal" (Ajustes, inactivo):
            confirma y factura el recibo de tarifas sin exigir acceso al
            portal, sin crear usuarios automáticamente.
          * "¿Tiene actividades de evaluación?" (por clase ofertada, activo):
            al desactivarlo la clase se gestiona solo con sesiones y
            asistencia, sin exigir tipos de actividad, ponderación del 100 %
            ni actividades asignadas para marcarla como hecha. Se define al
            crear la clase y después no puede cambiarse.
          * Lista de precios en las líneas del resumen de tarifas: se propone
            la del contacto del estudiante y, cuando esa lista define un
            precio para el concepto de cobro, la tarifa se toma de ahí; si no
            hay regla se conserva el valor de la estructura de tarifas.
        - Creación, ajuste y parametrización de campos para la gestión
          académica: catálogo configurable de "Tipo de programa"
          (Configuración -> Académicos); campos generales del estudiante y de
          la solicitud (municipio de expedición/origen, tipo de persona,
          estado civil, nivel de formación, idioma nativo, ocupación actual,
          barrio, correo DIAN independiente, edad calculada) organizados en
          las pestañas Ubicación, Contacto, Acudiente y Comentarios de la
          solicitud, con persistencia automática hacia el estudiante al
          inscribir; lista de Acudientes (uno a muchos) en solicitud y
          estudiante; libro y examen de clasificación en la inscripción;
          histórico único de Observaciones (wk.school.colombo.observation)
          con pestañas propias en Inscripción, Clase Ofertada y Estudiante;
          restricción del estudiante (check + motivo) visible solo para
          Officer/Admin, con el motivo dentro de la pestaña Disciplina;
          "Assistant Teacher" (el campo "Secondary Teachers" vuelve a
          mostrarse, relabelado); campo "Clase activa" y "Libro" en la Clase
          Ofertada; y placeholders de visibilidad de calificaciones
          (individual y grupal) sin lógica asociada, que desarrollará la
          subtarea de estructura de calificación. No incluye validación de
          duplicados, cruces académicos, cálculo de calificaciones,
          promoción/reasignación ni automatizaciones de facturación: esos
          comportamientos corresponden a sus propias subtareas.
        - Estructura de calificación avanzada para la operación académica de
          Inglés (subtarea 8): check "Habilitar estructura de calificación
          avanzada" en la Escala de calificación, con componentes y
          ponderaciones configurables por corte (1 o 2: Midterm/Final),
          equivalencias cualitativas de Class Performance, criterios de
          Class Performance, rangos de desempeño y parámetros de la regla
          de ausencias; aplicación de la estructura a la Clase ofertada
          (botón "Aplicar estructura de calificación") y herencia automática
          del Componente desde "Asignar tarea" hasta la evaluación; registro
          directo de la calificación por el docente (sin conversión por
          rangos de la Escala estándar) y evaluación de Class Performance
          por criterio con cálculo automático del promedio; horas de
          ausencia y observaciones desde "Marcar Asistencia"; nuevo
          Consolidado de notas (menú Maestros) con cálculo automático de
          Midterm/Final Grade, ranking, Pass/Fail (nota mínima + regla de
          ausencias) y rango de desempeño; confirmación por corte con
          histórico congelado, bloqueo/habilitación de edición al docente, y
          publicación individual/masiva de notas en el portal del
          estudiante; reportes Midterm, Final y Class List (con variantes
          Pass/Fail) desde el Consolidado.
        - Pago por cuotas y tabla de amortización (tarea 11856): check
          "Pago por cuotas" en "Generar recibos de tarifas" (fuerza Plazo de
          pago Personalizado y Entrega = 1), con monto inicial, número de
          abonos, periodicidad y vista previa editable de cuotas antes de
          confirmar. El acuerdo genera un único recibo y una única factura
          por el valor total, con los apuntes contables fragmentados por
          fecha de vencimiento (un término de pago a medida por acuerdo).
          "Registrar abono" reutiliza el asistente estándar de pagos de
          Odoo apuntado a la cuota elegida; un pago mayor al saldo de esa
          cuota se aplica automáticamente a las siguientes cuotas, sin
          recalcular fechas ni valores programados. Tabla de amortización
          disponible en Inscripción → Resumen de tarifas (Cuota, Fecha de
          vencimiento, Valor programado, Valor pagado, Saldo, Estado,
          Factura, Acción). "% Descuento" por concepto de cobro en Resumen
          de tarifas. Adaptador ligero de beneficios/cupones reutilizando el
          catálogo estándar de programas de fidelización de Odoo (código,
          descuento por porcentaje o monto fijo), aplicado como línea
          independiente del recibo, con registro de trazabilidad. Reporte
          "Recibos de cobro" ampliado con columnas del acuerdo de pago.
          Tirilla de pago básica imprimible desde el registro de pago.
        - Ronda de ajustes post-prueba del requerimiento de campos
          académicos: Sede (company_id) siempre visible y seleccionable en
          Aplicaciones y en la Clase ofertada, sin importar el número de
          compañías configuradas; columnas de "Clases ofertadas" reordenadas
          (Fecha de inicio, Clase ofertada, Sede, Nivel académico, Horario,
          Salón primero) y "Estado" oculto por defecto (sigue disponible como
          columna opcional); asistente de creación masiva de clases con
          Escala de calificación avanzada por línea (se aplica
          automáticamente al crear); campo "Libro" como texto libre en vez de
          Many2one al catálogo bibliotecario (no usado por la institución);
          catálogo configurable de Modalidad (Configuración -> Académicos),
          en reemplazo del Selection fijo; los campos generales del
          aspirante (estado civil, nivel de formación, idioma nativo,
          municipio de expedición, teléfono fijo, etc.) y los nombres y
          apellidos separados ahora también se sincronizan hacia el Contacto
          del estudiante, no solo hacia el Estudiante; y propagación
          automática del comentario del Consolidado hacia "Resultado examen
          de clasificación" de la Inscripción, exclusiva de la Clase marcada
          como examen de clasificación.
        - Tirilla de pago completa (tarea 12458): formato térmico angosto
          (institución, NIT, comprobante, fecha/hora, estudiante, clase
          -programa, nivel, horario, profesor, salón, libro- cuando aplica,
          concepto, total, forma de pago, cuotas pendientes, observaciones y
          texto legal configurable en Ajustes). Botón "Imprimir Tirilla"
          junto a "Ver pago" en la Tabla de amortización y junto a "Ver
          factura" en el Recibo de cobro de pago único; cada pago conserva
          su propia tirilla y puede reimprimirse sin afectar el pago, la
          factura ni la tabla de amortización.
        - Ajuste y ampliación de Reportes Académicos (tarea 12436): expone
          desde Informes los reportes que el Consolidado de notas ya
          construía en la subtarea 8. Botón "Generar Class List" en
          Informes → Hoja de calificaciones, con wizard de columnas
          opcionales (Notas, Factura, Teléfono, Celular, Correo
          electrónico) sobre el Class List existente, ahora con encabezado
          completo (Programa, Nivel, Módulo, Profesor, Assistant teacher,
          Libro, Horario, Salón, Fecha, Total de estudiantes). Botón
          "Imprimir Reporte Individual del Estudiante" en Informes →
          Boleta de calificaciones (menú Imprimir nativo), con un reporte
          nuevo que combina Midterm y Final en un solo PDF cuando la
          estructura usa 2 cortes, incluyendo la tabla de equivalencia con
          el Marco Común Europeo cuando el Tipo de programa la tiene
          habilitada. Nueva opción "Reportes de Análisis Académico" en
          Informes, con wizard (Tipo de reporte/Periodo académico/
          Programa/Sede) que genera en Excel el Reporte de Distribución
          por Desempeño y el Reporte de Retención/Promoción/Pérdida/
          Deserción, agrupados por Programa (incluye automáticamente
          todos los niveles, módulos, clases y horarios asociados); la
          condición de Deserción se determina por la etiqueta de
          asistencia "Deserción" (nueva, mismo mecanismo que "Llegada
          tarde"), no por horas de ausencia. Todos los reportes leen
          siempre la información ya consolidada, sin recalcular notas,
          Pass/Fail ni rango de desempeño. Corrige además un bug
          preexistente de Webkul en Informes → Hoja de calificaciones →
          "Consultar calificaciones" ("Expected singleton" en cualquier
          clase con Estructura de calificación avanzada cuando dos o más
          componentes comparten el mismo Tipo de actividad base), detectado
          al probar esta tarea en vivo; esa pantalla sigue sin mostrar las
          notas reales de una clase con estructura avanzada (lee un campo
          que esa estructura no usa), para eso están el Consolidado, la
          Boleta de calificaciones y el Class List.
        - Ajuste y ampliación del Histórico Académico del Estudiante (tarea
          12438): la pantalla existente Informes → Historial académico ya
          no se limita a una Programación académica -"Consultar historial
          académico" trae ahora TODA la trayectoria del estudiante
          (todos los programas, periodos, niveles/módulos y clases
          cursadas), leyendo siempre el Consolidado de notas, el Resultado
          académico y la Promoción/Finalización ya existentes, sin
          recalcular nada. Al seleccionar una fila de la trayectoria se
          muestra debajo el detalle de calificaciones de esa clase
          (componentes de Midterm/Final según corresponda, más un resumen
          con Final Grade, Equivalencia cualitativa -el Rango de desempeño
          ya existente-, Pass/Fail, Ranking y horas de ausencia); por
          defecto se muestra la clase más reciente. Botón "Descargar PDF"
          nuevo en la misma pantalla, con un reporte propio que agrupa la
          trayectoria por Programa y agrega las observaciones generales del
          estudiante -sin tocar el reporte ni el portal de transcripción
          estándar de Webkul, que siguen funcionando igual-. Mismos
          permisos Officer/Admin que ya protegían este menú.
        - Reportes de "Informes → Recibos de cobro" vía menú Imprimir
          nativo (tareas 12447 y 12450): el Reporte de Consecutivos y los
          3 Reportes Financieros de Matrículas (Clientes, Beneficios,
          Formas de Pago) se generan desde el engranaje ⚙ de la lista
          sobre los recibos seleccionados (uno, varios o todos), como
          cualquier otro reporte de impresión de Odoo -no con botones
          propios en la barra de herramientas-. Reporte de Consecutivos:
          agrupado por Usuario (quien creó el recibo), con Factura,
          Fecha, Estudiante, Cliente, Fechas de la clase, Cursos,
          Beneficios, Observaciones, Valor, Ingresos y Cuotas, subtotal
          por usuario y total general. Los 3 Reportes Financieros
          comparten encabezado (Programa/Sede/Fecha/Horario/Generado) y
          columnas comunes por recibo (Programa, Cursos, Fechas,
          Horario, Identidad y nombre del estudiante, Tipo -Nuevos si es
          el recibo más antiguo del estudiante, Antiguos en cualquier
          otro caso- y Matrículas -mes y año en español de la fecha del
          recibo-): Clientes agrega Cliente/Factura/Fecha/Valor;
          Beneficios una fila por descuento aplicado (wk.fee.discount.log,
          tarea 11856) o una fila en cero si no tiene ninguno; Formas de
          Pago una fila por pago conciliado con la factura o una fila en
          cero si aún no tiene pagos. Todos de solo consulta/exportación,
          restringidos a Officer/Admin.
        - Wizard de Generación de Certificados Académicos (tarea 12451):
          única opción de menú Gestión Educativa → Informes → Certificados,
          que abre un wizard para generar los Certificados de Inglés
          Básico, Inglés Intermedio (Adultos/Adolescentes) y Programa
          Avanzado, en PDF, individual o grupal (un único archivo con un
          certificado por estudiante). El tipo de certificado NUNCA se
          selecciona a mano: se infiere de Programa + Tipo de población +
          Nivel + Sede (o, si el Programa está marcado "Es Programa
          Avanzado", de la Clase ofertada elegida, de donde salen el nombre
          del curso y el Docente firmante). Los estudiantes elegibles se
          filtran por Inscripción con Resultado académico Aprobado en esa
          combinación. Intensidad horaria, Fecha de expedición, Lugar de
          expedición, Libro y Folio son siempre manuales (Odoo no los
          calcula ni asigna); en modalidad grupal pueden ser comunes a
          todo el lote o individuales por estudiante. Resolución
          institucional, lugar de expedición sugerido y firmas (Directora
          Ejecutiva/Académica) se gestionan por Sede en una pantalla de
          configuración nueva (Configuración → Académicos), sin tocar
          código si cambian. Cada certificado generado queda como un
          registro propio consultable después (Estudiante → pestaña
          Certificados), con su PDF descargable, para Libro/Folio/
          Consecutivo. Restringido a Officer/Admin.
    """,
    "category": "School Management",
    "version": "19.0.1.6.0",
    "author": "OdOne S.A.S.",
    "website": "https://www.odone.com.co",
    "license": "Other proprietary",
    "depends": [
        "wk_school_management",
        "l10n_co_data_bloodo",
        "loyalty",
        "report_xlsx",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/ir_rule.xml",
        "data/load_translations.xml",
        "data/ir_action_data_override.xml",
        "data/attendance_tag_data.xml",
        "data/class_modality_data.xml",
        "data/sede_data.xml",
        "data/certificate_config_data.xml",
        "data/jornada_data.xml",
        "data/health_regime_data.xml",
        "wizard/student_postpone_wizard_view.xml",
        "wizard/promote_bulk_wizard_view.xml",
        "wizard/class_list_wizard_view.xml",
        "wizard/academic_analysis_wizard_view.xml",
        "wizard/certificate_wizard_view.xml",
        "wizard/fee_benefit_wizard_view.xml",
        "views/student_student_view.xml",
        "views/grade_assignment_view.xml",
        "views/student_assignment_cp_view.xml",
        "views/class_assignment_view.xml",
        "views/student_enrollment_view.xml",
        "views/populate_class_view.xml",
        "views/class_attendance_view.xml",
        "views/grade_consolidated_view.xml",
        "views/grade_subject_view.xml",
        "views/school_grade_view.xml",
        "views/grade_scale_structure_view.xml",
        "views/grade_scale_view.xml",
        "views/wk_application_form_view.xml",
        "views/program_type_view.xml",
        "views/class_modality_view.xml",
        "views/sede_view.xml",
        "views/certificate_config_view.xml",
        "views/certificate_view.xml",
        "views/jornada_view.xml",
        "views/health_regime_view.xml",
        "views/class_location_view.xml",
        "views/class_timeslot_view.xml",
        "views/res_partner_view.xml",
        "views/observation_view.xml",
        "views/enrollment_continuity_log_view.xml",
        "views/menu_item.xml",
        "views/product_product_view.xml",
        "views/res_config_settings.xml",
        "views/website_portal_view.xml",
        "views/translations_override.xml",
        "views/fee_installment_plan_view.xml",
        "views/fee_slip_view.xml",
        "views/account_payment_view.xml",
        "wizard/enroll_wizard_view.xml",
        "wizard/assignment_wizard_view.xml",
        "wizard/evaluation_wizard_view.xml",
        "wizard/bulk_class_wizard_view.xml",
        "wizard/student_promote_wizard_view.xml",
        "wizard/fee_slip_wizard_view.xml",
        "wizard/account_payment_register_view.xml",
        "report/grade_consolidated_report.xml",
        "report/payment_receipt_report.xml",
        "report/academic_history_report.xml",
        "report/fee_slip_financial_reports.xml",
        "report/certificate_report.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "wk_school_colombo/static/src/grade_matrix/grade_matrix_field.js",
            "wk_school_colombo/static/src/grade_matrix/grade_matrix_field.xml",
            "wk_school_colombo/static/src/grade_matrix/grade_float_field.js",
            "wk_school_colombo/static/src/js/gradesheet_patch.js",
            "wk_school_colombo/static/src/xml/gradesheet_patch.xml",
            "wk_school_colombo/static/src/js/transcript_patch.js",
            "wk_school_colombo/static/src/xml/transcript_patch.xml",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
