# -*- coding: utf-8 -*-
from odoo import api, fields, models

VENDOR_MOVE_TYPES = ('in_invoice', 'in_refund', 'in_receipt')


class VendorStatementReport(models.AbstractModel):
    _name = 'report.website_baseline.vendor_statement'
    _description = 'Estado de cuenta del proveedor (portal)'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        partner = self.env['res.partner'].sudo().browse(docids[:1])
        company = self.env['res.company'].sudo().browse(
            data.get('company_id') or self.env.company.id)
        domain = [
            ('company_id', '=', company.id),
            ('commercial_partner_id', '=', partner.id),
            ('move_type', 'in', VENDOR_MOVE_TYPES),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', data.get('date_from')),
            ('invoice_date', '<=', data.get('date_to')),
        ]
        if data.get('only_pending'):
            domain.append(('amount_residual', '>', 0))
        moves = self.env['account.move'].sudo().search(domain, order='invoice_date, name')

        def sign(move):
            return -1 if move.move_type == 'in_refund' else 1

        return {
            'doc_ids': docids,
            'doc_model': 'res.partner',
            'docs': partner,
            'partner': partner,
            'company': company,
            'moves': moves,
            'sign': sign,
            # Totales en la moneda de la compañía; cada fila se muestra en la moneda de la factura.
            'total_amount': sum(sign(m) * abs(m.amount_total_signed) for m in moves),
            'total_residual': sum(sign(m) * abs(m.amount_residual_signed) for m in moves),
            'date_from': fields.Date.to_date(data.get('date_from')),
            'date_to': fields.Date.to_date(data.get('date_to')),
            'generated_at': fields.Datetime.now(),
        }
