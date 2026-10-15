import unicodedata

from odoo import api, models


def _norm(text):
    text = unicodedata.normalize('NFKD', text or '')
    return ''.join(c for c in text if not unicodedata.combining(c)).strip().lower()


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _get_or_create_city(self):
        self.ensure_one()
        city = self._resolve_city()
        if city and self.zip and not city.zipcode:
            try:
                with self.env.cr.savepoint():
                    city.sudo().zipcode = self.zip
            except Exception:
                pass
        return city

    def _resolve_city(self):
        self.ensure_one()
        name = (self.city or '').strip()
        if not name or not self.country_id:
            return self.city_id
        if self.city_id and self.city_id.name.lower() == name.lower():
            return self.city_id
        City = self.env['res.city'].sudo()
        domain = [('country_id', '=', self.country_id.id)]
        if self.state_id:
            domain.append(('state_id', '=', self.state_id.id))
        city = City.search(domain + [('name', '=ilike', name)], limit=1)
        if not city:
            target = _norm(name)
            city = City.search(domain).filtered(lambda c: _norm(c.name) == target)[:1]
        if not city and self.country_id.code != 'CO':
            try:
                with self.env.cr.savepoint():
                    city = City.create({
                        'name': name,
                        'country_id': self.country_id.id,
                        'state_id': self.state_id.id,
                        'zipcode': self.zip,
                    })
            except Exception:
                city = City.browse()
        return city or self.city_id

    def _ensure_city_id(self):
        for partner in self.filtered(lambda p: p.city and p.country_id):
            city = partner._get_or_create_city()
            if city != partner.city_id:
                partner.city_id = city

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        partners._ensure_city_id()
        return partners

    def write(self, vals):
        res = super().write(vals)
        if {'city', 'zip', 'state_id', 'country_id'} & vals.keys() and 'city_id' not in vals:
            self._ensure_city_id()
        return res
