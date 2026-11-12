# -*- coding: utf-8 -*-

from odoo import _, Command, fields, models
from odoo.exceptions import UserError


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    bom_product_tmpl_id = fields.Many2one(
        related='bom_id.product_tmpl_id',
        string='Producto de la LdM',
        store=True
    )

    bom_type = fields.Selection(
        related='bom_id.type',
        string='Tipo de lista de materiales',
        store=True
    )

    def copy_existing_components(self):
        bom_id = self.env.context.get('bom_id')
        if not bom_id:
            raise UserError(_('Guarde la lista de materiales antes de copiar componentes.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Seleccione componentes para copiar'),
            'res_model': 'mrp.bom.line',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('mrp_bom_copy_components.mrp_bom_line_copy_to_bom_list_view').id, 'list'),
                (False, 'form'),
            ],
            'search_view_id': [self.env.ref('mrp_bom_copy_components.mrp_bom_line_copy_to_bom_search_view').id],
            'domain': [('bom_id.active', '=', True), ('bom_id', '!=', bom_id)],
            'context': {'bom_id': bom_id},
        }

    def copy_to_bom(self):
        bom_id = self.env.context.get('bom_id')
        if not bom_id:
            return
        if not self:
            raise UserError(_('Debe seleccionar al menos un componente para copiar.'))
        bom = self.env['mrp.bom'].browse(bom_id)
        sequence = max(bom.bom_line_ids.mapped('sequence'), default=0)
        commands = []
        for line in self:
            sequence += 1
            # La operación y las variantes pertenecen a la LdM de origen
            commands += [Command.create(vals) for vals in line.copy_data({
                'bom_id': bom_id,
                'sequence': sequence,
                'operation_id': False,
                'bom_product_template_attribute_value_ids': [Command.clear()],
            })]
        # Escribir desde la LdM para que apliquen sus validaciones (ciclos, variantes)
        bom.write({'bom_line_ids': commands})
        return {
            'view_mode': 'form',
            'res_model': 'mrp.bom',
            'views': [(False, 'form')],
            'type': 'ir.actions.act_window',
            'res_id': bom_id,
        }
