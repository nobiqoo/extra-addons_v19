# -*- coding: utf-8 -*-
from odoo import models, fields, api, release, _
from odoo.exceptions import UserError, ValidationError

ADDRESS_HOME_ID_HELP = """
Enter here the private address of the employee, not the one linked to your company.
"""


def _get_stock_model():
    version = release.version_info[0]
    return 'res.users' if version == 15 else 'res.partner'


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    partner_id = fields.Many2one(
        comodel_name='res.partner', string='Contacto', required=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")

    name = fields.Char(string="Nombre", related='partner_id.name',
                       store=True, readonly=False, tracking=True)
    user_id = fields.Many2one(
        'res.users', related='', compute="_compute_res_user", store=True, readonly=True)
    active = fields.Boolean(
        'Active', related='partner_id.active', default=True, store=True, readonly=False)
    address_home_id = fields.Many2one(
        'res.partner', 'Address', tracking=True, store=True,
        related="partner_id", help=ADDRESS_HOME_ID_HELP)
    country_partner_id = fields.Many2one(
        'res.country', string="País", related="partner_id.country_id")
    state_partner_id = fields.Many2one(
        'res.country.state', string="Departamento", related="partner_id.state_id")
    city_partner_id = fields.Many2one(
        'res.city', string="Ciudad", related="partner_id.city_id")
    street = fields.Char(related="partner_id.street", readonly=False)
    street2 = fields.Char(related="partner_id.street2", readonly=False)
    phone = fields.Char(related='partner_id.phone',
                        related_sudo=False, string="Private Phone")
    private_email = fields.Char(
        related='partner_id.email', string="Private Email", readonly=False)
    emergency_contact_ids = fields.One2many(
        comodel_name='res.partner', inverse_name='employee2emergency_id', string='Contactos de emergencia')
    bank_account_id = fields.Many2one(
        'res.partner.bank', 'Cuenta Bancaria',
        tracking=True, help='Employee bank salary account')
    # domain="[('partner_id', '=', partner_id), ('company_id', '=', company_id)]",
    identification_id = fields.Char(
        string='Identification No', related='partner_id.vat', tracking=True, readonly=False)
    contract_ids = fields.One2many(
        comodel_name='hr.contract', inverse_name='employee_id', string='Contratos', readonly=True)
    payroll_mail_notifier = fields.Char('Correo notificador de nómina')
    use_partner_like_coach = fields.Boolean(
        related='company_id.use_partner_like_coach',
        readonly=True
    )
    coach_partner_id = fields.Many2one(
        'res.partner',
        string='Tercero Mentor',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help='Seleccione el contacto que actuará como mentor de este empleado.'
    )
    family_information_ids = fields.One2many(
        'hr.family.information', 
        'employee_id', 
        string='Hr Family Information'
    )
    medical_exam_ids = fields.One2many(
        'medical.exam',
        'employee_id', 
        string='Medical Exams'
    )
    personal_reference_ids = fields.One2many(
        'hr.personal.reference', 
        'employee_id', 
        string='Personal References'
    )
    # Campo Obsoleto pero se sebe mantener esta definicion por el related
    user_partner_id = fields.Many2one(
        comodel_name=_get_stock_model(), related='', related_sudo=False, string="User's partner")

    # Campo Obsoleto, se quita restriccion not null
    resource_id = fields.Many2one('resource.resource', required=False)
    resource_calendar_id = fields.Many2one('resource.calendar', required=False)

    family_information_ids = fields.One2many(
        'hr.family.information', 
        'employee_id', 
        string='Hr Información Familiar'
    )
    family_to_certified = fields.Many2one(
        'hr.family.information',
        string='Familar para el certificado',
        compute='_compute_family_to_certified',
        store=True
    )

    _partner_id_uniq = models.Constraint(
        'UNIQUE (partner_id, company_id)',
        'El contacto debe ser único por empleado y compañía',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('partner_id'):
                # Flujos automáticos del core (p. ej. pos_hr llamando a
                # res.users.action_create_employee) crean el empleado sin
                # partner_id: se toma el contacto del usuario.
                if vals.get('user_id'):
                    vals['partner_id'] = self.env['res.users'].browse(
                        vals['user_id']).partner_id.id
                elif vals.get('work_contact_id'):
                    vals['partner_id'] = vals['work_contact_id']
            if not vals.get('partner_id'):
                raise UserError(
                    _('El empleado debe tener contacto relacionado.'))
            partner_id = self.env['res.partner'].browse(vals['partner_id'])
            partner_id.write({'employee': True})
            vals['name'] = partner_id.name
        return super(models.Model, self).create(vals_list)

    @api.depends('partner_id')
    def _compute_res_user(self):
        for record in self:
            if not record.partner_id:
                continue
            self._cr.execute(
                'select id from res_users where partner_id = %s', (record.partner_id.id,))
            res = self._cr.fetchall()
            record.user_id = self.env['res.users'].browse(
                res[0][0]) if len(res) == 1 else False

    @api.depends('family_information_ids')
    def _compute_family_to_certified(self):
        for record in self:
            record.family_to_certified = False
            if record.family_information_ids.filtered(lambda x: x.is_in_certified):
                record.family_to_certified = record.family_information_ids.filtered(lambda x: x.is_in_certified)[0]

    def write(self, vals):
        for record in self:
            if 'partner_id' in vals:
                partner_id = self.env['res.partner'].browse(vals['partner_id'])
                if partner_id:
                    partner_id.write({'employee': True})
                if record.partner_id:
                    record.partner_id.write({'employee': False})
        return super(HrEmployee, self).write(vals)

    # Disable creation of work contact of the employee
    def _inverse_work_contact_details(self):
        pass
