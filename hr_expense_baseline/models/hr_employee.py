# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
# TODO: OK

from odoo import fields, models, api


class Employee(models.Model):
    _inherit = 'hr.employee'

    approvers_ids = fields.Many2many(
        comodel_name='res.users',
        string='Advance Approvers',
        help='Users who can approve the advances for this employee.'
    )

    def _get_expense_partner(self):
        """Contacto del empleado para los asientos de gastos.
        Con hr_payroll_co el contacto vive en address_home_id (= partner_id), como en v18;
        en el estándar de v19 está en work_contact_id."""
        partner = self.env['res.partner']
        for employee in self[:1].sudo():
            if 'address_home_id' in employee._fields:
                partner = employee.address_home_id
            partner = partner or employee.work_contact_id
        return self.env['res.partner'].browse(partner.id)
