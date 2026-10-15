# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountOperationSite(models.Model):
    """Sede de operación (tarea 10340).

    Maestro del equipo contable que asocia cada sede con su municipio y con el
    ReteICA que debe aplicarse allí. El usuario operativo solo elige la sede en
    el documento: la ciudad y los impuestos no se le muestran.
    """

    _name = 'account.operation.site'
    _description = 'Sede de Operación'
    _order = 'name'

    name = fields.Char(
        string="Nombre de la sede", required=True,
        help="Nombre con el que el usuario identifica la sede en los "
             "documentos. Ej.: Sede Cali Norte, Sede Medellín Poblado.")
    city_id = fields.Many2one(
        'res.city', string="Ciudad", required=True, ondelete='restrict',
        help="Municipio en el que opera la sede. Determina la tarifa de "
             "ReteICA que aplica a los documentos originados aquí.")
    sale_reteica_tax_id = fields.Many2one(
        'account.tax', string="ReteICA de venta",
        domain="[('type_tax_use', '=', 'sale'),"
               " ('company_id', 'in', (False, company_id))]",
        ondelete='restrict',
        help="Impuesto que se agrega a las líneas de las facturas y notas de "
             "crédito de cliente emitidas desde esta sede.")
    purchase_reteica_tax_id = fields.Many2one(
        'account.tax', string="ReteICA de compra",
        domain="[('type_tax_use', '=', 'purchase'),"
               " ('company_id', 'in', (False, company_id))]",
        ondelete='restrict',
        help="Impuesto que se agrega a las líneas de las facturas y notas de "
             "crédito de proveedor registradas desde esta sede.")
    company_id = fields.Many2one(
        'res.company', string="Compañía", required=True,
        default=lambda self: self.env.company)
    active = fields.Boolean(string="Activo", default=True)

    _name_company_uniq = models.Constraint(
        'unique (name, company_id)',
        "Ya existe una sede de operación con ese nombre en la compañía.",
    )

    @api.constrains('sale_reteica_tax_id', 'purchase_reteica_tax_id')
    def _check_tax_type(self):
        """Evita configurar un impuesto de compra como si fuera de venta."""
        for site in self:
            if site.sale_reteica_tax_id.type_tax_use not in (False, 'sale'):
                raise ValidationError(_(
                    "The tax %s is not a sales tax and cannot be used as the "
                    "sales ReteICA of the site.", site.sale_reteica_tax_id.name))
            if site.purchase_reteica_tax_id.type_tax_use not in (False, 'purchase'):
                raise ValidationError(_(
                    "The tax %s is not a purchase tax and cannot be used as "
                    "the purchase ReteICA of the site.",
                    site.purchase_reteica_tax_id.name))

    @api.depends('name', 'city_id')
    def _compute_display_name(self):
        for site in self:
            site.display_name = (
                f"{site.name} ({site.city_id.name})" if site.city_id
                else site.name)

    def _get_reteica_tax(self, move_type):
        """ReteICA que corresponde al tipo de documento, o un recordset vacío.

        Las notas de crédito siguen la misma dirección que la factura que
        corrigen, así que comparten el impuesto con su tipo de documento.
        """
        self.ensure_one()
        if move_type in self.env['account.move'].get_sale_types(include_receipts=True):
            return self.sale_reteica_tax_id
        if move_type in self.env['account.move'].get_purchase_types(include_receipts=True):
            return self.purchase_reteica_tax_id
        return self.env['account.tax']

    @api.model
    def _get_all_reteica_taxes(self):
        """Todos los impuestos configurados hoy como ReteICA en alguna sede.

        Sirve para reconocer qué impuestos gestiona el módulo y poder retirar
        el de la sede anterior sin tocar el IVA ni ningún otro impuesto que el
        usuario haya puesto a mano.
        """
        sites = self.sudo().with_context(active_test=False).search([])
        return sites.sale_reteica_tax_id | sites.purchase_reteica_tax_id
