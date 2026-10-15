# -*- coding: utf-8 -*-
from odoo import models, fields
import base64
import io
try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None

MAIL_TEMPLATE = "hr_payroll_co.hr_concept_rtefte_mail_template"

class HrConceptRteFte(models.Model):
    _name = "hr.concept.rtefte"
    _description = "Certificado de retención en la fuente"
    _rec_name = 'name'

    # _sql_constraints ya no está soportado en Odoo 19; el wizard depende de
    # esta restricción única para su INSERT ... ON CONFLICT (payslip_id, user_id).
    # El reporte es por usuario, por lo que la unicidad debe ser por nómina y usuario.
    _unique_payslip = models.Constraint(
        'UNIQUE (payslip_id, user_id)',
        'Ya existe un registro para esta nómina!',
    )

    # No redefinir display_name: en Odoo 17+ es un campo computado reservado
    # de BaseModel y nunca crea columna en la tabla.
    name = fields.Char(string='Nombre', readonly=True)
    company_id = fields.Many2one(
        comodel_name="res.company", string='Compañia', readonly=True)

    # Campos contextuales
    period_id = fields.Many2one(
        comodel_name='hr.period', string='Periodo', readonly=True)
    payslip_id = fields.Many2one(
        comodel_name='hr.payslip', string='Nómina', readonly=True)
    employee_id = fields.Many2one(
        comodel_name='hr.employee', string='Empleado', readonly=True)
    contract_id = fields.Many2one(
        comodel_name='hr.contract', string='Contrato', readonly=True)
    payslip_processing_id = fields.Many2one(
        comodel_name='hr.payslip.processing', string='Procesamiento de Nómina', readonly=True)

    contract_date_start = fields.Date(
        string='Fecha de inicio del contrato', readonly=True)
    contract_settlement_date = fields.Date(
        string='Fecha de liquidación del contrato', readonly=True)
    wage = fields.Float(string='Salario', readonly=True)
    contract_duration = fields.Float(
        string='Duración del contrato', readonly=True)

    # Campo de retención en la fuente
    earnings = fields.Float(string='Devengos', readonly=True)
    o_earnings = fields.Float(string='Otros devengos', readonly=True)
    o_salarial_earnings = fields.Float(
        string='Otros devengos salariales', readonly=True)
    comp_earnings = fields.Float(
        string='Ingresos complementarios', readonly=True)
    o_rights = fields.Float(string='Otros derechos', readonly=True)
    income_ext = fields.Float(string='Ingreso exento', readonly=True)
    apply_procedure_2 = fields.Boolean(string='Procedimiento 2', readonly=True)
    prima = fields.Float(string='Prima', readonly=True)
    prima_liq = fields.Float(string='Prima Liquida', readonly=True)
    total_income = fields.Float(string='Total Ingresos', readonly=True)
    ded_pens = fields.Float(string='Deducción Pensión', readonly=True)
    ded_eps = fields.Float(string='Deducción EPS', readonly=True)
    fond_sol = fields.Float(string='Fondo de solidaridad', readonly=True)
    fond_sub = fields.Float(string='Fondo de subsistencia', readonly=True)
    total_nci = fields.Float(
        string='Total Deducciones No Constitutivas de Ingreso', readonly=True)
    neto_income = fields.Float(string='Ingreso Neto', readonly=True)
    current_year = fields.Integer(string='Año actual', readonly=True)
    uvt = fields.Float(string='UVT', readonly=True)
    deduction_dependents = fields.Float(
        string='Deducción Dependientes', readonly=True)
    deduction_estate = fields.Float(
        string='Deducción Interes Vivienda', readonly=True)
    deduction_healthcare = fields.Float(
        string='Deducción Medicina Prepagada', readonly=True)
    deduction_icetex = fields.Float(
        string='Deducción Intereses ICETEX', readonly=True)
    deduction_total = fields.Float(string='Total Deducciones', readonly=True)
    avp = fields.Float(string='Aporte Voluntario Pensiones', readonly=True)
    afc = fields.Float(
        string='Ahorro para el Fomento a la Construcción', readonly=True)
    voluntary_contributions = fields.Float(
        string='Contribuciones Voluntarias', readonly=True)
    annual_top25 = fields.Float(string='Límite Anual Top 25%', readonly=True)
    top25_monthly = fields.Float(string='Top 25% Mensual', readonly=True)
    top25_total = fields.Float(string='Top 25% Total', readonly=True)
    annual_top40 = fields.Float(string='Límite Anual Top 40%', readonly=True)
    top40_monthly = fields.Float(string='Top 40% Mensual', readonly=True)
    top40_total = fields.Float(string='Top 40% Total', readonly=True)
    exempt_rent = fields.Float(string='Renta Exenta', readonly=True)
    brtf = fields.Float(string='Base RTEFTE', readonly=True)
    rate = fields.Float(string='Tasa RTEFTE', readonly=True)
    rtefte = fields.Float(string='Total RTEFTE', readonly=True)

    # Campos funcionales
    mail_sent = fields.Boolean(
        string='Correo enviado', default=False, readonly=True)

    user_id = fields.Many2one(
        comodel_name='res.users', string='Usuario', readonly=True)

    def action_send_mail(self):
        """Send the RTEFTE report by email to multiple records"""
        template = self.env.ref(MAIL_TEMPLATE)
        if not template:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'No se encontró la plantilla de correo.',
                    'type': 'danger',
                    'sticky': False,
                }
            }

        # Contador para mensajes
        sent_count = 0
        already_sent_count = 0

        for record in self:
            if record.mail_sent:
                already_sent_count += 1
                continue

            template.send_mail(record.id, force_send=True)
            record.mail_sent = True
            sent_count += 1

        # Preparar mensaje de respuesta
        message = []
        if sent_count > 0:
            message.append(
                f'Se enviaron {sent_count} certificado(s) exitosamente.')
        if already_sent_count > 0:
            message.append(
                f'{already_sent_count} certificado(s) ya habían sido enviados anteriormente.')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': ' '.join(message),
                'type': 'success' if sent_count > 0 else 'warning',
                'sticky': False,
            }
        }

    def action_export_excel(self):
        if not xlsxwriter:
            raise ImportError(
                'Esta función requiere la biblioteca xlsxwriter. Por favor instálela con pip install xlsxwriter')

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'nan_inf_to_errors': True})

        # Formatos
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'fg_color': '#D3D3D3',
            'border': 1
        })

        cell_format = workbook.add_format({
            'align': 'left',
            'valign': 'vcenter',
            'border': 1
        })

        number_format = workbook.add_format({
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
            'num_format': '#,##0.00'
        })

        date_format = workbook.add_format({
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
            'num_format': 'dd/mm/yyyy'
        })

        # Crear hoja de datos detallados
        worksheet = workbook.add_worksheet('Detalle RTEFTE')

        # Encabezados
        headers = {
            # Información básica
            'A1': 'Empleado',
            'B1': 'Contrato',
            'C1': 'Periodo',
            'D1': 'Fecha Inicio',
            'E1': 'Fecha Fin',
            'F1': 'Salario',
            'G1': 'Tipo de procedimiento',

            # Ingresos laborales
            'H1': 'Devengos',
            'I1': 'Devengos Salariales',
            'J1': 'Otros Devengos',
            'K1': 'Ingresos Complementarios',
            'L1': 'Otros Derechos',
            'M1': 'Prima',
            'N1': 'Prima Líquida',
            'O1': 'Ingreso Exento',
            'P1': 'Total Ingresos',

            # Ingresos no constitutivos de renta
            'Q1': 'Deducción Pensión',
            'R1': 'Deducción EPS',
            'S1': 'Fondo Solidaridad',
            'T1': 'Fondo Subsistencia',
            'U1': 'Total ingresos no constitutivos',

            # Deducciones
            'V1': 'Deducción Dependientes',
            'W1': 'Deducción Vivienda',
            'X1': 'Deducción Salud',
            'Y1': 'Deducción ICETEX',
            'Z1': 'Total Deducciones',

            # Aportes voluntarios
            'AA1': 'AVP',
            'AB1': 'AFC',
            'AC1': 'Contribuciones Voluntarias',

            # Depuración renta
            'AD1': 'Ingreso Neto',
            'AE1': 'UVT',
            'AF1': 'Top 25% Mensual',
            'AG1': 'Top 25% Total',
            'AH1': 'Top 40% Mensual',
            'AI1': 'Top 40% Total',
            'AJ1': 'Renta Exenta',

            # Retención
            'AK1': 'Base RTEFTE',
            'AL1': 'Tasa',
            'AM1': 'Total RTEFTE'
        }

        # Escribir encabezados en hoja de detalle
        for cell, value in headers.items():
            worksheet.write(cell, value, header_format)

        # Ajustar ancho de columnas
        worksheet.set_column('A:AM', 15)

        # Obtener registros seleccionados o todo el reporte del usuario
        records = self.env.context.get('active_ids', False)
        domain = [('id', 'in', records)] if records else [
            ('user_id', '=', self.env.uid), ('company_id', '=', self.env.company.id)]
        rtefte_records = self.search(domain)

        # Escribir datos en hoja de detalle
        row = 1
        for record in rtefte_records:
            # Información básica
            worksheet.write(row, 0, record.employee_id.name, cell_format)
            worksheet.write(row, 1, record.contract_id.name, cell_format)
            worksheet.write(row, 2, record.period_id.name, cell_format)

            # Manejo de fechas
            if record.contract_date_start:
                worksheet.write_datetime(
                    row, 3, record.contract_date_start, date_format)
            else:
                worksheet.write(row, 3, '', cell_format)

            if record.contract_settlement_date:
                worksheet.write_datetime(
                    row, 4, record.contract_settlement_date, date_format)
            else:
                worksheet.write(row, 4, '', cell_format)

            worksheet.write(row, 5, record.wage, number_format)
            worksheet.write(
                row, 6, '2' if record.apply_procedure_2 else '1', cell_format)

            # Ingresos laborales
            worksheet.write(row, 7, record.earnings, number_format)
            worksheet.write(row, 8, record.o_salarial_earnings, number_format)
            worksheet.write(row, 9, record.o_earnings, number_format)
            worksheet.write(row, 10, record.comp_earnings, number_format)
            worksheet.write(row, 11, record.o_rights, number_format)
            worksheet.write(row, 12, record.prima, number_format)
            worksheet.write(row, 13, record.prima_liq, number_format)
            worksheet.write(row, 14, record.income_ext, number_format)
            worksheet.write(row, 15, record.total_income, number_format)

            # Ingresos no constitutivos de renta
            worksheet.write(row, 16, record.ded_pens, number_format)
            worksheet.write(row, 17, record.ded_eps, number_format)
            worksheet.write(row, 18, record.fond_sol, number_format)
            worksheet.write(row, 19, record.fond_sub, number_format)
            worksheet.write(row, 20, record.total_nci, number_format)

            # Deducciones
            worksheet.write(
                row, 21, record.deduction_dependents, number_format)
            worksheet.write(row, 22, record.deduction_estate, number_format)
            worksheet.write(
                row, 23, record.deduction_healthcare, number_format)
            worksheet.write(row, 24, record.deduction_icetex, number_format)
            worksheet.write(row, 25, record.deduction_total, number_format)

            # Aportes voluntarios
            worksheet.write(row, 26, record.avp, number_format)
            worksheet.write(row, 27, record.afc, number_format)
            worksheet.write(
                row, 28, record.voluntary_contributions, number_format)

            # Depuración renta
            worksheet.write(row, 29, record.neto_income, number_format)
            worksheet.write(row, 30, record.uvt, number_format)
            worksheet.write(row, 31, record.top25_monthly, number_format)
            worksheet.write(row, 32, record.top25_total, number_format)
            worksheet.write(row, 33, record.top40_monthly, number_format)
            worksheet.write(row, 34, record.top40_total, number_format)
            worksheet.write(row, 35, record.exempt_rent, number_format)

            # Retención
            worksheet.write(row, 36, record.brtf, number_format)
            worksheet.write(row, 37, record.rate, number_format)
            worksheet.write(row, 38, record.rtefte, number_format)
            row += 1

        # Agregar totales en hoja de detalle
        worksheet.write(row, 0, 'TOTALES', header_format)

        # Lista de columnas que no deben tener totales (0-based index)
        no_total_columns = [6, 30, 37]  # Tipo procedimiento, UVT, Tasa

        # Agregar fórmulas de suma para las columnas numéricas
        for col in range(5, 39):
            if col not in no_total_columns:
                col_letter = xlsxwriter.utility.xl_col_to_name(col)
                start_row = 2  # Fila 2 (después del encabezado)
                end_row = row  # Última fila antes del total
                formula = f'=SUM({col_letter}{start_row}:{col_letter}{end_row})'
                worksheet.write_formula(row, col, formula, number_format)

        # Crear hoja de tabla dinámica
        pivot_sheet = workbook.add_worksheet('Análisis RTEFTE')

        # Configurar formato para la tabla dinámica
        pivot_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'fg_color': '#E6E6E6',
            'border': 1,
            'num_format': '#,##0.00'
        })

        # Escribir tabla dinámica para análisis por periodo
        pivot_sheet.write('A1', 'Análisis por Periodo', header_format)
        pivot_sheet.write('A3', 'Periodo', header_format)
        pivot_sheet.write('B3', 'Total Ingresos', header_format)
        pivot_sheet.write('C3', 'Total No Constitutivos', header_format)
        pivot_sheet.write('D3', 'Total Deducciones', header_format)
        pivot_sheet.write('E3', 'Renta Exenta', header_format)
        pivot_sheet.write('F3', 'Base RTEFTE', header_format)
        pivot_sheet.write('G3', 'Total RTEFTE', header_format)

        # Fórmulas para la tabla dinámica por periodo
        row_pivot = 4
        for period in list(set(record.period_id.name for record in rtefte_records)):
            pivot_sheet.write(f'A{row_pivot}', period, cell_format)

            # Fórmulas SUMIF para cada columna
            pivot_sheet.write_formula(
                f'B{row_pivot}',
                f'=SUMIF(Detalle!C:C,A{row_pivot},Detalle!P:P)',
                number_format
            )
            pivot_sheet.write_formula(
                f'C{row_pivot}',
                f'=SUMIF(Detalle!C:C,A{row_pivot},Detalle!U:U)',
                number_format
            )
            pivot_sheet.write_formula(
                f'D{row_pivot}',
                f'=SUMIF(Detalle!C:C,A{row_pivot},Detalle!Z:Z)',
                number_format
            )
            pivot_sheet.write_formula(
                f'E{row_pivot}',
                f'=SUMIF(Detalle!C:C,A{row_pivot},Detalle!AJ:AJ)',
                number_format
            )
            pivot_sheet.write_formula(
                f'F{row_pivot}',
                f'=SUMIF(Detalle!C:C,A{row_pivot},Detalle!AK:AK)',
                number_format
            )
            pivot_sheet.write_formula(
                f'G{row_pivot}',
                f'=SUMIF(Detalle!C:C,A{row_pivot},Detalle!AM:AM)',
                number_format
            )
            row_pivot += 1

        # Agregar totales a la tabla dinámica
        pivot_sheet.write(f'A{row_pivot}', 'TOTAL', header_format)
        for col in ['B', 'C', 'D', 'E', 'F', 'G']:
            end_cell = f'{col}{row_pivot-1}'
            start_cell = f'{col}4'
            pivot_sheet.write_formula(
                f'{col}{row_pivot}',
                f'=SUM({start_cell}:{end_cell})',
                pivot_format
            )

        # Ajustar ancho de columnas en la hoja de tabla dinámica
        pivot_sheet.set_column('A:G', 20)

        workbook.close()
        output.seek(0)

        # Crear adjunto
        filename = 'Retención_en_la_Fuente.xlsx'
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': base64.b64encode(output.read()),
            'store_fname': filename,
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
