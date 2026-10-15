# -*- coding: utf-8 -*-

import sys
import logging
import traceback
from lxml import etree
from pytz import timezone
from datetime import datetime
from requests import post, exceptions
from base64 import b64encode, b64decode

from odoo import api, fields, models, _
from odoo.modules.registry import Registry
from odoo.exceptions import ValidationError
from . import l10n_co_edi_sentences as satz

_logger = logging.getLogger(__name__)

EDI_TYPE = [
    ('nie', 'Nómina Individual'),
    ('niae_r', 'Nómina Ajuste (Reemplazar)'),
    ('niae_e', 'Nómina Ajuste (Eliminar)')
]

STATES = [
    ('neu', 'Nuevo'),
    ('gesendet', 'Enviado'),
    ('richtig', 'Correcto'),
    ('abgelehnt', 'Rechazado'),
    ('fehler', 'Error')
]

TYPE_NAME = {
    'nie': 'NIE',
    'niae_r': 'NIAE-R',
    'niae_e': 'NIAE-E'
}

URL_CUNE = {
    'hab': 'https://catalogo-vpfe-hab.dian.gov.co'
    '/document/searchqr?documentkey=CUNE',
    'prod': 'https://catalogo-vpfe.dian.gov.co'
    '/document/searchqr?documentkey=CUNE'
}

DIAN = {
    'wsdl-hab': 'https://vpfe-hab.dian.gov.co'
    '/WcfDianCustomerServices.svc?wsdl',
    'wsdl': 'https://vpfe.dian.gov.co/WcfDianCustomerServices.svc?wsdl',
    'catalogo-hab': 'https://catalogo-vpfe-hab.dian.gov.co'
    '/Document/FindDocument?documentKey={}&partitionKey={}&emissionDate={}',
    'catalogo': 'https://catalogo-vpfe.dian.gov.co'
    '/Document/FindDocument?documentKey={}&partitionKey={}&emissionDate={}'
}


class EdiHrDocument(models.Model):
    _name = 'edi.hr.document'
    _description = 'Documento de Nómina Electrónica'

    name = fields.Char('Nombre',
                       compute='_compute_name',
                       store=True)
    state = fields.Selection(STATES,
                             'Estado',
                             default='neu')
    edi_type = fields.Selection(EDI_TYPE,
                                'Tipo')
    payslip_id = fields.Many2one('hr.payslip',
                                 'Nómina',
                                 copy=False)
    payslip_ids = fields.Many2many('hr.payslip',
                                   'edi_doc_payslip_rel',
                                   'edi_id',
                                   'hr_id',
                                   'Nóminas')
    contract_id = fields.Many2one('hr.contract',
                                  'Contrato',
                                  compute='_compute_contract')
    edi_processing_id = fields.Many2one('edi.hr.processing',
                                        'Procesamiento NE')
    company_id = fields.Many2one('res.company',
                                 'Compañía',
                                 default=lambda self: self.env.company,
                                 readonly=True)
    edi_datum = fields.Date('Fecha de generación',
                            copy=False)
    edi_zahl = fields.Char('Número',
                           copy=False)
    # xml
    edi_xml_fname = fields.Char('XML name',
                                copy=False)
    edi_xml_file = fields.Binary('XML',
                                 copy=False)
    # zip
    edi_zip_fname = fields.Char('Zip name',
                                copy=False)
    edi_zip_file = fields.Binary('Zip',
                                 copy=False)
    edi_qr_image = fields.Binary('QR',
                                 copy=False)
    edi_cune = fields.Char('CUNE',
                           copy=False)
    edi_cune_uncode = fields.Char('CUNE Uncode',
                                  copy=False)
    edi_ssc = fields.Char('SSC',
                          copy=False)
    edi_ssc_uncode = fields.Char('SSC uncode',
                                 copy=False)
    edi_url = fields.Char('Edi URL',
                          copy=False)
    # Origin niae
    edi_doc_origin_id = fields.Many2one('edi.hr.document',
                                        'Doc. electrónico (ref)',
                                        copy=False)
    origin_payslip_id = fields.Many2one('hr.payslip',
                                        'Payslip origin',
                                        copy=False)
    edi_cune_origin = fields.Char('CUNE (ref)',
                                  copy=False)
    edi_zahl_origin = fields.Char('Número (ref)',
                                  copy=False)
    edi_gen_datum_origin = fields.Char('Fecha de generación (ref)',
                                       copy=False)
    # logs
    edi_log_ids = fields.One2many('edi.hr.log',
                                  'edi_hr_id',
                                  'Log Dian',
                                  copy=False)
    # Application Response
    edi_ar_fname = fields.Char('ApplicationResponse XML Filename',
                               copy=False,
                               default='ApplicationResponse.xml')
    edi_ar_file = fields.Binary('Ap. Response',
                                copy=False)
    # Zip key
    edi_zip_key = fields.Char('ZipKey',
                              copy=False)
    # Out Response
    hr_edi_state = fields.Char('Estado DIAN',
                               copy=False)
    hr_edi_response = fields.Text('Respuesta DIAN',
                                  copy=False)
    # Massen
    to_send = fields.Boolean('Envío pendiente',
                             help='Si el estado de este documento es "Nuevo" '
                             'y este campo está activo, será enviado a la '
                             'DIAN por medio de una acción planificada',
                             default=False)
    to_check_status = fields.Boolean('Comprobar estado',
                                     help='Si el estado de este documento es '
                                     '"Enviado" y este campo está activo, se '
                                     'consultará el estado en la DIAN '
                                     'por medio de una acción planificada',
                                     default=False)
    period_id = fields.Many2one('hr.period',
                                'Periodo',
                                domain=[('type_period', '=', 'MONTHLY')])
    
    def _compute_contract(self):
        for record in self:
            record.contract_id = record.payslip_ids \
                and record.payslip_ids[0].contract_id.id or False

    @api.depends('payslip_id', 'edi_type')
    def _compute_name(self):
        for record in self:
            record.name = '[ %s ] %s' % (
                record.edi_type
                and TYPE_NAME.get(record.edi_type, '-')
                or '-',
                record.edi_zahl
                or _('Undefined')
            )
            # record.payslip_id
            # and record.payslip_id.name

    @api.depends('edi_type', 'edi_zahl')
    def _compute_display_name(self):
        for record in self:
            record.display_name = u'[ %s ] %s' % (
                record.edi_type
                and TYPE_NAME.get(record.edi_type, '-')
                or '-',
                record.edi_zahl
                or _('Undefined')
            )

    # TODO revisar si sirve o mejor quitar
    # @api.onchange('payslip_id', 'edi_type')
    # def onchange_payslip_id_and_type(self):
    #     if self.payslip_id and self.edi_type == 'niae_e':
    #         doc_ids = self.payslip_id.edi_doc_ids.ids
    #         out = {
    #             'domain': {
    #                 'edi_doc_origin_id': [('id','in',doc_ids)]
    #             }
    #         }
    #         if len(self.payslip_id.edi_doc_ids.ids) == 1:
    #             out['value'] = {
    #                 'edi_doc_origin_id': doc_ids[0]
    #             }
    #         return out
    #     else:
    #         pass

    @api.onchange('edi_doc_origin_id', 'edi_type')
    def onchange_edi_doc_origin_and_type(self):
        if self.edi_doc_origin_id and self.edi_type == 'niae_e':
            return {
                'value': {
                    'payslip_id': self.edi_doc_origin_id.payslip_id.id
                }
            }
        else:
            pass
    
    @api.onchange('edi_type')
    def onchange_edi_type(self):
        if self.edi_type == 'nie':
            self.edi_doc_origin_id = False
        else:
            pass

    @api.onchange('edi_doc_origin_id')
    def onchange_edi_doc_origin_id(self):
        doc_id = self.edi_doc_origin_id or False
        return {
            'value': {
                # 'origin_payslip_id': doc_id and doc_id.payslip_id.id or False,
                'edi_cune_origin': doc_id and doc_id.edi_cune or False,
                'edi_zahl_origin': doc_id and doc_id.edi_zahl or False,
                'edi_gen_datum_origin': doc_id and doc_id.edi_datum or False,
            }
        }

    def xml_datei_erhalten(self):
        self.ensure_one()
        type_doc = self._get_type_document()
        xml_fname = self.edi_xml_fname \
            and self.edi_xml_fname \
            or self._get_edi_filenames(type_doc)
        zip_fname = self.edi_zip_fname and self.edi_zip_fname \
            or self._get_edi_filenames('zip')

        xml_str = self.get_xml_e_payroll(type_doc)
        xml_file = b64encode(xml_str)
        data_to_zip = [(xml_fname, xml_file)]
        zip_file = b64encode(
            satz.get_zipped_file(data_to_zip)
        )
        # .decode("utf-8", "ignore")
        self.write({
            'edi_xml_file': xml_file,
            'edi_xml_fname': xml_fname,
            'edi_zip_fname': zip_fname,
            'edi_zip_file': zip_file,
        })
        # print(xml_file)
    
    def genzip(self):
        self.ensure_one()
        data_to_zip = [(self.edi_xml_fname, self.edi_xml_file)]
        zip_file = b64encode(
            satz.get_zipped_file(data_to_zip)
        )
        self.edi_zip_file = zip_file

    def _get_type_document(self):
        self.ensure_one()
        if not self.edi_type:
            raise ValidationError(
                _('Es necesario definir el tipo de documento de '
                  'nómina electrónico "%s".', self.display_name))
        return self.edi_type

    def _get_edi_filenames(self, type_doc=False):
        '''
            Calculates the name of the electronic payroll files.
            Chapter. 3.3, 3.4, 3.5
        '''

        self.ensure_one()
        prefix = ''
        nnnnnnnnnn = ''
        aa = ''
        dddddddd = ''
        ext = '.xml'

        if self.company_id.partner_id.vat:
            nnnnnnnnnn = self.company_id.partner_id.vat.zfill(10)
        else:
            raise ValidationError(
                _('El documento de identificación de %s '
                  'no está establecido. \n', 
                  self.company_id.partner_id.name))

        aa = fields.Datetime.context_timestamp(
            self,
            datetime.now()).strftime('%y')

        if type_doc == 'nie':
            prefix = 'nie'
            nie_sent = self.company_id.nie_sent
            dddddddd = nie_sent + 1
            self.sudo().company_id.nie_sent = dddddddd
        elif type_doc == 'niae_r':
            prefix = 'niae'
            niae_sent = self.company_id.niae_sent
            dddddddd = niae_sent + 1
            self.sudo().company_id.niae_sent = dddddddd
        elif type_doc == 'niae_e':
            prefix = 'niae'
            niae_sent = self.company_id.niae_sent
            dddddddd = niae_sent + 1
            self.sudo().company_id.niae_sent = dddddddd
        elif type_doc == 'zip':
            prefix = 'z'
            ext = '.zip'
            z_sent = self.company_id.z_sent
            dddddddd = z_sent + 1
            self.sudo().company_id.z_sent = dddddddd
        else:
            raise ValidationError(
                _('ERROR: No se puede definir el tipo de documento '
                    'electrónico para la nómina %s') % self.payslip_id.name)

        dddddddd = '{:08x}'.format(dddddddd).upper()
        nnnnnnnnnnaadddddddd = nnnnnnnnnn + aa + dddddddd

        return prefix + nnnnnnnnnnaadddddddd + ext

    def get_xml_e_payroll(self, type_doc=''):
        self.ensure_one()
        if type_doc == 'nie':
            doc_values = self._get_values_nie(type_doc)
            doc_template = 'NominaIndividual'
        elif type_doc == 'niae_r':
            doc_values = self._get_values_niae_r(type_doc)
            doc_template = 'NominaIndividualDeAjuste'
        elif type_doc == 'niae_e':
            doc_values = self._get_values_niae_e(type_doc)
            doc_template = 'NominaIndividualDeAjuste'
        else:
            raise ValidationError(
                _('ERROR: No se puede definir el tipo de documento '
                    'electrónico de la nómina %s') % self.payslip_id.name)

        unsigned_xml = satz.render_xml_edi(
            doc_values,
            doc_template)

        xml_with_signature = satz.xml_mit_signatur_erhalten(
            unsigned_xml,
            self.company_id.hr_signature_policy_url,
            self.company_id.hr_signature_policy_description,
            self.company_id.hr_signature_policy_file,
            self.company_id.hr_certificate_file,
            self.company_id.hr_certificate_password)

        return xml_with_signature

    def _get_values_nie(self, type_doc):
        '''
            Data NominaIndividual
            output: {}
        '''
        werte = {}
        nie = self.payslip_ids
        self._concept_config_validation()
        # ingen = self._codegen(self, nie, type_doc)
        werte = self._datenwerte_erhalten(type_doc)
        self._xml_daten_validieren(werte, type_doc)
        return werte

    def _datenwerte_erhalten(self, type_doc):
        self.ensure_one()
        company = self.company_id
        nie = self.payslip_ids
        total_earnings = 0
        total_deductions = 0
        period_ne = nie._build_period_ne()
        employer_ne = nie._build_employer_ne()
        employee = nie._build_employee_ne()
        workplace = nie._build_workplace()
        # DEVENGOS
        basic_wage = nie._build_basic_wage()
        total_earnings += basic_wage['Dev_Bas_SueldoTrabajado']
        sub_trans = nie._build_sub_trans()
        total_earnings += float(sub_trans['AuxilioTransporte']) \
            + float(sub_trans['ViaticoManutAlojS']) \
                + float(sub_trans['ViaticoManutAlojNS'])
        hed = nie._build_hed_overtimes()
        for x in hed:
            total_earnings += float(x.get('Pago' , 0))
        hen = nie._build_hen_overtimes()
        for x in hen:
            total_earnings += float(x.get('Pago' , 0))
        hrn = nie._build_hrn_overtimes()
        for x in hrn:
            total_earnings += float(x.get('Pago' , 0))
        heddf = nie._build_heddf_overtimes()
        for x in heddf:
            total_earnings += float(x.get('Pago' , 0))
        hrddf = nie._build_hrddf_overtimes()
        for x in hrddf:
            total_earnings += float(x.get('Pago' , 0))
        hendf = nie._build_hendf_overtimes()
        for x in hendf:
            total_earnings += float(x.get('Pago' , 0))
        hrndf = nie._build_hrndf_overtimes()
        for x in hrndf:
            total_earnings += float(x.get('Pago' , 0))
        holidays = nie._build_holidays()
        for x in holidays.get('VacacionesComunes', []):
            total_earnings += float(x.get('Pago' , 0))
        for x in holidays.get('VacacionesCompensadas', []):
            total_earnings += float(x.get('Pago' , 0))
        prima = nie._build_prima()
        total_earnings += float(prima['Dev_Pri_Pago']) \
            + float(prima['Dev_Pri_PagoNS'])
        ces = nie._build_ces()
        total_earnings += float(ces['Dev_Ces_Pago']) \
            + float(ces['Dev_Ces_PagoIntereses'])
        inabilitys = nie._build_inabilitys()
        for x in inabilitys:
            total_earnings += float(x.get('Pago' , 0))
        licenses = nie._build_licenses()
        for x in licenses.get('LicenciaMP', []):
            total_earnings += float(x.get('Pago' , 0))
        for x in licenses.get('LicenciaR', []):
            total_earnings += float(x.get('Pago' , 0))
        bonds = nie._build_bonds()
        for x in bonds:
            total_earnings += float(x.get('BonificacionNS', 0)) \
                + float(x.get('BonificacionS', 0))
        # Auxilios
        aids = nie._build_aids()
        for x in aids:
            total_earnings += float(x.get('AuxilioNS', 0)) \
                + float(x.get('AuxilioS', 0))
        # HuelgasLegales
        # TODO
        # OtrosConceptos
        oconcepts = nie._build_other_concepts()
        for x in oconcepts:
            total_earnings += float(x.get('ConceptoS', 0)) \
                + float(x.get('ConceptoNS', 0))
        # Compensaciones
        compensations = nie._build_compensations()
        for x in compensations:
            total_earnings += float(x.get('CompensacionO', 0)) \
                + float(x.get('CompensacionE', 0))
        # BonoEPCTVs
        epctvs = nie._build_bonds_epctv()
        for x in epctvs:
            total_earnings += float(x.get('PagoS', 0)) \
                + float(x.get('PagoNS', 0)) \
                    + float(x.get('PagoAlimentacionS', 0)) \
                        + float(x.get('PagoAlimentacionNS', 0))
        # Comisiones
        commissions = nie._build_commissions()
        total_earnings += float(commissions.get('Comision', 0))
        # PagosTerceros
        dev_partners = nie._build_payment_partner()
        total_earnings += float(dev_partners.get('PagoTercero', 0))
        # Anticipos
        dev_advances = nie._build_advances()
        total_earnings += float(dev_advances.get('Anticipo', 0))
        # Dotacion
        dotation = nie._build_dotation()
        total_earnings += float(dotation)
        # ApoyoSost
        sus_support = nie._build_sustenance_support()
        total_earnings += float(sus_support)
        # Teletrabajo
        telew = nie._build_teleworking()
        total_earnings += float(telew)
        # BonifRetiro
        bonret = nie._build_retirement_bonus()
        total_earnings += float(bonret)
        # Indemnizacion
        indem = nie._build_indemnification()
        total_earnings += float(indem)
        # Reintegro
        dev_return = nie._build_return()
        total_earnings += float(dev_return)

        # Deducciones
        deduction_health = nie._build_deduction_health()
        total_deductions += float(deduction_health['Ded_Salud_Deduccion'])
        deduction_pension = nie._build_deduction_pension()
        total_deductions += float(deduction_pension['Ded_FoPen_Deduccion'])
        deduction_solidarity = nie._build_deduction_solidarity()
        total_deductions += float(deduction_solidarity['Ded_FoSP_Deduccion'])
        deduction_subsistence = nie._build_deduction_subsistence()
        total_deductions += float(deduction_subsistence['Ded_FoSP_DeduccionSub'])
        # TODO
        # Sindicatos
        # Sanciones
        sanctions = nie._build_sanctions()
        for x in sanctions:
            total_deductions += float(x.get('SancionPublic', 0)) \
                + float(x.get('SancionPriv', 0))
        # Libranzas
        prommissory = nie._build_promissory_notes()
        for x in prommissory:
            total_deductions += float(x.get('Deduccion', 0))
        # PagosTerceros
        ded_partners = nie._build_payment_partner_ded()
        total_deductions += float(ded_partners.get('PagoTercero', 0))
        # Anticipos
        ded_advances = nie._build_advances_ded()
        total_deductions += float(ded_advances.get('Anticipo', 0))
        # OtrasDeducciones
        odeductions = nie._build_other_ded()
        total_deductions += float(odeductions.get('OtraDeduccion', 0))
        # PensionVoluntaria
        vol_pension = nie._build_voluntary_pension()
        total_deductions += float(vol_pension)
        # RetencionFuente
        deduction_retfte = nie._build_deduction_rtefte()
        total_deductions += float(deduction_retfte)
        # AFC
        afc = nie._build_afc()
        total_deductions += float(afc)
        # Cooperativa
        coop = nie._build_cooperative()
        total_deductions += float(coop)
        # EmbargoFiscal
        tax_emb = nie._build_tax_embargo()
        total_deductions += float(tax_emb)
        # PlanComplementarios
        comp_plan = nie._build_complementary_plan()
        total_deductions += float(comp_plan)
        # Educacion
        education = nie._build_education()
        total_deductions += float(education)
        # Reintegro
        ded_return = nie._build_return_ded()
        total_deductions += float(ded_return)
        # Deuda
        debt = nie._build_debt()
        total_deductions += float(debt)
        notes = nie._get_notes_edi_hr()
        
        ingen = self._codegen(self, nie, type_doc, total_earnings, total_deductions)

        return {
            # Novedad
            'Novedad': 'false',
            'CuneNov': ingen.get('cune'),
            # Periodo
            'Per': {
                'FechaIngreso': period_ne.get('Per_FechaIngreso', ''),
                'FechaRetiro': period_ne.get('Per_FechaRetiro', ''),
                'FechaLiquidacionInicio':
                    period_ne.get('Per_FechaLiquidacionInicio', ''),
                'FechaLiquidacionFin':
                    period_ne.get('Per_FechaLiquidacionFin', ''),
                'TiempoLaborado': '{:.2f}'.format(
                    period_ne.get('Per_TiempoLaborado', 0)),
                'FechaGen': period_ne.get('Per_FechaGen', ''),  # FecNE,
            },
            # NumeroSecuenciaXML
            # Creo que esto es opcional
            'NSX': {
                'CodigoTrabajador': '',
                'Prefijo': ingen.get('prefix'),
                'Consecutivo': ingen.get('number'),
                'Numero': ingen.get('NumNE'),
            },
            # LugarGeneracionXML
            # Necesito ver las tablas 5.4.1 a 5.4.3
            'LGX': {
                'Pais': workplace['LGX_Pais'],
                'DepartamentoEstado': workplace['LGX_DepartamentoEstado'],
                'MunicipioCiudad': workplace['LGX_MunicipioCiudad'],
                'Idioma': workplace['LGX_Idioma'],
            },
            # ProveedorXML
            # Validar
            'PrX': {
                'RazonSocial': company.name, #'OdOne S.A.S',
                'PrimerApellido': '',
                'SegundoApellido': '',
                'PrimerNombre': '',
                'OtrosNombres': '',
                'NIT': company.partner_id.vat, #'901361603',
                'DV': company.partner_id.l10n_co_verification_code, # '8',
                'SoftwareID': ingen.get('IdSoft'),
                'SoftwareSC': ingen.get('ssc'),
            },
            # CodigoQR
            'CodigoQR': ingen.get('qr_data_url'),
            # InformacionGeneral
            # Ver tabla 5.5.1
            'IGe': {
                'Version': ingen.get('version'),
                'Ambiente': ingen.get('TipAmb'),
                'TipoXML': ingen.get('TipoXML'),
                'CUNE': ingen.get('cune'),
                'EncripCUNE': 'CUNE-SHA384',
                'FechaGen': ingen.get('FecNE'),
                'HoraGen': ingen.get('HorNE'),
                'PeriodoNomina': period_ne.get('IGe_PeriodoNomina', ''),
                'TipoMoneda': 'COP',
                'TRM': '1.00',
            },
            # Notas
            'Notas': notes,  # ObJinja
            # Empleador
            'Emp': {
                'RazonSocial': employer_ne.get('Emp_RazonSocial', ''),
                'PrimerApellido': employer_ne.get('Emp_PrimerApellido', ''),
                'SegundoApellido': employer_ne.get('Emp_SegundoApellido', ''),
                'PrimerNombre': employer_ne.get('Emp_PrimerNombre', ''),
                'OtrosNombres': employer_ne.get('Emp_OtrosNombres', ''),
                'NIT': employer_ne.get('Emp_NIT', ''),  # NitNE,
                'DV': employer_ne.get('Emp_DV', ''),
                'Pais': employer_ne.get('Emp_Pais', ''),
                'DepartamentoEstado':
                    employer_ne.get('Emp_DepartamentoEstado', ''),
                'MunicipioCiudad': employer_ne.get('Emp_MunicipioCiudad', ''),
                'Direccion': employer_ne.get('Emp_Direccion', ''),
            },
            # Trabajador
            'Tra': {
                'TipoTrabajador': employee.get('Tra_TipoTrabajador', ''),
                'SubTipoTrabajador':
                    employee.get('Tra_SubTipoTrabajador', ''),
                'AltoRiesgoPension':
                    employee.get('Tra_AltoRiesgoPension', ''),
                'TipoDocumento': employee.get('Tra_TipoDocumento', ''),
                'NumeroDocumento': employee.get('Tra_NumeroDocumento', ''),
                'PrimerApellido': employee.get('Tra_PrimerApellido', ''),
                'SegundoApellido': employee.get('Tra_SegundoApellido', ''),
                'PrimerNombre': employee.get('Tra_PrimerNombre', ''),
                'OtrosNombres': employee.get('Tra_OtrosNombres', ''),
                'LugarTrabajoPais': employee.get('Tra_LugarTrabajoPais', ''),
                'LugarTrabajoDepartamentoEstado':
                    employee.get('Tra_LugarTrabajoDepartamentoEstado', ''),
                'LugarTrabajoMunicipioCiudad':
                    employee.get('Tra_LugarTrabajoMunicipioCiudad', ''),
                'LugarTrabajoDireccion':
                    employee.get('Tra_LugarTrabajoDireccion', ''),
                'SalarioIntegral': employee.get('Tra_SalarioIntegral', ''),
                'TipoContrato': employee.get('Tra_TipoContrato', ''),
                'Sueldo': employee.get('Tra_Sueldo', ''),
                'CodigoTrabajador': employee.get('Tra_CodigoTrabajador', ''),
                'partner_name': employee.get('Tra_partner_name', ''),
                'partner_id': employee.get('Tra_partner_id', ''),
            },
            # Pago TODO
            'Pag': {
                'Forma': '1',
                'Metodo': '31',
                'Banco': '',
                'TipoCuenta': '',
                'NumeroCuenta': '',
            },
            # FechaPagos
            # TODO: validar campo FechaPagos
            'FechaPagos': {
                f'FechaPago_{c.id}': c.liquidation_date for c in nie.filtered(
                    lambda n: n.liquidation_date)
            },
            # #Devengos
            # Basico
            'Dev_Bas_DiasTrabajados':
                '{:.0f}'.format(float(basic_wage['Dev_Bas_DiasTrabajados'])),
            'Dev_Bas_SueldoTrabajado':
                '{:.2f}'.format(float(basic_wage['Dev_Bas_SueldoTrabajado'])),
            # Transporte
            'Dev_Transporte': [sub_trans],
            'Dev_HEDs': hed,
            'Dev_HENs': hen,
            'Dev_HRNs': hrn,
            'Dev_HEDDFs': heddf,
            'Dev_HRDDFs': hrddf,
            'Dev_HENDFs': hendf,
            'Dev_HRNDFs': hrndf,
            # Vacaciones
            'Dev_Vacaciones': holidays,
            # Primas
            'Dev_Pri_Cantidad': prima['Dev_Pri_Cantidad'],
            'Dev_Pri_Pago': prima['Dev_Pri_Pago'],
            'Dev_Pri_PagoNS': prima['Dev_Pri_PagoNS'],
            # Cesantias
            'Dev_Ces_Pago': ces['Dev_Ces_Pago'],
            'Dev_Ces_Porcentaje': ces['Dev_Ces_Porcentaje'],
            'Dev_Ces_PagoIntereses': ces['Dev_Ces_PagoIntereses'],
            # Incapacidades
            'Dev_Incapacidades': inabilitys,
            # Licencias
            'Dev_Licencias': licenses,
            # # Bonificaciones
            'Dev_Bonificaciones': bonds,
            # Auxilios
            'Dev_Auxilios': aids,
            # HuelgasLegales
            'Dev_HuelgasLegales': [
                # {'FechaInicio': '',  # TODO
                # 'FechaFin': '',
                # 'Cantidad': ''}
            ],
            # OtrosConceptos
            'Dev_OtrosConceptos': oconcepts,
            # Compensaciones
            'Dev_Compensaciones': compensations,
            # BonoEPCTVs
            'Dev_BonoEPCTVs': epctvs,
            # Comisiones
            'Dev_Comisiones': commissions,
            # PagosTerceros
            'Dev_PagosTerceros': dev_partners,
            # Anticipos
            'Dev_Anticipos': dev_advances,

            'Dev_Dotacion': dotation,
            'Dev_ApoyoSost': sus_support,
            'Dev_Teletrabajo': telew,
            'Dev_BonifRetiro': bonret,
            'Dev_Indemnizacion': indem,
            'Dev_Reintegro': dev_return,
            # # Deducciones
            # Salud
            'Ded_Salud_Porcentaje': deduction_health['Ded_Salud_Porcentaje'],
            'Ded_Salud_Deduccion': deduction_health['Ded_Salud_Deduccion'],
            # FondoPension
            'Ded_FoPen_Porcentaje': deduction_pension['Ded_FoPen_Porcentaje'],
            'Ded_FoPen_Deduccion': deduction_pension['Ded_FoPen_Deduccion'],
            # FondoSP
            'Ded_FoSP_Porcentaje': 
                deduction_solidarity['Ded_FoSP_Porcentaje'],
            'Ded_FoSP_Deduccion': deduction_solidarity['Ded_FoSP_Deduccion'],
            'Ded_FoSP_PorcentajeSub': 
                deduction_subsistence['Ded_FoSP_PorcentajeSub'],
            'Ded_FoSP_DeduccionSub': 
                deduction_subsistence['Ded_FoSP_DeduccionSub'],
            # Sindicatos
            'Ded_Sindicatos': [
                # {'Porcentaje': '',  # TODO
                #  'Deduccion': ''}
            ],
            # Sanciones
            'Ded_Sanciones': sanctions,
            # Libranzas
            'Ded_Libranzas': prommissory,
            # PagosTerceros
            'Ded_PagosTerceros': ded_partners,
            # Anticipos
            'Ded_Anticipos': ded_advances,
            # OtrasDeducciones
            'Ded_OtrasDeducciones': odeductions,
            # #
            'Ded_PensionVoluntaria': vol_pension,
            'Ded_RetencionFuente': deduction_retfte,
            'Ded_AFC': afc,
            'Ded_Cooperativa': coop,
            'Ded_EmbargoFiscal': tax_emb,
            'Ded_PlanComplementarios': comp_plan,
            'Ded_Educacion': education,
            'Ded_Reintegro': ded_return,
            'Ded_Deuda': debt,
            # #
            'Redondeo': '2.00',  # TODO
            'DevengadosTotal': ingen.get('ValDev'),
            'DeduccionesTotal': ingen.get('ValDed'),
            'ComprobanteTotal': ingen.get('ValTolNE'),
        }

    def _get_values_niae_e(self, type_doc):
        self.ensure_one()
        nie = self.payslip_ids
        company = self.company_id
        workplace = nie._build_workplace()
        employer_ne = nie._build_employer_ne()
        notes = nie._get_notes_edi_hr()
        werte = self._datenwerte_erhalten(type_doc)
        out = {
            'TipoNota': 2,
            # EliminandoPredecesor
            'ElPre': {
                'NumeroPred': self.edi_zahl_origin,
                'CUNEPred': self.edi_cune_origin,
                'FechaGenPred': self.edi_gen_datum_origin,
            },
            # NumeroSecuenciaXML
            'NSX': {
                'Prefijo': ingen.get('prefix'),
                'Consecutivo': ingen.get('number'),
                'Numero': ingen.get('NumNE'),
            },
            # LugarGeneracionXML
            'LGX': {
                'Pais': workplace['LGX_Pais'],
                'DepartamentoEstado': workplace['LGX_DepartamentoEstado'],
                'MunicipioCiudad': workplace['LGX_MunicipioCiudad'],
                'Idioma': workplace['LGX_Idioma'],
            },
            # ProveedorXML
            'PrX': {
                'RazonSocial': company.name, #'OdOne S.A.S',
                'PrimerApellido': '',
                'SegundoApellido': '',
                'PrimerNombre': '',
                'OtrosNombres': '',
                'NIT': company.partner_id.vat, #'901361603',
                'DV': company.partner_id.l10n_co_verification_code, # '8',
                'SoftwareID': ingen.get('IdSoft'),
                'SoftwareSC': ingen.get('ssc'),
            },
            # CodigoQR
            'CodigoQR': ingen.get('qr_data_url'),
            # InformacionGeneral
            'IGe': {
                'Version': ingen.get('version'),
                'Ambiente': ingen.get('TipAmb'),
                'TipoXML': ingen.get('TipoXML'),
                'CUNE': ingen.get('cune'),
                'EncripCUNE': 'CUNE-SHA384',
                'FechaGen': ingen.get('FecNE'),
                'HoraGen': ingen.get('HorNE'),
            },
            # Notas
            'Notas': notes,
            # Empleador
            'Emp': {
                'RazonSocial': employer_ne.get('Emp_RazonSocial', ''),
                'PrimerApellido': employer_ne.get('Emp_PrimerApellido', ''),
                'SegundoApellido': employer_ne.get('Emp_SegundoApellido', ''),
                'PrimerNombre': employer_ne.get('Emp_PrimerNombre', ''),
                'OtrosNombres': employer_ne.get('Emp_OtrosNombres', ''),
                'NIT': employer_ne.get('Emp_NIT', ''),  # NitNE,
                'DV': employer_ne.get('Emp_DV', ''),
                'Pais': employer_ne.get('Emp_Pais', ''),
                'DepartamentoEstado':
                    employer_ne.get('Emp_DepartamentoEstado', ''),
                'MunicipioCiudad': employer_ne.get('Emp_MunicipioCiudad', ''),
                'Direccion': employer_ne.get('Emp_Direccion', ''),
            },
        }
        werte = dict(werte, **out)
        return werte
        
    def _get_values_niae_r(self, type_doc):
        self.ensure_one()
        nie = self.payslip_ids
        self._concept_config_validation()
        werte = self._datenwerte_erhalten(type_doc)
        out = {
            'TipoNota': 1,
            # ReemplazandoPredecesor
            'RePre':{
                'NumeroPred': self.edi_zahl_origin,
                'CUNEPred': self.edi_cune_origin,
                'FechaGenPred': self.edi_gen_datum_origin,
            },
            # 'IGe_TipoXML': '102',
        }
        werte = dict(werte, **out)
        return werte

    def qrcode_erhalten(
        self, NumNE, FecNE, HorNE, TipoNota, NitNE,
        DocEmp, ValDev, ValDed, ValTol, CUNE, TipAmb):
        '''
            QR
        '''
        url = TipAmb == '1' and URL_CUNE['prod'] or URL_CUNE['hab']
        url = url.replace('CUNE', CUNE)
        txt_qr = ''
        txt_qr += 'NumNIE: {}'.format(NumNE and NumNE or '')
        txt_qr += '\nFecNIE: {}'.format(FecNE and FecNE or '')
        txt_qr += '\nHorNIE: {}'.format(HorNE and HorNE or '')
        if TipoNota:
            txt_qr += '\nTipoNota: {}'.format(TipoNota and TipoNota or '')
        txt_qr += '\nNitNIE: {}'.format(NitNE and NitNE or '')
        txt_qr += '\nDocEmp: {}'.format(DocEmp and DocEmp or '')
        txt_qr += '\nValDev: {:.2f}'.format(float(ValDev))
        txt_qr += '\nValDed: {:.2f}'.format(float(ValDed))
        txt_qr += '\nValTol: {:.2f}'.format(float(ValTol))
        txt_qr += '\nCUNE: {}'.format(CUNE and CUNE or '')
        txt_qr += '\nQRCode: {}'.format(url)

        img_qr = satz.qrcode_erzeugen(txt_qr)
        return {
            'img_qr': img_qr,
            'txt_qr': txt_qr,
            'url_cune': url
        }

    def gehaltsabrechnung_senden(self):
        self.ensure_one()
        msg1 = 'msg1'
        msg2 = 'msg2'
        b = "http://schemas.datacontract.org/2004/07/UploadDocumentResponse"
        wsdl = DIAN['wsdl-hab']
        anfrageart = 'SendTestSetAsync'
        exe_env = self.company_id.hr_target_environment
        if exe_env == '1':
            anfrageart = 'SendNominaSync'
            wsdl = DIAN['wsdl']
        anfrage = self._bring_anfrage_unterzeichnet(exe_env, wsdl, 'senden')
        try:
            antwort = post(
                wsdl,
                headers={
                    'content-type': 'application/soap+xml;charset=utf-8'
                },
                data=anfrage
            )
            if antwort.status_code == 200:
                daten_antwort = satz.datenantwort_erhalten(antwort)
                self.write({'state': 'gesendet'})
                self.versandlog_erstellen(anfrageart, daten_antwort, anfrage, exe_env)
                if exe_env == '1':
                    self.die_antwort_verarbeiten(
                        daten_antwort,
                        exe_env=exe_env)
                else:
                    self.write({
                        'edi_zip_key': daten_antwort.get('zipkey', 'Error'),
                        # 'state': 'sent'
                        })
                    self.zip_status_erhalten()
            elif antwort.status_code in (500, 503, 507):
                self.write({'state': 'fehler'})
                self.versandlog_erstellen(
                    anfrageart, 
                    {
                        'status_code': antwort.status_code,
                        'reason': antwort.reason,
                        'response_text': antwort.text.replace('><', '>\n<'),
                    },
                    anfrage,
                    exe_env
                )
            else:
                raise ValidationError(_(
                    'Error en método %s. \n\n'
                    '%s.\n%s'
                    ) % (anfrageart, antwort.status_code, antwort.reason)
                )
        except exceptions.RequestException as e:
            raise ValidationError(_(
                'Error desconocido en método %s. \n\n%s'
                ) % (anfrageart, e)
            )
        return True

    def _bring_anfrage_unterzeichnet(self, exe_env, wsdl, art):
        self.ensure_one()

        if exe_env == '1':
            if art == 'senden':
                SendBillAsync_values = self._get_SendNominaSync_values()
                SendBillAsync_values['To'] = wsdl.replace('?wsdl', '')
                signiert_xml = satz.get_xml_soap_with_signature(
                    satz.render_xml_edi(
                        SendBillAsync_values,
                        'SendNominaSync'
                    ),
                    SendBillAsync_values['Id'],
                    self.company_id.hr_certificate_file,
                    self.company_id.hr_certificate_password
                )
                _logger.error('********************** SendNominaSync')
            elif art == 'abfrage':
                GetStatus_values = self._get_GetStatus_values()
                GetStatus_values['To'] = wsdl.replace('?wsdl', '')
                signiert_xml = satz.get_xml_soap_with_signature(
                    satz.render_xml_edi(
                        GetStatus_values,
                        'GetStatus'
                    ),
                    GetStatus_values['Id'],
                    self.company_id.hr_certificate_file,
                    self.company_id.hr_certificate_password
                )
                _logger.error('********************** GetStatus')
        else:
            if art == 'senden':
                SendTestSetAsync_values = self._get_SendTestSetAsync_values()
                SendTestSetAsync_values['To'] = wsdl.replace('?wsdl', '')
                signiert_xml = satz.get_xml_soap_with_signature(
                    satz.render_xml_edi(
                        SendTestSetAsync_values,
                        'SendTestSetAsync'
                    ),
                    SendTestSetAsync_values['Id'],
                    self.company_id.hr_certificate_file,
                    self.company_id.hr_certificate_password
                )
                _logger.error('********************** SendTestSetAsync')
            elif art == 'abfrage':
                GetStatusZip_values = self._get_GetStatusZip_values()
                GetStatusZip_values['To'] = wsdl.replace('?wsdl', '')
                signiert_xml = satz.get_xml_soap_with_signature(
                    satz.render_xml_edi(
                        GetStatusZip_values,
                        'GetStatusZip'
                    ),
                    GetStatusZip_values['Id'],
                    self.company_id.hr_certificate_file,
                    self.company_id.hr_certificate_password
                )
                _logger.error('********************** GetStatusZip')
        signiert_xml = etree.tostring(
            signiert_xml,
            encoding="unicode"
        )
        return signiert_xml
    
    def _xml_soap_werte_erhalten(self):
        return satz.get_xml_soap_values(
            self.company_id.hr_certificate_file,
            self.company_id.hr_certificate_password
        )
    
    def _get_SendNominaSync_values(self):
        xml_soap_werte = self._xml_soap_werte_erhalten()
        xml_soap_werte['fileName'] = self.edi_zip_fname
        xml_soap_werte['contentFile'] = \
            self.edi_zip_file.decode("utf-8", "ignore")
        return xml_soap_werte

    def _get_SendTestSetAsync_values(self):
        xml_soap_werte = self._get_SendNominaSync_values()
        xml_soap_werte['testSetId'] = self.company_id.hr_test_set_id
        return xml_soap_werte
    
    def _get_GetStatusZip_values(self):
        xml_soap_werte = self._xml_soap_werte_erhalten()
        xml_soap_werte['trackId'] = self.edi_zip_key
        return xml_soap_werte
    
    def _get_GetStatus_values(self):
        xml_soap_werte = self._xml_soap_werte_erhalten()
        xml_soap_werte['trackId'] = self.edi_cune
        return xml_soap_werte

    def zip_status_erhalten(self):
        self.ensure_one()
        wsdl = DIAN['wsdl-hab']
        exe_env = self.company_id.hr_target_environment
        if exe_env == '1':
            wsdl = DIAN['wsdl']
        anfrage = self._bring_anfrage_unterzeichnet(exe_env, wsdl, 'abfrage')
        
        antwort = post(
            wsdl,
            headers={'content-type': 'application/soap+xml;charset=utf-8'},
            data=anfrage
        )
        if antwort.status_code == 200:
            daten_antwort = satz.datenantwort_erhalten(antwort)
            self.die_antwort_verarbeiten(
                daten_antwort,
                exe_env=exe_env
            )
            self.versandlog_erstellen(
                'GetStatusZip',
                daten_antwort,
                anfrage,
                exe_env
            )
        else:
            raise ValidationError(_(
                'Error en método GetStatusZip. \n'
                '%s \n%s'
                ) % (antwort.status_code, antwort.reason)
            )
        return True

    def versandlog_erstellen(self, anfrageart, daten_antwort, anfrage, exe_env):
        self.ensure_one()
        name = str(len(self.edi_log_ids) + 1)
        self.env['edi.hr.log'].create(
            {
                'name': 'log %s' % name,
                'type_request': anfrageart,
                'edi_hr_id': self.id,
                'status_code': daten_antwort.get('status_code', 'ERROR'),
                'reason': daten_antwort.get('reason','ERROR'),
                'response': daten_antwort.get('response_text', 'ERROR').replace('><', '>\n<'),
                'exec_env': exe_env,
                'edi_request_fname': 'Request %s.xml' % name,
                'edi_request_file': b64encode(anfrage.encode())
            }
        )

    def die_antwort_verarbeiten(self, antwort, exe_env):
        url = ''
        zustand_kod = antwort.get('zustand_kod', 'other')
        zustand_dok = zustand_kod == '00' and 'richtig' \
                    or zustand_kod == '99' and 'abgelehnt' \
                    or zustand_kod in ('66', '90') and 'fehler' \
                    or not zustand_kod and antwort.get('fehlerliste') and 'abgelehnt' \
                    or False
        bild = ' \n'.join(
            list(filter(
                lambda x: x,
                [
                    antwort.get('zustand_beschreiben', ''),
                    antwort.get('zustand_nachricht', ''),
                    ''.join([
                        '\n- %s.' % f for f in antwort.get('fehlerliste', [])
                    ])
                ]
            ))
        )
        if not bild:
            bild = antwort.get('response_text', '').replace('><', '>\n<')

        edi_ar_file = antwort.get('xml_base64')
        cune = antwort.get('xml_dokument_schlussel')
        if cune:
            url = exe_env == '1' and URL_CUNE['prod'] or URL_CUNE['hab']
            url = url.replace('CUNE', cune)
        
        to_write = {
            'hr_edi_state': zustand_kod,
            'hr_edi_response': bild
        }
        if zustand_dok:
            to_write['state'] = zustand_dok
        if edi_ar_file:
            to_write['edi_ar_file'] = edi_ar_file
        if cune:
            to_write['edi_cune'] = cune
        if url:
            to_write['edi_url'] = url
        self.write(to_write)
        return True

    def status_erhalten(self):
        self.ensure_one()
        wsdl = DIAN['wsdl-hab']
        exe_env = self.company_id.hr_target_environment
        if exe_env == '1':
            wsdl = DIAN['wsdl']
        anfrage = self._bring_anfrage_unterzeichnet(exe_env, wsdl, 'abfrage')

        antwort = post(
            wsdl,
            headers={'content-type': 'application/soap+xml;charset=utf-8'},
            data=anfrage
        )
        if antwort.status_code == 200:
            daten_antwort = satz.datenantwort_erhalten(antwort)
            self.die_antwort_verarbeiten(
                daten_antwort,
                exe_env=exe_env
            )
            self.versandlog_erstellen(
                'GetStatus',
                daten_antwort,
                anfrage,
                exe_env
            )
        else:
            raise ValidationError(_(
                'Error en método GetStatus. \n'
                '%s \n%s'
                ) % (antwort.status_code, antwort.reason)
            )
        return True

    def _codegen(self, doc=False, nie=False, type_doc='', total_earnings=0, total_deductions=0):
        # if not doc or not nie:
        #     raise ValidationError(_(
        #         'Se requiere el %s para generar el CUNE y '
        #         'Código de seguridad del software.'
        #     ) % 'documento de nómina electrónica' if not doc \
        #         else 'documento de nómina')
        seq_obj = self.env['ir.sequence']
        net_earned = total_earnings - total_deductions
        if total_deductions > total_earnings and nie._has_vacation_lines():
            net_earned = 0.0

        datetime_actual = self.create_date.astimezone(timezone('America/Bogota'))
        # fields.Datetime.context_timestamp(
        #     self,
        #     datetime.now()
        # )
        seq_code = type_doc.replace('_', '.')
        num = self.edi_zahl and self.edi_zahl or seq_obj.next_by_code(seq_code)
        if '-' in num:
            prefix = num.split('-')[0]
            number = int(num.split('-')[1])
        else:
            prefix = ''.join([x for x in num if not x.isdigit()])
            number = int(''.join([x for x in num if x.isdigit()]))
        if type_doc == 'niae_e':
            total_earnings = 0.0
            total_deductions = 0.0
            net_earned = total_earnings - total_deductions
        employee_id = nie.employee_id and nie.employee_id \
            or nie.contract_id.employee_id

        NumNE = '%s%s' % (
            prefix,
            str(number)
        )
        FecNE = datetime_actual.strftime('%Y-%m-%d')
        HorNE = datetime_actual.strftime('%H:%M:%S%Z:00')
        ValDev = '{:.2f}'.format(total_earnings)
        ValDed = '{:.2f}'.format(total_deductions)
        ValTolNE = '{:.2f}'.format(net_earned)
        NitNE = nie.company_id.partner_id.vat or ''
        DocEmp = employee_id.identification_id \
                 if type_doc != 'niae_e' else '0'
        TipoXML = type_doc == 'nie' and '102' or '103'
        SoftPIN = nie.company_id.hr_software_pin or ''
        TipAmb = nie.company_id.hr_target_environment or '2'
        IdSoft = nie.company_id.hr_software_id or ''
        cune = satz.cune_erhalten(
            NumNE, FecNE, HorNE, ValDev, ValDed, ValTolNE,
            NitNE, DocEmp, TipoXML, SoftPIN, TipAmb
        )
        ssc = satz.ssc_erhalten(
            IdSoft, SoftPIN, NumNE
        )
        qr_data = self.qrcode_erhalten(
            NumNE, FecNE, HorNE, False,
            NitNE, DocEmp, ValDev, ValDed,
            ValTolNE, cune['CUNE'], TipAmb
        )
        version = type_doc == 'nie' and \
            'V1.0: Documento Soporte de Pago de Nómina Electrónica' or \
            'V1.0: Nota de Ajuste de Documento Soporte de Pago de Nómina Electrónica'
            
        werte = {
            'version': version,
            'prefix': prefix,
            'number': number,
            'NumNE': NumNE,
            'FecNE': FecNE,
            'HorNE': HorNE,
            'ValDev': ValDev,
            'ValDed': ValDed,
            'ValTolNE': ValTolNE,
            'NitNE': NitNE,
            'DocEmp': DocEmp,
            'TipoXML': TipoXML,
            'SoftPIN': SoftPIN,
            'TipAmb': TipAmb,
            'IdSoft': IdSoft,
            'cune': cune.get('CUNE'),
            'cune_uncoded': cune.get('CUNEUncoded'),
            'ssc': ssc.get('SSC'),
            'ssc_uncoded': ssc.get('SSC_Uncoded'),
            'qr_data_img': qr_data.get('img_qr'),
            'qr_data_txt': qr_data.get('txt_qr'),
            'qr_data_url': qr_data.get('url_cune'),
        }
        self.write({
            'edi_zahl': werte.get('NumNE'),
            'edi_datum': datetime_actual,
            'edi_qr_image': werte.get('qr_data_img'),
            'edi_cune': werte.get('cune'),
            'edi_cune_uncode': werte.get('cune_uncoded'),
            'edi_ssc': werte.get('ssc'),
            'edi_ssc_uncode': werte.get('ssc_uncoded'),
            'edi_url': werte.get('qr_data_url')
        })
        return werte

    def _massenabrechnungs_xml_generieren(self, docs):
        edi_doc_obj = self.env['edi.hr.document']
        werte = []
        for doc in docs:
            if doc.edi_doc_ids:
                raise ValidationError(
                    _('La nómina %s ya tiene documentos electrónicos. \n'
                      'Por favor, verifique el documento.', doc.name))
            wert = {
                'payslip_id': doc.id,
                'company_id': doc.company_id.id,
                'edi_type': 'nie',
                'to_send': True,
                'to_check_status': True
            }
            werte.append(wert)
        edi_doc_ids = edi_doc_obj.create(werte)
        print("DOCS ****************", edi_doc_ids)
        for doc in edi_doc_ids:
            try:
                doc.xml_datei_erhalten()
            except Exception as error:
                raise ValidationError(_(
                    'Ocurrió un error generando el documento electrónico '
                    'de la nómina "%s": \n\nError:\n%s'
                ) % (
                    doc.payslip_id.name,
                    str(error)
                ))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Edi HR Documents'),
            'res_model': 'edi.hr.document',
            'view_mode': 'list,form',
            'domain': [('id','in',edi_doc_ids.ids)],
            'context': {},
            'target': 'current',
        }
    
    # Validieren

    def _xml_daten_validieren(self, werte, type_doc):
        msg = ''
        msg += self._xml_NSX_validieren(werte.get('NSX', {}))
        msg += self._xml_LGX_validieren(werte.get('LGX', {}))
        msg += self._xml_PrX_validieren(werte.get('PrX', {}))
        msg += self._xml_CodigoQR_validieren(werte.get('CodigoQR', {}))
        msg += self._xml_IGe_validieren(werte.get('IGe', {}))
        msg += self._xml_Emp_validieren(werte.get('Emp', {}))
        if type_doc == 'nie':
            msg += self._xml_Per_validieren(werte.get('Per', {}))
            msg += self._xml_Tra_validieren(werte.get('Tra', {}))
            msg += self._xml_Pag_validieren(werte.get('Pag', {}))
        elif type_doc == 'niae_r':
            msg += self._xml_ElPre_validieren(werte.get('ElPre', {}))
        else:
            msg += self._xml_ElPre_validieren(werte.get('ElPre', {}))

        if msg:
            raise ValidationError(msg)

    def _xml_NSX_validieren(self, werte):
        msg = ''
        # 
        # msg += '\n- Esto es una prueba de error\n- linea2'
        return msg

    def _xml_LGX_validieren(self, werte):
        msg = ''
        # 
        return msg
        
    def _xml_PrX_validieren(self, werte):
        msg = ''
        # 
        return msg
        
    def _xml_CodigoQR_validieren(self, werte):
        msg = ''
        # 
        return msg
        
    def _xml_IGe_validieren(self, werte):
        msg = ''
        # 
        return msg
        
    def _xml_Emp_validieren(self, werte):
        msg = ''
        # 
        if not werte.get('NIT', False):
            msg += _('\n- Número de identificación (NIT)')
        if msg:
            msg = _('\n--> Datos incorrectos del empleador "%s":', 
                    werte.get('RazonSocial', '')) + msg
        return msg
        
    def _xml_Per_validieren(self, werte):
        msg = ''
        # 
        return msg
        
    def _xml_Tra_validieren(self, werte):
        msg = ''
        # 
        if not werte.get('NumeroDocumento', False):
            msg += _('\n- Número de identificación')
        if not werte.get('TipoTrabajador', False):
            msg += _('\n- Tipo de cotizante en el contrato')
        if msg:
            msg = _('\n--> Datos incorrectos del empleado "%s (Id: %s)":', 
                    werte.get('partner_name', '**'),
                    werte.get('partner_id', '**')) + msg
        return msg
        
    def _xml_Pag_validieren(self, werte):
        msg = ''
        # 
        return msg
        
    def _xml_ElPre_validieren(self, werte):
        msg = ''
        # 
        return msg
        
    def _xml_ElPre_validieren(self, werte):
        msg = ''
        # 
        return msg
    
    def _concept_config_validation(self, nie=False):
        if not nie:
            nie = self.payslip_ids
        msg = ''
        noveltys = nie.payslip_line_ids.filtered(lambda n:
            n.novelty_id and not n.novelty_id.novelty_type_id.dian_concept_id)
        concepts = nie.payslip_line_ids.filtered(lambda c:
            c.concept_id and not c.concept_id.dian_concept_id)
        overtimes = nie.payslip_line_ids.filtered(lambda n:
            n.overtime_id and not n.overtime_id.overtime_type_id.dian_concept_id)
        if noveltys:
            novelty_ids = noveltys.mapped('novelty_id.novelty_type_id')
            msg += _('\n--> Las siguientes CATEGORÍAS DE NOVEDAD no tienen concepto DIAN:%s',
                     ''.join(['\n    - %s (id: %s)' % (n.display_name, n.id) for n in novelty_ids]))
        if concepts:
            concept_ids = concepts.mapped('concept_id')
            msg += _('\n--> Los siguientes CONCEPTOS DE NÓMINA no tienen concepto DIAN:%s',
                     ''.join(['\n    - %s (id: %s)' % (n.display_name, n.id) for n in concept_ids]))
        if overtimes:
            overtime_ids = noveltys.mapped('overtime_id.overtime_type_id')
            msg += _('\n--> Las siguientes CATEGORÍAS DE HORAS EXTRA no tienen concepto DIAN:%s',
                     ''.join(['\n    - %s (id: %s)' % (n.display_name, n.id) for n in overtime_ids]))
        if msg:
            raise ValidationError(msg)
            

    # MASSIV

    def _an_edi_hr_dokumenten_senden(self, num_docs=0):
        _logger.error("MASSIV SENDEN: Start")
        cr = Registry(self._cr.dbname).cursor()
        self = self.with_env(self.env(cr=cr))

        edi_doc_obj = self.env['edi.hr.document']
        edi_doc_ids = edi_doc_obj.search(
            [
                ('state','=','neu'),
                ('to_send','=',True)
            ],
            limit=num_docs
        )
        try:
            for doc in edi_doc_ids:
                try:
                    doc.gehaltsabrechnung_senden()
                    doc.to_send = False
                    self._cr.commit()
                except Exception as error:
                    _logger.error("MASSIV SENDEN: ERROR")
                    tb = traceback.format_tb(sys.exc_info()[2], 10)
                    _logger.error(''.join(tb))
                    self._cr.rollback()
        finally:
            try:
                self._cr.close()
            except Exception:
                pass
        _logger.error("MASSIV SENDEN: End")

    def _edi_hr_dokumenten_status_erhalten(self, num_docs=0):
        _logger.error("MASSIV STATUS: Start")
        cr = Registry(self._cr.dbname).cursor()
        self = self.with_env(self.env(cr=cr))

        edi_doc_obj = self.env['edi.hr.document']
        edi_doc_ids = edi_doc_obj.search(
            [
                ('state','=','gesendet'),
                ('to_check_status','=',True)
            ],
            limit=num_docs
        )
        try:
            for doc in edi_doc_ids:
                try:
                    doc.status_erhalten()
                    doc.to_check_status = False
                    self._cr.commit()
                except Exception:
                    _logger.error("MASSIV STATUS: ERROR")
                    tb = traceback.format_tb(sys.exc_info()[2], 10)
                    _logger.error(''.join(tb))
                    self._cr.rollback()
        finally:
            try:
                self._cr.close()
            except Exception:
                pass
        _logger.error("MASSIV STATUS: End")
