# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class DianAiConfig(models.Model):
    _name = 'dian.ai.config'
    _description = 'Configuración del agente de causación DIAN'
    _rec_name = 'company_id'
    _check_company_auto = True

    _company_uniq = models.Constraint(
        'UNIQUE(company_id)',
        'Solo puede haber una configuración del agente por compañía.',
    )

    company_id = fields.Many2one(
        'res.company', 'Compañía', required=True, ondelete='cascade',
        default=lambda self: self.env.company)
    enabled = fields.Boolean(
        'Activo', help='Mientras esté apagado, el agente no procesa documentos de esta compañía.')
    start_date = fields.Date(
        'Procesar documentos desde', required=True, default=fields.Date.context_today,
        help='El agente no causa ni envía eventos de documentos recibidos antes de esta fecha.')
    agent_id = fields.Many2one(
        'ai.agent', 'Agente', required=True,
        default=lambda self: self.env.ref(
            'l10n_co_dian_invoice_ai.ai_agent_dian_invoice', raise_if_not_found=False))
    user_id = fields.Many2one(
        'res.users', 'Usuario responsable', required=True, domain=[('share', '=', False)],
        help='El agente y sus herramientas se ejecutan con los permisos de este usuario, '
             'que debe ser administrador de contabilidad y usuario de compras de la compañía.')
    review_user_id = fields.Many2one(
        'res.users', 'Revisor', domain=[('share', '=', False)],
        help='Recibe las actividades de revisión. Si está vacío, las recibe el usuario responsable.')
    mode = fields.Selection(
        [('draft', 'Borrador'), ('post', 'Causar')], 'Modo', required=True, default='draft',
        help='Borrador: la factura queda lista para que un usuario la publique. '
             'Causar: el agente la publica si pasan todas las validaciones.')
    confidence_threshold = fields.Float(
        'Umbral de confianza', default=0.9,
        help='Entre 0 y 1. Por debajo de este valor la factura queda en borrador.')
    line_tolerance_amount = fields.Float('Tolerancia por línea (valor)', default=1000.0)
    line_tolerance_percent = fields.Float('Tolerancia por línea (%)', default=0.1)
    total_tolerance_amount = fields.Float('Tolerancia del total (valor)', default=1000.0)
    total_tolerance_percent = fields.Float('Tolerancia del total (%)', default=0.1)
    journal_id = fields.Many2one(
        'account.journal', 'Diario de compras', check_company=True,
        domain=[('type', '=', 'purchase')],
        help='Si está vacío se usa el diario que asigne la orden de compra.')
    post_with_tax_adjustment = fields.Boolean(
        'Causar con impuesto ajustado',
        help='Si está activo, cuando el agente agrega o quita un impuesto causa la factura y '
             'la marca "Para revisión". Si no, la factura queda en borrador hasta la revisión.')
    auto_event_030 = fields.Boolean('Enviar acuse de recibo (030)', default=True)
    auto_event_032 = fields.Boolean('Enviar recibo del bien (032)', default=True)
    auto_event_033 = fields.Boolean(
        'Enviar aceptación expresa (033)',
        help='Si está apagado, se crea una actividad para que un usuario la apruebe.')
    batch_size = fields.Integer('Documentos por ejecución', default=10)
    knowledge_base = fields.Html(
        'Base de conocimiento tributario',
        help='Matriz de retenciones, excepciones por proveedor y criterios internos de la '
             'compañía. La configuración de Odoo prevalece sobre este texto.')

    @api.constrains('user_id', 'company_id')
    def _check_user_id(self):
        for config in self:
            if not config.user_id.has_group('account.group_account_manager') \
                    or not config.user_id.has_group('purchase.group_purchase_user'):
                raise ValidationError(_(
                    'El usuario responsable debe ser administrador de contabilidad y usuario de compras.'))
            if config.company_id not in config.user_id.company_ids:
                raise ValidationError(_(
                    'El usuario responsable debe tener acceso a la compañía %s.',
                    config.company_id.name))

    @api.constrains('confidence_threshold')
    def _check_confidence_threshold(self):
        for config in self:
            if not 0 <= config.confidence_threshold <= 1:
                raise ValidationError(_('El umbral de confianza debe estar entre 0 y 1.'))

    @api.constrains('batch_size')
    def _check_batch_size(self):
        for config in self:
            if config.batch_size < 1:
                raise ValidationError(_('Los documentos por ejecución deben ser al menos 1.'))
