
from odoo import models


class res_partner(models.Model):
    _inherit = 'res.partner'

    def check_vat_co(self, vat):
        return True
