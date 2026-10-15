# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import collections

from odoo import api, models, fields, tools, _


class WorksheetTemplate(models.Model):
    _inherit = 'worksheet.template'

    inspection_release_format = fields.Boolean(
        'Inspection Release Format', default=False)
    refurbishment_format = fields.Boolean(
        'Refurbishment Format', default=False)
    biomedical_equipment_inspection_format = fields.Boolean(
        'Biomedical Equipment Inspection Format', default=False)

    @api.onchange('inspection_release_format', 'refurbishment_format', 'biomedical_equipment_inspection_format')
    def _onchange_format(self):
        if self.inspection_release_format:
            self.refurbishment_format = False
            self.biomedical_equipment_inspection_format = False
        elif self.refurbishment_format:
            self.inspection_release_format = False
            self.biomedical_equipment_inspection_format = False
        elif self.biomedical_equipment_inspection_format:
            self.refurbishment_format = False
            self.inspection_release_format = False

    def update_worksheet_model(self):

        res_model = self.res_model.replace('.', '_')
        name = 'x_%s_worksheet_template_%d' % (res_model, self.id)

        # Busca si el modelo ya existe
        existing_model = self.env['ir.model'].sudo().search(
            [('model', '=', name)], limit=1)
        if existing_model:
            # Actualiza campos faltantes
            fields_to_add = self._prepare_default_fields_values()
            for _operation, _priority, vals in fields_to_add:
                existing_field = self.env['ir.model.fields'].search([
                    ('name', '=', vals['name']),
                    ('model_id', '=', existing_model.id)
                ], limit=1)
                if not existing_field:
                    self.env['ir.model.fields'].create(
                        dict(vals, model_id=existing_model.id))
            # Encuentra la vista form principal
            form_view = self.env['ir.ui.view'].sudo().search([
                ('model', '=', existing_model.model),
                ('type', '=', 'form'),
                ('mode', '=', 'primary')
            ], limit=1)

            if form_view:
                # Actualiza la vista con el nuevo arch
                new_arch = self._default_quality_check_worksheet_form_arch()
                form_view.write({
                    'arch_db': new_arch
                })

                # Actualiza la vista de árbol si existe
                tree_view = self.env['ir.ui.view'].sudo().search([
                    ('model', '=', existing_model.model),
                    ('type', '=', 'tree')
                ], limit=1)
                if tree_view:
                    tree_view.write({
                        'arch_db': self._prepare_default_tree_view_values(existing_model)['arch']
                    })

                # Limpia las cachés para que los cambios sean visibles
                self.env['ir.ui.view'].clear_caches()
                self.env['ir.qweb'].clear_caches()

            # Actualiza el reporte QWeb si es necesario
            self.sudo()._generate_qweb_report_template()
        return True

    def _generate_worksheet_model(self):
        """_summary_
            #! ODONE:
            OVERWRITE THIS METHOD TO ADD ADDITIONAL FIELDS TO THE WORKSHEET MODEL FOR EURODENT
        """
        self.ensure_one()
        res_model = self.res_model.replace('.', '_')
        name = 'x_%s_worksheet_template_%d' % (res_model, self.id)

        # create access rights and rules
        if not hasattr(self, f'_get_{res_model}_manager_group'):
            raise NotImplementedError(
                f'Method _get_{res_model}_manager_group not implemented on {res_model}')
        if not hasattr(self, f'_get_{res_model}_user_group'):
            raise NotImplementedError(
                f'Method _get_{res_model}_user_group not implemented on {res_model}')
        if not hasattr(self, f'_get_{res_model}_access_all_groups'):
            raise NotImplementedError(
                f'Method _get_{res_model}_access_all_groups not implemented on {res_model}')

        # while creating model it will initialize the init_models method from create of ir.model
        # and there is related field of model_id in mail template so it's going to recursive loop while recompute so used flush
        self.env.flush_all()

        # Generate xml ids for some records: views, actions and models. This will let the ORM handle
        # the module uninstallation (removing all data belonging to the module using their xml ids).
        # NOTE: this is not needed for ir.model.fields, ir.model.access and ir.rule, as they are in
        # delete 'cascade' mode, so their database entries will removed (no need their xml id).
        module_name = getattr(self, f'_get_{res_model}_module_name')()
        xid_values = []
        model_counter = collections.Counter()

        def register_xids(records):
            for record in records:
                model_counter[record._name] += 1
                xid_values.append({
                    'name': "{}_{}_{}".format(
                        name,
                        record._name.replace('.', '_'),
                        model_counter[record._name],
                    ),
                    'module': module_name,
                    'model': record._name,
                    'res_id': record.id,
                    'noupdate': True,
                })
            return records

        # generate the ir.model (and so the SQL table)
        model = register_xids(self.env['ir.model'].sudo().create({
            'name': self.name,
            'model': name,
            'field_id': self._prepare_default_fields_values() + [
                (0, 0, {
                    'name': 'x_name',
                    'field_description': 'Name',
                    'ttype': 'char',
                    'related': 'x_%s_id.name' % res_model,
                }),
            ]
        }))
        if self.inspection_release_format or self.refurbishment_format:
            # Generate the model for the lines
            line_model_name = name + '_line'
            line_model = register_xids(self.env['ir.model'].sudo().create({
                'name': self.name + ' Line',
                'model': line_model_name,
                'field_id': [
                    (0, 0, {
                        'name': 'x_%s_id' % name,
                        'field_description': self.name,
                        'ttype': 'many2one',
                        'relation': name,
                        'on_delete': 'cascade',
                    }),
                    (0, 0, {
                        'name': 'x_default_code',
                        'field_description': _('Default Code'),
                        'ttype': 'char',
                    }),
                    (0, 0, {
                        'name': 'x_product_id',
                        'field_description': _('Decription'),
                        'ttype': 'many2one',
                        'relation': 'product.product',
                    }),
                    (0, 0, {
                        'name': 'x_invima',
                        'field_description': 'Registo Sanitario',
                        'ttype': 'char',
                    }),
                    (0, 0, {
                        'name': 'x_product_uom_qty',
                        'field_description': _('Planned Quantity'),
                        'ttype': 'float',
                    }),
                    (0, 0, {
                        'name': 'x_quantity',
                        'field_description': _('Quantity Done'),
                        'ttype': 'float',
                    }),
                    (0, 0, {
                        'name': 'x_product_uom',
                        'field_description': _('Unit of Measure'),
                        'ttype': 'many2one',
                        'relation': 'uom.uom',
                    }),
                    (0, 0, {
                        'name': 'x_lot_id',
                        'field_description': _('Lot/Serial Number'),
                        'ttype': 'many2one',
                        'relation': 'stock.lot',
                    }),
                    (0, 0, {
                        'name': 'x_expiration_date',
                        'field_description': _('Expiration Date'),
                        'ttype': 'date',
                    }),
                    # Inspection Release Format
                    (0, 0, {
                        'name': 'x_analysis_certificate',
                        'field_description': _('Analysis Certificate'),
                        'ttype': 'selection',
                        'selection': "[('approve', 'Cumple'), ('not_approve', 'No Cumple'), ('not_apply', 'No Aplica')]",
                        'readonly': False,
                    }),
                    (0, 0, {
                        'name': 'x_technical_specification',
                        'field_description': _('Technical Specification'),
                        'ttype': 'selection',
                        'selection': "[('approve', 'Cumple'), ('not_approve', 'No Cumple'), ('not_apply', 'No Aplica')]",
                        'readonly': False,
                    }),
                    (0, 0, {
                        'name': 'x_factory_labelling',
                        'field_description': _('Factory Labelling'),
                        'ttype': 'selection',
                        'selection': "[('approve', 'Cumple'), ('not_approve', 'No Cumple'), ('not_apply', 'No Aplica')]",
                        'readonly': False,
                    }),
                    (0, 0, {
                        'name': 'x_sanitary_registration',
                        'field_description': _('Sanitary Registration'),
                        'ttype': 'selection',
                        'selection': "[('approve', 'Cumple'), ('not_approve', 'No Cumple'), ('not_apply', 'No Aplica')]",
                        'readonly': False,
                    }),
                    (0, 0, {
                        'name': 'x_non_obligatory_certificate',
                        'field_description': _('Non Obligatory Certificate'),
                        'ttype': 'selection',
                        'selection': "[('approve', 'Cumple'), ('not_approve', 'No Cumple'), ('not_apply', 'No Aplica')]",
                        'readonly': False,
                    }),
                    (0, 0, {
                        'name': 'x_returns',
                        'field_description': _('Returns'),
                        'ttype': 'integer',
                        'readonly': False,
                    }),
                    (0, 0, {
                        'name': 'x_rejections',
                        'field_description': _('Rejections'),
                        'ttype': 'integer',
                        'readonly': False,
                    }),
                    (0, 0, {
                        'name': 'x_released_for_refurbishment',
                        'field_description': _('Released for Refurbishment'),
                        'ttype': 'integer',
                        'readonly': False,
                    }),
                    # Refurbishment Format
                    (0, 0, {
                        'name': 'x_receive',
                        'ttype': 'integer',
                        'field_description': 'Recibe',
                    }),
                    (0, 0, {
                        'name': 'x_use',
                        'ttype': 'integer',
                        'field_description': 'Utiliza',
                    }),
                    (0, 0, {
                        'name': 'x_refuse',
                        'ttype': 'integer',
                        'field_description': 'Rechaza',
                    }),
                    (0, 0, {
                        'name': 'x_return_to',
                        'ttype': 'integer',
                        'field_description': 'Devuelve',
                    }),
                    (0, 0, {
                        'name': 'x_witness',
                        'ttype': 'text',
                        'field_description': 'Testigo',
                    }),
                ]
            }))

            # Add the One2many field to the worksheet model
            self.env['ir.model.fields'].sudo().create({
                'name': 'x_line_ids',
                'field_description': _('Lines'),
                'ttype': 'one2many',
                'relation': line_model_name,
                'relation_field': 'x_%s_id' % name,
                'model_id': model.id,
            })

            self.env['ir.model.access'].sudo().create([{
                'name': line_model_name + '_manager_access',
                'model_id': line_model.id,
                'group_id': getattr(self, '_get_%s_manager_group' % res_model)().id,
                'perm_create': True,
                'perm_write': True,
                'perm_read': True,
                'perm_unlink': True,
            }, {
                'name': line_model_name + '_user_access',
                'model_id': line_model.id,
                'group_id': getattr(self, '_get_%s_user_group' % res_model)().id,
                'perm_create': True,
                'perm_write': True,
                'perm_read': True,
                'perm_unlink': True,
            }])

        self.env['ir.model.access'].sudo().create([{
            'name': name + '_manager_access',
            'model_id': model.id,
            'group_id': getattr(self, '_get_%s_manager_group' % res_model)().id,
            'perm_create': True,
            'perm_write': True,
            'perm_read': True,
            'perm_unlink': True,
        }, {
            'name': name + '_user_access',
            'model_id': model.id,
            'group_id': getattr(self, '_get_%s_user_group' % res_model)().id,
            'perm_create': True,
            'perm_write': True,
            'perm_read': True,
            'perm_unlink': True,
        }])

        # create the view to extend by 'studio' and add the user custom fields
        __, __, search_view = register_xids(self.env['ir.ui.view'].sudo().create([
            self._prepare_default_form_view_values(model),
            self._prepare_default_tree_view_values(model),
            self._prepare_default_search_view_values(model)
        ]))
        action = register_xids(self.env['ir.actions.act_window'].sudo().create({
            'name': 'Worksheets',
            'res_model': model.model,
            'search_view_id': search_view.id,
            'context': {
                'edit': False,
                'create': False,
                'delete': False,
                'duplicate': False,
            }
        }))

        self.env['ir.model.data'].sudo().create(xid_values)

        # link the worksheet template to its generated model and action
        self.write({
            'action_id': action.id,
            'model_id': model.id,
        })
        # this must be done after form view creation and filling the 'model_id' field
        self.sudo()._generate_qweb_report_template()

        # Add unique constraint on the x_model_id field since we want one worksheet per host record
        conname = '%s_x_%s_id_uniq' % (name, res_model)
        concode = 'unique(x_%s_id)' % (res_model)
        tools.add_constraint(self.env.cr, name, conname, concode)

    def _prepare_default_fields_values(self):
        res = super()._prepare_default_fields_values()
        if self.inspection_release_format or self.refurbishment_format:
            aditional_fields = [
                (0, 0, {
                    'name': 'x_inspection_release_format',
                    'ttype': 'boolean',
                    'field_description': 'Formato de Inspección y Liberación',
                }),
                (0, 0, {
                    'name': 'x_refurbishment_format',
                    'ttype': 'boolean',
                    'field_description': 'Formato de Acondicionamiento',
                }),
                (0, 0, {
                    'name': 'x_company_id',
                    'field_description': 'Compañía',
                    'ttype': 'many2one',
                    'relation': 'res.company',
                }),
                (0, 0, {
                    'name': 'x_purchase_import_id',
                    'ttype': 'many2one',
                    'relation': 'purchase.import',
                    'field_description': _('Purchase Import'),
                    'readonly': True,
                }),
                (0, 0, {
                    'name': 'x_partner_id',
                    'ttype': 'many2one',
                    'relation': 'res.partner',
                    'field_description': _('Supplier'),
                    'readonly': True,
                }),
                (0, 0, {
                    'name': 'x_packaging_unit',
                    'ttype': 'selection',
                    'field_description': _('Packaging Unit'),
                    'selection': "[('box','Cajas'),('pallet','Pallets')]",
                }),
                (0, 0, {
                    'name': 'x_packaging_state_physical',
                    'ttype': 'selection',
                    'field_description': _('Packaging Quantity'),
                    'selection': "[('approve','Cumple'),('not_approve','No Cumple')]",
                }),
                (0, 0, {
                    'name': 'x_total_verification',
                    'ttype': 'selection',
                    'field_description': _('Total Verification'),
                    'selection': "[('yes','Si'),('no','No')]",
                }),
                (0, 0, {
                    'name': 'x_random_sampling',
                    'ttype': 'selection',
                    'field_description': _('Random Sampling'),
                    'selection': "[('yes','Si'),('no','No')]",
                }),
                (0, 0, {
                    'name': 'x_purchase_order_id',
                    'ttype': 'many2one',
                    'relation': 'purchase.order',
                    'field_description': _('Purchase Order'),
                    'readonly': True,
                }),
                (0, 0, {
                    'name': 'x_date',
                    'ttype': 'date',
                    'field_description': 'Fecha',
                }),
                (0, 0, {
                    'name': 'x_refurbishment_order',
                    'ttype': 'char',
                    'field_description': 'No de Orden de Acondicionamiento',
                    'readonly': True,
                }),
                (0, 0, {
                    'name': 'x_date_received',
                    'ttype': 'date',
                    'field_description': _('Date Received'),
                }),
                (0, 0, {
                    'name': 'x_reported_quantity',
                    'ttype': 'float',
                    'field_description': _('Reported Quantity'),
                    'readonly': True,
                }),
                (0, 0, {
                    'name': 'x_received_quantity',
                    'ttype': 'float',
                    'field_description': _('Received Quantity'),
                }),
                (0, 0, {
                    'name': 'x_inspection_date',
                    'ttype': 'date',
                    'field_description': _('Inspection Date'),
                }),
                (0, 0, {
                    'name': 'x_release_date',
                    'ttype': 'date',
                    'field_description': _('Release Date'),
                }),
                (0, 0, {
                    'name': 'x_sampling_quantity',
                    'ttype': 'float',
                    'field_description': _('Sampling Quantity'),
                }),
                (0, 0, {
                    'name': 'x_observations',
                    'ttype': 'text',
                    'field_description': _('Observations'),
                }),
                # Approvals for inspection release format
                (0, 0, {
                    'name': 'x_technical_manager',
                    'ttype': 'char',
                    'field_description': 'VoBo. Dirección Técnica',
                    'readonly': True,
                }),
                (0, 0, {
                    'name': 'x_technical_manager_signature',
                    'ttype': 'binary',
                    'field_description': 'Firma Dirección Técnica',
                    'readonly': True,
                }),
                (0, 0, {
                    'name': 'x_warehouse_manager',
                    'ttype': 'char',
                    'field_description': 'VoBo. Director de Almacén',
                    'readonly': True,
                }),
                (0, 0, {
                    'name': 'x_warehouse_manager_signature',
                    'ttype': 'binary',
                    'field_description': 'Firma Director de Almacén',
                    'readonly': True,
                }),
                (0, 0, {
                    'name': 'x_importations_manager',
                    'ttype': 'char',
                    'field_description': 'VoBo. Director de Importaciones',
                    'readonly': True,
                }),
                (0, 0, {
                    'name': 'x_importations_manager_signature',
                    'ttype': 'binary',
                    'field_description': 'Firma Director de Importaciones',
                    'readonly': True,
                }),
                (0, 0, {
                    'name': 'x_warehouse_auxiliary',
                    'ttype': 'char',
                    'field_description': 'VoBo. Auxiliar de Almacén',
                    'readonly': True,
                }),
                (0, 0, {
                    'name': 'x_warehouse_auxiliary_signature',
                    'ttype': 'binary',
                    'field_description': 'Firma Auxiliar de Almacén',
                    'readonly': True,
                }),
                (0, 0, {
                    'name': 'x_importations_analyst',
                    'ttype': 'char',
                    'field_description': 'VoBo. Analista de Importaciones',
                    'readonly': True,
                }),
                (0, 0, {
                    'name': 'x_importations_analyst_signature',
                    'ttype': 'binary',
                    'field_description': 'Firma Analista de Importaciones',
                    'readonly': True,
                }),
                # Approvals for refurbishment format
                (0, 0, {
                    'name': 'x_refurbishment_responsible',
                    'ttype': 'char',
                    'field_description': 'VoBo. Responsable del Acondicionamiento',
                    'readonly': True,
                }),
                (0, 0, {
                    'name': 'x_refurbishment_responsible_signature',
                    'ttype': 'binary',
                    'field_description': 'Firma Responsable del Acondicionamiento',
                    'readonly': True,
                }),
                # Driver
                (0, 0, {
                    'name': 'x_driver_name',
                    'ttype': 'char',
                    'field_description': 'Nombre',
                }),
                (0, 0, {
                    'name': 'x_driver_vat',
                    'ttype': 'char',
                    'field_description': 'Cédula',
                }),
                (0, 0, {
                    'name': 'x_license_plate',
                    'ttype': 'char',
                    'field_description': 'Placa',
                }),
                (0, 0, {
                    'name': 'x_conveyor',
                    'ttype': 'char',
                    'field_description': 'Transportadora',
                }),
                (0, 0, {
                    'name': 'x_conveyer_number',
                    'ttype': 'char',
                    'field_description': 'Número de Transporte',
                }),
                (0, 0, {
                    'name': 'x_signature_drive',
                    'ttype': 'binary',
                    'field_description': 'firma de conductor',
                })
            ]
            res.extend(aditional_fields)
        elif self.biomedical_equipment_inspection_format:
            aditional_fields = [
                (0, 0, {
                    'name': 'x_execute_date',
                    'ttype': 'date',
                    'field_description': 'Fecha de Ejecución',
                }),
                (0, 0, {
                    'name': 'x_company_id',
                    'field_description': 'Compañía',
                    'ttype': 'many2one',
                    'relation': 'res.company',
                }),
                (0, 0, {
                    'name': 'x_product_name',
                    'ttype': 'char',
                    'field_description': 'Nombre del Producto',
                    'readonly': True,
                }),
                (0, 0, {
                    'name': 'x_product_code',
                    'ttype': 'char',
                    'field_description': 'Código del Producto',
                    'readonly': True,
                }),
                (0, 0, {
                    'name': 'x_lot_ids',
                    'ttype': 'many2many',
                    'relation': 'stock.lot',
                    'field_description': 'Lote/Serial',
                    'readonly': True,
                }),
                (0, 0, {
                    'name': 'x_model',
                    'ttype': 'char',
                    'field_description': 'Modelo',
                }),
                (0, 0, {
                    'name': 'x_brand_id',
                    'ttype': 'many2one',
                    'relation': 'product.brand',
                    'field_description': 'Marca',
                    'readonly': True,
                }),
                (0, 0, {
                    'name': 'x_ott_id',
                    'ttype': 'many2one',
                    'relation': 'repair.order',
                    'field_description': 'OTT',
                }),
                # Datos Generales del Equipo
                # Verificación General
                (0, 0, {
                    'name': 'x_box_sealed',
                    'ttype': 'selection',
                    'field_description': 'La Caja se Encuentra Sellada',
                    'selection': "[('approve','Cumple'),('not_approve','No Cumple')]",
                }),
                (0, 0, {
                    'name': 'x_box_not_wet',
                    'ttype': 'selection',
                    'field_description': 'La Caja no Presenta Humedad',
                    'selection': "[('approve','Cumple'),('not_approve','No Cumple')]",
                }),
                (0, 0, {
                    'name': 'x_box_free_knock',
                    'ttype': 'selection',
                    'field_description': 'La Caja no Presenta Golpes',
                    'selection': "[('approve','Cumple'),('not_approve','No Cumple')]",
                }),
                (0, 0, {
                    'name': 'x_box_equipment_data',
                    'ttype': 'selection',
                    'field_description': 'La Caja Cuenta con los Datos del Equipo',
                    'selection': "[('approve','Cumple'),('not_approve','No Cumple')]",
                }),
                (0, 0, {
                    'name': 'x_packing_observation',
                    'ttype': 'text',
                    'field_description': 'Observaciones de Verificación Embalaje',
                }),
                (0, 0, {
                    'name': 'x_free_knock',
                    'ttype': 'selection',
                    'field_description': 'No Presenta Golpes',
                    'selection': "[('approve','Cumple'),('not_approve','No Cumple')]",
                }),
                (0, 0, {
                    'name': 'x_not_scratches',
                    'ttype': 'selection',
                    'field_description': 'No Presenta Rayones',
                    'selection': "[('approve','Cumple'),('not_approve','No Cumple')]",
                }),
                (0, 0, {
                    'name': 'x_not_dirty',
                    'ttype': 'selection',
                    'field_description': 'No Prsenta Suciedad',
                    'selection': "[('approve','Cumple'),('not_approve','No Cumple')]",
                }),
                (0, 0, {
                    'name': 'x_optimal_ensamble',
                    'ttype': 'selection',
                    'field_description': 'Ensamble en Óptimas Condiciones',
                    'selection': "[('approve','Cumple'),('not_approve','No Cumple')]",
                }),
                (0, 0, {
                    'name': 'x_equipment_observation',
                    'ttype': 'text',
                    'field_description': 'Observaciones de Verificación del Equipo',
                }),
                # Verificación de Accesorios
                (0, 0, {
                    'name': 'x_accessories_include',
                    'ttype': 'selection',
                    'field_description': 'El Equipo Cuenta con Accesorios',
                    'selection': "[('approve','Cumple'),('not_approve','No Cumple')]",
                }),
                (0, 0, {
                    'name': 'x_accessories_complete',
                    'ttype': 'selection',
                    'field_description': 'Accesorios Completos',
                    'selection': "[('approve','Cumple'),('not_approve','No Cumple')]",
                }),
                (0, 0, {
                    'name': 'x_calibration_elements',
                    'ttype': 'selection',
                    'field_description': 'Elementos de Calibración',
                    'selection': "[('approve','Cumple'),('not_approve','No Cumple')]",
                }),
                (0, 0, {
                    'name': 'x_accessories_other',
                    'ttype': 'text',
                    'field_description': 'Otros',
                }),
                # Lista de Accesorios
                (0, 0, {
                    'name': 'x_accessories_include_list',
                    'ttype': 'text',
                    'field_description': 'Accesorios Incluidos en el Equipo',
                }),
                (0, 0, {
                    'name': 'x_accessories_not_include_list',
                    'ttype': 'text',
                    'field_description': 'Accesorios Faltantes Según Manual',
                }),
                # Lista de Software
                (0, 0, {
                    'name': 'x_has_software',
                    'ttype': 'selection',
                    'field_description': '¿Cuenta con Software?',
                    'selection': "[('apply','Aplica'),('not_apply','No Aplica')]",
                }),
                (0, 0, {
                    'name': 'x_which_software',
                    'ttype': 'text',
                    'field_description': 'Si Aplica Indique los Softwares',
                }),
                # Pruebas de Funcionamiento
                (0, 0, {
                    'name': 'x_equipment_turn_on',
                    'ttype': 'selection',
                    'field_description': 'El Equipo Enciende',
                    'selection': "[('approve','Cumple'),('not_approve','No Cumple')]",
                }),
                (0, 0, {
                    'name': 'x_equipment_work',
                    'ttype': 'selection',
                    'field_description': 'Funciona Totalmente',
                    'selection': "[('approve','Cumple'),('not_approve','No Cumple')]",
                }),
                (0, 0, {
                    'name': 'x_observation_functionality',
                    'ttype': 'text',
                    'field_description': 'Observaciones de Funcionamiento',
                }),
                (0, 0, {
                    'name': 'x_work_test',
                    'ttype': 'text',
                    'field_description': 'Describa las Pruebas de Funcionamiento Ejecutadas:',
                }),
                # Sellos de Verifiación
                (0, 0, {
                    'name': 'x_sanitary_registration_seal',
                    'ttype': 'selection',
                    'field_description': 'Registro Sanitario',
                    'selection': "[('apply','Aplica'),('not_apply','No Aplica')]",
                }),
                (0, 0, {
                    'name': 'x_not_required_certificate_seal',
                    'ttype': 'selection',
                    'field_description': 'Certificado No Requiere',
                    'selection': "[('apply','Aplica'),('not_apply','No Aplica')]",
                }),
                (0, 0, {
                    'name': 'x_warranty',
                    'ttype': 'selection',
                    'field_description': 'Garantía',
                    'selection': "[('apply','Aplica'),('not_apply','No Aplica')]",
                }),
                (0, 0, {
                    'name': 'x_initial_check',
                    'ttype': 'text',
                    'field_description': 'Revisión Inicial',
                }),
                # Datos de quien ejecuta la revisión
                (0, 0, {
                    'name': 'x_name_reviewed',
                    'ttype': 'char',
                    'field_description': 'Nombre',
                    'readonly': True,
                }),
                (0, 0, {
                    'name': 'x_vat_reviewed',
                    'ttype': 'char',
                    'field_description': 'Documento de Identidad',
                    'readonly': True,
                }),
                (0, 0, {
                    'name': 'x_job_id',
                    'ttype': 'many2one',
                    'relation': 'hr.job',
                    'field_description': 'Cargo',
                    'readonly': True,
                }),
                (0, 0, {
                    'name': 'x_name_reviewed_signature',
                    'ttype': 'binary',
                    'field_description': 'Firma',
                    'readonly': True,
                }),
                # Administración Técnica
                (0, 0, {
                    'name': 'x_technical_manager',
                    'ttype': 'char',
                    'field_description': 'VoBo. Dirección Técnica',
                    'readonly': True,
                }),
                (0, 0, {
                    'name': 'x_technical_manager_signature',
                    'ttype': 'binary',
                    'field_description': 'Firma Dirección Técnica',
                    'readonly': True,
                }),
                (0, 0, {
                    'name': 'x_vat_manager',
                    'ttype': 'char',
                    'field_description': 'Documento de Identidad',
                    'readonly': True,
                }),
                (0, 0, {
                    'name': 'x_job_manager_id',
                    'ttype': 'many2one',
                    'relation': 'hr.job',
                    'field_description': 'Cargo',
                    'readonly': True,
                }),
            ]
            res.extend(aditional_fields)
        return res

    @api.model
    def _default_quality_check_worksheet_form_arch(self):
        if self.inspection_release_format or self.refurbishment_format:
            return """
                <form create="false" js_class="worksheet_validation">
                    <sheet>
                        <h1 invisible="context.get('studio') or context.get('default_x_quality_check_id')">
                            <field name="x_quality_check_id" domain="[('test_type', '=', 'worksheet')]"/>
                        </h1>
                        <group>
                            <group>
                                <field name="x_inspection_release_format" invisible="1"/>
                                <field name="x_purchase_import_id"/>
                                <field name="x_company_id" invisible="1"/>
                                <field name="x_date" invisible="x_inspection_release_format"/>
                                <field name="x_partner_id" invisible="x_refurbishment_format"/>
                                <field name="x_packaging_unit" widget="radio" options="{'horizontal': true}" invisible="x_refurbishment_format"/>
                                <field name="x_packaging_state_physical" widget="radio" options="{'horizontal': true}" invisible="x_refurbishment_format"/>
                                <field name="x_total_verification" widget="radio" options="{'horizontal': true}" invisible="x_refurbishment_format"/>
                                <field name="x_random_sampling" widget="radio" options="{'horizontal': true}" invisible="x_refurbishment_format"/>
                            </group>
                            <group>
                                <field name="x_refurbishment_format" invisible="1"/>
                                <field name="x_purchase_order_id"/>
                                <field name="x_refurbishment_order" invisible="x_inspection_release_format"/>
                                <field name="x_date_received" invisible="x_refurbishment_format"/>
                                <field name="x_reported_quantity" invisible="x_refurbishment_format"/>
                                <field name="x_received_quantity" invisible="x_refurbishment_format"/>
                                <field name="x_inspection_date" invisible="x_refurbishment_format"/>
                                <field name="x_release_date" invisible="x_refurbishment_format"/>
                                <field name="x_sampling_quantity" invisible="x_refurbishment_format"/>
                            </group>
                        </group>
                        <notebook>
                            <page string="Lines">
                                <field name="x_line_ids">
                                    <tree editable="bottom">
                                        <field name="x_default_code"/>
                                        <field name="x_product_id"/>
                                        <field name="x_invima" column_invisible="parent.x_inspection_release_format"/>
                                        <field name="x_product_uom_qty" column_invisible="parent.x_refurbishment_format"/>
                                        <field name="x_quantity"/>
                                        <field name="x_product_uom" column_invisible="parent.x_refurbishment_format"/>
                                        <field name="x_lot_id"/>
                                        <field name="x_expiration_date"/>
                                        <field name="x_analysis_certificate" column_invisible="parent.x_refurbishment_format"/>
                                        <field name="x_technical_specification" column_invisible="parent.x_refurbishment_format"/>
                                        <field name="x_factory_labelling" column_invisible="parent.x_refurbishment_format"/>
                                        <field name="x_sanitary_registration" column_invisible="parent.x_refurbishment_format"/>
                                        <field name="x_non_obligatory_certificate" column_invisible="parent.x_refurbishment_format"/>
                                        <field name="x_returns" column_invisible="parent.x_refurbishment_format"/>
                                        <field name="x_rejections" column_invisible="parent.x_refurbishment_format"/>
                                        <field name="x_released_for_refurbishment" column_invisible="parent.x_refurbishment_format"/>
                                        <field name="x_receive" column_invisible="parent.x_inspection_release_format"/>
                                        <field name="x_use" column_invisible="parent.x_inspection_release_format"/>
                                        <field name="x_refuse" column_invisible="parent.x_inspection_release_format"/>
                                        <field name="x_return_to" column_invisible="parent.x_inspection_release_format"/>
                                        <field name="x_witness" column_invisible="parent.x_inspection_release_format"/>
                                    </tree>
                                </field>
                            </page>
                        </notebook>
                        <separator/>
                        <field name="x_observations" placeholder="Observaciones..." invisible="x_refurbishment_format"/>
                        <group>
                            <group>
                                <field name="x_technical_manager" />
                                <field name="x_technical_manager_signature" widget="signature"/>
                                <field name="x_importations_manager" invisible="x_refurbishment_format"/>
                                <field name="x_importations_manager_signature" invisible="x_refurbishment_format" widget="signature"/>
                                <field name="x_importations_analyst" invisible="x_refurbishment_format"/>
                                <field name="x_importations_analyst_signature" invisible="x_refurbishment_format" widget="signature"/>
                            </group>
                            <group>
                                <field name="x_warehouse_manager" invisible="x_refurbishment_format"/>
                                <field name="x_warehouse_manager_signature" invisible="x_refurbishment_format" widget="signature"/>
                                <field name="x_refurbishment_responsible" invisible="x_inspection_release_format"/>
                                <field name="x_refurbishment_responsible_signature" invisible="x_inspection_release_format" widget="signature"/>
                                <field name="x_warehouse_auxiliary" invisible="x_refurbishment_format"/>
                                <field name="x_warehouse_auxiliary_signature" invisible="x_refurbishment_format" widget="signature"/>
                            </group>
                        </group>
                        <group name="driver" string="Conductor" invisible="x_refurbishment_format">
                            <group>
                                <field name="x_driver_name"/>
                                <field name="x_driver_vat"/>
                                <field name="x_license_plate"/>
                                <field name="x_conveyor"/>
                                <field name="x_conveyer_number"/>
                            </group>
                            <group>
                                <field name="x_signature_drive" widget="signature"/>
                            </group>
                        </group>
                    </sheet>
                </form>
            """
        elif self.biomedical_equipment_inspection_format:
            return """
                <form create="false" js_class="worksheet_validation">
                    <sheet>
                        <h1 invisible="context.get('studio') or context.get('default_x_quality_check_id')">
                            <field name="x_quality_check_id" domain="[('test_type', '=', 'worksheet')]"/>
                        </h1>
                        <group>
                            <group></group>
                            <group>
                                <field name="x_execute_date"/>
                                <field name="x_company_id" invisible="1"/>
                            </group>
                        </group>
                        <group>
                            <group>
                                <field name="x_product_name"/>
                                <field name="x_product_code"/>
                                <field name="x_lot_ids" widget="many2many_tags"/>
                            </group>
                            <group>
                                <field name="x_model"/>
                                <field name="x_brand_id"/>
                                <field name="x_ott_id" domain="[('maintenance_type', '=', 'initial_review')]"/>
                            </group>
                        </group>
                        <h3 class="text-center">DATOS GENERALES DEL EQUIPO</h3>
                        <group string="Verificación General">
                            <group string="Verificación del Embalaje">
                                <field name="x_box_sealed" widget="radio" options="{'horizontal': true}"/>
                                <field name="x_box_not_wet" widget="radio" options="{'horizontal': true}"/>
                                <field name="x_box_free_knock" widget="radio" options="{'horizontal': true}"/>
                                <field name="x_box_equipment_data" widget="radio" options="{'horizontal': true}"/>
                                <field name="x_packing_observation" invisible="x_box_sealed != 'not_approve' and x_box_not_wet != 'not_approve' and x_box_free_knock != 'not_approve' and x_box_equipment_data != 'not_approve'"/>
                            </group>
                            <group string="Verificación del estado Físico del Equipo">
                                <field name="x_free_knock" widget="radio" options="{'horizontal': true}"/>
                                <field name="x_not_scratches" widget="radio" options="{'horizontal': true}"/>
                                <field name="x_not_dirty" widget="radio" options="{'horizontal': true}"/>
                                <field name="x_optimal_ensamble" widget="radio" options="{'horizontal': true}"/>
                                <field name="x_equipment_observation" invisible="x_free_knock != 'not_approve' and x_not_scratches != 'not_approve' and x_not_dirty != 'not_approve' and x_optimal_ensamble != 'not_approve'"/>
                            </group>
                        </group>
                        <group string="Verificación de Accesorios">
                            <group>
                                <field name="x_accessories_include" widget="radio" options="{'horizontal': true}"/>
                                <field name="x_accessories_complete" widget="radio" options="{'horizontal': true}"/>
                            </group>
                            <group>
                                <field name="x_calibration_elements" widget="radio" options="{'horizontal': true}"/>
                                <field name="x_accessories_other"/>
                            </group>
                        </group>
                        <group string="Lista de Accesorios">
                            <group>
                                <field name="x_accessories_include_list"/>
                            </group>
                            <group>
                                <field name="x_accessories_not_include_list"/>
                            </group>
                        </group>
                        <group string="Lista de Software">
                            <group>
                                <field name="x_has_software" widget="radio" options="{'horizontal': true}"/>
                            </group>
                            <group invisible="x_has_software != 'apply'">
                                <field name="x_which_software"/>
                            </group>
                        </group>
                        <group string="Pruebas de Funcionamiento">
                            <group>
                                <field name="x_equipment_turn_on" widget="radio" options="{'horizontal': true}"/>
                                <field name="x_equipment_work" widget="radio" options="{'horizontal': true}"/>
                                <field name="x_observation_functionality" invisible="x_equipment_turn_on != 'not_approve' and x_equipment_work != 'not_approve'"/>
                            </group>
                            <group>
                                <field name="x_work_test"/>
                            </group>
                        </group>
                        <group string="Sellos de Verificación">
                            <group>
                                <field name="x_sanitary_registration_seal" widget="radio" options="{'horizontal': true}"/>
                                <field name="x_not_required_certificate_seal" widget="radio" options="{'horizontal': true}"/>
                            </group>
                            <group>
                                <field name="x_warranty" widget="radio" options="{'horizontal': true}"/>
                                <field name="x_initial_check"/>
                            </group>
                        </group>
                        <group string="Aprobaciones">
                            <group string="Datos de Quien Ejecuta la Revisión">
                                <field name="x_name_reviewed"/>
                                <field name="x_vat_reviewed"/>
                                <field name="x_job_id"/>
                                <field name="x_name_reviewed_signature" widget="signature"/>
                            </group>
                            <group string="VoBo Administración Técnica">
                                <field name="x_technical_manager"/>
                                <field name="x_vat_manager"/>
                                <field name="x_job_manager_id"/>
                                <field name="x_technical_manager_signature" widget="signature"/>
                            </group>
                        </group>
                    </sheet>
                </form>

            """
        else:
            return """
            <form create="false" js_class="worksheet_validation">
                <sheet>
                    <h1 invisible="context.get('studio') or context.get('default_x_quality_check_id')">
                        <field name="x_quality_check_id" domain="[('test_type', '=', 'worksheet')]"/>
                    </h1>
                    <group>
                        <group>
                            <field name="x_comments"/>
                            <field name="x_passed"/>
                        </group>
                        <group>
                        </group>
                    </group>
                </sheet>
            </form>
        """
