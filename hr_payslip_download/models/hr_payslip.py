from odoo import models
import base64
import io
import zipfile
from odoo.exceptions import UserError

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def action_download_payslips(self):

        report_action = self.env.ref('hr_payroll_co.payslip_action_report')
        report = self.env['ir.actions.report'].browse(report_action.id)

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for payslip in self:
                pdf_content, _ = report._render_qweb_pdf('hr_payroll_co.payroll_template_report', payslip.id)
                filename = f"{payslip.employee_id.name}.pdf"
                zip_file.writestr(filename, pdf_content)


        zip_buffer.seek(0)
        zip_data = zip_buffer.read()
        zip_attachment = self.env['ir.attachment'].create({
            'name': 'Nominas.zip',
            'type': 'binary',
            'datas': base64.b64encode(zip_data),
            'store_fname': 'Nominas.zip',
            'mimetype': 'application/zip',
            'res_model': 'hr.payslip',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{zip_attachment.id}?download=true',
            'target': 'self',
        }
