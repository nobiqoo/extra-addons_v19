# -*- coding: utf-8 -*-

import io
import base64
import logging

from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError
import pandas as pd

from odoo import models, fields, _, api

_logger = logging.getLogger(__name__)


class MagneticMediaWizard(models.TransientModel):
    _name = 'mag.media.wizard'
    _description = 'Wizard Medios Magnéticos'

    date_from = fields.Date(string='Date from', required=True)
    date_to = fields.Date(string='Date to', required=True)
    city_id = fields.Many2one('res.city', string='City', help='Select the city for which you want to generate the report')

    def export(self):
        id = self.env.context.get('active_id')
        report = self.env['mag.media'].browse(id)

        city_filter = ""
        if self.city_id:
            city_dian_code = self.city_id.dian_code
            city_filter = f"AND rcsc.dian_code = '{city_dian_code}'"

        date_from_an = False
        if report.update_worked_days:
            date_from_an = self.date_to
            date_from_an = date_from_an - relativedelta(months=5)
            date_from_an = date_from_an.replace(day=1)
            self.env['hr.contract'].search([])._set_worked_days(self.date_from, date_from_an, self.date_to)

        sql = str(report.query).format(id=id, date_from=self.date_from,
                                       date_to=self.date_to,
                                       city_filter=city_filter,
                                       date_from_an=date_from_an,
                                       company_id=self.env.company.id)
        _logger.info(sql)
        self.env.cr.execute(sql)
        datas = self.env.cr.dictfetchall()
        if not datas:
            raise UserError(_('''There is no information to display. Check the parameters.'''))

        actual = str(datetime.now()).replace('-', '').replace(':', '').replace('.', '').replace(' ', '')

        # elimina adjuntos del usuario
        self.env['ir.attachment'].search(
            [('res_model', '=', self.env.context.get('active_model')), ('company_id', '=', self.env.user.company_id.id),
             ('name', 'like', '%' + report.name + '%' + self.env.user.name + '%')]).unlink()

        # Create a Pandas dataframe from the data.
        df = pd.DataFrame(data=datas, columns=datas[0].keys())
        # Create a Pandas Excel writer using XlsxWriter as the engine.
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            # Convert the dataframe to an XlsxWriter Excel object.
            df.to_excel(writer, sheet_name=report.name, startcol=-1)
        
        data_attach = {
            'name': report.name + '_' + self.env.user.company_id.name + self.env.user.name + '_' + actual + '.xlsx',
            'datas': base64.b64encode(buffer.getvalue()).decode('utf-8'),
            'store_fname': report.name + '_' + self.env.user.company_id.name + self.env.user.name + '_' + actual + '.xlsx',
            'res_model': 'mag.media',
            'res_id': id
        }
        # crea adjunto en blanco
        attachments = self.env['ir.attachment'].create(data_attach)

        return {
            "type": "ir.actions.act_url",
            "url": '/web/content/%s?download=true' % attachments.id,
            "target": "self",
        }


class MagneticMedia(models.Model):
    _name = 'mag.media'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Medios Magnéticos'

    active = fields.Boolean('Activo', default=True)
    code = fields.Char('Code', required=True, help='Code for magnetic media format', tracking=True)
    name = fields.Char('Name', required=True, help='Name for magnetic media format', tracking=True)
    smaller_amount = fields.Float('Minor amounts', default=0.0, help='The value must be indicated for minor amounts', tracking=True)
    line_ids = fields.One2many('mag.media.lines', 'magnetic_id', string='Lines', tracking=True)
    query = fields.Text(string='Query')
    state = fields.Selection([('draft', 'Draft'), ('confirm', 'Confirm'), ('cancel', 'Cancel')], name='State',
                             default='draft', tracking=True)
    update_worked_days = fields.Boolean(string='Update worked days', default=False)

    def confirm(self):
        self.state = 'confirm'

    def cancel(self):
        self.state = 'cancel'

    def to_draft(self):
        self.state = 'draft'

    def export(self):
        return {'type': 'ir.actions.act_window',
                'res_model': 'mag.media.wizard',
                'res_id': '',  # int(params.get('activeId')),
                'views': [[False, 'form']],
                'target': 'new',
                }


class MagneticMediaLines(models.Model):
    _name = 'mag.media.lines'
    _description = 'Lineas de Medios Magnéticos'

    code = fields.Char('Code', required=True, help='Code for magnetic media format')
    name = fields.Char(string='Line name', required=True,
                       help='The name of the line must be indicated for each concept of magnetic media')
    magnetic_id = fields.Many2one('mag.media', string='Magnetic media')
    concept_ids = fields.One2many('mag.media.lines.concepts', 'line_id', string='Concepts')


class MagneticMediaLinesConcepts(models.Model):
    _name = 'mag.media.lines.concepts'
    _description = 'Conceptos'

    sequence = fields.Char(string='Sequence',
                           help='You must indicate the sequence as it will be shown in the media format')
    name = fields.Char(string='Concept name', required=True,
                       help='The name of the concepts of magnetic media')
    type = fields.Selection([('d', 'Debit'), ('c', 'Credit'), ('sf', 'Saldo final'), ('bi', 'Base impuesto')], string='Type', default='sf', required=True)
    account_ids = fields.Many2many('account.account', string='Accounts',
                                   help='You must select the accounts that apply to this concept')
    tag_ids = fields.Many2many('account.account.tag', 'mag_media_lines_concepts_account_account_tag',
                               'concept_ids',
                               'tag_ids', string='Account Tags',
                               help='You must select the account tags that apply to this concept')
    line_id = fields.Many2one('mag.media.lines', string='Magnetic media')
    by_concept = fields.Boolean(string='Por concepto')
    by_jounals = fields.Boolean(string='Por diarios')
    concepts_ids = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        column1='concept_id',
        column2='line_id',
        relation='media_line_concept_rel',string='Conceptos', help="Selecciona los conceptos que necesitas para el informe")
    journal_ids = fields.Many2many(
        comodel_name='account.journal',
        relation='mag_media_lines_concepts_journal_rel',
        column1='concept_id',
        column2='journal_id',
        string='Journals',
        help='Selecciona los diarios que aplican a este concepto')
    sum_concepts = fields.Boolean(
        string='Sumar por conceptos'
    )
    sum_concepts_ids = fields.Many2many(
        comodel_name='mag.media.lines.concepts',
        relation='mag_media_concepts_rel',
        column1='concept_id',
        column2='rel_concept_id',
        domain="[('line_id', '=', line_id)]",
        string='Conceptos',
        help='Selecciona los conceptos que aplican a este concepto')

    @api.onchange('sum_concepts_ids')
    def _onchange_sum_concepts_ids(self):
        for record in self:
            for concept in record.sum_concepts_ids:
                for line in concept.concepts_ids:
                    record.concepts_ids += line
