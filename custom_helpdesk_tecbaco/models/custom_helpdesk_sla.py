from odoo import models, fields, api

class HelpdeskSla(models.Model):
    _inherit = 'helpdesk.sla'

    service_id = fields.Many2one('helpdesk.service.type',string="Tipo de servicio")
    zone_id = fields.Many2one('helpdesk.zone', string="Zona")
    support_type_id = fields.Many2one('helpdesk.support.type', string="Tipo de soporte")

    def _matches_ticket(self, ticket):
        self.ensure_one()

        def _match(rule_value, ticket_value):
            if ticket_value and not rule_value:
                return False
            if rule_value:
                return rule_value == ticket_value
            return True

        return all([
            _match(self.service_id, ticket.service_type_id),
            _match(self.zone_id, ticket.zone_id),
            _match(self.support_type_id, ticket.support_type_id),
            _match(self.priority, ticket.priority),
            _match(self.team_id, ticket.team_id),
        ])