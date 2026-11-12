# -*- coding: utf-8 -*-
from datetime import date, datetime

from odoo import http, _
from odoo.http import request

CERTIFICATE_REPORT = 'tax_certificate_management.tax_certificate_management_tmpl_action'


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return False


class PortalCertificates(http.Controller):
    """El proveedor solicita y descarga sus certificados de retenciones.

    Todo se lee y se genera con sudo, pero siempre sobre el contacto comercial del
    usuario que inició sesión: nunca se acepta un contacto desde el formulario.
    """

    def _get_form_values(self, year=None, **extra):
        env = request.env
        companies = env.user.sudo().company_ids
        types = env['withholding.certificate.type'].sudo().search([])
        Period = env['certificate.period'].sudo()
        all_periods = Period.search([], order='date_from desc')
        years = sorted(
            {p.date_from.year for p in all_periods if p.date_from}
            | {p.date_to.year for p in all_periods if p.date_to},
            reverse=True,
        )
        selected_year = _to_int(year)
        if selected_year not in years:
            selected_year = years[0] if years else None
        if selected_year:
            periods = Period.search([
                ('date_from', '>=', date(selected_year, 1, 1)),
                ('date_to', '<=', date(selected_year, 12, 31)),
            ], order='date_from desc')
        else:
            periods = all_periods
        values = {
            'companies': companies,
            'types': types,
            'periods': periods,
            'years': years,
            'selected_year': selected_year,
            'page_name': 'certificates',
        }
        values.update(extra)
        return values

    @http.route(['/my/certificates'], type='http', auth='user', website=True)
    def certificates_form(self, year=None, **kw):
        return request.render(
            'website_baseline.portal_certificates_form', self._get_form_values(year=year))

    @http.route(['/my/certificates/submit'], type='http', auth='user', methods=['POST'],
                website=True, csrf=True)
    def certificates_submit(self, **post):
        env = request.env
        partner = env.user.partner_id.commercial_partner_id
        year = post.get('year')

        def form_error(message):
            return request.render(
                'website_baseline.portal_certificates_form',
                self._get_form_values(year=year, error=message))

        company = env['res.company'].sudo().browse(_to_int(post.get('company_id')))
        if not company.exists() or company not in env.user.sudo().company_ids:
            return form_error(_('Seleccione una compañía válida.'))
        certificate_type = env['withholding.certificate.type'].sudo().browse(
            _to_int(post.get('certificate_id')))
        period = env['certificate.period'].sudo().browse(
            _to_int(post.get('certificate_period_id')))
        if not certificate_type.exists():
            return form_error(_('Seleccione el tipo de certificado.'))
        if not period.exists():
            return form_error(_('Seleccione el período del certificado.'))

        wizard = env['withholding.certificates.wizard'].sudo().create({
            'company_id': company.id,
            'certificate_id': certificate_type.id,
            'certificate_period_id': period.id,
            'partner_ids': [(6, 0, [partner.id])],
        })
        result = wizard.create_certificates()
        if result.get('res_model') != 'withholding.certificate.report':
            # El asistente pide confirmación: el proveedor no tiene retenciones en el período.
            return form_error(_(
                'No hay retenciones registradas a su nombre para el período seleccionado.'))
        certificate = env['withholding.certificate.report'].sudo().browse(
            result['domain'][0][2][:1])

        report = env.ref(CERTIFICATE_REPORT).sudo()
        pdf, _content_type = report._render_qweb_pdf(report.report_name, certificate.ids)
        filename = 'certificado_%s_%s.pdf' % (partner.id, datetime.now().strftime('%Y%m%d_%H%M%S'))
        return request.make_response(pdf, headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(pdf)),
            ('Content-Disposition', 'attachment; filename="%s"' % filename),
        ])
