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
import pytz
import logging

_logger = logging.getLogger(__name__)

class TransportTrip(models.Model):
    
    _name = 'transport.trip'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'wk.company.visibility.mixin']
    _description = 'Transport Trip'
    
    name = fields.Char(string='Trip Name', help="Name of the transport trip", copy=False, default=lambda self: _('New'), readonly=True)
    route_id = fields.Many2one('transport.route', string='Route', required=True)
    state = fields.Selection([('new', 'New'),
                              ('progress', 'In-Progress'),
                              ('completed', 'Completed'), 
                              ('cancelled', 'Cancelled')], string='Trip Status', default='new', help="Current status of the trip", tracking=True)
    trip_date = fields.Date(string='Trip Date', help="Date of the trip")
    trip_line_ids = fields.One2many('transport.trip.line', 'trip_id', string='Trip Lines', help="Lines associated with this trip")
    total_students = fields.Integer(string='Total Students', compute='_compute_total_students', help="Total number of students assigned to this trip", store=True)
    total_pickup_present = fields.Integer(string='Pickup (Present)', compute='_compute_total_present', help="Total number of students present for pickup", store=True)
    total_pickup_absent = fields.Integer(string='Pickup (Absent)', compute='_compute_total_absent', help="Total number of students absent for pickup", store=True)
    total_dropoff_present = fields.Integer(string='Dropoff (Present)', compute='_compute_total_present', help="Total number of students present for dropoff", store=True)
    total_dropoff_absent = fields.Integer(string='Dropoff (Absent)', compute='_compute_total_absent', help="Total number of students absent for dropoff", store=True)
    company_id = fields.Many2one('res.company', string='School', related='route_id.company_id', help="School associated with this transport trip")
    remarks = fields.Text(string='Remarks', help="Any remarks related to this trip")
    has_difference = fields.Boolean(string="Had difference in Pickup or Dropoff Attendance", compute="_compute_has_difference")
    
    driver_id = fields.Many2one('res.partner', string='Driver', help="Driver associated with this trip", domain="['|', ('company_id', '=', company_id), ('company_id', '=', False)]")
    driver_phone = fields.Char(related='driver_id.phone', string='Driver Phone', help="Phone number of the driver")
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle', help="Vehicle associated with this transport Trip", domain="[('company_id', '=', company_id)]")
    responsible_id = fields.Many2one('res.users', string='Responsible', help="User responsible for managing this transport trip")
    other_responsible_ids = fields.Many2many('res.users', string='Other Responsible Users', compute="_compute_other_responsible", help="Other users responsible for this transport trip")

    _unique_route_date = models.Constraint(
        'unique(route_id, trip_date)',
        'Only one trip per route is allowed for each date!'
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _("New")) == _("New"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'transport.trip.sequence') or _("New")
        return super().create(vals_list)
    
    @api.constrains('trip_date', 'trip_line_ids')
    def _check_trip_date_and_times(self):
        for trip in self:
            if not trip.trip_date:
                continue
            for line in trip.trip_line_ids:
                if line.pickup_time:
                    pickup_date = fields.Date.to_date(line.pickup_time)
                    if pickup_date != trip.trip_date:
                        raise UserError(
                            _("Pickup date (%s) for student '%s' does not match the trip date (%s).")
                            % (pickup_date, line.student_id.display_name or '', trip.trip_date)
                        )

                if line.dropoff_time:
                    dropoff_date = fields.Date.to_date(line.dropoff_time)
                    if dropoff_date != trip.trip_date:
                        raise UserError(
                            _("Drop-off date (%s) for student '%s' does not match the trip date (%s).")
                            % (dropoff_date, line.student_id.display_name or '', trip.trip_date)
                        )
    
    @api.depends('trip_line_ids')
    def _compute_total_students(self):
        for trip in self:
            trip.total_students = len(trip.trip_line_ids)

    @api.depends('trip_line_ids')
    def _compute_total_present(self):
        for trip in self:
            total_pickup_present = sum(1 for line in trip.trip_line_ids if line.picked_up )
            trip.total_pickup_present = total_pickup_present
            total_dropoff_present = sum(1 for line in trip.trip_line_ids if line.dropped_off)
            trip.total_dropoff_present = total_dropoff_present
    
    @api.depends('trip_line_ids')
    def _compute_total_absent(self):
        for trip in self:
            total_pickup_absent = sum(1 for line in trip.trip_line_ids if not line.picked_up)
            trip.total_pickup_absent = total_pickup_absent
            total_dropoff_absent = sum(1 for line in trip.trip_line_ids if not line.dropped_off)
            trip.total_dropoff_absent = total_dropoff_absent
    
    @api.depends('trip_line_ids')
    def _compute_has_difference(self):
        for trip in self:
          trip.has_difference = any(trip.picked_up != trip.dropped_off for trip in trip.trip_line_ids)
          
    def _compute_other_responsible(self):
        for trip in self:
            trip.other_responsible_ids = trip.route_id.transport_manager_id.ids + trip.route_id.other_responsible_ids.ids
          
    @api.onchange('route_id')
    def _onchange_route_id(self):
        if self.route_id:
            self.driver_id = self.route_id.driver_id
            self.responsible_id = self.route_id.transport_manager_id
            if self.env.uid == self.route_id.transport_manager_id.id or self.env.uid in self.route_id.other_responsible_ids.ids:
                self.responsible_id = self.env.uid
            if self.route_id.transport_manager_id or self.route_id.other_responsible_ids:
                self.other_responsible_ids = self.route_id.transport_manager_id.ids + self.route_id.other_responsible_ids.ids
            else:
                self.other_responsible_ids = False
            # Clear existing trip lines
            self.trip_line_ids = False
            # Create new trip lines based on students in the route
            self.trip_line_ids = [(0, 0, {'student_id': student.id, 'location_id': student.location_id.id}) for student in self.route_id.student_ids]
        
    def action_start_trip(self):
        self.state = 'progress'
    
    def action_trip_done(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Complete Trip',
            'res_model': 'transport.trip',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'view_id': self.env.ref('wk_school_management.view_transport_trip_pickup').id,
            }
    
    def action_cancel_trip(self):
        self.state = 'cancelled'
    
    def action_complete_trip(self):
        self.state = 'completed'
    
    def action_trip_new(self):
        self.state = 'new'
        

class TransportTripLine(models.Model):
    
    _name = 'transport.trip.line'
    _inherit = 'wk.company.visibility.mixin'
    _description = 'Transport Trip Line'
    
    trip_id = fields.Many2one('transport.trip', string='Trip', ondelete='cascade')
    location_id = fields.Many2one('transport.location', string='Location', help="Location associated with this trip line")
    student_id = fields.Many2one('student.student', string='Student', help="Student assigned to this trip")
    stop_id = fields.Many2one('transport.route.stop', string='Stop', help="Stop associated with this trip line")
    pickup_time = fields.Datetime(string='Pickup Time', help="Time at which the student is picked up")
    picked_up = fields.Boolean(string='Picked Up', default=False, help="Indicates if the student has been picked up")
    dropoff_time = fields.Datetime(string='Dropoff Time', help="Time at which the student is dropped off")
    dropped_off = fields.Boolean(string='Dropped Off', default=False, help="Indicates if the student has been dropped off")
    company_id = fields.Many2one(string='School', related='trip_id.company_id')
    
    @api.onchange('picked_up')
    def _onchange_picked_up(self):
        self.ensure_one()
        if self.picked_up:
            self.pickup_time = fields.Datetime.now()
        else:
            self.pickup_time = False
            
    @api.onchange('dropped_off')
    def _onchange_dropped_off(self):
        self.ensure_one()
        if self.dropped_off:
            self.dropoff_time = fields.Datetime.now()
        else:
            self.dropoff_time = False
            
    def convert_to_user_timezone(self, utc_naive_datetime):
        tz_from = pytz.utc
        tz_to  = pytz.timezone(self.env.user.tz) if self.env.user.tz else pytz.utc
        aware_datetime_to = tz_from.localize(utc_naive_datetime)
        utc_naive_datetime_to = aware_datetime_to.astimezone(tz_to).replace(tzinfo=None)
        return utc_naive_datetime_to
