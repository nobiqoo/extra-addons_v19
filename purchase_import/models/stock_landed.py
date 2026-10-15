# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import api, fields, models, tools


class StockLandedCost(models.Model):
    _inherit = "stock.landed.cost"

    import_is = fields.Boolean(
        string="Is Import?",
        default=False,
        copy=False,
    )
    import_ids = fields.Many2many(
        comodel_name="purchase.import",
        string="Importaciones",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("vendor_bill_id") and not vals.get("import_ids"):
                bill = self.env["account.move"].browse(vals["vendor_bill_id"])
                if bill.import_id:
                    vals["import_ids"] = [(4, bill.import_id.id)]
        return super().create(vals_list)

    @api.onchange("vendor_bill_id")
    def _onchange_vendor_bill_id_import(self):
        if self.vendor_bill_id and self.vendor_bill_id.import_id:
            self.import_ids |= self.vendor_bill_id.import_id

    def compute_landed_cost(self):
        res = super(StockLandedCost, self).compute_landed_cost()
        for record in self:
            if not record.cost_lines.line_move_ids:
                continue

            rounding = record.currency_id.rounding

            lines = record.cost_lines.line_move_ids

            value_split = 0.0

            for line in record.valuation_adjustment_lines:
                line_move = lines.filtered(
                    lambda l: l.cost_line_id.id == line.cost_line_id.id
                    and l.move_id.id == line.move_id.id
                )
                value = line_move and line_move.cost or 0.0

                if rounding:
                    value = tools.float_round(
                        value, precision_rounding=rounding, rounding_method="HALF-UP"
                    )
                value_split += value

                line.write({"additional_landed_cost": value})

            record.valuation_adjustment_lines.filtered(
                lambda v: not v.additional_landed_cost
            ).unlink()

            total_amount = sum(record.valuation_adjustment_lines.mapped('additional_landed_cost'))
            if not record.currency_id.is_zero(total_amount - record.amount_total):
                rounding_diff = total_amount - record.amount_total
                line = record.valuation_adjustment_lines[-1]
                line.additional_landed_cost -= rounding_diff

            val_to_cost_lines = defaultdict(lambda: 0.0)
            for val_line in record.valuation_adjustment_lines:
                val_to_cost_lines[val_line.cost_line_id] += val_line.additional_landed_cost
            for cost_line, val_amount in val_to_cost_lines.items():
                if not record.currency_id.is_zero(cost_line.price_unit - val_amount):
                    cost_line.price_unit -= cost_line.price_unit - val_amount
        return res


class StockLandedCostLines(models.Model):
    _inherit = "stock.landed.cost.lines"

    line_move_ids = fields.One2many(
        comodel_name="stock.landed.line.move", inverse_name="cost_line_id"
    )

    partner_id = fields.Many2one(comodel_name="res.partner", copy=False)


class StockLandedLineMove(models.Model):
    _name = "stock.landed.line.move"
    _description = "Stock Landed Line Move"

    cost = fields.Float()
    cost_line_id = fields.Many2one(
        comodel_name="stock.landed.cost.lines", string="Cost Line", required=True
    )

    move_id = fields.Many2one(
        comodel_name="stock.move", string="Stock Move", required=True
    )


class StockValuationAdjustmentLines(models.Model):
    _inherit = "stock.valuation.adjustment.lines"

    partner_id = fields.Many2one(related="cost_line_id.partner_id", readonly=True)

    def _create_account_move_line(
        self, credit_account_id, debit_account_id, remaining_qty
    ):
        lines = super()._create_account_move_line(
            credit_account_id, debit_account_id, remaining_qty
        )
        if self.partner_id:
            for line in lines:
                line[2].update({"partner_id": self.partner_id.id})
        return lines
