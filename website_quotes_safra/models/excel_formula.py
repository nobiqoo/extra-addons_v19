# -*- coding: utf-8 -*-
"""Evaluador de fórmulas de Excel (revisión 10-nov, combinaciones de Panel
Track): Safra mantiene la fórmula en su Excel y lo sube; Odoo la calcula
igual que la hoja «Configurador», sin traducirla a código.

Soporta lo que usan las fórmulas de Safra: LET, SEQUENCE, FILTER, CHOOSE, IF,
IFERROR, AND, OR, NOT, INT, MOD, ROUND, ROUNDUP, ROUNDDOWN, ABS, MIN, MAX,
SUM, números, textos, referencias a celdas de entrada, operaciones
(+ - * / ^ &, comparaciones) y matrices (como las «matrices dinámicas» de
Excel 365). Una función que no esté aquí se avisa al subir el archivo.
"""
import functools
import math
import re
from decimal import ROUND_HALF_UP, Decimal


class ErrorFormula(Exception):
    """La fórmula no se puede leer o calcular (mensaje para el funcional)."""


_PREFIJOS = re.compile(r'_xl(?:fn|pm|ws)\.', re.IGNORECASE)
_TOKEN = re.compile(r'''
    (?P<espacio>\s+)
  | (?P<texto>"(?:[^"]|"")*")
  | (?P<numero>\d+(?:\.\d*)?(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)
  | (?P<celda>\$?[A-Za-z]{1,3}\$?\d+(?![\w.(]))
  | (?P<nombre>[A-Za-z_\\][\w.]*)
  | (?P<op><>|<=|>=|[-+*/^&=<>%])
  | (?P<signo>[(),;{}])
''', re.VERBOSE)


def limpiar(formula):
    """Quita el «=» inicial y los prefijos que Excel guarda en el archivo
    (_xlfn.LET, _xlpm.ancho, _xlfn._xlws.FILTER)."""
    texto = (formula or '').strip()
    if texto.startswith('='):
        texto = texto[1:]
    return _PREFIJOS.sub('', texto)


def tokens(formula):
    res, pos = [], 0
    while pos < len(formula):
        m = _TOKEN.match(formula, pos)
        if not m:
            raise ErrorFormula('No se entiende la fórmula cerca de «%s».' % formula[pos:pos + 20])
        pos = m.end()
        tipo = m.lastgroup
        if tipo == 'espacio':
            continue
        valor = m.group()
        if tipo == 'texto':
            valor = valor[1:-1].replace('""', '"')
        elif tipo == 'numero':
            valor = float(valor)
        elif tipo == 'celda':
            valor = valor.replace('$', '').upper()
        elif tipo == 'signo' and valor == ';':
            valor = ','
        res.append((tipo, valor))
    return res


# --- Árbol --------------------------------------------------------------

class _Parser:
    """Precedencia de Excel: comparación < & < + - < * / < ^ < signo < %."""

    def __init__(self, formula):
        self.t = tokens(limpiar(formula))
        self.i = 0

    def ver(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def tomar(self, esperado=None):
        tok = self.ver()
        if esperado is not None and tok[1] != esperado:
            raise ErrorFormula('Se esperaba «%s» en la fórmula y vino «%s».' % (esperado, tok[1] or 'el final'))
        self.i += 1
        return tok

    def todo(self):
        nodo = self.comparacion()
        if self.i != len(self.t):
            raise ErrorFormula('Sobra «%s» al final de la fórmula.' % self.ver()[1])
        return nodo

    def _binario(self, siguiente, operadores):
        nodo = siguiente()
        while self.ver()[0] == 'op' and self.ver()[1] in operadores:
            op = self.tomar()[1]
            nodo = ('op', op, nodo, siguiente())
        return nodo

    def comparacion(self):
        return self._binario(self.concatenar, ('=', '<>', '<', '>', '<=', '>='))

    def concatenar(self):
        return self._binario(self.suma, ('&',))

    def suma(self):
        return self._binario(self.producto, ('+', '-'))

    def producto(self):
        return self._binario(self.potencia, ('*', '/'))

    def potencia(self):
        return self._binario(self.signo, ('^',))

    def signo(self):
        if self.ver() in (('op', '-'), ('op', '+')):
            op = self.tomar()[1]
            nodo = self.signo()
            return ('neg', nodo) if op == '-' else nodo
        return self.porcentaje()

    def porcentaje(self):
        nodo = self.atomo()
        while self.ver() == ('op', '%'):
            self.tomar()
            nodo = ('op', '/', nodo, ('val', 100.0))
        return nodo

    def atomo(self):
        tipo, valor = self.tomar()
        if tipo in ('numero', 'texto'):
            return ('val', valor)
        if tipo == 'celda':
            return ('celda', valor)
        if tipo == 'nombre':
            nombre = valor.upper()
            if self.ver() == ('signo', '('):
                self.tomar()
                args = []
                if self.ver() != ('signo', ')'):
                    while True:
                        args.append(self.comparacion())
                        if self.ver() == ('signo', ','):
                            self.tomar()
                            continue
                        break
                self.tomar(')')
                return ('fun', nombre, args)
            if nombre in ('TRUE', 'VERDADERO'):
                return ('val', True)
            if nombre in ('FALSE', 'FALSO'):
                return ('val', False)
            return ('nombre', valor)
        if (tipo, valor) == ('signo', '('):
            nodo = self.comparacion()
            self.tomar(')')
            return nodo
        if (tipo, valor) == ('signo', '{'):
            filas, fila = [], []
            while True:
                fila.append(self._constante())
                sig = self.tomar()[1]
                if sig == ',':
                    continue
                if sig == '}':
                    filas.append(fila)
                    break
                raise ErrorFormula('Matriz constante mal escrita en la fórmula.')
            return ('val', filas)
        raise ErrorFormula('No se esperaba «%s» en la fórmula.' % (valor if valor is not None else 'el final'))

    def _constante(self):
        nodo = self.signo()
        if nodo[0] == 'val':
            return nodo[1]
        if nodo[0] == 'neg' and nodo[1][0] == 'val':
            return -nodo[1][1]
        raise ErrorFormula('Una matriz constante solo lleva números o textos.')


@functools.lru_cache(maxsize=64)
def leer(formula):
    """Árbol de la fórmula (lanza ErrorFormula si no se entiende). Se
    guarda en memoria: el portal la calcula muchas veces."""
    return _Parser(formula).todo()


def funciones(arbol):
    """Nombres de las funciones que usa la fórmula."""
    res = set()

    def recorrer(nodo):
        if not isinstance(nodo, tuple):
            return
        if nodo[0] == 'fun':
            res.add(nodo[1])
            for a in nodo[2]:
                recorrer(a)
        else:
            for parte in nodo[1:]:
                recorrer(parte)
    recorrer(arbol)
    return res


def celdas(arbol):
    res = set()

    def recorrer(nodo):
        if not isinstance(nodo, tuple):
            return
        if nodo[0] == 'celda':
            res.add(nodo[1])
        for parte in nodo[1:]:
            if isinstance(parte, list):
                for p in parte:
                    recorrer(p)
            else:
                recorrer(parte)
    recorrer(arbol)
    return res


# --- Matrices (lista de filas) ------------------------------------------

def _es_matriz(v):
    return isinstance(v, list)


def _dims(v):
    return (len(v), len(v[0])) if _es_matriz(v) else (1, 1)


def _celda(v, f, c):
    if not _es_matriz(v):
        return v
    filas, cols = _dims(v)
    return v[0 if filas == 1 else f][0 if cols == 1 else c]


def _expandir(func, *valores):
    """Aplica `func` celda a celda, extendiendo filas o columnas de una
    sola posición, como Excel."""
    if not any(_es_matriz(v) for v in valores):
        return func(*valores)
    dims = [_dims(v) for v in valores]
    filas = max(d[0] for d in dims)
    cols = max(d[1] for d in dims)
    for d in dims:
        if d[0] not in (1, filas) or d[1] not in (1, cols):
            raise ErrorFormula('Las matrices de la fórmula no tienen el mismo tamaño.')
    return [[func(*[_celda(v, f, c) for v in valores]) for c in range(cols)] for f in range(filas)]


def _num(v):
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if v in (None, ''):
        return 0.0
    try:
        return float(str(v).replace(',', '.'))
    except ValueError:
        raise ErrorFormula('«%s» no es un número.' % v) from None


def _texto(v):
    if isinstance(v, bool):
        return 'TRUE' if v else 'FALSE'
    if isinstance(v, float):
        return str(int(v)) if v == int(v) else repr(round(v, 10)).rstrip('0').rstrip('.')
    return '' if v is None else str(v)


def _verdad(v):
    if isinstance(v, str):
        if v.upper() in ('TRUE', 'VERDADERO'):
            return True
        if v.upper() in ('FALSE', 'FALSO', ''):
            return False
        raise ErrorFormula('«%s» no es verdadero ni falso.' % v)
    return bool(_num(v))


def _comparar(op, a, b):
    if isinstance(a, str) or isinstance(b, str):
        a, b = _texto(a).lower(), _texto(b).lower()
    else:
        a, b = _num(a), _num(b)
    return {'=': a == b, '<>': a != b, '<': a < b, '>': a > b, '<=': a <= b, '>=': a >= b}[op]


def _redondeo(valor, decimales, modo):
    paso = Decimal(1).scaleb(-int(_num(decimales)))
    d = Decimal(repr(_num(valor)))
    if modo == 'normal':
        return float(d.quantize(paso, rounding=ROUND_HALF_UP))
    factor = 10 ** int(_num(decimales))
    v = _num(valor)
    funcion = math.ceil if modo == 'arriba' else math.floor
    return math.copysign(funcion(round(abs(v) * factor, 9)) / factor, v)


def _division(a, b):
    b = _num(b)
    if b == 0:
        raise ErrorFormula('División por cero en la fórmula (#¡DIV/0!).')
    return _num(a) / b


_OPERADORES = {
    '+': lambda a, b: _num(a) + _num(b),
    '-': lambda a, b: _num(a) - _num(b),
    '*': lambda a, b: _num(a) * _num(b),
    '/': _division,
    '^': lambda a, b: _num(a) ** _num(b),
    '&': lambda a, b: _texto(a) + _texto(b),
}


def _aplanar(valores):
    for v in valores:
        if _es_matriz(v):
            for fila in v:
                yield from fila
        else:
            yield v


class Evaluador:
    """Calcula el árbol con las celdas de entrada (`celdas`: {'K2': 2.5})."""

    FUNCIONES = ('LET', 'SEQUENCE', 'FILTER', 'CHOOSE', 'IF', 'IFERROR', 'AND', 'OR', 'NOT',
                 'INT', 'MOD', 'ROUND', 'ROUNDUP', 'ROUNDDOWN', 'ABS', 'MIN', 'MAX', 'SUM')

    def __init__(self, celdas=None):
        self.celdas = {k.upper(): v for k, v in (celdas or {}).items()}

    def valor(self, nodo, nombres):
        tipo = nodo[0]
        if tipo == 'val':
            return nodo[1]
        if tipo == 'celda':
            if nodo[1] not in self.celdas:
                raise ErrorFormula('La fórmula usa la celda %s, que no es un dato de entrada.' % nodo[1])
            return self.celdas[nodo[1]]
        if tipo == 'nombre':
            clave = nodo[1].lower()
            if clave not in nombres:
                raise ErrorFormula('La fórmula usa «%s», que no está definido.' % nodo[1])
            return nombres[clave]
        if tipo == 'neg':
            return _expandir(lambda a: -_num(a), self.valor(nodo[1], nombres))
        if tipo == 'op':
            op, a, b = nodo[1], self.valor(nodo[2], nombres), self.valor(nodo[3], nombres)
            if op in _OPERADORES:
                return _expandir(_OPERADORES[op], a, b)
            return _expandir(lambda x, y: _comparar(op, x, y), a, b)
        return self.funcion(nodo[1], nodo[2], nombres)

    def funcion(self, nombre, args, nombres):
        if nombre not in self.FUNCIONES:
            raise ErrorFormula('La función %s no se puede calcular en Odoo.' % nombre)
        if nombre == 'LET':
            if len(args) < 3 or len(args) % 2 == 0:
                raise ErrorFormula('LET necesita parejas nombre, valor y al final el cálculo.')
            locales = dict(nombres)
            for i in range(0, len(args) - 1, 2):
                if args[i][0] != 'nombre':
                    raise ErrorFormula('En LET los nombres van sin comillas.')
                locales[args[i][1].lower()] = self.valor(args[i + 1], locales)
            return self.valor(args[-1], locales)
        if nombre in ('IF', 'IFERROR'):
            if nombre == 'IFERROR':
                try:
                    return self.valor(args[0], nombres)
                except ErrorFormula:
                    return self.valor(args[1], nombres)
            cond = self.valor(args[0], nombres)
            si = self.valor(args[1], nombres) if len(args) > 1 else True
            no = self.valor(args[2], nombres) if len(args) > 2 else False
            return _expandir(lambda c, a, b: a if _verdad(c) else b, cond, si, no)
        vals = [self.valor(a, nombres) for a in args]
        if nombre == 'SEQUENCE':
            filas = int(_num(vals[0]))
            cols = int(_num(vals[1])) if len(vals) > 1 else 1
            inicio = _num(vals[2]) if len(vals) > 2 else 1.0
            paso = _num(vals[3]) if len(vals) > 3 else 1.0
            if filas < 1 or cols < 1 or filas * cols > 100000:
                raise ErrorFormula('SEQUENCE con un tamaño no válido (%s × %s).' % (filas, cols))
            return [[inicio + paso * (f * cols + c) for c in range(cols)] for f in range(filas)]
        if nombre == 'CHOOSE':
            opciones = vals[1:]

            def elegir(indice, *opts):
                i = int(_num(indice))
                if not 1 <= i <= len(opts):
                    raise ErrorFormula('CHOOSE no tiene la opción %s.' % i)
                return opts[i - 1]
            return _expandir(elegir, vals[0], *opciones)
        if nombre == 'FILTER':
            datos, incluir = vals[0], vals[1]
            datos = datos if _es_matriz(datos) else [[datos]]
            incluir = incluir if _es_matriz(incluir) else [[incluir]]
            filas_d, cols_d = _dims(datos)
            filas_i, cols_i = _dims(incluir)
            if cols_i == 1 and filas_i in (1, filas_d):
                res = [datos[f] for f in range(filas_d) if _verdad(_celda(incluir, f, 0))]
            elif filas_i == 1 and cols_i == cols_d:
                cols = [c for c in range(cols_d) if _verdad(incluir[0][c])]
                res = [[fila[c] for c in cols] for fila in datos] if cols else []
            else:
                raise ErrorFormula('FILTER: la condición no tiene el tamaño de los datos.')
            if not res or not res[0]:
                if len(vals) > 2:
                    return vals[2]
                raise ErrorFormula('FILTER no encontró datos (#¡CALC!).')
            return res
        if nombre in ('AND', 'OR'):
            todos = [_verdad(v) for v in _aplanar(vals)]
            return all(todos) if nombre == 'AND' else any(todos)
        if nombre in ('MIN', 'MAX', 'SUM'):
            nums = [_num(v) for v in _aplanar(vals) if v not in ('', None)]
            if nombre == 'SUM':
                return sum(nums)
            return (min if nombre == 'MIN' else max)(nums) if nums else 0.0
        if nombre == 'NOT':
            return _expandir(lambda a: not _verdad(a), vals[0])
        if nombre == 'INT':
            return _expandir(lambda a: float(math.floor(_num(a))), vals[0])
        if nombre == 'ABS':
            return _expandir(lambda a: abs(_num(a)), vals[0])
        if nombre == 'MOD':
            def modulo(a, b):
                b = _num(b)
                if b == 0:
                    raise ErrorFormula('MOD por cero en la fórmula (#¡DIV/0!).')
                return _num(a) - b * math.floor(_num(a) / b)
            return _expandir(modulo, vals[0], vals[1])
        modo = {'ROUND': 'normal', 'ROUNDUP': 'arriba', 'ROUNDDOWN': 'abajo'}[nombre]
        return _expandir(lambda a, d: _redondeo(a, d, modo), vals[0], vals[1] if len(vals) > 1 else 0.0)


def calcular(arbol, celdas):
    """Resultado de la fórmula como lista de filas (un valor suelto es una
    fila de una columna)."""
    resultado = Evaluador(celdas).valor(arbol, {})
    return resultado if _es_matriz(resultado) else [[resultado]]
