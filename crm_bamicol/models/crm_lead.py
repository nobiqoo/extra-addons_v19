# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CrmLead(models.Model):
    _inherit = 'crm.lead'


    architect_id = fields.Many2one(
        comodel_name='res.partner',
        string='Arquitecto',
        tracking=True,
        index=True,
        help=(
            'Arquitecto asociado a este '
            'lead/oportunidad. Obligatorio cuando el equipo de ventas tenga '
            'activada la opción "Requiere Arquitecto".'
        ),
    )


    architect_required = fields.Boolean(
        string='Arquitecto obligatorio',
        compute='_compute_architect_required',
        store=False,
    )

    @api.depends('team_id', 'team_id.require_architect')
    def _compute_architect_required(self):
        for lead in self:
            lead.architect_required = bool(
                lead.team_id and lead.team_id.require_architect
            )

    @api.constrains('architect_id', 'team_id')
    def _check_architect_required(self):
        for lead in self:
            if (
                lead.team_id
                and lead.team_id.require_architect
                and not lead.architect_id
            ):
                raise ValidationError(
                    'El campo "Arquitecto" es obligatorio para el equipo de '
                    f'ventas "{lead.team_id.name}". '
                    'Por favor seleccione un arquitecto antes de guardar.'
                )

    def _prepare_opportunity_quotation_context(self):
        ctx = super()._prepare_opportunity_quotation_context()
        ctx['default_architect_id'] = self.architect_id.id
        return ctx
