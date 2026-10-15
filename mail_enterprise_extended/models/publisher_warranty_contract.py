
import re
from odoo import api
from odoo.models import AbstractModel

VERSION_REGEX = '\\d+.\\d+'
DEFAULT_VERSION = '17.0'


class PublisherWarrantyContract(AbstractModel):
    _inherit = "publisher_warranty.contract"

    @api.model
    def _get_message(self):
        msg = super()._get_message()
        if 'maintenance' in msg:
            msg.pop('maintenance')
        match = re.search(VERSION_REGEX, msg.get('version', ''))
        msg['version'] = match.group() if match else DEFAULT_VERSION
        return msg
