# -*- coding: utf-8 -*-
import ast
import base64
import functools
import io
import logging
import math
import re
import unicodedata
from decimal import Decimal, ROUND_HALF_UP

import openpyxl
from markupsafe import Markup
from openpyxl.worksheet.formula import ArrayFormula

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import file_open
from odoo.tools.safe_eval import safe_eval, test_python_expr

from . import excel_formula
from .fields_vacio import FloatVacio


_logger = logging.getLogger(__name__)

_NOMBRE_VARIABLE = re.compile(r'^[a-z_][a-z0-9_]*$')


def variables_formulario(campos, base):
    """Reunión 28-sep (fila 16): las fórmulas pueden usar cualquier campo
    del cotizador por su código técnico (p. ej. «width», «tamano_traslape»
    o un campo creado después). Recibe {código: valor} de la línea y
    devuelve las variables utilizables: números como float, el resto como
    texto. Nunca reemplaza una variable propia de la fórmula (`base`)."""
    out = {}
    for code, val in (campos or {}).items():
        code = str(code)
        if not _NOMBRE_VARIABLE.match(code) or code in base:
            continue
        if isinstance(val, bool):
            out[code] = 1.0 if val else 0.0
            continue
        try:
            out[code] = float(str(val).replace(',', '.'))
        except (TypeError, ValueError):
            out[code] = val if isinstance(val, str) else ''
    return out


def vacio(valor):
    """True si el dato no se digitó en el maestro (casilla vacía); un 0
    digitado NO es vacío. Se usa dentro de cualquier fórmula:
    `if vacio(ancho_rollo): ...`."""
    return valor is None or valor is False


def _ruta(nodo):
    """`tela.peso_gm2` → ('tela', 'peso_gm2'); `limites['wmax']` y
    `limites.get('wmax')` → ('limites', "['wmax']"); None si no empieza en un
    nombre."""
    partes = []
    while True:
        if isinstance(nodo, ast.Attribute):
            partes.append(nodo.attr)
            nodo = nodo.value
        elif isinstance(nodo, ast.Subscript) and isinstance(nodo.slice, ast.Constant):
            partes.append('[%r]' % (nodo.slice.value,))
            nodo = nodo.value
        elif (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute)
              and nodo.func.attr == 'get' and nodo.args and isinstance(nodo.args[0], ast.Constant)):
            partes.append('[%r]' % (nodo.args[0].value,))
            nodo = nodo.func.value
        elif isinstance(nodo, ast.Name):
            partes.append(nodo.id)
            return tuple(reversed(partes))
        else:
            return None


@functools.lru_cache(maxsize=2048)
def datos_usados(codigo):
    """Lo que lee una fórmula: nombres y sus rutas (`tela.peso_gm2`,
    `limites['wmax']`), para avisar cuáles usan un dato sin digitar. Código
    que no se puede leer: ninguno."""
    try:
        arbol = ast.parse((codigo or '').strip())
    except SyntaxError:
        return frozenset()
    rutas = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.Name, ast.Attribute, ast.Subscript, ast.Call)):
            ruta = _ruta(nodo)
            if ruta:
                rutas.add(ruta)
    return frozenset(rutas)


def evaluar_formula(codigo, ctx):
    """Fórmulas al estilo de las reglas salariales de nómina: una expresión
    de una línea devuelve su valor; un bloque de varias líneas asigna
    `result` (y, si aplica, otras variables como `velcrado`). Devuelve
    (valor, variables del bloque). Lanza la excepción si el código falla."""
    codigo = (codigo or '').strip()
    if not codigo:
        return None, {}
    local = dict(ctx)
    local.setdefault('vacio', vacio)
    if not test_python_expr(codigo, mode='eval'):
        return safe_eval(codigo, local), local
    safe_eval(codigo, local, mode='exec')
    return local.get('result'), local


def _redondeo_excel(valor):
    """ROUND(x; 0) de Excel: el ,5 sube (Python redondea al par: 12,5 → 12)."""
    return int(Decimal(repr(valor)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def _par_hacia_arriba(valor):
    """EVEN(x) de Excel para positivos: el siguiente entero par hacia arriba
    (21,96 → 22; 14,34 → 16)."""
    n = math.ceil(round(valor, 9))
    return n + 1 if n % 2 else n


def _campos_en_cero(env):
    return {c: 0 for c in env['safra.field'].sudo().with_context(
        active_test=False).search([]).mapped('code') if c}


def probar_formula(env, codigo, contextos, ignorar=None, con_campos=True):
    """Revisión al guardar: compila el código y lo ejecuta con contextos de
    ejemplo (todos los campos del cotizador valen 0). Devuelve el mensaje
    del primer error o False si la fórmula funciona. Con `con_campos` en
    False solo valen las variables de los contextos (fórmulas que no
    reciben los campos del cotizador, como las del tubo)."""
    codigo = (codigo or '').strip()
    if not codigo:
        return False
    es_bloque = bool(test_python_expr(codigo, mode='eval'))
    if es_bloque:
        error = test_python_expr(codigo, mode='exec')
        if error:
            return _mensaje_amigable(error)
        if not _ASIGNA_RESULT.search(codigo):
            return 'Una fórmula de varias líneas debe asignar «result» (p. ej. result = telos + 1).'
    campos = _campos_en_cero(env) if con_campos else {}
    for ctx in contextos:
        base = dict(ctx)
        base.update(variables_formulario(campos, base))
        try:
            valor, _vars = evaluar_formula(codigo, base)
        except Exception as e:
            if ignorar and ignorar(e):
                continue
            causa = e.args[0] if isinstance(e, ValueError) and e.args else e
            return '%s (probando con %s)' % (
                _mensaje_amigable(str(causa).split(' while evaluating')[0]),
                ', '.join('%s=%s' % (k, ctx[k]) for k in sorted(ctx) if k in _MOSTRAR))
        if valor is not None and not isinstance(valor, (int, float)):
            return 'La fórmula debe devolver un número (o None); devolvió %r.' % (valor,)
    return False


def _mensaje_amigable(texto):
    """Errores de Python en palabras del funcional."""
    m = re.search(r"name '(\w+)' is not defined", texto)
    if m:
        return ('No existe la variable «%s». Revise la lista de variables o el '
                'código técnico del campo en el Catálogo de Campos.' % m.group(1))
    if 'division by zero' in texto:
        return 'División por cero.'
    m = re.search(r'^(\w+Error) : (.*) at line (\d+)\n(.*)', texto, re.S)
    if m:
        return 'Error de escritura en la línea %s (%s):\n%s' % (
            m.group(3), m.group(2), m.group(4).strip())
    return texto


_ASIGNA_RESULT = re.compile(r'(^|\n)\s*result\s*=(?!=)')
_MOSTRAR = ('telos', 'apertura', 'motorizado', 'ancho')


class SafraPanelTrack(models.AbstractModel):
    """Fórmula «Best Fit» de Panel Track (P19, archivo FORMULA FINAL).

    Calcula las configuraciones fabricables de un panel según ancho,
    traslape y total de telos: solo se ofrece el riel cuya cantidad de
    canales coincide EXACTAMENTE con los canales necesarios (sin canales
    sobrantes), con las dos excepciones de Riel Velcrado (unilateral de 7
    telos y extremos 6+6 en riel de 6 canales).
    """
    _name = 'safra.panel.track'
    _description = 'Fórmula Best Fit Panel Track'

    # Parámetros técnicos del documento del cliente. Se pueden sobrescribir
    # sin código con parámetros del sistema (ir.config_parameter):
    # safra.panel.rieles = "4,5,6" | safra.panel.ancho_telo_min |
    # safra.panel.ancho_telo_max | safra.panel.ancho_max
    RIELES = [4, 5, 6]
    ANCHO_TELO_MIN = 0.35
    ANCHO_TELO_MAX = 0.95
    ANCHO_MAX_PERSIANA = 8.0

    @api.model
    def _params(self, system=None):
        """Parámetros técnicos; Sprint 1.7: el ancho mínimo/máximo del telo
        del sistema (p. ej. Panel Duo 0,20–0,475 m) manda sobre el general."""
        get = self.env['ir.config_parameter'].sudo().get_param
        try:
            rieles = sorted(int(x) for x in (get('safra.panel.rieles') or '').split(',') if x.strip())
        except ValueError:
            rieles = []

        def _f(key, default):
            try:
                return float(get(key) or default)
            except ValueError:
                return default

        system = system.sudo() if system else None
        return {
            'rieles': rieles or list(self.RIELES),
            'telo_min': (system and system.panel_telo_min)
                        or _f('safra.panel.ancho_telo_min', self.ANCHO_TELO_MIN),
            'telo_max': (system and system.panel_telo_max)
                        or _f('safra.panel.ancho_telo_max', self.ANCHO_TELO_MAX),
            'persiana_max': _f('safra.panel.ancho_max', self.ANCHO_MAX_PERSIANA),
        }

    @api.model
    def compute_configs(self, ancho, traslape, total_telos, campos=None, system=None):
        """Configuraciones válidas para un total de telos dado.

        Devuelve [{canales, total_telos, telos_izquierda, telos_derecha,
        ancho_telo_m, ancho_telo_cm, codigo_apertura, tipo_apertura,
        codigo_condicion, condicion_especial}] (sección 28 del documento).
        """
        regla = self.env['safra.panel.combo.rule']._regla(system)
        max_telos = regla._max_telos() if regla else 0

        # Validaciones generales (sección 22). Revisión 10-nov: el rango del
        # telo, el ancho máximo y los rieles los decide la fórmula del Excel.
        if not ancho or ancho <= 0 or traslape < 0:
            return []
        if not total_telos or total_telos < 2 or total_telos > max_telos:
            return []
        try:
            ancho_telo = regla._ancho_telo(ancho, traslape, total_telos, campos)
        except Exception:
            _logger.warning('Fórmula de ancho de telo inválida', exc_info=True)
            ancho_telo = (ancho + (total_telos - 1) * traslape) / total_telos

        def row(canales, izq, der, cod_ap, nombre_ap, velcrado, telo_m=None):
            telo = telo_m if isinstance(telo_m, (int, float)) and not isinstance(telo_m, bool) else ancho_telo
            return dict(total_telos=total_telos,
                        ancho_telo_m=round(telo, 4),
                        ancho_telo_cm=round(telo * 100, 2),
                        canales=canales,
                        telos_izquierda=izq,
                        telos_derecha=der,
                        codigo_apertura=cod_ap,
                        tipo_apertura=nombre_ap,
                        codigo_condicion='riel_velcrado' if velcrado else 'estandar',
                        condicion_especial='Con Riel Velcrado' if velcrado else 'Configuración estándar')

        # Revisión 10-nov: las combinaciones salen de la fórmula del Excel de
        # Safra que se subió en la regla del sistema (hoja «Configurador»).
        resultados = []
        for fila in regla._filas(ancho, traslape, total_telos) if regla else []:
            codigo, _nombre = _FILA_APERTURA[fila['apertura']]
            resultados.append(row(fila['riel'], fila['izq'], fila['der'], codigo, fila['etiqueta'],
                                  fila['velcrado'], fila['telo_m']))
        return resultados

    @api.model
    def viable_width_range(self, traslape, telos=None, campos=None, system=None):
        """Rango de anchos que SÍ da combinaciones, para explicar el «sin
        configuraciones válidas» al cliente. Usa el mismo cálculo del
        portal (rieles y fórmulas del sistema) y, si el cliente digitó la
        cantidad de telos, solo esa cantidad. Devuelve {wmin, wmax, telos,
        telo_min, telo_max}, o {sin_riel: True, ...} si con esa cantidad no
        hay ninguna combinación posible."""
        p = self._params(system)
        regla = self.env['safra.panel.combo.rule']._regla(system)
        cantidades = [telos] if telos else (regla._cantidades() if regla else [])
        tope = int(math.floor(round(p['persiana_max'] * 100, 6)))

        def telo(cm, n):
            try:
                if regla:
                    return regla._ancho_telo(cm / 100.0, traslape, n, campos)
                return (cm / 100.0 + (n - 1) * traslape) / n
            except Exception:
                return None

        def primero(n, cond):
            # Búsqueda binaria: el ancho del telo crece con el de la persiana.
            lo, hi = 1, tope + 1
            while lo < hi:
                mid = (lo + hi) // 2
                v = telo(mid, n)
                if v is not None and cond(v):
                    hi = mid
                else:
                    lo = mid + 1
            return lo

        def sirve(cm, n):
            return bool(self.compute_configs(cm / 100.0, traslape, n, campos=campos, system=system))

        tramos = []
        for n in cantidades:
            # Tramo donde el telo queda en el rango; luego se confirma con el
            # cálculo real (rieles) y se ajustan los bordes al centímetro.
            a_cm = primero(n, lambda v: v >= p['telo_min'])
            b_cm = primero(n, lambda v: v > p['telo_max']) - 1
            if a_cm > b_cm or not sirve((a_cm + b_cm) // 2, n):
                continue
            for _i in range(3):
                if sirve(a_cm, n):
                    break
                a_cm += 1
            for _i in range(3):
                if sirve(b_cm, n):
                    break
                b_cm -= 1
            tramos.append((a_cm, b_cm))
        base = {'telo_min': p['telo_min'], 'telo_max': p['telo_max'], 'telos': telos or None}
        if not tramos:
            return dict(base, sin_riel=True)
        return dict(base, wmin=min(a for a, _b in tramos) / 100.0,
                    wmax=max(b for _a, b in tramos) / 100.0)

    @api.model
    def revisar_libre(self, ancho, traslape, telos, campos=None, system=None):
        """Correo de Safra (19-oct): la Apertura Libre no sale de la tabla de
        combinaciones, pero el cliente la puede escoger. Solo se revisa que
        cada telo quede entre el mínimo y el máximo y que la persiana no
        pase del ancho máximo; el riel no se restringe. Devuelve None si
        cumple, o el detalle para el mensaje."""
        p = self._params(system)
        max_telos = 2 * max(p['rieles'])
        if not ancho or not telos:
            return None
        regla = self.env['safra.panel.combo.rule']._regla(system)
        try:
            ancho_telo = (regla._ancho_telo(ancho, traslape, telos, campos) if regla
                          else (ancho + (telos - 1) * traslape) / telos)
        except Exception:
            ancho_telo = None
        cumple = (ancho_telo is not None and 2 <= telos <= max_telos
                  and ancho <= p['persiana_max']
                  and p['telo_min'] <= ancho_telo <= p['telo_max'])
        if cumple:
            return None
        return {'telo_cm': round((ancho_telo or 0) * 100, 2),
                'min_cm': round(p['telo_min'] * 100, 2), 'max_cm': round(p['telo_max'] * 100, 2),
                'ancho_max': p['persiana_max'], 'max_telos': max_telos}

    @api.model
    def suggest_configs(self, ancho, traslape, campos=None, system=None):
        """Tabla completa: todas las configuraciones válidas para el ancho
        digitado, recorriendo los totales de telos posibles."""
        regla = self.env['safra.panel.combo.rule']._regla(system)
        out = []
        for telos in (regla._cantidades() if regla else []):
            out.extend(self.compute_configs(ancho, traslape, telos, campos=campos, system=system))
        return out


# Aperturas de Panel Track → código de la fila del portal y nombre que se
# muestra. Centro y Extremos reparten mitad y mitad.
APERTURAS_PANEL = [
    ('derecha', 'Derecha'),
    ('izquierda', 'Izquierda'),
    ('centro', 'Centro'),
    ('extremos', 'Extremos'),
    ('libre', 'Apertura Libre'),
]
_FILA_APERTURA = {
    'derecha': ('unilateral_derecha', 'Unilateral Derecha'),
    'izquierda': ('unilateral_izquierda', 'Unilateral Izquierda'),
    'centro': ('centro', 'Apertura Centro'),
    'extremos': ('extremos', 'Apertura Extremos'),
    'libre': ('libre', 'Apertura Libre'),
}
FORMULA_ANCHO_TELO = '(ancho + (telos - 1) * traslape) / telos'
SIN_COMBINACION = 'Sin combinación'
ESTANDAR = 'Configuración estándar'
VELCRADO = 'Con Riel Velcrado'


def reparto(apertura, telos):
    """(telos a la izquierda, telos a la derecha) de la apertura; (None,
    None) en la Apertura Libre."""
    if apertura == 'derecha':
        return 0, telos
    if apertura == 'izquierda':
        return telos, 0
    if apertura in ('centro', 'extremos'):
        return telos // 2, telos // 2
    return None, None


# Revisión 10-nov: Safra mantiene la fórmula de combinaciones en su Excel
# (hoja «Configurador» de Panel_Track_Best_Fit_Odoo_CORREGIDO) y lo sube a
# Odoo; si cambia la fórmula, vuelve a subir el Excel.
EXCEL_INICIAL = 'website_quotes_safra/data/panel_track_best_fit.xlsx'
_APERTURA_TEXTO = re.compile(
    r'(derecha|izquierda|centro|extremos|libre)\D*(\d+)\s*\+\s*(\d+)')


def _sin_tildes(texto):
    texto = unicodedata.normalize('NFKD', str(texto or '')).encode('ascii', 'ignore').decode()
    return re.sub(r'\s+', ' ', texto.lower()).strip()


def _columnas_resultado(titulos):
    """{dato: posición} según los títulos de las columnas del resultado
    (Tipo Riel, Total Telos, Telos Izquierda, Telos Derecha, Ancho Telo (m),
    Tipo de Apertura, Observación)."""
    res = {}
    for n, titulo in enumerate(titulos):
        t = _sin_tildes(titulo)
        if not t:
            continue
        if 'riel' in t and 'riel' not in res:
            res['riel'] = n
        elif 'total' in t and 'telo' in t:
            res['telos'] = n
        elif 'izquierda' in t:
            res['izq'] = n
        elif 'derecha' in t:
            res['der'] = n
        elif 'apertura' in t:
            res['apertura'] = n
        elif 'observ' in t:
            res['observacion'] = n
        elif 'ancho' in t and 'telo' in t and '(m)' in t:
            res['telo_m'] = n
    return res


def _dato_de_entrada(etiqueta):
    """Qué dato del cotizador va en una celda de entrada, por su etiqueta
    (la celda de la izquierda): Ancho Panel (m), Tamaño Traslape (m),
    Número Telos."""
    t = _sin_tildes(etiqueta)
    if 'traslape' in t:
        return 'traslape'
    if 'telo' in t and 'ancho' not in t:
        return 'telos'
    if 'ancho' in t:
        return 'ancho'
    return None


class SafraPanelComboRule(models.Model):
    """Combinaciones de Panel Track. Revisión 10-nov: la fórmula es la del
    Excel de Safra, que Odoo calcula tal como la hoja «Configurador» (con el
    ancho, el traslape y los telos de la persiana). Una regla sirve a varios
    sistemas; un sistema con otra fórmula (p. ej. otro rango de telo) va en
    otra regla con su propio Excel."""
    _name = 'safra.panel.combo.rule'
    _description = 'Combinaciones de Panel Track'
    _order = 'id'

    name = fields.Char(string='Nombre', default='Panel Track')
    system_ids = fields.Many2many(
        'safra.system', 'safra_panel_combo_rule_system_rel', 'rule_id', 'system_id',
        string='Sistemas', required=True)
    active = fields.Boolean(string='Activa', default=True)
    formula_ancho_telo = fields.Text(
        string='Ancho de cada telo', required=True, default=FORMULA_ANCHO_TELO,
        help="Ancho de cada telo (m), para decirle al cliente entre qué anchos hay combinaciones.\n"
             "Variables: ancho, traslape (m) y telos.")
    telos_max = fields.Integer(
        string='Telos que se revisan (hasta)', default=12, required=True,
        help='El portal busca combinaciones de 2 telos hasta este número.')
    ofrecer_libre = fields.Boolean(
        string='Ofrecer Apertura Libre',
        help='La Apertura Libre no sale del Excel: no tiene riel fijo y solo se revisa el ancho de '
             'cada telo con los Parámetros.')
    excel_archivo = fields.Binary(string='Excel de combinaciones', attachment=True)
    excel_nombre = fields.Char(string='Nombre del archivo')
    excel_formula = fields.Text(string='Fórmula del Excel', readonly=True)
    excel_ubicacion = fields.Char(string='Celda de la fórmula', readonly=True)
    excel_entradas = fields.Json(string='Celdas de entrada', readonly=True)
    excel_columnas = fields.Json(string='Columnas del resultado', readonly=True)
    excel_entradas_texto = fields.Char(string='Datos que recibe', compute='_compute_excel_texto')
    matriz_html = fields.Html(string='Matriz resultante', compute='_compute_matriz_html', sanitize=False)

    @api.model
    def _regla(self, system=None):
        dominio = [('active', '=', True)]
        if system:
            dominio.append(('system_ids', 'in', system.id))
        return self.sudo().search(dominio, limit=1)

    def _ancho_telo(self, ancho, traslape, telos, campos=None):
        self.ensure_one()
        ctx = {'ancho': ancho, 'traslape': traslape, 'telos': telos, 'result': None}
        ctx.update(variables_formulario(campos, ctx))
        valor, _vars = evaluar_formula(self.formula_ancho_telo, ctx)
        return float(valor)

    # --- Excel ------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('excel_archivo'):
                vals.update(self._leer_excel(base64.b64decode(vals['excel_archivo'])))
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('excel_archivo'):
            vals = dict(vals, **self._leer_excel(base64.b64decode(vals['excel_archivo'])))
        elif 'excel_archivo' in vals:
            vals = dict(vals, excel_formula=False, excel_ubicacion=False, excel_entradas=False,
                        excel_columnas=False)
        return super().write(vals)

    @api.model
    def _leer_excel(self, contenido):
        """Busca en el Excel la fórmula que da las combinaciones (la que
        lleva los títulos Tipo Riel … Apertura encima) y sus celdas de
        entrada; la prueba de 2 a 12 telos. Si algo falla no se guarda y se
        dice qué corregir."""
        try:
            libro = openpyxl.load_workbook(io.BytesIO(contenido))
        except Exception:  # noqa: BLE001 — cualquier archivo que no sea un .xlsx
            raise UserError('El archivo no es un Excel (.xlsx) válido.') from None
        hojas = sorted(libro.worksheets, key=lambda h: 'configurador' not in _sin_tildes(h.title))
        problemas = []
        for hoja in hojas:
            for fila in hoja.iter_rows():
                for celda in fila:
                    valor = celda.value
                    texto = valor.text if isinstance(valor, ArrayFormula) else valor
                    if not (isinstance(texto, str) and texto.startswith('=') and 'FILTER' in texto.upper()):
                        continue
                    titulos = [hoja.cell(celda.row - 1, celda.column + n).value for n in range(12)] \
                        if celda.row > 1 else []
                    columnas = _columnas_resultado(titulos)
                    if not {'riel', 'apertura'} <= set(columnas):
                        problemas.append('%s!%s: encima de la fórmula deben ir los títulos «Tipo Riel» y '
                                         '«Tipo de Apertura».' % (hoja.title, celda.coordinate))
                        continue
                    try:
                        arbol = excel_formula.leer(texto)
                    except excel_formula.ErrorFormula as e:
                        problemas.append('%s!%s: %s' % (hoja.title, celda.coordinate, e))
                        continue
                    faltan = excel_formula.funciones(arbol) - set(excel_formula.Evaluador.FUNCIONES)
                    if faltan:
                        problemas.append('%s!%s: Odoo no calcula %s. Funciones que sí: %s.' % (
                            hoja.title, celda.coordinate, ', '.join(sorted(faltan)),
                            ', '.join(excel_formula.Evaluador.FUNCIONES)))
                        continue
                    entradas = {}
                    for ref in excel_formula.celdas(arbol):
                        col, num = openpyxl.utils.cell.coordinate_from_string(ref)
                        idx = openpyxl.utils.column_index_from_string(col)
                        etiqueta = hoja.cell(num, idx - 1).value if idx > 1 else ''
                        dato = _dato_de_entrada(etiqueta)
                        if not dato:
                            problemas.append('%s!%s: la fórmula usa la celda %s («%s» a su izquierda) y no '
                                             'se sabe qué dato es. Las entradas deben decir Ancho, '
                                             'Traslape o Número de telos.' % (
                                                 hoja.title, celda.coordinate, ref, etiqueta or 'vacía'))
                            break
                        entradas[dato] = ref
                    else:
                        if set(entradas) != {'ancho', 'traslape', 'telos'}:
                            problemas.append('%s!%s: la fórmula debe usar las celdas de Ancho, Traslape y '
                                             'Número de telos.' % (hoja.title, celda.coordinate))
                            continue
                        vals = {'excel_formula': texto, 'excel_entradas': entradas,
                                'excel_columnas': columnas,
                                'excel_ubicacion': "%s!%s" % (hoja.title, celda.coordinate)}
                        combinaciones = sum(len(self._calcular(vals, *muestra)) for muestra in self._muestras())
                        if not combinaciones:
                            problemas.append('%s!%s: la fórmula no da ninguna combinación de 2 a 12 telos.'
                                             % (hoja.title, celda.coordinate))
                            continue
                        return vals
        raise UserError('No se encontró en el Excel la fórmula de las combinaciones (una celda con '
                        'FILTER y encima los títulos Tipo Riel … Tipo de Apertura).%s' % (
                            ('\n\n' + '\n'.join(problemas)) if problemas else ''))

    @api.model
    def _muestras(self, telos_max=12):
        """(ancho, traslape, telos) de referencia para ver la matriz: un
        ancho con el que cada telo queda en la mitad del rango de los
        Parámetros (como la hoja «Matriz 2-12», sin filtro de ancho)."""
        p = self.env['safra.panel.track']._params()
        telo = (p['telo_min'] + p['telo_max']) / 2
        return [(round(n * telo - (n - 1) * 0.08, 4), 0.08, n) for n in range(2, telos_max + 1)]

    @api.model
    def _calcular(self, datos, ancho, traslape, telos):
        """Filas de la fórmula del Excel para una persiana: [{riel, apertura,
        izq, der, velcrado, etiqueta, telo_m}]. Las que no son una
        combinación (p. ej. «Sin combinaciones válidas») no cuentan."""
        formula, entradas, columnas = (datos.get('excel_formula'), datos.get('excel_entradas') or {},
                                       datos.get('excel_columnas') or {})
        if not formula:
            return []
        celdas = {entradas[k]: v for k, v in (('ancho', ancho), ('traslape', traslape), ('telos', telos))
                  if k in entradas}
        try:
            filas = excel_formula.calcular(excel_formula.leer(formula), celdas)
        except excel_formula.ErrorFormula as e:
            _logger.warning('Combinaciones: la fórmula del Excel falló (%s, %s, %s): %s',
                            ancho, traslape, telos, e)
            return []
        res = []
        for fila in filas:
            def dato(clave):
                n = columnas.get(clave)
                return fila[n] if n is not None and n < len(fila) else None
            m = _APERTURA_TEXTO.search(_sin_tildes(dato('apertura')))
            riel = dato('riel')
            if not m or not isinstance(riel, (int, float)) or isinstance(riel, bool):
                continue
            apertura, izq, der = m.group(1), int(m.group(2)), int(m.group(3))
            if apertura != 'libre' and izq + der != telos:
                continue
            res.append({'apertura': apertura, 'riel': int(riel), 'izq': izq, 'der': der,
                        'velcrado': 'velcr' in _sin_tildes(dato('observacion')),
                        'observacion': dato('observacion') or '', 'etiqueta': str(dato('apertura')),
                        'telo_m': dato('telo_m')})
        return res

    def _filas(self, ancho, traslape, telos):
        self.ensure_one()
        if not 2 <= telos <= self.telos_max:
            return []
        return self._calcular({'excel_formula': self.excel_formula, 'excel_entradas': self.excel_entradas,
                               'excel_columnas': self.excel_columnas}, ancho, traslape, telos)

    def _cantidades(self):
        """Cantidades de telos que dan alguna combinación (con un ancho de
        telo de referencia)."""
        self.ensure_one()
        return [n for a, t, n in self._muestras(self.telos_max) if self._filas(a, t, n)]

    def _max_telos(self):
        self.ensure_one()
        return self.telos_max

    def _aperturas(self):
        """Aperturas que se ofrecen en el portal: las que da el Excel y la
        Libre si está marcada."""
        self.ensure_one()
        usadas = {f['apertura'] for a, t, n in self._muestras(self.telos_max) for f in self._filas(a, t, n)}
        if self.ofrecer_libre:
            usadas.add('libre')
        return [_FILA_APERTURA[a][0] for a, _n in APERTURAS_PANEL if a in usadas]

    @api.depends('excel_entradas')
    def _compute_excel_texto(self):
        nombres = {'ancho': 'Ancho', 'traslape': 'Traslape', 'telos': 'Número de telos'}
        for rule in self:
            entradas = rule.excel_entradas or {}
            rule.excel_entradas_texto = ', '.join('%s → %s' % (nombres[k], entradas[k])
                                                  for k in ('ancho', 'traslape', 'telos') if k in entradas)

    @api.depends('excel_formula', 'excel_entradas', 'excel_columnas', 'telos_max')
    def _compute_matriz_html(self):
        """La matriz que da la fórmula de 2 telos al máximo, como la hoja
        «Matriz 2-12» del Excel de Safra, para comparar."""
        orden = [a for a, _n in APERTURAS_PANEL]
        for rule in self:
            if not rule.excel_formula:
                rule.matriz_html = Markup('<p class="text-muted mb-0">Suba el Excel de combinaciones.</p>')
                continue
            filas = []
            for ancho, traslape, telos in rule._muestras(max(rule.telos_max, 2)):
                combos = sorted(rule._filas(ancho, traslape, telos),
                                key=lambda f: (f['riel'], orden.index(f['apertura'])))
                if not combos:
                    filas.append(Markup('<tr class="text-muted"><td>%s</td><td>-</td><td>-</td><td>-</td>'
                                        '<td>Sin combinación</td><td>-</td></tr>') % telos)
                for f in combos:
                    filas.append(Markup('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>'
                                        '<td>%s</td></tr>') % (
                        telos, f['riel'], f['izq'], f['der'], f['etiqueta'], f['observacion']))
            rule.matriz_html = Markup(
                '<table class="table table-sm table-bordered w-auto mb-0"><thead><tr><th>Total telos</th>'
                '<th>Tipo riel</th><th>Telos izquierda</th><th>Telos derecha</th><th>Apertura</th>'
                '<th>Observación</th></tr></thead><tbody>%s</tbody></table>') % Markup('').join(filas)

    @api.constrains('formula_ancho_telo')
    def _check_formulas(self):
        """Revisión al guardar: se prueba con 2 a 12 telos, ancho 2,40 m y
        traslape 8 cm; si falla, no se guarda."""
        for rule in self:
            error = probar_formula(self.env, rule.formula_ancho_telo, [
                {'ancho': 2.4, 'traslape': 0.08, 'telos': n, 'result': None}
                for n in range(2, 13)])
            if error:
                raise ValidationError('La fórmula del ancho de cada telo tiene un error:\n%s' % error)

    @api.constrains('telos_max')
    def _check_telos_max(self):
        for rule in self:
            if not 2 <= rule.telos_max <= 40:
                raise ValidationError('Los telos que se revisan deben ir de 2 a 40.')

    @api.model
    def _ajuste_excel_combinaciones(self, _ids=None):
        """Revisión 10-nov, una sola vez por base: las reglas sin Excel
        reciben el de Safra (Panel_Track_Best_Fit_Odoo_CORREGIDO)."""
        with file_open(EXCEL_INICIAL, 'rb') as archivo:
            contenido = base64.b64encode(archivo.read())
        for rule in self.sudo().with_context(active_test=False).search([('excel_formula', '=', False)]):
            rule.write({'excel_archivo': contenido, 'excel_nombre': 'Panel_Track_Best_Fit_Odoo_CORREGIDO.xlsx'})


class SafraLamasRule(models.Model):
    """Máximo total de lamas/pantógrafos (revisión 17-sep, matriz col.
    Vertical/Vintage/Vintage Std, fila «Máximo total lamas»).

    Total = (Ancho real − Aux) / Divisor + Adicional, con Aux/Adicional
    según la apertura y el accionamiento; en apertura Extremos el
    resultado se redondea a número PAR. Vintage Estándar divide el total
    manual entre 2. Todo configurable por registro, sin código.
    """
    _name = 'safra.lamas.rule'
    _description = 'Fórmula de máximo total de lamas'
    _order = 'id'

    # Apunte 23-sep: UNA fórmula puede cubrir varios sistemas y todas las
    # aperturas/accionamientos — el código decide qué partes aplican.
    system_ids = fields.Many2many(
        'safra.system', 'safra_lamas_rule_system_rel', 'rule_id', 'system_id',
        string='Sistemas', required=True)
    drive_type = fields.Selection([
        ('any', 'Ambos'),
        ('manual', 'Manual'),
        ('motor', 'Motorizado'),
    ], string='Accionamiento', required=True, default='any')
    apertura = fields.Selection([
        ('any', 'Todas'),
        ('extremos', 'Extremos'),
        ('centro', 'Centro'),
        ('izquierda', 'Izquierda'),
        ('derecha', 'Derecha'),
    ], string='Apertura', required=True, default='any')
    aux = FloatVacio(string='Aux (m)', digits=(8, 3))
    divisor = fields.Float(
        string='Divisor (m)', required=True, digits=(8, 3),
        help='Ancho de tela menos traslape; constante modificable.')
    adicional = FloatVacio(string='Adicional', digits=(6, 1))
    # Ayudas (09-nov): cada casilla con la función de Excel que equivale,
    # según el Excel de Safra CALCULO PANTOGRAFOS (hoja «MAX T LAMAS»).
    dividir_2 = fields.Boolean(
        string='Dividir entre 2',
        help='Divide el total entre 2 antes de redondear.\n'
             'En Excel: el «/2» del final de la fórmula, como en Vintage Sencilla: '
             '=(((ancho - aux) / 0,106) + adicional) / 2 (celdas C23 e I30 de CALCULO PANTOGRAFOS).\n'
             'No se marca si la Fórmula (código) ya termina en / 2: dividiría dos veces.')
    round_even = fields.Boolean(
        string='Redondear a par (Extremos)',
        help='Solo en apertura Extremos, el resultado sube al siguiente número par.\n'
             'En Excel: REDONDEA.PAR (EVEN en Excel en inglés), como las celdas N19 (Vintage) '
             'y N30 (Vintage Sencilla) de CALCULO PANTOGRAFOS. Ejemplos: 18,38 → 20; 9,62 → 10; 22 → 22.\n'
             'Las demás aperturas usan el redondeo normal.\n'
             'Sin ninguna de las dos casillas de par, todas las aperturas redondean normal: '
             'en Excel REDONDEAR(x; 0) (ROUND en inglés), de ,5 para arriba sube: 37,375 → 37; 37,5 → 38.')
    # Correo del 19-oct (CALCULO PANTOGRAFOS): en Vintage Sencilla los
    # pantógrafos siempre son par hacia arriba, sin importar la apertura.
    round_even_all = fields.Boolean(
        string='Redondear a par (todas las aperturas)',
        help='El resultado sube al siguiente número par en todas las aperturas.\n'
             'En Excel: REDONDEA.PAR (EVEN en Excel en inglés) en la celda del resultado de cada '
             'apertura. Ejemplos: 18,38 → 20; 9,23 → 10.\n'
             'Hoy ninguna celda de CALCULO PANTOGRAFOS lo hace (solo lo menciona la nota de C28 '
             'de Vintage Sencilla).\n'
             'Si está marcada, no hace falta marcar «Redondear a par (Extremos)».')
    active = fields.Boolean(default=True)
    # Apunte 23-sep (estilo reglas salariales de nómina): fórmula libre en
    # Python. Si se escribe, REEMPLAZA el cálculo estándar; el redondeo (a
    # par si aplica) se hace después sobre el resultado.
    formula_code = fields.Text(
        string='Fórmula (código)',
        help="Expresión de una línea que devuelve el total ANTES del\n"
             "redondeo, o bloque de varias líneas que asigna result.\n"
             "Variables disponibles:\n"
             "  ancho      → ancho real digitado (m)\n"
             "  aux, divisor, adicional → constantes de esta regla\n"
             "  apertura   → 'extremos'/'centro'/'izquierda'/'derecha'\n"
             "  motorizado → True/False\n"
             "  y cualquier campo del cotizador por su código técnico\n"
             "  (p. ej. height, quantity_lamas)\n"
             "Ejemplo: (ancho - aux) / divisor + adicional\n"
             "Vacío = fórmula estándar con las constantes.")

    @api.model
    def _migrate_unified_rules(self, _ids=None):
        """Apunte 23-sep: el esquema pasó de una regla por sistema x
        apertura x accionamiento a UNA fórmula por sistema (el código
        decide las partes). Las reglas viejas quedan sin sistemas tras el
        cambio de campo y se retiran. Idempotente."""
        self.with_context(active_test=False).search(
            [('system_ids', '=', False)]).unlink()

    @api.model
    def _seed_formula_codes(self, _ids=None):
        """Apunte 23-sep: la fórmula de la matriz queda VISIBLE como código
        en cada regla (misma expresión del archivo, con las variables):
        Total = (Ancho − Aux) / Divisor + Adicional. Las constantes de la
        regla siguen alimentando el cálculo; idempotente y respetando lo
        que el funcional edite."""
        vacias = self.with_context(active_test=False).search(
            [('formula_code', '=', False)])
        vacias.write({'formula_code': '(ancho - aux) / divisor + adicional'})

    def _ctx_base(self, ancho, apertura, motorizado):
        self.ensure_one()
        return {'ancho': ancho, 'aux': self.aux, 'divisor': self.divisor,
                'adicional': self.adicional, 'apertura': apertura,
                'motorizado': bool(motorizado), 'result': None}

    @api.constrains('formula_code', 'aux', 'divisor', 'adicional')
    def _check_formula_code(self):
        """Revisión al guardar: la fórmula se prueba con las cuatro
        aperturas, manual y motorizada, con anchos de 1 y 3 m."""
        for rule in self:
            contextos = [rule._ctx_base(w, ap, mot)
                         for w in (1.0, 3.0)
                         for ap in ('extremos', 'centro', 'izquierda', 'derecha')
                         for mot in (False, True)]
            error = probar_formula(self.env, rule.formula_code, contextos)
            if error:
                raise ValidationError('La fórmula del máximo de lamas tiene un error:\n%s' % error)

    @api.model
    def _regla_max(self, system, apertura, motorized=False):
        """Regla de lamas que aplica: la más específica (apertura y
        accionamiento concretos antes que «Todas»/«Ambos»)."""
        if not system or not apertura:
            return self.browse()
        drive = 'motor' if motorized else 'manual'
        rules = self.search([
            ('system_ids', 'in', system.id),
            ('apertura', 'in', ['any', apertura]),
            ('drive_type', 'in', ['any', drive]),
        ])
        if not rules:
            return rules
        return max(rules, key=lambda r: (r.apertura != 'any') + (r.drive_type != 'any'))

    @api.model
    def compute_max(self, system, width, apertura, motorized=False, campos=None):
        """Máximo de lamas para el sistema/ancho/apertura, o None si el
        sistema no tiene fórmula configurada."""
        if not system or not width or not apertura:
            return None
        rule = self._regla_max(system, apertura, motorized)
        if not rule:
            return None
        if rule.formula_code:
            try:
                ctx = rule._ctx_base(width, apertura, motorized)
                ctx.update(variables_formulario(campos, ctx))
                total, _vars = evaluar_formula(rule.formula_code, ctx)
                if total is None:
                    return None
                total = float(total)
            except Exception:
                return None
        else:
            if not rule.divisor:
                return None
            total = (width - rule.aux) / rule.divisor + rule.adicional
        if rule.dividir_2:
            total = total / 2.0
        if rule.round_even_all or (rule.round_even and apertura == 'extremos'):
            n = _par_hacia_arriba(total)
        else:
            n = _redondeo_excel(total)
        return max(n, 0)

    # Correo de Safra del 19-oct (CALCULO PANTOGRAFOS): fórmula por sistema,
    # la misma con o sin motor. Vintage divide entre 0,106 (antes 1,106).
    FORMULAS_PANTOGRAFOS = {
        'website_quotes_safra.lru_vertical': {
            'divisor': 0.08, 'round_even': True, 'round_even_all': False,
            'formula_code': "(ancho - {'extremos': 0.132, 'centro': 0, 'izquierda': 0.09, "
                            "'derecha': 0.09}[apertura]) / divisor + {'extremos': 2, "
                            "'centro': 0, 'izquierda': 1, 'derecha': 1}[apertura]",
        },
        'website_quotes_safra.lru_vintage': {
            'divisor': 0.106, 'round_even': True, 'round_even_all': False,
            'formula_code': "(ancho - {'extremos': 0.172, 'centro': 0.164, 'izquierda': 0.150, "
                            "'derecha': 0.150}[apertura]) / divisor + {'extremos': 0, "
                            "'centro': 0, 'izquierda': 0, 'derecha': 0}[apertura]",
        },
        # Mejoras Sprint 1.1 (21-oct, fila 18): como el Excel de Safra, el par
        # solo en extremos (2,00 m: 9 lamas a un lado y al centro, 10 extremos).
        'website_quotes_safra.lru_vintage_std': {
            'divisor': 0.106, 'round_even': True, 'round_even_all': False,
            'formula_code': "((ancho - {'extremos': 0.172, 'centro': 0.164, 'izquierda': 0.150, "
                            "'derecha': 0.150}[apertura]) / divisor + {'extremos': 2, "
                            "'centro': 1, 'izquierda': 1, 'derecha': 1}[apertura]) / 2",
        },
    }

    @api.model
    def _aplicar_casos_pantografos(self, _ids=None):
        """Una sola vez por base: las reglas de Vertical, Vintage y Vintage
        Sencilla toman las fórmulas del archivo de Safra, y se archivan las
        demás reglas activas de esos sistemas (p. ej. una regla aparte para
        Derecha), que mandarían sobre la general."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.pantografos_1910'
        if Param.get_param(marca):
            return
        for xmlid, vals in self.FORMULAS_PANTOGRAFOS.items():
            rule = self.env.ref(xmlid, raise_if_not_found=False)
            if not rule:
                continue
            rule = rule.sudo().with_context(active_test=False)
            rule.write(dict(vals, active=True, apertura='any', drive_type='any',
                            aux=0.0, adicional=0.0, dividir_2=False))
            self.sudo().search([('id', '!=', rule.id),
                                ('system_ids', 'in', rule.system_ids.ids)]).write({'active': False})
        Param.set_param(marca, '1')
