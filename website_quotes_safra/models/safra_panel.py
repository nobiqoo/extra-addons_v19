# -*- coding: utf-8 -*-
import logging
import math
import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval, test_python_expr

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


def evaluar_formula(codigo, ctx):
    """Fórmulas al estilo de las reglas salariales de nómina: una expresión
    de una línea devuelve su valor; un bloque de varias líneas asigna
    `result` (y, si aplica, otras variables como `velcrado`). Devuelve
    (valor, variables del bloque). Lanza la excepción si el código falla."""
    codigo = (codigo or '').strip()
    if not codigo:
        return None, {}
    local = dict(ctx)
    if not test_python_expr(codigo, mode='eval'):
        return safe_eval(codigo, local), local
    safe_eval(codigo, local, mode='exec')
    return local.get('result'), local


def _campos_en_cero(env):
    return {c: 0 for c in env['safra.field'].sudo().with_context(
        active_test=False).search([]).mapped('code') if c}


def probar_formula(env, codigo, contextos, ignorar=None):
    """Revisión al guardar: compila el código y lo ejecuta con contextos de
    ejemplo (todos los campos del cotizador valen 0). Devuelve el mensaje
    del primer error o False si la fórmula funciona."""
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
    campos = _campos_en_cero(env)
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
    def _params(self):
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

        return {
            'rieles': rieles or list(self.RIELES),
            'telo_min': _f('safra.panel.ancho_telo_min', self.ANCHO_TELO_MIN),
            'telo_max': _f('safra.panel.ancho_telo_max', self.ANCHO_TELO_MAX),
            'persiana_max': _f('safra.panel.ancho_max', self.ANCHO_MAX_PERSIANA),
        }

    @api.model
    def compute_configs(self, ancho, traslape, total_telos, campos=None, system=None):
        """Configuraciones válidas para un total de telos dado.

        Devuelve [{canales, total_telos, telos_izquierda, telos_derecha,
        ancho_telo_m, ancho_telo_cm, codigo_apertura, tipo_apertura,
        codigo_condicion, condicion_especial}] (sección 28 del documento).
        """
        p = self._params()
        rieles = p['rieles']
        max_telos = 2 * max(rieles)

        # Validaciones generales (sección 22)
        if not ancho or ancho <= 0 or ancho > p['persiana_max']:
            return []
        if traslape < 0:
            return []
        if not total_telos or total_telos < 2 or total_telos > max_telos:
            return []

        # Ancho de cada telo (sección 11): fórmula de la regla del sistema
        regla = self.env['safra.panel.combo.rule']._regla(system)
        try:
            ancho_telo = (regla._ancho_telo(ancho, traslape, total_telos, campos) if regla
                          else (ancho + (total_telos - 1) * traslape) / total_telos)
        except Exception:
            _logger.warning('Fórmula de ancho de telo inválida', exc_info=True)
            return []
        if not (p['telo_min'] <= ancho_telo <= p['telo_max']):
            return []

        base = {
            'total_telos': total_telos,
            'ancho_telo_m': round(ancho_telo, 4),
            'ancho_telo_cm': round(ancho_telo * 100, 2),
        }

        def row(canales, izq, der, cod_ap, nombre_ap, velcrado):
            return dict(base,
                        canales=canales,
                        telos_izquierda=izq,
                        telos_derecha=der,
                        codigo_apertura=cod_ap,
                        tipo_apertura=nombre_ap,
                        codigo_condicion='riel_velcrado' if velcrado else 'estandar',
                        condicion_especial='Con Riel Velcrado' if velcrado else 'Configuración estándar')

        resultados = []

        # Reunión 28-sep (fila 16) / revisión 09-oct: las combinaciones
        # salen SOLO de la fórmula del sistema, escrita como la del Máximo
        # de lamas (la apertura es una variable). La fórmula del documento
        # queda como respaldo si el sistema no tiene regla.
        regla = self.env['safra.panel.combo.rule']._regla(system)
        if regla:
            lado = total_telos // 2
            for apertura, _nombre in APERTURAS_PANEL:
                par = apertura in ('centro', 'extremos')
                if par and total_telos % 2:
                    continue
                ctx = regla._ctx_base(total_telos, apertura, ancho, traslape, rieles)
                ctx.update(variables_formulario(campos, ctx))
                canales, ofrecida = regla._canales(ctx, apertura)
                if not ofrecida:
                    continue
                riel_vel = regla._velcrado(apertura, total_telos)
                velcrado = bool(riel_vel)
                if velcrado:
                    canales = riel_vel
                if not canales or canales not in rieles:
                    continue
                codigo, nombre = _FILA_APERTURA[apertura]
                izq, der = {'derecha': (0, total_telos), 'izquierda': (total_telos, 0)}.get(
                    apertura, (lado, lado) if par else (None, None))
                etiqueta = ('%s %d+%d' % (nombre, izq, der)) if izq is not None else (
                    '%s (%d telos)' % (nombre, total_telos))
                resultados.append(row(canales, izq, der, codigo, etiqueta, velcrado))
            return resultados

        # Unilateral (sección 19.1): canales = telos; excepción 7 telos →
        # riel de 6 canales con Riel Velcrado.
        es_velcrado_uni = total_telos == 7
        canales_uni = 6 if es_velcrado_uni else total_telos
        if canales_uni in rieles:
            resultados.append(row(
                canales_uni, 0, total_telos, 'unilateral_derecha',
                'Unilateral Derecha 0+%d' % total_telos, es_velcrado_uni))
            resultados.append(row(
                canales_uni, total_telos, 0, 'unilateral_izquierda',
                'Unilateral Izquierda %d+0' % total_telos, es_velcrado_uni))

        # Centro y Extremos: solo distribución equilibrada (secciones 19.2/19.3)
        if total_telos % 2 == 0:
            lado = total_telos // 2
            # Centro: canales = telos + 1, coincidencia exacta
            if total_telos + 1 in rieles:
                resultados.append(row(
                    total_telos + 1, lado, lado, 'centro',
                    'Apertura Centro %d+%d' % (lado, lado), False))
            # Extremos: canales = lado + 1; excepción 6+6 → riel 6 Velcrado
            es_velcrado_ext = total_telos == 2 * max(rieles)
            canales_ext = max(rieles) if es_velcrado_ext else lado + 1
            if canales_ext in rieles:
                resultados.append(row(
                    canales_ext, lado, lado, 'extremos',
                    'Apertura Extremos %d+%d' % (lado, lado), es_velcrado_ext))

        return resultados

    @api.model
    def viable_width_range(self, traslape, telos=None, campos=None, system=None):
        """Rango de anchos que SÍ da combinaciones, para explicar el «sin
        configuraciones válidas» al cliente. Usa el mismo cálculo del
        portal (rieles y fórmulas del sistema) y, si el cliente digitó la
        cantidad de telos, solo esa cantidad. Devuelve {wmin, wmax, telos,
        telo_min, telo_max}, o {sin_riel: True, ...} si con esa cantidad no
        hay ninguna combinación posible."""
        p = self._params()
        cantidades = [telos] if telos else list(range(2, 2 * max(p['rieles']) + 1))
        regla = self.env['safra.panel.combo.rule']._regla(system)
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
    def suggest_configs(self, ancho, traslape, campos=None, system=None):
        """Tabla completa: todas las configuraciones válidas para el ancho
        digitado, recorriendo los totales de telos posibles."""
        p = self._params()
        out = []
        for telos in range(2, 2 * max(p['rieles']) + 1):
            out.extend(self.compute_configs(ancho, traslape, telos, campos=campos, system=system))
        return out


# Aperturas de Panel Track: valor de la variable `apertura` en la fórmula
# (los mismos nombres del Máximo de lamas) → código de la fila del portal y
# nombre que se muestra. Centro y Extremos reparten mitad y mitad.
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
FORMULA_CANALES = (
    "telos * {'derecha': 1, 'izquierda': 1, 'centro': 1, 'extremos': 0.5}[apertura]"
    " + {'derecha': 0, 'izquierda': 0, 'centro': 1, 'extremos': 1}[apertura]")


def _apertura_ausente(error, apertura):
    """La fórmula no tiene valor para esta apertura (KeyError del
    diccionario): esa apertura simplemente no se ofrece."""
    causa = error
    while causa is not None:
        if isinstance(causa, KeyError) and causa.args and causa.args[0] == apertura:
            return True
        causa = causa.__context__
    return False


class SafraPanelComboRule(models.Model):
    """Reunión 28-sep (fila 16) y revisión con Jorge (09-oct): las
    combinaciones de Panel Track salen de UNA fórmula por sistema, escrita
    como la del Máximo de lamas — la apertura es una variable y un
    diccionario da el valor de cada una. Lo que no es fórmula (Riel
    Velcrado) va en una tabla."""
    _name = 'safra.panel.combo.rule'
    _description = 'Fórmula de combinaciones de Panel Track'
    _order = 'id'

    system_ids = fields.Many2many(
        'safra.system', 'safra_panel_combo_rule_system_rel', 'rule_id', 'system_id',
        string='Sistemas', required=True)
    active = fields.Boolean(default=True)
    formula_ancho_telo = fields.Text(
        string='Ancho de cada telo', required=True, default=FORMULA_ANCHO_TELO,
        help="Ancho de cada telo (m) para una cantidad de telos. Variables:\n"
             "ancho, traslape (m) y telos.")
    formula_canales = fields.Text(
        string='Canales de riel', required=True, default=FORMULA_CANALES,
        help="Canales de riel que necesita cada apertura. Variables: telos,\n"
             "lado (telos ÷ 2), apertura ('derecha', 'izquierda', 'centro',\n"
             "'extremos', 'libre'), ancho, traslape, max_riel, rieles y\n"
             "cualquier campo del cotizador por su código técnico.\n"
             "Una apertura que no esté en la fórmula no se ofrece.")
    velcrado_ids = fields.One2many(
        'safra.panel.combo.velcrado', 'rule_id', string='Riel Velcrado')

    @api.model
    def _regla(self, system=None):
        dominio = [('active', '=', True)]
        if system:
            dominio.append(('system_ids', 'in', system.id))
        return self.sudo().search(dominio, limit=1)

    @api.model
    def _ctx_base(self, telos, apertura, ancho, traslape, rieles):
        return {'telos': telos, 'lado': telos // 2, 'apertura': apertura,
                'ancho': ancho, 'traslape': traslape,
                'max_riel': max(rieles), 'rieles': list(rieles),
                'result': None}

    def _ancho_telo(self, ancho, traslape, telos, campos=None):
        self.ensure_one()
        ctx = {'ancho': ancho, 'traslape': traslape, 'telos': telos, 'result': None}
        ctx.update(variables_formulario(campos, ctx))
        valor, _vars = evaluar_formula(self.formula_ancho_telo, ctx)
        return float(valor)

    def _canales(self, ctx, apertura):
        """(canales, ofrecida). Sin valor para la apertura en la fórmula →
        no se ofrece; con un error, tampoco (queda en el log)."""
        self.ensure_one()
        try:
            valor, _vars = evaluar_formula(self.formula_canales, ctx)
        except Exception as e:
            if not _apertura_ausente(e, apertura):
                _logger.warning('Fórmula de canales inválida (%s)', apertura, exc_info=True)
            return None, False
        if valor is None or isinstance(valor, bool):
            return None, True
        valor = float(valor)
        if abs(valor - round(valor)) > 1e-9:
            return None, True
        return int(round(valor)), True

    def _velcrado(self, apertura, telos):
        self.ensure_one()
        fila = self.velcrado_ids.filtered(
            lambda v: v.apertura == apertura and v.telos == telos)[:1]
        return fila.riel or None

    def _aperturas(self):
        """Aperturas que tienen valor en la fórmula (las demás no se
        muestran en el portal)."""
        self.ensure_one()
        rieles = self.env['safra.panel.track']._params()['rieles']
        campos = _campos_en_cero(self.env)
        out = []
        for apertura, _nombre in APERTURAS_PANEL:
            for telos in (4, 6):
                ctx = self._ctx_base(telos, apertura, 2.4, 0.08, rieles)
                ctx.update(variables_formulario(campos, ctx))
                _can, ofrecida = self._canales(ctx, apertura)
                if ofrecida:
                    out.append(_FILA_APERTURA[apertura][0])
                    break
        return out

    @api.constrains('formula_ancho_telo', 'formula_canales')
    def _check_formulas(self):
        """Revisión al guardar: se prueban con 2 a 12 telos, ancho 2,40 m,
        traslape 8 cm y cada apertura; si fallan, no se guarda."""
        rieles = self.env['safra.panel.track']._params()['rieles']
        telos_prueba = range(2, 2 * max(rieles) + 1)
        for rule in self:
            error = probar_formula(self.env, rule.formula_ancho_telo, [
                {'ancho': 2.4, 'traslape': 0.08, 'telos': n, 'result': None}
                for n in telos_prueba])
            if error:
                raise ValidationError('La fórmula del ancho de cada telo tiene un error:\n%s' % error)
            for apertura, nombre in APERTURAS_PANEL:
                contextos = [rule._ctx_base(n, apertura, 2.4, 0.08, rieles) for n in telos_prueba]
                error = probar_formula(self.env, rule.formula_canales, contextos,
                                       ignorar=lambda e, ap=apertura: _apertura_ausente(e, ap))
                if error:
                    raise ValidationError('La fórmula de canales tiene un error con la apertura %s:\n%s' % (
                        nombre, error))
            if not rule._aperturas():
                raise ValidationError('La fórmula de canales no da valor para ninguna apertura.')

    @api.model
    def _migrar_desde_tipos(self, _ids=None):
        """Una sola vez: si existía la tabla de tipos de reparto (una fórmula
        por apertura) con fórmulas editadas, se arma la fórmula única con
        esas mismas expresiones para no cambiar el resultado."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.combos_formula_unica'
        if Param.get_param(marca):
            return
        Param.set_param(marca, '1')
        self.env.cr.execute("SELECT to_regclass('safra_panel_combo_tipo')")
        if not self.env.cr.fetchone()[0]:
            return
        self.env.cr.execute("""SELECT code, formula_canales, formula_velcrado, active
                                 FROM safra_panel_combo_tipo""")
        tipos = {code: (canales, velcrado, active)
                 for code, canales, velcrado, active in self.env.cr.fetchall()}
        # Los registros sembrados del modelo retirado ya no se usan.
        self.env.cr.execute("DELETE FROM ir_model_data WHERE model = 'safra.panel.combo.tipo'")
        originales = {
            'unilateral_derecha': ('telos', '6 if telos == 7 else None'),
            'unilateral_izquierda': ('telos', '6 if telos == 7 else None'),
            'centro': ('telos + 1', None),
            'extremos': ('lado + 1', 'max_riel if telos == 2 * max_riel else None'),
        }
        sin_cambios = all(
            code in tipos and tipos[code][2]
            and (tipos[code][0] or '').strip() == canales
            and ((tipos[code][1] or '').strip() or None) == velcrado
            for code, (canales, velcrado) in originales.items()
        ) and set(tipos) == set(originales)
        if sin_cambios:
            self._borrar_tabla_tipos()
            return
        partes = []
        for apertura, _nombre in APERTURAS_PANEL:
            code = _FILA_APERTURA[apertura][0]
            canales, velcrado, active = tipos.get(code, (None, None, False))
            if not active or not (canales or '').strip() or '\n' in canales.strip():
                continue
            partes.append("'%s': (%s)" % (apertura, canales.strip()))
            if (velcrado or '').strip() and velcrado.strip() != originales.get(code, ('', ''))[1]:
                _logger.warning('Excepción Velcrado editada en %s no migrada: %s', code, velcrado)
        if partes:
            for rule in self.with_context(active_test=False).search([]):
                rule.formula_canales = '{%s}[apertura]' % ', '.join(partes)
        self._borrar_tabla_tipos()

    @api.model
    def _borrar_tabla_tipos(self):
        # Odoo retira el modelo pero deja su tabla: ya se leyó, se borra.
        self.env.cr.execute('DROP TABLE IF EXISTS safra_panel_combo_tipo')


class SafraPanelComboVelcrado(models.Model):
    """Excepciones de Riel Velcrado del documento FORMULA FINAL: con esa
    apertura y esa cantidad de telos se usa ese riel, pegando con velcro."""
    _name = 'safra.panel.combo.velcrado'
    _description = 'Excepción Riel Velcrado de Panel Track'
    _order = 'apertura, telos'

    rule_id = fields.Many2one('safra.panel.combo.rule', required=True, ondelete='cascade')
    apertura = fields.Selection(APERTURAS_PANEL, string='Apertura', required=True)
    telos = fields.Integer(string='Telos', required=True)
    riel = fields.Integer(string='Riel (canales)', required=True)

    _velcrado_uniq = models.Constraint(
        'UNIQUE(rule_id, apertura, telos)', 'Ya hay una excepción para esa apertura y cantidad de telos.')

    @api.constrains('telos', 'riel')
    def _check_valores(self):
        for fila in self:
            if fila.telos < 2 or fila.riel < 1:
                raise ValidationError('En Riel Velcrado, los telos deben ser 2 o más y el riel 1 o más.')


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
    aux = fields.Float(string='Aux (m)', digits=(8, 3))
    divisor = fields.Float(
        string='Divisor (m)', required=True, digits=(8, 3),
        help='Ancho de tela menos traslape; constante modificable.')
    adicional = fields.Float(string='Adicional', digits=(6, 1))
    dividir_2 = fields.Boolean(
        string='Dividir entre 2', help='Vintage Estándar: el total manual se divide entre 2.')
    round_even = fields.Boolean(
        string='Redondear a par (Extremos)',
        help='En apertura Extremos el resultado se redondea a número par '
             '(regla de la matriz); las demás aperturas redondean normal.')
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
    def compute_max(self, system, width, apertura, motorized=False, campos=None):
        """Máximo de lamas para el sistema/ancho/apertura, o None si el
        sistema no tiene fórmula configurada."""
        if not system or not width or not apertura:
            return None
        drive = 'motor' if motorized else 'manual'
        rules = self.search([
            ('system_ids', 'in', system.id),
            ('apertura', 'in', ['any', apertura]),
            ('drive_type', 'in', ['any', drive]),
        ])
        if not rules:
            return None
        # La regla más específica gana (apertura y accionamiento concretos
        # antes que «Todas»/«Ambos»).
        rule = max(rules, key=lambda r: (r.apertura != 'any') + (r.drive_type != 'any'))
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
        n = int(round(total))
        if rule.round_even and apertura == 'extremos' and n % 2:
            n += 1
        return max(n, 0)
