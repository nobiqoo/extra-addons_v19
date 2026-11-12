# -*- coding: utf-8 -*-

from odoo import _, models
from odoo.exceptions import UserError


class PurchaseImport(models.Model):
    _inherit = 'purchase.import'

    def action_open_lot_import_arthome(self):
        """Abre el asistente para importar los lotes de todos los productos de la importación."""
        self.ensure_one()
        if not self.moves_ids:
            raise UserError(_('First load the products of the import with the "Products" button.'))
        if not self.moves_ids.filtered('display_import_lot'):
            raise UserError(_("This import has no products that use lots/serial numbers to import."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import Serial/Lot Numbers'),
            'res_model': 'stock.picking.lot.import',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_purchase_import_id': self.id, 'dialog_size': 'extra-large'},
        }
