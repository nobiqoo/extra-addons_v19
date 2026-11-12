# -*- coding: utf-8 -*-
"""
Tools the model can call. They always act on the document of the run (taken from the
context, not from an argument), with the permissions of the user of the configuration,
and re-check in code everything that matters: the model chooses and explains, but a
wrong answer can only leave the invoice as a draft.
"""
import json
from functools import wraps

from odoo import _, models
from odoo.exceptions import AccessError, UserError


def _ai_tool(func):
    @wraps(func)
    def wrapper(self, **kwargs):
        document = self._ai_current_document()
        try:
            with self.env.cr.savepoint():
                result = func(document, **kwargs)
        except Exception as e:
            document._ai_trace(func.__name__, kwargs, {'error': str(e)})
            raise
        document._ai_trace(func.__name__, kwargs, result)
        return json.dumps(result, ensure_ascii=False, default=str)
    return wrapper


def _exceeds(xml_value, odoo_value, amount=None, percent=None):
    """Tolerance reached first, in value or in percentage."""
    difference = abs((xml_value or 0.0) - (odoo_value or 0.0))
    if amount is not None and difference > amount:
        return True
    if percent is not None:
        base = abs(xml_value or 0.0) or abs(odoo_value or 0.0)
        return bool(base) and difference / base * 100 > percent
    return False


class DianDocument(models.Model):
    _inherit = 'dian.document'

    def _ai_current_document(self):
        document_id = self.env.context.get('dian_ai_document_id')
        if not document_id:
            raise UserError(_('Esta herramienta solo la puede usar el agente durante una ejecución.'))
        if not self.env.user.has_group('account.group_account_manager'):
            raise AccessError(_('El usuario %s no es administrador de contabilidad.', self.env.user.name))
        document = self.browse(document_id)
        document = document.with_company(document.sudo().company_id)
        document.check_access('write')
        return document

    # ── Lectura ──────────────────────────────────────────────────────────────

    def _ai_responsibilities(self):
        """Compare the responsibilities of the issuer in the XML with those of the vendor."""
        self.ensure_one()
        partner = self.purchase_id.partner_id
        odoo_types = partner.dian_obligation_type_ids or partner.property_account_position_id.dian_obligation_type_ids
        odoo_codes = {code for code in odoo_types.mapped('dian_code') if code}
        xml_codes = {code.strip() for code in (self.xml_tax_level_codes or '').split(';') if code.strip()}
        return {
            'xml': sorted(xml_codes),
            'odoo': sorted(odoo_codes),
            # Without the data in the XML there is nothing to contradict the vendor
            'match': not xml_codes or xml_codes == odoo_codes,
        }

    @_ai_tool
    def _ai_tool_get_document(self):
        return self._ai_read_document()

    def _ai_read_document(self):
        self.ensure_one()
        order = self.purchase_id
        config = self._ai_any_config()
        return {
            'document': {
                'name': self.name,
                'cufe': self.cufe,
                'invoice_type': self.invoice_type,
                'issue_date': self.xml_issue_date or self.emission_date,
                'due_date': self.xml_due_date,
                'currency': self.currency_id.name,
                'payment_means_code': self.payment_means_code,
                'tax_exclusive_amount': self.tax_exclusive_amount,
                'payable_amount': self.payable_amount,
                'taxes': [{
                    'scheme': tax.tax_scheme_id, 'name': tax.tax_scheme_name,
                    'percent': tax.percent, 'amount': tax.tax_amount, 'base': tax.taxable_amount,
                } for tax in self.tax_total_ids],
            },
            'xml_lines': [{
                'line_number': line.line_number,
                'description': line.description,
                'seller_code': line.sellers_item_identification,
                'quantity': line.invoiced_quantity,
                'unit_price': line.price_amount / (line.base_quantity or 1.0),
                'subtotal': line.line_extension_amount,
                'taxes': [{'scheme': tax.tax_scheme_id, 'percent': tax.percent, 'amount': tax.tax_amount}
                          for tax in line.tax_total_ids],
            } for line in self.invoice_line_ids.sorted('line_number')],
            'purchase_order': {
                'name': order.name,
                'vendor': order.partner_id.name,
                'currency': order.currency_id.name,
                'fiscal_position': order.fiscal_position_id.name,
                'lines': [{
                    'product': line.product_id.display_name,
                    'quantity': line.product_qty,
                    'received': line.qty_received,
                    'unit_price': line.price_unit,
                    'taxes': line.tax_ids.mapped('name'),
                } for line in order.order_line.filtered(lambda l: not l.display_type)],
            },
            'invoice': self.move_id.display_name,
            'vendor_responsibilities': self._ai_responsibilities(),
            'company_responsibilities': self.company_id.partner_id.dian_obligation_type_ids.mapped('dian_code'),
            'knowledge_base': config.knowledge_base and str(config.knowledge_base),
        }

    # ── Creación de la factura ───────────────────────────────────────────────

    @_ai_tool
    def _ai_tool_create_bill(self):
        """Create the bill with the standard button of the order and fill it from the XML."""
        self.ensure_one()
        if self.move_id:
            return {'invoice': self.move_id.display_name, 'already_created': True}
        code, detail = self._ai_get_exception()
        if code:
            self._ai_to_exception(code, detail)
            return {'stop': True, 'reason': detail}
        order = self.purchase_id
        before = order.invoice_ids
        try:
            order.action_create_invoice()
        except UserError as e:
            # Nothing invoiceable yet (usually no goods received): not an error of the agent
            self._ai_to_exception('not_invoiceable', str(e))
            return {'stop': True, 'reason': str(e)}
        move = order.invoice_ids - before
        if len(move) != 1:
            raise UserError(_('Crear factura de la orden %s no generó una sola factura.', order.name))
        self.move_id = move
        self._ai_complete_bill(move)
        return {
            'invoice': move.display_name,
            'invoice_id': move.id,
            'lines': [{
                'line_id': line.id,
                'product': line.product_id.display_name,
                'quantity': line.quantity,
                'unit_price': line.price_unit,
                'subtotal': line.price_subtotal,
                'taxes': line.tax_ids.mapped('name'),
            } for line in move.invoice_line_ids.filtered(lambda l: l.display_type == 'product')],
            'amount_total': move.amount_total,
        }

    def _ai_to_exception(self, code, detail):
        self.ensure_one()
        self.write({
            'ai_state': 'exception',
            'ai_exception_code': code,
            'ai_detail': detail,
            'ai_processing_since': False,
        })

    def _ai_complete_bill(self, move):
        self.ensure_one()
        vals = {
            'ai_document_id': self.id,
            'ref': self.name,
            'uuid_ei_ref': self.cufe,
            'invoice_date': self.xml_issue_date or self.emission_date,
        }
        if self.xml_due_date:
            vals.update({'invoice_payment_term_id': False, 'invoice_date_due': self.xml_due_date})
        config = self._ai_any_config()
        if config.journal_id:
            vals['journal_id'] = config.journal_id.id
        if self.payment_means_code:
            payment_option = self.env['dian.payment.option'].search(
                [('dian_code', '=', self.payment_means_code)], limit=1)
            if payment_option:
                vals['fe_payment_option_id'] = payment_option.id
        move.write(vals)

    # ── Cruce contra el XML ──────────────────────────────────────────────────

    def _ai_match_lines(self, move):
        """Pair each XML line with a bill line: by vendor code, then name, then position."""
        self.ensure_one()
        remaining = move.invoice_line_ids.filtered(
            lambda line: line.display_type == 'product' and line.quantity)
        xml_lines = self.invoice_line_ids.sorted('line_number')
        pairs = {}

        def by_code(xml_line, line):
            code = xml_line.sellers_item_identification
            if not code:
                return False
            sellers = line.product_id.seller_ids.filtered(lambda s: s.partner_id == move.partner_id)
            return code == line.product_id.default_code or code in sellers.mapped('product_code')

        def by_name(xml_line, line):
            description = (xml_line.description or '').strip().lower()
            name = (line.product_id.name or '').strip().lower()
            return bool(description and name) and (description in name or name in description)

        for matcher in (by_code, by_name):
            for xml_line in xml_lines:
                if xml_line.id in pairs:
                    continue
                match = remaining.filtered(lambda line, xl=xml_line: matcher(xl, line))[:1]
                if match:
                    pairs[xml_line.id] = match
                    remaining -= match
        for xml_line in xml_lines:
            if xml_line.id not in pairs and remaining:
                pairs[xml_line.id] = remaining[0]
                remaining = remaining[1:]
        return [(xml_line, pairs.get(xml_line.id)) for xml_line in xml_lines], remaining

    def _ai_compare(self):
        """Cross the bill against the XML. Plain code: the result does not depend on the model."""
        self.ensure_one()
        move = self.move_id
        config = self._ai_any_config()
        pairs, extra_lines = self._ai_match_lines(move)
        lines = []
        for xml_line, line in pairs:
            differences = []
            if not line:
                differences.append({'field': 'product', 'xml': xml_line.description, 'odoo': None})
            else:
                unit_price = xml_line.price_amount / (xml_line.base_quantity or 1.0)
                checks = (
                    ('quantity', xml_line.invoiced_quantity, line.quantity, None, config.line_tolerance_percent),
                    ('unit_price', unit_price, line.price_unit,
                     config.line_tolerance_amount, config.line_tolerance_percent),
                    ('subtotal', xml_line.line_extension_amount, line.price_subtotal,
                     config.line_tolerance_amount, config.line_tolerance_percent),
                )
                for field, xml_value, odoo_value, amount, percent in checks:
                    if _exceeds(xml_value, odoo_value, amount, percent):
                        differences.append({'field': field, 'xml': xml_value, 'odoo': odoo_value})
                xml_taxes = sorted(
                    round(tax.percent, 2) for tax in xml_line.tax_total_ids
                    if tax.percent and tax.tax_scheme_id in ('01', '04'))
                odoo_taxes = sorted(round(tax.amount, 2) for tax in line.tax_ids.flatten_taxes_hierarchy()
                                    if tax.amount > 0 and not tax.dian_tax_type_id.retention)
                if xml_taxes != odoo_taxes:
                    differences.append({'field': 'tax', 'xml': xml_taxes, 'odoo': odoo_taxes})
            lines.append({
                'line_number': xml_line.line_number,
                'invoice_line_id': line.id if line else None,
                'product': line.product_id.display_name if line else None,
                'ok': not differences,
                'differences': differences,
            })
        extra = [{'invoice_line_id': line.id, 'product': line.product_id.display_name} for line in extra_lines]
        # Withholdings are the buyer's: the XML total does not include them
        withholdings = sum(
            line.amount_currency for line in move.line_ids
            if line.tax_line_id and (line.tax_line_id.amount < 0 or line.tax_line_id.dian_tax_type_id.retention)
        )
        odoo_total = move.amount_total - withholdings
        total_ok = not _exceeds(
            self.payable_amount, odoo_total, config.total_tolerance_amount, config.total_tolerance_percent)
        currency_ok = not self.currency_id or self.currency_id == move.currency_id
        result = {
            'ok': total_ok and currency_ok and not extra and all(line['ok'] for line in lines),
            'lines': lines,
            'extra_invoice_lines': extra,
            'total': {'xml': self.payable_amount, 'odoo_without_withholdings': odoo_total, 'ok': total_ok},
            'currency': {'xml': self.currency_id.name, 'odoo': move.currency_id.name, 'ok': currency_ok},
        }
        self.ai_compare_result = json.dumps(result, ensure_ascii=False, default=str)
        return result

    @_ai_tool
    def _ai_tool_compare(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError(_('Primero debe crear la factura.'))
        return self._ai_compare()

    # ── Impuestos ────────────────────────────────────────────────────────────

    def _ai_serialize_tax(self, tax):
        return {
            'tax_id': tax.id,
            'name': tax.name,
            'percent': tax.amount,
            'withholding': bool(tax.amount < 0 or tax.dian_tax_type_id.retention),
            'type': tax.dian_tax_type_id.display_name,
            'minimum_base': tax.base_minimum,
            'base_by_city': tax.base_city,
            'base_value': tax.base_value,
        }

    @_ai_tool
    def _ai_tool_review_taxes(self):
        """Everything needed to judge the taxes of each line. Nothing is computed by the model."""
        self.ensure_one()
        move = self.move_id
        if not move:
            raise UserError(_('Primero debe crear la factura.'))
        partner = move.partner_id
        fiscal_position = move.fiscal_position_id
        lines = []
        for line in move.invoice_line_ids.filtered(lambda l: l.display_type == 'product'):
            product = line.product_id
            expected = product.supplier_taxes_id.filtered(lambda t: t.company_id == self.company_id)
            if fiscal_position:
                expected = fiscal_position.map_tax(expected)
            history = self.env['account.move.line'].search([
                ('company_id', '=', self.company_id.id),
                ('partner_id', '=', partner.id),
                ('product_id', '=', product.id),
                ('parent_state', '=', 'posted'),
                ('move_id.move_type', '=', 'in_invoice'),
                ('display_type', '=', 'product'),
            ], order='date desc', limit=3)
            lines.append({
                'line_id': line.id,
                'product': product.display_name,
                'applied_taxes': [self._ai_serialize_tax(tax) for tax in line.tax_ids],
                'expected_by_configuration': [self._ai_serialize_tax(tax) for tax in expected],
                'missing': (expected - line.tax_ids).mapped('name'),
                'not_expected': (line.tax_ids - expected).mapped('name'),
                'previous_invoices': [{
                    'invoice': previous.move_id.name,
                    'date': previous.date,
                    'taxes': previous.tax_ids.mapped('name'),
                } for previous in history],
                'learned_rules': self.env['dian.ai.rule']._ai_applicable(
                    self.company_id, partner, product)._ai_serialize(),
            })
        available = self.env['account.tax'].search([
            ('company_id', '=', self.company_id.id),
            ('type_tax_use', '=', 'purchase'),
        ], limit=100)
        return {
            'fiscal_position': fiscal_position.name,
            'vendor_responsibilities': self._ai_responsibilities(),
            'amount_untaxed': move.amount_untaxed,
            'amount_total': move.amount_total,
            'tax_groups': move.tax_totals,
            'lines': lines,
            'available_purchase_taxes': [self._ai_serialize_tax(tax) for tax in available],
        }

    @_ai_tool
    def _ai_tool_adjust_tax(self, line_id, tax_id, operation, reason, rule_id=0):
        """Add or remove a configured tax on a bill line. Odoo computes the amount."""
        self.ensure_one()
        move = self.move_id
        if not move or move.state != 'draft':
            raise UserError(_('Solo se ajustan impuestos de la factura en borrador de este documento.'))
        line = move.invoice_line_ids.filtered(lambda l: l.id == line_id and l.display_type == 'product')
        if not line:
            raise UserError(_('La línea %s no pertenece a la factura de este documento.', line_id))
        tax = self.env['account.tax'].search([
            ('id', '=', tax_id),
            ('company_id', '=', self.company_id.id),
            ('type_tax_use', '=', 'purchase'),
        ])
        if not tax:
            raise UserError(_('El impuesto %s no es un impuesto de compra de esta compañía.', tax_id))
        if operation not in ('add', 'remove'):
            raise UserError(_('La operación debe ser add o remove.'))
        rule = self.env['dian.ai.rule'].search([
            ('id', '=', rule_id),
            ('company_id', '=', self.company_id.id),
            ('state', '=', 'learned'),
            ('tax_id', '=', tax.id),
            ('operation', '=', operation),
        ]) if rule_id else self.env['dian.ai.rule']
        learned = rule and rule._ai_applies_to(move.partner_id, line.product_id)
        original = ', '.join(line.tax_ids.mapped('name'))
        line.tax_ids = [(4 if operation == 'add' else 3, tax.id)]
        vals = {'ai_explanation': '\n'.join(filter(None, [move.ai_explanation, reason]))}
        if not learned:
            vals['ai_review_state'] = 'pending'
            self.env['dian.ai.rule'].create({
                'company_id': self.company_id.id,
                'state': 'proposed',
                'origin': 'agent',
                'scope': 'partner_product',
                'partner_id': move.partner_id.id,
                'product_id': line.product_id.id,
                'field_name': 'tax',
                'operation': operation,
                'tax_id': tax.id,
                'original_value': original,
                'corrected_value': ', '.join(line.tax_ids.mapped('name')),
                'explanation': reason,
                'move_id': move.id,
            })
        move.write(vals)
        return {
            'line_id': line.id,
            'taxes': line.tax_ids.mapped('name'),
            'amount_total': move.amount_total,
            'requires_review': not learned,
            'rule_cited': rule.id if learned else None,
        }

    # ── Reclamo ──────────────────────────────────────────────────────────────

    @_ai_tool
    def _ai_tool_propose_claim(self, claim_code, reason):
        """Propose a claim (031). It is never sent from here: an accountant decides."""
        self.ensure_one()
        concept = self.env['dian.claim.concept'].search([('dian_code', '=', claim_code)], limit=1)
        if not concept:
            valid = self.env['dian.claim.concept'].search([]).mapped('dian_code')
            raise UserError(_('El código %(code)s no existe. Códigos válidos: %(valid)s',
                              code=claim_code, valid=', '.join(valid)))
        self.ie_claim_id = concept
        self._ai_create_activity(
            _('Reclamo (031) propuesto por el agente'),
            _('Concepto %(code)s - %(name)s. Motivo: %(reason)s',
              code=claim_code, name=concept.name, reason=reason))
        return {'proposed': True, 'sent': False}

    # ── Finalización ─────────────────────────────────────────────────────────

    def _ai_blocking_reasons(self, confidence, config):
        """Everything that prevents posting. The model cannot skip any of these checks."""
        self.ensure_one()
        move = self.move_id
        reasons = []
        code, detail = self._ai_get_exception()
        if code:
            reasons.append(detail)
        comparison = self._ai_compare()
        if not comparison['ok']:
            reasons.append(_('El cruce contra el XML tiene diferencias: %s',
                             self._ai_format_differences(comparison)))
        responsibilities = self._ai_responsibilities()
        if not responsibilities['match']:
            reasons.append(_(
                'Las responsabilidades del XML (%(xml)s) difieren de las del contacto (%(odoo)s).',
                xml=', '.join(responsibilities['xml']), odoo=', '.join(responsibilities['odoo'])))
            self._ai_create_activity(
                _('Corregir responsabilidades del proveedor'),
                _('Se propone actualizar %(partner)s con las responsabilidades del XML: %(xml)s',
                  partner=move.partner_id.name, xml=', '.join(responsibilities['xml'])))
        if confidence < config.confidence_threshold:
            reasons.append(_('La confianza del agente (%(confidence)s) no supera el umbral (%(threshold)s).',
                             confidence=confidence, threshold=config.confidence_threshold))
        if move.duplicated_ref_ids:
            reasons.append(_('Odoo advierte una posible factura duplicada: %s',
                             ', '.join(move.duplicated_ref_ids.mapped('display_name'))))
        notes = self._ai_pending_notes()
        if notes:
            reasons.append(_('La factura tiene notas pendientes de revisar: %s',
                             ', '.join(notes.mapped('name'))))
        if move.ai_review_state == 'pending' and not config.post_with_tax_adjustment:
            reasons.append(_('El agente ajustó impuestos y la compañía pide revisarlos antes de causar.'))
        return reasons

    def _ai_format_differences(self, comparison):
        parts = []
        for line in comparison['lines']:
            for difference in line['differences']:
                parts.append(_('línea %(line)s, %(field)s: XML %(xml)s, Odoo %(odoo)s',
                               line=line['line_number'], field=difference['field'],
                               xml=difference['xml'], odoo=difference['odoo']))
        for line in comparison['extra_invoice_lines']:
            parts.append(_('la factura tiene una línea que no está en el XML: %s', line['product']))
        if not comparison['total']['ok']:
            parts.append(_('total: XML %(xml)s, Odoo %(odoo)s',
                           xml=comparison['total']['xml'],
                           odoo=comparison['total']['odoo_without_withholdings']))
        if not comparison['currency']['ok']:
            parts.append(_('moneda: XML %(xml)s, Odoo %(odoo)s',
                           xml=comparison['currency']['xml'], odoo=comparison['currency']['odoo']))
        return '; '.join(parts)

    def _ai_run_record(self):
        return self.env['dian.ai.run'].sudo().browse(self.env.context.get('dian_ai_run_id'))

    def _ai_leave_draft(self, reasons):
        self.ensure_one()
        message = '\n'.join(reasons)
        self.write({'ai_state': 'draft', 'ai_detail': message, 'ai_processing_since': False})
        self.move_id.message_post(body=_('Agente de causación: la factura queda en borrador. %s', message))
        self._ai_create_activity(_('Revisar factura del agente'), message, self.move_id)
        self._ai_run_record().write({'outcome': 'draft', 'reasons': message})

    @_ai_tool
    def _ai_tool_finish(self, confidence, explanation):
        """Decide the fate of the bill: posted only if every check of the code passes."""
        self.ensure_one()
        move = self.move_id
        if not move:
            raise UserError(_('Primero debe crear la factura.'))
        config = self._ai_any_config()
        move.ai_explanation = '\n'.join(filter(None, [move.ai_explanation, explanation]))
        self._ai_run_record().write({'confidence': confidence, 'move_id': move.id})
        reasons = self._ai_blocking_reasons(confidence, config)
        if reasons:
            self._ai_leave_draft(reasons)
            return {'posted': False, 'state': 'draft', 'reasons': reasons}
        if config.mode == 'draft':
            self._ai_leave_draft([_('La compañía tiene el agente en modo Borrador: lista para publicar.')])
            return {'posted': False, 'state': 'draft', 'reasons': []}
        try:
            with self.env.cr.savepoint():
                move.action_post()
        except (UserError, AccessError) as e:
            self._ai_leave_draft([_('Odoo no permitió publicar: %s', e)])
            return {'posted': False, 'state': 'draft', 'reasons': [str(e)]}
        review = move.ai_review_state == 'pending'
        self.write({
            'ai_state': 'review' if review else 'posted',
            'ai_detail': False,
            'ai_processing_since': False,
        })
        self._ai_run_record().write({'outcome': 'review' if review else 'posted', 'automatic': 1})
        move.message_post(body=_('Agente de causación: factura causada. %s', explanation))
        if review:
            self._ai_create_activity(
                _('Para revisión: impuesto ajustado por el agente'),
                move.ai_explanation or explanation, move)
        return {'posted': True, 'state': self.ai_state, 'invoice': move.name}
