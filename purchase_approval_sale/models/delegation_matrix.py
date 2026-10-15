# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SaleDelegationAuthoritySetting(models.Model):
    _name = "sale.delegation.authority.setting"
    _description = "Matriz de Delegación y Autoridad (Cotizaciones)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "company_id, name"

    name = fields.Char(string="Nombre de Matriz", required=True, tracking=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, tracking=True)
    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        required=True,
        default=lambda self: self.env.company.currency_id,
        tracking=True,
    )

    is_default_to_sale = fields.Boolean(string="Usar por defecto en ventas", tracking=True)
    smmlv_code = fields.Char(string="Código variable SMMLV", default="SMMLV", required=True, tracking=True)
    smmlv_value = fields.Integer(
        string="SMMLV",
        compute="_compute_smmlv",
        store=False,
        help="Valor SMMLV vigente (año en curso). Se usa como base para comparar el total de la cotización.",
    )

    approval_with_sequence = fields.Boolean(string="Aprobación con Secuencia", default=True, tracking=True)
    approval_automatic_send = fields.Boolean(
        string="Envío automático al aprobar",
        default=True,
        tracking=True,
        help="Al completar todos los niveles aplicables, se envía automáticamente la cotización al cliente.",
    )

    line_ids = fields.One2many(
        "sale.delegation.authority.line",
        "setting_id",
        string="Líneas de Aprobación",
        copy=True,
    )

    @api.constrains("is_default_to_sale", "company_id")
    def _check_one_default_per_company(self):
        for rec in self:
            if rec.is_default_to_sale:
                domain = [
                    ("id", "!=", rec.id),
                    ("company_id", "=", rec.company_id.id),
                    ("is_default_to_sale", "=", True),
                ]
                if self.search_count(domain):
                    raise ValidationError(_("Solo puede existir una Matriz por compañía marcada como 'Usar por defecto en ventas'."))

    @api.depends("company_id", "smmlv_code")
    def _compute_smmlv(self):
        today = fields.Date.context_today(self)
        current_year = today.year
        if "economic.variable.line" not in self.env.registry:
            for rec in self:
                rec.smmlv_value = 0
            return

        Line = self.env["economic.variable.line"].sudo()

        for rec in self:
            rec.smmlv_value = 0

            domain = []

            if "year" in Line._fields:
                domain.append(("year", "=", current_year))
            elif "anio" in Line._fields:
                domain.append(("anio", "=", current_year))

            if "company_id" in Line._fields:
                domain.append(("company_id", "in", [rec.company_id.id, False]))

            if "variable_code" in Line._fields:
                domain.append(("variable_code", "=", rec.smmlv_code))
            elif "code" in Line._fields:
                domain.append(("code", "=", rec.smmlv_code))
            elif "variable_id" in Line._fields and "economic.variable" in self.env.registry:
                Var = self.env["economic.variable"].sudo()
                var = Var.search([("code", "=", rec.smmlv_code)], limit=1)
                if var:
                    domain.append(("variable_id", "=", var.id))

            if "month" in Line._fields:
                order = "month desc, id desc"
            elif "mes" in Line._fields:
                order = "mes desc, id desc"
            elif "date" in Line._fields:
                order = "date desc, id desc"
            else:
                order = "id desc"

            line = Line.search(domain, order=order, limit=1)
            if line and "value" in Line._fields:
                try:
                    rec.smmlv_value = int(round(line.value or 0))
                except Exception:
                    rec.smmlv_value = 0


class SaleDelegationAuthorityLine(models.Model):
    _name = "sale.delegation.authority.line"
    _description = "Línea Matriz Delegación y Autoridad"
    _order = "sequence, id"

    setting_id = fields.Many2one("sale.delegation.authority.setting", required=True, ondelete="cascade")
    sequence = fields.Integer(string="Secuencia", default=10)

    approver_id = fields.Many2one("res.users", string="Aprobador Principal", required=True)
    alternate_approver_id = fields.Many2one("res.users", string="Aprobador Paralelo", help="Usuario alterno (backup).")

    smmlv_from = fields.Integer(
        string="A partir de (SMMLV)",
        default=0,
        help="Si la cotización equivale (COP/SMMLV) >= a este valor, el nivel se activa.",
    )

    active = fields.Boolean(default=True)
