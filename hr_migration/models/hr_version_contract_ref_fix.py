# -*- coding: utf-8 -*-

from odoo import models
import logging

_logger = logging.getLogger(__name__)


class HrVersionContractRefFix(models.AbstractModel):
    _name = "hr.version.contract.ref.fix"
    _description = "HR Version/Contract Ref Fix"

    # Registros de hr_payroll_co que guardan un model_id hacia hr.contract y
    # viven en un bloque noupdate, así que un upgrade no los reescribe desde
    # el XML: el upgrade a 19.0 renombró esa fila vieja de ir_model (compartida
    # hasta la 18.0 por el core y por hr_payroll_co) a hr.version, y estos tres
    # se quedaron apuntando ahí en vez de a la fila nueva de hr.contract.
    STALE_XMLIDS = [
        'hr_payroll_co.cron_update_days_left',
        'hr_payroll_co.cron_update_holiday_lines',
        'hr_payroll_co.hr_contract_rule',
    ]

    def run_fix(self):
        _logger.warning("START hr.version -> hr.contract ref fix")

        model = self.env.ref('hr_payroll_co.model_hr_contract', raise_if_not_found=False)
        if not model or model.model != 'hr.contract':
            _logger.warning(
                "hr_payroll_co.model_hr_contract no resuelve a hr.contract, no se reapunta nada")
            return

        for xmlid in self.STALE_XMLIDS:
            record = self.env.ref(xmlid, raise_if_not_found=False)
            if not record:
                _logger.warning("%s no existe, se omite", xmlid)
                continue
            if record.model_id == model:
                _logger.warning("%s ya apunta a hr.contract, no se toca", xmlid)
                continue
            old_model = record.model_id.model
            record.model_id = model
            _logger.warning("%s apuntaba a %s, se reapunta a hr.contract", xmlid, old_model)

        _logger.warning("FINISHED hr.version -> hr.contract ref fix")
