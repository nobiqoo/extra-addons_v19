# -*- coding: utf-8 -*-
"""Estructura de calificación avanzada (subtarea 8, requerimiento 2.1-2.5).

Extiende la Escala de calificación (wk.grade.scales) con un check
"Habilitar estructura de calificación avanzada" y, cuando está activo, con
las pestañas de configuración que necesita la operación académica de Inglés
del Centro Colombo Americano: equivalencias cualitativas (2.2), componentes
y ponderaciones por corte (2.3), criterios de Class Performance (2.4),
rangos de desempeño y la regla de ausencias (2.5/2.11).

Con el check desactivado -el valor por defecto en cualquier escala nueva o
ya existente-, el comportamiento estándar del módulo no cambia en nada: los
campos y modelos nuevos de este archivo simplemente no se usan, y el check
estándar "Habilitar cálculo del promedio académico" (gpa_calculation) sigue
intacto.
"""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from .populate_class import CLASS_MODALITY_SELECTION

# Semillas sugeridas al activar la estructura avanzada por primera vez
# (2.2, 2.4 y 2.5): son solo un punto de partida editable para no empezar de
# una pantalla vacía -nunca valores fijos usados en el cálculo-. El cálculo
# (próxima fase de esta subtarea) siempre lee los registros guardados en la
# base de datos, nunca estas listas; un usuario autorizado puede editarlas,
# agregar más filas o borrarlas sin ninguna restricción.
RATING_SEED = [
    (10, "Excellent", 95.0, "Desempeño sobresaliente."),
    (20, "Very Good", 85.0, "Desempeño muy bueno."),
    (30, "Good", 75.0, "Desempeño bueno."),
    (40, "Fair", 65.0, "Desempeño aceptable."),
    (50, "Needs Improvement", 50.0, "Necesita mejorar."),
]

CP_CRITERION_SEED = [
    (10, "Attendance / Promptness"),
    (20, "Engagement"),
    (30, "Listening Skill"),
    (40, "Behavior"),
    (50, "Preparation"),
]

PERFORMANCE_RANGE_SEED = [
    (10, "DS", "Desempeño Superior", 90.0, 100.0),
    (20, "DA", "Desempeño Alto", 80.0, 89.9),
    (30, "DBS", "Desempeño Básico", 70.0, 79.9),
    (40, "DBJ", "Desempeño Bajo", 0.0, 69.9),
]

CUTS_COUNT_SELECTION = [
    ('1', "1 corte"),
    ('2', "2 cortes (Midterm / Final)"),
]


class GradeScale(models.Model):
    """Configuración avanzada de la Escala de calificación (2.1, 2.2, 2.4, 2.5)."""

    _inherit = 'wk.grade.scales'

    advanced_structure = fields.Boolean(
        string="Habilitar estructura de calificación avanzada",
        help="Al activarlo, esta Escala deja de usar el cálculo estándar "
             "(promedio GPA por tipo de actividad + rangos) y pasa a usar "
             "la estructura de componentes, cortes y reglas propias de la "
             "operación académica de Inglés del Centro Colombo Americano. "
             "Con el check desactivado, la Escala conserva el "
             "comportamiento estándar sin ningún cambio.")
    advanced_active = fields.Boolean(
        string="Estructura activa", default=True,
        help="Al desmarcarlo, la estructura deja de poder aplicarse a "
             "Clases ofertadas nuevas, pero las que ya la tienen aplicada "
             "siguen funcionando sin cambios.")
    program_type_id = fields.Many2one(
        'wk.school.colombo.program.type', string="Tipo de programa")
    modality = fields.Selection(
        CLASS_MODALITY_SELECTION, string="Programa o modalidad")
    pass_grade = fields.Float(
        string="Nota mínima de aprobación", default=60.0)
    grade_decimals = fields.Integer(
        string="Decimales", default=1,
        help="Cantidad de decimales con la que se redondean, muestran y "
             "comparan el Midterm Grade y la Final Grade -Pass/Fail y el "
             "rango de desempeño incluidos-, para que lo que ve el usuario "
             "coincida siempre con el resultado usado en la clasificación.")
    cuts_count = fields.Selection(
        CUTS_COUNT_SELECTION, string="Número de cortes", default='1')

    # Regla de aprobación por ausencias (2.11): el requerimiento solo define
    # el tramo 10-15 horas con promedio exigido 85; estos parámetros
    # permiten ajustar esos tres valores por escala, y decidir qué pasa por
    # encima del máximo, sin dejarlos fijos en código.
    abs_min_hours = fields.Float(
        string="Horas mínimas del rango", default=10.0,
        help="Al superar esta cantidad de horas de ausencia (sin llegar a "
             "las horas máximas) se exige el promedio mínimo configurado "
             "abajo para conservar la aprobación.")
    abs_max_hours = fields.Float(
        string="Horas máximas del rango", default=15.0)
    abs_required_average = fields.Float(
        string="Promedio exigido en el rango", default=85.0,
        help="Dentro del rango de horas, el estudiante debe superar este "
             "promedio en la Final Grade para conservar la aprobación.")
    abs_auto_fail_above_max = fields.Boolean(
        string="Reprobar automáticamente al superar las horas máximas",
        default=True,
        help="Si está activo, superar las horas máximas de ausencia "
             "reprueba al estudiante sin importar su Final Grade.")

    show_performance_description = fields.Boolean(
        string="Mostrar descriptivo del desempeño en la boleta de notas",
        default=True,
        help="Incluye el nombre del rango de desempeño (p. ej. "
             "\"Desempeño Alto\") en el Reporte Final del Consolidado, "
             "además del Final Grade. Si se desactiva, el reporte solo "
             "muestra la nota.")
    additional_message = fields.Text(
        string="Mensaje adicional en la boleta de notas",
        help="Texto libre (p. ej. una nota institucional) que se imprime "
             "al final del Reporte Final de cualquier clase que use esta "
             "Escala.")
    allow_edit_confirmed = fields.Boolean(
        string="Permitir edición de calificaciones confirmadas (solo "
               "usuarios autorizados)",
        default=False,
        help="Controla si \"Reabrir Final\" está disponible para el "
             "Consolidado de una clase con esta Escala. Desactivado (por "
             "defecto): el corte Final confirmado queda bloqueado para "
             "siempre, sin excepción. Activado: un Admin todavía puede "
             "reabrirlo desde el Consolidado.")

    component_ids = fields.One2many(
        'wk.school.colombo.grade.scale.component', 'scale_id',
        string="Componentes de calificación")
    rating_ids = fields.One2many(
        'wk.school.colombo.grade.scale.rating', 'scale_id',
        string="Equivalencias cualitativas")
    cp_criterion_ids = fields.One2many(
        'wk.school.colombo.grade.scale.cp.criterion', 'scale_id',
        string="Criterios de Class Performance")
    performance_range_ids = fields.One2many(
        'wk.school.colombo.grade.scale.performance.range', 'scale_id',
        string="Rangos de desempeño")

    @api.onchange('advanced_structure')
    def _onchange_advanced_structure(self):
        """Fuerza gpa_calculation=False y sugiere datos de partida.

        Ver el comentario de las constantes *_SEED al inicio del archivo:
        esto solo prellena el formulario la primera vez que se activa el
        check en una Escala que todavía no tiene ninguna línea propia.
        """
        for scale in self:
            if not scale.advanced_structure:
                continue
            scale.gpa_calculation = False
            if not scale.rating_ids:
                scale.rating_ids = [
                    (0, 0, {'sequence': seq, 'name': name, 'value': value,
                            'description': description})
                    for seq, name, value, description in RATING_SEED]
            if not scale.cp_criterion_ids:
                scale.cp_criterion_ids = [
                    (0, 0, {'sequence': seq, 'name': name})
                    for seq, name in CP_CRITERION_SEED]
            if not scale.performance_range_ids:
                scale.performance_range_ids = [
                    (0, 0, {
                        'sequence': seq, 'code': code, 'name': name,
                        'min_grade': min_grade, 'max_grade': max_grade,
                    })
                    for seq, code, name, min_grade, max_grade
                    in PERFORMANCE_RANGE_SEED]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('advanced_structure'):
                vals['gpa_calculation'] = False
        return super().create(vals_list)

    def write(self, vals):
        """Impide que ambos mecanismos de cálculo operen simultáneamente.

        Cubre además escrituras por código, importación o API que no pasan
        por el onchange de la vista (p. ej. activar advanced_structure
        sobre una escala que ya tenía gpa_calculation=True).
        """
        res = super().write(vals)
        if vals.get('advanced_structure'):
            self.filtered(
                lambda s: s.advanced_structure and s.gpa_calculation
            ).write({'gpa_calculation': False})
        return res

    @api.constrains('component_ids', 'cuts_count', 'advanced_structure',
                     'advanced_active')
    def _check_component_weight_sum(self):
        """Valida automáticamente la suma de ponderaciones por corte (2.3).

        Con 1 corte, el peso de cada componente va en ``weight`` y debe
        sumar 100 % entre los componentes activos. Con 2 cortes, ``weight``
        es el peso dentro de Midterm y ``weight_final`` el de Final; cada
        uno se valida de forma independiente, considerando solo los
        componentes con un peso mayor que 0 en ese corte (0 = no participa).
        Mientras no haya ningún componente activo todavía, no se valida: la
        Escala se puede guardar mientras se sigue configurando por partes.
        """
        for scale in self:
            if not (scale.advanced_structure and scale.advanced_active):
                continue
            active = scale.component_ids.filtered('active')
            if not active:
                continue
            if scale.cuts_count == '1':
                total = sum(active.mapped('weight'))
                if abs(total - 100.0) > 0.01:
                    raise ValidationError(_(
                        "La suma de las ponderaciones de los componentes de "
                        "\"%(scale)s\" es %(total).2f%%; debe ser "
                        "exactamente 100%%."
                    ) % {'scale': scale.name, 'total': total})
            else:
                for cut_label, field_name in (
                        ("Midterm", 'weight'), ("Final", 'weight_final')):
                    in_cut = active.filtered(lambda c: c[field_name] > 0)
                    if not in_cut:
                        continue
                    total = sum(in_cut.mapped(field_name))
                    if abs(total - 100.0) > 0.01:
                        raise ValidationError(_(
                            "La suma de las ponderaciones de %(cut)s en "
                            "\"%(scale)s\" es %(total).2f%%; debe ser "
                            "exactamente 100%%."
                        ) % {'cut': cut_label, 'scale': scale.name,
                             'total': total})


class GradeScaleComponent(models.Model):
    """Componente de calificación de una estructura avanzada (2.3)."""

    _name = 'wk.school.colombo.grade.scale.component'
    _description = "Componente de calificación"
    _order = 'sequence, id'

    scale_id = fields.Many2one(
        'wk.grade.scales', string="Escala", required=True,
        ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Nombre del componente", required=True)
    assignment_type_id = fields.Many2one(
        'wk.assignment.type', string="Tipo de actividad", required=True)
    is_class_performance = fields.Boolean(
        string="Es Class Performance",
        help="Marca este componente como el que recibe, ya convertido a "
             "valor cuantitativo, el resultado de la evaluación cualitativa "
             "de Class Performance (ver pestaña Class Performance). Con 2 "
             "cortes, cada corte maneja su propio componente de Class "
             "Performance (uno con este check para Midterm y otro para "
             "Final).")
    in_quiz_average = fields.Boolean(
        string="Incluir en Fin. Quiz Average",
        help="Solo afecta el indicador informativo \"Fin. Quiz Average\" "
             "del Consolidado (promedio simple de los componentes "
             "marcados); no cambia la ponderación real del componente, que "
             "siempre es la configurada en Peso Midterm/Peso Final.")
    weight = fields.Float(
        string="Peso Midterm (%)", default=0.0,
        help="Con 1 corte, es el peso del componente sobre el 100% total. "
             "Con 2 cortes, es su peso dentro de Midterm; 0 significa que "
             "el componente no participa en Midterm.")
    weight_final = fields.Float(
        string="Peso Final (%)", default=0.0,
        help="Peso del componente dentro de Final (solo aplica con 2 "
             "cortes). 0 significa que el componente no participa en "
             "Final. Un componente puede repetirse en ambos cortes (por "
             "ejemplo, Quiz 1 aporta a Midterm y también a Final) "
             "reutilizando la misma calificación registrada por el "
             "docente, cada vez con su propio peso.")
    cut_display = fields.Char(
        string="Corte", compute='_compute_cut_display',
        help="Informativo: en qué corte(s) pesa este componente, según "
             "Peso Midterm/Peso Final. No es un selector -un componente "
             "puede pesar en los dos cortes a la vez reutilizando la misma "
             "calificación (ver ayuda de Peso Final)-.")
    active = fields.Boolean(default=True)

    @api.depends('weight', 'weight_final')
    def _compute_cut_display(self):
        for component in self:
            in_midterm = component.weight > 0
            in_final = component.weight_final > 0
            if in_midterm and in_final:
                component.cut_display = _("Midterm y Final")
            elif in_midterm:
                component.cut_display = _("Midterm")
            elif in_final:
                component.cut_display = _("Final")
            else:
                component.cut_display = _("—")

    @api.constrains('weight', 'weight_final')
    def _check_weight_not_negative(self):
        for component in self:
            if component.weight < 0 or component.weight_final < 0:
                raise ValidationError(_(
                    "El peso de un componente de calificación no puede ser "
                    "negativo."))


class GradeScaleRating(models.Model):
    """Equivalencia cualitativa -> cuantitativa de Class Performance (2.2)."""

    _name = 'wk.school.colombo.grade.scale.rating'
    _description = "Equivalencia cualitativa de Class Performance"
    _order = 'sequence, id'

    scale_id = fields.Many2one(
        'wk.grade.scales', string="Escala", required=True,
        ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Valoración", required=True)
    value = fields.Float(string="Valor cuantitativo", required=True)
    description = fields.Char(
        string="Descripción",
        help="Texto libre y opcional (p. ej. qué significa esta "
             "valoración para quien califica). No participa en el "
             "cálculo: solo documenta la valoración.")
    active = fields.Boolean(default=True)


class GradeScaleCpCriterion(models.Model):
    """Criterio evaluado dentro de Class Performance (2.4)."""

    _name = 'wk.school.colombo.grade.scale.cp.criterion'
    _description = "Criterio de Class Performance"
    _order = 'sequence, id'

    scale_id = fields.Many2one(
        'wk.grade.scales', string="Escala", required=True,
        ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Criterio", required=True)
    active = fields.Boolean(
        default=True,
        help="Un criterio inactivo deja de aparecer en nuevas evaluaciones "
             "de Class Performance; las ya registradas no se modifican.")


class GradeScalePerformanceRange(models.Model):
    """Rango de desempeño usado para clasificar la Final Grade (2.5)."""

    _name = 'wk.school.colombo.grade.scale.performance.range'
    _description = "Rango de desempeño"
    _order = 'sequence, min_grade'

    scale_id = fields.Many2one(
        'wk.grade.scales', string="Escala", required=True,
        ondelete='cascade')
    sequence = fields.Integer(default=10)
    code = fields.Char(string="Código", required=True)
    name = fields.Char(string="Desempeño", required=True)
    min_grade = fields.Float(string="Nota mínima", required=True)
    max_grade = fields.Float(string="Nota máxima", required=True)
    active = fields.Boolean(
        default=True,
        help="Un rango inactivo deja de usarse para nuevas "
             "clasificaciones; las ya calculadas no se modifican.")

    @api.constrains('min_grade', 'max_grade', 'scale_id', 'active')
    def _check_ranges(self):
        """Evita solapes y exige que el rango más bajo empiece en 0.

        No exige que los rangos sean contiguos sin huecos (90.0 tras 89.9
        deja un hueco de 89.91 a 89.99): la clasificación por nota
        (_classify_grade, próxima fase de esta subtarea) usa el mayor
        ``min_grade`` que sea <= la nota, así que un hueco simplemente cae
        en el rango inferior más cercano y no produce un error.
        """
        for scale in self.mapped('scale_id'):
            ranges = scale.performance_range_ids.filtered('active').sorted(
                key=lambda r: r.min_grade)
            previous = None
            for rank, rng in enumerate(ranges):
                if rng.min_grade > rng.max_grade:
                    raise ValidationError(_(
                        "El rango \"%s\" tiene la nota mínima mayor que la "
                        "máxima.") % rng.name)
                if rank == 0 and rng.min_grade != 0:
                    raise ValidationError(_(
                        "El rango de menor nota (\"%s\") debe empezar en "
                        "0.") % rng.name)
                if previous is not None and rng.min_grade <= previous.max_grade:
                    raise ValidationError(_(
                        "Los rangos \"%s\" y \"%s\" se solapan.") % (
                            previous.name, rng.name))
                previous = rng
