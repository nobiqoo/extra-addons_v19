# -*- coding: utf-8 -*-
from datetime import date, timedelta

from odoo import fields, http
from odoo.http import request

STATEMENT_REPORT = 'website_baseline.vendor_statement_action'


class PortalVendorStatement(http.Controller):

    @http.route(['/my/invoices/statement'], type='http', auth='user', website=True)
    def portal_vendor_statement(self, date_from=None, date_to=None, date_begin=None,
                                date_end=None, filterby=None, **kw):
        partner = request.env.user.partner_id.commercial_partner_id
        company = request.env.company

        # La lista de facturas del portal filtra con date_begin / date_end.
        try:
            d_to = fields.Date.to_date(date_to or date_end) if (date_to or date_end) else None
        except ValueError:
            d_to = None
        try:
            d_from = fields.Date.to_date(date_from or date_begin) if (date_from or date_begin) else None
        except ValueError:
            d_from = None
        d_to = d_to or date.today()
        d_from = d_from or d_to - timedelta(days=180)

        report = request.env.ref(STATEMENT_REPORT).sudo()
        pdf, _content_type = report._render_qweb_pdf(
            report.report_name, [partner.id],
            data={
                'date_from': fields.Date.to_string(d_from),
                'date_to': fields.Date.to_string(d_to),
                'company_id': company.id,
                'only_pending': filterby == 'bills',
            })
        filename = 'estado_de_cuenta_%s_%s_%s.pdf' % (partner.id, d_from.isoformat(), d_to.isoformat())
        return request.make_response(pdf, headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Length', str(len(pdf))),
            ('Content-Disposition', 'attachment; filename="%s"' % filename),
        ])
