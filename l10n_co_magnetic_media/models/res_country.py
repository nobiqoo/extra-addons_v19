# -*- coding: utf-8 -*-

import logging
import pandas as pd
from os.path import join, dirname, realpath

from odoo import fields, models, _

_logger = logging.getLogger(__name__)


class ResCountry(models.Model):
    _inherit = 'res.country'

    medios_code = fields.Char('Código medios')

    def update_medios_code(self):

        csv_path = join(dirname(dirname(realpath(__file__))), 'data',
                    'res.country.csv')
        df = pd.read_csv(csv_path, dtype={'medios_code': str})
        # df['medios_code'] = df['medios_code'].astype(str)
        for index, row in df.iterrows():
            country_id = self.env.ref(row['id'])
            country_id.medios_code = row['medios_code']
        _logger.info('Código medios para magneticos en paises ACTUALIZADO')
        return True