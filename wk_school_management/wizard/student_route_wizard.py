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

import logging
_logger = logging.getLogger(__name__)

class StudentRouteWizard(models.TransientModel):
    _name = 'student.route.wizard'
    _description = 'Add Student to Transport Route Wizard'

    student_ids = fields.Many2many('student.student', string='Students', help="Select students to add to the transport route")
    route_id = fields.Many2one('transport.route', string='Transport Route', help="Select the transport route to which students will be added")
    route_stop_ids = fields.Many2many('transport.route.stop', string='Route Stops', help="Select stops for the transport route")
    location_id = fields.Many2one('transport.location', string='Location', help='select location for the student')
    available_routes = fields.Many2many('transport.route', string='Available Transport Route')

    def action_assign_route(self):
        if not self.student_ids or not self.route_id:
            raise UserError(_("Please select at least one student and a transport route."))
        
        if self.route_id.remaining_capacity < len(self.student_ids):
            raise UserError(_("The number of selected students exceeds the available capacity of the route. Please reduce the number of students."))
        
        for student in self.student_ids:
            student.write({'route_id': self.route_id.id})
        
        return {'type': 'ir.actions.act_window_close'}
    
    @api.onchange('location_id')
    def _onchange_location_id(self):
        if not self.location_id:
            self.route_stop_ids = False
            self.available_routes = False
        else:
            loaction = self.location_id
            company = self.env.context.get('student_company')
            location_stops = self.env['transport.route.stop'].search([('company_id', '=', company),('location_id', '=', loaction.id)])
            self.route_stop_ids = location_stops.ids
            self.available_routes = location_stops.mapped('route_id.id')
            
    def action_enable_transport(self):
        students = self.env['student.student'].browse(self.env.context.get('active_ids'))       
        if not students:
            raise UserError(_("No student found to assign the route."))
        else:
            for student in students:
                if student.route_id:
                    student.route_id = False
                    
                if self.route_id.remaining_capacity > 0:
                    student.write({'route_id': self.route_id.id,
                                'location_id': self.location_id.id,
                                'is_transport_enabled': True,
                                })
                else:
                    raise UserError(_("No room left in this Route please choose another Route"))
        
        return {'type': 'ir.actions.act_window_close'}
    
    def action_enable_transport_bulk(self):
        
        students = self.env['student.student'].browse(self.env.context.get('active_ids'))
        
        if not students:
            raise UserError(_("No student found to assign the route."))
        elif self.route_id.remaining_capacity < len(students):
            raise UserError(_("The number of selected students exceeds the available capacity for the chosen route. Please select a different route or reduce the number of students."))
        else:
            for student in students:
                student.write({'route_id': self.route_id.id,
                                'location_id': self.location_id.id,
                                'is_transport_enabled': True,
                                })
    
        message = _(
            "Transportation services for students have been successfully activated."
        )
        return {
            'type': 'ir.actions.act_window',
            'name': 'Transport Activated',
            'res_model': 'wk.message.wizard',
            'views': [(self.env.ref('wk_school_management.wk_message_wizard_view_form_success').id, 'form')],
            'target': 'new',
            'context': {
                'default_message': message
            }
        }