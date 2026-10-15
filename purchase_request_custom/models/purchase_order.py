from odoo import models, fields, _
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    version = fields.Integer(string='Versión', default=1, readonly=True, copy=False, tracking=True)
    _sql_constraints = [('version_positive', 'CHECK(version >= 1)', 'La versión debe ser >= 1.')]

    def action_request_draft(self):
        prev_state = {rec.id: rec.state for rec in self}
        res = super().action_request_draft()
        for rec in self:
            if prev_state.get(rec.id) == 'cancel' and rec.state == 'draft':
                rec.write({'version': rec.version + 1})
        return res
