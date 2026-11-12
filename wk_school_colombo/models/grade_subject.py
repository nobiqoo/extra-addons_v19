# -*- coding: utf-8 -*-
from odoo import _, api, models, fields
from odoo.exceptions import ValidationError


class WkGradeSubjects(models.Model):
    _inherit = 'wk.grade.subjects'

    is_active_subject = fields.Boolean(string="Activa", default=True)
    # Ajustes de la sesion de revision (nov-2026): la Materia ("Modulo" en la
    # Clase ofertada) se liga a las modalidades y sedes en las que se dicta,
    # para que la Clase ofertada y la programacion masiva solo ofrezcan las
    # materias que corresponden a la sede y modalidad elegidas.
    modality_ids = fields.Many2many(
        'wk.school.colombo.class.modality',
        'wk_grade_subjects_modality_rel', 'subject_id', 'modality_id',
        string="Modalidades")
    sede_ids = fields.Many2many(
        'wk.school.colombo.sede',
        'wk_grade_subjects_sede_rel', 'subject_id', 'sede_id',
        string="Sedes")

    @api.model_create_multi
    def create(self, vals_list):
        # @api.constrains solo se dispara si las claves vienen en vals; al
        # crear sin ellas (API/importación) la validación se saltaría.
        records = super().create(vals_list)
        records._check_modality_and_sede_required()
        return records

    @api.constrains('modality_ids', 'sede_ids')
    def _check_modality_and_sede_required(self):
        """Modalidad y sede son obligatorias.

        Many2many no admite ``required=True`` de forma fiable (no hay columna
        que marcar NOT NULL), asi que se valida aqui; la vista las marca con
        ``required="1"``. Solo corre al crear/escribir, por lo que las
        materias existentes no rompen la actualizacion del modulo: quedan
        pendientes de configurar.
        """
        for subject in self:
            if not subject.modality_ids or not subject.sede_ids:
                raise ValidationError(_(
                    "La materia %(name)s debe tener al menos una modalidad y "
                    "una sede.", name=subject.display_name))
