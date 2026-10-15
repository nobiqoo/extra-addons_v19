# -*- coding: utf-8 -*-

from odoo import models

line_ids = (
    ["product_id", "Producto", "many2one"],
    ["name", "Nombre", "caracter"],
    ["product_qty", "Cantidad", "flotante"],
    ["product_uom", "UdM", "many2one"],
    ["product_weight", "Peso", "flotante"],
    ["product_volume", "Volumen", "flotante"],
    ["price_unit", "Precio", "monetario"],
    ["price_unit_currency", "Precio en moneda", "monetario"],
    ["price_cost", "Costo", "monetario"],
    ["price_cost_currency", "Costo en moneda", "monetario"],
    ["price_insurance", "Seguro", "monetario"],
    ["price_insurance_currency", "Seguro en moneda", "monetario"],
    ["price_freight", "Flete", "monetario"],
    ["price_freight_currency", "Flete en moneda", "monetario"],
    ["price_cif", "CIF", "monetario"],
    ["price_cif_currency", "CIF en moneda", "monetario"],
    ["tariffes_ids", "Aranceles", "many2many"],
    ["price_tariff", "Arancel", "monetario"],
    ["price_tariff_currency", "Arancel en moneda", "monetario"],
    ["taxes_ids", "Impuestos", "many2many"],
    ["price_tax", "Impuesto", "monetario"],
    ["price_tax_currency", "Impuesto en moneda", "monetario"],
    ["price_expense", "Gasto", "monetario"],
    ["price_expense_currency", "Gasto en moneda", "monetario"],
    ["price_subtotal", "Subtotal", "monetario"],
    ["price_subtotal_currency", "Subtotal en moneda", "monetario"],
    ["price_total", "Total", "monetario"],
    ["price_total_currency", "Total en moneda", "monetario"],
    ["price_total_unit", "Total unitario", "monetario"],
    ["price_total_unit_currency", "Total unitario en moneda", "monetario"],
)


class ReportPurchaseImport(models.AbstractModel):
    _name = "report.purchase_import.report_purchase_import"
    _inherit = "report.report_xlsx.abstract"

    def generate_xlsx_report(self, workbook, data, objs):
        for obj in objs:
            # Create a worksheet.
            worksheet = workbook.add_worksheet(obj.name)

            # Add a bold format to use to highlight cells.
            bold = workbook.add_format({"bold": True})
            monetario = workbook.add_format({"num_format": "$#,##0"})

            # Titulos
            col = 0
            for campo, nombre, tipo in line_ids:
                worksheet.write(0, col, nombre, bold)
                col += 1

            # Iterate over the data and write it out row by row.
            formula = {}
            row = 0
            for line in obj.line_ids:
                row += 1
                col = 0
                for campo, nombre, tipo in line_ids:
                    valor = getattr(line, campo)

                    if tipo == "many2one":
                        valor = valor.name

                    if tipo == "many2many":
                        valor = ",".join(v.name for v in valor)

                    if tipo == "monetario":
                        worksheet.write(row, col, valor, monetario)

                    else:
                        worksheet.write(row, col, valor)

                    if tipo in ["flotante", "monetario"]:
                        formula.update({campo: formula.get(campo, 0) + valor})

                    col += 1

            row += 1
            col = 0
            for campo, nombre, tipo in line_ids:
                if tipo in ["flotante", "monetario"]:
                    if tipo == "monetario":
                        worksheet.write(row, col, formula.get(campo), monetario)
                    else:
                        worksheet.write(row, col, formula.get(campo))
                col += 1
