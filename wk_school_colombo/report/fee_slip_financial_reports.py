# -*- coding: utf-8 -*-
"""Reportes xlsx de "Informes → Recibos de cobro" (tareas 12447 y 12450).

Expuestos vía ``ir.actions.report`` (``binding_type='report'``) sobre
``wk.fee.slip``, por lo que aparecen en el menú Imprimir nativo
-engranaje ⚙ de la lista, sobre la selección del usuario- en vez de
botones propios en la barra de herramientas. La hoja de cálculo la
construye el propio ``wk.fee.slip`` (incluye el control de acceso y de
selección); aquí solo se delega.
"""
from odoo import models


class ReportFeeSlipConsecutivos(models.AbstractModel):
    _name = 'report.wk_school_colombo.report_fee_slip_consecutivos'
    _description = "Reporte de Consecutivos (xlsx)"
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, objs):
        objs._wk_build_consecutivos_workbook(workbook)


class ReportFeeSlipClientes(models.AbstractModel):
    _name = 'report.wk_school_colombo.report_fee_slip_clientes'
    _description = "Reporte Financiero – Clientes / Matrículas (xlsx)"
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, objs):
        objs._wk_build_reporte_clientes_workbook(workbook)


class ReportFeeSlipBeneficios(models.AbstractModel):
    _name = 'report.wk_school_colombo.report_fee_slip_beneficios'
    _description = "Reporte Financiero – Beneficios / Matrículas (xlsx)"
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, objs):
        objs._wk_build_reporte_beneficios_workbook(workbook)


class ReportFeeSlipFormasPago(models.AbstractModel):
    _name = 'report.wk_school_colombo.report_fee_slip_formas_pago'
    _description = "Reporte Financiero – Formas de Pago / Matrículas (xlsx)"
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, objs):
        objs._wk_build_reporte_formas_pago_workbook(workbook)
