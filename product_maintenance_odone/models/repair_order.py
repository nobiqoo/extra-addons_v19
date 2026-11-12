from odoo import fields, models


class RepairOrder(models.Model):
    _inherit = 'repair.order'

    sign_technician = fields.Image(
        string='Firma del Técnico',
        copy=False,
        attachment=False,
        max_width=1024,
        max_height=1024,
    )
    sign_client = fields.Image(
        string='Firma del Cliente',
        copy=False,
        attachment=False,
        max_width=1024,
        max_height=1024,
    )
    use_signed_work_orders_in_maintenance = fields.Boolean(
        related='company_id.use_signed_work_orders_in_maintenance',
    )

    def _get_maintenance_type_display(self):
        self.ensure_one()
        selection = dict(self._fields['maintenance_type']._description_selection(self.env))
        return selection.get(self.maintenance_type, '') or ''
