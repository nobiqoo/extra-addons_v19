# -*- coding: utf-8 -*-
{
    'name': 'Nómina Profesores - Colombo Americano',
    'summary': '''
        Política de cálculo de nómina por tipo de contrato y cargue de horas
        aprobadas desde el módulo académico
    ''',
    'description': '''
        Nómina de profesores para el Centro Colombo Americano.

        Horas aprobadas desde académico (tarea 10268):

        - Cuenta analítica origen en la clase ofertada, que es el curso que
          soporta el costo de las horas dictadas.
        - Registro de asistencia del profesor con el curso asociado, las horas
          a pagar y la cuenta analítica que hereda del curso, más el
          interruptor "Aprobado para Nómina" que solo pueden mover el Gerente
          de Asistencias y el Administrador de Recursos Humanos.
        - Al aprobar una asistencia, sus horas se suman solas a la novedad de
          nómina en borrador del profesor para ese mes, con una línea por
          curso: horas, cuenta analítica, valor hora vigente del contrato,
          subtotal y peso porcentual del curso sobre el total de horas del
          mes. Si el mes no tiene novedad en borrador, se crea. Al desaprobar
          o eliminar la asistencia, sus horas salen de la novedad mientras
          siga en borrador. El valor queda visible antes de confirmar para
          que contabilidad lo verifique.
        - Asistente "Generar novedades de horas" para consolidar las
          asistencias aprobadas que hayan quedado por fuera de una novedad.
        - Pestaña "Histórico de horas" en el contrato del profesor con las
          horas consolidadas por curso y mes, su valor y el estado Pendiente
          o Pagado, que cambia a Pagado al pagar la nómina.
        - La distribución analítica de la nómina de un profesor se toma de esa
          matriz de porcentajes por curso en lugar de la distribución fija del
          contrato.

        Política de cálculo por tipo de contrato (tarea 10269):

        - Interruptor "Activar Política de Cálculo por Tipo de Contrato" en los
          ajustes de nómina. Con la política activa se exige que el contrato
          tenga categoría de empleado, subtipo de profesor cuando aplique y
          valor hora vigente antes de poder liquidar.
        - Pestaña "Tipo de Empleado" en el contrato: categoría (Administrativo
          o Profesor), subtipo de profesor (Tipo 10, Tipo 12 o Mixto), la marca
          técnica de cálculo especial de prestaciones —que se activa sola en
          los subtipos marcados en Ajustes, por defecto Tipo 10 y Mixto— y la
          base de días de liquidación resultante.
        - Prestaciones sobre 330 días: en los subtipos marcados, las
          cesantías, sus intereses, la prima y las vacaciones —pago,
          liquidación del contrato y libro de vacaciones— se causan sobre 330
          días en lugar de 360. En el mixto aplica a todo el contrato. En el
          profesor Tipo 10 o Tipo 12 la base salarial de esas prestaciones es
          el promedio de las horas devengadas, no el valor hora del contrato.
          La nómina colombiana expone la base de días en
          hr.contract.get_benefits_days_base.
        - Histórico de valor hora del profesor (pestaña Tipo de Empleado), con
          la trazabilidad del cambio de tarifa en el tiempo. El valor vigente
          se resuelve por fecha.
        - Interruptor "Provisiones profesores" con sus propios porcentajes de
          cesantías, intereses de cesantías, prima y vacaciones, independientes
          de los porcentajes de los administrativos, y los subtipos de profesor
          a los que se aplican (por defecto Tipo 10 y Mixto). Los porcentajes se
          aplican tal cual sobre el valor de las horas del mes; los intereses
          de cesantías, como en las provisiones simples, son un porcentaje de
          la provisión de cesantías.
        - Provisiones calculadas según la naturaleza del contrato: el
          administrativo provisiona sobre el salario básico y el profesor de un
          subtipo no marcado (por defecto Tipo 12) sobre el valor de las horas
          del mes, ambos con los porcentajes de los administrativos; el
          profesor de un subtipo marcado provisiona sobre las horas con los
          porcentajes de profesor. El contrato mixto genera las dos
          provisiones en el mismo periodo: la fracción administrativa sobre el
          básico con la cuenta analítica del contrato, sin el valor de las
          horas, y la fracción profesor sobre las horas del mes con la matriz
          de porcentajes por curso. Cada provisión de profesor deja en su
          registro de cálculo la base de días del contrato.
        - El IBC de seguridad social del profesor se toma del valor de las
          horas del mes y nunca queda por debajo del salario mínimo; en el
          contrato mixto suma el salario básico y el valor de las horas.
        - El auxilio de transporte compara el tope de dos salarios mínimos
          contra el básico más el valor de las horas del profesor. El
          prorrateo diario ya lo resuelve la nómina colombiana y no se
          modifica.
        - El profesor Tipo 10 o Tipo 12 no devenga salario básico: la línea de
          básico queda en cero con los días trabajados y su remuneración es el
          valor de las horas del mes.
        - Nómina electrónica: la novedad de horas se reporta a la DIAN como
          sueldo trabajado (concepto Básico), con los días trabajados de la
          línea de básico, y las provisiones de profesor quedan homologadas con
          los conceptos DIAN de provisiones.
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'category': 'Human Resources/Payroll',
    'license': 'OPL-1',
    'version': '19.0.0.1',
    'depends': [
        'hr_payroll_co',
        'hr_attendance',
        'wk_school_management',
        'l10n_co_hr_bloodo',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/hr_novelty_type_data.xml',
        'data/ir_config_parameter_data.xml',
        'views/populate_class_views.xml',
        'views/hr_attendance_views.xml',
        'views/hr_contract_views.xml',
        'views/hr_novelty_views.xml',
        'views/hr_payslip_line_log_views.xml',
        'views/res_config_settings_views.xml',
        'wizard/teacher_hours_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
