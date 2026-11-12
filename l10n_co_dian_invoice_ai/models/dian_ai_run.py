# -*- coding: utf-8 -*-
from odoo import fields, models


class DianAiRun(models.Model):
    _name = 'dian.ai.run'
    _description = 'Ejecución del agente de causación DIAN'
    _order = 'id desc'
    _check_company_auto = True

    document_id = fields.Many2one(
        'dian.document', 'Documento DIAN', required=True, ondelete='cascade',
        index=True, check_company=True)
    company_id = fields.Many2one(related='document_id.company_id', store=True, index=True)
    move_id = fields.Many2one('account.move', 'Factura', check_company=True, ondelete='set null')
    agent_id = fields.Many2one('ai.agent', 'Agente', ondelete='set null')
    llm_model = fields.Char('Modelo de IA')
    user_id = fields.Many2one('res.users', 'Usuario responsable')
    outcome = fields.Selection(
        [('running', 'En curso'),
         ('posted', 'Causada'),
         ('review', 'Causada para revisión'),
         ('draft', 'Borrador'),
         ('exception', 'Excepción'),
         ('error', 'Error')],
        'Resultado', default='running', required=True)
    automatic = fields.Integer('Causación automática', aggregator='sum')
    confidence = fields.Float('Confianza', aggregator='avg')
    reasons = fields.Text('Motivos')
    input_tokens = fields.Integer('Tokens de entrada', aggregator='sum')
    cached_tokens = fields.Integer('Tokens en caché', aggregator='sum')
    output_tokens = fields.Integer('Tokens de salida', aggregator='sum')
    response = fields.Text('Respuesta del agente')
