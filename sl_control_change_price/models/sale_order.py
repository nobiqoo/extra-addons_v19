from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    can_edit_price_after_confirm = fields.Boolean(
        string='Can Edit Price After confirm',
        compute='_compute_can_edit_price',
        store=False
    )

    def _compute_can_edit_price(self):
        has_permission = self.env.user.has_group('sl_control_change_price.group_can_approve_reject')
        for record in self:
            record.can_edit_price_after_confirm = has_permission


    @api.depends(
        'order_line.price_unit',
        'order_line.product_template_id.list_price',
        'order_line.discount',
        'approved',
        'company_id')
    def _compute_disable_confirm_button(self):
        for order in self:
            price_unit_restriction = order.company_id.price_unit_restriction

            discount_restriction = order.company_id.discount_restriction

            maximun_discount_restriction = order.company_id.maximun_discount_restriction

            price_unit_restriction_selection = order.company_id.price_unit_restriction_selection

            # Si la orden ya fue aprobada, no bloquear la confirmación
            if order.approved:
                order.disable_confirm_button = False
                continue

            precision = self.env['decimal.precision'].precision_get('Product Price') or 6
            maximun_discount_restriction = float(maximun_discount_restriction) * 100 if discount_restriction else None

            # Filtrar solo las líneas que cumplen la condición not line.display_type
            filtered_lines = [line for line in order.order_line if not line.display_type]

            for line in filtered_lines:

                line.warning_line = False
                line_price_unit = round(line.price_unit, precision)

                product_price = round(line.product_template_id.list_price, precision) if price_unit_restriction_selection == 'price_unit' else None
                pricelist = round(line.order_id.pricelist_id._get_product_price(line.product_id, line.product_uom_qty, line.product_uom), precision) if price_unit_restriction_selection == 'price_list' else None

                warning_conditions = {
                    'both': (
                            price_unit_restriction_selection == 'price_unit'
                            and discount_restriction
                            and (line_price_unit < product_price or line.discount > maximun_discount_restriction)
                    ),
                    'price': (
                            price_unit_restriction_selection == 'price_unit'
                            and line_price_unit < product_price
                    ),
                    'price_list': (
                            price_unit_restriction_selection == 'price_list'
                            and (
                                    (discount_restriction and (
                                                line_price_unit < pricelist or line.discount > maximun_discount_restriction))
                                    or (not discount_restriction and line_price_unit < pricelist)
                            )
                    ),
                    'discount': discount_restriction and line.discount > maximun_discount_restriction,
                }

                for message, condition in warning_conditions.items():
                    if condition:
                        line.warning_line = True
                        line.message_restriction = message
                        break


            order.disable_confirm_button = any(line.warning_line for line in order.order_line)

    state = fields.Selection(selection_add=[('to_approve', 'Por Aprobar'),
                                            ('approved', 'Aprobado'),
                                            ('refused', 'Rechazado')
                                            ])

    disable_confirm_button = fields.Boolean(string="Disable Confirm Button",
                                            compute="_compute_disable_confirm_button",
                                            store=True)

    approved = fields.Boolean(string="approved order?", default=False)
    
    # Campo para guardar el estado original antes de solicitar aprobación
    state_before_approval = fields.Selection([
        ('draft', 'Quotation'),
        ('sent', 'Quotation Sent'),
    ], string='State Before Approval', copy=False)

    def send_request_to_change_price(self):
        """Solicitar aprobación de cambio de precio"""
        for order in self:
            # Guardar el estado actual antes de cambiar
            order.state_before_approval = order.state
            order.state = 'to_approve'

    def refuse_change_price(self):
        """Rechazar cambio de precio - vuelve al estado original"""
        for order in self:
            # Restaurar el estado original o poner en draft
            order.state = order.state_before_approval or 'draft'
            order.state_before_approval = False

    def approve_change_price(self):
        """Aprobar cambio de precio - vuelve al estado original para permitir confirmación"""
        for order in self:
            # Restaurar el estado original para que pueda ser confirmado
            original_state = order.state_before_approval or 'draft'
            order.approved = True
            order.state = original_state
            order.state_before_approval = False

    def _get_forbidden_state_confirm(self):
        """Retorna un conjunto de estados que no pueden ser confirmados"""
        res = super(SaleOrder, self)._get_forbidden_state_confirm()
        # Agregar 'to_approve' y 'refused' como estados prohibidos para confirmación
        res.add('to_approve')
        res.add('refused')
        return res

    def _confirmation_error_message(self):
        """Validar si la orden puede ser confirmada con control de aprobación"""
        self.ensure_one()
        
        # Validar si tiene restricciones de precio sin aprobar
        if self.disable_confirm_button and not self.approved:
            return _(
                'La orden no se puede confirmar sin ser aprobada.\n'
                'Por favor, solicite la aprobación del cambio de precio.'
            )
        
        # Llamar al método padre para validaciones estándar (estados draft/sent, productos, etc.)
        return super()._confirmation_error_message()

    def action_confirm(self):
        """Confirmar orden - Validaciones adicionales"""
        return super().action_confirm()


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    warning_line = fields.Boolean('warning line')
    message_restriction = fields.Selection([
        ('price', 'Uno o varios de los productos tiene un precio menor al presente en el producto'),
        ('discount', 'Uno o varios de los productos tiene un descuento mayor que el permitido'),
        ('price_list', 'Uno o varios de los productos tiene un precio menor al de la lista de precios'),
        ('both',
         'Uno o varios de los productos tiene un descuento mayor que el permitido o un precio menor al de la lista de precios'),
    ], string='Message Restriction',
        readonly="1")

    def show_message_restriction(self):
        if self.message_restriction:
            # Obtener el texto de la selección
            message_dict = dict(self._fields['message_restriction'].selection)
            message_text = message_dict[self.message_restriction]

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Restricción!"),
                    'message': _(message_text),
                    'type': 'danger',
                    'sticky': False,
                }
            }


class SaleOrderReport(models.AbstractModel):
    _name = 'report.sale.report_saleorder'
    _description = 'Sale order Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['sale.order'].browse(docids)
        for doc in docs:
            if doc.state not in ['sale', 'done', 'approved'] and doc.disable_confirm_button:
                raise ValidationError('La orden debe ser aprobada para que la pueda imprimir')

        return {
            'doc_ids': docs.ids,
            'doc_model': 'sale.order',
            'docs': docs,
            'proforma': True
        }
