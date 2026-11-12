import base64
from datetime import datetime

from babel.dates import format_date

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.image import image_data_uri, image_process

FORMAT_IMAGE_MIMETYPES = ('image/jpeg', 'image/png')
FORMAT_IMAGE_SIZE = (1024, 1024)
FORMAT_LANG = 'es_CO'


class RepairOrder(models.Model):
    _inherit = 'repair.order'

    contact_id = fields.Many2one(
        comodel_name='res.partner',
        string='Contacto',
        domain="[('parent_id', '=', partner_id)]",
    )
    service_type_ids = fields.Many2many(
        comodel_name='repair.service.type',
        string='Tipos de servicio',
    )
    other_service_desc = fields.Char(
        string='Describa otros',
    )
    reception_date = fields.Datetime(
        string='Fecha de ingreso',
        copy=False,
    )
    received_by_id = fields.Many2one(
        comodel_name='res.users',
        string='Recibido por',
        domain="[('share', '=', False)]",
        copy=False,
    )
    reception_image_ids = fields.Many2many(
        comodel_name='ir.attachment',
        relation='repair_order_reception_image_rel',
        column1='repair_id',
        column2='attachment_id',
        string='Registro fotográfico de ingreso',
        copy=False,
    )
    reception_signature = fields.Image(
        string='Firma de quien elabora',
        copy=False,
        attachment=False,
        max_width=1024,
        max_height=1024,
    )
    delivery_issue_date = fields.Date(
        string='Fecha de emisión',
        copy=False,
    )
    delivery_date = fields.Date(
        string='Fecha de entrega',
        copy=False,
    )
    delivery_station_date = fields.Datetime(
        string='Movido a estación de entrega',
        copy=False,
    )
    delivered_by_id = fields.Many2one(
        comodel_name='res.users',
        string='Entregado por',
        domain="[('share', '=', False)]",
        copy=False,
    )
    delivery_image_ids = fields.Many2many(
        comodel_name='ir.attachment',
        relation='repair_order_delivery_image_rel',
        column1='repair_id',
        column2='attachment_id',
        string='Registro fotográfico de salida',
        copy=False,
    )
    delivery_signature = fields.Image(
        string='Firma de quien entrega',
        copy=False,
        attachment=False,
        max_width=1024,
        max_height=1024,
    )
    inventory_line_ids = fields.One2many(
        comodel_name='repair.order.inventory.line',
        inverse_name='repair_id',
        string='Inventario',
        copy=False,
    )
    customer_signer_name = fields.Char(
        string='Nombre de quien recibe',
        copy=False,
    )
    customer_signer_vat = fields.Char(
        string='Cédula de quien recibe',
        copy=False,
    )
    customer_sign_date = fields.Date(
        string='Fecha de firma del cliente',
        compute='_compute_customer_sign_date',
        store=True,
        readonly=False,
        copy=False,
    )

    @api.depends('sign_client')
    def _compute_customer_sign_date(self):
        for record in self:
            if not record.sign_client:
                record.customer_sign_date = False
            elif not record.customer_sign_date:
                record.customer_sign_date = fields.Date.context_today(record)

    @api.onchange('partner_id')
    def _onchange_partner_id_contact(self):
        for record in self:
            if record.contact_id.parent_id != record.partner_id:
                record.contact_id = False

    @api.constrains('reception_image_ids', 'delivery_image_ids')
    def _check_format_images(self):
        for record in self:
            images = (record.reception_image_ids | record.delivery_image_ids).sudo()
            if images.filtered(lambda image: image.mimetype not in FORMAT_IMAGE_MIMETYPES):
                raise ValidationError(_("El registro fotográfico solo admite imágenes JPG o PNG."))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._bind_format_images()
        return records

    def write(self, vals):
        res = super().write(vals)
        if {'reception_image_ids', 'delivery_image_ids'} & set(vals):
            self._bind_format_images()
        return res

    def _bind_format_images(self):
        # Un adjunto sin res_id solo lo puede leer quien lo subió: sin esto, otro usuario no podría imprimir el formato
        for record in self:
            images = (record.reception_image_ids | record.delivery_image_ids).sudo()
            images.filtered(
                lambda image: not image.res_id and image.create_uid == self.env.user
            ).write({'res_model': self._name, 'res_id': record.id})

    def _get_format_contact_data(self):
        self.ensure_one()
        contact = self.contact_id or self.partner_id
        return {
            'name': contact.name or '',
            'function': contact.function or '',
            'email': contact.email or '',
            'phone': contact.phone or '',
        }

    def _get_format_service_types(self):
        self.ensure_one()
        return self.env['repair.service.type'].search([]) | self.service_type_ids

    def _get_format_equipment_data(self):
        self.ensure_one()
        equipment_data = [{
            'category': equipment.product_id.categ_id.name or '',
            'brand': equipment.brand_id.display_name or '',
            'model': equipment.model_id.name or equipment.model or '',
            'serial': equipment.lot_id.name or '',
        } for equipment in self.maintenance_equipment_ids]
        return equipment_data or [{
            'category': self.product_id.categ_id.name or '',
            'brand': '',
            'model': '',
            'serial': self.lot_id.name or '',
        }]

    def _get_format_signer_data(self, user):
        self.ensure_one()
        user = user.sudo().with_company(self.company_id)
        employee = user.employee_id
        return {
            'name': user.name or '',
            'job': employee.job_title or employee.job_id.name or user.partner_id.function or '',
            'email': employee.work_email or user.email or '',
        }

    def _get_format_control_data(self):
        get_param = self.env['ir.config_parameter'].sudo().get_param
        return {
            'update_date': get_param('stock_metromat.format_update_date', ''),
            'version': get_param('stock_metromat.format_version', ''),
        }

    def _get_format_image_uris(self, images):
        return [
            image_data_uri(base64.b64encode(image_process(image.raw, size=FORMAT_IMAGE_SIZE)))
            for image in images
        ]

    def _format_date_es(self, value, date_format):
        # Los formatos son documentos en español, sin importar el idioma del usuario ni los idiomas activos
        if not value:
            return ''
        if isinstance(value, datetime):
            value = fields.Datetime.context_timestamp(self, value)
        return format_date(value, format=date_format, locale=FORMAT_LANG)

    def _format_long_date(self, value):
        return self._format_date_es(value, 'long')

    def _format_full_date(self, value):
        return self._format_date_es(value, 'full')
