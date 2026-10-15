# -*- coding: utf-8 -*-

from odoo import fields, models, _, api
from odoo.exceptions import UserError


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    consignment_ids = fields.One2many('consignment.data',
                                      'move_line_id',
                                      'Registro remesas')
    consignment_txt = fields.Char('Remesas',
                                  compute='compute_consignment_txt')
    fe_mandante_id = fields.Many2one('res.partner',
                                'Mandante')
    # consignment_m_ids = fields.Many2many('consignment.data',
    #                                    'move_line_consignment_rel',
    #                                    'line_id', 'consignment_id',
    #                                   'Registro remesas',
    #                                   ondelete='cascade')

    # button_consignment = fields.Boolean('Remesas!')
    
    # @api.depends('button_consignment')
    # def onchange_button(self):
    #     action = {
    #         'name': _('Registro de remesas'),
    #         'type': 'ir.actions.act_window',
    #         'res_model': 'account.move.line',
    #         'view_mode': 'form',
    #         'view_id': self.env.ref('l10n_co_bloodo.aml_consignment_data_form_view').id,
    #         'res_id': self.id,
    #         # 'context': {'editable': 'bottom'},
    #         'target': 'new'
    #     }
    #     action1 = {
    #         'name': _('Registro de remesas'),
    #         'type': 'ir.actions.act_window',
    #         'res_model': 'consignment.data',
    #         'view_mode': 'tree,form',
    #         # 'view_id': self.env.ref('l10n_co_bloodo.aml_consignment_data_form_view').id,
    #         # 'res_id': self.id,
    #         'context': {'default_move_line_id': self.id},
    #         'target': 'new'
    #     }
    #     print(action)
    #     self.add_consignment()
    #     return action
    #     # return {'action': action}

    def _copy_data_extend_business_fields(self, values):
        super(AccountMoveLine, self)._copy_data_extend_business_fields(values)
        if self.consignment_ids:
            new_consignment_ids = self.env['consignment.data']
            for cons_id in self.consignment_ids:
                new_consignment_ids |= cons_id.copy()
            values['consignment_ids'] = [(6, None, new_consignment_ids.ids)]
    
    def compute_consignment_txt(self):
        for record in self:
            txt = ''
            if record.consignment_ids:
                for y in record.consignment_ids:
                    txt += 'Tipo servicio: {type}\n' \
                            'Radicado remesa: {rndc}\n' \
                            'Número remesa: {numr}\n' \
                            'Flete: {valf}\n' \
                            'Cantidad: {qty} {udm}\n' \
                            'Orden de compra: {oref}\n\n'.format(
                                type=y.transport_rec or '',
                                rndc=y.rndc_id or '',
                                numr=y.consignment_id or '',
                                valf=y.freight,
                                qty=y.quantity,
                                udm=y.udm or '',
                                oref=y.order_ref or ''
                            )
            record.consignment_txt = txt and txt or 'Sin remesa'

    # @api.model
    def add_consignment(self):
        self.ensure_one()
        action = {
            'name': _('Registro de remesas'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.line',
            'view_mode': 'form',
            'view_id': self.env.ref('l10n_co_bloodo.aml_consignment_data_form_view').id,
            'res_id': self.id,
            # 'context': {'editable': 'bottom'},
            'target': 'new'
        }
        return action

    def _get_product_standard_code(self):
        '''
            For identifying products, different standards can be used.
            If there is a barcode, we take that one, because normally in the
            GTIN standard it will be the most specific one.'
            Otherwise, we will check the
            :return: (standard, product_code)
        '''
        self.ensure_one()
        code = []
        if self.product_id:
            if self.move_id.fe_type == '02' and self.product_id.dian_customs_code:
                # if not self.product_id.dian_customs_code:
                #     raise UserError(
                #         _('Las facturas de exportación requieren un código '
                #           'aduanero en todos los productos, complete esta '
                #           'información antes de validar la factura.'))
                code = [self.product_id.dian_customs_code, '020',
                        '195', 'Partida Arancelarias']
            elif self.product_id.barcode:
                code = [self.product_id.barcode, '010', '9', 'GTIN']
            elif self.product_id.dian_unspsc_id:
                code = [self.product_id.dian_unspsc_id.code, '001',
                        '10', 'UNSPSC']
            elif self.product_id.default_code:
                code = [self.product_id.default_code, '999', '',
                        'Estándar de adopción del contribuyente']
        if not code:
            code = ['NA', '999', '',
                    'Estándar de adopción del contribuyente']
        return {'ID': code[0],
                'schemeID': code[1],
                'schemeAgencyID': code[2],
                'schemeName': code[3]}

    def _get_information_content_provider_party_values(self):
        return {
            'IDschemeID': False,
            'IDschemeName': False,
            'ID': False}

    def _get_taxes_line_edi(self, dict_tax, tax, rate, tax_section, doc='fe'):

        tax_code = tax.dian_tax_type_id.dian_code
        tax_name = tax.dian_tax_type_id.name
# TODO: Validar si tambien aplica para retenciones
        if doc == 'ds' and tax_code not in ('01', '05', '06'):
            tax_code = 'ZZ'
            tax_name = 'No aplica'

        if tax_code == '34':
            tax_data = tax._get_tax_details(
                price_unit=self.price_unit,
                quantity=self.quantity,
                product=self.product_id
            )
            tax_amount = tax_data.get('taxes_data', [])[0].get('tax_amount')
            base_unit = self.product_id.dian_nominal_tax * self.quantity
            per_unit = tax_amount * 100 / base_unit
            tax_amount_str = '{:.2f}'.format(per_unit)
        else:
            tax_amount = abs(tax.amount)
            base_unit = 0
            per_unit = 0

            num_decimal = self._get_qty_decimal_part(tax_amount)
            tax_amount_str = num_decimal < 3 \
                and '{:.2f}'.format(float(tax_amount)) \
                    or '{:.3f}'.format(float(tax_amount))

        if tax_code not in dict_tax:
            dict_tax[tax_code] = {'total': 0,
                                  'name': tax_name,
                                  'taxes': {},}

        if tax_amount_str not in dict_tax[tax_code]['taxes']:
            dict_tax[tax_code]['taxes'][tax_amount_str] = {'base': 0,
                                                           'amount': 0,
                                                           'base_unit': 0,
                                                           'per_unit': 0,}
        # HEADER
        if tax_section == 'header':
            if tax_code == '34':
                base_amount = base_unit
                total_head = tax_amount
                dict_tax[tax_code]['taxes'][tax_amount_str]['base_unit'] += base_unit
                dict_tax[tax_code]['taxes'][tax_amount_str]['per_unit'] += per_unit
            else:
                percent_base = self._get_percent_base_tax(tax)
                base_amount = self.tax_base_amount * percent_base / 100 # / rate
                total_head = round(base_amount * tax_amount / 100, 2)

            dict_tax[tax_code]['total'] += total_head
            dict_tax[tax_code]['taxes'][tax_amount_str]['base'] += base_amount
            dict_tax[tax_code]['taxes'][tax_amount_str]['amount'] += total_head
        # LINEA
        if tax_section == 'item':
            if tax_code == '34':
                base_amount = base_unit
                total_line = tax_amount
                dict_tax[tax_code]['taxes'][tax_amount_str]['base_unit'] += base_unit
                dict_tax[tax_code]['taxes'][tax_amount_str]['per_unit'] += per_unit
            else:
                subtotal = (self.price_subtotal or (self.price_unit * self.quantity)) * rate
                percent_base = self._get_percent_base_tax(tax)
                base_amount = subtotal * percent_base / 100
                total_line = round(base_amount * tax_amount / 100, 2)

            dict_tax[tax_code]['total'] += total_line
            dict_tax[tax_code]['taxes'][tax_amount_str]['base'] += base_amount
            dict_tax[tax_code]['taxes'][tax_amount_str]['amount'] += total_line

        return dict_tax

    def _get_qty_decimal_part(self, num=0):
        str_num = str(num)
        if '.' in str_num:
            decimal = str_num.split('.')[1]
            return len(decimal)
        else:
            return 0

    def _get_percent_base_tax(self, tax_id):
        rep_line_ids = tax_id.invoice_repartition_line_ids.filtered(
            lambda z: z.repartition_type == 'tax')
        out = 100
        if rep_line_ids:
            out = rep_line_ids[0].factor_percent
        return out

    def _scheme_id_abrufen(self):
        '''
            Tipo operacion: 11 (Mandatos)
                '0' --> B/S ingreso propio
                '1' --> B/S Ingresos Recibidos para Terceros
            Tipo operacion: 12 (Transporte)
                '0' --> Servicio adicional
                '1' --> Remesa de transporte registrada en el RNDC
        '''
        out = ''
        if self.move_id.fe_operation_type in ('11',):
            if self.product_id and self.product_id.third_party_income:
                out = '1'
            else:
                out = '0'
        elif self.move_id.fe_operation_type in ('12',):
            for s in self.consignment_ids.filtered(lambda x: x.transport_rec):
                out = s.transport_rec or ''
        return out


    def _zeilenattribute_abrufen(self):
        '''
        out:    [
            {'Name': ...,
             'Value': ...,
             'ValueQuantity': ...},
            {...},
            ...
        ]
        '''
        # TODO v1.9: Si tipo operación = 12 (Transporte) 
        #            entonces llamar codigo de la tabla 
        #            13.5.2 Remesa de transporte y 
        #            el valor que corresponda
        out = []
        for s in self.consignment_ids.filtered(lambda x: x.transport_rec == '1'):
            out += [
                {'Name': '01',
                'Value': s.rndc_id},
                {'Name': '02',
                 'Value': s.consignment_id},
                {'Name': '03',
                 'Value': s.freight,
                 'ValueQuantity': s.quantity,
                 'unitCode': s.udm}
            ]
            # if s.order_ref:
            #     out.append({'Name': '04',
            #                 'Value': s.order_ref})
        return out
