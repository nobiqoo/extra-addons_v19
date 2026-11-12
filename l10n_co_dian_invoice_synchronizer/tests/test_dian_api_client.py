# -*- coding: utf-8 -*-
from datetime import date
from unittest.mock import MagicMock

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from ..models.dian_api_client import DIAN_PROTOCOL_PARAM, DianUnexpectedResponse


def _item(cufe, type_name='Factura electrónica'):
    """Item as DIAN returns it (live capture 2026-10-05, trimmed)."""
    return {
        'Id': cufe,
        'DocumentTypeName': type_name,
        'SerieAndNumber': 'FE%s' % cufe,
        'SenderCode': '901778934',
        'SenderName': 'Proveedor',
        'ReceiverCode': '901361603',
        'ReceiverName': 'OD. ONE. S.A.S.',
        'ReceptionDate': '/Date(1786012753432)/',
        'StatusName': 'Aprobado con notificación',
        'RadianStatusName': 'Factura Electrónica',
        'TotalAmount': 83474.07,
    }


def _http(payload):
    response = MagicMock(status_code=200)
    response.json.return_value = payload
    return response


def _html(status=200, location=None):
    """Non-JSON answer (e.g. DIAN's login page) or a redirect."""
    response = MagicMock(status_code=status, text='<html><body>Iniciar sesión</body></html>',
                         url='https://dian/User/Login')
    response.headers = {'Content-Type': 'text/html; charset=utf-8'}
    if location:
        response.headers['Location'] = location
    response.json.side_effect = ValueError('Expecting value')
    return response


def _token_page(data, records_filtered, has_more=False, token=''):
    """Response of the token contract (2026-10-05)."""
    return _http({
        'draw': 0, 'start': 0, 'recordsTotal': records_filtered,
        'recordsFiltered': records_filtered, 'data': data,
        'hasMore': has_more, 'continuationToken': token,
    })


def _block(block_data, records_filtered, token=''):
    """Response of the legacy block contract (2026-09-23)."""
    return _http({
        'draw': 1, 'start': 0, 'recordsTotal': records_filtered,
        'recordsFiltered': records_filtered, 'data': block_data[:1],
        'blockData': block_data, 'continuationToken': token,
    })


@tagged('post_install', '-at_install')
class TestDianApiClient(TransactionCase):

    def _fetch(self, responses, existing=(), protocol=None):
        if protocol:
            self.env['ir.config_parameter'].sudo().set_param(DIAN_PROTOCOL_PARAM, protocol)
        for cufe in existing:
            # Reception outside the synchronized range: duplicates are found by CUFE
            self.env['dian.document'].create({
                'cufe': cufe, 'name': 'FE%s' % cufe, 'reception': '2026-08-07 01:00:00'})
        session = MagicMock()
        session.post.side_effect = responses
        result = self.env['dian.api.client']._get_documents_for_date_range(
            session, 'https://dian', date(2026, 8, 1), date(2026, 8, 6), 'FORM-TOKEN')
        return result, [call.kwargs['data'] for call in session.post.call_args_list]

    # -- token contract ---------------------------------------------------------------

    def test_token_pages_follow_continuation_token(self):
        (documents, discarded, records_filtered, ar_count, errors, protocol), bodies = self._fetch([
            # recordsFiltered is the count of each page in the token contract
            _token_page([_item('A'), _item('EV', 'Application response')], 2, True, 'T1'),
            _token_page([_item('B'), _item('C')], 2),
        ], existing=['C'])
        self.assertEqual(protocol, 'token')
        self.assertEqual([b['ContinuationToken'] for b in bodies], ['', 'T1'])
        for body in bodies:
            self.assertEqual(body['SearchRequested'], 'true')
            self.assertEqual(body['ReferencesType'], '00')
            self.assertEqual(body['StartDate'], '2026-08-01')
            self.assertEqual(body['__RequestVerificationToken'], 'FORM-TOKEN')
            self.assertNotIn('blockIndex', body)
        self.assertEqual([d['cufe'] for d in documents], ['A', 'B'])
        self.assertEqual(discarded, ['C'])
        self.assertEqual(ar_count, 1)
        self.assertEqual(records_filtered, 4)
        self.assertFalse(errors)

    def test_cufe_repeated_across_pages_is_created_once(self):
        (documents, discarded, *_), _bodies = self._fetch([
            _token_page([_item('A')], 1, True, 'T1'),
            _token_page([_item('A'), _item('B')], 2),
        ])
        self.assertEqual([d['cufe'] for d in documents], ['A', 'B'])
        self.assertEqual(discarded, ['A'])

    def test_application_response_by_type_id(self):
        event = dict(_item('EV', 'Evento'), DocumentTypeId='96')
        invoice = dict(_item('A', 'Application response'), DocumentTypeId='01')
        (documents, _discarded, _rf, ar_count, *_), _bodies = self._fetch(
            [_token_page([event, invoice], 2)])
        self.assertEqual([d['cufe'] for d in documents], ['A'])
        self.assertEqual(ar_count, 1)

    def test_item_fields_mapped(self):
        # Item of the live capture 2026-10-20 (EQ1018, Regus Colombia)
        item = dict(
            _item('A'),
            EmissionDate='/Date(1788652800000)/',
            ReceptionDate='/Date(1788722426978)/',
            DocumentTypeId='01',
            Status=10,
            TotalAmount=4489870,
            TaxAmountIva5Percent=0,
            TaxAmountIva19Percent=0,
            TaxAmountIva=716870,
            TaxesDetail={
                'TaxAmountIva5Percent': 0, 'TaxAmountIva14Percent': 0,
                'TaxAmountIva16Percent': 0, 'TaxAmountIva19Percent': 0,
                'TaxAmountIva': 0, 'TaxAmountIca': 0, 'TaxAmountIpc': 0,
            },
        )
        (documents, *_), _bodies = self._fetch([_token_page([item], 1)])
        vals = documents[0]
        # 00:00 UTC of the emission day, kept as that day (not the day before in Colombia)
        self.assertEqual(vals['emission_date'], date(2026, 9, 6))
        self.assertEqual(str(vals['reception']), '2026-09-06 19:20:26.978000')
        self.assertEqual(vals['type_code'], '01')
        self.assertEqual(vals['status_code'], 10)
        self.assertEqual(vals['tax_amount_iva'], 716870)
        # Not split by DIAN: left at 0 for the XML to fill
        self.assertEqual(vals['tax_amount_19_percent'], 0.0)
        document = self.env['dian.document'].create(vals)
        self.assertEqual(document.emission_date, date(2026, 9, 6))

    def test_taxes_from_taxes_detail(self):
        item = dict(_item('A'), TaxAmountIva19Percent=0, TaxAmountIva=0, TaxesDetail={
            'TaxAmountIva5Percent': 50, 'TaxAmountIva16Percent': 16,
            'TaxAmountIva19Percent': 190, 'TaxAmountIva': 0, 'TaxAmountIca': 7,
        })
        (documents, *_), _bodies = self._fetch([_token_page([item], 1)])
        vals = documents[0]
        self.assertEqual(vals['tax_amount_5_percent'], 50)
        self.assertEqual(vals['tax_amount_19_percent'], 190)
        self.assertEqual(vals['tax_amount_ica'], 7)
        # IVA total missing at both levels: sum of the rates
        self.assertEqual(vals['tax_amount_iva'], 256)

    def test_invalid_token_url_raises_clear_error(self):
        client = self.env['dian.api.client']
        for url in ('', 'Document Count? 5 Already in System? 0', 'catalogo-vpfe.dian.gov.co/User'):
            with self.assertRaisesRegex(ValidationError, 'token URL is not valid'):
                client._create_authenticated_session(url)

    def test_token_repeated_token_stops_pagination(self):
        (documents, *_), bodies = self._fetch([
            _token_page([_item('A')], 1, True, 'T1'),
            _token_page([_item('B')], 1, True, 'T1'),
        ])
        self.assertEqual(len(bodies), 2)
        self.assertEqual(len(documents), 2)

    def test_token_range_total_reported_on_each_page(self):
        # If DIAN reports the range total instead of the page count, it is not summed
        (*_, records_filtered, _ar, _errors, _protocol), bodies = self._fetch([
            _token_page([_item('A')], 3, True, 'T1'),
            _token_page([_item('B'), _item('C')], 3),
        ])
        self.assertEqual(records_filtered, 3)

    # -- block contract ---------------------------------------------------------------

    def test_block_protocol_forced(self):
        (documents, discarded, records_filtered, ar_count, errors, protocol), bodies = self._fetch([
            _block([_item('A'), _item('EV', 'Application response')], 3, 'K0'),
            _block([_item('B')], 3, ''),
        ], protocol='block')
        self.assertEqual(protocol, 'block')
        self.assertEqual([b['blockIndex'] for b in bodies], [0, 1])
        self.assertEqual([b['IsNextPage'] for b in bodies], ['false', 'true'])
        self.assertEqual([b['ContinuationToken'] for b in bodies], ['', 'K0'])
        self.assertNotIn('SearchRequested', bodies[0])
        # Documents come from blockData, not from data
        self.assertEqual([d['cufe'] for d in documents], ['A', 'B'])
        self.assertEqual(ar_count, 1)

    # -- auto detection ---------------------------------------------------------------

    def test_auto_uses_token_when_it_answers(self):
        (documents, *_, protocol), bodies = self._fetch([_token_page([_item('A')], 1)])
        self.assertEqual(protocol, 'token')
        self.assertEqual(len(bodies), 1)
        self.assertEqual(len(documents), 1)

    def test_auto_switches_to_block_when_response_has_block_data(self):
        (documents, *_, protocol), bodies = self._fetch([
            _block([_item('A')], 2, 'K0'),          # answer to the token request
            _block([_item('A')], 2, 'K0'),          # block 0
            _block([_item('B')], 2, ''),            # block 1
        ])
        self.assertEqual(protocol, 'block')
        self.assertIn('SearchRequested', bodies[0])
        self.assertEqual([b.get('blockIndex') for b in bodies[1:]], [0, 1])
        self.assertEqual([d['cufe'] for d in documents], ['A', 'B'])

    def test_auto_falls_back_to_block_when_token_returns_nothing(self):
        (documents, *_, protocol), bodies = self._fetch([
            _token_page([], 0),
            _block([_item('A')], 1),
        ])
        self.assertEqual(protocol, 'block')
        self.assertEqual(len(documents), 1)

    def test_auto_empty_range(self):
        (documents, discarded, records_filtered, *_, protocol), bodies = self._fetch([
            _token_page([], 0),
            _block([], 0),
        ])
        self.assertEqual(protocol, 'token')
        self.assertEqual((documents, discarded, records_filtered), ([], [], 0))

    # -- unexpected answers -----------------------------------------------------------

    def test_auto_falls_back_to_block_when_token_answer_is_not_json(self):
        (documents, *_, protocol), bodies = self._fetch([_html(), _block([_item('A')], 1)])
        self.assertEqual(protocol, 'block')
        self.assertEqual(len(documents), 1)

    def test_non_json_answer_raises_clear_error(self):
        with self.assertRaises(DianUnexpectedResponse):
            self._fetch([_html()], protocol='token')

    def test_redirect_is_reported_as_expired_session(self):
        with self.assertRaises(ValidationError) as error:
            self._fetch([_html(302, '/User/Login')], protocol='token')
        self.assertIn('/User/Login', str(error.exception))

    def test_requests_do_not_follow_redirects(self):
        session = MagicMock()
        session.post.side_effect = [_token_page([], 0), _block([], 0)]
        self.env['dian.api.client']._get_documents_for_date_range(
            session, 'https://dian', date(2026, 8, 1), date(2026, 8, 6), 'FORM-TOKEN')
        for call in session.post.call_args_list:
            self.assertIs(call.kwargs['allow_redirects'], False)
