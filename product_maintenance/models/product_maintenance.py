# -*- coding: utf-8 -*-

from odoo import _, api, models, fields
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta


class ProductMaintenance(models.Model):
    _name = 'product.maintenance'
    _description = 'Productos de Mantenimiento'

    name = fields.Char(
        string='Nombre'
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Cliente'
    )
    provider_id = fields.Many2one(
        comodel_name='res.partner',
        string='Proveedor'
    )
    brand_id = fields.Many2one(
        comodel_name='product.brand',
        string='Marca'
    )
    model = fields.Char(
        string='Modelo texto'
    )
    model_id = fields.Many2one(
        comodel_name='product.model',
        string='Modelo'
    )
    utilization_type = fields.Selection([
        ('km', 'Kilómetros'),
        ('hour', 'Horómetro')
    ], string='Utilización')
    daily_use = fields.Float(
        string='Utilización Diaria',
        help='Promedio de horas de uso diario del equipo'
    )
    current_mileage = fields.Float(
        string='Kilometraje Actual',
        help='Kilometraje actual del equipo'
    )
    mileage_log_ids = fields.One2many(
        'maintenance.mileage.log',
        'product_maintenance_id',   # <- debe existir en el comodel
        string='Histórico de Horómetro',
        readonly=True,
    )
    serial_no = fields.Char(
        string='Número de serie'
    )
    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Producto',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        check_company=True
    )
    effective_date = fields.Date(
        string='Fecha Efectiva',
        default=fields.Date.context_today,
        help="Esta fecha se usara para calcular el tiempo medio entre fallos"
    )
    maintenance_to_date = fields.Date(
        string='Fecha Final de Mantenimiento',
    )
    expected_mtbf = fields.Integer(
        string='Tiempo medio estimado entre fallos'
    )
    mtbf = fields.Integer(
        compute='_compute_maintenance_request',
        string='Tiempo medio entre fallos'
    )
    mttr = fields.Integer(
        compute='_compute_maintenance_request',
        string='Tiempo Medio de Reparación',
        help='Mean Time To Repair'
    )
    estimated_next_failure = fields.Date(
        compute='_compute_maintenance_request',
        string='Proximo fallo estimado',
        help='Computed as Latest Failure Date + MTBF'
    )
    latest_failure_date = fields.Date(
        compute='_compute_maintenance_request',
        string='Último Fallo'
    )
    maintenance_detail_ids = fields.One2many(
        comodel_name='product.template.maintenance.detail',
        string='Detalle de Mantenimiento',
        inverse_name='product_maintenance_id',
    )
    repair_order_ids = fields.One2many(
        comodel_name='repair.order',
        string='Ordenes de mantenimiento',
        inverse_name='maintenance_product_id',
    )
    company_id = fields.Many2one(
        comodel_name='res.company', 
        string='Compañía',
        default=lambda self: self.env.company
    )
    workcenter_id = fields.Many2one(
        comodel_name='mrp.workcenter',
        string='Centro de Trabajo',
        check_company=True
    )
    show_maintenance_tab_in_product_maintenance = fields.Boolean(
        related='company_id.show_maintenance_tab_in_product_maintenance'
    )
    maintenance_product_ids = fields.One2many(
        comodel_name='product.template.maintenance.product',
        string='Productos Aditamientos',
        inverse_name='product_maintenance_id'
    )
    risk_type = fields.Char(
        string='Tipo de Riesgo',
    )
    voltage = fields.Char(
        string='Voltaje (V)'
    )
    current = fields.Char(
        string='Corriente (A)'
    )
    frequency = fields.Char(
        string='Frecuencia (Hz)'
    )
    power = fields.Char(
        string='Potencia (W)'
    )
    pretion = fields.Char(
        string='Presión (Psi)'
    )
    temperature = fields.Char(
        string='Temperatura (°C)'
    )
    weight = fields.Char(
        string='Peso (Kg)'
    )
    flow = fields.Char(
        string='Flujo (L/min)'
    )
    other = fields.Char(
        string='Otro'
    )
    order_id = fields.Many2one(
        comodel_name='purchase.order',
        string='Orden de Compra',
        check_company=True
    )
    picking_id = fields.Many2one(
        comodel_name='stock.picking',
        string='Transferencia',
        check_company=True
    )
    stock_move_id = fields.Many2one(
        comodel_name='stock.move',
        string='Movimiento de Inventario',
        check_company=True
    )
    lot_id = fields.Many2one(
        comodel_name='stock.lot',
        string='Lote',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        check_company=True
    )
    placa = fields.Many2one(
        comodel_name='product.plate',
        string='Placa'
    )
    maintenance_to_date = fields.Date(
        string='Fecha Final de Mantenimiento',
    )
    product_maintenance_open_count = fields.Integer(
        string="Ordenes Actuales",
        compute='_compute_product_maintenance_count'
    )
    warranty_end_date = fields.Date(
        string='Fecha Fin de Garantía'
    )
    location_name = fields.Char(
        string='Ubicación'
    )
    city_id = fields.Many2one(
        comodel_name='res.city',
        string='Ciudad'
    )
    health_registration = fields.Char(
        string='Registro Sanitario'
    )
    have_catalog = fields.Selection(
        string='Posee Catálogo de Manejo u Operación',
        selection=[
            ('no', 'No'),
            ('yes', 'Si')
        ],
        default='no'
    )
    manufacturing = fields.Char(
        string='Fabricación'
    )
    active = fields.Boolean(default=True)
    tempario_ids = fields.Many2many(
        'maintenance.tempario',
        string='Temparios aplicables',
        compute='_compute_tempario_by_model',
        store=False,
    )
    employee_id = fields.Many2one('hr.employee', string='Empleado Asignado')

    # Integración activos fijos: asociación equipo – activo fijo y herencia de cuenta analítica
    asset_id = fields.Many2one(
        comodel_name='account.asset',
        string='Activo Fijo',
        domain="[('state', '=', 'open'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        check_company=True,
    )
    analytic_distribution = fields.Json(
        string='Analytic Distribution',
    )
    analytic_precision = fields.Integer(
        store=False,
        default=lambda self: self.env['decimal.precision'].precision_get('Percentage Analytic'),
    )
    require_analytic_in_maintenance = fields.Boolean(
        related='company_id.require_analytic_in_maintenance',
    )

    # Integración activos fijos: herencia automática de cuenta analítica desde el activo
    @api.onchange('asset_id')
    def _onchange_asset_id(self):
        for rec in self:
            if rec.asset_id:
                rec.analytic_distribution = rec.asset_id.analytic_distribution or False
            else:
                rec.analytic_distribution = False

    @api.constrains('asset_id')
    def _check_asset_id(self):
        for rec in self:
            if rec.require_analytic_in_maintenance and not rec.asset_id:
                raise ValidationError(
                    _("La política de la compañía requiere asociar un activo fijo "
                      "al equipo de mantenimiento '%s'.")
                    % rec.display_name
                )
            if not rec.asset_id:
                continue
            if rec.asset_id.state != 'open':
                raise ValidationError(
                    _("El activo fijo '%s' no está en estado activo. "
                      "Solo se pueden asociar activos en estado 'En ejecución'.")
                    % rec.asset_id.display_name
                )
            if rec.require_analytic_in_maintenance and not rec.asset_id.analytic_distribution:
                raise ValidationError(
                    _("El activo fijo '%s' no tiene cuenta analítica configurada. "
                      "La política de la compañía requiere cuenta analítica para equipos de mantenimiento.")
                    % rec.asset_id.display_name
                )

    @api.depends('product_id', 'product_id.product_tmpl_id', 'model_id')
    def _compute_tempario_by_model(self):
        """Trae temparios cuyos modelos coincidan con el del producto o con self.model_id (fallback).
        No hacemos depends sobre product.template.model_id porque puede no existir en esta BD.
        """
        TemparioModel = self.env['maintenance.tempario.model']
        PT = self.env['product.template']

        # Helper: obtener el campo de modelo disponible en product.template (si existe)
        def _tmpl_model_field_name():
            # Ajusta el orden si en tu módulo usas otro nombre (ej. 'product_model_id' o 'x_model_id')
            for fname in ('model_id', 'product_model_id', 'x_model_id'):
                if fname in PT._fields:
                    return fname
            return None

        model_fname = _tmpl_model_field_name()

        # 1) mapear equipo -> model_id efectivo
        rec_to_model = {}
        model_ids = set()
        for rec in self:
            mid = False
            tmpl = rec.product_id.product_tmpl_id if rec.product_id else False
            if tmpl and model_fname:
                mval = getattr(tmpl, model_fname)
                mid = mval.id if mval else False
            # fallback: usa el modelo del propio equipo si lo tiene
            if not mid and getattr(rec, 'model_id', False):
                mid = rec.model_id.id
            rec_to_model[rec.id] = mid
            if mid:
                model_ids.add(mid)

        # 2) buscar temparios en una sola query
        tempx_model = {}
        if model_ids:
            for line in TemparioModel.search([('model_id', 'in', list(model_ids))]):
                tempx_model.setdefault(line.model_id.id, set()).add(line.tempario_id.id)

        # 3) asignar al many2many computado
        for rec in self:
            mids = tempx_model.get(rec_to_model.get(rec.id), set())
            rec.tempario_ids = [(6, 0, list(mids))]

    def write(self, vals):
        # Integración activos fijos: sincronizar analytic_distribution al cambiar asset_id
        if 'asset_id' in vals and 'analytic_distribution' not in vals:
            asset_id = vals.get('asset_id')
            if asset_id:
                asset = self.env['account.asset'].browse(asset_id)
                vals['analytic_distribution'] = asset.analytic_distribution or False
            else:
                vals['analytic_distribution'] = False

        create_logs = 'current_mileage' in vals
        old_vals_map = {}
        if create_logs:
            for rec in self:
                old_vals_map[rec.id] = rec.current_mileage

        res = super().write(vals)

        if create_logs:
            for rec in self:
                old_val = old_vals_map.get(rec.id)
                new_val = rec.current_mileage
                if old_val != new_val:
                    self.env['maintenance.mileage.log'].create({
                        'product_maintenance_id': rec.id,
                        'old_value': old_val or 0.0,
                        'new_value': new_val or 0.0,
                    })
                    # === REPLANIFICAR CONTRATOS TEMPARIO PARA ESTE EQUIPO ===
                    rec._reschedule_contracts_on_mileage_change()
        return res
    
    def _reschedule_contracts_on_mileage_change(self):
        """Borra líneas futuras sin orden (si existe ese campo) y re-genera solo para este equipo en contratos TEMPARIO."""
        Detail = self.env['product.template.maintenance.detail']
        Contract = self.env['maintenance.contract']
        today = fields.Date.context_today(self)

        # Detectar cómo identificar "sin orden" en tu modelo de detalle
        has_order_id = 'order_id' in Detail._fields              # p.ej. Many2one a repair.order
        has_repair_order_id = 'repair_order_id' in Detail._fields
        has_order_state = 'order_state' in Detail._fields        # p.ej. Char/Selection calculado

        for equipment in self:
            contracts = Contract.search([
                ('contract_equipment_ids', 'in', [equipment.id]),
                ('strategy_type', '=', 'tempario'),
                ('tempario_start_date', '!=', False),
                ('tempario_end_date', '!=', False),
            ])

            for contract in contracts:
                # Dominio base: solo FUTURO de este contrato/equipo
                domain = [
                    ('contract_id', '=', contract.id),
                    ('product_maintenance_id', '=', equipment.id),
                    ('repair_date', '>=', today),
                ]
                # Agregar condición "sin orden" según el campo disponible
                if has_order_id:
                    domain.append(('order_id', '=', False))
                elif has_repair_order_id:
                    domain.append(('repair_order_id', '=', False))
                elif has_order_state:
                    # Si no hay campo de enlace, asumimos que sin orden => order_state False
                    domain.append(('order_state', '=', False))
                # Si no hay ningún indicador, borrará todo futuro (decisión consciente)
                to_delete = Detail.search(domain)
                if to_delete:
                    to_delete.unlink()

                # Re-generar SOLO para este equipo
                contract._regenerate_tempario_for_equipment(equipment)

    @api.depends('strategy_type')
    def _compute_show_period_fields(self):
        for rec in self:
            rec.show_period_fields = rec.strategy_type == 'period'

    def _compute_product_maintenance_count(self):
        for record in self:
            orders = self.env['repair.order'].search([('maintenance_product_id', '=', record.id)])
            record.product_maintenance_open_count = len(orders)

    @api.depends(
        'effective_date',
        'maintenance_detail_ids.repair_date',
        'maintenance_detail_ids.repair_state',
        'repair_order_ids.close_date',
        'repair_order_ids.maintenance_type',
        'repair_order_ids.schedule_date',
        'repair_order_ids.state',
    )
    def _compute_maintenance_request(self):
        for record in self:
            estimated_next_failure = False
            latest_failure_date = False
            repair_days = []
            pending_details = record.maintenance_detail_ids.filtered(lambda x: x.repair_state != 'done')
            if pending_details:
                estimated_next_failure = pending_details.sorted('repair_date')[0].repair_date

            valid_repair_orders = record.repair_order_ids.filtered(
                lambda repair: repair.state == 'done'
                and repair.maintenance_type == 'correctives'
                and repair.schedule_date
                and repair.close_date
            )
            for repair in valid_repair_orders:
                repair_start_date = repair.schedule_date.date()
                if repair.close_date >= repair_start_date:
                    repair_days.append((repair.close_date - repair_start_date).days)
                    latest_failure_date = max(latest_failure_date or repair_start_date, repair_start_date)

            record.mttr = repair_days and sum(repair_days) / len(repair_days) or 0
            record.latest_failure_date = latest_failure_date
            record.mtbf = record.expected_mtbf
            record.estimated_next_failure = estimated_next_failure

    def action_create_maintenance_detailed(self):
        for record in self:
            if not record.effective_date or record.expected_mtbf <= 0:
                raise ValidationError(
                    'Por Favor Validar la Información Ingresada en La Fecha '
                    'Efectiva o Tiempo medio estimado entre fallos')
            dates_range = self._get_date_range(record.effective_date, record.expected_mtbf)
            for date_range in dates_range:
                self.env['product.template.maintenance.detail'].create({
                    'repair_date': date_range,
                    'product_maintenance_id': record.id
                })


    def _get_date_range(self, date, interval):
        is_last_date = True
        if self.maintenance_detail_ids and self.maintenance_detail_ids.filtered(lambda x: x.repair_id):
            current_date = self.maintenance_detail_ids.filtered(lambda x: x.repair_id)[-1].repair_date
        else:
            current_date = date
        self.maintenance_detail_ids.filtered(lambda x: not x.repair_id).unlink()
        dates = []

        if date.month == 2 and date.day == 29:
            last_date = date(date.year+1, date.month, 28)
        else:
            last_date = date + relativedelta(years=1)

        if self.maintenance_to_date and self.maintenance_to_date > last_date:
            last_date = self.maintenance_to_date

        while(is_last_date):
            current_date = current_date + relativedelta(days=interval)
            if current_date > last_date:
                is_last_date = False
            else:
                dates.append(current_date)
        
        return dates

    def get_lines_by_months(self):
        schedule_lines = {}
        for line in self.maintenance_detail_ids:
            month = self._get_name_month(line.repair_date.month)
            if month in schedule_lines.keys():
                schedule_lines[month].append(line.repair_date.day)
            else:
                schedule_lines[month] = [line.repair_date.day]
        return schedule_lines

    def _get_name_month(self, month):
        months_names = {
            1: 'ENE',
            2: 'FEB',
            3: 'MAR',
            4: 'ABR',
            5: 'MAY',
            6: 'JUN',
            7: 'JUL',
            8: 'AGO',
            9: 'SEP',
            10: 'OCT',
            11: 'NOV',
            12: 'DIC',
        }
        return months_names[month]

    def get_name_brand(self):
        return self.brand_id.display_name if self.brand_id else ''

    def get_model_name(self):
        return self.model or ''

    def get_serial_name(self):
        return self.serial_no or ''
    
    def get_from_day(self):
        return self.effective_date.day or ''

    def get_from_month(self):
        return self.effective_date.month or ''

    def get_from_year(self):
        return self.effective_date.year or ''

    def get_to_day(self):
        if self.maintenance_detail_ids:
            return self.maintenance_detail_ids[-1].repair_date.day
        return ''

    def get_to_month(self):
        if self.maintenance_detail_ids:
            return self.maintenance_detail_ids[-1].repair_date.month
        return ''

    def get_to_year(self):
        if self.maintenance_detail_ids:
            return self.maintenance_detail_ids[-1].repair_date.year
        return ''

    @api.model
    def action_cron_notify_maintenance(self):
        today = date.today()
        in_five_days = date.today() + relativedelta(days=5)
        details = self.env['product.template.maintenance.detail'].search([
            ('repair_date', '>=', today),
            ('repair_date', '<=', in_five_days),
            ('repair_id.state', 'not in', ('cancel', 'done'))
        ])
        mail_template = self.env.ref('product_maintenance.product_maintenance_mail_template')
        for detail in details:
            try:
                mail_template.sudo().send_mail(detail.product_tmpl_id.id, force_send=True)
            except:
                pass

    def unlink(self):
        for record in self:
            if record.maintenance_detail_ids.filtered(lambda x: x.repair_id.state == 'done'):
                raise ValidationError('No se puede eliminar el producto de '
                                      'mantenimiento {name} ya que tiene una '
                                      'reparación asociada terminada.'.format(name=record.name))
        return super().unlink()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            picking_id = vals.get('picking_id')
            product_id = vals.get('product_id')
            lot_id = vals.get('lot_id')
            if picking_id and product_id and lot_id:
                o_record = self.env['product.maintenance'].search([
                    ('product_id', '=', product_id),
                    ('lot_id', '=', lot_id),
                    ('picking_id', '=', picking_id)
                ])
                if o_record:
                    return True
            # Integración activos fijos: sincronizar analytic_distribution al crear con asset_id
            if vals.get('asset_id') and not vals.get('analytic_distribution'):
                asset = self.env['account.asset'].browse(vals['asset_id'])
                vals['analytic_distribution'] = asset.analytic_distribution or False
        return super().create(vals_list)

    # Integración activos fijos: obtener distribución analítica del equipo
    def _get_analytic_distribution(self):
        self.ensure_one()
        return self.analytic_distribution or False

    # Integración activos fijos: navegar al activo fijo asociado
    def action_view_asset(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.asset',
            'res_id': self.asset_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def get_catalog(self):
        if self.have_catalog == 'yes':
            return 'Si'
        return 'No'
