
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class SupplySelectorWizard(models.TransientModel):
    _name = "supply.selector.wizard"
    _description = "Wizard - A Abastecer"

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, readonly=True)
    picking_type_id = fields.Many2one('stock.picking.type', string='Tipo de operación', required=True)
    location_src_id = fields.Many2one('stock.location', string='Ubicación Origen', required=True, domain=[('usage','=','internal')])
    location_dest_id = fields.Many2one('stock.location', string='Ubicación Destino', required=True, domain=[('usage','=','internal')])
    scheduled_date = fields.Datetime(string='Fecha programada')
    project_id = fields.Many2one('project.project', string='Proyecto')

    line_ids = fields.One2many('supply.selector.wizard.line', 'wizard_id', string='Líneas')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        # Pre-cargar líneas desde los seleccionados en approval.purchase.item
        active_model = self.env.context.get('active_model')
        active_ids = self.env.context.get('active_ids', [])
        if active_model != 'approval.purchase.item' or not active_ids:
            return res

        items = self.env['approval.purchase.item'].browse(active_ids)
        # Proyecto por defecto: si todos tienen el mismo, lo ponemos; si alguno no, dejamos vacío
        projects = items.mapped('project_id')
        if len(projects) == 1:
            res['project_id'] = projects.id

        lines_vals = []
        for it in items:
            # qty_pending_purchase trae el pendiente; qty_on_hand ya consolidado pero necesitamos por ubicación origen
            lines_vals.append((0, 0, {
                'item_id': it.id,
                'line_id': it.line_id,
                'request_name': it.request_name,
                'product_id': it.product_id.id,
                'description': it.description,
                'uom_id': it.uom_id.id if it.uom_id else (it.product_id.uom_id.id if it.product_id else False),
                'qty_approved': it.qty_approved,
                'qty_pending_supply': it.qty_pending_purchase,  # inicial
                'qty_to_supply': 0.0,
                'qty_on_hand': 0.0,
            }))
        res['line_ids'] = lines_vals
        return res

    @api.onchange('location_src_id')
    def _onchange_location_src(self):
        if not self.location_src_id:
            for ln in self.line_ids:
                ln.qty_on_hand = 0.0
            return
        # calcular on hand por producto en la ubicación origen
        # Usamos quants para esa ubicación y sus hijos
        Location = self.env['stock.location']
        child_loc_ids = Location.search([('id','child_of', self.location_src_id.id), ('usage','=','internal')]).ids
        if not child_loc_ids:
            child_loc_ids = [self.location_src_id.id]

        self.env.cr.execute("""
            SELECT sq.product_id, SUM(sq.quantity) AS qty
            FROM stock_quant sq
            WHERE sq.location_id = ANY(%s)
            GROUP BY sq.product_id
        """, (child_loc_ids,))
        by_prod = dict(self.env.cr.fetchall()) if self.env.cr.rowcount else {}

        for ln in self.line_ids:
            ln.qty_on_hand = float(by_prod.get(ln.product_id.id, 0.0))

    def action_generate_supply(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('No hay líneas para procesar.'))

        # Validaciones de cantidades
        bad = []
        for ln in self.line_ids:
            if ln.qty_to_supply and ln.qty_to_supply > ln.qty_on_hand + 1e-9:
                bad.append('%s (req %s): a abastecer %.2f > a la mano %.2f' % (
                    ln.product_id.display_name, ln.request_name, ln.qty_to_supply, ln.qty_on_hand
                ))
        if bad:
            raise UserError(_('No se puede crear el abastecimiento porque hay líneas con cantidades superiores a lo disponible en origen:\n- ') + '\n- '.join(bad))

        # Crear picking con movimientos
        Picking = self.env['stock.picking']
        Move = self.env['stock.move']
        Request = self.env['approval.request']
        req_names = set()
        apl_ids = set()

        picking = Picking.create({
            'picking_type_id': self.picking_type_id.id,
            'location_id': self.location_src_id.id,
            'location_dest_id': self.location_dest_id.id,
            'scheduled_date': self.scheduled_date or fields.Datetime.now(),
            'company_id': self.company_id.id,
        })

        for ln in self.line_ids:
            if ln.qty_to_supply <= 0:
                continue
            apl = ln.line_id or (ln.item_id and ln.item_id.line_id and self.env['approval.product.line'].browse(ln.item_id.line_id))
            if apl and apl.id:
                apl_id = apl.id
            else:
                apl_id = False

            Move.create({
                'name': ln.description or ln.product_id.display_name,
                'product_id': ln.product_id.id,
                'product_uom': ln.uom_id.id or ln.product_id.uom_id.id,
                'product_uom_qty': ln.qty_to_supply,
                'location_id': self.location_src_id.id,
                'location_dest_id': self.location_dest_id.id,
                'picking_id': picking.id,
                'approval_line_id': apl_id,
                'company_id': self.company_id.id,
            })
            _logger.info("[SUPPLY] Move creado con APL=%s qty=%.2f", apl_id, ln.qty_to_supply)
            if ln.request_name:
                req_names.add(ln.request_name)
            if ln.line_id:
                apl_ids.add(ln.line_id.id)

        # Confirmar para que quede En Espera
        if picking.state == 'draft':
            picking.action_confirm()

        # Enlazar requisiciones al picking (origen + relación)
        if req_names:
            reqs = Request.search([('name','in', list(req_names))])
            origin = ', '.join(reqs.mapped('name'))[:255]
            picking.write({'origin': origin})
            if hasattr(picking, 'approval_request_ids'):
                picking.approval_request_ids = [(6, 0, reqs.ids)]

            _logger.info("[SUPPLY] Picking %s origin=%s reqs=%s", picking.name, origin, reqs.ids)

            Move = self.env['stock.move'].sudo()
            POL  = self.env['purchase.order.line'].sudo()

            for req in reqs:
                _logger.info("[SUPPLY] Revisando req id=%s name=%s estado_actual=%s",
                             req.id, req.name, req.request_status)

                req.write({'picking_ids': [(4, picking.id)]})
                fully_managed = True

                for l in req.product_line_ids:
                    # comprado
                    pol_qty = 0.0
                    for pol in POL.search([
                        ('approval_line_id', '=', l.id),
                        ('order_id.state', '!=', 'cancel')
                    ]):
                        pol_uom = pol.product_uom_id or pol.product_id.uom_id
                        tgt_uom = l.product_uom_id or pol_uom
                        pol_qty += pol_uom._compute_quantity(pol.product_qty, tgt_uom)

                    # movido
                    mv_qty = 0.0
                    for mv in Move.search([
                        ('approval_line_id', '=', l.id),
                        ('state', '!=', 'cancel')
                    ]):
                        mv_uom = mv.product_uom or mv.product_id.uom_id
                        tgt_uom = l.product_uom_id or mv_uom
                        mv_qty += mv_uom._compute_quantity(mv.product_uom_qty, tgt_uom)

                    pending = (l.quantity or 0.0) - pol_qty - mv_qty
                    _logger.info(
                        "[SUPPLY] req=%s apl_line=%s qty_aprob=%.4f comprado=%.4f movido=%.4f pendiente=%.4f",
                        req.name, l.id, (l.quantity or 0.0), pol_qty, mv_qty, pending
                    )

                    if pending > 1e-6:
                        fully_managed = False
                        # no hacemos break para loguear todas las líneas
                _logger.info("[SUPPLY] Resultado req=%s fully_managed=%s", req.name, fully_managed)

                if fully_managed:
                    _logger.info("[SUPPLY] Cambiando estado req=%s -> 'abastecido'", req.name)
                    req.request_status = 'abastecido'
                else:
                    _logger.info("[SUPPLY] Req=%s NO marcado como abastecido (queda pendiente)", req.name)
                    
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_confirm(self):
        self.ensure_one()
        if self.line_ids.filtered(lambda x: x.qty_to_supply <= 0.0):
            raise UserError(_('Hay líneas con Cant. a Abastecer en cero.'))
        return {
            "type": "ir.actions.act_window",
            "name": "Confirmación",
            "res_model": "supply.selector.confirm.wizard",
            "view_mode": "form",
            "target": "new",
            "context": dict(self.env.context, active_id=self.id),
        }

class SupplySelectorWizardLine(models.TransientModel):
    _name = "supply.selector.wizard.line"
    _description = "Línea del Wizard - A Abastecer"

    wizard_id = fields.Many2one('supply.selector.wizard', required=True, ondelete='cascade')
    item_id = fields.Many2one('approval.purchase.item', string='Item', readonly=False)
    line_id = fields.Many2one('approval.product.line', string='ID línea REQ', readonly=True)
    request_name = fields.Char('N° Requerimiento', related="item_id.request_name", readonly=False)

    product_id = fields.Many2one(comodel_name='product.product', string='Producto', related="item_id.product_id", readonly=False)
    description = fields.Char('Descripción')
    uom_id = fields.Many2one('uom.uom', 'UoM', compute="_compute_uom", readonly=False)

    qty_approved = fields.Float('Cant. Aprobada', digits='Product Unit of Measure', readonly=True)
    qty_on_hand = fields.Float('A la mano', digits='Product Unit of Measure', readonly=True)
    qty_pending_supply = fields.Float('Cant. Pendiente', digits='Product Unit of Measure')
    qty_to_supply = fields.Float('Cant. a Abastecer', digits='Product Unit of Measure')
    qty_pending_supply_show = fields.Float('Cant. Pendiente', digits='Product Unit of Measure', related='qty_pending_supply')

    def _compute_uom(self):
        for ln in self:
            it = ln.item_id
            ln.uom_id = it.uom_id.id if it.uom_id else (it.product_id.uom_id.id if it.product_id else False)
