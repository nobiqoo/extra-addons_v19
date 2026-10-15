# -*- coding: utf-8 -*-
from odoo import api, models, fields
from odoo.tools import str2bool

# Parametro que habilita el cierre de clases el mismo dia de su finalizacion.
# Si nunca se ha guardado (instalacion nueva) se asume activo.
ALLOW_SAME_DAY_PARAM = 'wk_school_colombo.allow_same_day_class_completion'

# Parametros de la tarea 11293. A diferencia del anterior, ambos se asumen
# INACTIVOS cuando nunca se han guardado, para conservar el comportamiento
# estandar del modulo mientras la institucion no los habilite.
ALLOW_MULTIPLE_ENROLLMENTS_PARAM = (
    'wk_school_colombo.allow_multiple_active_enrollments')
ALLOW_BILLING_WITHOUT_PORTAL_PARAM = (
    'wk_school_colombo.allow_billing_without_portal_user')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    wk_allow_same_day_class_completion = fields.Boolean(
        string="Permitir cerrar clases el mismo día de finalización",
        default=True,
        help="Si está activo, la acción 'Marcar como hecho' permite cerrar el "
             "curso ofertado cuando su fecha de finalización es igual o "
             "anterior a la fecha actual.\n"
             "Si está inactivo, se aplica el comportamiento estándar: el "
             "curso solo puede cerrarse a partir del día siguiente a su "
             "fecha de finalización.")

    wk_allow_multiple_active_enrollments = fields.Boolean(
        string="Permitir múltiples inscripciones activas",
        default=False,
        help="Si está activo, un estudiante puede tener varias inscripciones "
             "en curso al mismo tiempo, siempre que correspondan a niveles "
             "académicos distintos. La duplicidad se sigue bloqueando cuando "
             "ya existe una inscripción en curso en el mismo nivel.\n"
             "Si está inactivo, se aplica el comportamiento estándar: una "
             "sola inscripción en curso por estudiante.")

    wk_allow_billing_without_portal_user = fields.Boolean(
        string="Permitir facturación sin usuario portal",
        default=False,
        help="Si está activo, el recibo de tarifas se puede confirmar y "
             "facturar aunque ni el estudiante ni su acudiente tengan usuario "
             "del portal. No se crean usuarios del portal automáticamente.\n"
             "Si está inactivo, se aplica la validación estándar y el recibo "
             "queda bloqueado hasta que exista acceso al portal.")

    # Requerimiento "Estados académicos del estudiante" (2.8): se guarda
    # directamente en la Sede (res.company), no como parámetro de texto -es
    # un Many2one real, no un booleano-, siguiendo el patrón estándar de
    # Odoo para ajustes por compañía.
    accounting_reclassification_user_id = fields.Many2one(
        related='company_id.accounting_reclassification_user_id',
        string="Responsable de reclasificación contable", readonly=False)

    @api.model
    def get_values(self):
        res = super().get_values()
        params = self.env['ir.config_parameter'].sudo()
        res['wk_allow_same_day_class_completion'] = str2bool(
            params.get_param(ALLOW_SAME_DAY_PARAM, 'True'), True)
        res['wk_allow_multiple_active_enrollments'] = str2bool(
            params.get_param(ALLOW_MULTIPLE_ENROLLMENTS_PARAM, 'False'), False)
        res['wk_allow_billing_without_portal_user'] = str2bool(
            params.get_param(ALLOW_BILLING_WITHOUT_PORTAL_PARAM, 'False'),
            False)
        return res

    def set_values(self):
        super().set_values()
        # Se guarda el valor explicitamente ('True'/'False') en lugar de usar
        # el atributo config_parameter del campo: al desactivarlo, Odoo borra
        # el parametro y se volveria a aplicar el valor por defecto.
        params = self.env['ir.config_parameter'].sudo()
        params.set_param(
            ALLOW_SAME_DAY_PARAM,
            'True' if self.wk_allow_same_day_class_completion else 'False')
        params.set_param(
            ALLOW_MULTIPLE_ENROLLMENTS_PARAM,
            'True' if self.wk_allow_multiple_active_enrollments else 'False')
        params.set_param(
            ALLOW_BILLING_WITHOUT_PORTAL_PARAM,
            'True' if self.wk_allow_billing_without_portal_user else 'False')
