from odoo import models, api
from datetime import date
import xml.etree.ElementTree as ET
import logging
import requests
from dateutil.relativedelta import relativedelta
from datetime import datetime

_logger = logging.getLogger(__name__)


class ResCurrency(models.Model):
    _inherit = 'res.currency'

    @api.model
    def get_trm_service(self):
        companies = self.env['res.company'].sudo().search([('sync_trm_state', '!=', 'disabled')])
        for company in companies:
            url = company.url_service_superintendency
            currency = company.service_currency_id
            if not (url and currency):
                _logger.info(
                    "URL del servicio de superintendencia o moneda no configurada.")
                continue

            today = date.today()

            if self.env['res.currency.rate'].sudo().search_count([
                ('currency_id', '=', currency.id),
                ('company_id', '=', company.id),
                ('name', '=', today)
            ]):
                _logger.info("La TRM para la fecha {date} ya existe.".format(date=today))
                continue

            raw_data = """
                <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                xmlns:act="http://action.trm.services.generic.action.superfinanciera.nexura.sc.com.co/">
                <soapenv:Header/>
                <soapenv:Body>
                <act:queryTCRM>
                <tcrmQueryAssociatedDate>{date}</tcrmQueryAssociatedDate>
                </act:queryTCRM>
                </soapenv:Body>
                </soapenv:Envelope>
            """.format(date=str(today))

            try:
                with requests.post(url, data=raw_data) as response:
                    if response.status_code == 200:
                        root = ET.fromstring(response.text)
                        value_tag = root.find('.//return/value')
                        date_tag = root.find('.//return/validityTo')
                        if value_tag is not None and date_tag is not None:
                            date_str = date_tag.text[:10]
                            date_ref = datetime.strptime(date_str, '%Y-%m-%d').date()
                            if date_ref == today:
                                trm_value = float(value_tag.text)
                                if company.apply_percentage:
                                    trm_value = trm_value + (trm_value * (company.percentage / 100))
                                self.env['res.currency.rate'].sudo().create({
                                    'name': today,
                                    'inverse_company_rate': trm_value,
                                    'currency_id': currency.id,
                                    'company_id': company.id
                                })
                            else:
                                _logger.warning("No se encontró el valor de TRM para la fecha {date}.".format(date=today))
                        else:
                            _logger.warning("No se encontró el valor de TRM en la respuesta.")
                    else:
                        _logger.warning(f"Error en la respuesta del servicio con código {response.status_code}")
            except Exception as e:
                _logger.exception("Error al obtener la TRM: %s", e)
