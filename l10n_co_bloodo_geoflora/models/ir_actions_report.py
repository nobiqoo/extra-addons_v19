# -*- coding: utf-8 -*-
from collections import OrderedDict

from odoo import models

RG_REPORT_NAME = 'l10n_co_bloodo.report_account_move_einvoicing_document'


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _get_rg_langs(self, report_ref, res_ids):
        """Idioma de RG de cada factura, o None si no es el reporte de FE."""
        if not res_ids or self._get_report(report_ref).report_name != RG_REPORT_NAME:
            return None
        moves = self.env['account.move'].browse(res_ids).exists()
        return {move.id: move._get_rg_lang() for move in moves}

    def _render_qweb_html(self, report_ref, docids, data=None):
        # La RG se renderiza en el idioma del cliente (textos de la plantilla,
        # campos traducibles y formato de fechas y números).
        report = self
        langs = self._get_rg_langs(report_ref, docids)
        if langs and len(set(langs.values())) == 1:
            report = self.with_context(lang=next(iter(langs.values())))
        return super(IrActionsReport, report)._render_qweb_html(report_ref, docids, data=data)

    def _render_qweb_pdf_prepare_streams(self, report_ref, data, res_ids=None):
        langs = self._get_rg_langs(report_ref, res_ids)
        if (not langs or len(set(langs.values())) == 1
                or len(res_ids) != len(set(res_ids))):
            return super()._render_qweb_pdf_prepare_streams(report_ref, data, res_ids=res_ids)
        # Facturas de clientes con idiomas distintos: cada una por separado.
        collected_streams = OrderedDict()
        for res_id in res_ids:
            collected_streams.update(super()._render_qweb_pdf_prepare_streams(
                report_ref, dict(data or {}), res_ids=[res_id]))
        return collected_streams
