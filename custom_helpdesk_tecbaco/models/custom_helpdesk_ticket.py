# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    
    sub_category_id = fields.Many2one('helpdesk.service.subcategory', string="Nivel 2", compute="_compute_readonly", store=True)
    service_type_id = fields.Many2one('helpdesk.service.type', string="Servicio")
    zone_id = fields.Many2one('helpdesk.zone', string="Zona de servicio")
    support_type_id = fields.Many2one('helpdesk.support.type', string="Tipo de soporte")
    category_id = fields.Many2one('helpdesk.service.category', string="Nivel 1", compute="_compute_readonly", store=True)

    is_service = fields.Boolean(compute="_compute_is_service")
    
    custom_sequence = fields.Char(
        string='Consecutivo',
        readonly=True,
        copy=False,
        index=True,
        help='Consecutivo personalizado basado en el equipo',
        tracking= True
    )
    

    # Compute field for service_type_id domain
    allowed_service_type_ids = fields.Many2many(
        'helpdesk.service.type',
        compute='_compute_allowed_service_types',
        store=False
    ) 

    allowed_category_ids = fields.Many2many(
    'helpdesk.service.category',
    compute='_compute_allowed_categories',
    string='Categorías Permitidas',
    store= False
)

    allowed_subcategory_ids = fields.Many2many(
        'helpdesk.service.subcategory',
        compute='_compute_allowed_subcategories',
        string='Subcategorías Permitidas',
        store = False
    )
    @api.model_create_multi
    def create(self, list_value):
        for vals in list_value:
            zone_rule = False
            if vals.get('partner_id') and vals.get('team_id'):
                zone_rule = self.env['helpdesk.zone.rule'].search([
                    ('partner_ids', 'in', [vals['partner_id']]),
                    ('team_id', '=', vals['team_id'])
                ], limit=1)

                if zone_rule:
                    vals['zone_id'] = zone_rule.zone_id.id
            service_priority = 0
            if vals.get('service_type_id'):
                service_priority = int(
                    self.env['helpdesk.service.type']
                    .browse(vals['service_type_id'])
                    .priority or 0
                )

            rule_priority = 0
            if vals.get('zone_id') and vals.get('partner_id'):
                zone_rule = self.env['helpdesk.zone.rule'].search([
                    ('zone_id', '=', vals['zone_id']),
                    ('partner_ids', 'in', [vals['partner_id']]),
                    ('team_id', '=', vals.get('team_id'))
                ], limit=1)

                rule_priority = int(zone_rule.priority or 0) if zone_rule else 0

            vals['priority'] = str(max(service_priority, rule_priority))

            if vals.get('zone_id') and not vals.get('service_type_id') and zone_rule:
                vals['user_id'] = zone_rule.user_rule_id.id

            elif vals.get('service_type_id'):
                if vals.get('team_id') and not vals.get('user_id'):
                    team = self.env['helpdesk.team'].browse(vals['team_id'])
                    if team.auto_assignment and team.assign_method == 'by_rule':
                        user_id = team._onchange_assignment_rule(
                            priority_ticket=vals.get('priority'),
                            subcategory_ticket=vals.get('sub_category_id'),
                            zone_ticket=vals.get('zone_id'),
                            support_ticket=vals.get('support_type_id'),
                        )
                        if user_id:
                            vals['user_id'] = user_id
                        elif zone_rule and zone_rule.user_rule_id:
                            vals['user_id'] = zone_rule.user_rule_id.id
            if vals.get('team_id') and not vals.get('custom_sequence'):
                team = self.env['helpdesk.team'].browse(vals['team_id'])
                sequence = self._get_or_create_sequence(team)
                vals['custom_sequence'] = sequence.next_by_id()

        return super(HelpdeskTicket, self).create(list_value)
    
    def write(self, vals):
        """Recalculate the sequence if the team changed"""
        if 'team_id' in vals:
            for ticket in self:
                new_team = self.env['helpdesk.team'].browse(vals['team_id'])
                sequence = self._get_or_create_sequence(new_team)
                vals['custom_sequence'] = sequence.next_by_id()
                
        return super(HelpdeskTicket, self).write(vals)
    
    @api.model
    def default_get(self, fields):
        # Call the original method
        result = super(HelpdeskTicket, self).default_get(fields)
        
        zone_id = result.get('zone_id')
        service_type_id = result.get('service_type_id')
        partner_id = result.get('partner_id')

        # If the ticket has zone_id, but not service_type_id, the user will be of the rule by zone
        if zone_id and not service_type_id and partner_id:
            rule = self.env['helpdesk.zone.rule'].search([
                ('zone_id', '=', zone_id),
                ('partner_ids', 'in', [partner_id])
            ], limit=1)

            if rule and rule.user_rule_id:
                result['user_id'] = rule.user_rule_id.id

        # If the ticket has service_type_id, the user will be of the function _onchange_assignment_rule
        elif service_type_id:
            if result.get('team_id') and fields:
                team = self.env['helpdesk.team'].browse(result['team_id'])
                if 'user_id' in fields and result.get('user_id'):
                    # Override the user_id with the custom logic
                    if team.auto_assignment and team.assign_method =='by_rule':
                        result['user_id'] = team._onchange_assignment_rule(
                            priority_ticket = result.get('priority'),
                            subcategory_ticket=result.get('sub_category_id'),
                            zone_ticket=result.get('zone_id'),
                            support_ticket=result.get('support_type_id'),
                        )
        
        return result
    
    @api.depends('service_type_id','sub_category_id','zone_id','support_type_id','team_id')
    def _compute_user_and_stage_ids(self):
        # Call the original method
        super(HelpdeskTicket, self)._compute_user_and_stage_ids()
        
        # Overwrite only with tickets that have a team
        for ticket in self.filtered(lambda t: t.team_id):
            service_priority = 0
            if ticket.service_type_id:
                service_priority = int(
                    self.env['helpdesk.service.type']
                    .browse(ticket.service_type_id.id)
                    .priority or 0
                )

            rule_priority = 0
            zone_rule = False
            if ticket.zone_id and ticket.partner_id:
                zone_rule = self.env['helpdesk.zone.rule'].search([
                    ('zone_id', '=',ticket.zone_id.id),
                    ('partner_ids', 'in', [ticket.partner_id.id])
                ], limit=1)

                rule_priority = int(zone_rule.priority or 0)

            ticket.priority = str(max(service_priority, rule_priority))

            if ticket.zone_id and not ticket.service_type_id and zone_rule:
                ticket.user_id = zone_rule.user_rule_id.id

            elif  ticket.service_type_id:
                if ticket.team_id.auto_assignment and ticket.team_id.assign_method =='by_rule':
                    ticket.user_id = ticket.team_id._onchange_assignment_rule(
                        priority_ticket = ticket.priority,
                        subcategory_ticket=ticket.sub_category_id.id if ticket.sub_category_id.id else False,
                        zone_ticket=ticket.zone_id.id,
                        support_ticket=ticket.support_type_id.id if ticket.support_type_id.id else False,
                    )
                

    
            
    
    @api.depends('service_type_id')
    def _compute_readonly(self):
        for ticket in self:
            if ticket.service_type_id:
                ticket.category_id = ticket.service_type_id.category_id
                ticket.sub_category_id = ticket.service_type_id.sub_category_id
            else:
                ticket.category_id = False
                ticket.sub_category_id = False

    @api.depends('service_type_id')
    def _compute_is_service(self):
        for ticket in self:
            ticket.is_service = bool(ticket.service_type_id)
    
    @api.onchange('team_id','partner_id')
    def _onchange_values_service(self):
        for record in self:
            record.service_type_id = False
    
    @api.model
    def _sla_reset_trigger(self):
        """Add the new fields to the trigger list so they are taken into account"""
        result = super()._sla_reset_trigger()
        result.extend(['service_type_id', 'zone_id', 'support_type_id'])
        return result

    def _sla_find_domain(self):
        domain = super()._sla_find_domain()
        domain.extend([
            ('service_id', '=', self.service_type_id.id or False),
            ('zone_id', '=', self.zone_id.id or False),
            ('support_type_id', '=', self.support_type_id.id or False),
        ])
        return domain
    

    @api.depends('partner_id', 'category_id', 'team_id')
    def _compute_allowed_service_types(self):
        """Get service_type_id according with filters"""
        for record in self:
            domain = []
            or_domain = []
            
            # Conditions OR
            if record.partner_id:
                or_domain.append(('partner_company_ids', '=', record.partner_id.id))
            
            if record.team_id:
                or_domain.append(('team_ids', '=', record.team_id.id))
            
            # If exist OR conditions, they have to be add with '|'
            if or_domain:
                if len(or_domain) == 1:
                    domain.extend(or_domain)
                else:
                    # Add operators '|' for OR
                    domain.append('|')
                    domain.extend(or_domain)
            
            # Condition AND (category_id)
            if record.category_id:
                domain.append(('category_id', '=', record.category_id.id))
            
            if domain:
                # Find the records that have the domain
                record.allowed_service_type_ids = self.env['helpdesk.service.type'].search(domain)
            else:
                # Without filters, it won't show records
                record.allowed_service_type_ids = False
    
   
        
    @api.depends('allowed_service_type_ids')
    def _compute_allowed_categories(self):
        """Extract unique category_ids from allowed_service_type_ids"""
        for record in self:
            if record.allowed_service_type_ids:
                # Get all the category_id according with service_type_id domain
                categories = record.allowed_service_type_ids.mapped('category_id')
                record.allowed_category_ids = categories
            else:
                record.allowed_category_ids = False

    @api.depends('allowed_service_type_ids')
    def _compute_allowed_subcategories(self):
        """Extract unique sub_category_ids from allowed_service_type_ids"""
        for record in self:
            if record.allowed_service_type_ids:
                # get all the sub_category_id according with service_type_id domain
                subcategories = record.allowed_service_type_ids.mapped('sub_category_id')
                record.allowed_subcategory_ids = subcategories
            else:
                record.allowed_subcategory_ids = False
                
    
    def _get_customer_initial(self, team):
        """Prefix for sequence (the first two letter of the team's name)"""
        if not team or not team.name:
            return 'XX'
        initial = team.name[0].upper()
        second_letter = team.name[1].upper() if len(team.name) > 1 else 'X'
        prefix = initial + second_letter
        return prefix
    
    def _get_sequence_code(self, team):
        name_code = team.replace(" ", ".")
        """Generate the sequence code for the prefix"""
        return f'helpdesk.ticket.customer.{name_code}'
    
    def _create_customer_sequence(self, initial,team):
        """Create a new sequence for the team's prefix"""
        name_code = team.replace(" ", ".")
        sequence_code = self._get_sequence_code(name_code)
        sequence_vals = {
            'name': f'Helpdesk Ticket - equipo {team}',
            'code': sequence_code,
            'implementation': 'standard',
            'prefix': f'{initial}-',
            'padding': 6,
            'number_increment': 1,
            'number_next': 1,
            'use_date_range': False,
            'company_id': False, 
        }
        
        sequence = self.env['ir.sequence'].sudo().create(sequence_vals)
        return sequence
    
    def _get_or_create_sequence(self, team):
        """Get or create the sequence for the team"""
        initial = self._get_customer_initial(team)
        sequence_code = self._get_sequence_code(team.name)
        
        sequence = self.env['ir.sequence'].sudo().search([
            ('code', '=', sequence_code)
        ], limit=1)

        if not sequence:
            sequence = self._create_customer_sequence(initial,team.name)
        
        return sequence
