# -*- coding: utf-8 -*-

import base64
import calendar
import io
import logging
import traceback
from datetime import date

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.addons.utilities_collection.time import days360

_logger = logging.getLogger(__name__)

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None

# ------------------------------------------------------------------
# Descripción de todas las columnas del informe
# Formato: (clave_dict, encabezado, ancho_col, grupo)
# Grupos: 'emp' = A-AH (empleado/contrato), 'dev' = devengos, 'ded' = deducciones, 'tot' = totales
# ------------------------------------------------------------------
REPORT_COLUMNS = [
    # ── A-AH: EMPLEADO / CONTRATO / NE ─────────────────────────────
    ('periodo',            'Período',                    15, 'emp'),
    ('fecha_inicio',       'Inicio Período',             14, 'emp'),
    ('fecha_fin',          'Fin Período',                14, 'emp'),
    ('tipo_periodo_dian',  'Tipo Período DIAN',          18, 'emp'),
    ('nit_empleador',      'NIT Empleador',              16, 'emp'),
    ('dv_empleador',       'DV',                          5, 'emp'),
    ('razon_social',       'Razón Social Empleador',     32, 'emp'),
    ('tipo_doc',           'Tipo Doc.',                  10, 'emp'),
    ('nro_doc',            'Número Doc.',                16, 'emp'),
    ('primer_apellido',    'Primer Apellido',            20, 'emp'),
    ('segundo_apellido',   'Segundo Apellido',           20, 'emp'),
    ('primer_nombre',      'Primer Nombre',              20, 'emp'),
    ('otros_nombres',      'Otros Nombres',              20, 'emp'),
    ('tipo_trabajador',    'Tipo Trabajador',            15, 'emp'),
    ('subtipo_trabajador', 'Subtipo Trabajador',         18, 'emp'),
    ('alto_riesgo',        'Alto Riesgo Pensión',        18, 'emp'),
    ('tipo_contrato',      'Tipo Contrato',              13, 'emp'),
    ('salario_integral',   'Sal. Integral',              12, 'emp'),
    ('sueldo',             'Sueldo',                     14, 'emp'),
    ('fecha_ingreso',      'Fecha Ingreso',              13, 'emp'),
    ('fecha_retiro',       'Fecha Retiro',               13, 'emp'),
    ('fecha_liq_inicio',   'Inicio Liquidación',         18, 'emp'),
    ('fecha_liq_fin',      'Fin Liquidación',            18, 'emp'),
    ('tiempo_laborado',    'Tiempo Laborado',            14, 'emp'),
    ('pais_trabajo',       'País Trabajo',               12, 'emp'),
    ('dpto_trabajo',       'Dpto. Trabajo',              15, 'emp'),
    ('ciudad_trabajo',     'Ciudad Trabajo',             15, 'emp'),
    ('numero_ne',          'Número NE',                  28, 'emp'),
    ('cune',               'CUNE',                       50, 'emp'),
    ('estado_dian',        'Estado DIAN',                12, 'emp'),
    ('tipo_ne',            'Tipo NE',                    10, 'emp'),
    ('fecha_gen_ne',       'Fecha Gen. NE',              14, 'emp'),
    ('ambiente_dian',      'Ambiente',                   12, 'emp'),
    ('periodo_nomina_dian','Período Nómina DIAN',        20, 'emp'),  # ← columna AH
    # ── AI+: DEVENGOS ──────────────────────────────────────────────
    ('bas_dias',           'BAS - Días Trabajados',      20, 'dev'),
    ('bas_valor',          'BAS - Sueldo Trabajado',     22, 'dev'),
    ('tpt_auxilio',        'TPT - Aux. Transporte',      20, 'dev'),
    ('vma_salarial',       'VMA - Viático Salarial',     22, 'dev'),
    ('vma_no_salarial',    'VMA - Viático No Salarial',  24, 'dev'),
    ('hed_cantidad',       'HED - H.E. Diurna Cant.',    22, 'dev'),
    ('hed_valor',          'HED - H.E. Diurna Valor',    22, 'dev'),
    ('hen_cantidad',       'HEN - H.E. Nocturna Cant.',  24, 'dev'),
    ('hen_valor',          'HEN - H.E. Nocturna Valor',  24, 'dev'),
    ('hrn_cantidad',       'HRN - H.R. Nocturno Cant.',  24, 'dev'),
    ('hrn_valor',          'HRN - H.R. Nocturno Valor',  24, 'dev'),
    ('heddf_cantidad',     'HEDDF - H.E. Diurna D/F Cant.',  28, 'dev'),
    ('heddf_valor',        'HEDDF - H.E. Diurna D/F Valor',  28, 'dev'),
    ('hrddf_cantidad',     'HRDDF - H.R. Noct. D/F Cant.',   28, 'dev'),
    ('hrddf_valor',        'HRDDF - H.R. Noct. D/F Valor',   28, 'dev'),
    ('hendf_cantidad',     'HENDF - H.E. Noct. D/F Cant.',   28, 'dev'),
    ('hendf_valor',        'HENDF - H.E. Noct. D/F Valor',   28, 'dev'),
    ('hrndf_cantidad',     'HRNDF - H.R. Noct. D/F Cant.',   28, 'dev'),
    ('hrndf_valor',        'HRNDF - H.R. Noct. D/F Valor',   28, 'dev'),
    ('vac_dias',           'VAC - Vac. Comunes Días',    22, 'dev'),
    ('vac_valor',          'VAC - Vac. Comunes Valor',   22, 'dev'),
    ('vap_dias',           'VAP - Vac. Compensadas Días',  26, 'dev'),
    ('vap_valor',          'VAP - Vac. Compensadas Valor', 26, 'dev'),
    ('pri_cantidad',       'PRI - Prima Cant. (días)',   24, 'dev'),
    ('pri_salarial',       'PRI - Prima Salarial',       20, 'dev'),
    ('pri_no_salarial',    'PRI - Prima No Salarial',    22, 'dev'),
    ('ces_valor',          'CES - Cesantías',            16, 'dev'),
    ('ces_porcentaje',     'CES - Cesantías %',          16, 'dev'),
    ('ces_intereses',      'ICE - Intereses Cesantías',  24, 'dev'),
    ('inc_enf_dias',       'INC-ENF - Inc. Enf. Días',   24, 'dev'),
    ('inc_enf_valor',      'INC-ENF - Inc. Enf. Valor',  24, 'dev'),
    ('inc_atep_dias',      'INC-ATEP - Inc. AT/EP Días', 26, 'dev'),
    ('inc_atep_valor',     'INC-ATEP - Inc. AT/EP Valor',26, 'dev'),
    ('lic_mp_dias',        'LIC-MP - Lic. Mat/Pat Días', 26, 'dev'),
    ('lic_mp_valor',       'LIC-MP - Lic. Mat/Pat Valor',26, 'dev'),
    ('lic_rem_dias',       'LIC-R - Lic. Rem. Días',     22, 'dev'),
    ('lic_rem_valor',      'LIC-R - Lic. Rem. Valor',    22, 'dev'),
    ('lic_no_rem_dias',    'LIC-NR - Lic. No Rem. Días', 24, 'dev'),
    ('bon_salarial',       'BON - Bonif. Salarial',      22, 'dev'),
    ('bon_no_salarial',    'BON - Bonif. No Salarial',   24, 'dev'),
    ('aux_salarial',       'AUX - Auxilio Salarial',     22, 'dev'),
    ('aux_no_salarial',    'AUX - Auxilio No Salarial',  24, 'dev'),
    ('ocp_salarial',       'OCP - Otros Conc. Salarial', 24, 'dev'),
    ('ocp_no_salarial',    'OCP - Otros Conc. No Salarial', 26, 'dev'),
    ('comp_ordinaria',     'COMP - Compensación Ord.',   24, 'dev'),
    ('comp_extraordinaria','COMP - Compensación Ext.',   24, 'dev'),
    ('bepctv_pago_s',      'BEP - Bono EPCTV Pago S',   24, 'dev'),
    ('bepctv_pago_ns',     'BEP - Bono EPCTV Pago NS',  24, 'dev'),
    ('bepctv_alim_s',      'BEA - Bono EPCTV Alim. S',  24, 'dev'),
    ('bepctv_alim_ns',     'BEA - Bono EPCTV Alim. NS', 24, 'dev'),
    ('comision',           'COM - Comisión',             16, 'dev'),
    ('pago_tercero_dev',   'PTP - Pago Tercero Dev.',    22, 'dev'),
    ('anticipo_dev',       'ANT - Anticipo Dev.',        20, 'dev'),
    ('dotacion',           'DOT - Dotación',             16, 'dev'),
    ('apoyo_sost',         'ASO - Apoyo Sost.',          18, 'dev'),
    ('teletrabajo',        'TTR - Teletrabajo',          16, 'dev'),
    ('bonif_retiro',       'BRT - Bonif. Retiro',        18, 'dev'),
    ('indemnizacion',      'IND - Indemnización',        20, 'dev'),
    ('reintegro_dev',      'REI - Reintegro Dev.',       20, 'dev'),
    # ── DEDUCCIONES ────────────────────────────────────────────────
    ('ded_salud_pct',      'EPS - Salud %',              14, 'ded'),
    ('ded_salud',          'EPS - Salud Valor',          18, 'ded'),
    ('ded_pension_pct',    'PEN - Pensión %',            14, 'ded'),
    ('ded_pension',        'PEN - Pensión Valor',        18, 'ded'),
    ('ded_fsol_pct',       'FSL - Fondo Sol. %',         16, 'ded'),
    ('ded_fsol',           'FSL - Fondo Sol. Valor',     20, 'ded'),
    ('ded_fsub_pct',       'FSB - Subsistencia %',       18, 'ded'),
    ('ded_fsub',           'FSB - Subsistencia Valor',   22, 'ded'),
    ('ded_sancion_pub',    'SPU - Sanción Pública',      22, 'ded'),
    ('ded_sancion_priv',   'SPV - Sanción Privada',      22, 'ded'),
    ('ded_libranzas',      'LIB - Libranzas',            16, 'ded'),
    ('ded_pago_tercero',   'PTR - Pago Tercero Ded.',    22, 'ded'),
    ('ded_anticipo',       'ADV - Anticipo Ded.',        20, 'ded'),
    ('ded_otras',          'ODD - Otras Deducciones',    24, 'ded'),
    ('ded_pension_vol',    'PVL - Pensión Voluntaria',   24, 'ded'),
    ('ded_rtefte',         'RFT - Retención Fuente',     22, 'ded'),
    ('ded_afc',            'AFC - AFC',                  12, 'ded'),
    ('ded_cooperativa',    'COO - Cooperativa',          18, 'ded'),
    ('ded_embargo',        'EMB - Embargo Fiscal',       20, 'ded'),
    ('ded_plan_comp',      'CPN - Plan Complementarios', 26, 'ded'),
    ('ded_educacion',      'EDU - Educación',            16, 'ded'),
    ('ded_reintegro',      'RIN - Reintegro Ded.',       20, 'ded'),
    ('ded_deuda',          'DEU - Deuda',                14, 'ded'),
    # ── TOTALES ────────────────────────────────────────────────────
    ('total_devengado',    'TOTAL DEVENGADO',            18, 'tot'),
    ('total_deducciones',  'TOTAL DEDUCCIONES',          20, 'tot'),
    ('total_neto',         'TOTAL NETO',                 16, 'tot'),
]

# Índice de columna AH (0-based) = posición 33 (columnas emp = 34 cols)
IDX_AH = 33


class EdiHrReportWizard(models.TransientModel):
    _name = 'edi.hr.report.wizard'
    _description = 'Asistente - Informe Previo Nómina Electrónica'

    # ── Filtros ────────────────────────────────────────────────────
    fecha_informe = fields.Date(
        string='Fecha del informe',
        default=fields.Date.today,
        required=True,
        help='Seleccione cualquier día del mes que desea reportar. '
             'El sistema tomará automáticamente todo el mes '
             '(del 1 al último día) para incluir quincenas, semanas '
             'u otro tipo de períodos de pago.',
    )
    edi_processing_ids = fields.Many2many(
        'edi.hr.processing',
        string='Procesamiento(s)',
        domain="[('company_id','=',company_id)]",
    )
    edi_type = fields.Selection(
        [('all', 'Todos'),
         ('nie', 'NIE - Nómina Individual'),
         ('niae_r', 'NIAE-R - Ajuste (Reemplazar)'),
         ('niae_e', 'NIAE-E - Ajuste (Eliminar)')],
        string='Tipo NE',
        default='all',
    )
    state_filter = fields.Selection(
        [('all', 'Todos'),
         ('neu', 'Nuevo'),
         ('gesendet', 'Enviado'),
         ('richtig', 'Correcto'),
         ('abgelehnt', 'Rechazado'),
         ('fehler', 'Error')],
        string='Estado',
        default='all',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
    )

    # ── Acción principal ───────────────────────────────────────────
    def action_generate_report(self):
        self.ensure_one()
        if xlsxwriter is None:
            raise UserError(
                _('La librería xlsxwriter no está instalada. '
                  'Ejecute: pip install xlsxwriter'))

        payslip_groups = self._get_payslip_groups()
        if not payslip_groups:
            f = self.fecha_informe or fields.Date.today()
            raise UserError(
                _('No se encontraron nóminas liquidadas (estado "Hecho" o "Pagado") '
                  'para %02d/%s en la compañía %s.\n\n'
                  'Verifique que las nóminas del mes estén liquidadas.')
                % (f.month, f.year, self.company_id.name))

        xlsx_data = self._generate_xlsx(payslip_groups)

        fecha = self.fecha_informe or fields.Date.today()
        fname = 'NE_Informe_%s-%02d.xlsx' % (fecha.year, fecha.month)

        attachment = self.env['ir.attachment'].create({
            'name': fname,
            'type': 'binary',
            'datas': base64.b64encode(xlsx_data),
            'mimetype': 'application/vnd.openxmlformats-'
                        'officedocument.spreadsheetml.sheet',
            'res_model': self._name,
            'res_id': self.id,
        })

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%d?download=true' % attachment.id,
            'target': 'self',
        }

    # ── Calcular rango del mes a partir de fecha_informe ────────
    def _mes_rango(self):
        """Devuelve (primer_dia, ultimo_dia) del mes de fecha_informe."""
        f = self.fecha_informe or fields.Date.today()
        primer_dia = date(f.year, f.month, 1)
        ultimo_dia = date(f.year, f.month,
                          calendar.monthrange(f.year, f.month)[1])
        return primer_dia, ultimo_dia

    # ── Obtener nóminas del mes agrupadas por empleado ────────────
    def _get_payslip_groups(self):
        """
        Devuelve lista de dicts {'payslips': hr.payslip, 'edi_doc': edi.hr.document|False}
        agrupados por empleado.

        Funciona en CUALQUIER etapa del proceso:
        - Antes de crear edi.hr.document → edi_doc = False, campos NE vacíos
        - Después de crear edi.hr.document → muestra número NE, CUNE, estado
        """
        # ── 1. Obtener nóminas confirmadas ─────────────────────────
        if self.edi_processing_ids:
            # Filtrar por procesamiento específico
            all_payslips = self.edi_processing_ids.mapped('payslip_ids').filtered(
                lambda p: p.state in ('done', 'paid'))
        else:
            # Calcular todos los sub-períodos del mes
            primer_dia, ultimo_dia = self._mes_rango()
            sub_periods = self.env['hr.period'].search([
                ('start', '>=', primer_dia),
                ('start', '<=', ultimo_dia),
                ('company_id', '=', self.company_id.id),
            ])
            if not sub_periods:
                f = self.fecha_informe or fields.Date.today()
                raise UserError(
                    _('No se encontraron períodos de nómina para %02d/%s '
                      'en la compañía %s. Verifique la configuración de períodos.')
                    % (f.month, f.year, self.company_id.name))
            all_payslips = self.env['hr.payslip'].search([
                ('period_id', 'in', sub_periods.ids),
                ('state', 'in', ('done', 'paid')),
                ('company_id', '=', self.company_id.id),
            ], order='employee_id, period_id')

        if not all_payslips:
            return []

        # ── 2. Agrupar por empleado ────────────────────────────────
        groups = {}
        for p in all_payslips:
            emp_id = p.employee_id.id
            if emp_id not in groups:
                groups[emp_id] = self.env['hr.payslip']
            groups[emp_id] |= p

        # ── 3. Buscar edi.hr.document asociado (si ya existe) ──────
        result = []
        for emp_id, payslips in groups.items():
            edi_doc = self.env['edi.hr.document'].search([
                ('payslip_ids', 'in', payslips.ids),
                ('company_id', '=', self.company_id.id),
            ], limit=1)

            # Aplicar filtros de tipo NE y estado (solo relevantes si hay doc)
            if edi_doc:
                if self.edi_type != 'all' and edi_doc.edi_type != self.edi_type:
                    continue
                if self.state_filter != 'all' and edi_doc.state != self.state_filter:
                    continue
            else:
                # Sin doc NE aún: solo incluir si los filtros son "Todos"
                # o si se filtra explícitamente por "Nuevo" (pendiente de crear)
                if self.state_filter not in ('all', 'neu'):
                    continue

            result.append({'payslips': payslips, 'edi_doc': edi_doc})

        return result

    # ── Generación del Excel ───────────────────────────────────────
    def _generate_xlsx(self, payslip_groups):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        ws = workbook.add_worksheet('Nómina Electrónica')

        # Formatos
        fmt_title = workbook.add_format({
            'bold': True, 'font_size': 13,
            'align': 'center', 'valign': 'vcenter',
            'bg_color': '#003366', 'font_color': 'white',
        })
        fmt_header_emp = workbook.add_format({
            'bold': True, 'font_size': 9,
            'align': 'center', 'valign': 'vcenter',
            'bg_color': '#1F4E79', 'font_color': 'white',
            'border': 1, 'text_wrap': True,
        })
        fmt_header_dev = workbook.add_format({
            'bold': True, 'font_size': 9,
            'align': 'center', 'valign': 'vcenter',
            'bg_color': '#375623', 'font_color': 'white',
            'border': 1, 'text_wrap': True,
        })
        fmt_header_ded = workbook.add_format({
            'bold': True, 'font_size': 9,
            'align': 'center', 'valign': 'vcenter',
            'bg_color': '#7B2C2C', 'font_color': 'white',
            'border': 1, 'text_wrap': True,
        })
        fmt_header_tot = workbook.add_format({
            'bold': True, 'font_size': 9,
            'align': 'center', 'valign': 'vcenter',
            'bg_color': '#7F6000', 'font_color': 'white',
            'border': 1, 'text_wrap': True,
        })
        fmt_group_emp = workbook.add_format({
            'bold': True, 'font_size': 10,
            'align': 'center', 'valign': 'vcenter',
            'bg_color': '#BDD7EE', 'border': 1,
        })
        fmt_group_dev = workbook.add_format({
            'bold': True, 'font_size': 10,
            'align': 'center', 'valign': 'vcenter',
            'bg_color': '#E2EFDA', 'border': 1,
        })
        fmt_group_ded = workbook.add_format({
            'bold': True, 'font_size': 10,
            'align': 'center', 'valign': 'vcenter',
            'bg_color': '#FCE4D6', 'border': 1,
        })
        fmt_group_tot = workbook.add_format({
            'bold': True, 'font_size': 10,
            'align': 'center', 'valign': 'vcenter',
            'bg_color': '#FFF2CC', 'border': 1,
        })
        fmt_text = workbook.add_format({
            'font_size': 9, 'border': 1, 'valign': 'vcenter',
        })
        fmt_number = workbook.add_format({
            'font_size': 9, 'border': 1, 'valign': 'vcenter',
            'num_format': '#,##0.00',
        })
        fmt_date = workbook.add_format({
            'font_size': 9, 'border': 1, 'valign': 'vcenter',
            'num_format': 'yyyy-mm-dd',
        })
        fmt_error = workbook.add_format({
            'font_size': 9, 'border': 1, 'valign': 'vcenter',
            'bg_color': '#FF9999', 'font_color': '#8B0000',
        })
        fmt_total_row_num = workbook.add_format({
            'bold': True, 'font_size': 9, 'border': 1,
            'num_format': '#,##0.00', 'bg_color': '#FFF2CC',
        })
        fmt_total_row_txt = workbook.add_format({
            'bold': True, 'font_size': 9, 'border': 1,
            'bg_color': '#FFF2CC',
        })

        # Mapa formato de encabezado por grupo
        fmt_header_map = {
            'emp': fmt_header_emp,
            'dev': fmt_header_dev,
            'ded': fmt_header_ded,
            'tot': fmt_header_tot,
        }
        fmt_group_map = {
            'emp': fmt_group_emp,
            'dev': fmt_group_dev,
            'ded': fmt_group_ded,
            'tot': fmt_group_tot,
        }

        num_cols = len(REPORT_COLUMNS)

        # ── Fila 0: Título ─────────────────────────────────────────
        f = self.fecha_informe or fields.Date.today()
        MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre',
                 'Diciembre']
        mes_label = '%s %d' % (MESES[f.month - 1], f.year)
        ws.merge_range(0, 0, 0, num_cols - 1,
                       'INFORME PREVIO NÓMINA ELECTRÓNICA - %s'
                       % mes_label, fmt_title)
        ws.set_row(0, 22)

        # ── Fila 1: Grupos de columnas ────────────────────────────
        groups = {}
        for col_idx, (key, header, width, grupo) in enumerate(REPORT_COLUMNS):
            if grupo not in groups:
                groups[grupo] = {'start': col_idx, 'end': col_idx}
            else:
                groups[grupo]['end'] = col_idx

        group_labels = {
            'emp': 'EMPLEADO / CONTRATO / NE',
            'dev': 'DEVENGOS DIAN',
            'ded': 'DEDUCCIONES DIAN',
            'tot': 'TOTALES',
        }
        for grupo, info in groups.items():
            s, e = info['start'], info['end']
            if s == e:
                ws.write(1, s, group_labels[grupo], fmt_group_map[grupo])
            else:
                ws.merge_range(1, s, 1, e,
                               group_labels[grupo], fmt_group_map[grupo])
        ws.set_row(1, 18)

        # ── Fila 2: Encabezados de columna ────────────────────────
        for col_idx, (key, header, width, grupo) in enumerate(REPORT_COLUMNS):
            ws.write(2, col_idx, header, fmt_header_map[grupo])
            ws.set_column(col_idx, col_idx, width)
        ws.set_row(2, 45)
        ws.freeze_panes(3, IDX_AH + 1)  # Congela hasta AH

        # ── Filas de datos ────────────────────────────────────────
        data_row = 3
        totals = {key: 0.0 for key, _, _, grupo in REPORT_COLUMNS
                  if grupo in ('dev', 'ded', 'tot')}

        for group in payslip_groups:
            payslips = group['payslips']
            edi_doc = group['edi_doc']
            emp_name = payslips.employee_id[:1].name or str(payslips.ids)
            try:
                row_data = self._build_report_row(payslips, edi_doc)
            except Exception as e:
                tb = traceback.format_exc()
                _logger.error(
                    'Error generando fila empleado %s: %s\n%s',
                    emp_name, e, tb)
                # Escribir fila de error
                ws.write(data_row, 0,
                         'ERROR en %s: %s' % (emp_name, str(e)),
                         fmt_error)
                for col_idx in range(1, num_cols):
                    ws.write(data_row, col_idx, '', fmt_error)
                data_row += 1
                continue

            for col_idx, (key, header, width, grupo) in enumerate(REPORT_COLUMNS):
                val = row_data.get(key, '')
                if isinstance(val, float) and grupo in ('dev', 'ded', 'tot'):
                    ws.write_number(data_row, col_idx, val, fmt_number)
                    totals[key] = totals.get(key, 0.0) + val
                elif isinstance(val, float):
                    # Numérico de emp (sueldo, días, etc.)
                    ws.write_number(data_row, col_idx, val, fmt_number)
                elif hasattr(val, 'strftime'):
                    ws.write_datetime(data_row, col_idx, val, fmt_date)
                else:
                    ws.write(data_row, col_idx, str(val) if val else '', fmt_text)

            data_row += 1

        # ── Fila de totales ────────────────────────────────────────
        if data_row > 3:
            ws.write(data_row, 0, 'TOTALES', fmt_total_row_txt)
            for col_idx, (key, header, width, grupo) in enumerate(REPORT_COLUMNS):
                if grupo in ('dev', 'ded', 'tot'):
                    ws.write_number(
                        data_row, col_idx, totals.get(key, 0.0),
                        fmt_total_row_num)
                elif col_idx > 0:
                    ws.write(data_row, col_idx, '', fmt_total_row_txt)

        workbook.close()
        return output.getvalue()

    # ── Construcción de una fila por grupo de nóminas ────────────
    def _build_report_row(self, payslips, edi_doc=None):
        """
        Construye el dict de una fila del informe a partir de un grupo
        de hr.payslip del mismo empleado.

        - Funciona ANTES de crear edi.hr.document (edi_doc=None o False).
        - Si ya existe edi.hr.document, lo usa para mostrar número NE,
          CUNE y estado DIAN.
        - Reutiliza los mismos métodos _build_* de hr.payslip que usa el
          envío a la DIAN, garantizando consistencia total con lo enviado.
        """
        if not payslips:
            raise UserError(_('Grupo de nóminas vacío.'))
        company = payslips.company_id[:1] or self.company_id

        # ── Info empleado y período ────────────────────────────────
        period_ne = payslips._build_period_ne()
        employer_ne = payslips._build_employer_ne()
        employee = payslips._build_employee_ne()
        workplace = payslips._build_workplace()

        # ── Devengos ───────────────────────────────────────────────
        basic_wage = payslips._build_basic_wage()
        sub_trans = payslips._build_sub_trans()
        hed = payslips._build_hed_overtimes()
        hen = payslips._build_hen_overtimes()
        hrn = payslips._build_hrn_overtimes()
        heddf = payslips._build_heddf_overtimes()
        hrddf = payslips._build_hrddf_overtimes()
        hendf = payslips._build_hendf_overtimes()
        hrndf = payslips._build_hrndf_overtimes()
        holidays = payslips._build_holidays()
        prima = payslips._build_prima()
        ces = payslips._build_ces()
        inabilitys = payslips._build_inabilitys()
        licenses = payslips._build_licenses()
        bonds = payslips._build_bonds()
        aids = payslips._build_aids()
        oconcepts = payslips._build_other_concepts()
        compensations = payslips._build_compensations()
        epctvs = payslips._build_bonds_epctv()
        commissions = payslips._build_commissions()
        dev_partners = payslips._build_payment_partner()
        dev_advances = payslips._build_advances()
        dotation = payslips._build_dotation()
        sus_support = payslips._build_sustenance_support()
        telew = payslips._build_teleworking()
        bonret = payslips._build_retirement_bonus()
        indem = payslips._build_indemnification()
        dev_return = payslips._build_return()

        # ── Deducciones ────────────────────────────────────────────
        ded_health = payslips._build_deduction_health()
        ded_pension = payslips._build_deduction_pension()
        ded_solidarity = payslips._build_deduction_solidarity()
        ded_subsistence = payslips._build_deduction_subsistence()
        sanctions = payslips._build_sanctions()
        prommissory = payslips._build_promissory_notes()
        ded_partners = payslips._build_payment_partner_ded()
        ded_advances = payslips._build_advances_ded()
        odeductions = payslips._build_other_ded()
        vol_pension = payslips._build_voluntary_pension()
        ded_rtefte = payslips._build_deduction_rtefte()
        afc = payslips._build_afc()
        coop = payslips._build_cooperative()
        tax_emb = payslips._build_tax_embargo()
        comp_plan = payslips._build_complementary_plan()
        education = payslips._build_education()
        ded_return = payslips._build_return_ded()
        debt = payslips._build_debt()

        # ── Cálculo de totales (igual que _datenwerte_erhalten) ────
        total_earnings = (
            float(basic_wage.get('Dev_Bas_SueldoTrabajado', 0))
            + float(sub_trans.get('AuxilioTransporte', 0))
            + float(sub_trans.get('ViaticoManutAlojS', 0))
            + float(sub_trans.get('ViaticoManutAlojNS', 0))
            + sum(float(x.get('Pago', 0)) for x in hed + hen + hrn + heddf + hrddf + hendf + hrndf)
            + sum(float(x.get('Pago', 0)) for x in holidays.get('VacacionesComunes', []))
            + sum(float(x.get('Pago', 0)) for x in holidays.get('VacacionesCompensadas', []))
            + float(prima.get('Dev_Pri_Pago', 0))
            + float(prima.get('Dev_Pri_PagoNS', 0))
            + float(ces.get('Dev_Ces_Pago', 0))
            + float(ces.get('Dev_Ces_PagoIntereses', 0))
            + sum(float(x.get('Pago', 0)) for x in inabilitys)
            + sum(float(x.get('Pago', 0)) for x in licenses.get('LicenciaMP', []))
            + sum(float(x.get('Pago', 0)) for x in licenses.get('LicenciaR', []))
            + sum(float(x.get('BonificacionS', 0)) + float(x.get('BonificacionNS', 0)) for x in bonds)
            + sum(float(x.get('AuxilioS', 0)) + float(x.get('AuxilioNS', 0)) for x in aids)
            + sum(float(x.get('ConceptoS', 0)) + float(x.get('ConceptoNS', 0)) for x in oconcepts)
            + sum(float(x.get('CompensacionO', 0)) + float(x.get('CompensacionE', 0)) for x in compensations)
            + sum(
                float(x.get('PagoS', 0)) + float(x.get('PagoNS', 0))
                + float(x.get('PagoAlimentacionS', 0)) + float(x.get('PagoAlimentacionNS', 0))
                for x in epctvs)
            + float(commissions.get('Comision', 0))
            + float(dev_partners.get('PagoTercero', 0))
            + float(dev_advances.get('Anticipo', 0))
            + float(dotation) + float(sus_support) + float(telew)
            + float(bonret) + float(indem) + float(dev_return)
        )

        total_deductions = (
            float(ded_health.get('Ded_Salud_Deduccion', 0))
            + float(ded_pension.get('Ded_FoPen_Deduccion', 0))
            + float(ded_solidarity.get('Ded_FoSP_Deduccion', 0))
            + float(ded_subsistence.get('Ded_FoSP_DeduccionSub', 0))
            + sum(float(x.get('SancionPublic', 0)) + float(x.get('SancionPriv', 0)) for x in sanctions)
            + sum(float(x.get('Deduccion', 0)) for x in prommissory)
            + float(ded_partners.get('PagoTercero', 0))
            + float(ded_advances.get('Anticipo', 0))
            + float(odeductions.get('OtraDeduccion', 0))
            + float(vol_pension) + float(ded_rtefte) + float(afc)
            + float(coop) + float(tax_emb) + float(comp_plan)
            + float(education) + float(ded_return) + float(debt)
        )
        
          # Enviar el concepto negativo a su inverso DIAN
        inverse_accumulator = {}

        def _reclassify(value, concept_dian_codes, label=None):
            """
            Si value es negativo y hay inverso DIAN, acumula el
            valor absoluto en inverse_accumulator y retorna None
            (señal de que la clave debe eliminarse del dict origen).
            Si no hay inverso DIAN, retorna value original.
            Si value >= 0, retorna value sin tocar.
            """
            if value >= 0:
                return value
            # l10n_co_hr_bloodo 19.0 todavía no trae _get_inverse_dian_code
            # (PT9831, v18). Sin él no se reclasifica, igual que el XML DIAN.
            get_inverse = getattr(payslips, '_get_inverse_dian_code', None)
            inv_code = get_inverse(concept_dian_codes) if get_inverse else None
            if not inv_code:
                return value
            inverse_accumulator[inv_code] = \
                inverse_accumulator.get(inv_code, 0.0) + abs(value)
          
            return None  # Indica que hay que eliminar la clave del original y así no se visualiza en el XML

        def _reclassify_list(lst, key_to_dian):
            """
            Recorre lista de dicts. Por cada clave numérica indicada en
            key_to_dian = {key: (dian_codes, label)}, si el valor es
            negativo y hay inverso, elimina la clave del dict.
            Si tras la limpieza el dict queda sin ninguna clave de pago,
            lo elimina de la lista.
            Retorna la lista limpia.
            """
            pay_keys = set(key_to_dian.keys())
            clean = []
            for item in lst:
                for key, (dian_codes, label) in key_to_dian.items():
                    if key not in item:
                        continue
                    val = float(item[key])
                    result = _reclassify(val, dian_codes, label)
                    if result is None:
                        del item[key]
                    else:
                        item[key] = '{:.2f}'.format(result)
                # Conservar el item solo si todavía tiene al menos una clave de pago
                if any(k in item for k in pay_keys):
                    clean.append(item)
            return clean

        _concept_labels = {
            'TPT': 'AuxilioTransporte', 'VMA': 'Viatico',
            'HED': 'HED', 'HEN': 'HEN', 'HRN': 'HRN',
            'HEDDF': 'HEDDF', 'HRDDF': 'HRDDF', 'HENDF': 'HENDF', 'HRNDF': 'HRNDF',
            'VACL': 'Vacaciones', 'VAP': 'Vacaciones', 'PVAC': 'Vacaciones',
            'PRI': 'Prima', 'PPRI': 'Prima', 'PRIL': 'Prima',
            'CES': 'Cesantias', 'CESL': 'Cesantias', 'PCES': 'Cesantias',
            'ICE': 'InteresesCesantias', 'ICEL': 'InteresesCesantias', 'PICE': 'InteresesCesantias',
            'INC': 'Incapacidad', 'IAT': 'IncapacidadAT',
            'LMP': 'LicenciaMatPat', 'LPA': 'LicenciaMatPat', 'LRE': 'LicenciaRemunerada',
            'BON': 'Bonificacion', 'AUX': 'Auxilio', 'OCP': 'OtroConcepto',
            'COR': 'CompensacionOrd', 'CEX': 'CompensacionExt',
            'BEP': 'BonusEPCTV', 'BEA': 'BonusAlimentacionEPCTV',
            'COM': 'Comision', 'PTP': 'PagoTercerosDev', 'ANT': 'AnticiposDev',
            'DOT': 'Dotacion', 'ASO': 'ApoyoSostenimiento', 'TTR': 'Teletrabajo',
            'BRT': 'BonifRetiro', 'IND': 'Indemnizacion', 'REI': 'ReintegroDev',
            'DED_EPS': 'DedSalud', 'DED_PENS': 'DedPension',
            'FOND_SOL': 'DedSolidaridad', 'FOND_SUB': 'DedSubsistencia',
            'SPU': 'SancionPublica', 'SPV': 'SancionPrivada',
            'LIB': 'Libranza', 'PTR': 'PagoTercerosDed', 'ADV': 'AnticiposDed',
            'ODD': 'OtraDeduccion', 'PVL': 'PensionVoluntaria', 'RFT': 'RetencionFuente',
            'AFC': 'AFC', 'COO': 'Cooperativa', 'EMB': 'EmbargoFiscal',
            'CPN': 'PlanComplementario', 'EDU': 'Educacion',
            'RIN': 'ReintegroDed', 'DEU': 'Deuda',
        }

        def _label(codes):
            return _concept_labels.get(codes[0], codes[0]) if codes else '?'

        # sub_trans
        for key, codes in [
            ('AuxilioTransporte', ['TPT']),
            ('ViaticoManutAlojS', ['VMA']),
            ('ViaticoManutAlojNS', ['VMA']),
        ]:
            val = float(sub_trans[key])
            result = _reclassify(val, codes, _label(codes))
            sub_trans[key] = '0.00' if result is None else '{:.2f}'.format(result)


        # holidays
        for vac_key, codes in [
            ('VacacionesComunes',     ['VACL', 'VAP', 'PVAC']),
            ('VacacionesCompensadas', ['VACL', 'VAP']),
        ]:
            if vac_key in holidays:
                cleaned = _reclassify_list(
                    holidays[vac_key],
                    {'Pago': (codes, vac_key)})
                if cleaned:
                    holidays[vac_key] = cleaned
                else:
                    del holidays[vac_key]

        # prima
        for key, codes in [
            ('Dev_Pri_Pago',   ['PRI', 'PPRI', 'PRIL']),
            ('Dev_Pri_PagoNS', ['PRI', 'PPRI', 'PRIL']),
        ]:
            val = float(prima[key])
            result = _reclassify(val, codes, _label(codes))
            prima[key] = '{:.2f}'.format(result) if result is not None else '0.00'

        # cesantías
        for key, codes in [
            ('Dev_Ces_Pago',          ['CES', 'CESL', 'PCES']),
            ('Dev_Ces_PagoIntereses', ['ICE', 'ICEL', 'PICE']),
        ]:
            val = float(ces[key])
            result = _reclassify(val, codes, _label(codes))
            ces[key] = '{:.2f}'.format(result) if result is not None else '0.00'

        # incapacidades
        inabilitys[:] = _reclassify_list(
            inabilitys, {'Pago': (['INC', 'IAT'], _label(['INC']))})

        # licencias
        for lic_key, codes in [
            ('LicenciaMP', ['LMP', 'LPA']),
            ('LicenciaR',  ['LRE']),
        ]:
            if lic_key in licenses:
                cleaned = _reclassify_list(
                    licenses[lic_key],
                    {'Pago': (codes, _label(codes))})
                licenses[lic_key] = cleaned

        # bonificaciones
        bonds[:] = _reclassify_list(bonds, {
            'BonificacionS':  (['BON'], _label(['BON'])),
            'BonificacionNS': (['BON'], _label(['BON'])),
        })

        # auxilios
        aids[:] = _reclassify_list(aids, {
            'AuxilioS':  (['AUX'], _label(['AUX'])),
            'AuxilioNS': (['AUX'], _label(['AUX'])),
        })

        # otros conceptos
        oconcepts[:] = _reclassify_list(oconcepts, {
            'ConceptoS':  (['OCP'], _label(['OCP'])),
            'ConceptoNS': (['OCP'], _label(['OCP'])),
        })

        # compensaciones
        compensations[:] = _reclassify_list(compensations, {
            'CompensacionO': (['COR'], _label(['COR'])),
            'CompensacionE': (['CEX'], _label(['CEX'])),
        })

        # bonos EPCTV
        epctvs[:] = _reclassify_list(epctvs, {
            'PagoS':              (['BEP'], _label(['BEP'])),
            'PagoNS':             (['BEP'], _label(['BEP'])),
            'PagoAlimentacionS':  (['BEA'], _label(['BEA'])),
            'PagoAlimentacionNS': (['BEA'], _label(['BEA'])),
        })

        # comisiones
        if 'Comision' in commissions:
            result = _reclassify(float(commissions['Comision']), ['COM'], _label(['COM']))
            if result is None:
                del commissions['Comision']
            else:
                commissions['Comision'] = '{:.2f}'.format(result)

        # pagos terceros devengo
        if 'PagoTercero' in dev_partners:
            result = _reclassify(float(dev_partners['PagoTercero']), ['PTP'], _label(['PTP']))
            if result is None:
                del dev_partners['PagoTercero']
            else:
                dev_partners['PagoTercero'] = '{:.2f}'.format(result)

        # anticipos dev
        if 'Anticipo' in dev_advances:
            result = _reclassify(float(dev_advances['Anticipo']), ['ANT'], _label(['ANT']))
            if result is None:
                del dev_advances['Anticipo']
            else:
                dev_advances['Anticipo'] = '{:.2f}'.format(result)

    
        for var_name, codes in [
            ('dotation',   ['DOT']),
            ('sus_support',['ASO']),
            ('telew',      ['TTR']),
            ('bonret',     ['BRT']),
            ('indem',      ['IND']),
            ('dev_return', ['REI']),
        ]:
            val = float(locals()[var_name])
            result = _reclassify(val, codes, _label(codes))
            
            locals()[var_name] 
            if result is None:
                exec(f"{var_name} = '0.00'") 
            elif result != val:
                exec(f"{var_name} = '{result:.2f}'") 


        _dev_scalars = {}
        for var_name, codes in [
            ('dotation',   ['DOT']),
            ('sus_support',['ASO']),
            ('telew',      ['TTR']),
            ('bonret',     ['BRT']),
            ('indem',      ['IND']),
            ('dev_return', ['REI']),
        ]:
            val = float({'dotation': dotation, 'sus_support': sus_support,
                         'telew': telew, 'bonret': bonret,
                         'indem': indem, 'dev_return': dev_return}[var_name])
            result = _reclassify(val, codes, _label(codes))
            _dev_scalars[var_name] = '0.00' if result is None else '{:.2f}'.format(result)

        dotation    = _dev_scalars['dotation']
        sus_support = _dev_scalars['sus_support']
        telew       = _dev_scalars['telew']
        bonret      = _dev_scalars['bonret']
        indem       = _dev_scalars['indem']
        dev_return  = _dev_scalars['dev_return']

        # deducciones con sus claves propias
        for d, key, codes in [
            (ded_health,      'Ded_Salud_Deduccion',    ['DED_EPS']),
            (ded_pension,     'Ded_FoPen_Deduccion',    ['DED_PENS']),
            (ded_solidarity,  'Ded_FoSP_Deduccion',     ['FOND_SOL']),
            (ded_subsistence, 'Ded_FoSP_DeduccionSub',  ['FOND_SUB']),
        ]:
            result = _reclassify(float(d[key]), codes, _label(codes))
            d[key] = '0.00' if result is None else '{:.2f}'.format(result)

        # sanciones
        sanctions[:] = _reclassify_list(sanctions, {
            'SancionPublic': (['SPU'], _label(['SPU'])),
            'SancionPriv':   (['SPV'], _label(['SPV'])),
        })

        # libranzas
        prommissory[:] = _reclassify_list(
            prommissory, {'Deduccion': (['LIB'], _label(['LIB']))})

        # pagos terceros deducciones
        if 'PagoTercero' in ded_partners:
            result = _reclassify(float(ded_partners['PagoTercero']), ['PTR'], _label(['PTR']))
            if result is None:
                del ded_partners['PagoTercero']
            else:
                ded_partners['PagoTercero'] = '{:.2f}'.format(result)

        # anticipos deduccion
        if 'Anticipo' in ded_advances:
            result = _reclassify(float(ded_advances['Anticipo']), ['ADV'], _label(['ADV']))
            if result is None:
                del ded_advances['Anticipo']
            else:
                ded_advances['Anticipo'] = '{:.2f}'.format(result)

        # otras deducciones
        if 'OtraDeduccion' in odeductions:
            result = _reclassify(float(odeductions['OtraDeduccion']), ['ODD'], _label(['ODD']))
            if result is None:
                del odeductions['OtraDeduccion']
            else:
                odeductions['OtraDeduccion'] = '{:.2f}'.format(result)

        # ── escalares deducciones ──
        _ded_scalars = {}
        for var_name, codes in [
            ('vol_pension',      ['PVL']),
            ('ded_rtefte', ['RFT']),
            ('afc',              ['AFC']),
            ('coop',             ['COO']),
            ('tax_emb',          ['EMB']),
            ('comp_plan',        ['CPN']),
            ('education',        ['EDU']),
            ('ded_return',       ['RIN']),
            ('debt',             ['DEU']),
        ]:
            val = float({
                'vol_pension': vol_pension, 'ded_rtefte': ded_rtefte,
                'afc': afc, 'coop': coop, 'tax_emb': tax_emb,
                'comp_plan': comp_plan, 'education': education,
                'ded_return': ded_return, 'debt': debt,
            }[var_name])
            result = _reclassify(val, codes, _label(codes))
            _ded_scalars[var_name] = '0.00' if result is None else '{:.2f}'.format(result)

        vol_pension      = _ded_scalars['vol_pension']
        ded_rtefte = _ded_scalars['ded_rtefte']
        afc              = _ded_scalars['afc']
        coop             = _ded_scalars['coop']
        tax_emb          = _ded_scalars['tax_emb']
        comp_plan        = _ded_scalars['comp_plan']
        education        = _ded_scalars['education']
        ded_return       = _ded_scalars['ded_return']
        debt             = _ded_scalars['debt']

        # Colocar inverse_accumulator en las variables destino
        inverse_target_map = {
            # Destino devengado
            'PTP': ('dev_partners',  'PagoTercero',  False),
            'ANT': ('dev_advances',  'Anticipo',      False),
            'COM': ('commissions',   'Comision',      False),
            'DOT': ('dotation',      None,            True),
            'ASO': ('sus_support',   None,            True),
            'TTR': ('telew',         None,            True),
            'BRT': ('bonret',        None,            True),
            'IND': ('indem',         None,            True),
            'REI': ('dev_return',    None,            True),
            # Destino deducción
            'PTR': ('ded_partners',  'PagoTercero',  False),
            'ADV': ('ded_advances',  'Anticipo',      False),
            'ODD': ('odeductions',   'OtraDeduccion', False),
            'LIB': ('prommissory',   'Deduccion',     False),
            'PVL': ('vol_pension',   None,            True),
            'RFT': ('ded_rtefte', None,         True),
            'AFC': ('afc',           None,            True),
            'COO': ('coop',          None,            True),
            'EMB': ('tax_emb',       None,            True),
            'CPN': ('comp_plan',     None,            True),
            'EDU': ('education',     None,            True),
            'RIN': ('ded_return',    None,            True),
            'DEU': ('debt',          None,            True),
        }

        _all_vars = {
            'dev_partners': dev_partners, 'dev_advances': dev_advances,
            'commissions': commissions, 'dotation': dotation,
            'sus_support': sus_support, 'telew': telew, 'bonret': bonret,
            'indem': indem, 'dev_return': dev_return,
            'ded_partners': ded_partners, 'ded_advances': ded_advances,
            'odeductions': odeductions, 'prommissory': prommissory,
            'vol_pension': vol_pension, 'ded_rtefte': ded_rtefte,
            'afc': afc, 'coop': coop, 'tax_emb': tax_emb,
            'comp_plan': comp_plan, 'education': education,
            'ded_return': ded_return, 'debt': debt,
        }

        for inv_code, accumulated in inverse_accumulator.items():
            if inv_code not in inverse_target_map:
                continue
            var_name, dict_key, is_scalar = inverse_target_map[inv_code]
            current = _all_vars[var_name]
            if is_scalar:
                current_val = float(current) if current else 0.0
                _all_vars[var_name] = '{:.2f}'.format(current_val + accumulated)
            else:
                if not isinstance(current, (dict, list)):
                    current = {} if dict_key else []
                if isinstance(current, list):
                    # Para libranza, se añade la descripción
                    current.append({
                        'Descripcion': 'Reclasificación automática',
                        dict_key: '{:.2f}'.format(accumulated),
                    })
                    _all_vars[var_name] = current
                else:
                    current_val = float(current.get(dict_key, 0))
                    current[dict_key] = '{:.2f}'.format(current_val + accumulated)
                    _all_vars[var_name] = current

        # Reasignación final desde _all_vars
        dev_partners     = _all_vars['dev_partners']
        dev_advances     = _all_vars['dev_advances']
        commissions      = _all_vars['commissions']
        dotation         = _all_vars['dotation']
        sus_support      = _all_vars['sus_support']
        telew            = _all_vars['telew']
        bonret           = _all_vars['bonret']
        indem            = _all_vars['indem']
        dev_return       = _all_vars['dev_return']
        ded_partners     = _all_vars['ded_partners']
        ded_advances     = _all_vars['ded_advances']
        odeductions      = _all_vars['odeductions']
        prommissory      = _all_vars['prommissory']
        vol_pension      = _all_vars['vol_pension']
        ded_rtefte = _all_vars['ded_rtefte']
        afc              = _all_vars['afc']
        coop             = _all_vars['coop']
        tax_emb          = _all_vars['tax_emb']
        comp_plan        = _all_vars['comp_plan']
        education        = _all_vars['education']
        ded_return       = _all_vars['ded_return']
        debt             = _all_vars['debt']

       

        # Recalcular totales con valores corregidos y reasignaciones 
        total_earnings = 0
        total_deductions = 0

        total_earnings += basic_wage['Dev_Bas_SueldoTrabajado']
        total_earnings += float(sub_trans.get('AuxilioTransporte', 0)) \
            + float(sub_trans.get('ViaticoManutAlojS', 0)) \
            + float(sub_trans.get('ViaticoManutAlojNS', 0))
        for x in hed:
            total_earnings += float(x.get('Pago', 0))
        for x in hen:
            total_earnings += float(x.get('Pago', 0))
        for x in hrn:
            total_earnings += float(x.get('Pago', 0))
        for x in heddf:
            total_earnings += float(x.get('Pago', 0))
        for x in hrddf:
            total_earnings += float(x.get('Pago', 0))
        for x in hendf:
            total_earnings += float(x.get('Pago', 0))
        for x in hrndf:
            total_earnings += float(x.get('Pago', 0))
        for x in holidays.get('VacacionesComunes', []):
            total_earnings += float(x.get('Pago', 0))
        for x in holidays.get('VacacionesCompensadas', []):
            total_earnings += float(x.get('Pago', 0))
        total_earnings += float(prima['Dev_Pri_Pago']) \
            + float(prima['Dev_Pri_PagoNS'])
        total_earnings += float(ces['Dev_Ces_Pago']) \
            + float(ces['Dev_Ces_PagoIntereses'])
        for x in inabilitys:
            total_earnings += float(x.get('Pago', 0))
        for x in licenses.get('LicenciaMP', []):
            total_earnings += float(x.get('Pago', 0))
        for x in licenses.get('LicenciaR', []):
            total_earnings += float(x.get('Pago', 0))
        for x in bonds:
            total_earnings += float(x.get('BonificacionNS', 0)) \
                + float(x.get('BonificacionS', 0))
        for x in aids:
            total_earnings += float(x.get('AuxilioNS', 0)) \
                + float(x.get('AuxilioS', 0))
        for x in oconcepts:
            total_earnings += float(x.get('ConceptoS', 0)) \
                + float(x.get('ConceptoNS', 0))
        for x in compensations:
            total_earnings += float(x.get('CompensacionO', 0)) \
                + float(x.get('CompensacionE', 0))
        for x in epctvs:
            total_earnings += float(x.get('PagoS', 0)) \
                + float(x.get('PagoNS', 0)) \
                + float(x.get('PagoAlimentacionS', 0)) \
                + float(x.get('PagoAlimentacionNS', 0))
        total_earnings += float(commissions.get('Comision', 0))
        total_earnings += float(dev_partners.get('PagoTercero', 0))
        total_earnings += float(dev_advances.get('Anticipo', 0))
        total_earnings += float(dotation)
        total_earnings += float(sus_support)
        total_earnings += float(telew)
        total_earnings += float(bonret)
        total_earnings += float(indem)
        total_earnings += float(dev_return)

        total_deductions += float(ded_health['Ded_Salud_Deduccion'])
        total_deductions += float(ded_pension['Ded_FoPen_Deduccion'])
        total_deductions += float(ded_solidarity['Ded_FoSP_Deduccion'])
        total_deductions += float(ded_subsistence['Ded_FoSP_DeduccionSub'])
        for x in sanctions:
            total_deductions += float(x.get('SancionPublic', 0)) \
                + float(x.get('SancionPriv', 0))
        for x in prommissory:
            total_deductions += float(x.get('Deduccion', 0))
        total_deductions += float(ded_partners.get('PagoTercero', 0))
        total_deductions += float(ded_advances.get('Anticipo', 0))
        total_deductions += float(odeductions.get('OtraDeduccion', 0))
        total_deductions += float(vol_pension)
        total_deductions += float(ded_rtefte)
        total_deductions += float(afc)
        total_deductions += float(coop)
        total_deductions += float(tax_emb)
        total_deductions += float(comp_plan)
        total_deductions += float(education)
        total_deductions += float(ded_return)
        total_deductions += float(debt)

        # ── Ambiente y campos NE ───────────────────────────────────
        ambiente = company.hr_target_environment or '2'
        ambiente_label = 'Producción' if ambiente == '1' else 'Habilitación'
        # Datos NE: disponibles solo si ya se creó el edi.hr.document
        numero_ne    = (edi_doc and edi_doc.edi_zahl)  or 'Pendiente'
        cune         = (edi_doc and edi_doc.edi_cune)  or ''
        estado_dian  = (edi_doc and edi_doc.hr_edi_state) or 'Sin enviar'
        tipo_ne      = (edi_doc and edi_doc.edi_type)  or ''
        fecha_gen_ne = (edi_doc and edi_doc.edi_datum) or ''
        # Período de liquidación: derivado de las nóminas (min start → max end)
        periodo_liq_inicio = period_ne.get('Per_FechaLiquidacionInicio', '')
        periodo_liq_fin    = period_ne.get('Per_FechaLiquidacionFin', '')
        f = self.fecha_informe or fields.Date.today()
        MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre',
                 'Diciembre']
        periodo_label = '%s %d' % (MESES[f.month - 1], f.year)

        # ── Días trabajados con days360 ────────────────────────────
        # Regla DIAN:
        #   inicio = max(fecha_inicio_contrato, primer_día_del_mes)
        #   fin    = fecha_liquidación si cae en este mes, si no → último_día_mes
        #   días   = days360(inicio, fin)
        primer_dia_mes, ultimo_dia_mes = self._mes_rango()
        contrato = payslips.mapped('contract_id').sorted(
            key=lambda r: r.date_start)
        contrato_inicio = contrato[0].date_start if contrato else primer_dia_mes
        contrato_fin    = contrato[-1] if contrato else False
        fecha_ini_dias = max(contrato_inicio, primer_dia_mes)
        settlement = (contrato_fin and contrato_fin.settlement_date) or False
        if settlement and primer_dia_mes <= settlement <= ultimo_dia_mes:
            fecha_fin_dias = settlement
        else:
            fecha_fin_dias = ultimo_dia_mes
        bas_dias_calc = float(days360(fecha_ini_dias, fecha_fin_dias))

        return {
            # ── A-AH: EMPLEADO / CONTRATO ─────────────────────────
            'periodo':            periodo_label,
            'fecha_inicio':       periodo_liq_inicio,
            'fecha_fin':          periodo_liq_fin,
            'tipo_periodo_dian':  period_ne.get('IGe_PeriodoNomina', ''),
            'nit_empleador':      employer_ne.get('Emp_NIT', ''),
            'dv_empleador':       employer_ne.get('Emp_DV', ''),
            'razon_social':       employer_ne.get('Emp_RazonSocial', ''),
            'tipo_doc':           employee.get('Tra_TipoDocumento', ''),
            'nro_doc':            employee.get('Tra_NumeroDocumento', ''),
            'primer_apellido':    employee.get('Tra_PrimerApellido', ''),
            'segundo_apellido':   employee.get('Tra_SegundoApellido', ''),
            'primer_nombre':      employee.get('Tra_PrimerNombre', ''),
            'otros_nombres':      employee.get('Tra_OtrosNombres', ''),
            'tipo_trabajador':    employee.get('Tra_TipoTrabajador', ''),
            'subtipo_trabajador': employee.get('Tra_SubTipoTrabajador', ''),
            'alto_riesgo':        employee.get('Tra_AltoRiesgoPension', ''),
            'tipo_contrato':      employee.get('Tra_TipoContrato', ''),
            'salario_integral':   employee.get('Tra_SalarioIntegral', ''),
            'sueldo':             float(employee.get('Tra_Sueldo', 0) or 0),
            'fecha_ingreso':      period_ne.get('Per_FechaIngreso', ''),
            'fecha_retiro':       period_ne.get('Per_FechaRetiro', ''),
            'fecha_liq_inicio':   period_ne.get('Per_FechaLiquidacionInicio', ''),
            'fecha_liq_fin':      period_ne.get('Per_FechaLiquidacionFin', ''),
            'tiempo_laborado':    float(period_ne.get('Per_TiempoLaborado', 0) or 0),
            'pais_trabajo':       workplace.get('LGX_Pais', ''),
            'dpto_trabajo':       workplace.get('LGX_DepartamentoEstado', ''),
            'ciudad_trabajo':     workplace.get('LGX_MunicipioCiudad', ''),
            'numero_ne':          numero_ne,
            'cune':               cune,
            'estado_dian':        estado_dian,
            'tipo_ne':            tipo_ne,
            'fecha_gen_ne':       fecha_gen_ne,
            'ambiente_dian':      ambiente_label,
            'periodo_nomina_dian': period_ne.get('IGe_PeriodoNomina', ''),  # AH
            # ── AI+: DEVENGOS ─────────────────────────────────────
            'bas_dias':           bas_dias_calc,
            'bas_valor':          float(basic_wage.get('Dev_Bas_SueldoTrabajado', 0) or 0),
            'tpt_auxilio':        float(sub_trans.get('AuxilioTransporte', 0) or 0),
            'vma_salarial':       float(sub_trans.get('ViaticoManutAlojS', 0) or 0),
            'vma_no_salarial':    float(sub_trans.get('ViaticoManutAlojNS', 0) or 0),
            'hed_cantidad':       sum(float(x.get('Cantidad', 0)) for x in hed),
            'hed_valor':          sum(float(x.get('Pago', 0)) for x in hed),
            'hen_cantidad':       sum(float(x.get('Cantidad', 0)) for x in hen),
            'hen_valor':          sum(float(x.get('Pago', 0)) for x in hen),
            'hrn_cantidad':       sum(float(x.get('Cantidad', 0)) for x in hrn),
            'hrn_valor':          sum(float(x.get('Pago', 0)) for x in hrn),
            'heddf_cantidad':     sum(float(x.get('Cantidad', 0)) for x in heddf),
            'heddf_valor':        sum(float(x.get('Pago', 0)) for x in heddf),
            'hrddf_cantidad':     sum(float(x.get('Cantidad', 0)) for x in hrddf),
            'hrddf_valor':        sum(float(x.get('Pago', 0)) for x in hrddf),
            'hendf_cantidad':     sum(float(x.get('Cantidad', 0)) for x in hendf),
            'hendf_valor':        sum(float(x.get('Pago', 0)) for x in hendf),
            'hrndf_cantidad':     sum(float(x.get('Cantidad', 0)) for x in hrndf),
            'hrndf_valor':        sum(float(x.get('Pago', 0)) for x in hrndf),
            'vac_dias':           sum(float(x.get('Cantidad', 0))
                                      for x in holidays.get('VacacionesComunes', [])),
            'vac_valor':          sum(float(x.get('Pago', 0))
                                      for x in holidays.get('VacacionesComunes', [])),
            'vap_dias':           sum(float(x.get('Cantidad', 0))
                                      for x in holidays.get('VacacionesCompensadas', [])),
            'vap_valor':          sum(float(x.get('Pago', 0))
                                      for x in holidays.get('VacacionesCompensadas', [])),
            'pri_cantidad':       float(prima.get('Dev_Pri_Cantidad', 0) or 0),
            'pri_salarial':       float(prima.get('Dev_Pri_Pago', 0) or 0),
            'pri_no_salarial':    float(prima.get('Dev_Pri_PagoNS', 0) or 0),
            'ces_valor':          float(ces.get('Dev_Ces_Pago', 0) or 0),
            'ces_porcentaje':     float(ces.get('Dev_Ces_Porcentaje', 0) or 0),
            'ces_intereses':      float(ces.get('Dev_Ces_PagoIntereses', 0) or 0),
            'inc_enf_dias':       sum(float(x.get('Cantidad', 0))
                                      for x in inabilitys if x.get('Tipo') == '1'),
            'inc_enf_valor':      sum(float(x.get('Pago', 0))
                                      for x in inabilitys if x.get('Tipo') == '1'),
            'inc_atep_dias':      sum(float(x.get('Cantidad', 0))
                                      for x in inabilitys if x.get('Tipo') == '2'),
            'inc_atep_valor':     sum(float(x.get('Pago', 0))
                                      for x in inabilitys if x.get('Tipo') == '2'),
            'lic_mp_dias':        sum(float(x.get('Cantidad', 0))
                                      for x in licenses.get('LicenciaMP', [])),
            'lic_mp_valor':       sum(float(x.get('Pago', 0))
                                      for x in licenses.get('LicenciaMP', [])),
            'lic_rem_dias':       sum(float(x.get('Cantidad', 0))
                                      for x in licenses.get('LicenciaR', [])),
            'lic_rem_valor':      sum(float(x.get('Pago', 0))
                                      for x in licenses.get('LicenciaR', [])),
            'lic_no_rem_dias':    sum(float(x.get('Cantidad', 0))
                                      for x in licenses.get('LicenciaNR', [])),
            'bon_salarial':       sum(float(x.get('BonificacionS', 0)) for x in bonds),
            'bon_no_salarial':    sum(float(x.get('BonificacionNS', 0)) for x in bonds),
            'aux_salarial':       sum(float(x.get('AuxilioS', 0)) for x in aids),
            'aux_no_salarial':    sum(float(x.get('AuxilioNS', 0)) for x in aids),
            'ocp_salarial':       sum(float(x.get('ConceptoS', 0)) for x in oconcepts),
            'ocp_no_salarial':    sum(float(x.get('ConceptoNS', 0)) for x in oconcepts),
            'comp_ordinaria':     sum(float(x.get('CompensacionO', 0)) for x in compensations),
            'comp_extraordinaria':sum(float(x.get('CompensacionE', 0)) for x in compensations),
            'bepctv_pago_s':      sum(float(x.get('PagoS', 0)) for x in epctvs),
            'bepctv_pago_ns':     sum(float(x.get('PagoNS', 0)) for x in epctvs),
            'bepctv_alim_s':      sum(float(x.get('PagoAlimentacionS', 0)) for x in epctvs),
            'bepctv_alim_ns':     sum(float(x.get('PagoAlimentacionNS', 0)) for x in epctvs),
            'comision':           float(commissions.get('Comision', 0)),
            'pago_tercero_dev':   float(dev_partners.get('PagoTercero', 0)),
            'anticipo_dev':       float(dev_advances.get('Anticipo', 0)),
            'dotacion':           float(dotation),
            'apoyo_sost':         float(sus_support),
            'teletrabajo':        float(telew),
            'bonif_retiro':       float(bonret),
            'indemnizacion':      float(indem),
            'reintegro_dev':      float(dev_return),
            # ── DEDUCCIONES ───────────────────────────────────────
            'ded_salud_pct':      float(ded_health.get('Ded_Salud_Porcentaje', 0) or 0),
            'ded_salud':          float(ded_health.get('Ded_Salud_Deduccion', 0) or 0),
            'ded_pension_pct':    float(ded_pension.get('Ded_FoPen_Porcentaje', 0) or 0),
            'ded_pension':        float(ded_pension.get('Ded_FoPen_Deduccion', 0) or 0),
            'ded_fsol_pct':       float(ded_solidarity.get('Ded_FoSP_Porcentaje', 0) or 0),
            'ded_fsol':           float(ded_solidarity.get('Ded_FoSP_Deduccion', 0) or 0),
            'ded_fsub_pct':       float(ded_subsistence.get('Ded_FoSP_PorcentajeSub', 0) or 0),
            'ded_fsub':           float(ded_subsistence.get('Ded_FoSP_DeduccionSub', 0) or 0),
            'ded_sancion_pub':    sum(float(x.get('SancionPublic', 0)) for x in sanctions),
            'ded_sancion_priv':   sum(float(x.get('SancionPriv', 0)) for x in sanctions),
            'ded_libranzas':      sum(float(x.get('Deduccion', 0)) for x in prommissory),
            'ded_pago_tercero':   float(ded_partners.get('PagoTercero', 0)),
            'ded_anticipo':       float(ded_advances.get('Anticipo', 0)),
            'ded_otras':          float(odeductions.get('OtraDeduccion', 0)),
            'ded_pension_vol':    float(vol_pension),
            'ded_rtefte':         float(ded_rtefte),
            'ded_afc':            float(afc),
            'ded_cooperativa':    float(coop),
            'ded_embargo':        float(tax_emb),
            'ded_plan_comp':      float(comp_plan),
            'ded_educacion':      float(education),
            'ded_reintegro':      float(ded_return),
            'ded_deuda':          float(debt),
            # ── TOTALES ───────────────────────────────────────────
            'total_devengado':    total_earnings,
            'total_deducciones':  total_deductions,
            'total_neto':         total_earnings - total_deductions,
        }
