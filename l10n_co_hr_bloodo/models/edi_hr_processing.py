#  -*- coding: utf-8 -*-

import sys
import logging
import traceback

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

EDI_TYPE = [
    ('nie', 'Nómina Individual'),
    ('niae_r', 'Nómina Ajuste (Reemplazar)'),
    ('niae_e', 'Nómina Ajuste (Eliminar)')
]

TYPE_NAME = {
    'nie': 'NIE',
    'niae_r': 'NIAE-R',
    'niae_e': 'NIAE-E'
}


class EdiHrProcessing(models.Model):
    _name = 'edi.hr.processing'
    _description = 'Procesamiento de nómina electrónica'

    edi_type = fields.Selection(EDI_TYPE,
                                'Tipo',
                                default='nie')
    period_id = fields.Many2one('hr.period',
                                'Periodo')
    period_ids = fields.Many2many('hr.period',
                                 'Periodos',
                                 compute='_compute_period_ids')
    payslip_ids = fields.Many2many('hr.payslip',
                                   'hr_edi_proccessing_rel',
                                   'edi_id',
                                   'hr_id',
                                   'Nóminas')
    edi_hr_ids = fields.One2many('edi.hr.document',
                                 'edi_processing_id',
                                 'Nóminas Electrónicas')
    company_id = fields.Many2one('res.company',
                                 'Company',
                                 default=lambda self: self.env.company,
                                 readonly=True)
    state = fields.Selection([('draft', 'Borrador'),
                              ('post', 'Generado')],
                              'Estado',
                              default='draft')
    # Ajuste
    from_edi_hr_id = fields.Many2one('edi.hr.document',
                                     'NE predecesora')
    from_contract_id = fields.Many2one('hr.contract',
                                       'Contrato',
                                       compute='_compute_from_contract')
    payslip_count = fields.Integer('# Nóminas',
                                   compute='_compute_doc_count')
    edi_hr_count = fields.Integer('# Nóminas electrónicas',
                                  compute='_compute_doc_count')
    gesendet_edi_count = fields.Integer('# Enviados',
                                      compute='_compute_doc_count')
    richtig_edi_count = fields.Integer('# Exitosos',
                                      compute='_compute_doc_count')
    abgelehnt_edi_count = fields.Integer('# Rechazos',
                                         compute='_compute_doc_count')
    fehler_edi_count = fields.Integer('# Errores',
                                      compute='_compute_doc_count')
    
    @api.depends('period_id.name', 'edi_type')
    def _compute_display_name(self):
        for record in self:
            record.display_name = u'%s [%s] %s' % (
                record.period_id.name,
                record.edi_type and TYPE_NAME.get(record.edi_type, '-') or '-',
                record.id)
    
    def _compute_doc_count(self):
        for record in self:
            record.payslip_count = len(record.payslip_ids)
            record.edi_hr_count = len(record.edi_hr_ids)
            record.gesendet_edi_count = len(record.edi_hr_ids.filtered(
                lambda z: z.state == 'gesendet'))
            record.richtig_edi_count = len(record.edi_hr_ids.filtered(
                lambda z: z.state == 'richtig'))
            record.abgelehnt_edi_count = len(record.edi_hr_ids.filtered(
                lambda z: z.state == 'abgelehnt'))
            record.fehler_edi_count = len(record.edi_hr_ids.filtered(
                lambda z: z.state == 'fehler'))
    
    def _compute_from_contract(self):
        for record in self:
            record.from_contract_id = record.from_edi_hr_id \
                and record.from_edi_hr_id.contract_id.id \
                or False
    
    @api.depends('period_id')
    def _compute_period_ids(self):
        for record in self:
            period_ids = self._get_periods_monthly(self.period_id)
            record.period_ids = period_ids and period_ids.ids or False
    
    @api.onchange('edi_type', 'period_id', 'from_edi_hr_id')
    def _onchange_payslip_ids(self):
        period_ids = self._get_periods_monthly(self.period_id)
        domain = [('id','=',0)]
        if period_ids:
            if self.edi_type == 'nie':
                domain = [('state', '=' , 'paid'),
                        ('period_id', 'in', period_ids.ids),
                        ('company_id', '=', self.company_id.id)]
            elif self.edi_type == 'niae_r' and self.from_edi_hr_id:
                contract_id = self.from_edi_hr_id.payslip_ids[0].contract_id
                domain = [('state', '=' , 'paid'),
                        ('period_id', 'in', period_ids.ids),
                        ('company_id', '=', self.company_id.id),
                        ('contract_id', '=', contract_id.id)]
            elif self.edi_type == 'niae_e' and self.from_edi_hr_id:
                domain = [('id','in',self.from_edi_hr_id.payslip_ids.ids)]
        return {
            'domain': {
                'payslip_ids': domain,
            }
        }
    
    def unlink(self):
        for record in self:
            if record.state != 'draft' or record.edi_hr_ids:
                raise ValidationError(
                    _('No se puede eliminar procesamientos que '
                      'ya tienen nóminas electrónicas creadas: \n%s',
                      record.display_name))
        return super(EdiHrProcessing, self).unlink()
        
    def _get_periods_monthly(self, period_id=False):
        if not period_id:
            return False
        period_obj = self.env['hr.period']
        # search
        period_ids = period_obj.search([('start', '>=', period_id.start),
                                        ('end', '<=', period_id.end)])
        return period_ids
    
    def siehe_lohnliste(self):
        self.ensure_one()
        if self.state != 'draft':
            raise ValidationError(
                _('Acción no permitida, el documento de procesamiento '
                  'ya creó los documentos electrónicos para las nóminas'))
        # Obj
        hr_obj = self.env['hr.payslip']

        period_ids = self._get_periods_monthly(self.period_id)
        # TODO Validar si las nominas ya tienen docs electronicos
        if self.edi_type == 'nie':
            hr_ids = hr_obj.search([('state', '=' , 'paid'),
                                ('period_id', 'in', period_ids.ids),
                                ('company_id', '=', self.company_id.id)])
            # for doc in hr_ids:
            #     if doc.edi_hr_ids:
            #         raise ValidationError(
            #             _('La nómina %s ya tiene documentos electrónicos. \n'
            #             'Por favor, verifique el documento.\n%s', 
            #             doc.name,
            #             '\n'.join(
            #                 [f'{x.name} ({x.state})' for x in doc.edi_hr_ids])
            #         ))
        elif self.edi_type == 'niae_r':
            if not self.from_edi_hr_id:
                raise ValidationError(
                    _('Se requiere el doc. electrónico al cuál aplica el '
                      'ajuste (NE predecesor).'))
            contract_id = self.from_edi_hr_id.payslip_ids[0].contract_id
            hr_ids = hr_obj.search([('state', '=' , 'paid'),
                                    ('period_id', 'in', period_ids.ids),
                                    ('company_id', '=', self.company_id.id),
                                    ('contract_id', '=', contract_id.id)])
        elif self.edi_type == 'niae_e':
            if not self.from_edi_hr_id:
                raise ValidationError(
                    _('Se requiere el doc. electrónico al cuál aplica el '
                      'ajuste (NE predecesor).'))
            hr_ids = self.from_edi_hr_id.payslip_ids
        self.write({'payslip_ids': [(6, 0, hr_ids.ids)]})
        self._onchange_payslip_ids()
    
    def tun_elohnliste(self):
        self.ensure_one()
        if self.state != 'draft':
            raise ValidationError(
                _('Acción no permitida, el documento de procesamiento '
                  'ya creó los documentos electrónicos para las nóminas'))
        edi_doc_obj = self.env['edi.hr.document']
        type_ne = self.edi_type
        werte = {}
        for doc in self.payslip_ids:
            if type_ne == 'nie' and doc.edi_hr_ids:
                raise ValidationError(
                    _('La nómina %s ya tiene documentos electrónicos. \n'
                      'Por favor, verifique el documento.\n%s', 
                      doc.name,
                      '\n'.join([f'{x.name} {x.state}' for x in doc.edi_hr_ids])
                    ))
            contract = str(doc.contract_id.id)
            if contract not in werte:
                werte[contract] = {
                        'payslip_ids': [(6, 0, doc.ids)],
                        'company_id': self.company_id.id,
                        'period_id': self.period_id.id,
                        'edi_type': type_ne,
                        'to_send': True,
                        'to_check_status': True,
                        'edi_processing_id': self.id,
                }
            else:
                werte[contract]['payslip_ids'][0][2].append(doc.id)
            if type_ne != 'nie':
                from_edi_hr_id = self.from_edi_hr_id
                if not from_edi_hr_id:
                    raise ValidationError(
                        _('Se requiere informar el documento electrónico al '
                          'cuál aplicará la nota de ajuste.'))
                werte[contract].update({
                    'edi_doc_origin_id': from_edi_hr_id.id,
                    'edi_cune_origin': from_edi_hr_id.edi_cune,
                    'edi_zahl_origin': from_edi_hr_id.edi_zahl,
                    'edi_gen_datum_origin': from_edi_hr_id.edi_datum,
                })
        # TODO Ver si se requiere validar numero de nominas por contrato 
        #       cuando son quincenales, etc.
        #      Se debe tener en cuenta cuando es un inicio a trabajar o
        #       un retiro de trabajo porque pueden darse antes del fin de mes
        werte2 = [v for v in werte.values()]
        edi_doc_ids = edi_doc_obj.create(werte2)
        num_docs = len(edi_doc_ids)
        counter = 0
        for doc in edi_doc_ids:
            try:
                doc.xml_datei_erhalten()
                counter += 1
                progress = (counter / num_docs) * 100
                _logger.info('\nNIE calculadas {}, progreso: {:.2f} %'.format(counter, progress))
            except Exception as error:
                tb = traceback.format_tb(sys.exc_info()[2], 10)
                raise ValidationError(
                    _('Ocurrió un error al generar el documento electrónico '
                      'de la nómina: \n_____NOMINA_____|_PERIODO_|__ID__\n%s'
                      '\n\nError: %s\n\nTraza:\n%s',
                      '\n'.join([
                          f'{n.name} {n.period_id.name} ({n.id})' 
                          for n in doc.payslip_ids
                      ]),
                      str(error),
                      ''.join(tb)))
        self.write({'state': 'post'})
    
    def action_payslips(self):
        ids = []
        for record in self:
            ids = record.payslip_ids.ids
        if ids:
            action = self.env.ref('hr_payroll_co.hr_payslip_action').read()[0]
            action['domain'] = [('id', 'in', ids)]
            action['context'] = {
                'create': False,
                'edit': False,
                'delete': False
            }
            return action
        else:
            raise ValidationError(
                _('No hay nóminas para visualizar'))
    
    def action_edi_hr(self):
        ids = []
        filter_state = self.env.context.get('edi_state', False)
        for record in self:
            if filter_state:
                ids = record.edi_hr_ids.filtered(
                    lambda z: z.state == filter_state).ids
            else:
                ids = record.edi_hr_ids.ids
        if ids:
            action = self.env.ref(
                'l10n_co_hr_bloodo.edi_hr_document_action').read()[0]
            action['domain'] = [('id', 'in', ids)]
            action['context'] = {
                'create': False,
                'edit': False,
                'delete': False
            }
            return action
        else:
            raise ValidationError(
                _('No hay nóminas para visualizar'))
    
    def _change_rel_to_m2m(self):
        self.ensure_one()
        if self.state != 'draft':
            raise ValidationError(
                _('Este documento ya tiene nóminas electónicas generadas.'))
        ne_obj = self.env['edi.hr.document']
        ne_ids = ne_obj.search([('edi_type', '=', self.edi_type),
                                ('payslip_id', '!=', False)])
        period_ids = self.period_ids.ids
        add_ne_ids = ne_ids.filtered(
            lambda n: n.payslip_id.period_id.id in period_ids)
        if add_ne_ids:
            add_n_ids = [ne.payslip_id.id for ne in add_ne_ids]
            self.write({
                'payslip_ids': [(6, 0, add_n_ids)]
            })
            for ne in add_ne_ids:
                ne.write({
                    'payslip_ids': [(6, 0, ne.payslip_id.ids)],
                    'payslip_id': False,
                    'period_id': self.period_id.id,
                    'edi_processing_id': self.id
                })
        else:
            raise ValidationError(
                _('No hay nada'))
