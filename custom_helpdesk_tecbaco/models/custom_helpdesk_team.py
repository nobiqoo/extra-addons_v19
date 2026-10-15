# -*- coding: utf-8 -*-

from odoo import models, fields
import random


class HelpdeskTeam(models.Model):
    _inherit = "helpdesk.team"

    service_ids = fields.Many2many('helpdesk.service.type', string="Servicios que este equipo atiende")
    partner_company_id = fields.Many2one('res.partner', string="Compañía del equipo")
    assignment_rule_ids = fields.One2many('helpdesk.assignment.rule','team_id',string="Reglas de asignación del equipo",domain="[('team_id','=',id)]") 
    footer_report = fields.Html(string="Pie de página para reporte de tickets")
    logo_report = fields.Binary("Logo File")
    assign_method = fields.Selection(
        selection_add=[('by_rule', 'Por regla')],
        default='by_rule',
        ondelete={'by_rule': 'set default'}
    )

    def _onchange_assignment_rule(self, priority_ticket=False, subcategory_ticket=False, zone_ticket=False, support_ticket=False):
        for team in self:
            if team.auto_assignment and team.assign_method =='by_rule':
                lines = team.assignment_rule_ids

                if subcategory_ticket and priority_ticket and zone_ticket and support_ticket:
                    result = lines.filtered(
                        lambda l: l.priority == priority_ticket and l.sub_category_id.id == subcategory_ticket and l.zone_id.id == zone_ticket and l.support_type_id.id == support_ticket
                    )
                   
                    if result and result[0].user_ids:
                        return random.choice(result[0].user_ids.ids)

                if subcategory_ticket and zone_ticket:
                    result = lines.filtered(
                        lambda l: l.sub_category_id.id == subcategory_ticket and l.zone_id.id == zone_ticket
                    )
                    if result and result[0].user_ids:
                        return random.choice(result[0].user_ids.ids)

                if subcategory_ticket and support_ticket:
                    result = lines.filtered(
                        lambda l: l.sub_category_id.id == subcategory_ticket and l.support_type_id.id == support_ticket
                    )
                    if result and result[0].user_ids:
                        return random.choice(result[0].user_ids.ids)
                
                if subcategory_ticket:
                    result = lines.filtered(
                        lambda l: l.sub_category_id.id == subcategory_ticket
                    )
                    if result and result[0].user_ids:
                        return random.choice(result[0].user_ids.ids)
                
            return False
