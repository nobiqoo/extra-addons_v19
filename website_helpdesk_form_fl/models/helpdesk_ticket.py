# -*- coding: utf-8 -*-
from lxml import etree
from markupsafe import Markup
from odoo import api, fields, models, _

class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    arl_affiliation = fields.Binary(string="Afiliación ARL")
    arl_affiliation_fname = fields.Char()
    ccf_affiliation = fields.Binary(string="Afiliación CCF")
    ccf_affiliation_fname = fields.Char()
    email_authorization = fields.Binary(string="Autorización de correo")
    email_authorization_fname = fields.Char()
    bank_certificate = fields.Binary(string="Certificación Bancaria")
    bank_certificate_fname = fields.Char()
    severance_certificate = fields.Binary(string="Certificación Cesantías")
    severance_certificate_fname = fields.Char()
    eps_certificate = fields.Binary(string="Certificación EPS")
    eps_certificate_fname = fields.Char()
    pension_certificate = fields.Binary(string="Certificación Pensiones")
    pension_certificate_fname = fields.Char()
    id_card = fields.Binary(string="Cédula")
    id_card_fname = fields.Char()
    job_application = fields.Binary(string="Solicitud de Empleo")
    job_application_fname = fields.Char()

    job_id = fields.Many2one("hr.job", string="Cargo")
    city_id = fields.Many2one("res.city", string="Ciudad")
    hr_coordinator_id = fields.Many2one("hr.employee.public", string="Coordinadora de RH")
    department_id = fields.Many2one("hr.department", string="Departamento")
    manager_id = fields.Many2one("hr.employee.public", string="Jefe Inmediato")

    document_number = fields.Integer(string="Documento (N°)")
    entry_date = fields.Date(string="Fecha de Ingreso")
    employee_name = fields.Char(string="Nombre del Colaborador")

    currency_id = fields.Many2one("res.currency", string="Moneda", default=lambda self: self.env.company.currency_id.id)
    wage = fields.Monetary(string="Salario", currency_field="currency_id")

    contract_term = fields.Selection([
        ('fixed', "Fijo"),
        ('indefinite', "Indefinido"),
        ('project', "Por proyecto"),
    ], string="Término del Contrato")

    task_count = fields.Integer(string="Tareas", compute="_compute_task_count", store=False)
    
    attachments_are_visible = fields.Boolean(related="team_id.attachments_are_visible")

    def _task_relation_field(self):
        Task = self.env['project.task']
        if 'ticket_id' in Task._fields:
            return 'ticket_id'
        return 'x_helpdesk_ticket_id'

    def _task_domain_for_this_ticket(self):
        self.ensure_one()
        rel = self._task_relation_field()
        return [(rel, '=', self.id)]

    def _compute_task_count(self):
        Task = self.env['project.task']
        rel = self._task_relation_field()
        for t in self:
            t.task_count = Task.search_count([(rel, '=', t.id)])

    def action_view_tasks(self):
        self.ensure_one()
        tree_view = self.env.ref('website_helpdesk_form_fl.view_project_task_tree_helpdesk_ticket').id
        return {
            "type": "ir.actions.act_window",
            "name": _("Tareas del ticket"),
            "res_model": "project.task",
            "view_mode": "list,form",   
            "views": [(False, "list"), (False, "form")],
            "target": "current",
            "domain": self._task_domain_for_this_ticket(),
            "context": {"default_%s" % self._task_relation_field(): self.id},
        }

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for ticket in records:
            ticket._autocreate_tasks_from_team()
        return records

 

    def _autocreate_tasks_from_team(self):
        self.ensure_one()
        team = self.team_id
        if not team or not team.task_template_ids:
            return

        Task = self.env['project.task']
        tpl_to_task = {}

        REL_FIELD = self._task_relation_field()

        for tpl in team.task_template_ids.sorted(key=lambda r: r.sequence or 0):
            vals = {
                'name': tpl.name,
                'project_id': tpl.project_id.id,
                'template_id': tpl.id,
                REL_FIELD: self.id,
            }
            if getattr(tpl, 'description', False):
                vals['description'] = tpl.description
            if getattr(tpl, 'user_id', False) and tpl.user_id:
                vals['user_ids'] = [(6, 0, [tpl.user_id.id])]
            if getattr(tpl, 'next_stage_id', False):
                vals['next_stage_id'] = tpl.next_stage_id.id

            task = Task.create(vals)
            tpl_to_task[tpl.id] = task.id

        not_linked_tpls = []
        for tpl in team.task_template_ids:
            if tpl.predecessor_id:
                child_task_id = tpl_to_task.get(tpl.id)
                pred_task_id = tpl_to_task.get(tpl.predecessor_id.id)
                if child_task_id and pred_task_id:
                    child_task = Task.browse(child_task_id)
                    child_task.write({
                        'depend_on_ids': [(4, pred_task_id)],
                        'x_is_blocked': True,  
                    })
                    if 'predecessor_task_id' in Task._fields:
                        child_task.predecessor_task_id = pred_task_id
                else:
                    not_linked_tpls.append(tpl)

        if not_linked_tpls:
            bullets = []
            for t in not_linked_tpls:
                pred_name = t.predecessor_id.display_name if t.predecessor_id else _('(sin predecesora)')
                bullets.append(
                    Markup("• ") + Markup.escape(t.display_name) +
                    Markup(" (") + Markup.escape(pred_name) + Markup(")")
                )
            body = Markup(_("No se pudieron enlazar predecesoras para las siguientes plantillas porque no pertenecen al equipo o no fueron incluidas en la creación:"))
            body += Markup("<br/>") + Markup("<br/>").join(bullets)
            self.message_post(body=body, subtype_xmlid="mail.mt_note", message_type='comment')

            self.message_post(
                body=Markup("<b>") + Markup(_("Las tareas de esas plantillas permanecerán BLOQUEADAS hasta corregir la configuración.")) + Markup("</b>"),
                subtype_xmlid="mail.mt_note",
                message_type='comment'
            )

        created_tasks = Task.browse(list(tpl_to_task.values()))
        if created_tasks:
            bullets = []
            for t in created_tasks:
                link = Markup(t._get_html_link()) 
                if 'predecessor_task_id' in Task._fields and t.predecessor_task_id:
                    pred = Markup(t.predecessor_task_id._get_html_link())
                    bullets.append(Markup("• ") + link + Markup(" (") + Markup(_("predecesora: ")) + pred + Markup(")"))
                else:
                    bullets.append(Markup("• ") + link)

            body = Markup(_("Se crearon tareas automáticas para este ticket:"))
            body += Markup("<br/>") + Markup("<br/>").join(bullets)
            self.message_post(body=body, subtype_xmlid="mail.mt_note", message_type='comment')

    def write(self, vals):
        old_user = {ticket.id: ticket.user_id.id for ticket in self}

        res = super().write(vals)

        if 'user_id' in vals:
            template = self.env.ref(
                'website_helpdesk_form_fl.mail_template_change_responsible',
                raise_if_not_found=False,
            )

            for ticket in self:
                if template and ticket.user_id and old_user.get(ticket.id) != ticket.user_id.id:
                    template.send_mail(ticket.id, force_send=True)

        return res
