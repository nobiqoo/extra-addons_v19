# -*- coding: utf-8 -*-

from odoo import models


class L10nCoReportHandler(models.AbstractModel):
    _inherit = 'l10n_co.report.handler'

    # Código DIAN del tributo que separa un certificado de otro. Los informes
    # nativos lo leen de l10n_co_edi_type y, sin ese módulo, no filtran nada:
    # aquí la clasificación llega desde l10n_co_data_bloodo.
    _dian_tax_code = False

    def _get_domain(self, report, options, line_dict_id=None):
        domain = super()._get_domain(report, options, line_dict_id=line_dict_id)
        if self._dian_tax_code and 'l10n_co_edi_type' not in self.env['account.tax']._fields:
            domain += [('tax_line_id.dian_tax_type_id.dian_code', '=', self._dian_tax_code)]
        return domain


class L10nCoIvaReportHandler(models.AbstractModel):
    _inherit = 'l10n_co.iva.report.handler'

    _dian_tax_code = '05'


class L10nCoFuenteReportHandler(models.AbstractModel):
    _inherit = 'l10n_co.fuente.report.handler'

    _dian_tax_code = '06'


class L10nCoIcaReportHandler(models.AbstractModel):
    _inherit = 'l10n_co.ica.report.handler'

    _dian_tax_code = '07'
