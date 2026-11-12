# -*- coding: utf-8 -*-
from odoo import fields, models


class WkSchoolColomboProgramType(models.Model):
    """Catálogo configurable de Tipo de programa.

    Requerimiento de campos académicos: el Tipo de programa no debe depender
    de valores fijos en código. Se modela como catálogo independiente (mismo
    patrón mínimo que wk.class.location) para que un usuario autorizado pueda
    crear, modificar y activar/desactivar tipos sin necesitar un desarrollo
    nuevo. La selección de un tipo no dispara ningún comportamiento
    académico: es puramente descriptivo.
    """

    _name = 'wk.school.colombo.program.type'
    _inherit = 'wk.company.visibility.mixin'
    _description = 'Tipo de programa'
    _order = 'sequence, name'

    name = fields.Char(string="Nombre", required=True)
    sequence = fields.Integer(default=1)
    company_id = fields.Many2one(
        'res.company', string="Sede", default=lambda self: self.env.company,
        required=True)
    active = fields.Boolean(
        'Activo', default=True,
        help="Al desmarcarlo, el tipo de programa deja de estar disponible "
             "para nuevas solicitudes, pero las que ya lo usan conservan la "
             "información sin cambios.")
    show_mce_equivalence = fields.Boolean(
        string="Mostrar equivalencia con el Marco Común Europeo",
        help="Incluye en el Reporte Individual del Estudiante la tabla de "
             "equivalencia entre los niveles del Colombo y el Marco Común "
             "Europeo (A1/A2/B1/B1-B2). Aplica solo a los programas de "
             "Inglés donde esa equivalencia tiene sentido -se activa por "
             "Tipo de programa, nunca por código-.")
    # Tarea 12451 (Certificados académicos): el Programa Avanzado tiene una
    # estructura de certificado totalmente distinta a los demás Programas
    # (sin Nivel/Tipo de población, sin Libro/Folio/Consecutivo, con nombre
    # de curso y Docente propios de una Clase ofertada puntual). El wizard
    # de Certificados usa este check para cambiar de modo, en vez de inferir
    # "es Avanzado" a partir del nombre del Programa.
    is_advanced_program = fields.Boolean(
        string="Es Programa Avanzado (Certificados)",
        help="Marca este Programa como \"Programa Avanzado\" para el "
             "wizard de Certificados académicos (Informes > Certificados): "
             "en vez de Nivel y Tipo de población, pide la Clase ofertada "
             "puntual, y el certificado no usa Libro/Folio/Consecutivo.")
