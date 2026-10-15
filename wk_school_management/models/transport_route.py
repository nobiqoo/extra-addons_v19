# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.date_utils import float_to_time
import logging

_logger = logging.getLogger(__name__)


class TransportRoute(models.Model):
    
    _name = 'transport.route'
    _inherit = 'wk.company.visibility.mixin'
    _description = 'Transport Route'
    
    name = fields.Char(string='Route Name', required=True, help="Name of the transport route")
    
    transport_manager_id = fields.Many2one('res.users', required=True, string='Transport Manager', domain=lambda self: [('group_ids', 'in', self.env.ref('wk_school_management.wk_school_management_staff_group').id)], help="User responsible for managing this transport route")
    other_responsible_ids = fields.Many2many('res.users', string='Other Responsible Users', domain=lambda self: [('group_ids', 'in', self.env.ref('wk_school_management.wk_school_management_staff_group').id)], help="Other users responsible for this transport route")
    
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle', help="Vehicle associated with this transport route", domain="[('company_id', '=', company_id)]")
    driver_id = fields.Many2one('res.partner', string='Driver', related="vehicle_id.driver_id", domain="['|', ('company_id', '=', company_id), ('company_id', '=', False)]", help="Driver associated with the vehicle of this transport route")
    driver_phone = fields.Char(string='Driver Phone', help="Contact number of the driver", related="driver_id.phone")
    
    student_ids = fields.One2many('student.student', 'route_id', string='Students', help="Students assigned to this transport route")
    trip_ids = fields.One2many('transport.trip', 'route_id', string='Trips', help="Trips associated with this transport route")
    trip_count = fields.Integer(string='Trip Count', compute='_compute_trip_count', help="Number of trips associated with this transport route")
    route_stop_ids = fields.One2many('transport.route.stop', 'route_id', string='Route Stops', help="Stops associated with this transport route")
    state = fields.Selection([('draft', 'Draft'),
                              ('active', 'Active'),
                              ('inactive', 'Inactive')], string='Status', default='draft', help="Current status of the transport route")
    company_id = fields.Many2one('res.company', string='School', default=lambda self: self.env.company, help="School associated with this transport route")
    student_capacity = fields.Integer(string='Student Capacity', help="Maximum number of students that can be accommodated in this transport route")
    enrolled_students = fields.Integer(string='Enrolled Students', compute='_compute_enrolled_students', help="Number of students currently enrolled in this transport route")
    remaining_capacity = fields.Integer(string='Remaining Capacity', compute='_compute_remaining_capacity', help="Remaining capacity for students in this transport route")
    has_running_trip = fields.Boolean(string='Has Running Trip', compute='_compute_has_running_trip', help="Indicates if there is an ongoing trip for this route")
    
    def _compute_trip_count(self):
        for route in self:
            route.trip_count = len(route.trip_ids)
    
    def _compute_enrolled_students(self):
        for route in self:
            route.enrolled_students = len(route.student_ids)
    
    def _compute_remaining_capacity(self):
        for route in self:
            route.remaining_capacity = route.student_capacity - route.enrolled_students if route.student_capacity else 0

    def action_confirm(self):
        for route in self:
            if route.state != 'draft':
                raise UserError(_("Only routes in draft state can be confirmed."))
            route.state = 'active'
            
    def _compute_has_running_trip(self):
        for route in self:
            route.has_running_trip = any(trip.state == 'new' or trip.state == 'progress' for trip in route.trip_ids)
    
    @api.constrains('transport_manager_id', 'other_responsible_ids')
    def _check_unique_teacher_transport_manager(self):
        for rec in self:
            if rec.transport_manager_id in rec.other_responsible_ids:
                raise ValidationError(
                    _("A Staff assigned as transport manager cannot be assigned as Other responsible in same route.")
                )
            transport_manager_id = rec.transport_manager_id.id
            if not transport_manager_id:
                continue
            domain = [
                ('transport_manager_id', '=', transport_manager_id),
                ('id', '!=', rec.id)
            ]
            conflict = self.search(domain, limit=1)
            if conflict:
                raise ValidationError(
                    _("A Staff assigned as transport manager cannot be assigned to another route as transport manager.")
                )
    
    @api.constrains('vehicle_id')
    def _check_unique_vehicle(self):
        for rec in self:
            if rec.vehicle_id:
                domain = [
                    ('vehicle_id', '=', rec.vehicle_id.id),
                    ('id', '!=', rec.id)
                ]
                conflict = self.search(domain, limit=1)
                if conflict:
                    raise ValidationError(
                        _("The vehicle is already assigned to another route.")
                    )
    
    @api.onchange('student_capacity')
    def _onchange_student_capacity(self):
        for route in self:
            if route.student_capacity < 0:
                raise UserError(_("Student capacity cannot be negative. Please enter a valid capacity."))
            if route.enrolled_students > route.student_capacity:
                raise UserError(_("Enrolled students exceed the student capacity. Please adjust the capacity or remove some students."))
            
    def action_cancel(self):
        for route in self:
            route.state = 'inactive'
    
    def action_draft(self):
        for route in self:
            if route.state != 'inactive':
                raise UserError(_("Only routes in inactive state can be set to draft."))
            route.state = 'draft'
             
    def add_student(self):
        for route in self:
            _logger.info("Adding student to route: %s", route.name)
            # Collect all location_ids from route_stop_ids
            location_ids = route.route_stop_ids.mapped('location_id.id')
            return {
                'type': 'ir.actions.act_window',
                'name': 'Add Student',
                'res_model': 'student.route.wizard',
                'view_mode': 'form',
                'target': 'new',
                'view_id': self.env.ref('wk_school_management.student_route_wizard_view_form').id,
                'context': {
                    'default_route_id': route.id,
                    'location_ids': location_ids,
                }
            }
            
    def get_enrolled_students(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Enrolled Students',
            'res_model': 'student.student',
            'domain': [('route_id', '=', self.id)],
            'views': [(self.env.ref('wk_school_management.student_student_tree').id, 'list'), (False, 'form')],
        }
    
    def action_view_trips(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Trips',
            'res_model': 'transport.trip',
            'view_mode': 'list,form,pivot,graph,calendar',
            'domain': [('route_id', '=', self.id)],
            'views': [
                (self.env.ref('wk_school_management.view_transport_trip_tree').id, 'list'), 
                (self.env.ref('wk_school_management.view_transport_trip_form').id, 'form'),
                (self.env.ref('wk_school_management.view_transport_trip_calendar').id, 'calendar'),
                (self.env.ref('wk_school_management.view_transport_trip_graph').id, 'graph'),
                (self.env.ref('wk_school_management.view_transport_trip_pivot').id, 'pivot'),
                ],
        }
        
    def action_start_trip(self):
        self.ensure_one()
        if self.state != 'active':
            raise UserError(_("Only active routes can start trips."))
        
        if not self.student_ids:
            raise UserError(_("No students are enrolled in this route. Please add students before starting a trip."))
        
        if self.has_running_trip:
            trip = self.trip_ids.filtered(lambda t: t.state == 'new' or t.state == 'picked')
            if trip:
                if len(trip) > 1:
                    return {
                        'type': 'ir.actions.act_window',
                        'name': 'Running Trips',
                        'res_model': 'transport.trip',
                        'domain': [('id', 'in', trip.ids)],
                        'views': [(self.env.ref('wk_school_management.view_transport_trip_tree').id, 'list'), (self.env.ref('wk_school_management.view_transport_trip_form').id, 'form')],
                    }
                else:
                    return {
                        'type': 'ir.actions.act_window',
                        'name': 'Running Trip',
                        'res_model': 'transport.trip',
                        'res_id': trip.id,
                        'views': [(self.env.ref('wk_school_management.view_transport_trip_form').id, 'form')],
                    }
        
        context = {
            'default_route_id': self.id,
            'default_state': 'new',
            'default_trip_date': fields.Date.today(),
            'default_driver_id': self.driver_id.id,
            'default_responsible_id': self.transport_manager_id.id,
            'default_vehicle_id': self.vehicle_id.id,
            'default_trip_line_ids': [(0, 0, {'student_id':student.id,'location_id': student.location_id.id}) for student in self.student_ids],
        }
        
        if self.env.uid == self.transport_manager_id.id or self.env.uid in self.other_responsible_ids.ids:
            context['default_responsible_id'] = self.env.uid
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'New Trip',
            'res_model': 'transport.trip',
            'view_mode': 'form',
            'views': [(self.env.ref('wk_school_management.view_transport_trip_form').id, 'form')],
            'target': 'current',
            'context': context,
        }
    
    def action_stop_trip(self):
        if self.has_running_trip:
            trip = self.trip_ids.filtered(lambda t: t.state == 'new' or t.state == 'progress')
            if trip:
                if len(trip) > 1:
                    return {
                        'type': 'ir.actions.act_window',
                        'name': 'Running Trips',
                        'res_model': 'transport.trip',
                        'domain': [('id', 'in', trip.ids)],
                        'views': [(self.env.ref('wk_school_management.view_transport_trip_tree').id, 'list'), (self.env.ref('wk_school_management.view_transport_trip_form').id, 'form')],
                    }
                else:
                    return {
                        'type': 'ir.actions.act_window',
                        'name': 'Running Trip',
                        'res_model': 'transport.trip',
                        'res_id': trip.id,
                        'views': [(self.env.ref('wk_school_management.view_transport_trip_form').id, 'form')],
                    }
        else:
            raise UserError(_("No running trip found for this route."))


class TransportRouteStop(models.Model):
    
    _name = 'transport.route.stop'
    _inherit = 'wk.company.visibility.mixin'
    _description = 'Transport Route Stop'
    
    route_id = fields.Many2one('transport.route', string='Route', help="Transport route associated with this stop", ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10, help="Sequence order of the stop in the route")
    location_id = fields.Many2one('transport.location', string='Location', help="Location of the transport stop")
    pickup_time = fields.Float(string='Pickup Time', 
                               help="Time at which the stop is scheduled for pickup.\n"
                               "24-hour time format is supported (HH:MM). Please set the time accordingly.")
    dropoff_time = fields.Float(string='Dropoff Time', 
                                help="Time at which the stop is scheduled for dropoff.\n"
                                "24-hour time format is supported (HH:MM). Please set the time accordingly.")
    
    student_capacity = fields.Integer(string='Student Capacity', related='route_id.student_capacity')
    enrolled_students = fields.Integer(string='Enrolled Students', related='route_id.enrolled_students')
    remaining_capacity = fields.Integer(string='Remaining Capacity', related='route_id.remaining_capacity')
    company_id = fields.Many2one(string='School', related='route_id.company_id')

    @api.constrains('route_id', 'location_id')
    def _constrains_route_id(self):
        for rec in self:
            record = self.search([
                ('route_id', '=', rec.route_id.id),
                ('location_id', '=', rec.location_id.id),
                ('id', '!=', rec.id)
            ], limit=1)
            if record:
                raise UserError(_("This location is already assigned to the route, Please choose another location."))
    
    @api.onchange('pickup_time', 'dropoff_time')
    def _onchange_pickup_time(self):
        for rec in self:
            if rec.pickup_time > 24.00 or rec.dropoff_time > 24.00:
                raise UserError(_("Pickup Time or Drop time should Less then 24:00"))
            elif rec.dropoff_time and rec.pickup_time > rec.dropoff_time:
                raise UserError(_("Pickup time should before the drop time"))
            
    def float_to_time_format(self, time):
        return float_to_time(time).strftime("%I:%M %p")
