# -*- coding: utf-8 -*-

import logging
import re
from lxml import etree
from base64 import b64encode
from datetime import datetime, timedelta
from requests import post
from odoo.tools.safe_eval import safe_eval

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

INVOICE_HEADER = {
    'type_invoice': {
        'name': 'Tipo de factura',
        'type': 'select',
        'values': ('FV', 'FC', 'FV-NC', 'FV-ND', 'FC-NC', 'FC-ND', 'NC', 'ND'),
        'model': False,
        'domain': False,
        'required': True,
        'o_field': ['move_type'],
        'o_unique_rec': False,
    },
    'invoice_id': {
        'name': 'ID Prefactura',
        'type': 'char',
        'values': False,
        'model': False,
        'domain': False,
        'required': True,
        'o_field': ['code_cw'],
        'o_unique_rec': True,
    },
    'ref_invoice': {
        'name': 'ID Factura de referencia',
        'type': 'related',
        'values': False,
        'model': 'account.move',
        'domain': "[('code_cw','=','%s')]",
        'required': False,  # ('type_invoice', ('NC', 'ND')),
        'o_field': ['reversed_entry_id'],
        'o_unique_rec': False,
    },
    'partner': {
        'name': 'Cliente',
        'type': 'related',
        'values': False,
        'model': 'res.partner',
        'domain': "[('code_cw','=','%s')]",
        'required': True,
        'o_field': ['partner_id'],
        'o_unique_rec': False,
    },
    'city': {
        'name': 'Ciudad',
        'type': 'char',
        'values': False,
        'model': False,
        'domain': False,
        'required': False,
        'o_field': ['city'],
        'o_unique_rec': False,
    },
    'customer_order': {
        'name': 'Orden del cliente',
        'type': 'char',
        'values': False,
        'model': False,
        'domain': False,
        'required': False,
        'o_field': ['customer_order', 'ref'],
        'o_unique_rec': False,
    },
    'hbl': {
        'name': 'HBL',
        'type': 'char',
        'values': False,
        'model': False,
        'domain': False,
        'required': True,
        'o_field': ['hbl'],
        'o_unique_rec': False,
    },
    'mn': {
        'name': 'MN',
        'type': 'char',
        'values': False,
        'model': False,
        'domain': False,
        'required': False,
        'o_field': ['motor_ship'],
        'o_unique_rec': False,
    },
    'position': {
        'name': 'Posición',
        'type': 'char',
        'values': False,
        'model': False,
        'domain': False,
        'required': True,
        'o_field': ['position'],
        'o_unique_rec': False,
    },
    'origin': {
        'name': 'Origen',
        'type': 'char',
        'values': False,
        'model': False,
        'domain': False,
        'required': False,
        'o_field': ['origin'],
        'o_unique_rec': False,
    },
    'destination': {
        'name': 'Destino',
        'type': 'char',
        'values': False,
        'model': False,
        'domain': False,
        'required': False,
        'o_field': ['destination'],
        'o_unique_rec': False,
    },
    'container': {
        'name': 'Contenedor',
        'type': 'char',
        'values': False,
        'model': False,
        'domain': False,
        'required': False,
        'o_field': ['container_number'],
        'o_unique_rec': False,
    },
    'weight': {
        'name': 'Peso',
        'type': 'char',
        'values': False,
        'model': False,
        'domain': False,
        'required': False,
        'o_field': ['text_weight'],
        'o_unique_rec': False,
    },
    'volume': {
        'name': 'Volumen',
        'type': 'char',
        'values': False,
        'model': False,
        'domain': False,
        'required': False,
        'o_field': ['volume'],
        'o_unique_rec': False,
    },
    'vendor': {
        'name': 'Comercial',
        'type': 'related',
        'values': False,
        'model': 'res.partner',
        'domain': "[('salesman_code_cw','=','%s')]",
        'required': False,
        'o_field': ['salesman_cw_id'],
        'o_unique_rec': False,
    },
    'shipmentId': {
        'name': 'Embarque',
        'type': 'char',
        'values': False,
        'model': False,
        'domain': False,
        'required': False,
        'o_field': ['shipmentid'],
        'o_unique_rec': False,
    },
    'departmentCode': {
        'name': 'Código departamento',
        'type': 'char',
        'values': False,
        'model': False,
        'domain': False,
        'required': False,
        'o_field': ['department_code'],
        'o_unique_rec': False,
    },
    'eta': {
        'name': 'ETA',
        'type': 'datetime',
        'values': '%Y-%m-%dT%H:%M:%S',
        'model': False,
        'domain': False,
        'required': False,
        'o_field': ['eta'],
        'o_unique_rec': False,
    },
    'etd': {
        'name': 'ETD',
        'type': 'datetime',
        'values': '%Y-%m-%dT%H:%M:%S',
        'model': False,
        'domain': False,
        'required': False,
        'o_field': ['etd'],
        'o_unique_rec': False,
    },
    'doc_validity': {
        'name': 'Vigencia documento',
        'type': 'date',
        'values': '%Y-%m-%d',
        'model': False,
        'domain': False,
        'required': False,
        'o_field': ['doc_validity'],
        'o_unique_rec': False,
    },
    'closure': {
        'name': 'Cierre',
        'type': 'boolean',
        'values': False,
        'model': False,
        'domain': False,
        'required': False,
        'o_field': ['closure'],
        'o_unique_rec': False,
    },
    'service_level': {
        'name': 'Nivel de servicio',
        'type': 'char',
        'values': False,
        'model': False,
        'domain': False,
        'required': False,
        'o_field': ['service_level'],
        'o_unique_rec': False,
    },
    'consol_id': {
        'name': 'Consol ID',
        'type': 'char',
        'values': False,
        'model': False,
        'domain': False,
        'required': False,
        'o_field': ['id_consol'],
        'o_unique_rec': False,
    },
    'currency': {
        'name': 'Modena',
        'type': 'related',
        'values': False,
        'model': 'res.currency',
        'domain': "[('name','!=',False), ('name','=','%s')]",
        'required': True,
        'o_field': ['currency_id']
    },
    'company_code': {
        'name': 'Código Compañía',
        'type': 'related',
        'values': False,
        'model': 'res.company',
        'domain': "[('cw_code','=','%s')]",
        'required': False,
        'o_field': [],
        'o_unique_rec': False,
    },

}

INVOICE_LINES = {
    'product': {
        'name': 'ID Producto',
        'type': 'related',
        'values': False,
        'model': 'product.product',
        'domain': "[('default_code','=','%s')]",
        'required': True,
        'o_field': ['product_id'],
    },
    'uom_line': {
        'name': 'UdM',
        'type': 'related',
        'values': False,
        'model': 'uom.uom',
        'domain': "[('dian_uom_id.dian_code','=','%s')]",
        'required': False,
        'o_field': ['product_uom_id']
    },
    'description': {
        'name': 'Descripción',
        'type': 'char',
        'values': False,
        'model': False,
        'domain': False,
        'required': True,
        'o_field': ['name'],
    },
    'city_line': {
        'name': 'Ciudad',
        'type': 'char',
        'values': False,
        'model': False,
        'domain': False,
        'required': False,
        'o_field': ['city']
    },
    'qty': {
        'name': 'Cantidad',
        'type': 'float',
        'values': False,
        'model': False,
        'domain': False,
        'required': True,
        'o_field': ['quantity'],
    },
    'price_unit': {
        'name': 'Precio unitario',
        'type': 'float',
        'values': False,
        'model': False,
        'domain': False,
        'required': True,
        'o_field': ['price_unit'],
    },
    # 'currency': {
    #     'name': 'Modena',
    #     'type': 'related',
    #     'values': False,
    #     'model': 'res.currency',
    #     'domain': "[('name','!=',False), ('name','=','%s')]",
    #     'required': False,
    #     'o_field': ['currency_id']
    # },
}


class AccountMove(models.Model):
    _inherit = 'account.move'

    code_cw = fields.Char('Código CW', tracking=True)
    salesman_cw_id = fields.Many2one('res.partner', 'Vendedor CW')
    salesman_cw_txt = fields.Char('Vendedor CW (texto)')
    cw_log_ids = fields.One2many('invoice.cw.log', 'move_id', 'Log CW')
    ref_inv_cw_ids = fields.One2many(
        'invoice.reference.cw', 'move_id', 'Reference Invoices CW')
    shipmentid = fields.Char('N° Embarque')
    department_code = fields.Char('Código departamento')
    eta = fields.Datetime('ETA')
    etd = fields.Datetime('ETD')
    eta_txt = fields.Char('ETA (texto)')
    etd_txt = fields.Char('ETD (texto)')

    doc_validity = fields.Date('Vigencia documento')
    closure = fields.Boolean('Cierre', default=False)
    service_level = fields.Char('Nivel de servicio')
    id_consol = fields.Char('Consol ID')
    invoice_merge = fields.Boolean('Fusión facturas', default=False)

    def create_invoice_cargowise(self, vals):
        # log
        log_ok = self.env['ir.config_parameter'].sudo().get_param('cargowise.sync.logistic.log')
        if log_ok:
            _logger.info('\n--------- LOGISTIC ---------')
            _logger.info(vals)
            _logger.info('\n----------------------------')
        # Resolver compañía
        company_id = self._resolve_company_cw(vals)
        self = self.with_company(company_id)

        vals_invoice = self._validate_data_cw_create_invoice(vals, company_id)
        vals_invoice['company_id'] = company_id

        if 2 == 1:
            raise ValidationError(
                '\nLa interfaz para creacón de facturas para CargoWise '
                'se encuentra bloqueada por el area de Desarrollo de Odoo. \n'
                'Por el momento están habilitadas las validaciones de campos. '
                'Si ha llegado a este punto, quiere decir que ha superado con exito '
                'las validaciones de campos.\n'
                'Estos son los datos para la creación de Facturas Logisticas: \n\n %s'
                % str(vals_invoice)
            )
        move_type = vals['type_invoice']
        if move_type == 'FV-NC':
            vals_invoice['type_note'] = 'credit'
        if move_type == 'FV-ND':
            vals_invoice['type_note'] = 'debit'
        invoice_id = self.create(vals_invoice)

        # En v17 este método forzaba el recálculo con
        # invoice_id._onchange_partner_id() / _recompute_dynamic_lines(...).
        # _recompute_dynamic_lines ya no existe en v19: el equivalente actual
        # es recomputar tax_ids en las líneas (toma el impuesto configurado
        # en el producto) y luego los totales del documento.
        invoice_id.invoice_line_ids._compute_tax_ids()
        invoice_id._compute_tax_totals()

        try:
            api_cw = self.env['res.partner'].with_company(
                company_id).search(
                [('name', '=', 'Api CW')], limit=1)
            invoice_id.message_unsubscribe(partner_ids=api_cw.ids)
        except Exception:
            pass
        return invoice_id.id

    def _resolve_company_cw(self, vals):
        """Resuelve la compañía para la creación de facturas.
        Si se informa company_code, busca la compañía por el código CargoWise (cw_code).
        Si no, y solo existe una compañía activa, la usa automáticamente.
        Si hay múltiples compañías, exige el código."""
        company_obj = self.env['res.company']
        if vals.get('company_code'):
            company = company_obj.search(
                [('cw_code', '=', vals['company_code'])], limit=1)
            if not company:
                raise ValidationError(_(
                    'No se encontró la compañía con código "%s". '
                    'Verifique el campo company_code.'
                ) % vals['company_code'])
            return company.id

        # Auto-detectar si solo hay una compañía
        company_count = company_obj.search_count([])
        if company_count == 1:
            return company_obj.search([], limit=1).id
        elif company_count == 0:
            raise ValidationError(_(
                'No hay compañías configuradas en el sistema.'
            ))
        else:
            raise ValidationError(_(
                'Entorno multicompañía detectado (%s compañías). '
                'Debe informar el campo company_code para indicar '
                'en qué compañía crear la factura.'
            ) % company_count)

    def _validate_data_cw_create_invoice(self, vals, company_id=False):
        # Remover company_code antes del mapeo (ya fue procesado)
        vals_copy = dict(vals)
        vals_copy.pop('company_code', None)
        if vals_copy.get('type_invoice') in ('FC-NC', 'FC-ND', 'FV-NC', 'FV-ND') and \
                vals_copy.get('ref_invoice'):
            del vals_copy['ref_invoice']
        validated_vals = {}
        msg_error = ''
        # Campo no está en xml
        msg_error += self._validate_cw_not_in_xml(vals_copy)
        # Campo vacío
        msg_error += self._validate_cw_empty_fields(vals_copy)
        # Mapeos
        text, validated_vals = self._validate_cw_mapping_fields(
            vals_copy, company_id)
        msg_error += text

        if msg_error:
            raise ValidationError(msg_error)

        validated_vals = self._validate_cw_type_invoice(validated_vals, company_id)
        validated_vals = self._add_default_values_cw(validated_vals, company_id)
        return validated_vals

    def _validate_cw_not_in_xml(self, vals):
        msg = ''
        msg += self._validate_cw_not_xml_section(vals, INVOICE_HEADER, 'H-NX', 0)
        l = 1
        for line in vals.get('lines', []):
            msg += self._validate_cw_not_xml_section(
                line, INVOICE_LINES, 'L{:02d}-NX'.format(l), l)
            l += 1
        return msg

    def _validate_cw_empty_fields(self, vals):
        msg = ''
        msg += self._validate_cw_empty_fields_section(vals, INVOICE_HEADER, 'H-OF', 0)
        l = 1
        for line in vals.get('lines', []):
            msg += self._validate_cw_empty_fields_section(
                line, INVOICE_LINES, 'L{:02d}-OF'.format(l), l)
            l += 1
        return msg

    def _validate_cw_not_xml_section(self, vals=None, MAPPING=None, code='', line=0):
        vals = vals or {}
        MAPPING = MAPPING or {}
        msg = ''
        c = 1
        for field, config in MAPPING.items():
            required = config.get('required')
            if (isinstance(required, tuple) and
                vals.get(required[0]) in required[1] and
                field not in vals) or \
                (not isinstance(required, tuple) and
                 required and
                 field not in vals):
                msg += '\n- {}{:03d}: Campo {} ({}) {}no se encuentra ' \
                       'en la estructura XML de recepción.'.format(
                           code, c, config['name'], field,
                           line > 0 and 'de la línea {:02d} '.format(line) or '')
            c += 1
        return msg

    def _validate_cw_empty_fields_section(self, vals=None, MAPPING=None, code='', line=0):
        vals = vals or {}
        MAPPING = MAPPING or {}
        msg = ''
        c = 1
        for field, config in MAPPING.items():
            required = config.get('required')
            if required and field in vals:
                if isinstance(required, tuple) and \
                        vals.get(required[0]) in required[1] and \
                        not vals[field]:
                    msg += '\n- {}{:03d}: Campo {} ({}) es obligatorio{}.'.format(
                        code, c, config['name'], field,
                        line > 0 and ' en la línea {:02d}'.format(line) or '')
                elif not isinstance(required, tuple) and field in vals and not vals[field]:
                    msg += '\n- {}{:03d}: Campo {} ({}) es obligatorio{}.'.format(
                        code, c, config['name'], field,
                        line > 0 and ' en la línea {:02d},'.format(line) or '')
            c += 1
        return msg

    def _validate_cw_mapping_fields(self, vals, company_id=False):
        out_vals = {}
        msg = ''
        text, out = self._validate_cw_mapping_fields_section(
            vals, INVOICE_HEADER, 'H-MP', 0, company_id)
        msg += text
        out_vals.update(out)
        l = 1
        lines = []
        for line in vals.get('lines', []):
            text, out = self._validate_cw_mapping_fields_section(
                line, INVOICE_LINES, 'L{:02d}-MP'.format(l), l, company_id)
            msg += text
            lines.append(out)
            l += 1
        out_vals['invoice_line_ids'] = lines
        return msg, out_vals

    def _get_val_out(self, val):
        if val or isinstance(val, (int, float)):
            return val
        return False

    def _validate_cw_mapping_fields_section(self, vals=None, MAPPING=None, code='', line=0, company_id=False):
        vals = vals or {}
        MAPPING = MAPPING or {}
        move_obj = self.env['account.move']
        msg = ''
        out_vals = {}
        c = 1
        for field, config in MAPPING.items():
            if config.get('type') != 'related':
                for o_field in config['o_field']:
                    out_vals[o_field] = self._get_val_out(vals.get(field, False))
            required = config.get('required')
            field_present = (isinstance(required, tuple) and
                             vals.get(required[0]) in required[1] and
                             field in vals and vals[field]) or \
                            (not isinstance(required, tuple) and
                             field in vals and vals[field])
            if field_present:
                if config.get('type') == 'select':
                    if vals[field] not in config['values']:
                        msg += '\n- {}{:03d}: El valor "{}" para {} ({})' \
                            '{} no está en los valores permitidos [{}].'.format(
                                code, c, vals[field], config['name'], field,
                                line > 0 and ', línea {:02d},'.format(line) or '',
                                ', '.join(config['values']))
                elif config.get('type') == 'related':
                    domain = safe_eval(config['domain'] % str(vals[field]))
                    # Filtrar por compañía en búsquedas de modelos con company_id
                    if company_id and config.get('model'):
                        model = self.env[config['model']]
                        if 'company_id' in model._fields:
                            domain.append(('company_id', 'in', [company_id, False]))
                        record = model.search_read(domain, ['id'])
                    else:
                        record = self.env[config['model']].search_read(domain, ['id'])
                    if not record:
                        msg += '\n- {}{:03d}: No se encontró {} con ' \
                            'código "{}" (Campo "{}"){} en la BD de Odoo.'.format(
                                code, c, config['name'], vals[field], field,
                                line > 0 and ', línea {:02d}'.format(line) or '')
                    elif len(record) > 1:
                        msg += '\n- {}{:03d}: Más de un {} con código "{}" (Campo "{}"){} en la BD de Odoo. IDs: ({})'.format(
                            code, c, config['name'], vals[field], field,
                            line > 0 and ', línea {:02d}'.format(line) or '',
                            ', '.join([str(r['id']) for r in record]))
                    else:
                        for o_field in config['o_field']:
                            out_vals[o_field] = record[0]['id']
                elif config.get('type') == 'datetime':
                    dt_format = config.get('values')
                    dt = datetime.strptime(vals[field], dt_format)
                    dt = dt + timedelta(hours=5)
                    for o_field in config['o_field']:
                        out_vals[o_field] = dt.strftime('%Y-%m-%d %H:%M:%S')
            if config.get('o_unique_rec', False):
                unique_domain = [
                    (config['o_field'][0], '!=', False),
                    (config['o_field'][0], '=', vals[field])
                ]
                if company_id:
                    unique_domain.append(('company_id', '=', company_id))
                records = move_obj.search_read(
                    unique_domain, ['id', 'name'])
                if records:
                    msg += '\n- H-UNQ{:03d}: Ya existe factura con {} código "{}" ({}){}. IDs: ({})'.format(
                        c, config['name'], vals.get(field, ''), field,
                        line > 0 and ', en la línea {:02d},'.format(line) or '',
                        ', '.join(['%s-%s' % (r['id'], r['name']) for r in records]))
            c += 1
        return msg, out_vals

    def _validate_cw_type_invoice(self, vals, company_id=False):
        move_obj = self.env['account.move']
        inv_type = {
            'FV': 'out_invoice',
            'FV-NC': 'out_refund',
            'FV-ND': 'out_invoice',
            'FC': 'in_invoice',
            'FC-NC': 'in_refund',
            'FC-ND': 'in_invoice',
        }
        new_inv_type = vals['move_type']
        if new_inv_type not in inv_type:
            ref_id = str(vals.get('reversed_entry_id', '')).isdigit() and \
                int(vals.get('reversed_entry_id', 0)) or 0
            ref_inv_id = move_obj.browse(ref_id)
            if not ref_inv_id:
                raise ValidationError(_(
                    'No fue posible crear la factura rectificativa (%s). '
                    'La factura de referencia (id: %s) no se encuentra en el sistema.'
                ) % (vals.get('code_cw', 'N/A'), str(ref_id)))
            if company_id and ref_inv_id.company_id.id != company_id:
                raise ValidationError(_(
                    'No fue posible crear la factura rectificativa (%s). '
                    'La factura de referencia (%s) pertenece a otra compañía.'
                ) % (vals.get('code_cw', 'N/A'), ref_inv_id.code_cw or 'N/A'))
            if ref_inv_id.state != 'posted':
                raise ValidationError(_(
                    'No fue posible crear la factura rectificativa (%s). '
                    'La factura de referencia (%s) debe estar publicada.'
                ) % (vals.get('code_cw', 'N/A'), ref_inv_id.code_cw or 'N/A'))
            ref_inv_type = (ref_inv_id.move_type == 'out_invoice' and 'FV') or \
                           (ref_inv_id.move_type == 'in_invoice' and 'FC') or False
            if not ref_inv_type:
                raise ValidationError(_(
                    'No fue posible crear la nota rectificativa (%s). '
                    'La factura de referencia (%s) no corresponde a '
                    'una factura de venta (FV) o '
                    'una factura de compra (FC). [move_type: "%s"]'
                ) % (vals.get('code_cw', 'N/A'), ref_inv_id.code_cw or 'N/A',
                    ref_inv_id.move_type,
                ))
            new_inv_type = '%s-%s' % (ref_inv_type, new_inv_type)
            vals['move_type'] = inv_type.get(new_inv_type)
        else:
            vals['move_type'] = inv_type.get(new_inv_type)
            if 'reversed_entry_id' in vals:
                del vals['reversed_entry_id']

        # Lines
        analytic_id = self._get_analytic_account_cw(
            vals.get('position', False), company_id)
        lines = []
        reverse_sign = self.env['ir.config_parameter'].search(
            [('key', '=', 'reverse.nc.cw.api')], limit=1)
        for line in vals.get('invoice_line_ids', []):
            if analytic_id:
                line['analytic_distribution'] = {str(analytic_id): 100}
            if vals['move_type'] in ('out_refund', 'in_refund') and \
                    reverse_sign and reverse_sign.value == 'True':
                line['price_unit'] = line.get('price_unit', 0) * -1
            lines.append((0, 0, line))
        vals['invoice_line_ids'] = lines
        return vals

    def _get_analytic_account_cw(self, analytic_val=False, company_id=False):
        if analytic_val:
            analytic_ac_obj = self.env['account.analytic.account']
            plan_obj = self.env['account.analytic.plan']
            domain = [('name', '=', analytic_val)]
            if company_id:
                domain.append(('company_id', 'in', [company_id, False]))
            analytic_id = analytic_ac_obj.search_read(domain, ['id'], limit=1)
            if analytic_id:
                return analytic_id[0]['id']
            else:
                plan_id = plan_obj.search_read([], ['id'], limit=1)
                create_vals = {
                    'name': analytic_val,
                    'plan_id': plan_id and plan_id[0]['id'] or False,
                }
                if company_id:
                    create_vals['company_id'] = company_id
                analytic_id = analytic_ac_obj.create(create_vals)
                return analytic_id.id
        else:
            return False

    def _add_default_values_cw(self, vals, company_id=False):
        journal_obj = self.env['account.journal']
        # journal
        type_journal = 'sale' if vals['move_type'] in ('out_invoice', 'out_refund') else 'purchase'
        journal_domain = [
            ('type', '=', type_journal),
            ('is_default_cw', '=', True),
        ]
        if company_id:
            journal_domain.append(('company_id', '=', company_id))
        journal_id = journal_obj.search(journal_domain, limit=1)
        if not journal_id:
            fallback_domain = [('type', '=', type_journal)]
            if company_id:
                fallback_domain.append(('company_id', '=', company_id))
            journal_id = journal_obj.search(fallback_domain, limit=1)
        if journal_id and not vals.get('journal_id'):
            vals['journal_id'] = journal_id.id
        return vals

    # ---- Envío de estados hacia CargoWise ----

    def get_xml_request_cw(self, values=None, code_cw=False):
        self.ensure_one()
        values = values or []
        company_id = self.company_id
        template = self.env.ref('cargowise_sync_logistic_odone.cw_template_xml', raise_if_not_found=False)
        if not template:
            return b''
        request = self.env['ir.qweb']._render(template.id, {
            'enterprise_id': company_id.api_cw_enterprise_id,
            'server': company_id.api_cw_server,
            'invoice_id': code_cw or self.code_cw,
            'date': fields.Datetime.context_timestamp(
                self, datetime.now()).strftime('%Y-%m-%dT%H:%M:%S'),
            'event_type': company_id.api_cw_event_type,
            'event_reference': company_id.api_cw_event_reference,
            'values': values,
        })
        return request

    def send_status_to_cw(self, values, type_doc, ref_id=False):
        self.ensure_one()
        if self.code_cw and not self.ref_inv_cw_ids:
            request = self.get_xml_request_cw(values)
            self.sync_odoo_cw(
                request,
                type_doc,
                self.code_cw
            )
        elif self.ref_inv_cw_ids:
            # Generar lista de request
            request_list = []
            for ref in self.ref_inv_cw_ids.filtered(lambda x: ref_id and x.id == ref_id or not ref_id):
                request_val = self.get_xml_request_cw(values, ref.code_cw)
                request_list.append([ref.code_cw, ref.id, request_val])
            # Enviar lista de request
            for request in request_list:
                self.sync_odoo_cw(
                    request[2],
                    type_doc,
                    request[0],
                    request[1]
                )
        else:
            raise ValidationError(_(
                'It is only allowed to send invoice status to Cargowise, '
                'documents with CW code or with Invoices reference CW'
            ))

    # FACTURADO
    def send_posted_invoice_to_cw(self, ref_id=False):
        self.ensure_one()
        if (self.code_cw and not self.ref_inv_cw_ids) or (self.ref_inv_cw_ids):
            type_doc = 'invoiced'

            values = [
                {
                    'type': 'AccTransactionHeader.AH_TransactionReference',
                    'value': self.name
                },
                {
                    'type': 'AccTransactionHeader.InvoiceRemittanceReference',
                    'value': 'FACTURADO'
                }
            ]
            self.send_status_to_cw(values, type_doc, ref_id)
        else:
            pass

    # PAGADO
    def send_posted_paid_to_cw(self, ref_id=False):
        self.ensure_one()
        if (self.code_cw and not self.ref_inv_cw_ids) or (self.ref_inv_cw_ids):
            type_doc = 'paid'

            values = [
                {
                    'type': 'AccTransactionHeader.InvoiceRemittanceReference',
                    'value': 'PAGADO'
                }
            ]
            self.send_status_to_cw(values, type_doc, ref_id)
            # request = self.get_xml_request_cw(values)
            # self.sync_odoo_cw(request, type_doc)
        else:
            pass

    # CANCELADO
    def send_posted_cancelled_to_cw(self, ref_id=False):
        self.ensure_one()
        if (self.code_cw and not self.ref_inv_cw_ids) or (self.ref_inv_cw_ids):
            type_doc = 'cancelled'

            values = [
                {
                    'type': 'AccTransactionHeader.InvoiceRemittanceReference',
                    'value': 'CANCELADO'
                }
            ]
            self.send_status_to_cw(values, type_doc, ref_id)
            # request = self.get_xml_request_cw(values)
            # self.sync_odoo_cw(request, type_doc)
        else:
            pass

    def sync_odoo_cw(self, xml, type_doc, code_cw=False, ref_cw_id=False):
        self.ensure_one()
        try:
            xml = xml.encode().decode()
            auth = self.company_id._get_authorization_cw_api()
            url = self.company_id.api_cw_url
            header = {
                'Authorization': 'Basic %s' % auth
            }
            response = post(url=url, headers=header, data=xml)
            if response.status_code == 200:
                response_txt = response.text.replace('ï»¿', '')
                self._create_log_odoo_cw(
                    response_txt, xml, type_doc, code_cw, ref_cw_id)
            else:
                self._create_log_odoo_cw(
                    response.text, xml, type_doc, code_cw, ref_cw_id)
        except Exception as error:
            self._create_log_odoo_cw(
                '\n'.join([str(x) for x in error.args]),
                xml,
                type_doc,
                code_cw,
                ref_cw_id
            )
            # raise ValidationError(_(
            #     'Ocurrio un error: %s'
            # ) % error)

    def _create_log_odoo_cw(self, response, request, type_doc, code_cw=False, ref_cw_id=False):
        self.ensure_one()
        log_obj = self.env['invoice.cw.log']
        result_txt = False
        state = 'error'

        if 'UniversalResponse' in response:
            result = self._proccess_response_cw(response)
            ctx_coll = result.get('ctx_collection', {})
            result_txt = \
                'Estado Conexión:       {s_1}\n' \
                '--> {l_1}\n\n' \
                'Estado Actualización:  {s_2}\n' \
                '--> {l_2}'.format(
                    s_1=result.get('status_root', '-'),
                    l_1=result.get('log_root', ''),
                    s_2=ctx_coll.get('ProcessingStatusCode', '-'),
                    l_2=ctx_coll.get('FailureReason', '') or ctx_coll.get(
                        'ProcessingLog', '')
                )
            if ctx_coll.get('ProcessingStatusCode', '-') == 'PRS':
                state = 'done'

        log_obj.create({
            'name': _('Envío %s') % str(len(self.cw_log_ids) + 1),
            'request': b64encode(request.encode()),
            'request_fname': 'request.xml',
            'response': result_txt and b64encode(response.encode()) or False,
            'response_fname': 'response.xml',
            'response_txt': result_txt or response,
            'move_id': self.id,
            'type_doc': type_doc,
            'state': state,
            'code_cw': code_cw,
            'ref_inv_cw_id': ref_cw_id
        })

    # ["|","&","&",["state","=","draft"],["code_cw","!=",False],["ref_inv_cw_ids","=",False],"&","&",["state","=","draft"],["code_cw","=",False],["ref_inv_cw_ids","!=",False]]

    def _proccess_response_cw(self, response):
        ns = 'http://www.cargowise.com/Schemas/Universal/2011/11'
        result = {}
        ctxcol = {}
        root = etree.fromstring(response.encode())
        status_root = root.find('{%s}Status' % ns)
        log_root = root.find('{%s}ProcessingLog' % ns)
        for cc in root.iter('{%s}ContextCollection' % ns):
            for ctx in cc.findall('{%s}Context' % ns):
                t_name = ctx.find('{%s}Type' % ns)
                t_value = ctx.find('{%s}Value' % ns)
                ctxcol[t_name.text] = t_value.text
        result = {
            'status_root': status_root.text,
            'log_root': log_root.text,
            'ctx_collection': ctxcol
        }
        return result

    def resend_status_invoice_to_cw(self, num_docs=0):
        _logger.info("Odoo-CW INV STATE: Start")
        move_obj = self.env['account.move']

        try:
            err_query = '''
                SELECT log.move_id
                FROM (SELECT move_id, string_agg(state, ',') AS state_log
                        FROM invoice_cw_log
                        GROUP BY move_id
                        ORDER BY move_id) AS log
                WHERE position('done' in log.state_log) = 0'''

            self.env.cr.execute(err_query)
            move_error_ids = [x[0] for x in self.env.cr.fetchall()]
            query = '''
                SELECT move_id
                FROM invoice_cw_log
                WHERE move_id IS NOT NULL
                    AND state = 'done'
                    AND type_doc = %s
                GROUP BY move_id
            '''
            events = {
                'invoiced': {'state': 'posted', 'domain': [], 'sync': 'send_posted_invoice_to_cw'},
                'paid': {'state': 'posted', 'domain': [('amount_residual', '=', 0)], 'sync': 'send_posted_paid_to_cw'},
                'cancelled': {'state': 'cancel', 'domain': [], 'sync': 'send_posted_cancelled_to_cw'}}
            for type_ev, config in events.items():
                self.env.cr.execute(query, [type_ev])
                move_no_ids = [x[0] for x in self.env.cr.fetchall()]
                domain = config['domain']
                domain += [('state', '=', config['state']),
                           ('id', 'not in', move_error_ids + move_no_ids),
                           '|',
                           ('code_cw', '!=', False),
                           ('ref_inv_cw_ids', '!=', False),]
                moves = move_obj.search(domain, limit=num_docs)

                for move in moves:
                    getattr(move, config['sync'])()
        except Exception as error:
            _logger.warning(error)
        _logger.info("Odoo-CW INV STATE: End")

    def action_merge_invoice_cw(self):
        '''
            Merge invoices sent from Cargowise to be management in 
            a single invoice from Odoo.
        '''
        inv_not_draft = self.filtered(lambda i: i.state != 'draft')
        inv_not_cw = self.filtered(lambda i: not i.code_cw)
        if inv_not_draft:
            raise ValidationError(_(
                'It is only allowed to merge invoices in draft status.\n\n'
                '%s'
            ) % (
                '\n'.join(
                    [
                        _('Invoice Id: %s / Code CW: %s is in status %s') % (
                            rec.id,
                            rec.code_cw,
                            rec.state
                        ) for rec in inv_not_draft
                    ]
                )
            ))

        if inv_not_cw:
            raise ValidationError(_(
                'It is only allowed to merge invoices sent from Cargowise.\n\n'
                '%s'
            ) % (
                '\n'.join(
                    [_(
                        'Invoice Id: %s is not invoice sent from Cargowise.'
                    ) % rec.id for rec in inv_not_cw
                    ]
                )
            ))
        if len(self.partner_id) > 1:
            raise ValidationError(_(
                'It is only allowed to merge invoices with same %s'
            ) % (self[0].move_type in ('out_invoice', 'out_refund') and _('client') or _('provider'))
            )
        lines = []
        ref_data = []
        for record in self:
            # Lineas
            for line in record.invoice_line_ids.filtered(lambda l: not l.display_type):
                line_vals = {
                    'product_id': line.product_id.id,
                    'name': line.name,
                    'city': line.city,
                    'code': line.code,
                    'quantity': line.quantity,
                    'multi_price_unit': line.multi_currency_id and line.multi_price_unit or line.price_unit,
                    'price_unit': line.price_unit,
                    'multi_currency_id': line.multi_currency_id and line.multi_currency_id.id or False,
                    'analytic_distribution': line.analytic_distribution,
                    'product_uom_id': line.product_uom_id and line.product_uom_id.id or False
                }
                lines.append((0, 0, line_vals))
            # Referencia facturas originales
            ref_inv = {
                'code_cw': record.code_cw,
                'city': record.city,
                'customer_order': record.customer_order,
                'hbl': record.hbl,
                'motor_ship': record.motor_ship,
                'position': record.position,
                'destination': record.destination,
                'text_weight': record.text_weight,
                'volume': record.volume,
                'salesman_cw_id': record.salesman_cw_id and record.salesman_cw_id.id
            }
            ref_data.append((0, 0, ref_inv))
        # Nueva factura
        inv_data = {
            'partner_id': self[0].partner_id.id,
            'move_type': self[0].move_type,
            'journal_id': self[0].journal_id.id,
            'currency_id': self[0].currency_id.id,
            'multi_currency': self[0].multi_currency,
            'current_exchange_rate': self[0].current_exchange_rate,
            'invoice_line_ids': lines,
            'ref_inv_cw_ids': ref_data,
            'salesman_cw_txt': self._join_field_values('salesman_cw_id'),
            'code_cw': self._join_field_values('code_cw'),
            'position': self._join_field_values('position'),
            'hbl': self._join_field_values('hbl'),
            'volume': self._join_field_values('volume'),
            'motor_ship': self._join_field_values('motor_ship'),
            'shipmentid': self._join_field_values('shipmentid'),
            'department_code': self._join_field_values('department_code'),
            'eta_txt': self._join_field_datetime('eta'),
            'etd_txt': self._join_field_datetime('etd'),
            'invoice_merge': True,
            'service_level': self._join_field_values('service_level'),
            'origin': self._join_field_values('origin'),
            'destination': self._join_field_values('destination'),
            'customer_order': self._join_field_values('customer_order'),
            'text_weight': self._join_field_values('text_weight'),
        }
        # inv_data = self._add_default_values_cw(inv_data)
        invoice_id = self.env['account.move'].with_context(
            onchange_date_aux=True).create(inv_data)
        invoice_id = invoice_id.with_context(check_move_validity=False)

        invoice_id._onchange_partner_id()
        invoice_id._onchange_date_aux()
        invoice_id.line_ids.onchange_multi_price_unit()

        # v17 recalculaba aquí con _onchange_account_id() / _onchange_price_subtotal()
        # y _recompute_dynamic_lines(...). Ese último método ya no existe en v19;
        # el equivalente es recomputar tax_ids en las líneas y los totales.
        invoice_id.invoice_line_ids._compute_tax_ids()
        invoice_id._compute_tax_totals()

        print("FACTURA MERGE", invoice_id.id)
        # Cancelar facturas originales de la base de datos
        self.button_cancel()
        # TODO HABILITAR AL FINAL

        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoice Merge (*%s)') % str(invoice_id.id),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            # 'context': {},
            'domain': [
                ('id', '=', invoice_id.id)
            ],
            'target': 'current',
        }

    def _join_field_values(self, field):
        values = []
        seen = set()
        for record in self:
            if field == 'salesman_cw_id':
                value = record.salesman_cw_id.name
            else:
                value = getattr(record, field)
            if value and value not in seen:
                seen.add(value)
                values.append(value)
        return ' / '.join(values)

    def _join_field_datetime(self, field, date_format='%Y-%m-%d'):
        values = []
        seen = set()
        for record in self:
            value = getattr(record, field)
            if value and value.strftime(date_format) not in seen:
                seen.add(value.strftime(date_format))
                values.append(value.strftime(date_format))
        return ' / '.join(values)
