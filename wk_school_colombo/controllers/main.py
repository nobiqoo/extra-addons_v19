# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

from odoo.addons.wk_school_management.controllers.main import (
    WebsiteMenuApplication,
)


class WkColomboWebsiteMenuApplication(WebsiteMenuApplication):

    @http.route('/application/check_duplicate', type='jsonrpc', auth='public', website=True)
    def check_duplicate_application(self, email, grade_id):
        """Ya no se bloquea por correo repetido.

        Un acudiente puede matricular a varios hijos con el mismo correo
        (ajuste pedido por Colombo), asi que el formulario web nunca debe
        mostrar el aviso de "solicitud duplicada" por correo + nivel. Se
        conserva el contrato de respuesta que espera application_form.js.
        """
        grade_name = ''
        if grade_id:
            grade = request.env['wk.school.grade'].sudo().browse(int(grade_id))
            grade_name = grade.name or ''
        return {'exists': False, 'grade_name': grade_name}
