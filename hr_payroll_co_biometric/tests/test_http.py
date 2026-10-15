from odoo.tests import HttpCase, tagged, new_test_user


@tagged('post_install', '-at_install')
class TestBiometricDocumentation(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        new_test_user(cls.env, context={'no_reset_password': True}, login='bio_docs_allowed', password='test_docs_allowed',
                      groups='base.group_user,hr_payroll_co_biometric.group_biometric_user')
        new_test_user(cls.env, context={'no_reset_password': True}, login='bio_docs_denied', password='test_docs_denied', groups='base.group_user')

    def test_documentation_authorized(self):
        self.authenticate('bio_docs_allowed', 'test_docs_allowed')
        response = self.url_open('/hr_payroll_co_biometric/documentation')
        self.assertEqual(response.status_code, 200)
        self.assertIn('19.0.1.0.0', response.text)

    def test_documentation_unauthorized(self):
        self.authenticate('bio_docs_denied', 'test_docs_denied')
        self.assertEqual(self.url_open('/hr_payroll_co_biometric/documentation').status_code, 404)

    def test_documentation_anonymous(self):
        self.authenticate(None, None)
        response = self.url_open('/hr_payroll_co_biometric/documentation', allow_redirects=False)
        self.assertIn(response.status_code, (302, 303))
        self.assertIn('/web/login', response.headers['Location'])
