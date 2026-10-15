# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    state = fields.Selection(
        selection=[
            ('unaudited', 'Sin Auditar'),
            ('audited', 'Auditado'),
            ('closed_commissions', 'Comisiones Cerradas'),
            ('pending_commissions', 'Comisiones Pendientes'),
            ('closed', 'Cerrado'),
        ],
        string='Estado',
        default='unaudited',
    )
