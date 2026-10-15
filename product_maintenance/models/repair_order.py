
# -*- coding: utf-8 -*-

from odoo import _, models, fields, api
from datetime import date, datetime
from odoo.exceptions import UserError
from odoo.tools.misc import groupby


class RepairOrder(models.Model):
    _inherit = 'repair.order'

    technical_user_id = fields.Many2one(
        comodel_name='res.users',
        string='Técnico'
    )
    alternate_technical_user_id = fields.Many2one(
        comodel_name='res.users',
        string='Técnico Suplente'
    )
    close_date = fields.Date(
        string='Fecha de Reparación'
    )
    work_detail_ids = fields.One2many(
        comodel_name='repair.order.work.detail',
        string='Trabajos',
        inverse_name='repair_id'
    )
    excuter_type = fields.Selection(
        selection=[
            ('internal', 'Interno'),
            ('external', 'Externo')
        ],
        default='internal',
        string='Tipo Ejecutor'
    )
    excuter_user_id = fields.Many2one(
        comodel_name='res.users',
        string='Ejecutor Mantenimiento'
    )
    maintenance_type = fields.Selection(
        selection=[
            ('pre_inst', 'Preinstalaciones'),
            ('correctives', 'Correctivos'),
            ('precentive', 'Preventivos'),
            ('instalations', 'Instalaciones'),
            ('consultations', 'Asesorias'),
            ('diagnosis', 'Diagnostico'),
            ('initial_review', 'Revisión Inicial')
        ],
        string='Tipo de Mantenimiento',
        default='precentive'
    )
    account_analytic_id = fields.Many2one(
        comodel_name='account.analytic.account',
        string='Cuentas Analiticas',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        check_company=True
    )
    analytic_distribution = fields.Json(
        string='Analytic Distribution'
    )
    analytic_precision = fields.Integer(
        store=False,
        default=lambda self: self.env['decimal.precision'].precision_get('Percentage Analytic'),
    )
    is_presential = fields.Boolean(
        string='Presencial',
        default=True
    )
    maintenance_product_ids = fields.One2many(
        comodel_name='product.template.maintenance.product',
        string='Productos Aditamientos',
        inverse_name='repair_id'
    )
    service_reasons = fields.Char(
        string='Motivos de Servicio',
    )
    recommendations = fields.Char(
        string='Recomendaciones'
    )
    city_id = fields.Many2one(
        comodel_name='res.city',
        string='Ciudad'
    )
    domain_product_ids = fields.Many2many(
        comodel_name='product.product',
        string='Dominio Productos',
        compute='_compute_domain_product_ids',
        store=True
    )
    product_id = fields.Many2one(
        domain="[('type', 'in', ['product', 'consu']), '|', ('company_id', '=', company_id), ('company_id', '=', False), '|', ('id', 'in', picking_product_ids), ('id', '=?', picking_product_id)]",
    )
    picking_type_id = fields.Many2one(
        domain="[('code', '=', 'repair_operation'), ('company_id', '=', company_id), ('warehouse_id.enabled_for_repair', '=', True)]",
    )
    maintenance_product_id = fields.Many2one(
        comodel_name='product.maintenance',
        string='Producto de Mantenimiento',
        domain="[('id', 'in', domain_maintenance_product_ids)]",
        check_company=True
    )
    maintenance_equipment_ids = fields.Many2many(
        comodel_name='product.maintenance',
        relation='repair_order_product_maintenance_rel',
        column1='repair_id',
        column2='maintenance_product_id',
        string='Equipos de Mantenimiento',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        check_company=True
    )
    workcenter_id = fields.Many2one(
        comodel_name='mrp.workcenter',
        string='Centro de Trabajo',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        check_company=True
    )
    production_id = fields.Many2one(
        comodel_name='mrp.production',
        string='Orden de fabricación',
        domain="[('company_id', '=', company_id)]",
        check_company=True
    )
    workorder_id = fields.Many2one(
        comodel_name='mrp.workorder',
        string='Orden de trabajo',
        domain="[('company_id', '=', company_id)]",
        check_company=True
    )
    origin = fields.Char(
        string='Origen'
    )
    is_maintenance_product = fields.Boolean(
        string='Es Equipo de Mantenimiento',
        compute='_compute_is_maintenance_product'
    )
    domain_maintenance_product_ids = fields.Many2many(
        comodel_name='product.maintenance',
        string='Dominio Productos de Mantenimiento',
        compute='_compute_domain_maintenance_product_ids',
        store=True
    )
    check_required_maintenance_product = fields.Boolean(
        string='Producto de Mantenimiento Requerido',
        default=True
    )
    survey_id = fields.Many2one(
        comodel_name='survey.survey',
        string='Encuesta'
    )
    survey_response_id = fields.Many2one(
        comodel_name='survey.user_input',
        string='Respuesta Encuesta'
    )
    use_native_parts_in_maintenance = fields.Boolean(
        related='company_id.use_native_parts_in_maintenance'
    )
    require_product_to_repair_in_maintenance = fields.Boolean(
        related='company_id.require_product_to_repair_in_maintenance'
    )
    enable_survey = fields.Boolean(
        string='Habilitar encuesta',
        default=False,
        help='Si está activo, esta orden requiere generar y completar la encuesta antes de finalizar.'
    )
    # Integración activos fijos: campo related para condicionar obligatoriedad de analítica en vista
    require_analytic_in_maintenance = fields.Boolean(
        related='company_id.require_analytic_in_maintenance',
    )

    # Integración activos fijos: validar cuenta analítica obligatoria según política de la compañía
    @api.constrains('analytic_distribution', 'company_id')
    def _check_required_analytic_distribution(self):
        for record in self:
            if record.company_id.require_analytic_in_maintenance and not record.analytic_distribution:
                raise UserError(
                    _("La política de la compañía requiere cuenta analítica en las órdenes de mantenimiento. "
                      "Asigne una distribución analítica antes de confirmar.")
                )

    @api.constrains('company_id', 'product_id')
    def _check_required_product_to_repair(self):
        for record in self:
            if record.company_id.require_product_to_repair_in_maintenance and not record.product_id:
                raise UserError(
                    _("Debe diligenciar el Producto a reparar para esta compañía.")
                )

    def _get_account_analytic_distribution(self):
        self.ensure_one()
        if self.analytic_distribution:
            return self.analytic_distribution
        if self.account_analytic_id:
            return {str(self.account_analytic_id.id): 100.0}
        return False

    @api.onchange('account_analytic_id')
    def _onchange_account_analytic_id(self):
        for record in self:
            if record.account_analytic_id and not record.analytic_distribution:
                record.analytic_distribution = {str(record.account_analytic_id.id): 100.0}

    @api.onchange('analytic_distribution')
    def _onchange_analytic_distribution(self):
        for record in self:
            distribution = record._get_account_analytic_distribution()
            for line in record.maintenance_product_ids:
                line.analytic_distribution = distribution or False
            for move in record.move_ids:
                move.analytic_distribution = distribution or False

    def _sync_analytic_distribution_to_related_lines(self):
        for record in self:
            distribution = record._get_account_analytic_distribution()
            record.maintenance_product_ids.write({
                'analytic_distribution': distribution or False,
            })
            record.move_ids.write({
                'analytic_distribution': distribution or False,
            })

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('analytic_distribution') and vals.get('account_analytic_id'):
                vals['analytic_distribution'] = {str(vals['account_analytic_id']): 100.0}
        records = super().create(vals_list)
        records._sync_analytic_distribution_to_related_lines()
        records._sync_maintenance_equipment_fields()
        return records

    def write(self, vals):
        if not vals.get('analytic_distribution') and vals.get('account_analytic_id'):
            vals['analytic_distribution'] = {str(vals['account_analytic_id']): 100.0}
        res = super().write(vals)
        if 'analytic_distribution' in vals or 'account_analytic_id' in vals:
            self._sync_analytic_distribution_to_related_lines()
        if (
                not self.env.context.get('skip_maintenance_equipment_sync')
                and ({'maintenance_product_id', 'maintenance_equipment_ids'} & set(vals))
        ):
            self._sync_maintenance_equipment_fields()
        return res

    def _sync_maintenance_equipment_fields(self):
        for record in self:
            if record.maintenance_product_id and record.maintenance_product_id not in record.maintenance_equipment_ids:
                record.with_context(skip_maintenance_equipment_sync=True).write({
                    'maintenance_equipment_ids': [(4, record.maintenance_product_id.id)],
                })
            elif record.maintenance_equipment_ids and not record.maintenance_product_id:
                record.with_context(skip_maintenance_equipment_sync=True).write({
                    'maintenance_product_id': record.maintenance_equipment_ids[0].id,
                })

    @api.depends('product_id', 'product_id.is_maintenance_product', 'check_required_maintenance_product')
    def _compute_is_maintenance_product(self):
        for record in self:
            if not record.check_required_maintenance_product:
                record.is_maintenance_product = False
            else:
                record.is_maintenance_product = record.product_id.is_maintenance_product

    @api.depends('product_id', 'product_id.is_maintenance_product')
    def _compute_domain_maintenance_product_ids(self):
        for record in self:
            products = self.env['product.maintenance'].search([
                ('product_id', '=', record.product_id.id),
                '|', ('company_id', '=', False), ('company_id', '=', record.company_id.id),
            ])
            record.domain_maintenance_product_ids = products

    @api.depends('partner_id')
    def _compute_domain_product_ids(self):
        for record in self:
            record.domain_product_ids = False
            if record.partner_id:
                products = self.env['product.product'].search([('company_id', '=', record.company_id.id)])
                record.domain_product_ids = products

    @api.depends('picking_id', 'partner_id')
    def compute_picking_product_ids(self):
        for repair in self:
            repair.picking_product_ids = False
            repair.picking_product_ids = repair.picking_id.move_ids.product_id
            if repair.partner_id:
                products = self.env['product.maintenance'].search([
                    ('partner_id', '=', repair.partner_id.id),
                    '|', ('company_id', '=', False), ('company_id', '=', repair.company_id.id),
                ])
                for product in products:
                    repair.picking_product_ids += product.product_id

    @api.onchange('maintenance_product_id')
    def _onchange_maintenance_product_id(self):
        for record in self:
            record.lot_id = record.maintenance_product_id.lot_id
            if record.maintenance_product_id and record.maintenance_product_id not in record.maintenance_equipment_ids:
                record.maintenance_equipment_ids = [(4, record.maintenance_product_id.id)]
            # Integración activos fijos: heredar cuenta analítica del equipo de mantenimiento
            if record.maintenance_product_id and record.maintenance_product_id.analytic_distribution:
                record.analytic_distribution = record.maintenance_product_id.analytic_distribution

    @api.onchange('maintenance_equipment_ids')
    def _onchange_maintenance_equipment_ids(self):
        for record in self:
            if record.maintenance_equipment_ids and not record.maintenance_product_id:
                record.maintenance_product_id = record.maintenance_equipment_ids[0]
            if record.maintenance_product_id:
                record.lot_id = record.maintenance_product_id.lot_id
            # Integración activos fijos: fusionar distribuciones analíticas de todos los equipos
            if record.maintenance_equipment_ids:
                merged = {}
                for equipment in record.maintenance_equipment_ids:
                    if equipment.analytic_distribution:
                        merged.update(equipment.analytic_distribution)
                record.analytic_distribution = merged or False
            else:
                record.analytic_distribution = False

    @api.onchange('technical_user_id')
    def _onchange_technical_user_id(self):
        for record in self:
            record.excuter_user_id = record.technical_user_id

    def action_repair_end(self):
        for record in self:
            attachments = self.env['ir.attachment'].search([
                ('res_model', '=', record._name),
                ('res_id', '=', record.id)
            ])
            if not attachments:
                raise UserError('No se puede finalizar esta orden '
                                'debido a que no se ha adjuntado ningún archivo.')
            if record.maintenance_type not in ('initial_review', 'consultations') and record.enable_survey:
                if not record.survey_response_id:
                    raise UserError('No se puede finalizar esta orden '
                                    'debido a que no se ha generado una encuesta.')
                if not record.survey_response_id.deadline:
                    raise UserError('No se puede finalizar esta orden '
                                    'debido a que el campo fecha limite en la respuesta asociada no está diligenciado.')
                if record.survey_response_id.state != 'done' and record.survey_response_id.deadline > datetime.now():
                    raise UserError('No se puede finalizar esta orden '
                                    'debido a que no se ha obtenido respuesta a la encuesta.')
            record.close_date = date.today()
        return super().action_repair_end()

    # Override native method
    def action_validate(self):
        if self.use_native_parts_in_maintenance:
            return super().action_validate()
        self.ensure_one()
        if self.filtered(lambda repair: any(m.product_uom_qty < 0 for m in repair.move_ids)):
            raise UserError("No puede reparar cantidades negativas.")
        repairs_to_confirm = self.filtered(lambda repair: repair.state == 'draft')
        repairs_to_confirm._check_company()
        repairs_to_confirm.write({'state': 'confirmed'})

    def action_repair_done(self):
        native_repairs = self.filtered('use_native_parts_in_maintenance')
        custom_repairs = self - native_repairs
        if native_repairs:
            super(RepairOrder, native_repairs).action_repair_done()
        custom_repairs.write({'state': 'done'})
        return True

    # Override native method: exclude warehouses not enabled for repairs from the
    # default/available "Tipo de operación" (picking_type_id) computation
    def _get_picking_type(self):
        companies = self.company_id or self.env.company
        if not self:
            default_warehouse = self.env.user.with_company(companies.id)._get_default_warehouse_id()
            if (
                default_warehouse
                and default_warehouse.repair_type_id
                and default_warehouse.enabled_for_repair
            ):
                return {(companies, self.env.user): default_warehouse.repair_type_id}
            fallback_type = self.env['stock.picking.type'].search([
                ('code', '=', 'repair_operation'),
                ('company_id', '=', companies.id),
                ('warehouse_id.enabled_for_repair', '=', True),
            ], limit=1)
            return {(companies, self.env.user): fallback_type} if fallback_type else {}

        picking_type_by_company_user = {}
        without_default_warehouse_companies = set()
        for (company, user), dummy in groupby(self, lambda r: (r.company_id, r.user_id)):
            default_warehouse = user.with_company(company.id)._get_default_warehouse_id()
            if (
                default_warehouse
                and default_warehouse.repair_type_id
                and default_warehouse.enabled_for_repair
            ):
                picking_type_by_company_user[(company, user)] = default_warehouse.repair_type_id
            else:
                without_default_warehouse_companies.add(company.id)

        if not without_default_warehouse_companies:
            return picking_type_by_company_user

        domain = [
            ('code', '=', 'repair_operation'),
            ('warehouse_id.company_id', 'in', list(without_default_warehouse_companies)),
            ('warehouse_id.enabled_for_repair', '=', True),
        ]
        picking_types = self.env['stock.picking.type'].search_read(domain, ['company_id'], load=False)
        for picking_type in picking_types:
            if (picking_type.company_id, False) not in picking_type_by_company_user:
                picking_type_by_company_user[(picking_type.company_id, False)] = picking_type
        return picking_type_by_company_user

    def _get_total_time(self):
        return sum([x.duration for x in self.work_detail_ids])

    def _get_name_repair(self):
        list_name = self.name.split('/')
        return 'OTT-' + list_name[2]

    def _get_internal_notes(self):
        return self.env['helpdesk.ticket'].remove_html_tags(self.internal_notes).replace('\n', '')
