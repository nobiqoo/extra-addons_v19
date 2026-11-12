# -*- coding: utf-8 -*-
"""Certificados académicos (tarea 12451).

Dos plantillas: una compartida para Inglés Básico/Intermedio (el cuerpo y
las horas/niveles varían según Tipo de población, ver POPULATION_TEXT) y
otra para Programa Avanzado (formato visual distinto, sin Libro/Folio/
Consecutivo, con nombre de curso y Docente de la Clase ofertada).

El texto institucional (resolución, firmas) viene siempre de
wk.school.colombo.certificate.config por Sede -nunca se hardcodea aquí-.
Libro y Folio se imprimen en palabras + dígito ("Uno (1)"), igual que el
formato físico histórico del Colombo; Consecutivo no se imprime en el
documento (solo queda disponible para consulta posterior, 2.21/2.22) porque
ningún anexo de referencia lo muestra impreso.
"""
from odoo import models

UNIDADES = ['', 'uno', 'dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete',
            'ocho', 'nueve']
DIECIS = ['diez', 'once', 'doce', 'trece', 'catorce', 'quince', 'dieciséis',
          'diecisiete', 'dieciocho', 'diecinueve']
VEINTIS = ['veinte', 'veintiuno', 'veintidós', 'veintitrés', 'veinticuatro',
           'veinticinco', 'veintiséis', 'veintisiete', 'veintiocho',
           'veintinueve']
DECENAS = ['', '', '', 'treinta', 'cuarenta', 'cincuenta', 'sesenta',
           'setenta', 'ochenta', 'noventa']
CENTENAS = ['', 'ciento', 'doscientos', 'trescientos', 'cuatrocientos',
            'quinientos', 'seiscientos', 'setecientos', 'ochocientos',
            'novecientos']
MESES = ['', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
         'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

# Tarea 12451: Básico es siempre para Niños (8 niveles); Intermedio existe
# para Adultos y Adolescentes (12 niveles), solo cambia la redacción de la
# población. Fuera de estos 3 valores no hay certificado "regular" -el
# cuarto tipo (Programa Avanzado) usa program_type_id.is_advanced_program,
# no population_type-.
POPULATION_TEXT = {
    'ninos': {
        'niveles_text': 'ocho (8)',
        'title': 'INGLÉS BÁSICO',
        'programa_frase': 'Programa de Inglés Básico para Niños',
    },
    'adultos': {
        'niveles_text': 'doce (12)',
        'title': 'INGLÉS INTERMEDIO',
        'programa_frase': 'Programa de Inglés Intermedio para Adultos',
    },
    'adolescentes': {
        'niveles_text': 'doce (12)',
        'title': 'INGLÉS INTERMEDIO',
        'programa_frase': 'Programa de Inglés Intermedio para Adolescentes',
    },
}


def _wk_decenas_a_letras(n):
    if n < 10:
        return UNIDADES[n]
    if n < 20:
        return DIECIS[n - 10]
    if n < 30:
        return VEINTIS[n - 20]
    decena, unidad = divmod(n, 10)
    if unidad == 0:
        return DECENAS[decena]
    return "%s y %s" % (DECENAS[decena], UNIDADES[unidad])


def _wk_centenas_a_letras(n):
    if n == 100:
        return 'cien'
    centena, resto = divmod(n, 100)
    if centena == 0:
        return _wk_decenas_a_letras(resto)
    prefix = CENTENAS[centena]
    return prefix if resto == 0 else "%s %s" % (prefix, _wk_decenas_a_letras(resto))


def _wk_miles_a_letras(n):
    if n < 1000:
        return _wk_centenas_a_letras(n)
    # `miles` (n // 1000) can itself be >= 1000 (e.g. n >= 1,000,000), so it
    # must go through this same function again, not _wk_centenas_a_letras
    # (which only accepts 0-999) -- otherwise CENTENAS[centena] overflows.
    miles, resto = divmod(n, 1000)
    prefix = 'mil' if miles == 1 else "%s mil" % _wk_miles_a_letras(miles)
    return prefix if resto == 0 else "%s %s" % (prefix, _wk_centenas_a_letras(resto))


def wk_numero_a_letras(value, title_case=False):
    """Convierte un entero a letras en español; si ``value`` no es un
    entero válido (p. ej. un Consecutivo alfanumérico) o la conversión falla
    por cualquier motivo, lo devuelve tal cual -- Libro/Folio son Char libres
    que el usuario escribe a mano, así que nunca deben tumbar la generación
    del certificado por un valor inesperado."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return value or ''
    # Above a million the "mil"-based recursion reads as "mil mil ..."
    # instead of proper "millón/millones" (never implemented, out of scope
    # for a book/folio number) -- fall back to the plain digits rather than
    # print wrong Spanish.
    if n < 0 or n >= 1000000:
        return str(value)
    try:
        words = _wk_miles_a_letras(n) if n else 'cero'
    except (IndexError, RecursionError):
        return str(value)
    if title_case:
        words = ' '.join(word.capitalize() for word in words.split(' '))
    return words


def wk_fecha_en_letras(fecha):
    if not fecha:
        return ''
    return "a los %s (%s) días del mes de %s de %s (%02d)" % (
        wk_numero_a_letras(fecha.day), fecha.day, MESES[fecha.month],
        wk_numero_a_letras(fecha.year, title_case=True), fecha.year % 100)


def wk_fecha_larga(fecha):
    """'27 de junio de 2026', igual al formato de los 2 Excel/certificados
    de referencia de Programa Avanzado (nunca MM/DD/YYYY del widget
    t-field, que depende del idioma de quien genera el certificado)."""
    if not fecha:
        return ''
    return "%s de %s de %s" % (fecha.day, MESES[fecha.month], fecha.year)


class CertificateReportMixin(models.AbstractModel):
    _name = 'report.wk_school_colombo.certificate_mixin'
    _description = 'Certificado académico - datos comunes'

    def _wk_certificate_configs(self, certificates):
        configs = self.env['wk.school.colombo.certificate.config'].search(
            [('sede_id', 'in', certificates.sede_id.ids)])
        return {config.sede_id.id: config for config in configs}

    def _wk_firma_url(self, config, field_name):
        """URL servida por Odoo (/web/image/...) en vez de incrustar la
        firma como data-URI base64 en el <img src>: un atributo HTML tan
        largo (varios KB en una sola línea) hace que wkhtmltopdf calcule
        mal el alto de los contenedores ancestros (confirmado en vivo: con
        la firma como data-URI, min-height/height en mm o px dejaba de
        aplicarse al marco del certificado de Programa Avanzado -el marco
        no llegaba a cubrir la hoja-; con la misma firma servida por URL,
        el alto se respeta normalmente)."""
        if not (config and config[field_name]):
            return ''
        return '/web/image/wk.school.colombo.certificate.config/%d/%s' % (
            config.id, field_name)

    def _wk_certificate_common_data(self, cert, config):
        return {
            'document_number': cert.student_id.partner_id.vat or '',
            'fecha_texto': wk_fecha_en_letras(cert.fecha_expedicion),
            'directora_ejecutiva_nombre': config.directora_ejecutiva_nombre if config else '',
            'directora_ejecutiva_cargo': config.directora_ejecutiva_cargo if config else '',
            'firma_directora_ejecutiva_url': self._wk_firma_url(
                config, 'firma_directora_ejecutiva'),
            'directora_academica_nombre': config.directora_academica_nombre if config else '',
            'directora_academica_cargo': config.directora_academica_cargo if config else '',
            'firma_directora_academica_url': self._wk_firma_url(
                config, 'firma_directora_academica'),
        }


class CertificateBasicoIntermedioReport(models.AbstractModel):
    # Nombre corto a propósito: el nombre de tabla Postgres derivado
    # (report_wk_school_colombo_...) no puede superar 63 caracteres.
    _name = 'report.wk_school_colombo.report_cert_basico_intermedio'
    _inherit = 'report.wk_school_colombo.certificate_mixin'
    _description = 'Certificado académico - Inglés Básico/Intermedio'

    def _get_report_values(self, docids, data=None):
        certificates = self.env['wk.school.colombo.certificate'].browse(docids)
        configs_by_sede = self._wk_certificate_configs(certificates)
        wk_data = {}
        for cert in certificates:
            config = configs_by_sede.get(cert.sede_id.id)
            pop_text = POPULATION_TEXT.get(cert.population_type, {})
            wk_data[cert.id] = {
                **self._wk_certificate_common_data(cert, config),
                'niveles_text': pop_text.get('niveles_text', ''),
                'title': pop_text.get('title', ''),
                'programa_frase': pop_text.get('programa_frase', ''),
                'resolucion_text': config.resolucion_estandar if config else '',
                'libro_texto': wk_numero_a_letras(cert.libro, title_case=True),
                'folio_texto': wk_numero_a_letras(cert.folio, title_case=True),
            }
        return {
            'doc_ids': docids,
            'doc_model': 'wk.school.colombo.certificate',
            'docs': certificates,
            'wk_data': wk_data,
        }


class CertificateAvanzadoReport(models.AbstractModel):
    _name = 'report.wk_school_colombo.report_cert_avanzado'
    _inherit = 'report.wk_school_colombo.certificate_mixin'
    _description = 'Certificado académico - Programa Avanzado'

    def _get_report_values(self, docids, data=None):
        certificates = self.env['wk.school.colombo.certificate'].browse(docids)
        configs_by_sede = self._wk_certificate_configs(certificates)
        wk_data = {}
        for cert in certificates:
            config = configs_by_sede.get(cert.sede_id.id)
            klass = cert.populate_class_id
            wk_data[cert.id] = {
                **self._wk_certificate_common_data(cert, config),
                'resolucion_text': (
                    config.resolucion_avanzado or config.resolucion_estandar
                ) if config else '',
                'curso_nombre': klass.title or klass.name,
                'docente_nombre': klass.teacher_id.name or '',
                'fecha_expedicion_larga': wk_fecha_larga(cert.fecha_expedicion),
            }
        return {
            'doc_ids': docids,
            'doc_model': 'wk.school.colombo.certificate',
            'docs': certificates,
            'wk_data': wk_data,
        }
