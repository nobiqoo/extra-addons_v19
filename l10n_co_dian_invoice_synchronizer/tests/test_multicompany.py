# -*- coding: utf-8 -*-
from psycopg2 import IntegrityError

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestDianMulticompany(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_a.vat = '900.111.222-3'
        cls.company_b = cls.env['res.company'].create({'name': 'Company B', 'vat': '800333444'})
        cls.env.user.company_ids |= cls.company_b
        cls.accountant = cls.env['res.users'].create({
            'name': 'Accountant',
            'login': 'dian_mc_accountant',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, (cls.company_a | cls.company_b).ids)],
            'group_ids': [(6, 0, [cls.env.ref('account.group_account_manager').id])],
        })
        cls.Document = cls.env['dian.document']
        cls.wizard = cls.env['dian.invoice.synchronizer']

    def _document(self, company, cufe='CUFE-1'):
        return self.Document.create({
            'cufe': cufe,
            'name': 'FV-1',
            'reception': fields.Datetime.now(),
            'company_id': company.id,
        })

    def test_company_from_receiver_nit(self):
        # Company NIT with verification digit, DIAN NIT without it
        self.assertEqual(
            self.wizard._get_company_for_documents([{'receiver_vat': '900111222'}], []),
            self.company_a)
        self.assertEqual(
            self.wizard._get_company_for_documents([{'receiver_vat': '800333444'}], []),
            self.company_b)

    def test_unknown_receiver_nit_is_rejected(self):
        with self.assertRaises(UserError):
            self.wizard._get_company_for_documents([{'receiver_vat': '123456789'}], [])

    def test_documents_of_several_companies_are_rejected(self):
        with self.assertRaises(UserError):
            self.wizard._get_company_for_documents(
                [{'receiver_vat': '900111222'}, {'receiver_vat': '800333444'}], [])

    def test_only_discarded_documents_use_their_company(self):
        self._document(self.company_b, cufe='CUFE-B')
        self.assertEqual(self.wizard._get_company_for_documents([], ['CUFE-B']), self.company_b)

    def test_same_cufe_allowed_in_other_company(self):
        self._document(self.company_a)
        self._document(self.company_b)

    @mute_logger('odoo.sql_db')
    def test_cufe_unique_per_company(self):
        self._document(self.company_a)
        with self.assertRaises(IntegrityError), self.env.cr.savepoint():
            self._document(self.company_a)

    def test_purchase_order_of_other_company_is_rejected(self):
        partner = self.env['res.partner'].create({'name': 'Vendor'})
        order = self.env['purchase.order'].with_company(self.company_b).create({
            'partner_id': partner.id,
            'company_id': self.company_b.id,
        })
        document = self._document(self.company_a)
        with self.assertRaises(UserError):
            document.purchase_id = order

    def test_record_rules_isolate_companies(self):
        document_b = self._document(self.company_b, cufe='CUFE-B')
        Document = self.Document.with_user(self.accountant)
        only_a = Document.with_context(allowed_company_ids=[self.company_a.id])
        self.assertFalse(only_a.search([('cufe', '=', 'CUFE-B')]))
        both = Document.with_context(allowed_company_ids=(self.company_a | self.company_b).ids)
        self.assertEqual(both.search([('cufe', '=', 'CUFE-B')]), document_b)

    def test_sync_gets_a_name_in_any_company(self):
        for company in self.company_a | self.company_b:
            sync = self.env['dian.sync'].with_company(company).create({'company_id': company.id})
            self.assertTrue(sync.name.startswith('SYNC/'))

    def test_count_discarded_in_other_companies(self):
        self._document(self.company_a, cufe='CUFE-A')
        self._document(self.company_b, cufe='CUFE-B')
        self._document(self.company_a, cufe='CUFE-AB')
        self._document(self.company_b, cufe='CUFE-AB')
        discarded = ['CUFE-A', 'CUFE-B', 'CUFE-AB']
        # Only CUFE-B is missing from company A
        self.assertEqual(self.wizard._count_discarded_in_other_companies(discarded, self.company_a), 1)
        self.assertEqual(self.wizard._count_discarded_in_other_companies(discarded, self.company_b), 1)
        self.assertEqual(self.wizard._count_discarded_in_other_companies([], self.company_a), 0)
