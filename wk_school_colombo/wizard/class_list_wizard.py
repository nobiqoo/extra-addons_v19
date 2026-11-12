# -*- coding: utf-8 -*-
"""Wizard "Generar Class List" (Ajuste y ampliación de Reportes Académicos).

Punto de entrada nuevo desde Informes → Hoja de calificaciones: el botón
"Generar Class List" de esa pantalla (static/src/js/gradesheet_patch.js)
abre este wizard con la Clase ofertada ya seleccionada, y reutiliza el
reporte Class List que el Consolidado de notas ya construyó en la subtarea 8
(models/grade_consolidated.py::_wk_print_class_list), solo agregando las
columnas opcionales que pide esta subtarea.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class WkSchoolColomboClassListWizard(models.TransientModel):
    _name = 'wk.school.colombo.class.list.wizard'
    _description = "Generar Class List / Listado del Módulo"

    populate_class_id = fields.Many2one(
        'wk.school.class', string="Clase ofertada", required=True, readonly=True)
    cuts_count = fields.Selection(
        related='populate_class_id.grading_scale_id.cuts_count', readonly=True)
    cut = fields.Selection([
        ('midterm', "Midterm"), ('final', "Final"),
    ], string="Calificación", default='final', required=True,
        help="Solo aplica cuando la Escala de la clase maneja 2 cortes; con "
             "1 corte, el Class List siempre usa el resultado Final.")

    show_grades = fields.Boolean(string="Notas (componentes académicos)")
    show_invoice = fields.Boolean(string="Factura")
    show_phone = fields.Boolean(string="Teléfono")
    show_mobile = fields.Boolean(string="Celular")
    show_email = fields.Boolean(string="Correo electrónico")

    def action_generate_pdf(self):
        self.ensure_one()
        if not self.populate_class_id.grading_scale_id:
            raise UserError(_(
                "Esta Clase ofertada no tiene aplicada una Estructura de "
                "calificación avanzada (botón \"Aplicar estructura de "
                "calificación\" en la Clase ofertada)."))
        consolidated = self.populate_class_id._wk_get_or_create_consolidated()
        cut = self.cut if consolidated.cuts_count == '2' else 'final'
        return consolidated._wk_print_class_list(
            variant='all', cut=cut, show_grades=self.show_grades,
            show_invoice=self.show_invoice, show_phone=self.show_phone,
            show_mobile=self.show_mobile, show_email=self.show_email)
