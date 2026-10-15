# -*- coding: utf-8 -*-
from odoo import models, fields, release
from odoo.http import content_disposition
from odoo.tools import pdf


class HrContractWorkCertificateWizard(models.TransientModel):
    _name = 'hr.contract.work.certificate.wizard'
    _description = 'Wizard Cetificado Laboral'

    certificate_type = fields.Selection(
        selection=[
            ('without_salary', 'Sin Salario'),
            ('with_salary', 'Con Salario'),
            ('with_variable_salary', 'Con Salario Variable'),
        ],
        string='Tipo de Certificado',
        default='without_salary'
    )

    def send_certificate(self):
        mail_template = self.env.ref('hr_payroll_co.payroll_work_certificate_mail_template')
        mail_template.sudo().with_context(
            certificate_type=self.certificate_type).send_mail(self._context.get('active_id'), force_send=True)

    def download_certificate_pdf(self):
        contract = self.env['hr.contract'].browse(self._context.get('active_id'))
        if release.version_info[0] == 15:
            report = self.env.ref(
                'hr_payroll_co.action_payroll_work_certificate_report', False)
            pdf_content, _ = report.sudo().with_context(
                certificate_type=self.certificate_type)._render_qweb_pdf(contract.id)
        else:
            pdf_content, _ = self.env['ir.actions.report'].with_context(
                certificate_type=self.certificate_type)._render_qweb_pdf(
                    'hr_payroll_co.payroll_work_certificate_report', contract.id)

        attachment = self.env['ir.attachment'].create({
            'name': f'certificado_laboral_{contract.employee_id.name}.pdf',
            'raw': pdf_content,
            'res_id': contract.id,
            'res_model': contract._name,
            'type': 'binary',
            'mimetype': 'application/pdf',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }
