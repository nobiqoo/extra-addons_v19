# -*- coding: utf-8 -*-
import base64
import csv
import io
import re
from collections import defaultdict

from odoo import _, fields, models
from odoo.exceptions import UserError


class SaleCarrierUpdateWizard(models.TransientModel):
    _name = 'sale.carrier.update.wizard'
    _description = "Sales Order Carrier Mass Update"

    file = fields.Binary(string="File", required=True, attachment=False)
    filename = fields.Char(string="File Name")
    state = fields.Selection(
        selection=[('draft', "Draft"), ('done', "Done")],
        default='draft',
    )
    updated_count = fields.Integer(string="Updated Orders", readonly=True)
    unchanged_count = fields.Integer(string="Unchanged Orders", readonly=True)
    rejected_count = fields.Integer(string="Rejected Rows", readonly=True)
    result_log = fields.Text(string="Rejected Rows Detail", readonly=True)

    @staticmethod
    def _normalize_vat(vat):
        return re.sub(r'[^0-9A-Za-z]', '', vat or '').upper()

    @staticmethod
    def _normalize_name(name):
        return ' '.join((name or '').split()).casefold()

    @staticmethod
    def _cell_to_str(value):
        if value is None:
            return ''
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value).strip()

    def _read_rows(self):
        content = base64.b64decode(self.file)
        extension = (self.filename or '').rsplit('.', 1)[-1].lower()
        if extension == 'xlsx':
            import openpyxl
            book = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            raw_rows = [list(row) for row in book.worksheets[0].iter_rows(values_only=True)]
        elif extension == 'csv':
            try:
                text = content.decode('utf-8-sig')
            except UnicodeDecodeError:
                text = content.decode('latin-1')
            try:
                dialect = csv.Sniffer().sniff(text[:2048], delimiters=',;\t')
            except csv.Error:
                dialect = csv.excel
            raw_rows = list(csv.reader(io.StringIO(text), dialect))
        else:
            raise UserError(_("Unsupported file format. Please upload a CSV or XLSX file."))
        rows = []
        # La primera fila es el encabezado
        for row_number, raw_row in enumerate(raw_rows[1:], start=2):
            values = [self._cell_to_str(value) for value in (raw_row + [None] * 4)[:4]]
            if any(values):
                rows.append((row_number, values))
        return rows

    def _find_carrier(self, vat, name, carriers_by_vat, carriers_by_name):
        if vat:
            candidates = carriers_by_vat.get(self._normalize_vat(vat), [])
            if len(candidates) > 1 and name:
                candidates = [partner for partner in candidates if self._normalize_name(partner.name) == self._normalize_name(name)]
            if not candidates:
                return None, _("No carrier found with VAT %s.", vat)
        else:
            candidates = carriers_by_name.get(self._normalize_name(name), [])
            if not candidates:
                return None, _("No carrier found with name %s.", name)
        if len(candidates) > 1:
            return None, _("More than one carrier matches VAT/name.")
        return candidates[0], None

    def action_update(self):
        self.ensure_one()
        rows = self._read_rows()
        if not rows:
            raise UserError(_("The file has no data rows."))

        orders_by_name = defaultdict(lambda: self.env['sale.order'])
        for order in self.env['sale.order'].search([('name', 'in', list({values[0] for _row, values in rows}))]):
            orders_by_name[order.name] |= order
        carriers_by_vat = defaultdict(list)
        carriers_by_name = defaultdict(list)
        for carrier in self.env['res.partner'].search([('is_carrier', '=', True)]):
            carriers_by_vat[self._normalize_vat(carrier.vat)].append(carrier)
            carriers_by_name[self._normalize_name(carrier.name)].append(carrier)

        errors = []
        seen_names = set()
        unchanged = 0
        orders_by_values = defaultdict(lambda: self.env['sale.order'])
        for row_number, (order_name, vat, carrier_name, tracking_number) in rows:
            error = None
            order = self.env['sale.order']
            carrier = None
            if not order_name:
                error = _("Missing order number.")
            elif order_name in seen_names:
                error = _("Order number repeated in the file.")
            elif not (vat or carrier_name or tracking_number):
                error = _("No carrier or tracking number provided.")
            else:
                order = orders_by_name.get(order_name, self.env['sale.order'])
                if not order:
                    error = _("Order not found or not accessible.")
                elif len(order) > 1:
                    error = _("More than one order has this number.")
            seen_names.add(order_name)
            if not error and (vat or carrier_name):
                carrier, error = self._find_carrier(vat, carrier_name, carriers_by_vat, carriers_by_name)
                if not error and carrier.company_id and carrier.company_id != order.company_id:
                    error = _("The carrier belongs to another company.")
            if error:
                errors.append(_("Row %(row)s (%(order)s): %(error)s", row=row_number, order=order_name, error=error))
                continue
            carrier = carrier or order.carrier_partner_id
            tracking_number = tracking_number or order.carrier_tracking_number
            if (order.carrier_partner_id, order.carrier_tracking_number) == (carrier, tracking_number):
                unchanged += 1
                continue
            orders_by_values[(carrier.id, tracking_number)] |= order

        updated_orders = self.env['sale.order']
        for (carrier_id, tracking_number), orders in orders_by_values.items():
            orders.with_context(skip_carrier_propagation=True).write({
                'carrier_partner_id': carrier_id,
                'carrier_tracking_number': tracking_number,
            })
            updated_orders |= orders
        updated_orders._propagate_carrier_to_pickings()

        self.write({
            'state': 'done',
            'updated_count': len(updated_orders),
            'unchanged_count': unchanged,
            'rejected_count': len(errors),
            'result_log': '\n'.join(errors),
        })
        return {
            'name': _("Update Carriers"),
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
