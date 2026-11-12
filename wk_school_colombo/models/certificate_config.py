# -*- coding: utf-8 -*-
"""Configuración institucional de Certificados académicos por Sede (tarea
12451). Resolución, lugar de expedición y firmas institucionales varían por
Sede y no existía ninguna infraestructura para esto; se modela como un
registro por Sede, editable por Officer/Admin sin necesitar un desarrollo
nuevo cuando cambie una resolución o una firma.
"""
from odoo import fields, models


class WkSchoolColomboCertificateConfig(models.Model):
    _name = 'wk.school.colombo.certificate.config'
    _description = 'Configuración institucional de Certificados por Sede'

    sede_id = fields.Many2one(
        'wk.school.colombo.sede', string="Sede", required=True)
    lugar_expedicion = fields.Char(
        string="Lugar de expedición", required=True,
        help="Valor sugerido en el wizard de Certificados para esta Sede; "
             "el usuario puede cambiarlo al generar un certificado puntual.")
    resolucion_estandar = fields.Text(
        string="Resolución (Inglés Básico/Intermedio)", required=True,
        help="Texto completo de licencia de funcionamiento y Registro de "
             "Programas, tal como debe imprimirse en los certificados de "
             "Inglés Básico e Intermedio de esta Sede.")
    resolucion_avanzado = fields.Text(
        string="Resolución (Programa Avanzado)",
        help="Texto de resolución para el certificado de Programa "
             "Avanzado de esta Sede (formato más corto que el anterior, "
             "sin Registro de Programas).")
    directora_ejecutiva_nombre = fields.Char(string="Directora Ejecutiva - Nombre")
    directora_ejecutiva_cargo = fields.Char(
        string="Directora Ejecutiva - Cargo", default="Directora Ejecutiva")
    firma_directora_ejecutiva = fields.Image(
        string="Directora Ejecutiva - Firma", max_width=1024, max_height=1024)
    directora_academica_nombre = fields.Char(
        string="Directora Académica - Nombre", required=True)
    directora_academica_cargo = fields.Char(
        string="Directora Académica - Cargo", default="Directora Académica")
    firma_directora_academica = fields.Image(
        string="Directora Académica - Firma", max_width=1024, max_height=1024)

    _sede_uniq = models.Constraint(
        'unique(sede_id)',
        "Ya existe una configuración de Certificados para esta Sede.")
