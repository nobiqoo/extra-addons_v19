from odoo import _, fields, models


class MarginWarningWizard(models.TransientModel):
    _name = 'margin.warning.wizard'
    _description = 'Advertencia de Margen Bajo'

    line_id = fields.Many2one('sale.order', string='Cotizacion', required=True)
    message = fields.Text(string='Mensaje')
    res_users_sale_activity = fields.Many2many(
        'res.users',
        string='Usuarios responsables',
    )

    def action_continue(self):
        self.ensure_one()
        activity_type = self.env.ref('mail.mail_activity_data_todo')
        sale_model_id = self.env['ir.model']._get_id('sale.order')

        for user in self.res_users_sale_activity:
            self.env['mail.activity'].sudo().create({
                'activity_type_id': activity_type.id,
                'res_model_id': sale_model_id,
                'res_id': self.line_id.id,
                'user_id': user.id,
                'summary': _('Aprobacion de Margen Bajo'),
                'note': self.message,
            })
        return {'type': 'ir.actions.act_window_close'}

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}
