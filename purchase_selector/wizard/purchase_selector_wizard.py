from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class PurchaseSelectorWizard(models.TransientModel):
    _name = "purchase.selector.wizard"
    _description = "Wizard - Tratar Líneas de Aprobaciones"

    # Encabezado
    date_deadline = fields.Date("Fecha límite de la orden")
    vendor_id = fields.Many2one(
        "res.partner", string="Proveedor",
        domain=[("supplier_rank", ">", 0)]
    )
    picking_type_id = fields.Many2one(
        "stock.picking.type", string="Entregar a",
        domain=[("code", "=", "incoming")], required=False
    )
    company_id = fields.Many2one("res.company", default=lambda s: s.env.company, required=True)

    # Detalle
    line_ids = fields.One2many("purchase.selector.wizard.line", "wizard_id", string="Líneas a tratar")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get("active_ids") or []
        items = self.env["approval.purchase.item"].browse(active_ids).exists()
        if not items:
            raise UserError(_("No hay ítems seleccionados."))

        vendor_set = set()
        for it in items:
            seller = it.product_id.seller_ids[:1]
            if seller:
                vendor_set.add(seller.partner_id.id)
        if len(vendor_set) == 1:
            res["vendor_id"] = vendor_set.pop()
        else:
            res["vendor_id"] = False


        default_picking = self.env["stock.picking.type"].search(
            [("code", "=", "incoming"), ("warehouse_id.company_id", "in", [self.env.company.id, False])],
            limit=1
        )
        if default_picking:
            res["picking_type_id"] = default_picking.id

        lines_vals = []
        for it in items:
            prod_f, uom_f, approved_f, descr_f = self._source_from_line_id(it.line_id)

            if not approved_f and it.request_name and it.product_id:
                prod_g, uom_g, approved_g, descr_g = self._source_from_req_and_product(it.request_name, it.product_id.id)
                if approved_g:
                    prod_f, uom_f, approved_f, descr_f = prod_g, uom_g, approved_g, descr_g

            qty_approved = approved_f if approved_f not in (None, False, 0.0) else (it.qty_approved or 0.0)
            qty_on_hand = it.qty_on_hand or 0.0
            qty_purchase_default = max(qty_approved - qty_on_hand, 0.0)

            lines_vals.append((0, 0, {
                "item_id": it.id,
                "line_id": it.line_id,
                "request_name": it.request_name,
                "product_id": (prod_f and prod_f.id) or it.product_id.id,
                "description": it.description or descr_f,
                "uom_id": (uom_f and uom_f.id) or it.uom_id.id,
                "qty_approved": qty_approved,
                "qty_on_hand": qty_on_hand,
                "qty_to_process": qty_purchase_default,
            }))
        if not lines_vals:
            raise UserError(_("Los ítems seleccionados no tienen datos para procesar."))

        res["line_ids"] = lines_vals
        return res
        
    def _source_from_line_id(self, line_id):
        if not line_id:
            return (False, False, 0.0, '')
        self.env.cr.execute("""
            SELECT apl.product_id, apl.product_uom_id, COALESCE(apl.quantity,0.0), COALESCE(apl.description,'')
            FROM approval_product_line apl
            WHERE apl.id = %s
            LIMIT 1
        """, (line_id,))
        row = self.env.cr.fetchone()
        if not row:
            return (False, False, 0.0, '')
        prod = self.env['product.product'].browse(row[0]) if row[0] else False
        uom  = self.env['uom.uom'].browse(row[1]) if row[1] else False
        approved_qty = float(row[2] or 0.0)
        descr = row[3] or (prod and prod.display_name) or ''
        return (prod, uom, approved_qty, descr)
    
    def _source_from_req_and_product(self, req_name, product_id):
        if not req_name or not product_id:
            return (False, False, 0.0, '')
        self.env.cr.execute("""
            SELECT apl.product_id, apl.product_uom_id, COALESCE(apl.quantity,0.0), COALESCE(apl.description,'')
            FROM approval_product_line apl
            JOIN approval_request ar ON ar.id = apl.approval_request_id
            WHERE ar.name = %s AND apl.product_id = %s
            LIMIT 1
        """, (req_name, product_id))
        row = self.env.cr.fetchone()
        if not row:
            return (False, False, 0.0, '')
        prod = self.env['product.product'].browse(row[0]) if row[0] else False
        uom  = self.env['uom.uom'].browse(row[1]) if row[1] else False
        approved_qty = float(row[2] or 0.0)
        descr = row[3] or (prod and prod.display_name) or ''
        return (prod, uom, approved_qty, descr)

    def _safe_origin_parts(self):
        return sorted({str(x) for x in self.line_ids.mapped("request_name") if x})

    def action_confirm(self):
        _logger.info("  [PS] action_confirm START: vendor=%s company=%s picking_type=%s num_lines=%s",
                    self.vendor_id.display_name if self.vendor_id else None,
                    self.company_id.display_name if self.company_id else None,
                    self.picking_type_id.display_name if self.picking_type_id else None,
                    len(self.line_ids))

        if not self.line_ids:
            _logger.warning("ƒ [PS] abort: no hay líneas seleccionadas")
            raise UserError(_("No hay líneas para procesar."))
        if not self.vendor_id:
            _logger.warning(" [PS] abort: no hay proveedor seleccionado")
            raise UserError(_("Selecciona un proveedor en el encabezado."))

        PO = self.env["purchase.order"]
        po_vals = {
            "partner_id": self.vendor_id.id,
            "company_id": self.company_id.id,
            "origin": ", ".join(self._safe_origin_parts())[:255] or False,
        }
        vendor = self.vendor_id.with_company(self.company_id) if self.company_id else self.vendor_id
        if vendor.property_supplier_payment_term_id:
            po_vals["payment_term_id"] = vendor.property_supplier_payment_term_id.id
        if self.picking_type_id:
            po_vals["picking_type_id"] = self.picking_type_id.id

        po = PO.create(po_vals)
        _logger.info("  [PS] PO creado id=%s partner=%s origin=%s",
                    po.id, po.partner_id.display_name, po.origin)

        Item = self.env['approval.purchase.item'].sudo()
        req_ids = set()
        used_apl_ids = set()

        for ln in self.line_ids:
            _logger.info("  [PS] Línea wizard: req=%s line_id=%s prod=%s uom=%s qty_aprob=%s qty_hand=%s qty_compra=%s",
                        ln.request_name,
                        getattr(ln.line_id, 'id', ln.line_id),
                        ln.product_id.display_name if ln.product_id else None,
                        ln.uom_id.display_name if ln.uom_id else None,
                        ln.qty_approved, ln.qty_on_hand, ln.qty_to_process)

            item = ln.item_id
            if not item and ln.line_id:
                item = Item.search([('line_id', '=', getattr(ln.line_id, 'id', ln.line_id))], limit=1)

            prod = ln.product_id or (item and item.product_id)
            uom  = ln.uom_id     or (item and item.uom_id)
            approved = (ln.qty_approved if ln.qty_approved not in (None, False)
                        else (item and item.qty_approved))
            descr = ln.description or (item and item.description) or (prod and prod.display_name) or ''
            to_buy = ln.qty_to_process or 0.0

            if not prod or approved in (None, False):
                prod_f, uom_f, approved_f, descr_f = self._source_from_line_id(getattr(ln.line_id, 'id', ln.line_id))
                prod = prod or prod_f
                uom = uom or uom_f
                approved = (approved if approved not in (None, False) else approved_f)
                if not descr:
                    descr = descr_f

            if (not prod or approved in (None, False, 0.0)) and (ln.request_name and (ln.product_id or (item and item.product_id))):
                req_name = ln.request_name
                pid = (ln.product_id and ln.product_id.id) or (item and item.product_id.id)
                prod_h, uom_h, approved_h, descr_h = self._source_from_req_and_product(req_name, pid)
                if prod_h and not prod:
                    prod = prod_h
                if uom_h and not uom:
                    uom = uom_h
                if (approved in (None, False, 0.0)) and approved_h:
                    approved = approved_h
                if not descr and descr_h:
                    descr = descr_h

            approved = float(approved or 0.0)

            # Snapshot del wizard (si no viene, usamos approved para no dejarla en 0)
            pending_snapshot = float((getattr(ln, 'qty_pending_purchase', 0.0) or 0.0))
            if pending_snapshot <= 0 and approved > 0:
                pending_snapshot = approved
            _logger.info("  [PS] Cota inicial: approved=%s pending(wizard)=%s to_buy=%s",
                        approved, pending_snapshot, to_buy)

            if to_buy < 0:
                raise UserError(_("La cantidad a comprar de %s no puede ser negativa.")
                                % (prod.display_name if prod else _("(sin producto)")))
            if to_buy == 0:
                _logger.info(" [PS] Línea saltada (to_buy=0) req=%s prod=%s", ln.request_name, prod and prod.display_name)
                continue
            if not prod:
                raise UserError(_("No se pudo resolver el producto para la línea."))

            # Token/descr
            # token = f"[{ln.request_name or 'REQ?'}#{(getattr(ln.line_id, 'id', False) or ln.id)}] "
            base_descr = (descr or (prod and prod.display_name) or '')
            descr = base_descr  # ← sin prefijo

            # Precio/uom
            date_planned = fields.Datetime.to_datetime(self.date_deadline) if self.date_deadline else fields.Datetime.now()
            seller = prod.with_company(po.company_id)._select_seller(
                partner_id=self.vendor_id, quantity=to_buy, date=fields.Date.context_today(self)
            )
            price = seller.price if (seller and seller.price) else 0.0
            product_uom_id = uom.id if uom else (prod.uom_id.id if (prod and prod.uom_id) else False)

            # ====== Resolver APL y calcular permitido real ======
            apl_id = False
            req_id = False
            if item and getattr(item, 'request_id', False):
                req_id = item.request_id.id
            # 1) si ya viene en la línea del wizard, úsala  
            if getattr(ln.line_id, 'id', False):
                apl_id = ln.line_id.id
            elif isinstance(ln.line_id, int) and ln.line_id:
                apl_id = ln.line_id
            # 2) si viene desde el item del consolidado
            elif item and getattr(item, 'line_id', False):
                apl_id = item.line_id

            # 3) búsqueda determinística: producto + descripción + requisición
            if not apl_id:
                dom = []
                # requisición exacta primero
                if req_id:
                    dom.append(('approval_request_id', '=', req_id))
                elif ln.request_name:
                    dom.append(('approval_request_id.name', '=', ln.request_name))

                if prod:
                    dom.append(('product_id', '=', prod.id))
                if (descr or '').strip():
                    dom.append(('description', '=', (descr or '').strip()))

                if dom:
                    apl = self.env['approval.product.line'].search(dom, order='id desc', limit=1)
                    apl_id = apl.id or False

            if not apl_id:
                raise UserError(_(
                    "No se pudo identificar la línea exacta de requisición para %s. "
                    "Cierra y abre de nuevo el asistente para recargar la selección."
                ) % (prod.display_name if prod else _("(sin producto)")))

            # 4) evitar repetir la misma APL en esta corrida del wizard
            if apl_id and apl_id in used_apl_ids:
                dom_alt = [('id', '!=', apl_id)]
                if prod:
                    dom_alt.append(('product_id', '=', prod.id))
                if (descr or '').strip():
                    dom_alt.append(('description', '=', (descr or '').strip()))
                if req_id:
                    dom_alt.append(('approval_request_id', '=', req_id))
                elif ln.request_name:
                    dom_alt.append(('approval_request_id.name', '=', ln.request_name))
                apl_alt = self.env['approval.product.line'].search(dom_alt, order='id desc', limit=1)
                apl_id = apl_alt.id or apl_id

            if apl_id:
                used_apl_ids.add(apl_id)

            _logger.info("  [PS] Resuelto approval_line_id=%s", apl_id)


            # Historial (aprobada - ya gestionado)
            allowed_by_history = approved
            already_managed = 0.0
            if apl_id:
                TxModel = self.env.get("approval.purchase.tx")
                try:
                    if TxModel:
                        rg = TxModel.read_group([('approval_line_id', '=', apl_id)], ['qty:sum'], [])
                        already_managed = float((rg and rg[0].get('qty_sum')) or 0.0)
                    else:
                        self.env.cr.execute(
                            "SELECT COALESCE(SUM(product_qty),0) FROM purchase_order_line WHERE approval_line_id = %s",
                            (apl_id,)
                        )
                        already_managed = float(self.env.cr.fetchone()[0] or 0.0)
                except Exception as e:
                    _logger.warning(" [PS] No fue posible leer histórico de compras para APL(%s): %s", apl_id, e)
                allowed_by_history = max(approved - already_managed, 0.0)

            # Pendiente vivo desde la APL (si existe)
            effective_allowed = None
            if apl_id:
                apl_rec = self.env['approval.product.line'].sudo().browse(apl_id)
                if apl_rec.exists():
                    live_pending = float(apl_rec.qty_pending_to_buy or 0.0)
                    effective_allowed = live_pending
                    _logger.info("  [PS] Pendiente vivo en APL=%s -> allowed=%s",
                                live_pending, effective_allowed)

            if effective_allowed is None:
                effective_allowed = float(pending_snapshot or 0.0)
                _logger.info("  [PS] Fallback allowed: wizard_snapshot=%s -> allowed=%s",
                            pending_snapshot, effective_allowed)

            if to_buy - effective_allowed > 1e-9:
                raise UserError(_("La cantidad de compra (%s) para %s supera la cantidad pendiente por comprar (%s).")
                                % (to_buy, prod.display_name if prod else _("(sin producto)"), effective_allowed))
            
            # Nombre del producto del proveedor
            supplier_name = ''
            try:
                if seller and getattr(seller, 'product_name', False):
                    supplier_name = (seller.product_name or '').strip()
                else:
                    si = self.env['product.supplierinfo'].search([
                        ('product_tmpl_id', '=', prod.product_tmpl_id.id),
                        ('partner_id', '=', self.vendor_id.id),
                    ], limit=1)
                    supplier_name = (si.product_name or '').strip()
            except Exception as e:
                _logger.warning(" [PS] No se pudo obtener nombre de proveedor: %s", e)
                supplier_name = ''


            # ====== Crear POL con enlace ======
            pol_vals = {
                "order_id": po.id,
                "product_id": prod.id,
                "name": supplier_name or '',
                "descripcion": descr,
                "product_qty": to_buy,
                "product_uom_id": product_uom_id,
                "price_unit": price,
                "date_planned": date_planned,
                "approval_line_id": apl_id,
            }
            if apl_id:
                apl = self.env['approval.product.line'].browse(apl_id).sudo()
                if getattr(apl, 'analytic_account_id', False):
                    pol_vals['analytic_distribution'] = {apl.analytic_account_id.id: 100.0}
                req = apl.approval_request_id
                if req and getattr(req, 'project_id', False) and not po.project_id:
                    po.write({'project_id': req.project_id.id})

            _logger.info("  [PS] pol_vals=%s", pol_vals)
            pol = self.env["purchase.order.line"].create(pol_vals)
            _logger.info("  [PS] POL creada id=%s order=%s product=%s qty=%s",
                        pol.id, po.name, pol.product_id.display_name, pol.product_qty)

            if apl_id:
                try:
                    self.env['approval.product.line'].browse(apl_id).write({'purchase_order_line_id': pol.id})
                    _logger.info("  [PS] APL(%s) ← POL(%s) enlazadas", apl_id, pol.id)
                except Exception as e:
                    _logger.warning(" [PS] No se pudo escribir purchase_order_line_id: %s", e)

                req = self.env['approval.product.line'].browse(apl_id).approval_request_id
                if req:
                    req_ids.add(req.id)

                TxModel = self.env.get("approval.purchase.tx")
                if TxModel:
                    try:
                        TxModel.create({
                            "approval_line_id": apl_id,
                            "product_id": prod.id,
                            "uom_id": product_uom_id,
                            "qty": to_buy,
                            "po_id": po.id,
                            "pol_id": pol.id,
                            "vendor_id": self.vendor_id.id,
                            "company_id": self.company_id.id,
                        })
                        _logger.info("  [PS] TX creada (apl=%s qty=%s)", apl_id, to_buy)
                    except Exception as e:
                        _logger.warning(" [PS] No se pudo crear TX: %s", e)

        if req_ids:
            po.write({'approval_request_ids': [(6, 0, list(req_ids))]})
            _logger.info("  [PS] OC(%s) enlazada a requisiciones %s", po.id, list(req_ids))

            # Si todas las líneas quedaron en 0, marcamos la req como 'OC. Creada'
            reqs = self.env['approval.request'].browse(list(req_ids)).sudo()
            po.write({
                'approval_request_ids': [(6, 0, reqs.ids)],
                'origin': ', '.join(reqs.mapped('name'))[:255],
            })
            for req in reqs:
                lines = req.product_line_ids.sudo()
                sum_pending = sum((l.qty_pending_to_buy or 0.0) for l in lines)
                _logger.info("  [PS] REQ(%s) pendiente total=%.6f", req.name, sum_pending)
                if sum_pending <= 1e-9 and req.request_status != 'created_po':
                    req.write({'request_status': 'created_po'})
                    req.message_post(body=_("Marcada como 'OC. Creada' al quedar todas las líneas con Pendiente=0,00."))
                    _logger.info("  [PS] REQ(%s) marcada como created_po", req.name)
                else:
                    _logger.info(" [PS] REQ(%s) mantiene estado; aún hay pendientes.", req.name)

        action = self.env.ref("purchase.purchase_rfq").sudo().read()[0]
        action["views"] = [(self.env.ref("purchase.purchase_order_form").id, "form")]
        action["res_id"] = po.id
        _logger.info("  [PS] action_confirm END -> abrir PO id=%s", po.id)
        return action


    def action_open_confirm(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Confirmación",
            "res_model": "purchase.selector.confirm.wizard",
            "view_mode": "form",
            "target": "new",
            "context": dict(self.env.context, active_id=self.id),
        }


class PurchaseSelectorWizardLine(models.TransientModel):
    _name = "purchase.selector.wizard.line"
    _description = "Línea del Wizard - Tratar Líneas"

    wizard_id = fields.Many2one("purchase.selector.wizard", required=True, ondelete="cascade")
    item_id = fields.Many2one("approval.purchase.item", string="Item", readonly=True)
    line_id = fields.Many2one('approval.product.line',string="ID línea REQ", readonly=True)
    request_name = fields.Char("N° Requerimiento", readonly=True)

    product_id = fields.Many2one("product.product", "Producto", readonly=True)
    description = fields.Char("Descripción")
    uom_id = fields.Many2one("uom.uom", "UoM", readonly=True)

    qty_approved = fields.Float("Cant. Aprobada", digits="Product Unit of Measure", readonly=True)
    qty_on_hand = fields.Float("A la mano", digits="Product Unit of Measure", readonly=True)
    qty_to_process = fields.Float("Cant. Compra", digits="Product Unit of Measure")  # editable
    qty_pending_purchase = fields.Float(
        string="Cant. Pendiente por comprar",
        digits="Product Unit of Measure",
        readonly=True,
        related="item_id.qty_pending_purchase",
        store=False
    )

    @api.onchange('product_id')
    def _onchange_product_id_set_vendor(self):
        if self.product_id:
            seller = self.product_id.seller_ids[:1]
            if seller:
                self.wizard_id.vendor_id = seller.name.id
