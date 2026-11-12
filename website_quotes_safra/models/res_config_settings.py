# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .safra_panel import probar_formula
from . import safra_reglas_17 as R17


class ResConfigSettings(models.TransientModel):
    """Parámetros de la fórmula Best Fit de Panel Track (P19), editables
    por el cliente sin modo desarrollador. Se guardan como parámetros del
    sistema; si están vacíos rigen los valores del documento «Formula
    Final» (telo 0.35–0.95 m, persiana 8 m, rieles 4/5/6)."""
    _inherit = 'res.config.settings'

    # Mejoras Sprint 1.1 (21-oct, fila 18): texto de Safra junto al Máximo
    # total de lamas en el portal.
    MAX_LAMAS_TEXTO = ("Este valor indica el máximo total de lamas que puede seleccionar. En algunos sistemas, este valor se calcula según el ancho, tipo de mando y tipo de apertura seleccionados. (Si el valor mostrado es cero '0', asegúrese de haber ingresado correctamente el ancho, mando y apertura).")
    safra_max_lamas_texto = fields.Char(
        string='Texto del Máximo total de lamas', default=MAX_LAMAS_TEXTO,
        config_parameter='safra.max_lamas_texto',
        help='Se muestra en el portal junto al máximo total de lamas calculado.')

    # Revisión 27-oct (fila [0] #1): cuando falla la impresora se inhabilita
    # el estampado sin quitar la marca «estampable» de las telas. La casilla
    # enciende la regla V_ESTAMPADO_FUERA_SERVICIO (su mensaje se edita en
    # Validaciones).
    safra_estampado_fuera_servicio = fields.Boolean(
        string='Inhabilitar servicios de estampación',
        help='Al marcar «Diseño Impresión» en el portal sale el error de estampados fuera '
             'de servicio y no se deja continuar. Solo aplica en los sistemas con '
             'estampación.')

    # Revisión 27-oct (fila [0] #1): ancho máximo que permite la impresora;
    # la regla V_ESTAMPADO_SHEER_ELEGANCE lo usa como ancho_max_impresion.
    ANCHO_MAX_IMPRESION = 2.5
    safra_estampado_ancho_max = fields.Float(
        string='Ancho máximo de impresión (m)', default=ANCHO_MAX_IMPRESION, digits=(6, 2),
        config_parameter='safra.estampado.ancho_max',
        help='Valor que permite la impresora. Si la persiana es más ancha, no se deja '
             'estampar. Cambia cuando se cambia de equipo.')

    safra_panel_telo_min = fields.Float(
        string='Ancho mínimo del telo (m)', default=0.35,
        config_parameter='safra.panel.ancho_telo_min')
    safra_panel_telo_max = fields.Float(
        string='Ancho máximo del telo (m)', default=0.95,
        config_parameter='safra.panel.ancho_telo_max')
    safra_panel_ancho_max = fields.Float(
        string='Ancho máximo de la persiana (m)', default=8.0,
        config_parameter='safra.panel.ancho_max')
    safra_panel_rieles = fields.Char(
        string='Rieles disponibles (canales)', default='4,5,6',
        config_parameter='safra.panel.rieles',
        help='Cantidades de canales separadas por coma, ej: 4,5,6')

    # Prueba 126.1 (26-oct): pedidos de venta de exportación.
    safra_export_fiscal_position_id = fields.Many2one(
        'account.fiscal.position', string='Posición fiscal de exportación',
        config_parameter='safra.exportacion_posicion_fiscal',
        help='Se pone en el pedido de venta de una cotización de exportación (mapea el '
             'IVA a exento). Vacía = las líneas van sin impuestos.')
    safra_export_journal_id = fields.Many2one(
        'account.journal', string='Diario de facturas de exportación',
        config_parameter='safra.exportacion_diario', domain=[('type', '=', 'sale')],
        help='Diario con el que se facturan los pedidos de exportación. Vacío = el diario '
             'de ventas por defecto.')

    # Archivos de Safra «Tipos de corte tela» (26-oct): corte normal,
    # atravesado, añadido (persianas) y bajo falso o paños (cortinas).
    safra_corte_constante_tubo = fields.Char(
        string='Constante por tubo (m)', default='R8:0.17, R16:0.20, R24:0.20',
        config_parameter='safra.corte.constante_tubo',
        help='Persianas: tubo:metros separados por coma. Se suma al alto para ver si la '
             'tela se puede atravesar y limita el añadido (alto ≤ 2 × ancho del rollo − '
             'constante). Un tubo que no esté aquí usa el «Aumento tela del tubo» de la '
             'tabla de estructura.')
    safra_cortina_dobladillo_superior = fields.Float(
        string='Dobladillo superior (m)', default=0.06, digits=(6, 3),
        config_parameter='safra.cortina.dobladillo_superior')
    safra_cortina_dobladillo_inferior = fields.Float(
        string='Dobladillo inferior máximo (m)', default=0.21, digits=(6, 3),
        config_parameter='safra.cortina.dobladillo_inferior_max',
        help='Solo si ninguna opción de «Dobladillo o Bajo falso» del sistema tiene Consumo del '
             'dobladillo (revisión 30-oct).')
    safra_cortina_riel = fields.Float(
        string='Riel y espacio arriba (m)', default=0.035, digits=(6, 3),
        config_parameter='safra.cortina.riel')
    safra_cortina_tolerancia_bajo_falso = fields.Float(
        string='Bajo falso sobre el ancho del rollo (m)', default=0.12, digits=(6, 3),
        config_parameter='safra.cortina.tolerancia_bajo_falso')
    # Revisión 30-oct: fórmulas de alto y peso máximo del tubo, visibles y
    # editables (vacías = las del módulo).
    safra_formula_tubo_alto_espacio = fields.Char(
        string='Alto máximo por espacio',
        default=R17.FORMULAS_TUBO['safra.formula.tubo_alto_espacio'],
        config_parameter='safra.formula.tubo_alto_espacio')
    safra_formula_tubo_alto_carga = fields.Char(
        string='Alto máximo por carga',
        default=R17.FORMULAS_TUBO['safra.formula.tubo_alto_carga'],
        config_parameter='safra.formula.tubo_alto_carga')
    safra_formula_tubo_peso_total = fields.Char(
        string='Peso total de la persiana',
        default=R17.FORMULAS_TUBO['safra.formula.tubo_peso_total'],
        config_parameter='safra.formula.tubo_peso_total')
    safra_formula_tubo_carga_motor = fields.Char(
        string='Carga máxima del motor',
        default=R17.FORMULAS_TUBO['safra.formula.tubo_carga_motor'],
        config_parameter='safra.formula.tubo_carga_motor')
    # Revisión 30-oct: las fórmulas del corte de las cortinas, visibles y
    # editables (vacías = las del módulo).
    safra_formula_alto_maximo_dobladillo = fields.Char(
        string='Alto máximo con un dobladillo',
        default=R17.FORMULAS_CORTE_CORTINA['safra.formula.alto_maximo_dobladillo'],
        config_parameter='safra.formula.alto_maximo_dobladillo')
    safra_formula_cortina_normal = fields.Char(
        string='Cortina con corte normal si…',
        default=R17.FORMULAS_CORTE_CORTINA['safra.formula.cortina_normal'],
        config_parameter='safra.formula.cortina_normal')
    safra_formula_cortina_bajo_falso = fields.Char(
        string='Cortina con bajo falso si…',
        default=R17.FORMULAS_CORTE_CORTINA['safra.formula.cortina_bajo_falso'],
        config_parameter='safra.formula.cortina_bajo_falso')
    # Reunión 28-oct (fila 91): ancho de la cenefa en tela = ancho + esta
    # medida por cada lateral (Matriz 1.7: 11 cm).
    safra_cenefa_lateral = fields.Float(
        string='Cenefa en tela: medida por lateral (m)', default=0.11, digits=(6, 3),
        config_parameter='safra.cenefa.lateral')

    # Probar fórmulas (03-nov): campo de Ajustes de cada fórmula y su clave.
    CAMPOS_FORMULA = {
        'safra_formula_tubo_alto_espacio': 'safra.formula.tubo_alto_espacio',
        'safra_formula_tubo_alto_carga': 'safra.formula.tubo_alto_carga',
        'safra_formula_tubo_peso_total': 'safra.formula.tubo_peso_total',
        'safra_formula_tubo_carga_motor': 'safra.formula.tubo_carga_motor',
        'safra_formula_alto_maximo_dobladillo': 'safra.formula.alto_maximo_dobladillo',
        'safra_formula_cortina_normal': 'safra.formula.cortina_normal',
        'safra_formula_cortina_bajo_falso': 'safra.formula.cortina_bajo_falso',
    }

    def action_probar_formulas(self):
        """Ventana para probar las fórmulas tal como están escritas en
        pantalla (aunque no se hayan guardado) con una persiana real."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': 'Probar fórmulas con una persiana',
            'res_model': 'safra.formula.prueba', 'view_mode': 'form', 'target': 'new',
            'context': {'safra_formulas_prueba': {
                clave: self[campo] or '' for campo, clave in self.CAMPOS_FORMULA.items()}},
        }

    @api.model
    def _ancho_max_impresion(self):
        valor = self.env['ir.config_parameter'].sudo().get_param('safra.estampado.ancho_max')
        try:
            return float(valor) if valor else self.ANCHO_MAX_IMPRESION
        except ValueError:
            return self.ANCHO_MAX_IMPRESION

    def _regla_estampado_fuera_servicio(self):
        return self.env['safra.validation.rule']._por_clave(['V_ESTAMPADO_FUERA_SERVICIO'])[:1]

    @api.model
    def get_values(self):
        res = super().get_values()
        res['safra_estampado_fuera_servicio'] = bool(self._regla_estampado_fuera_servicio().active)
        return res

    def set_values(self):
        for campo, clave in (('safra_formula_alto_maximo_dobladillo', 'safra.formula.alto_maximo_dobladillo'),
                             ('safra_formula_cortina_normal', 'safra.formula.cortina_normal'),
                             ('safra_formula_cortina_bajo_falso', 'safra.formula.cortina_bajo_falso')):
            error = probar_formula(self.env, self[campo], [dict(R17.VARIABLES_CORTE_CORTINA)])
            if error:
                raise ValidationError('La fórmula «%s» tiene un error:\n%s'
                                      % (self._fields[campo].string, error))
        for campo in ('safra_formula_tubo_alto_espacio', 'safra_formula_tubo_alto_carga',
                      'safra_formula_tubo_peso_total', 'safra_formula_tubo_carga_motor'):
            error = probar_formula(self.env, self[campo], [dict(R17.VARIABLES_TUBO)], con_campos=False)
            if error:
                raise ValidationError('La fórmula «%s» del tubo tiene un error:\n%s'
                                      % (self._fields[campo].string, error))
        super().set_values()
        regla = self._regla_estampado_fuera_servicio()
        if regla and regla.active != self.safra_estampado_fuera_servicio:
            regla.active = self.safra_estampado_fuera_servicio
