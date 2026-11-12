# -*- coding: utf-8 -*-
from odoo import fields
from odoo.tests import TransactionCase, tagged

from .test_dian_document_xml import INVOICE_XML


@tagged('post_install', '-at_install')
class TestDianXmlMulticompany(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env['res.company'].create({'name': 'Company B'})
        cls.accountant = cls.env['res.users'].create({
            'name': 'Accountant',
            'login': 'dian_xml_mc_accountant',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, (cls.company_a | cls.company_b).ids)],
            'group_ids': [(6, 0, [
                cls.env.ref('account.group_account_manager').id,
                cls.env.ref('l10n_co_bloodo.group_dian_invoice_intake').id,
            ])],
        })
        Document = cls.env['dian.document']
        cls.document_b = Document.create(dict(
            Document._xml_vals_from_content(INVOICE_XML),
            cufe='CUFE-B', name='FV-B', reception=fields.Datetime.now(),
            company_id=cls.company_b.id,
        ))

    def _as_accountant_in(self, companies):
        return self.env(user=self.accountant, context={'allowed_company_ids': companies.ids})

    def test_xml_detail_takes_document_company(self):
        line = self.document_b.invoice_line_ids
        self.assertEqual(line.company_id, self.company_b)
        self.assertEqual(self.document_b.tax_total_ids.company_id, self.company_b)
        # Line-level taxes hang from the line, not from the document
        line_tax = self.env['dian.document.tax.total'].create(
            {'invoice_line_id': line.id, 'tax_amount': 1.0})
        self.assertEqual(line_tax.company_id, self.company_b)

    def test_xml_detail_isolated_by_company(self):
        env_a = self._as_accountant_in(self.company_a)
        self.assertFalse(env_a['dian.document.invoice.line'].search(
            [('document_id', '=', self.document_b.id)]))
        self.assertFalse(env_a['dian.document.tax.total'].search(
            [('company_id', '=', self.company_b.id)]))
        env_ab = self._as_accountant_in(self.company_a | self.company_b)
        self.assertTrue(env_ab['dian.document.invoice.line'].search(
            [('document_id', '=', self.document_b.id)]))

    def test_intake_isolated_by_company(self):
        intake_b = self.env['dian.invoice.intake'].create({'company_id': self.company_b.id})
        env_a = self._as_accountant_in(self.company_a)
        self.assertNotIn(intake_b, env_a['dian.invoice.intake'].search([]))
