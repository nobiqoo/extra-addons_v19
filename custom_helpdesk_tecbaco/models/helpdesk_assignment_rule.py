from odoo import models, fields, api

from odoo.exceptions import ValidationError


TICKET_PRIORITY = [
    ('0', 'Low priority'),
    ('1', 'Medium priority'),
    ('2', 'High priority'),
    ('3', 'Urgent'),
]

class HelpdeskAssignmentRule(models.Model):
    _name = "helpdesk.assignment.rule"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Reglas de asignación automática de tickets"

    name= fields.Char(string="Nombre de la regla", required=True)
    team_id = fields.Many2one('helpdesk.team', string="Equipo donde aplica la regla")
    sub_category_id = fields.Many2one('helpdesk.service.subcategory', string="Subcategoría asociada")
    zone_id = fields.Many2one('helpdesk.zone', string="Zona del cliente")
    support_type_id = fields.Many2one('helpdesk.support.type', string="Tipo de soporte")
    priority = fields.Selection(TICKET_PRIORITY, string='Prioridad', default='0', tracking=True)
    user_ids = fields.Many2many('res.users', string="Usuarios que pueden recibir la asignación")
    active = fields.Boolean(default=True)

    @api.constrains('team_id', 'zone_id', 'support_type_id','priority')
    def _check_unique_rule(self):
        for record in self:
            if not record.team_id:
                continue

            domain = [
                ('id', '!=', record.id or 0),
                ('team_id', '=', record.team_id.id),
                ('sub_category_id', '=', record.sub_category_id.id),
                ('zone_id', '=', record.zone_id.id),
                ('support_type_id', '=', record.support_type_id.id),
                ('priority', '=', record.priority),
            ]

            
            duplicates = self.search(domain, limit=1)

            if duplicates:
                raise ValidationError(
                    f"Ya existe una regla con los mismos parámetros (ID: {duplicates.id})"
                )