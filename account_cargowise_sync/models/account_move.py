# -*- coding: utf-8 -*-
import logging
from base64 import b64encode
from datetime import datetime, timedelta

from requests import post

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
        'required': False,
        'o_field': ['reversed_entry_id'],
        'o_unique_rec': False,
    },
    'invoice_date': {
        'name': 'Fecha de la factura',
        'type': 'date',
        'values': '%Y-%m-%d',
        'model': False,
        'domain': False,
        'required': False,
        'o_field': ['invoice_date'],
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
    'journey': {
        'name': 'Trayecto',
        'type': 'char',
        'values': False,
        'model': False,
        'domain': False,
        'required': False,
        'o_field': ['destination'],
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
    'description': {
        'name': 'Descripción',
        'type': 'char',
        'values': False,
        'model': False,
        'domain': False,
        'required': True,
        'o_field': ['name'],
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
}


class AccountMove(models.Model):
    _inherit = 'account.move'

    # ---- Campos operación logística (consolcargo) ----
    city = fields.Char(string='Ciudad')
    position = fields.Char(string='Posición')
    hbl = fields.Char(string='HBL')
    container_number = fields.Char(string='Número contenedor')
    origin = fields.Char(string='Origen')
    destination = fields.Char(string='Destino')
    volume = fields.Char(string='Volumen')
    customer_order = fields.Char(string='Orden del cliente')
    motor_ship = fields.Char(string='Motonave')
    text_weight = fields.Char(string='Peso')
    current_exchange_rate = fields.Float(
        string='TRM',
        readonly=False,
        default=1,
    )
    due_days = fields.Integer(
        string='Días de Vencimiento',
        compute='_compute_due_days',
        store=True,
    )
    release_status = fields.Selection(
        selection=[('auto_release', 'Liberación Automática')],
        string='Estado Liberación',
    )

    # ---- Campos CargoWise ----
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

    @api.depends('invoice_date_due', 'payment_state', 'state')
    def _compute_due_days(self):
        today = fields.Date.today()
        for record in self:
            if record.payment_state in ('paid', 'in_payment', 'reversed'):
                record.due_days = 0
            elif record.invoice_date_due and record.state == 'posted':
                record.due_days = (today - record.invoice_date_due).days
            else:
                record.due_days = 0

    # ---- Métodos CargoWise ----

    def create_invoice_cargowise(self, vals):
        self = self.sudo()
        vals_invoice = self._validate_data_cw_create_invoice(vals)
        move_type = vals['type_invoice']
        if move_type == 'FV-NC':
            vals_invoice['type_note'] = 'credit'
        if move_type == 'FV-ND':
            vals_invoice['type_note'] = 'debit'
        invoice_id = self.create(vals_invoice)
        try:
            api_cw = self.env['res.partner'].search(
                [('name', '=', 'Api CW')], limit=1)
            invoice_id.message_unsubscribe(partner_ids=api_cw.ids)
        except Exception:
            pass
        return invoice_id.id

    def _validate_data_cw_create_invoice(self, vals):
        if vals.get('type_invoice') in ('FC-NC', 'FC-ND', 'FV-NC', 'FV-ND') and \
                vals.get('ref_invoice'):
            del vals['ref_invoice']
        validated_vals = {}
        msg_error = ''
        msg_error += self._validate_cw_not_in_xml(vals)
        msg_error += self._validate_cw_empty_fields(vals)
        text, validated_vals = self._validate_cw_mapping_fields(vals)
        msg_error += text
        if msg_error:
            raise ValidationError(msg_error)
        validated_vals = self._validate_cw_type_invoice(validated_vals)
        validated_vals = self._add_default_values_cw(validated_vals)
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

    def _validate_cw_mapping_fields(self, vals):
        out_vals = {}
        msg = ''
        text, out = self._validate_cw_mapping_fields_section(vals, INVOICE_HEADER, 'H-MP', 0)
        msg += text
        out_vals.update(out)
        l = 1
        lines = []
        for line in vals.get('lines', []):
            text, out = self._validate_cw_mapping_fields_section(
                line, INVOICE_LINES, 'L{:02d}-MP'.format(l), l)
            out['tax_ids'] = []
            msg += text
            lines.append(out)
            l += 1
        out_vals['invoice_line_ids'] = lines
        return msg, out_vals

    def _get_val_out(self, val):
        if val or isinstance(val, (int, float)):
            return val
        return False

    def _validate_cw_mapping_fields_section(self, vals=None, MAPPING=None, code='', line=0):
        vals = vals or {}
        MAPPING = MAPPING or {}
        move_obj = self.env['account.move']
        msg = ''
        out_vals = {}
        c = 1
        for field, config in MAPPING.items():
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
                    domain = eval(config['domain'] % str(vals[field]))
                    record = self.env[config['model']].search_read(domain, ['id'])
                    if not record:
                        msg += '\n- {}{:03d}: No se encontró {} con ' \
                            'código "{}" ({}){}. '.format(
                                code, c, config['name'], vals[field], field,
                                line > 0 and ', línea {:02d}'.format(line) or '')
                    elif len(record) > 1:
                        msg += '\n- {}{:03d}: Más de un {} con código "{}" ({}){}. IDs: ({})'.format(
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
                records = move_obj.search_read([
                    (config['o_field'][0], '!=', False),
                    (config['o_field'][0], '=', vals.get(field, False)),
                ], ['id', 'name'])
                if records:
                    msg += '\n- H-UNQ{:03d}: Ya existe factura con {} código "{}" ({}). IDs: ({})'.format(
                        c, config['name'], vals.get(field, ''), field,
                        ', '.join(['%s-%s' % (r['id'], r['name']) for r in records]))
            c += 1
        return msg, out_vals

    def _validate_cw_type_invoice(self, vals):
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
                    'La factura de referencia (%s) no es FV ni FC.'
                ) % (vals.get('code_cw', 'N/A'), ref_inv_id.code_cw or 'N/A'))
            new_inv_type = '%s-%s' % (ref_inv_type, new_inv_type)
            vals['move_type'] = inv_type.get(new_inv_type)
        else:
            vals['move_type'] = inv_type.get(new_inv_type)
            vals.pop('reversed_entry_id', None)

        # Cuenta analítica
        analytic_id = self._get_analytic_account_cw(vals.get('position', False))
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

    def _get_analytic_account_cw(self, analytic_val=False):
        if analytic_val:
            analytic_ac_obj = self.env['account.analytic.account']
            plan_obj = self.env['account.analytic.plan']
            analytic_id = analytic_ac_obj.search_read([('name', '=', analytic_val)], ['id'], limit=1)
            if analytic_id:
                return analytic_id[0]['id']
            else:
                plan_id = plan_obj.search_read([], ['id'], limit=1)
                analytic_id = analytic_ac_obj.create({
                    'name': analytic_val,
                    'plan_id': plan_id and plan_id[0]['id'] or False,
                })
                return analytic_id.id
        else:
            return False

    def _add_default_values_cw(self, vals):
        journal_obj = self.env['account.journal']
        type_journal = 'sale' if vals['move_type'] in ('out_invoice', 'out_refund') else 'purchase'
        journal_id = journal_obj.search([
            ('type', '=', type_journal),
            ('is_default_cw', '=', True),
        ], limit=1)
        if not journal_id:
            journal_id = journal_obj.search([('type', '=', type_journal)], limit=1)
        if journal_id and not vals.get('journal_id'):
            vals['journal_id'] = journal_id.id
        return vals

    # ---- Envío de estados hacia CargoWise ----

    def get_xml_request_cw(self, values=None, code_cw=False):
        self.ensure_one()
        values = values or []
        company_id = self.company_id
        template = self.env.ref('account_cargowise_sync.cw_template_xml', raise_if_not_found=False)
        if not template:
            return b''
        request = template._render({
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
        company_id = self.company_id
        request = self.get_xml_request_cw(values=values)
        request_bytes = request if isinstance(request, bytes) else request.encode('utf-8')
        try:
            auth = self.company_id._get_authorization_cw_api()
            url = self.company_id.api_cw_url
            header = {
                'Authorization': 'Basic %s' % auth
            }
            response = post(url=url, headers=header, data=request_bytes)
            state = 'done' if response.status_code == 200 else 'error'
            log_vals = {
                'name': 'Sync CW %s' % self.name,
                'move_id': self.id,
                'request': b64encode(request_bytes),
                'request_fname': 'request.xml',
                'response': b64encode(response.content),
                'response_fname': 'response.xml',
                'response_txt': response.text,
                'type_doc': type_doc,
                'state': state,
                'code_cw': self.code_cw,
            }
            if ref_id:
                log_vals['ref_inv_cw_id'] = ref_id
            self.env['invoice.cw.log'].sudo().create(log_vals)
        except Exception as e:
            _logger.error('Error enviando estado a CW: %s', str(e))

    def send_posted_invoice_to_cw(self, ref_id=False):
        for record in self:
            if not record.code_cw and not record.ref_inv_cw_ids:
                continue
            codes = record.ref_inv_cw_ids.mapped('code_cw') or (
                [record.code_cw] if record.code_cw else [])
            for code in codes:
                record.send_status_to_cw(
                    values=[{'key': 'ESTADO', 'value': 'FACTURADO'}],
                    type_doc='invoiced',
                    ref_id=ref_id,
                )

    def send_posted_paid_to_cw(self, ref_id=False):
        for record in self:
            if not record.code_cw and not record.ref_inv_cw_ids:
                continue
            record.send_status_to_cw(
                values=[{'key': 'ESTADO', 'value': 'PAGADO'}],
                type_doc='paid',
                ref_id=ref_id,
            )

    def send_posted_cancelled_to_cw(self, ref_id=False):
        for record in self:
            if not record.code_cw and not record.ref_inv_cw_ids:
                continue
            record.send_status_to_cw(
                values=[{'key': 'ESTADO', 'value': 'CANCELADO'}],
                type_doc='cancelled',
                ref_id=ref_id,
            )

    def resend_status_invoice_to_cw(self, num_docs=5):
        """Tarea programada: reenviar estados pendientes."""
        logs = self.env['invoice.cw.log'].search(
            [('state', '=', 'error')], limit=num_docs)
        for log in logs:
            if log.move_id:
                log.move_id.send_posted_invoice_to_cw(ref_id=log.ref_inv_cw_id.id)

    def action_merge_invoice_cw(self):
        """Acción servidor: fusionar en un solo documento varias facturas
        enviadas desde CargoWise, para gestionarlas desde Odoo.

        Las facturas originales quedan canceladas y se conservan como
        referencia en la pestaña CW Log del documento resultante.
        """
        if len(self) < 2:
            raise ValidationError(_(
                'Debe seleccionar al menos dos facturas para fusionar.'))

        self._validate_merge_invoice_cw()

        lines = []
        ref_data = []
        for record in self:
            # Líneas (en Odoo 19 las líneas de producto usan display_type='product')
            for line in record.invoice_line_ids.filtered(
                    lambda l: l.display_type == 'product'):
                lines.append((0, 0, {
                    'product_id': line.product_id.id,
                    'name': line.name,
                    'quantity': line.quantity,
                    'price_unit': line.price_unit,
                    'discount': line.discount,
                    'tax_ids': [(6, 0, line.tax_ids.ids)],
                    'analytic_distribution': line.analytic_distribution,
                    'product_uom_id': line.product_uom_id.id or False,
                }))
            # Referencia de las facturas originales
            ref_data.append((0, 0, {
                'code_cw': record.code_cw,
                'city': record.city,
                'customer_order': record.customer_order,
                'hbl': record.hbl,
                'motor_ship': record.motor_ship,
                'position': record.position,
                'destination': record.destination,
                'text_weight': record.text_weight,
                'volume': record.volume,
                'salesman_cw_id': record.salesman_cw_id.id or False,
            }))

        # Nueva factura
        inv_data = {
            'company_id': self[0].company_id.id,
            'partner_id': self[0].partner_id.id,
            'move_type': self[0].move_type,
            'journal_id': self[0].journal_id.id,
            'currency_id': self[0].currency_id.id,
            'invoice_date': max(dates) if (dates := self.mapped('invoice_date')) else False,
            'invoice_payment_term_id': self[0].invoice_payment_term_id.id or False,
            'current_exchange_rate': self[0].current_exchange_rate,
            'invoice_line_ids': lines,
            'ref_inv_cw_ids': ref_data,
            'invoice_merge': True,
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
            'service_level': self._join_field_values('service_level'),
            'origin': self._join_field_values('origin'),
            'destination': self._join_field_values('destination'),
            'customer_order': self._join_field_values('customer_order'),
            'text_weight': self._join_field_values('text_weight'),
        }
        invoice_id = self.env['account.move'].create(inv_data)
        _logger.info('Odoo-CW INV MERGE: %s <- %s', invoice_id.id, self.ids)

        # Cancelar las facturas originales
        self.button_cancel()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Fusión de facturas (*%s)') % invoice_id.id,
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice_id.id,
            'target': 'current',
        }

    def _validate_merge_invoice_cw(self):
        """Valida que las facturas seleccionadas se puedan fusionar."""
        inv_not_draft = self.filtered(lambda i: i.state != 'draft')
        if inv_not_draft:
            raise ValidationError(_(
                'Solo se permite fusionar facturas en estado borrador.\n\n%s'
            ) % '\n'.join([
                _('Factura Id: %s / Código CW: %s está en estado %s') % (
                    rec.id, rec.code_cw or 'N/A', rec.state)
                for rec in inv_not_draft
            ]))

        inv_not_cw = self.filtered(lambda i: not i.code_cw)
        if inv_not_cw:
            raise ValidationError(_(
                'Solo se permite fusionar facturas enviadas desde '
                'CargoWise.\n\n%s'
            ) % '\n'.join([
                _('Factura Id: %s no es una factura enviada desde CargoWise.')
                % rec.id for rec in inv_not_cw
            ]))

        if len(self.company_id) > 1:
            raise ValidationError(_(
                'Solo se permite fusionar facturas de la misma compañía.'))

        if len(self.partner_id) > 1:
            raise ValidationError(_(
                'Solo se permite fusionar facturas del mismo %s.'
            ) % (self[0].move_type in ('out_invoice', 'out_refund')
                 and _('cliente') or _('proveedor')))

        if len(set(self.mapped('move_type'))) > 1:
            raise ValidationError(_(
                'Solo se permite fusionar facturas del mismo tipo de '
                'documento.'))

        if len(self.currency_id) > 1:
            raise ValidationError(_(
                'Solo se permite fusionar facturas con la misma moneda.'))

        if len(self.journal_id) > 1:
            raise ValidationError(_(
                'Solo se permite fusionar facturas del mismo diario.'))

    def _join_field_values(self, field):
        """Concatena, sin repetir, los valores del campo en el conjunto."""
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
        """Igual que _join_field_values pero formateando fechas."""
        values = []
        seen = set()
        for record in self:
            value = getattr(record, field)
            if value and value.strftime(date_format) not in seen:
                seen.add(value.strftime(date_format))
                values.append(value.strftime(date_format))
        return ' / '.join(values)
