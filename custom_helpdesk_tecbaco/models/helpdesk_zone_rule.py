# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


TICKET_PRIORITY = [
    ('0', 'Low priority'),
    ('1', 'Medium priority'),
    ('2', 'High priority'),
    ('3', 'Urgent'),
]

class HelpdeskZone(models.Model):
    _name = "helpdesk.zone.rule"
    _description="Helpdesk zone rule"

    zone_id = fields.Many2one(
        'helpdesk.zone',
        string='Zona',
        required=True,
        ondelete='cascade'
    )

    user_rule_id = fields.Many2one(
        'res.users',
        string="Usuario de atención"
    )

    partner_ids = fields.Many2many(
        'res.partner',
        string='Correos remitentes'
    )

    team_id = fields.Many2one(
        'helpdesk.team',
        string="Equipo de helpdesk"
    )

    priority = fields.Selection(TICKET_PRIORITY, string='Prioridad', default='0')
    
    @api.constrains('partner_ids', 'zone_id')
    def _check_partner_unique_zone(self):
        for rule in self:
            if not rule.partner_ids or not rule.zone_id:
                continue

            conflicts = []

            for partner in rule.partner_ids:
                other_rules = self.search([
                    ('id', '!=', rule.id),
                    ('partner_ids', 'in', partner.id),
                    ('zone_id', '!=', rule.zone_id.id),
                ], limit=1)

                if other_rules:
                    conflicts.append(
                        _("• %(partner)s ya está asignado a la zona '%(zone)s'")
                        % {
                            'partner': partner.display_name,
                            'zone': other_rules.zone_id.display_name,
                        }
                    )

            if conflicts:
                raise ValidationError(_(
                    "No se puede guardar la configuración porque los siguientes correos "
                    "ya están asociados a otra zona:\n\n%s"
                ) % "\n".join(conflicts))