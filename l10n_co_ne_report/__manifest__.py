# -*- coding: utf-8 -*-
{
    'name': 'Informe Previo Nómina Electrónica CO',
    'summary': '''
        Genera informe Excel con la información exacta que se envía a la DIAN,
        previo al envío de Nómina Electrónica.
    ''',
    'description': '''
        - Genera informe Excel con todos los devengos y deducciones DIAN
        - Usa los mismos métodos de cálculo que el envío a la DIAN
        - Permite filtrar por período, procesamiento, tipo y estado
        - Columnas A-AH: datos de empleado/contrato
        - Columnas AI+: conceptos DIAN (devengos y deducciones)
    ''',
    'author': 'OdOne S.A.S',
    'website': '',
    'license': 'OPL-1',
    'category': 'Human Resources',
    'version': '19.0.0.0.1',
    'depends': [
        'l10n_co_hr_bloodo',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/edi_hr_report_wizard_views.xml',
    ],
}
