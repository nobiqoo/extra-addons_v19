# -*- coding: utf-8 -*-

import logging

from odoo import api, models
from odoo.exceptions import AccessError


_logger = logging.getLogger(__name__)


class AccountReport(models.Model):
    _inherit = "account.report"

    def _with_safe_company_context(self):
        requested_company_ids = self.env.context.get("allowed_company_ids")
        if not requested_company_ids:
            return self

        authorized_company_ids = set(self.env.user._get_company_ids())
        safe_company_ids = [
            company_id
            for company_id in requested_company_ids
            if company_id in authorized_company_ids
        ]

        if not safe_company_ids:
            _logger.warning(
                "Contexto de compañías inválido para el usuario %s: %s",
                self.env.user.id,
                requested_company_ids,
            )
            raise AccessError(
                "No hay empresas autorizadas en el contexto del reporte."
            )

        if set(safe_company_ids) != set(requested_company_ids):
            _logger.warning(
                "Se corrigió el contexto de compañías para el usuario %s: "
                "%s -> %s",
                self.env.user.id,
                requested_company_ids,
                safe_company_ids,
            )
            return self.with_context(allowed_company_ids=safe_company_ids)

        return self

    def _with_safe_report_options(self, options):
        if not options or "companies" not in options:
            return options

        authorized_company_ids = set(self.env.user._get_company_ids())
        safe_companies = [
            company
            for company in options["companies"]
            if company.get("id") in authorized_company_ids
        ]

        if not safe_companies:
            raise AccessError(
                "No hay empresas autorizadas en las opciones del reporte."
            )

        if len(safe_companies) != len(options["companies"]):
            _logger.warning(
                "Se corrigieron las compañías de las opciones del reporte "
                "para el usuario %s: %s -> %s",
                self.env.user.id,
                [company.get("id") for company in options["companies"]],
                [company.get("id") for company in safe_companies],
            )
            options = dict(options)
            options["companies"] = safe_companies

        return options

    @api.readonly
    def get_options(self, previous_options=None):
        self = self._with_safe_company_context()
        previous_options = self._with_safe_report_options(previous_options)
        return super().get_options(previous_options)

    def get_report_information(self, options):
        self = self._with_safe_company_context()
        options = self._with_safe_report_options(options)
        return super().get_report_information(options)

    @api.readonly
    def get_report_information_readonly(self, options):
        self = self._with_safe_company_context()
        options = self._with_safe_report_options(options)
        return super().get_report_information_readonly(options)


class AgedPayableReportHandler(models.AbstractModel):
    _inherit = "account.aged.payable.report.handler"

    def _custom_line_postprocessor(self, report, options, lines):
        partner_lines_map = {}

        for line in lines:
            model, model_id = report._get_model_info_from_id(line["id"])
            if model == "res.partner":
                partner_lines_map[model_id] = line

        if partner_lines_map:
            authorized_company_ids = set(self.env.user._get_company_ids())
            authorized_company = self.env.company
            for partner, line_dict in zip(
                self.env["res.partner"].browse(partner_lines_map),
                partner_lines_map.values(),
            ):
                partner_company = partner.company_id
                company = (
                    partner_company
                    if partner_company.id in authorized_company_ids
                    else authorized_company
                )
                line_dict["trust"] = partner.with_company(company).trust

        return lines
