# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HelpdeskTeamTaskTemplate(models.Model):
    _name = "helpdesk.team.task.template"
    _description = "Plantilla de Tareas Automáticas por Equipo"
    _order = "sequence, id"

    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    team_id = fields.Many2one("helpdesk.team", string="Equipo", required=True, ondelete="cascade")
    name = fields.Char(string="Nombre de la tarea", help="Si se deja vacío, se usa el asunto del ticket.")
    project_id = fields.Many2one("project.project", string="Proyecto", required=True)
    user_id = fields.Many2one("res.users", string="Asignado a")
    description = fields.Html(string="Descripción por defecto", sanitize=True)
    create_ticket_message = fields.Boolean(string="Agregar enlace al ticket", default=True)
    predecessor_id = fields.Many2one(
        'helpdesk.team.task.template', string="Predecesora", ondelete='restrict'
    )
    dependent_ids = fields.One2many(
        'helpdesk.team.task.template', 'predecessor_id', string="Dependientes"
    )
    next_stage_id = fields.Many2one(
        'project.task.type', string="Etapa al desbloquear",
        domain="[('project_ids','in',project_id)]"
    )

    @api.constrains('predecessor_id')
    def _check_no_cyclic_predecessor(self):
        for rec in self:
            seen = set()
            node = rec.predecessor_id
            while node:
                if node.id in seen or node == rec:
                    raise ValidationError(_("Dependencia cíclica detectada en plantillas de tarea."))
                seen.add(node.id)
                node = node.predecessor_id

class HelpdeskTeam(models.Model):
    _inherit = "helpdesk.team"

    task_template_ids = fields.One2many(
        "helpdesk.team.task.template", "team_id",
        string="Plantillas de Tareas"
    )
    x_helpdesk_ticket_id = fields.Many2one(
        "helpdesk.ticket", string="Ticket de Helpdesk",
        index=True, ondelete="set null",
        help="Relación con el ticket (usado cuando project.task no expone 'ticket_id')."
    )
    attachments_are_visible = fields.Boolean(
        string="Los adjuntos son visibles",
        default=False
    )
   
