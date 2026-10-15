# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError

SIGNUP_FIELD_TYPES = [
    'char',
    'integer',
    'float',
    'boolean',
    'text',
    'selection',
    'many2one',
    'many2many',
    'binary',
    'date'
]
IMP_FIELDS = [
    'student_name',
    'email',
    'company_id',
    'gender',
    'grade_id',
    'phone',
    'student_image',
    'id',
]

FIELDS_INPUT_TYPE = [
    ('char', 'text'),
    ('integer', 'number'),
    ('float', 'float'),
    ('boolean', 'checkbox'),
    ('text', 'textarea'),
    ('selection', 'selection'),
    ('many2one', 'selection_m2o'),
    ('many2many', 'selection_m2m'),
    ('binary','binary'),
    ('date','date')
]


class ApplicationPortalSettings(models.Model):
    _name = "application.portal.settings"
    _order = "active desc"
    _description = "Application Portal Settings"

    def _default_website(self):
        return self.env['website'].search([
            ('company_id', '=', self.env.user.company_id.id)], limit=1)

    name= fields.Char("Name", required=True, translate=True)
    active = fields.Boolean('Active', default=False, copy=False)
    website_id = fields.Many2one('website', string= "Website",default= _default_website,
        ondelete= 'cascade', required= True)
    portal_field_ids = fields.One2many("application.portal.fields",
        "application_setting_id", "Application Fields")
    required_document_ids = fields.Many2many('wk.student.document.type',
        string='Required Documents')

    @api.constrains('portal_field_ids', 'required_document_ids')
    def _check_signup_field_ids(self):
        for record in self:
            if not record.portal_field_ids and not record.required_document_ids:
                raise UserError(_('At least one application field or required document must be added.'))

    def toggle_active(self):
        active_website_setting = self.search(
            [('active', '=', True),('website_id', 'in', [self.website_id.id])], limit=1)
        if active_website_setting and not self.active:
            active_website_setting.active = False
            self.active = True
        else:
            self.active = not self.active
        return


class ApplicationPortalSettings(models.Model):
    _name = "application.portal.fields"
    _description = "Application Portal Fields"

    field = fields.Many2one("ir.model.fields", "Application Field",
        required=True, help="Associated field in the Application form.",
        domain="[('model', 'in', ['wk.application.form']),('ttype', 'in', %s),('name','not in', %s), ('readonly', '=', False)]" % (SIGNUP_FIELD_TYPES, IMP_FIELDS),
        ondelete='cascade')
    field_type = fields.Selection(
            related = "field.ttype",
            store = True,
            readonly = True,
            string = "Field Type",
            help="Associated field type in the Application form.")
    field_domain = fields.Char("Field Domain")
    field_input_type = fields.Char("Input Type", help="Field input type in signup form",
        compute = "_compute_field_input_type", store=True)
    sequence = fields.Integer("Sequence",
        help="Sequence number for this field in application form")
    application_setting_id = fields.Many2one("application.portal.settings", "Application Settings")
    is_required = fields.Boolean("Is required?",
        help="Enable if associated field will be required")
    field_label = fields.Char("Field Label",
        help="Label for this field in application form", translate=True)
    placeholder = fields.Char("Placeholder",
        help="Placeholder value for this field in application form", translate=True)
    help = fields.Text("Help",
        help="Description for this field in application form", translate=True)
    no_of_cols = fields.Selection([('1','1'),('2','2')], "Number of columns",
        help="Number of columns in signup form")
    
    @api.depends("field_type")
    def _compute_field_input_type(self):
        for rec in self:
            field_type = rec.field_type
            if field_type:
                input_type = [item for item in FIELDS_INPUT_TYPE if field_type in item[0]]
                if input_type and input_type[0] and input_type[0][1]:
                    rec.field_input_type = input_type[0][1]

    def get_field_obj_relation(self):
        for rec in self:
            obj_relation = None
            field = rec.field
            if field and rec.field_type in ['many2one', 'many2many']:
                obj_relation = field.relation
        return obj_relation

    def action_add_domain(self):
        obj_relation = self.get_field_obj_relation()
        view_id = self.env["field.add.domain"].create({'related_model1':obj_relation })
        vals = {
            'name' : _("Add Domain"),
            'view_mode' : 'form',
            'res_model' : 'field.add.domain',
            'res_id' : view_id.id,
            'context' : {'default_related_model1': obj_relation},
            'type' : "ir.actions.act_window",
            'target' : 'new',
         }
        return vals
