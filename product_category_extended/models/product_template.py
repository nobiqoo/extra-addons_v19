# -*- coding: utf-8 -*-

import itertools
from odoo import models, fields, _, api
from odoo.exceptions import ValidationError, UserError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    secuence_reference = fields.Char(string="Secuence")
    skip_automatic_reference = fields.Boolean(
        string="Skip automatic reference", default=False)
    material_ids = fields.One2many(
        'product.material.template.line', 'tmpl_id', string="Materials")
    # show_reference = fields.Boolean('Show reference', string="Dummy boolean", compute='_compute_is_product_variant')

    # def _compute_is_product_variant(self):
    #     self.show_reference

    def write(self, vals):
        for record in self:
            if not record.secuence_reference:
                prefix = self.env['ir.sequence'].next_by_code(
                    'product.template.secuence.to.reference')
                vals['secuence_reference'] = prefix
            else:
                prefix = record.secuence_reference
            if 'skip_automatic_reference' in vals:
                skip_reference = vals['skip_automatic_reference']
            else:
                skip_reference = record.skip_automatic_reference
            if not skip_reference and self.env.company.apply_product_reference:
                reference = self.get_default_code_reference(
                    record, vals, prefix)
                vals['default_code'] = reference
        return super(ProductTemplate, self).write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            prefix = self.env['ir.sequence'].next_by_code(
                'product.template.secuence.to.reference')
            vals['secuence_reference'] = prefix
        res = super(ProductTemplate, self).create(vals_list)
        if not res.skip_automatic_reference and self.env.company.apply_product_reference:
            reference = self.get_default_code_reference(
                res, {}, res.secuence_reference)
            res.default_code = reference
        return res

    @api.model
    def default_get(self, field_list):
        res = super().default_get(field_list)
        company = self.env.company
        res.update(
            {
                "company_id": company.id,
            }
        )
        return res

    def update_variants_default_code(self):
        self.ensure_one()
        for product in self.product_variant_ids:
            product.update_default_code_to_product()

    def create_mrp_bom_lists(self):
        self._create_mrp_bom_ids()

    def get_default_code_reference(self, product, vals, code_reference):
        categ = vals['categ_id'] if 'categ_id' in vals else False
        if categ:
            categ = self.env['product.category'].browse(categ)
        else:
            categ = product.categ_id if product.categ_id else False
        cat_reference = ''
        if categ:
            categs = []
            while len(categ) > 0:
                if categ.reference != False:
                    categs.insert(0, categ.reference)
                categ = categ.parent_id
            try:
                cat_reference = cat_reference + ''.join(categs)
            except:
                raise ValidationError(
                    _("Some category reference has format incorrect"))

        reference = cat_reference + '/' + code_reference
        return reference

    def _prepare_variant_values(self, combination):
        self.ensure_one()
        res = {
            'product_tmpl_id': self.id,
            'product_template_attribute_value_ids': [(6, 0, combination.ids)],
            'active': self.active
        }
        if not self.skip_automatic_reference and self.env.company.apply_product_reference:
            default_code = self.get_variant_default_code(
                [com.product_attribute_value_id for com in combination])
            res['default_code'] = default_code
        return res

    def get_variant_default_code(self, attributes):
        tmlp_code = self.get_default_code_reference(
            self, {'categ_id': self.categ_id.id}, self.secuence_reference)
        attribute_list = []
        for attribute in attributes:
            if attribute.number != False:
                attribute_list.append(attribute.number)
        reference_code = tmlp_code + ''.join(attribute_list)
        return reference_code

    def _create_variant_ids(self):
        self.env.flush_all()
        Product = self.env["product.product"]

        variants_to_create = []
        variants_to_activate = Product
        variants_to_unlink = Product

        for tmpl_id in self:
            lines_without_no_variants = tmpl_id.valid_product_template_attribute_line_ids._without_no_variant_attributes()

            all_variants = tmpl_id.with_context(
                active_test=False).product_variant_ids.sorted(lambda p: (p.active, -p.id))

            current_variants_to_create = []
            current_variants_to_activate = Product

            # adding an attribute with only one value should not recreate product
            # write this attribute on every product to make sure we don't lose them
            single_value_lines = lines_without_no_variants.filtered(
                lambda ptal: len(ptal.product_template_value_ids._only_active()) == 1)
            if single_value_lines:
                for variant in all_variants:
                    combination = variant.product_template_attribute_value_ids | single_value_lines.product_template_value_ids._only_active()
                    # Do not add single value if the resulting combination would
                    # be invalid anyway.
                    if (
                        len(combination) == len(lines_without_no_variants) and
                        combination.attribute_line_id == lines_without_no_variants
                    ):
                        variant.product_template_attribute_value_ids = combination

            # Set containing existing `product.template.attribute.value` combination
            existing_variants = {
                variant.product_template_attribute_value_ids: variant for variant in all_variants
            }

            # Determine which product variants need to be created based on the attribute
            # configuration. If any attribute is set to generate variants dynamically, skip the
            # process.
            # Technical note: if there is no attribute, a variant is still created because
            # 'not any([])' and 'set([]) not in set([])' are True.
            if not tmpl_id.has_dynamic_attributes():
                # Iterator containing all possible `product.template.attribute.value` combination
                # The iterator is used to avoid MemoryError in case of a huge number of combination.
                all_combinations = itertools.product(*[
                    ptal.product_template_value_ids._only_active() for ptal in lines_without_no_variants
                ])
                # For each possible variant, create if it doesn't exist yet.
                for combination_tuple in all_combinations:
                    combination = self.env['product.template.attribute.value'].concat(
                        *combination_tuple)
                    is_combination_possible = tmpl_id._is_combination_possible_by_config(
                        combination, ignore_no_variant=True)
                    if not is_combination_possible:
                        continue
                    if combination in existing_variants:
                        current_variants_to_activate += existing_variants[combination]
                    else:
                        current_variants_to_create.append(
                            tmpl_id._prepare_variant_values(combination))
                        if len(current_variants_to_create) > 1000:
                            raise UserError(_(
                                'The number of variants to generate is too high. '
                                'You should either not generate variants for each combination or generate them on demand from the sales order. '
                                'To do so, open the form view of attributes and change the mode of *Create Variants*.'))
                variants_to_create += current_variants_to_create
                variants_to_activate += current_variants_to_activate

            else:
                for variant in existing_variants.values():
                    is_combination_possible = self._is_combination_possible_by_config(
                        combination=variant.product_template_attribute_value_ids,
                        ignore_no_variant=True,
                    )
                    if is_combination_possible:
                        current_variants_to_activate += variant
                variants_to_activate += current_variants_to_activate

            variants_to_unlink += all_variants - current_variants_to_activate

        if variants_to_activate:
            variants_to_activate.write({'active': True})
            for variant in variants_to_activate:
                variant.update_default_code_to_product()
        if variants_to_create:
            Product.create(variants_to_create)
        if variants_to_unlink:
            variants_to_unlink._unlink_or_archive()
            # prevent change if exclusion deleted template by deleting last variant
            if self.exists() != self:
                raise UserError(
                    _("This configuration of product attributes, values, and exclusions would lead to no possible variant. Please archive or delete your product directly if intended."))

        # prefetched o2m have to be reloaded (because of active_test)
        # (eg. product.template: product_variant_ids)
        # We can't rely on existing invalidate_cache because of the savepoint
        # in _unlink_or_archive.
        self.env.flush_all()
        self.env.invalidate_all()
        return True

    def _create_mrp_bom_ids(self):
        self.ensure_one()
        mrp_bom_list = []
        for variant in self.product_variant_ids:
            mrp_list = self.find_list_by_material_template(variant)
            if bool(mrp_list):
                if not variant.mrp_bom_since_tmpl:
                    bom_line_ids = []
                    for line in mrp_list:
                        bom_line_ids.append(
                            (0, 0, {
                             'product_id': line[0].id, 'product_qty': line[1]})
                        )
                    mrp_bom_list.append(
                        {
                            'code': variant.default_code,
                            'product_id': variant.id,
                            'product_tmpl_id': self.id,
                            'product_qty': 1,
                            'type': 'normal',
                            'bom_line_ids':
                                bom_line_ids
                        }
                    )
                else:
                    bom_line_ids = []
                    for line in mrp_list:
                        bom_line_ids.append(
                            (0, 0, {
                             'product_id': line[0].id, 'product_qty': line[1]})
                        )
                    mrp_bom_obj = variant.mrp_bom_since_tmpl
                    mrp_bom_obj.write(
                        {
                            'bom_line_ids': [(5, 0, 0)]
                        }
                    )
                    mrp_bom_obj.write(
                        {
                            'code': variant.default_code,
                            'bom_line_ids': bom_line_ids
                        }
                    )
        mrp_bom_objs = self.env['mrp.bom'].create(
            mrp_bom_list
        )
        for mrp_bom_obj in mrp_bom_objs:
            mrp_bom_obj.product_id.mrp_bom_since_tmpl = mrp_bom_obj
        print('mrp list created for variant nnn')

    def find_list_by_material_template(self, variant):
        """ Create de variants list based on the configured materials. Tab 'Materials'.

        Parameters
        ----------
        variant : object, required
            The variant object object for which the list will be created

        Returns
        -------
        variant_son
            a list of the variants with the correspondent quantity.

        Raises
        ------
        ValidationError
            If the material template no contain right values setted.
        """

        # Group the attributes and values in dicts
        attributes = {}
        bom_list = []
        for attr in self.attribute_line_ids:
            if len(attr.value_ids) > 1:
                attributes[attr.attribute_id.id] = attr.value_ids.ids
        for material in self.material_ids:
            tmpl_attributes = {}
            for attr_tmpl in material.product_tmpl_id.attribute_line_ids:
                if len(attr_tmpl.value_ids) > 1:
                    if attr_tmpl.attribute_id.id in attributes:
                        attr_line = variant.product_template_attribute_value_ids.filtered(
                            lambda line: line.attribute_id.id == attr_tmpl.attribute_id.id
                        )
                        secondary_value = attr_line.product_attribute_value_id.secondary_value
                        tmpl_attributes[attr_tmpl.attribute_id.name] = ([attr_line.product_attribute_value_id.id,
                                                                         secondary_value.id if secondary_value else False],
                                                                        attr_line.attribute_id.name + ': ' + attr_line.product_attribute_value_id.name
                                                                        )
                    else:
                        raise ValidationError(_("Attribute %s of the material --> %s is not on the template attributes.\n ") % (attr_tmpl.attribute_id.name,
                                                                                                                                material.product_tmpl_id.display_name
                                                                                                                                )
                                              )
            # Find the product variant with the specific attribute and values
            if bool(tmpl_attributes):
                # Código de prueba
                attributes_qty = len(tmpl_attributes)
                combination_num = 2**attributes_qty
                combination_list = list(range(combination_num))
                string_format_bin = '{0:0%sb}' % (attributes_qty)
                combination_list = [string_format_bin.format(
                    x) for x in combination_list]
                values_filters = []
                for combination in combination_list:
                    j = list(combination)
                    value_filter = []
                    for count, i in enumerate(j):
                        vals = list(tmpl_attributes.values())[count][0]
                        val_0 = vals[0]
                        val_1 = vals[1]
                        if i == '0':
                            line_filter = (
                                'product_template_attribute_value_ids.product_attribute_value_id', '=', val_0)
                        else:
                            line_filter = (
                                'product_template_attribute_value_ids.product_attribute_value_id', '=', val_1)
                        value_filter.append(line_filter)
                    values_filters.append(value_filter)
                for count, val_filter in enumerate(values_filters):
                    variant_son = self.env['product.product'].search([
                        ('product_template_attribute_value_ids.attribute_id',
                         'in', list(tmpl_attributes.keys())),
                        ('product_template_attribute_value_ids.product_tmpl_id',
                         '=', material.product_tmpl_id.id),
                    ] + val_filter,
                        limit=1
                    )
                    if variant_son.exists():
                        bom_list.append([variant_son, material.uom_qty])
                        break
                    else:
                        if count >= (combination_num):
                            warning_message = _(
                                "The material %s with the attributes --> [") % (material.product_tmpl_id.display_name)
                            for msg in tmpl_attributes.values():
                                warning_message += " " + msg[2] + ","
                            warning_message += _("] was not found.\n")
                            warning_message.replace(',]', ']')
                            raise ValidationError(warning_message)
        return bom_list


class ProductMaterialTemplateLine(models.Model):
    _name = 'product.material.template.line'

    product_tmpl_id = fields.Many2one(
        'product.template', string="Product", required=True)
    uom_id = fields.Many2one(
        'uom.uom', string="Unit of measure", related="product_tmpl_id.uom_id")
    uom_qty = fields.Float(string="Quantity", default=0, required=True)
    tmpl_id = fields.Many2one('product.template', string="Template")

    def write(self, vals):
        for record in self:
            uom_qty = uom_qty = vals['uom_qty'] if 'uom_qty' in vals else self.uom_qty
            if 'product_tmpl_id' in vals:
                tmpl = self.env['product.template'].browse(
                    vals['product_tmpl_id'])
            else:
                tmpl = record.product_tmpl_id
            vals['uom_qty'] = tmpl.uom_id._compute_quantity(
                uom_qty, tmpl.uom_id
            )
        return super(ProductMaterialTemplateLine, self).write(vals)

    @api.model_create_multi
    def create(self, vals):
        res = super(ProductMaterialTemplateLine, self).create(vals)
        res.uom_qty = res.uom_id._compute_quantity(
            res.uom_qty, res.product_tmpl_id.uom_id
        )
        return res
