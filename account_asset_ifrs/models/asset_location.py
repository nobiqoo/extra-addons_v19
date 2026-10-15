from odoo import fields, models


class AssetLocation(models.Model):
    _name = 'asset.location'
    _description = 'Asset Location'

    name = fields.Char(
        string='Name',
        required=True
    )
