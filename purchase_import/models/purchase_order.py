# -*- coding: utf-8 -*-
from odoo import models, fields, _
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    import_count = fields.Integer(
        string='Importaciones',
        compute='_compute_import_count',
        compute_sudo=True,
        store=False,
        readonly=True,
    )

    def _detect_import_link(self):
        if 'purchase.import' not in self.env:
            return None, None, None, {'reason': 'model_not_found'}

        Import = self.env['purchase.import']
        dbg = {}

        try:
            dbg['has_purchases_ids_in__fields'] = 'purchases_ids' in Import._fields
        except Exception as e:
            dbg['__fields_error'] = str(e)

        try:
            fg = Import.fields_get(['purchases_ids'])
            dbg['fields_get_has_purchases_ids'] = 'purchases_ids' in fg
        except Exception as e:
            dbg['fields_get_error'] = str(e)

        try:
            imf = self.env['ir.model.fields'].sudo().search([
                ('model', '=', 'purchase.import'),
                ('name', '=', 'purchases_ids'),
            ], limit=1)
            dbg['ir_model_fields_has_purchases_ids'] = bool(imf)
        except Exception as e:
            dbg['ir_model_fields_error'] = str(e)

        direct_field = None
        direct_type = None
        for c in ('purchase_id', 'purchase_order_id', 'purchase_ids', 'purchase_order_ids', 'purchases_ids'):
            if c in Import._fields:
                direct_field = c
                direct_type = Import._fields[c].type
                break

        if direct_field:
            return 'direct', direct_field, direct_type, dbg

        if dbg.get('ir_model_fields_has_purchases_ids') or dbg.get('fields_get_has_purchases_ids'):
            return 'direct', 'purchases_ids', 'many2many', dbg

        for fname, f in Import._fields.items():
            if f.type != 'one2many':
                continue
            line_model = self.env[f.comodel_name]
            to_po_field = None
            for ln, lf in line_model._fields.items():
                if lf.type == 'many2one' and lf.comodel_name == 'purchase.order':
                    to_po_field = ln
                    break
            if to_po_field:
                return 'bridge', fname, 'one2many', {'o2m_field': fname, 'line_to_po': to_po_field, **dbg}

        return None, None, None, dbg

    def _get_import_domain_for_po(self):
        mode, fname, ftype, extra = self._detect_import_link()
        for rec in self:
            # En onchange el registro tiene un NewId virtual; usar el id real
            # de _origin y omitir registros aún no guardados.
            rec_id = rec._origin.id or rec.id
            if not mode or not rec_id:
                yield rec, False, [], {}
                continue
            if mode == 'direct':
                dom = [(fname, '=', rec_id)] if ftype == 'many2one' else [(fname, 'in', [rec_id])]
                yield rec, True, dom, {'mode': 'direct', 'field': fname, 'ftype': ftype}
            else:
                dom = [(f"{extra['o2m_field']}.{extra['line_to_po']}", '=', rec_id)]
                yield rec, True, dom, {'mode': 'bridge', **extra}

    def _compute_import_count(self):
        if 'purchase.import' not in self.env:
            for rec in self:
                rec.import_count = 0
            return
        Import = self.env['purchase.import']
        for rec, ok, dom, _info in self._get_import_domain_for_po():
            rec.import_count = Import.search_count(dom) if ok else 0

    def action_open_imports(self):
        if 'purchase.import' not in self.env:
            raise UserError(_("El modelo de importaciones no está instalado."))

        self.ensure_one()
        Import = self.env['purchase.import']

        dom, info = [], {}
        for rec, ok, d, i in self._get_import_domain_for_po():
            if rec == self and ok:
                dom, info = d, i
                break

        count = Import.search_count(dom) if dom else 0

        if count == 0:
            ctx = {}
            if info.get('mode') == 'direct':
                if info.get('ftype') == 'many2one':
                    ctx[f"default_{info['field']}"] = self.id
                else:
                    ctx[f"default_{info['field']}"] = [self.id]
            elif info.get('mode') == 'bridge':
                o2m = info['o2m_field']
                to_po = info['line_to_po']
                ctx[f"default_{o2m}"] = [(0, 0, {to_po: self.id})]
            ctx['default_partner_id'] = self.partner_id.id
            ctx['default_currency_id'] = self.currency_id.id
            if self.partner_id.country_id:
                ctx['default_country_id'] = self.partner_id.country_id.id

            return {
                'name': _('Nueva Importación'),
                'type': 'ir.actions.act_window',
                'res_model': 'purchase.import',
                'view_mode': 'form',
                'target': 'current',
                'context': ctx,
            }

        return {
            'name': _('Importaciones'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.import',
            'view_mode': 'list,kanban,form',
            'views': [(False, 'list'), (False, 'kanban'), (False, 'form')],
            'domain': dom,
            'target': 'current',
        }
