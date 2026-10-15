# -*- coding: utf-8 -*-

import json
import uuid
from http import HTTPStatus
from datetime import date, datetime

from odoo import http, _
from odoo.http import request


class DateTimeEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj, datetime) or isinstance(obj, date):
            return obj.isoformat()
        return super(DateTimeEncoder, self).default(obj)


class ExcelOdooApi(http.Controller):
    @http.route('/odc15/<key>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_data_for_excel(self, key, **kw):
        if not self.is_valid_uuid(key):
            return self._create_response(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE.phrase,
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE.value)
        record_id = request.env['excel.data.search'].sudo().search(
            [('access_key', '=', key)], limit=1)
        if record_id and record_id.query:
            query = 'SELECT %s' % record_id.query
        else:
            return self._create_response(
                HTTPStatus.UNPROCESSABLE_ENTITY.phrase,
                HTTPStatus.UNPROCESSABLE_ENTITY.value)

        request.cr.execute(query)
        data = request.cr.dictfetchall()
        if record_id.type_out == 'json':
            data = json.dumps(data, cls=DateTimeEncoder)
            headers = [('Content-Type', 'application/json'),
                       ('Cache-Control', 'no-store')]
            response = request.make_response(data, headers)
            response.status_code = HTTPStatus.OK.value
            return response
        else:
            data = str(request.env['ir.ui.view']._render_template(
                'excel_odoo_api.excel_data_search_table', {'lines': data}))

        out = data
        return out

    def is_valid_uuid(self, val):
        try:
            uuid.UUID(str(val))
            return True
        except ValueError:
            return False

    def _create_response(self, data, status: int) -> dict:
        data = json.dumps({
            'message': data,
            'status': status,
        })
        headers = [('Content-Type', 'application/json'),
                   ('Cache-Control', 'no-store')]
        response = request.make_response(data, headers)
        response.status_code = status
        return response
