# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class WkSchoolGrade(models.Model):
    """Nivel con las modalidades y sedes en las que se dicta.

    Ajustes de la sesion de revision (nov-2026): la programacion masiva de
    Clases ofertadas solo debe ofrecer los niveles ligados a la modalidad y la
    sede elegidas (sabatino / diario / vacacional, por sede). El vinculo se
    configura aqui, en el propio Nivel.
    """

    _inherit = 'wk.school.grade'

    modality_ids = fields.Many2many(
        'wk.school.colombo.class.modality',
        'wk_school_grade_modality_rel', 'grade_id', 'modality_id',
        string="Modalidades")
    sede_ids = fields.Many2many(
        'wk.school.colombo.sede',
        'wk_school_grade_sede_rel', 'grade_id', 'sede_id',
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

        Many2many no admite ``required=True`` de forma fiable, asi que se
        valida aqui (y la vista las marca con ``required="1"``). Solo corre al
        crear/escribir: los niveles existentes no rompen la actualizacion del
        modulo, quedan pendientes de configurar.
        """
        for grade in self:
            if not grade.modality_ids or not grade.sede_ids:
                raise ValidationError(_(
                    "El nivel %(name)s debe tener al menos una modalidad y "
                    "una sede.", name=grade.display_name))
