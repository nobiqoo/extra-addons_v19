# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    accounting_reclassification_user_id = fields.Many2one(
        'res.users', string="Responsable de reclasificación contable",
        help="Usuario que recibe la actividad de reclasificación contable "
             "cuando se aplaza a un estudiante. Si se deja vacío, la "
             "actividad queda asignada a quien confirme el aplazamiento.")

    # Tarea 12458: texto legal/institucional impreso al pie de la tirilla de
    # pago (exención de IVA, política de no devoluciones, protección de
    # datos, etc.). Editable sin tocar código porque es un texto que la
    # institución puede necesitar ajustar.
    tirilla_legal_text = fields.Text(
        string="Texto legal de la tirilla de pago",
        help="Texto institucional/legal que se imprime al pie de la tirilla "
             "de pago (exención de IVA, política de devoluciones, aviso de "
             "protección de datos, etc.).")
