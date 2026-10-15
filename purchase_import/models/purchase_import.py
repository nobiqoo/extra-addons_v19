# -*- coding: utf-8 -*-
import odoo
from ast import literal_eval

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

COST_LIST = [
    ("equal", "Equal"),
    ("by_quantity", "By Quantity"),
    ("by_current_cost_price", "By Cost"),
    ("by_weight", "By Weight"),
    ("by_volume", "By Volume"),
]

COST_DICT = {
    "equal": "product_equal",
    "by_quantity": "product_qty",
    "by_current_cost_price": "price_cost",
    "by_weight": "product_weight",
    "by_volume": "product_volume",
}


class PurchaseImport(models.Model):
    _name = "purchase.import"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Purchase import"
    _order = "id desc"

    def _default_company_id(self):
        return self.env.company

    def _default_currency_id(self):
        return self.env.company.currency_id

    def _default_user_id(self):
        return self.env.user

    # Company
    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        copy=False,
        default=_default_company_id,
    )
    company_currency_id = fields.Many2one(
        related="company_id.currency_id", string="Company currency", readonly=True
    )

    country_id = fields.Many2one(comodel_name="res.country", required=True)

    # Cost
    cost_id = fields.Many2one(
        comodel_name="stock.landed.cost", string="Landed cost", copy=False
    )
    landed_costs_count = fields.Integer(compute="_compute_landed_costs_count")
    cost_type = fields.Selection(
        selection=COST_LIST, string="Cost method", required=True, default="by_quantity"
    )

    # Currency
    currency_id = fields.Many2one(
        comodel_name="res.currency", required=True, default=_default_currency_id
    )

    # Date
    date_destination = fields.Date()
    date_import = fields.Date()
    date_load = fields.Date()
    date_nationalization = fields.Date(default=fields.Date.today())
    date_origin = fields.Char("Port of origin")
    date_port = fields.Char("Port of destination")
    date_rate = fields.Date(default=fields.Date.today())

    # Expense
    expense_freight = fields.Float(compute="_compute_expense")
    expense_freight_currency = fields.Float(compute="_compute_expense")
    expense_insurance = fields.Float(compute="_compute_expense")
    expense_insurance_currency = fields.Float(compute="_compute_expense")

    # Incoterm
    # Meramente informativo: la selección no afecta el cálculo de flete/seguro.
    incoterms_id = fields.Many2one(
        comodel_name="account.incoterms", string="Incoterm", required=True
    )

    invoices_ids = fields.Many2many(
        comodel_name="account.move",
        relation="account_move_purchase_import_rel",
        column1="purchase_import_id",
        column2="account_move_id",
        copy=False,
    )

    import_type = fields.Selection(
        selection=[
            ("purchase", "Purchases"),
            ("picking", "Pickings"),
        ],
        required=True,
        default="purchase",
    )

    immediate_transfer = fields.Boolean(default=False)

    line_ids = fields.One2many(
        comodel_name="purchase.import.line", inverse_name="import_id", string="Lines"
    )

    # Manual
    manual_freight = fields.Monetary()
    manual_insurance = fields.Monetary()

    move_is = fields.Boolean(default=False, copy=False)
    moves_ids = fields.Many2many(comodel_name="stock.move", copy=False)
    move_lines_ids = fields.Many2many(comodel_name="stock.move.line", copy=False)

    name = fields.Char(required=True, copy=False, default=lambda self: _("New"))

    notes = fields.Html("Terms and Conditions")

    # Partner
    partner_id = fields.Many2one(
        comodel_name="res.partner", required=True, tracking=True
    )
    partner_ref = fields.Char("Vendor Reference", copy=False)

    # Picking
    pickings_ids = fields.Many2many("stock.picking")
    picking_type_id = fields.Many2one(
        comodel_name="stock.picking.type",
        compute="_compute_picking_type_id",
        store=True,
    )
    picking_type_code = fields.Selection(related="picking_type_id.code", readonly=True)

    # Price
    price_cost = fields.Monetary(string="Cost", compute="_compute_price_cost")
    price_expense = fields.Monetary("Expense", compute="_compute_price_expense_sum", store=True)
    price_expense_currency = fields.Monetary(
        string="Currency Expense",
        compute="_compute_price_expense",
        currency_field="company_currency_id",
    )
    price_expenses = fields.Float(
        string="Expenses", compute="_compute_price_expenses"
    )
    price_expenses_currency = fields.Monetary(
        string="Currency Expenses",
        compute="_compute_price_expenses",
        currency_field="company_currency_id",
    )
    price_freight = fields.Float(string="Freight", compute="_compute_price_freight")
    price_freight_currency = fields.Monetary(
        string="Currency Freight",
        compute="_compute_price_freight_currency",
        currency_field="company_currency_id",
    )
    price_insurance = fields.Monetary(
        string="Insurance", 
        compute="_compute_price_insurance"
    )
    price_insurance_currency = fields.Monetary(
        string="Currency Insurance",
        compute="_compute_price_insurance_currency",
        currency_field="company_currency_id",
    )
    price_tariff = fields.Monetary(string="Tariff", compute="_compute_price_tariff")
    price_tariff_currency = fields.Monetary(
        string="Currency Tariff",
        compute="_compute_price_tariff",
        currency_field="company_currency_id",
    )
    price_taxes = fields.Float(string="Taxes", compute="_compute_price_taxes")
    price_taxes_currency = fields.Monetary(
        string="Currency Taxes",
        compute="_compute_price_taxes",
        currency_field="company_currency_id",
    )
    price_total = fields.Monetary(string="Subtotal", compute="_compute_price_total")

    purchases_ids = fields.Many2many(comodel_name="purchase.order", copy=False)

    show_operations = fields.Boolean(compute="_compute_show_operations")

    user_id = fields.Many2one(
        comodel_name="res.users", required=True, copy=False, default=_default_user_id
    )

    use_create_lots = fields.Boolean(related="picking_type_id.use_create_lots")

    # Rate
    rate_currency = fields.Float(
        compute="_compute_rate", store=True, help="Exchange rate."
    )
    rate_inverse = fields.Float(
        compute="_compute_rate", store=True, help="Reverse exchange rate."
    )

    show_lots_text = fields.Boolean(compute="_compute_show_lots_text")

    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("confirm", "Confirm"),
            ("done", "Done"),
            ("cancel", "Cancel"),
        ],
        readonly=True,
        copy=False,
        default="draft",
        tracking=True,
    )

    # Other information
    purchase_names = fields.Char(
        string="Compras", compute="_get_purchase_names", store=True
    )

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        self.country_id = self.partner_id.country_id

    @api.onchange("purchases_ids")
    def _onchange_purchases_ids_currency(self):
        currencies = self.purchases_ids.mapped("currency_id")
        if len(currencies) == 1:
            self.currency_id = currencies

    @api.onchange("pickings_ids")
    def _onchange_pickings_ids_currency(self):
        currencies = self.pickings_ids.purchase_id.mapped("currency_id")
        if len(currencies) == 1:
            self.currency_id = currencies

    @api.constrains("currency_id", "purchases_ids")
    def _check_currency_purchases(self):
        for record in self:
            currencies = record.purchases_ids.mapped("currency_id")
            if len(currencies) > 1:
                raise ValidationError(_(
                    "Las compras seleccionadas tienen monedas distintas (%s); "
                    "una importación no puede mezclar monedas."
                ) % ", ".join(currencies.mapped("name")))
            if currencies and record.currency_id != currencies:
                raise ValidationError(_(
                    "La moneda de la importación (%s) no coincide con la moneda "
                    "de la compra seleccionada (%s). Corrija la moneda para que "
                    "los subtotales y totales se calculen correctamente."
                ) % (record.currency_id.name, currencies.name))

    @api.model_create_multi
    def create(self, vals_list):
        Sequence = self.env["ir.sequence"]
        for vals in vals_list:
            code = "purchase.import"
            if vals.get("name", "New") == "New":
                vals["name"] = Sequence.next_by_code(code) or "/"
        return super(PurchaseImport, self).create(vals_list)

    @api.depends(
        "invoices_ids",
        "invoices_ids.line_ids.is_landed_costs_line",
        "invoices_ids.line_ids.product_id",
        "price_cost",
        "line_ids.price_freight",
        "line_ids.price_insurance",
    )
    def _compute_expense(self):
        for record in self:
            invoice_field = record.company_id.purchase_import_type
            amount_freight = 0.0
            amount_insurance = 0.0

            for invoice in record.invoices_ids:
                price_cost = sum(invoice.imports_ids.mapped("price_cost"))
                percentage = record.price_cost / (price_cost or record.price_cost or 1)
                landed_lines = invoice.line_ids.filtered(
                    lambda l: l.is_landed_costs_line and l.import_type
                )
                if landed_lines:
                    freight_lines = landed_lines.filtered(lambda l: l.import_type == "freight")
                    insurance_lines = landed_lines.filtered(lambda l: l.import_type == "insurance")
                    amount_freight += percentage * abs(sum(freight_lines.mapped("balance")))
                    amount_insurance += percentage * abs(sum(insurance_lines.mapped("balance")))
                elif invoice.import_type == "freight":
                    amount_freight += percentage * getattr(invoice, invoice_field)
                elif invoice.import_type == "insurance":
                    amount_insurance += percentage * getattr(invoice, invoice_field)

            line_freight = sum(record.line_ids.mapped("price_freight"))
            line_insurance = sum(record.line_ids.mapped("price_insurance"))
            record.update({
                "expense_freight": line_freight if line_freight else record.action_currency_company_convert(abs(amount_freight)),
                "expense_freight_currency": abs(amount_freight) if amount_freight else record.action_currency_convert(line_freight),
                "expense_insurance": line_insurance if line_insurance else record.action_currency_company_convert(abs(amount_insurance)),
                "expense_insurance_currency": abs(amount_insurance) if amount_insurance else record.action_currency_convert(line_insurance),
            })

    @api.depends('line_ids.price_expense')
    def _compute_price_expense_sum(self):
        for record in self:
            record.price_expense = sum(record.line_ids.mapped('price_expense'))

    @api.depends('line_ids.price_expense_currency')
    def _compute_price_expense(self):
        for record in self:
            price_expense_currency = sum(record.line_ids.mapped('price_expense_currency'))
            record.update({'price_expense_currency': price_expense_currency})

    @api.depends('line_ids.price_freight_currency')
    def _compute_price_freight_currency(self):
        for record in self:
            price_freight_currency = sum(record.line_ids.mapped('price_freight_currency'))
            record.update({'price_freight_currency': price_freight_currency})

    @api.depends("line_ids.price_cost")
    def _compute_price_cost(self):
        for record in self:
            price_cost = sum(record.line_ids.mapped("price_cost"))
            record.update({"price_cost": price_cost})

    @api.depends(
        "date_import",
        "currency_id",
        "date_rate",
        "invoices_ids",
        "invoices_ids.line_ids.is_landed_costs_line",
        "invoices_ids.line_ids.product_id",
        "price_cost",
        "line_ids.price_expense",
    )
    def _compute_price_expenses(self):
        for record in self:
            invoice_field = record.company_id.purchase_import_type
            amount_untaxed = 0.0

            for invoice in record.invoices_ids:
                price_cost = sum(invoice.imports_ids.mapped("price_cost"))
                percentage = record.price_cost / (price_cost or record.price_cost or 1)
                landed_lines = invoice.line_ids.filtered(
                    lambda l: l.is_landed_costs_line and l.import_type
                )
                if landed_lines:
                    expense_lines = landed_lines.filtered(lambda l: l.import_type == "expense")
                    amount_untaxed += percentage * abs(sum(expense_lines.mapped("balance")))
                elif invoice.import_type == "expense":
                    amount_untaxed += percentage * getattr(invoice, invoice_field)

            line_expenses = sum(record.line_ids.mapped("price_expense"))
            if line_expenses:
                price_expenses = line_expenses
                if not amount_untaxed:
                    amount_untaxed = record.action_currency_convert(line_expenses)
            elif amount_untaxed:
                price_expenses = record.action_currency_company_convert(abs(amount_untaxed))
            else:
                price_expenses = 0.0
                amount_untaxed = 0.0

            record.update({
                "price_expenses": price_expenses,
                "price_expenses_currency": abs(amount_untaxed),
            })

    @api.depends(
        "date_import",
        "invoices_ids",
        "invoices_ids.line_ids.is_landed_costs_line",
        "invoices_ids.line_ids.product_id",
        "price_cost",
        "line_ids.price_import_tax",
    )
    def _compute_price_taxes(self):
        for record in self:
            invoice_field = record.company_id.purchase_import_type
            amount_untaxed = 0.0

            for invoice in record.invoices_ids:
                price_cost = sum(invoice.imports_ids.mapped("price_cost"))
                percentage = record.price_cost / (price_cost or record.price_cost or 1)
                landed_lines = invoice.line_ids.filtered(
                    lambda l: l.is_landed_costs_line and l.import_type
                )
                if landed_lines:
                    tax_lines = landed_lines.filtered(lambda l: l.import_type == "tax")
                    amount_untaxed += percentage * abs(sum(tax_lines.mapped("balance")))
                elif invoice.import_type == "tax":
                    amount_untaxed += percentage * getattr(invoice, invoice_field)

            line_taxes = sum(record.line_ids.mapped("price_import_tax"))
            if line_taxes:
                price_taxes = line_taxes
                if not amount_untaxed:
                    price_taxes_currency = record.action_currency_convert(line_taxes)
                else:
                    price_taxes_currency = abs(amount_untaxed)
            elif amount_untaxed:
                price_taxes = record.action_currency_company_convert(abs(amount_untaxed))
                price_taxes_currency = abs(amount_untaxed)
            else:
                price_taxes = 0.0
                price_taxes_currency = 0.0
            record.update({
                "price_taxes": price_taxes,
                "price_taxes_currency": price_taxes_currency,
            })

    @api.depends("manual_freight", "expense_freight")
    def _compute_price_freight(self):
        for record in self:
            price_freight = record.manual_freight or record.expense_freight
            record.update({"price_freight": price_freight})

    @api.depends("manual_insurance", "expense_insurance")
    def _compute_price_insurance(self):
        for record in self:
            price_insurance = record.manual_insurance or record.expense_insurance
            record.update({"price_insurance": price_insurance})

    @api.depends('line_ids.price_insurance_currency')
    def _compute_price_insurance_currency(self):
        for record in self:
            price_insurance_currency = sum(record.line_ids.mapped('price_insurance_currency'))
            record.update({'price_insurance_currency': price_insurance_currency})

    @api.depends(
        "line_ids.price_tariff",
        "invoices_ids",
        "invoices_ids.line_ids.is_landed_costs_line",
        "invoices_ids.line_ids.product_id",
        "price_cost",
    )
    def _compute_price_tariff(self):
        for record in self:
            line_tariff = sum(record.line_ids.mapped("price_tariff"))
            invoice_amount = record._get_tariff_invoice_amount()
            if line_tariff:
                price_tariff = line_tariff
                # Use exact COP from invoice to avoid round-trip conversion loss (COP→USD→COP)
                price_tariff_currency = abs(invoice_amount) if invoice_amount else record.action_currency_convert(line_tariff)
            elif invoice_amount:
                price_tariff = record.action_currency_company_convert(abs(invoice_amount))
                price_tariff_currency = abs(invoice_amount)
            else:
                price_tariff = 0.0
                price_tariff_currency = 0.0
            record.update({
                "price_tariff": price_tariff,
                "price_tariff_currency": price_tariff_currency,
            })

    @api.depends("line_ids.price_subtotal")
    def _compute_price_total(self):
        for record in self:
            price_subtotal = sum(record.line_ids.mapped("price_subtotal"))
            price_total = record.action_currency_convert(price_subtotal)
            record.update({"price_total": price_total})

    @api.depends("date_rate", "currency_id")
    def _compute_rate(self):
        for record in self:
            from_currency = record.company_currency_id
            to_currency = record.currency_id
            company = record.company_id
            date = record.date_rate or fields.Date.today()

            currencies = from_currency + to_currency
            currency_rates = currencies._get_rates(company, date)
            from_currency_rate = currency_rates.get(from_currency.id)
            to_currency_rate = currency_rates.get(to_currency.id)

            record.rate_currency = to_currency_rate / (from_currency_rate or 1)
            record.rate_inverse = from_currency_rate / (to_currency_rate or 1)

    def _compute_show_operations(self):
        for record in self:
            type_show_operations = self.env.user.has_group(
                "stock.group_production_lot, stock.group_stock_multi_locations, stock.group_tracking_lot"
            )
            if type_show_operations:
                record.show_operations = True
            else:
                record.show_operations = False

    @api.depends("pickings_ids")
    def _compute_picking_type_id(self):
        type_import = self.env.ref("purchase_import.type_import")
        for record in self:
            record.picking_type_id = (
                record.pickings_ids
                and record.pickings_ids[0].picking_type_id
                or type_import
            )

    @api.depends(
        "move_lines_ids",
        "picking_type_id.use_create_lots",
        "picking_type_id.use_existing_lots",
        "state",
    )
    def _compute_show_lots_text(self):
        group_production_lot_enabled = self.env.user.has_group(
            "stock.group_production_lot"
        )
        for record in self:
            if not record.move_lines_ids and not record.picking_type_id.use_create_lots:
                record.show_lots_text = False
            elif (
                group_production_lot_enabled
                and record.picking_type_id.use_create_lots
                and not record.picking_type_id.use_existing_lots
                and record.state != "done"
            ):
                record.show_lots_text = True
            else:
                record.show_lots_text = False

    @api.depends("purchases_ids")
    def _get_purchase_names(self):
        for record in self:
            record.purchase_names = ",".join(record.purchases_ids.mapped("name"))

    def action_draft(self):
        return self.write({"state": "draft"})

    def action_confirm(self):
        return self.write({"state": "confirm"})

    def action_validate(self):
        def fix_account_date():
            date_to_update = {"date": fields.Date.today()}
            moves_ids = self.mapped(
                "pickings_ids.move_ids.account_move_id"
            )
            moves_ids.write({"state": "draft"})
            moves_ids.write(date_to_update)
            for move in moves_ids:
                move.action_post()

        self.ensure_one()
        self.action_moves()
        self.action_lines()
        self = self.with_context(
            purchase_import_id=self.id,
            force_period_date=self.date_rate,
            from_import=True,
        )
        res = self.pickings_ids.button_validate()
        fix_account_date()
        return res

    def _compute_landed_costs_count(self):
        for record in self:
            if not isinstance(record.id, int):
                record.landed_costs_count = 0
                continue
            record.landed_costs_count = self.env["stock.landed.cost"].search_count(
                [("import_ids", "in", [record.id])]
            )

    def action_view_landed_costs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Costos de Destino",
            "res_model": "stock.landed.cost",
            "view_mode": "list,form",
            "domain": [("import_ids", "in", [self.id])],
            "context": {"default_import_ids": [(4, self.id)]},
        }

    def action_done(self):
        for record in self:
            # A move claimed before validation can be displaced into a new
            # backorder picking during that same validation (partial delivery).
            # Closing the import must not leave it holding a permanent claim
            # on a move that was never actually received here.
            pending = record.moves_ids.filtered(lambda m: m.state not in ("done", "cancel"))
            if pending:
                pending.write({"purchase_import_id": False})
                remaining = record.moves_ids - pending
                record.write({
                    "moves_ids": [(6, 0, remaining.ids)],
                    "move_lines_ids": [(6, 0, remaining.move_line_ids.ids)],
                    "pickings_ids": [(6, 0, remaining.picking_id.ids)],
                })
        return self.write({"state": "done"})

    def action_cancel(self):
        self.moves_ids.write({"purchase_import_id": False})
        return self.write({"state": "cancel"})

    def action_restore(self):
        for record in self:
            # Only reclaim moves nobody else has taken since the cancel (a new
            # import could have claimed the same picking/moves in the
            # meantime); those are left alone instead of being stolen back.
            reclaimable = record.moves_ids.filtered(
                lambda m: not m.purchase_import_id or m.purchase_import_id == record
            )
            reclaimable.write({"purchase_import_id": record.id})
        return self.write({"state": "draft"})

    def action_moves(self):
        for record in self:
            # Once closed, an import must not reclaim any move: recomputing
            # from purchases_ids/pickings_ids would pull in a backorder created
            # afterwards (e.g. the remaining, not-yet-received quantity), which
            # then becomes unreachable to any later import for that same move.
            if record.state in ("done", "cancel"):
                continue

            record.moves_ids.write({"purchase_import_id": False})

            if record.import_type == "purchase":
                picking_ids = record.purchases_ids.picking_ids

            if record.import_type == "picking":
                picking_ids = record.pickings_ids

            pickings = picking_ids.filtered(lambda p: p.state != "cancel")

            # Claim per move, not per picking: a single (backorder) picking can
            # hold both moves already claimed by another, still-valid import and
            # moves that are genuinely free, and only the free ones belong here.
            moves_ids = pickings.move_ids.filtered(
                lambda m: not m.purchase_import_id
                or m.purchase_import_id == record
                or m.purchase_import_id.state == "cancel"
            )
            moves_ids.write({"purchase_import_id": record.id})

            record.update(
                {
                    "move_is": True,
                    "moves_ids": [(6, 0, moves_ids.ids)],
                    "move_lines_ids": [(6, 0, moves_ids.move_line_ids.ids)],
                    "pickings_ids": [(6, 0, moves_ids.picking_id.ids)],
                }
            )

    def action_lines(self):
        self = self.with_company(self.company_id)
        for record in self:
            if record.move_is:
                record.line_ids.unlink()
                line_ids = record.prepare_line_ids()
                record.write({"line_ids": line_ids, "move_is": False})
            record.action_line_ids()

    def prepare_line_ids(self):
        self.ensure_one()

        def get_move_quantity_done(move_id):
            version = odoo.release.version_info[0]
            if version == 17:
                return move_id.quantity
            return move_id.quantity

        line_ids = []
        move_ids = self.moves_ids.filtered(lambda m: get_move_quantity_done(m))

        for move in move_ids:
            line = move.purchase_line_id
            product = move.product_id

            product_qty = get_move_quantity_done(move)

            if self.import_type == "purchase":
                price_unit = line.product_uom_id._compute_price(
                    line.price_unit, move.product_uom
                )

            else:
                price_move = move._get_price_unit()
                price_unit = self.action_currency_company_convert(price_move)

            price_cost = price_unit * product_qty

            vals = {
                "line_id": line and line.id or False,
                "move_id": move.id,
                "name": line and line.name or move.name,
                "partner_id": move.partner_id.id,
                "product_id": product.id,
                "product_qty": product_qty,
                "product_uom": move.product_uom.id,
                "product_weight": product_qty * product.weight,
                "product_volume": product_qty * product.volume,
                "price_unit": price_unit,
                "price_cost": price_cost,
            }
            line_ids.append((0, 0, vals))

        return line_ids

    def _get_tariff_invoice_amount(self):
        self.ensure_one()
        invoice_field = self.company_id.purchase_import_type
        invoice_amount = 0.0
        for invoice in self.invoices_ids:
            price_cost = sum(invoice.imports_ids.mapped("price_cost"))
            percentage = self.price_cost / (price_cost or self.price_cost or 1)
            landed_lines = invoice.line_ids.filtered(
                lambda l: l.is_landed_costs_line and l.import_type
            )
            if landed_lines:
                tariff_lines = landed_lines.filtered(lambda l: l.import_type == "tariff")
                invoice_amount += percentage * abs(sum(tariff_lines.mapped("balance")))
            elif invoice.import_type == "tariff":
                invoice_amount += percentage * getattr(invoice, invoice_field)
        return invoice_amount

    def _compute_delivery_ratio(self):
        self.ensure_one()
        delivered_cost = 0.0
        demanded_cost = 0.0
        for line in self.line_ids:
            move = line.move_id
            if not move:
                continue
            delivered_cost += line.price_unit * line.product_qty
            demanded_cost += line.price_unit * move.product_uom_qty
        if demanded_cost and delivered_cost < demanded_cost:
            return delivered_cost / demanded_cost
        return 1.0

    def action_line_ids(self):
        self.ensure_one()
        ratio = self._compute_delivery_ratio()
        self.action_line_price(ratio)
        self.action_line_tariff(ratio)
        self.action_line_total(ratio)

    # Price
    def action_line_price(self, delivery_ratio=1.0):
        lines_sum, line_field = self.prepare_percentage()
        total_insurance = self.price_insurance * delivery_ratio
        total_freight = self.price_freight * delivery_ratio
        for line in self.line_ids:
            product_tmpl = line.product_id.product_tmpl_id

            percentage = sum(line.mapped(line_field)) / lines_sum

            price_insurance = total_insurance * percentage
            price_freight = total_freight * percentage
            price_cif = line.price_cost + price_insurance + price_freight

            tariffes_ids = product_tmpl.get_tariff_ids(self.country_id)
            tariffes = tariffes_ids.compute_all(
                price_cif,
                currency=self.currency_id,
                quantity=1,
                product=line.product_id,
                partner=line.partner_id,
            )

            price_tariff = tariffes["total_included"] - tariffes["total_excluded"]

            line.write(
                {
                    "price_insurance": price_insurance,
                    "price_freight": price_freight,
                    "price_cif": price_cif,
                    "tariffes_ids": [(6, 0, tariffes_ids.ids)],
                    "price_tariff": price_tariff,
                }
            )

    # Tarrif
    def action_line_tariff(self, delivery_ratio=1.0):
        invoice_amount = self._get_tariff_invoice_amount()
        if not invoice_amount:
            return
        total_tariff = self.action_currency_company_convert(abs(invoice_amount)) * delivery_ratio
        total_tariff_currency = abs(invoice_amount) * delivery_ratio
        lines_sum, line_field = self.prepare_percentage()
        for line in self.line_ids:
            percentage = sum(line.mapped(line_field)) / lines_sum
            line.write(
                {
                    "price_tariff": total_tariff * percentage,
                    "price_tariff_currency": total_tariff_currency * percentage,
                }
            )

    # Total
    def action_line_total(self, delivery_ratio=1.0):
        lines_sum, line_field = self.prepare_percentage()
        total_expenses = self.price_expenses * delivery_ratio
        total_expenses_currency = self.price_expenses_currency * delivery_ratio
        total_taxes = self.price_taxes * delivery_ratio
        for line in self.line_ids:
            product_tmpl = line.product_id.product_tmpl_id

            percentage = sum(line.mapped(line_field)) / lines_sum

            price_insurance = line.price_insurance
            price_freight = line.price_freight
            price_cif = line.price_cif
            price_tariff = line.price_tariff

            supplier_taxes_id = product_tmpl.supplier_taxes_id
            taxes_ids = line.partner_id.property_account_position_id.map_tax(
                supplier_taxes_id
            )
            taxes = taxes_ids.compute_all(
                price_cif + price_tariff,
                currency=self.currency_id,
                quantity=1,
                product=line.product_id,
                partner=line.partner_id,
            )

            price_tax = taxes["total_included"] - taxes["total_excluded"]

            price_expense = total_expenses * percentage
            price_expenses_currency = total_expenses_currency * percentage
            price_import_tax = total_taxes * percentage

            price_subtotal = (
                price_insurance + price_freight + price_tariff + price_expense + price_import_tax
            )
            price_total = price_subtotal + line.price_cost
            price_total_unit = price_total / line.product_qty

            line.write(
                {
                    "taxes_ids": [(6, 0, taxes_ids.ids)],
                    "price_tax": price_tax,
                    "price_expense": price_expense,
                    "price_expense_currency": price_expenses_currency,
                    "price_import_tax": price_import_tax,
                    "price_subtotal": price_subtotal,
                    "price_total": price_total,
                    "price_total_unit": price_total_unit,
                }
            )

    def prepare_percentage(self):
        self.ensure_one()
        line_field = COST_DICT.get(self.cost_type)
        lines_sum = sum(self.line_ids.mapped(line_field))
        if not lines_sum:
            raise ValidationError(_("Please modify cost method"))
        return lines_sum, line_field

    def action_cost(self):
        self.ensure_one()
        cost = self.prepare_cost()
        return self.write(
            {"cost_id": cost and cost.id or False, "price_expense": self.price_expenses}
        )

    def prepare_cost(self):
        self.ensure_one()
        Cost = self.env["stock.landed.cost"]
        cost_lines = self.prepare_cost_lines()
        if not cost_lines:
            return False
        vals = {
            "picking_ids": [(6, 0, self.pickings_ids.ids)],
            "cost_lines": cost_lines,
        }
        cost = Cost.create(vals)
        cost.compute_landed_cost()
        cost.button_validate()
        cost.write({"import_is": True})
        return cost

    def prepare_cost_lines(self):
        # TODO
        # Crear confoguracion para preguntar si se agrupan en subtotal o separado
        # stock.landed.line.move, line_move_ids
        self.ensure_one()
        lines = []

        # Insurance
        if self.price_insurance:
            product = self.env.ref("purchase_import.product_import_insurance")
            if self.manual_insurance:
                partner = self.partner_id
                price = self.action_currency_convert(self.price_insurance)
                vals = self.prepare_cost_line(partner, product, price, "price_insurance_currency")
                lines.append((0, 0, vals))
            else:
                invoice_field = self.company_id.purchase_import_type
                partner_amounts = {}
                for invoice in self.invoices_ids:
                    landed_lines = invoice.line_ids.filtered(
                        lambda l: l.is_landed_costs_line and l.import_type == "insurance"
                    )
                    if landed_lines:
                        inv_amount = abs(sum(landed_lines.mapped("balance")))
                    elif invoice.import_type == "insurance":
                        inv_amount = abs(getattr(invoice, invoice_field))
                    else:
                        continue
                    partner_amounts[invoice.partner_id] = (
                        partner_amounts.get(invoice.partner_id, 0.0) + inv_amount
                    )
                for partner, price in partner_amounts.items():
                    vals = self.prepare_cost_line(partner, product, price, "price_insurance_currency")
                    lines.append((0, 0, vals))

        # Freight
        if self.price_freight:
            product = self.env.ref("purchase_import.product_import_freight")
            if self.company_id.purchase_import_freight == "invoice":
                invoice_field = self.company_id.purchase_import_type
                partner_amounts = {}
                for invoice in self.invoices_ids:
                    landed_lines = invoice.line_ids.filtered(
                        lambda l: l.is_landed_costs_line and l.import_type == "freight"
                    )
                    if landed_lines:
                        inv_amount = abs(sum(landed_lines.mapped("balance")))
                    elif invoice.import_type == "freight":
                        inv_amount = abs(getattr(invoice, invoice_field))
                    else:
                        continue
                    partner_amounts[invoice.partner_id] = (
                        partner_amounts.get(invoice.partner_id, 0.0) + inv_amount
                    )
                for partner, price in partner_amounts.items():
                    vals = self.prepare_cost_line(partner, product, price, "price_freight_currency")
                    lines.append((0, 0, vals))
            else:
                partner = self.partner_id
                price = self.action_currency_convert(self.price_freight)
                vals = self.prepare_cost_line(partner, product, price, "price_freight_currency")
                lines.append((0, 0, vals))

        # Tariff
        # TODO
        # Crear una condicione en la compañia para preguntar
        if self.price_tariff:
            partner = self.env.ref("purchase_import.partner_import_dian")
            product = self.env.ref("purchase_import.product_import_tariff")
            price = self.action_currency_convert(self.price_tariff)
            vals = self.prepare_cost_line(
                partner, product, price, "price_tariff_currency"
            )
            lines.append((0, 0, vals))

        # Expense
        if self.price_expenses:
            product = self.env.ref("purchase_import.product_import_expense")
            invoice_field = self.company_id.purchase_import_type
            partner_amounts = {}
            for invoice in self.invoices_ids:
                landed_lines = invoice.line_ids.filtered(
                    lambda l: l.is_landed_costs_line and l.import_type == "expense"
                )
                if landed_lines:
                    inv_amount = abs(sum(landed_lines.mapped("balance")))
                elif invoice.import_type == "expense":
                    inv_amount = abs(getattr(invoice, invoice_field))
                else:
                    continue
                partner_amounts[invoice.partner_id] = (
                    partner_amounts.get(invoice.partner_id, 0.0) + inv_amount
                )
            for partner, price in partner_amounts.items():
                vals = self.prepare_cost_line(partner, product, price, "price_expense_currency")
                lines.append((0, 0, vals))

        return lines

    def prepare_cost_line(self, partner, product, price, cfield):
        self.ensure_one()
        accounts = product.product_tmpl_id.get_product_accounts()
        account_id = accounts.get("expense") and accounts["expense"].id or False
        vals = {
            "partner_id": partner.id,
            "product_id": product.id,
            "name": product.name,
            "account_id": account_id,
            "split_method": self.cost_type,
            "price_unit": price,
            "line_move_ids": self.prepare_line_move(price, cfield=cfield),
        }
        return vals

    def prepare_line_move(self, price, cfield=False):
        self.ensure_one()

        line_move_ids = []
        if not cfield:
            return line_move_ids

        total = getattr(self, cfield)

        for line in self.line_ids:
            if not getattr(line, cfield):
                continue
            cost = getattr(line, cfield)
            per = cost / total
            vals = {"move_id": line.move_id.id, "cost": price * per}
            line_move_ids.append((0, 0, vals))
        return line_move_ids

    def action_invoice(self):
        self.ensure_one()
        invoices = []

        if self.company_id.purchase_import_tax:
            invoice_tax = self.prepare_invoice()
            if invoice_tax:
                invoices.append(invoice_tax.id)

        if self.import_type == "purchase":
            purchases_ids = self.purchases_ids.filtered(
                lambda p: p.invoice_status == "to invoice"
            )
            if purchases_ids:
                purchase_act = purchases_ids.action_create_invoice()
                if purchase_act.get("res_id"):
                    invoices.append(purchase_act["res_id"])
                else:
                    invoices = purchase_act["domain"][0][2]

        return self.write({"invoices_ids": [(4, invoice, 0) for invoice in invoices]})

    def prepare_invoice(self):
        self.ensure_one()
        Move = self.env["account.move"]
        invoice_line_ids = self.prepare_invoice_lines()

        if not invoice_line_ids:
            return False

        vals = {"move_type": "in_invoice", "invoice_line_ids": invoice_line_ids}
        return Move.create(vals)

    def prepare_invoice_lines(self):
        self.ensure_one()
        lines = []

        # product_tariff = self.env.ref('purchase_import.product_import_tariff')
        product_tariff = 0
        product_tax = self.env.ref("purchase_import.product_import_tax")

        price_tariff = sum(self.line_ids.mapped("price_tariff"))
        price_tax = sum(self.line_ids.mapped("price_tax"))

        if price_tariff:
            vals = self.prepare_invoice_line(product_tariff, price_tariff)
            lines.append((0, 0, vals))

        if price_tax:
            vals = self.prepare_invoice_line(product_tax, price_tax)
            lines.append((0, 0, vals))

        return lines

    def prepare_invoice_line(self, product, price):
        price_unit = self.action_currency_convert(price)
        vals = {
            "product_id": product.id,
            "name": product.name,
            "quantity": 1,
            "price_unit": price_unit,
        }
        return vals

    def action_currency_convert(self, amount):
        self.ensure_one()
        return self.currency_id._convert(
            amount,
            self.company_currency_id,
            self.company_id,
            self.date_rate or fields.Date.today(),
            False
        )

    def action_currency_company_convert(self, amount):
        self.ensure_one()
        return self.company_currency_id._convert(
            amount,
            self.currency_id,
            self.company_id,
            self.date_rate or fields.Date.today(),
            False
        )



class PurchaseImportLine(models.Model):
    _name = "purchase.import.line"
    _description = "Purchase import line"

    company_currency_id = fields.Many2one(related="import_id.company_currency_id")

    currency_id = fields.Many2one(related="import_id.currency_id")

    import_id = fields.Many2one(
        comodel_name="purchase.import", ondelete="cascade", required=True
    )

    line_id = fields.Many2one("purchase.order.line")

    move_id = fields.Many2one("stock.move")

    name = fields.Char(required=True)

    # Partner
    partner_id = fields.Many2one("res.partner")

    # Price
    price_cif = fields.Monetary("CIF")
    price_cif_currency = fields.Monetary(
        string="Currency CIF",
        compute="_compute_price_currency",
        currency_field="company_currency_id",
    )
    price_cost = fields.Monetary("Cost")
    price_cost_currency = fields.Monetary(
        string="Currency Cost",
        compute="_compute_price_currency",
        currency_field="company_currency_id",
    )
    price_expense = fields.Monetary("Expense")
    price_expense_currency = fields.Monetary(
        string="Currency Expense",
        compute="_compute_price_currency",
        currency_field="company_currency_id",
    )
    price_freight = fields.Float("Freight")
    price_freight_currency = fields.Monetary(
        string="Currency Freight",
        compute="_compute_price_currency",
        currency_field="company_currency_id",
    )
    price_import_tax = fields.Monetary("Taxes")
    price_import_tax_currency = fields.Monetary(
        string="Currency Import Tax",
        compute="_compute_price_currency",
        currency_field="company_currency_id",
    )
    price_insurance = fields.Monetary("Insurance")
    price_insurance_currency = fields.Monetary(
        string="Currency Insurance",
        compute="_compute_price_currency",
        currency_field="company_currency_id",
    )
    price_subtotal = fields.Monetary("Subtotal")
    price_subtotal_currency = fields.Monetary(
        string="Currency Subtotal",
        compute="_compute_price_currency",
        currency_field="company_currency_id",
    )
    price_tariff = fields.Monetary("Tariff")
    price_tariff_currency = fields.Monetary(
        string="Currency Tariff",
        compute="_compute_price_currency",
        currency_field="company_currency_id",
    )
    price_tax = fields.Monetary("Tax")
    price_tax_currency = fields.Monetary(
        string="Currency Tax",
        compute="_compute_price_currency",
        currency_field="company_currency_id",
    )
    price_total = fields.Monetary("Total")
    price_total_currency = fields.Monetary(
        string="Currency Total",
        compute="_compute_price_currency",
        currency_field="company_currency_id",
    )
    price_total_unit = fields.Monetary("Unit Total")
    price_total_unit_currency = fields.Monetary(
        string="Currency Unit Total",
        compute="_compute_price_currency",
        currency_field="company_currency_id",
    )
    price_unit = fields.Monetary("Price")
    price_unit_currency = fields.Monetary(
        string="Currency Price",
        compute="_compute_price_currency",
        currency_field="company_currency_id",
    )

    # Product
    product_equal = fields.Float(
        string="Equal",
        default=1,
    )
    product_id = fields.Many2one(comodel_name="product.product", required=True)
    product_qty = fields.Float(
        string="Quantity", digits="Product Unit of Measure", required=True
    )
    product_uom = fields.Many2one(comodel_name="uom.uom", string="UoM")
    product_volume = fields.Float(
        string="Volume",
        digits="Volume",
    )
    product_weight = fields.Float(
        string="Weight",
        digits="Stock Weight",
    )

    tariffes_ids = fields.Many2many(
        comodel_name="account.tax",
        relation="line_tarrif_rel",
        column1="line_id",
        column2="tax_id",
        string="Tariffes",
    )

    taxes_ids = fields.Many2many(
        comodel_name="account.tax",
        relation="line_tax_rel",
        column1="line_id",
        column2="tax_id",
        string="Taxes",
    )

    @api.depends(
        "currency_id",
        "company_currency_id",
        "import_id.date_rate",
        "import_id.price_tariff_currency",
        "import_id.price_taxes_currency",
        "import_id.price_expenses_currency",
        "import_id.expense_insurance_currency",
        "import_id.expense_freight_currency",
        "price_subtotal",
    )
    def _compute_price_currency(self):
        for line in self:
            price_unit = line.action_currency_convert(line.price_unit)
            price_cost = line.action_currency_convert(line.price_cost)
            price_tax = line.action_currency_convert(line.price_tax)

            # Distribute header's exact COP proportionally to avoid COP→USD→COP round-trip precision loss
            def _prop(line_usd, header_cop, all_lines_usd):
                if all_lines_usd and header_cop:
                    return header_cop * (line_usd / all_lines_usd)
                return line.action_currency_convert(line_usd)

            all_tariff = sum(line.import_id.line_ids.mapped("price_tariff"))
            all_taxes = sum(line.import_id.line_ids.mapped("price_import_tax"))
            all_expense = sum(line.import_id.line_ids.mapped("price_expense"))
            all_insurance = sum(line.import_id.line_ids.mapped("price_insurance"))
            all_freight = sum(line.import_id.line_ids.mapped("price_freight"))

            price_tariff = _prop(line.price_tariff, line.import_id.price_tariff_currency, all_tariff)
            price_import_tax = _prop(line.price_import_tax, line.import_id.price_taxes_currency, all_taxes)
            price_expense = _prop(line.price_expense, line.import_id.price_expenses_currency, all_expense)
            price_insurance = _prop(line.price_insurance, line.import_id.expense_insurance_currency, all_insurance)
            price_freight = _prop(line.price_freight, line.import_id.expense_freight_currency, all_freight)

            # CIF, subtotal and total in company currency must be the sum of their
            # already-correct components, not an independent re-conversion of the
            # foreign-currency total (which can use a different implied rate and
            # silently drift from the real invoiced amounts).
            price_cif = price_cost + price_insurance + price_freight
            price_subtotal = (
                price_insurance + price_freight + price_tariff + price_import_tax + price_expense
            )
            price_total = price_subtotal + price_cost
            price_total_unit = price_total / line.product_qty

            line.price_unit_currency = price_unit
            line.price_cost_currency = price_cost
            line.price_import_tax_currency = price_import_tax
            line.price_insurance_currency = price_insurance
            line.price_freight_currency = price_freight
            line.price_cif_currency = price_cif
            line.price_tariff_currency = price_tariff
            line.price_tax_currency = price_tax
            line.price_expense_currency = price_expense
            line.price_subtotal_currency = price_subtotal
            line.price_total_currency = price_total
            line.price_total_unit_currency = price_total_unit

    def action_currency_convert(self, amount):
        self.ensure_one()
        date_currency = self.import_id.date_rate or fields.Date.today()
        if self.env.context.get("date_currency"):
            date_currency = self.env.context.get("date_currency")
        return self.currency_id._convert(
            amount, 
            self.company_currency_id, 
            self.import_id.company_id, 
            date_currency,
            False
        )
