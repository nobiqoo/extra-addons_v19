
# -*- coding: utf-8 -*-

from odoo import api, models, fields
from datetime import date
from odoo.exceptions import ValidationError
from datetime import timedelta


class ProductTemplateMaintenanceDetail(models.Model):
    _name = 'product.template.maintenance.detail'
    _description = 'Detalles de Mantenimiento'

    repair_date = fields.Date(
        string='Fecha'
    )
    repair_id = fields.Many2one(
        comodel_name='repair.order',
        string='Orden de Mantenimiento'
    )
    product_tmpl_id = fields.Many2one(
        comodel_name='product.template',
        string='Producto Template'
    )
    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Producto'
    )
    repair_state = fields.Selection(
        string='Estado Orden de Mantenimiento',
        related="repair_id.state"
    )
    product_maintenance_id = fields.Many2one(
        comodel_name='product.maintenance',
        string='Producto de Mantenimiento'
    )
    period_tempario_ids = fields.Many2many('maintenance.tempario', string='Temparios Aplicados')
    repair_end_date = fields.Date(string="Fecha Fin", compute="_compute_repair_end_date", store=True)
    maintenance_type = fields.Selection([
        ('pre_inst', 'Pre-Instalación'),
        ('correctives', 'Correctivos'),
        ('precentive', 'Preventivos'),
        ('instalaciones', 'Instalaciones'),
        ('consultaciones', 'Consultaciones'),
        ('diagnosis', 'Diagnóstico'),
        ('inicial_review', 'Revisión Inicial'),
    ], string='Tipo de Mantenimiento')
    contract_id = fields.Many2one('maintenance.contract', string='Contrato')
    is_weekend = fields.Boolean(string='Fin de semana', help='La fecha cae en sábado o domingo.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            dt = vals.get('repair_date')
            if dt:
                # dt puede venir como str; normalizamos
                if isinstance(dt, str):
                    dt = fields.Date.from_string(dt)
                vals.setdefault('is_weekend', dt.weekday() >= 5)
        recs = super().create(vals_list)
        return recs

    def write(self, vals):
        res = super().write(vals)
        if 'repair_date' in vals:
            for rec in self:
                dt = rec.repair_date
                rec.is_weekend = bool(dt and dt.weekday() >= 5)
        return res

    @api.depends('repair_date')
    def _compute_repair_end_date(self):
        for rec in self:
            rec.repair_end_date = rec.repair_date + timedelta(days=1) if rec.repair_date else False

    def _get_repair_picking_type(self, product_maintenance):
        company = product_maintenance.company_id or self.env.company
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'repair_operation'),
            ('company_id', '=', company.id),
            ('sequence_id', '!=', False),
            '|', ('sequence_id.company_id', '=', False), ('sequence_id.company_id', '=', company.id),
        ], order='warehouse_id, id', limit=1)
        if not picking_type:
            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'repair_operation'),
                ('company_id', '=', False),
                ('sequence_id', '!=', False),
                '|', ('sequence_id.company_id', '=', False), ('sequence_id.company_id', '=', company.id),
            ], order='warehouse_id, id', limit=1)
        if not picking_type:
            raise ValidationError(
                "No hay un tipo de operación de reparación con secuencia configurado para la compañía '%s'."
                % company.display_name
            )
        return picking_type

    def create_repair(self):
        for record in self:
            if record.repair_id:
                continue
            product_maintenance = record.product_maintenance_id
            picking_type = record._get_repair_picking_type(product_maintenance)
            # Integración activos fijos: propagar cuenta analítica del equipo a la orden
            repair_vals = {
                'company_id': product_maintenance.company_id.id or self.env.company.id,
                'partner_id': product_maintenance.partner_id.id,
                'product_id': product_maintenance.product_id.id,
                'schedule_date': record.repair_date,
                'lot_id': product_maintenance.lot_id.id,
                'maintenance_product_id': product_maintenance.id,
                'picking_type_id': picking_type.id,
            }
            distribution = product_maintenance._get_analytic_distribution()
            if distribution:
                repair_vals['analytic_distribution'] = distribution
            repair = self.env['repair.order'].create(repair_vals)
            repair._onchange_technical_user_id()
            record.repair_id = repair.id
            for product_detail in product_maintenance.maintenance_product_ids:
                new_detail = product_detail.copy()
                new_detail.product_maintenance_id = False
                new_detail.write({'repair_id': repair.id})

    def create_repair_with_tempario(self):
        for record in self:
            contract = record.contract_id
            temparios = record.period_tempario_ids
            product = record.product_maintenance_id

            if not record.repair_id:
                picking_type = record._get_repair_picking_type(product)
                # Integración activos fijos: propagar cuenta analítica del equipo a la orden
                repair_vals = {
                    'company_id': product.company_id.id or self.env.company.id,
                    'partner_id': product.partner_id.id,
                    'product_id': product.product_id.id,
                    'schedule_date': record.repair_date,
                    'lot_id': product.lot_id.id,
                    'maintenance_product_id': product.id,
                    'maintenance_type': contract.maintenance_type,
                    'picking_type_id': picking_type.id,
                }
                distribution = product._get_analytic_distribution()
                if distribution:
                    repair_vals['analytic_distribution'] = distribution
                repair = self.env['repair.order'].create(repair_vals)
                record.repair_id = repair.id

                for tempario in temparios:
                    for spare in tempario.spare_part_ids:
                        self.env['product.template.maintenance.product'].create({
                            'repair_id': repair.id,
                            'product_id': spare.spare_part_id.product_variant_id.id,
                            'product_uom_id': spare.spare_part_id.uom_id.id,
                            'product_uom_qty': 1,
                        })

                    for t_act in tempario.activity_ids:
                        if not t_act.activity_id:
                            raise ValidationError(
                                "La línea de actividad del tempario '%s' no tiene 'Actividad' definida."
                                % tempario.display_name
                            )
                        self.env['repair.order.work.detail'].create({
                            'repair_id': repair.id,
                            'activity_id': t_act.activity_id.id,
                            'name': t_act.activity_id.name or 'Actividad',
                            'description': getattr(t_act, 'description', False) or '',
                            'date': record.repair_date,
                            'duration': getattr(t_act, 'duration', 1.0) or 1.0,
                        })
