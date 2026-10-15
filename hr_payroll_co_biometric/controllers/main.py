# -*- coding: utf-8 -*-
import os
import logging

from markupsafe import Markup
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

_README_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'README.md')


def _md_to_html(md_text):
    """Convierte Markdown a HTML.  Usa la librería `markdown` si está disponible,
    de lo contrario aplica un renderizado básico con regex."""
    try:
        import markdown
        return markdown.markdown(
            md_text,
            extensions=['tables', 'fenced_code', 'toc'],
        )
    except ImportError:
        pass

    # Fallback: renderizado básico sin dependencias externas
    import re
    html = md_text

    # Escapar HTML
    html = html.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    # Bloques de código cercados (``` ```)
    html = re.sub(r'```[\w]*\n(.*?)```', lambda m: '<pre><code>%s</code></pre>' % m.group(1), html, flags=re.DOTALL)

    # Encabezados
    for lvl in range(6, 0, -1):
        html = re.sub(r'^#{%d}\s+(.+)$' % lvl, r'<h%d>\1</h%d>' % (lvl, lvl), html, flags=re.MULTILINE)

    # Negrita / cursiva
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
    html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)

    # Separadores horizontales
    html = re.sub(r'^---+$', '<hr/>', html, flags=re.MULTILINE)

    # Tablas simples (| col | col |)
    def replace_table(m):
        rows = [r.strip() for r in m.group(0).strip().splitlines() if r.strip()]
        result = ['<table class="table table-sm table-bordered">']
        for i, row in enumerate(rows):
            if re.match(r'^\|[\s\-|]+\|$', row):
                continue
            cells = [c.strip() for c in row.strip('|').split('|')]
            tag = 'th' if i == 0 else 'td'
            result.append('<tr>' + ''.join('<%s>%s</%s>' % (tag, c, tag) for c in cells) + '</tr>')
        result.append('</table>')
        return '\n'.join(result)

    html = re.sub(r'(\|.+\|\n)+', replace_table, html)

    # Listas no ordenadas
    html = re.sub(r'^[-*]\s+(.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
    html = re.sub(r'(<li>.*</li>\n?)+', lambda m: '<ul>%s</ul>' % m.group(0), html)

    # Párrafos (líneas vacías entre texto)
    html = re.sub(r'\n\n+', '</p><p>', html)
    html = '<p>' + html + '</p>'

    # Limpiar párrafos vacíos o que envuelven bloques
    html = re.sub(r'<p>\s*(<(?:h\d|ul|pre|table|hr)[^>]*>)', r'\1', html)
    html = re.sub(r'(</(?:h\d|ul|pre|table|hr)>)\s*</p>', r'\1', html)

    return html


class BiometricDocumentation(http.Controller):

    @http.route(
        '/hr_payroll_co_biometric/documentation',
        type='http',
        auth='user',
        website=False,
    )
    def documentation(self, **kwargs):
        # Requiere al menos el rol de usuario del módulo
        if not request.env.user.has_group('hr_payroll_co_biometric.group_biometric_user'):
            return request.not_found()

        try:
            with open(_README_PATH, 'r', encoding='utf-8') as fh:
                content_html = _md_to_html(fh.read())
        except Exception as e:
            _logger.warning('No se pudo leer el README: %s', e)
            content_html = '<p class="text-danger">No se pudo cargar la documentación.</p>'

        try:
            action = request.env.ref('hr_payroll_co_biometric.action_hr_attendance_record')
            back_url = '/web#action=%d' % action.id
        except Exception:
            back_url = '/odoo'

        return request.render(
            'hr_payroll_co_biometric.documentation_page',
            {'content': Markup(content_html), 'back_url': back_url},
        )
