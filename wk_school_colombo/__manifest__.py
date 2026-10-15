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
    """,
    "category": "School Management",
    "version": "19.0.1.6.0",
    "author": "OdOne S.A.S.",
    "website": "https://www.odone.com.co",
    "license": "Other proprietary",
    "depends": [
        "wk_school_management",
        "l10n_co_data_bloodo",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/ir_rule.xml",
        "data/load_translations.xml",
        "data/ir_action_data_override.xml",
        "data/attendance_tag_data.xml",
        "wizard/student_postpone_wizard_view.xml",
        "wizard/promote_bulk_wizard_view.xml",
        "views/student_student_view.xml",
        "views/grade_assignment_view.xml",
        "views/student_assignment_cp_view.xml",
        "views/class_assignment_view.xml",
        "views/student_enrollment_view.xml",
        "views/populate_class_view.xml",
        "views/class_attendance_view.xml",
        "views/grade_consolidated_view.xml",
        "views/grade_subject_view.xml",
        "views/grade_scale_view.xml",
        "views/grade_scale_structure_view.xml",
        "views/wk_application_form_view.xml",
        "views/program_type_view.xml",
        "views/observation_view.xml",
        "views/enrollment_continuity_log_view.xml",
        "views/menu_item.xml",
        "views/product_product_view.xml",
        "views/res_config_settings.xml",
        "views/website_portal_view.xml",
        "views/translations_override.xml",
        "wizard/enroll_wizard_view.xml",
        "wizard/assignment_wizard_view.xml",
        "wizard/evaluation_wizard_view.xml",
        "wizard/bulk_class_wizard_view.xml",
        "wizard/student_promote_wizard_view.xml",
        "report/grade_consolidated_report.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "wk_school_colombo/static/src/grade_matrix/grade_matrix_field.js",
            "wk_school_colombo/static/src/grade_matrix/grade_matrix_field.xml",
            "wk_school_colombo/static/src/grade_matrix/grade_float_field.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
