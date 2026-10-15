from odoo import models, fields, api


class ResCompany(models.Model):
    _inherit = 'res.company'

    url_service_superintendency = fields.Char(
        string='URL Servicio Superintendencia',
        default='https://www.superfinanciera.gov.co/SuperfinancieraWebServiceTRM/TCRMServicesWebService/TCRMServicesWebService?WSDL'
    )
    service_currency_id = fields.Many2one(
        string='Moneda a Actualizar',
        comodel_name='res.currency',
    )
    sync_trm_state = fields.Selection(
        selection=[
            ('enabled', 'Habilitado'),
            ('disabled', 'Deshabilitado')
        ],
        string='Estado Sincronización USD TRM',
        default='disabled',
    )
    apply_percentage = fields.Boolean(
        string='Aplicar Porcentaje',
        default=False,
    )
    percentage = fields.Float(
        string='Porcentaje',
        default=0.0,
    )

    @api.constrains('percentage')
    def _check_percentage(self):
        for record in self:
            if record.percentage > 100:
                raise models.ValidationError(
                    'El porcentaje no puede ser mayor a 100.'
                )
            if record.percentage < 0:
                raise models.ValidationError(
                    'El porcentaje no puede ser menor a 0.'
                )
