# -*- coding: utf-8 -*-
from odoo import models, _
from odoo.exceptions import UserError
from odoo.tools import str2bool

from .res_config_settings import ALLOW_BILLING_WITHOUT_PORTAL_PARAM


class FeeSlip(models.Model):
    """Recibo de tarifas.

    Tarea 11292: el aviso de "sin acceso al portal" se construye con una
    f-string dentro de ``_()``, por lo que no se puede traducir desde un .po.
    Se valida antes de llamar a ``super()`` con el mismo criterio de Webkul
    (``_has_fee_portal_access``): cuando el estudiante no tiene acceso, el
    mensaje sale en espanol y el metodo original nunca llega a ejecutarse;
    cuando lo tiene, la validacion de Webkul pasa igual que siempre.

    Tarea 11293: cuando la institucion no usa el portal de Odoo, el parametro
    de configuracion neutraliza esa exigencia. Se hace en el propio
    ``_has_fee_portal_access`` para que tanto la validacion de arriba como el
    ``raise`` original de Webkul queden cubiertos con un solo punto de cambio.
    El resto del flujo de facturacion no se toca: ``_get_fee_invoice_partner``
    ya prefiere el contacto del estudiante, asi que la factura se genera sin
    usuario de portal y nada crea usuarios automaticamente.
    """

    _inherit = 'wk.fee.slip'

    def _allow_billing_without_portal_user(self):
        """Indica si se puede facturar sin usuario del portal."""
        param = self.env['ir.config_parameter'].sudo().get_param(
            ALLOW_BILLING_WITHOUT_PORTAL_PARAM, 'False')
        return str2bool(param, False)

    def _has_fee_portal_access(self, student):
        if self._allow_billing_without_portal_user():
            return True
        return super()._has_fee_portal_access(student)

    def confirm_fee_slip(self):
        for slip in self:
            if not self._has_fee_portal_access(slip.student_id):
                raise UserError(_(
                    "The student %(student)s does not have any portal access "
                    "(student or parent). Please provide portal access to "
                    "proceed!",
                    student=slip.student_id.name,
                ))
        return super().confirm_fee_slip()
