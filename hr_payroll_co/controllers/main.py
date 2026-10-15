# -*- coding: utf-8 -*-
import json
import logging
from odoo import http, fields
from odoo.http import request

_logger = logging.getLogger(__name__)

# Nombre de la clave que se usará en los parámetros del sistema de Odoo
API_KEY_SYSTEM_PARAM = 'hr_payroll_co.api_key_access'
# Nombre del encabezado HTTP donde se espera la clave
API_KEY_HEADER = 'API-KEY'

class HrPayrollNoveltyController(http.Controller):
    """
    Controlador para recibir datos y crear registros en hr.overtime (Novedades/Horas Extras).
    Ruta: /payslip/api/create_overtime
    """

    @http.route('/hr_payroll_co/api/create_overtime', type='http', auth='public', methods=['POST'], csrf=False)
    def create_overtime(self, **kw):
        """
        Endpoint para crear una novedad de tipo hr.overtime.
        Se incluye validación mediante API Key en los encabezados HTTP.
        """
        # --- 0. Validación de API Key ---
        # 1. Obtener la clave del sistema
        system_api_key = request.env['ir.config_parameter'].sudo().get_param(API_KEY_SYSTEM_PARAM)
        
        # 2. Obtener la clave de los encabezados de la petición
        # Usamos request.httprequest.headers.get para obtener la clave del encabezado
        request_api_key = request.httprequest.headers.get(API_KEY_HEADER)

        if not system_api_key:
            _logger.warning("Parámetro del sistema '%s' no está configurado. Denegando acceso por seguridad.", API_KEY_SYSTEM_PARAM)
            return self._response_error(503, "Error de configuración: La clave de acceso del sistema no está definida. Contacte al administrador.")

        if request_api_key != system_api_key:
            _logger.warning("Intento de acceso denegado con clave API incorrecta: %s", request_api_key)
            return self._response_error(401, "Acceso no autorizado. Clave API inválida.")
        
        # El endpoint ahora usa auth='none', por lo que debemos asegurar el acceso con .sudo()
        # a los modelos necesarios.

        try:
            data = request.httprequest.json or {}
            _logger.info("Datos recibidos para la creación de novedad: %s", data)
            document_number = data.get('document_number')
            payload_rows = data.get('data')

            if not isinstance(payload_rows, list) or not payload_rows:
                return self._response_error(400, "Error: El campo 'data' debe ser una lista con al menos una hora extra.")

            sync_model = request.env['hr.overtime.sync'].sudo().with_context(lang='es_CO')
            overtime_model = request.env['hr.overtime'].sudo().with_context(lang='es_CO')

            overtime_vals_list = []
            for row_index, row_data in enumerate(payload_rows, start=1):
                if not isinstance(row_data, dict):
                    return self._response_error(400, f"Error: El elemento {row_index} de 'data' no tiene un formato válido.")
                overtime_vals, error = self._prepare_overtime_vals(row_data)
                if error:
                    return self._response_error(error.get('status', 400), f"Error en item {row_index}: {error.get('message')}")
                overtime_vals_list.append(overtime_vals)

            is_update = document_number not in (None, False, '')
            if is_update:
                overtime_sync = sync_model.search([('id', '=', document_number)], limit=1)
                if not overtime_sync:
                    return self._response_error(404, f"Error: No se encontró el documento de sincronización {document_number}.")

                blocked_lines = overtime_sync.line_ids.filtered(lambda line: line.state in ('validated', 'paid'))
                if blocked_lines:
                    return self._response_error(
                        400,
                        "Error: El documento tiene horas extra en estado Validada o Pagada y no se puede actualizar."
                    )

                # Solo se reemplazan líneas editables para mantener consistencia del documento sincronizado.
                overtime_sync.line_ids.unlink()
            else:
                overtime_sync = sync_model.create({
                    'send_date': fields.Datetime.now(),
                })

            created_overtimes = request.env['hr.overtime'].sudo()
            for overtime_vals in overtime_vals_list:
                overtime_vals['overtime_sync_id'] = overtime_sync.id
                created_overtimes |= overtime_model.create(overtime_vals)

            overtime_sync.write({
                'send_date': fields.Datetime.now(),
                'payload_json': json.dumps(data, ensure_ascii=False),
            })

            _logger.info("Documento de sincronización de horas extra %s procesado.", overtime_sync.id)
            return self._response_success({
                'document_number': overtime_sync.id,
                'novelties': [self._build_overtime_response(overtime) for overtime in created_overtimes],
                'message': 'Horas extra sincronizadas exitosamente.'
            })

        except Exception as e:
            request.env.cr.rollback()
            _logger.error("Error al procesar la solicitud de novedad: %s", e)
            return self._response_error(500, f"Error interno del servidor: {str(e)}")

    def _prepare_overtime_vals(self, data):
        """Prepara y valida los valores para crear hr.overtime."""
        contract_number = data.get('identification_number')
        category_name = data.get('category_name')
        quantity = data.get('qty')
        date_start_str = data.get('date_start')
        date_approved_str = data.get('date_approved') or False

        if not all([contract_number, category_name, quantity, date_start_str]):
            return None, {
                'status': 400,
                'message': "Faltan campos requeridos. Asegúrate de enviar 'identification_number', 'category_name', 'qty', 'date_start'."
            }

        employee = request.env['hr.employee'].sudo().search([
            ('identification_id', '=', contract_number)
        ], limit=1)

        if not employee:
            return None, {
                'status': 404,
                'message': f"El contrato {contract_number} no está asociado a un empleado."
            }

        contract = request.env['hr.contract'].sudo().search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'open')
        ], limit=1)

        if not contract:
            return None, {
                'status': 404,
                'message': f"No se encontró un contrato abierto para el número: {contract_number}."
            }

        overtime_type = request.env['hr.overtime.type'].sudo().search([
            ('name', '=', category_name),
            ('company_id', '=', contract.company_id.id)
        ], limit=1)

        if not overtime_type:
            return None, {
                'status': 404,
                'message': f"No se encontró una categoría de hora extra con el nombre: {category_name}."
            }

        return {
            'contract_id': contract.id,
            'employee_id': employee.id,
            'company_id': contract.company_id.id,
            'overtime_type_id': overtime_type.id,
            'date_start': date_start_str,
            'approve_date': date_approved_str,
            'qty': quantity,
            'state': 'draft',
        }, None

    def _build_overtime_response(self, overtime):
        return {
            'id': overtime.id,
            'name': overtime.name,
            'employee': overtime.employee_id.name,
            'contract': overtime.contract_id.name,
            'state': overtime.state,
        }

    def _response_success(self, data, status=200):
        """Genera una respuesta de éxito estandarizada."""
        # Asegura que los cambios se guarden antes de la respuesta
        request.env.cr.commit() 
        return http.Response(
            json.dumps({'success': True, 'data': data}),
            status=status,
            mimetype='application/json'
        )

    def _response_error(self, status, error_message):
        """Genera una respuesta de error estandarizada."""
        return http.Response(
            json.dumps({'success': False, 'error': error_message}),
            status=status,
            mimetype='application/json'
        )
