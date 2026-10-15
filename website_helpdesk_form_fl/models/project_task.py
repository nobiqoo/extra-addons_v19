# -*- coding: utf-8 -*-
from odoo import fields,api, models, _
from markupsafe import Markup

class ProjectTask(models.Model):
    _inherit = "project.task"

    x_helpdesk_ticket_id = fields.Many2one(
        "helpdesk.ticket",
        string="Ticket de Helpdesk",
        index=True,
        ondelete="set null",
        help="Relación con el ticket cuando project.task no expone el campo nativo 'ticket_id'.",
    )
    count_helpdesk_tickets = fields.Integer(
        string="Tickets de Helpdesk",
        compute="_compute_count_helpdesk_tickets",
    )

    template_id = fields.Many2one('helpdesk.team.task.template', string="Plantilla origen", index=True)
    predecessor_task_id = fields.Many2one('project.task', string="Tarea predecesora", ondelete='restrict')
    dependent_task_ids = fields.One2many('project.task', 'predecessor_task_id', string="Tareas dependientes")
    x_is_blocked = fields.Boolean(string="Bloqueada", default=False)
    next_stage_id = fields.Many2one('project.task.type', string="Etapa al desbloquear")


    def _get_unified_dependents(self):
        self.ensure_one()
        dependents = self.child_ids
        if 'dependent_task_ids' in self._fields:
            dependents |= self.dependent_task_ids
        return dependents

    def _is_now_completed(self, vals):
        if 'state' in vals and vals['state'] == '1_done':
            return True
        if 'stage_id' in vals:
            stage = self.env['project.task.type'].browse(vals['stage_id'])
            return bool(getattr(stage, 'fold', False))
        return False

    def _get_related_ticket(self):
        self.ensure_one()
        for fname in ('x_helpdesk_ticket_id', 'ticket_id'):
            if fname in self._fields and getattr(self, fname):
                return getattr(self, fname)
        return self.env['helpdesk.ticket']

    def _unlock_dependents(self):
        Task = self.env['project.task']
        for task in self:
            pred_link = Markup(task._get_html_link()) if hasattr(task, '_get_html_link') else Markup.escape(task.display_name)

            unlocked_links = []

            for child in task._get_unified_dependents():
                upd = {'x_is_blocked': False}

                if 'depend_on_ids' in child._fields:
                    upd['depend_on_ids'] = [(3, task.id)]

                if child.next_stage_id:
                    upd['stage_id'] = child.next_stage_id.id

                child.write(upd)

                recipients = []
                if 'user_ids' in child._fields and child.user_ids:
                    recipients += child.user_ids.mapped('partner_id').ids
                recipients = list(set(recipients))

                if recipients:
                    child.message_subscribe(partner_ids=recipients)

                body_child = Markup(_("Desbloqueada por finalización de %s")) % pred_link
                child.message_post(
                    body=body_child,
                    subtype_xmlid="mail.mt_note",
                    message_type='comment',
                    partner_ids=recipients,
                )

                user_for_activity = (child.user_ids and child.user_ids[0].id) or False
                if user_for_activity:
                    note_txt = Markup(_("La predecesora %s ha finalizado. Continúa el flujo.")) % pred_link
                    child.activity_schedule(
                        'mail.mail_activity_data_todo',
                        user_id=user_for_activity,
                        summary=_("Tarea disponible"),
                        note=note_txt,
                    )

                unlocked_links.append(Markup(child._get_html_link()) if hasattr(child, '_get_html_link') else Markup.escape(child.display_name))

            if unlocked_links:
                bullets = [Markup("• ") + link for link in unlocked_links]
                body_pred = Markup(_("La tarea liberó dependientes:"))
                body_pred += Markup("<br/>") + Markup("<br/>").join(bullets)
                task.message_post(
                    body=body_pred,
                    subtype_xmlid="mail.mt_note",
                    message_type='comment',
                )

            ticket = task._get_related_ticket()
            if ticket and unlocked_links:
                bullets = [Markup("• ") + link for link in unlocked_links]
                body_ticket = (Markup(_("Se desbloquearon tareas dependientes de %s:")) % pred_link)
                body_ticket += Markup("<br/>") + Markup("<br/>").join(bullets)
                ticket.message_post(
                    body=body_ticket,
                    subtype_xmlid="mail.mt_note",
                    message_type='comment',
                )


    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            if rec._is_now_completed(vals):
                rec._unlock_dependents()
            if rec.predecessor_task_id and not rec.parent_id:
                rec.parent_id = rec.predecessor_task_id.id
        return res

    @api.model
    def create(self, vals):
        if vals.get('predecessor_task_id') and not vals.get('parent_id'):
            vals['parent_id'] = vals['predecessor_task_id']
        return super().create(vals)
    
    def action_view_dependents(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("project.action_view_task")
        all_ids = (self.child_ids | (self.dependent_task_ids if 'dependent_task_ids' in self._fields else self.env['project.task'])).ids
        action.update({
            "domain": [("id", "in", all_ids)],
            "context": dict(self.env.context, search_default_project_id=self.project_id.id),
            "name": _("Dependientes / Sub-tareas de %s") % self.display_name,
        })
        return action

    def _compute_count_helpdesk_tickets(self):
        for task in self:
            task.count_helpdesk_tickets = len(self.x_helpdesk_ticket_id)

    def action_open_helpdesk_ticket(self):
        self.ensure_one()
        ticket = self.x_helpdesk_ticket_id
        return {
            "type": "ir.actions.act_window",
            "name": "Ticket de Helpdesk",
            "res_model": "helpdesk.ticket",
            "view_mode": "form",
            "res_id": ticket.id,
            "target": "current",
        }
