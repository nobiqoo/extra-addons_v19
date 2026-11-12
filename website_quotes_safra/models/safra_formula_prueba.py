# -*- coding: utf-8 -*-
"""Probar fórmulas (03-nov): las fórmulas de Ajustes › Cotizador Safra
(tubo y corte de las cortinas) con los datos de una persiana real, como
probar una regla salarial en una nómina: variable por variable con su
valor y el «result» de cada fórmula, o su error. No cambia nada."""
import re

from markupsafe import Markup, escape

from odoo import api, fields, models

from .safra_panel import _mensaje_amigable, evaluar_formula
from . import safra_reglas_17 as R17

FORMULAS_TUBO = [
    ('safra.formula.tubo_carga_motor', 'Carga máxima del motor'),
    ('safra.formula.tubo_alto_espacio', 'Alto máximo por espacio'),
    ('safra.formula.tubo_alto_carga', 'Alto máximo por carga'),
    ('safra.formula.tubo_peso_total', 'Peso total de la persiana'),
]
FORMULAS_CORTINA = [
    ('safra.formula.alto_maximo_dobladillo', 'Alto máximo con un dobladillo'),
    ('safra.formula.cortina_normal', 'Cortina con corte normal si…'),
    ('safra.formula.cortina_bajo_falso', 'Cortina con bajo falso si…'),
]
TIPOS_CORTE = {
    'normal': 'Corte normal', 'bajo_falso': 'Bajo falso', 'panos': 'Por paños',
    'atravesado': 'Atravesado', 'anadido': 'Añadido', 'anadido_excede': 'Añadido (excede el máximo)',
    'no_fabricable': 'No se puede fabricar', 'sin_ancho_rollo': 'Sin ancho del rollo',
}
_NOMBRE = re.compile(r'\b[a-zA-Z_]\w*\b')
# Variables numéricas que salen del maestro: False = sin digitar.
NUMERICAS = {'peso_tela', 'grosor_tela', 'peso_perfil', 'espacio_eje_techo', 'diametro_tubo',
             'carga_maxima', 'torque', 'ancho_rollo'}


def _texto(valor, nombre=None):
    """Valor como se escribe en la fórmula (punto decimal)."""
    if valor is False and nombre in NUMERICAS:
        return 'vacío (sin digitar; vacio(%s) es True)' % nombre
    if isinstance(valor, bool):
        return '%s (%s)' % (valor, 'sí' if valor else 'no')
    if valor is None:
        return 'None (no se calcula)'
    if isinstance(valor, float):
        return repr(round(valor, 4))
    return repr(valor) if isinstance(valor, str) else str(valor)


class SafraFormulaPrueba(models.TransientModel):
    _name = 'safra.formula.prueba'
    _description = 'Probar las fórmulas de Ajustes con una persiana'

    line_id = fields.Many2one(
        'safra.quote.line', string='Persiana', domain=[('system_id', '!=', False), ('width', '>', 0)],
        help='Persiana de una cotización. Se usan sus medidas, su tela, su motor y su sistema; '
             'no se cambia nada en ella.')
    resultado = fields.Html(string='Resultado', compute='_compute_resultado', sanitize=False)

    # --- Evaluación -----------------------------------------------------

    @api.model
    def _codigo(self, clave):
        defectos = R17.FORMULAS_TUBO if clave in R17.FORMULAS_TUBO else R17.FORMULAS_CORTE_CORTINA
        return self.env['safra.structure.rule']._codigo_formula(self.env, clave, defectos)

    @api.model
    def _evaluar(self, clave, ctx):
        """(variables que usa la fórmula con su valor, result, error)."""
        codigo = self._codigo(clave)
        sin_comentarios = re.sub(r'#.*', '', codigo)
        usadas = [(n, ctx[n]) for n in dict.fromkeys(_NOMBRE.findall(sin_comentarios))
                  if n in ctx and n != 'result']
        try:
            return usadas, evaluar_formula(codigo, dict(ctx))[0], None
        except Exception as e:  # noqa: BLE001 — el error es lo que se quiere ver
            causa = e.args[0] if isinstance(e, ValueError) and e.args else e
            texto = str(causa).split(' while evaluating')[0]
            # raise Exception(...) en la fórmula: se muestra lo que trae.
            m = re.match(r"^Exception\((.*)\)$", texto, re.S)
            return usadas, None, m.group(1).strip('\'"') if m else _mensaje_amigable(texto)

    # --- HTML -------------------------------------------------------------

    @staticmethod
    def _tabla_formulas(filas):
        """filas: [(nombre, variables, result, error)]."""
        html = Markup('<table class="table table-sm table-bordered mb-3"><thead><tr>'
                      '<th>Fórmula</th><th>Variables (valor en esta persiana)</th><th>result</th>'
                      '</tr></thead><tbody>')
        for nombre, variables, valor, error in filas:
            vars_html = Markup('<br/>').join(
                Markup('<code>%s</code> = %s') % (n, _texto(v, n)) for n, v in variables) \
                or Markup('<span class="text-muted">—</span>')
            res = Markup('<span class="text-danger fw-bold">Error: %s</span>') % error if error \
                else Markup('<b>%s</b>') % _texto(valor)
            html += Markup('<tr><td>%s</td><td class="small">%s</td><td>%s</td></tr>') % (
                nombre, vars_html, res)
        return html + Markup('</tbody></table>')

    def _html_tubo(self, line):
        system = line.system_id
        Rule = self.env['safra.structure.rule'].sudo()
        html = Markup('<h5 class="mt-2">Tubo: alto y peso máximo</h5>')
        if not Rule.search_count([('system_ids', 'in', system.id)]):
            return html + Markup('<p class="text-muted">El sistema %s no tiene Estructura por Ancho: '
                                 'no usa estas fórmulas.</p>') % system.name
        if system.tubo_solo_ancho:
            return html + Markup('<p class="text-muted">El sistema %s tiene «Tubo solo por ancho»: '
                                 'el tubo sale de la Estructura por Ancho y no usa estas fórmulas.</p>') % system.name
        attrs = line.attribute_values or {}
        params = line._params_estructura()
        res = Rule.elegir(system, line.width or 0.0, line.height or 0.0,
                          motorized=bool(line.has_motor or attrs.get('unificacion_motor')),
                          cabezal=line._cabezal_elegido()[0],
                          unificacion=attrs.get('unificacion_mando') or None, **params)
        regla = res['regla']
        if not regla:
            return html + Markup('<p class="text-muted">No hay fila de la Estructura por Ancho para '
                                 'este ancho.</p>')
        texto = Markup('Tubo de esta persiana: <b>%s</b> (%s).') % (
            regla.tubo, 'con motor' if regla.drive_type == 'motor' or line.has_motor else 'manual')
        if res['subio_de']:
            texto += Markup(' Por el ancho tocaba %s, pero el alto no alcanza y pasó a %s.') % (
                res['subio_de'], regla.tubo)
        html += Markup('<p>%s</p>') % texto
        # Sin motor, _params_estructura trae torque y carga del motor en 0.
        filas = []
        if line.has_motor:
            filas.append(('Carga máxima del motor',) + self._evaluar(
                'safra.formula.tubo_carga_motor', regla._ctx_carga_motor(params['torque'])))
        ctx = regla._ctx_limites(line.width or 0.0, line.height or 0.0, **params)
        for clave, nombre in FORMULAS_TUBO[1:]:
            filas.append((nombre,) + self._evaluar(clave, ctx))
        html += self._tabla_formulas(filas)
        if line.has_motor and filas[0][2] is None:
            html += Markup('<p class="small text-muted mb-1">La carga del motor no se calcula con el torque: '
                           'se usa la Carga maxima del producto del motor. Sin ninguno de los dos en el '
                           'maestro no hay con qué comparar el peso (sin motor elegido, la de la fila '
                           'de la Estructura por Ancho).</p>')
        # Revisión 10-nov: de dónde sale la carga y cómo está cada dato.
        if res['limites'].get('carga_detalle'):
            html += Markup('<p class="small mb-1">%s</p>') % res['limites']['carga_detalle']
        lim = res['limites']
        html += Markup('<p class="small mb-1">Con esto: alto máximo <b>%s</b> m (el menor entre espacio y '
                       'carga), peso <b>%s</b> g contra carga máxima <b>%s</b> g → %s.</p>') % (
            _texto(lim.get('alto_maximo')), _texto(lim.get('peso_total')), _texto(lim.get('carga_maxima')),
            'cumple' if lim.get('alto_ok') is not False and lim.get('peso_ok') is not False else 'no cumple')
        # El mismo cuadro del «?» de la Ficha técnica.
        cuadro = Rule.opciones(system, line.width or 0.0, line.height or 0.0,
                               cabezal=line._cabezal_elegido()[0], **params)
        if cuadro:
            html += Markup('<p class="small text-muted mb-1">Cuadro del «?» de la Ficha técnica con estas '
                           'fórmulas:</p><table class="table table-sm mb-3"><thead><tr><th>Accionamiento</th>'
                           '<th>Tubo</th><th>Alto máximo</th><th>Peso persiana</th><th>Carga máxima</th>'
                           '<th>Cumple</th></tr></thead><tbody>')
            for f in cuadro:
                html += Markup('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>') % (
                    f['accionamiento'], f['tubo'], _texto(f['alto_maximo']), _texto(f['peso_total']),
                    _texto(f['carga_maxima']), 'Sí' if f['cumple'] else 'No')
            html += Markup('</tbody></table>')
        return html

    def _html_cortina(self, line):
        html = Markup('<h5 class="mt-2">Cortinas: fórmulas del corte</h5>')
        if not line._ancho_rollo():
            return html + Markup('<p class="text-muted">El color no tiene ancho del rollo (U_Ancho): '
                                 'no se calculan.</p>')
        filas = []
        for consumo in line._consumos_cortina():
            filas.append(('%s (consumo %s)' % (FORMULAS_CORTINA[0][1], _texto(consumo)),) + self._evaluar(
                FORMULAS_CORTINA[0][0], line._variables_corte_cortina(consumo=consumo)))
        ctx = line._ctx_corte_cortina()
        for clave, nombre in FORMULAS_CORTINA[1:]:
            filas.append((nombre,) + self._evaluar(clave, ctx))
        html += self._tabla_formulas(filas)
        corte = line._corte_tela()
        texto = Markup('Corte de esta cortina: <b>%s</b>') % TIPOS_CORTE.get(corte['tipo'], corte['tipo'] or '—')
        if corte.get('panos'):
            texto += Markup(' (%s paños)') % corte['panos']
        if corte.get('motivo'):
            texto += Markup(': %s') % corte['motivo']
        return html + Markup('<p class="small">%s.</p>') % texto

    @api.depends('line_id')
    def _compute_resultado(self):
        for wiz in self:
            line = wiz.line_id.sudo()
            if not line:
                wiz.resultado = Markup('<p class="text-muted">Elija una persiana.</p>')
                continue
            html = Markup('<p class="mb-2"><b>%s</b> · %s × %s m · %s %s%s</p>') % (
                line.system_id.name, line.width or 0, line.height or 0, line.fabric_id.name or '',
                line.color_id.name or '', Markup(' · con motor') if line.has_motor else '')
            if line.system_id.calculo_corte == 'cortina':
                html += wiz._html_cortina(line)
            else:
                html += wiz._html_tubo(line)
            wiz.resultado = html
