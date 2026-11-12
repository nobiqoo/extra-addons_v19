# -*- coding: utf-8 -*-
"""Sprint 1.6 (fila 125): cargue masivo de pedidos por archivo de Excel.

Cada fila del archivo es una persiana. La plantilla se descarga por
sistema con las columnas de sus campos (fila 1: nombre del campo; fila 2:
código técnico, que es lo que se lee) y una hoja con las opciones válidas.
El archivo se convierte en el mismo formulario del portal, pasa por el
mismo motor de validaciones y crea la cotización igual que «Finalizar
pedido».

Las rutas viven en SafraQuoterController (main.py), que hereda este mixin:
Odoo no admite un segundo controlador que herede del primero."""
import io
import re

import openpyxl
import xlsxwriter

from odoo.http import content_disposition, request

# Campos que calcula el portal (no se digitan) o que necesitan un archivo.
NO_CARGABLES = {'print_m2', 'ancho_telo', 'lamas_table', 'design_upload'}
SI = {'si', 'sí', 'x', '1', 'true', 'verdadero', 'yes'}


def _texto(valor):
    if valor is None:
        return ''
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return str(valor).strip()


def _clave(valor):
    return _texto(valor).lower()


class SafraCargueMixin:

    def _sistemas_visibles(self):
        systems = request.env['safra.system'].sudo().search([
            ('active', '=', True), ('product_tmpl_id.safra_is_system', '=', True)], order='name')
        return systems.filtered(lambda s: s._visible_for_user(request.env.user))

    def _campos_cargue(self, system):
        config = self._build_form_config(system)
        return config, [f for f in config['fields'] if f['code'] not in NO_CARGABLES]

    def _render_cargue(self, **valores):
        user = request.env.user
        return request.render('website_quotes_safra.portal_cargue_masivo', dict({
            'systems': self._sistemas_visibles(),
            'errores': [],
            'puede_exportar': user.has_group('website_quotes_safra.group_safra_exportacion'),
            'puede_verificar': user.has_group('website_quotes_safra.group_safra_verificacion'),
            **self._contexto_despacho(),
        }, **valores))

    def _plantilla_cargue(self, system_id):
        try:
            system = self._sistemas_visibles().filtered(lambda s: s.id == int(system_id))
        except (TypeError, ValueError):
            system = None
        if not system:
            return request.redirect('/cotizador/cargue')
        config, campos = self._campos_cargue(system)
        out = io.BytesIO()
        book = xlsxwriter.Workbook(out, {'in_memory': True})
        titulo = book.add_format({'bold': True, 'bg_color': '#DDEBF7', 'border': 1, 'text_wrap': True})
        codigo = book.add_format({'font_color': '#808080', 'italic': True, 'border': 1})
        hoja = book.add_worksheet('Persianas')
        opciones = book.add_worksheet('Opciones')
        columnas = [('Sistema', 'system_id')] + [(f['label'], f['code']) for f in campos]
        for col, (nombre, code) in enumerate(columnas):
            obligatorio = code == 'system_id' or any(
                f['code'] == code and f['required'] for f in campos)
            hoja.write(0, col, nombre + (' *' if obligatorio else ''), titulo)
            hoja.write(1, col, code, codigo)
            hoja.set_column(col, col, 18)
        hoja.write(2, 0, system.name)
        hoja.freeze_panes(2, 1)
        # Hoja de opciones: lo que se puede escribir en cada columna.
        opciones.write_row(0, 0, ['Campo', 'Código', 'Valor que puede escribir'], titulo)
        fila = 1
        for f in campos:
            for valor in self._valores_validos(f, config):
                opciones.write_row(fila, 0, [f['label'], f['code'], valor])
                fila += 1
        opciones.set_column(0, 2, 32)
        book.close()
        nombre = 'Plantilla cargue %s.xlsx' % re.sub(r'[^\w .-]', '', system.name)
        return request.make_response(out.getvalue(), headers=[
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', content_disposition(nombre)),
        ])

    def _valores_validos(self, campo, config):
        tipo = campo['type']
        if tipo == 'boolean':
            return ['Sí', 'No']
        if tipo == 'fabric':
            return [f['name'] for f in config.get('fabrics') or []]
        if tipo == 'color':
            return ['Nombre o código del color de la referencia']
        if tipo in ('selection', 'ref_categoria', 'design'):
            return [o.get('label') or o.get('value') for o in campo.get('options') or []]
        if tipo in ('integer', 'float'):
            return ['Número (decimales con punto o coma)']
        return []

    def _subir_cargue(self, post):
        archivo = request.httprequest.files.get('archivo')
        if not (archivo and archivo.filename):
            return self._render_cargue(errores=['Adjunte el archivo de Excel con las persianas.'])
        try:
            libro = openpyxl.load_workbook(io.BytesIO(archivo.read()), read_only=True, data_only=True)
            filas = list(libro.worksheets[0].iter_rows(values_only=True))
        except Exception:
            return self._render_cargue(errores=[
                'El archivo no se pudo leer: use la plantilla de Excel (.xlsx).'])
        form, filas_excel, errores = self._formulario_desde_excel(filas)
        lines = self._parse_lines(form) if not errores else []
        if not errores and not lines:
            errores.append('El archivo no trae persianas (desde la fila 3, con Sistema y Referencia).')
        pedido = self._parse_pedido(post)
        issues = []
        if lines:
            issues = self._validate_lines(lines, pedido=pedido) + self._errores_pedido(pedido)
            if any(v.get('sin_restricciones') for v in lines) and not post.get('acepta_sin_garantia'):
                errores.append('Hay persianas sin restricciones: acepte que no tienen garantía.')
            # Reunión 09-nov (fila 74): igual con la verificación de fabricación.
            if pedido.get('requiere_verificacion') and not pedido.get('acepta_sin_garantia'):
                errores.append(self._error_sin_garantia()['message'])
            for n, vals in enumerate(lines, start=1):
                if vals.get('custom_design') == 'OTROS':
                    errores.append('Fila %d: el diseño propio necesita su archivo; '
                                   'agregue esa persiana desde el formulario.' % filas_excel[n - 1])
            for issue in issues:
                if issue['severity'] != 'error':
                    continue
                donde = ('Fila %d' % filas_excel[issue['line'] - 1]) if issue.get('line') else 'Pedido'
                errores.append('%s: %s' % (donde, issue['message']))
        if errores:
            return self._render_cargue(errores=errores)
        quote = self._guardar_cotizacion(lines, issues, pedido)
        avisos = [i for i in issues if i['severity'] != 'error']
        if avisos:
            quote.message_post(body='Advertencias del cargue masivo:\n' + '\n'.join(
                '%s: %s' % (('Fila %d' % filas_excel[i['line'] - 1]) if i.get('line') else 'Pedido',
                            i['message']) for i in avisos))
        return request.redirect('/mis-cotizaciones/%d' % quote.id)

    def _formulario_desde_excel(self, filas):
        """Convierte las filas del Excel en los nombres del formulario del
        portal (código_índice). Devuelve (form, fila de Excel de cada
        persiana, errores)."""
        errores = []
        if len(filas) < 2:
            return {}, [], ['El archivo no tiene la fila de códigos (fila 2 de la plantilla).']
        codigos = [_texto(c) for c in filas[1]]
        if 'system_id' not in codigos:
            return {}, [], ['La fila 2 debe traer los códigos de la plantilla (falta «system_id»).']
        sistemas = self._sistemas_visibles()
        configs = {}
        form, filas_excel = {}, []
        for num, fila in enumerate(filas[2:], start=3):
            datos = {codigos[i]: v for i, v in enumerate(fila)
                     if i < len(codigos) and codigos[i] and _texto(v) != ''}
            if not datos:
                continue
            nombre_sistema = _clave(datos.get('system_id'))
            system = sistemas.filtered(lambda s: _clave(s.name) == nombre_sistema or
                                       _clave(s.code) == nombre_sistema)[:1]
            if not system:
                errores.append('Fila %d: el sistema «%s» no existe o no está disponible.'
                               % (num, _texto(datos.get('system_id'))))
                continue
            if system.id not in configs:
                configs[system.id] = self._campos_cargue(system)
            config, campos = configs[system.id]
            idx = len(filas_excel)
            form['system_id_%d' % idx] = str(system.id)
            telas = {}
            for campo in campos:
                code = campo['code']
                if code not in datos or campo['type'] == 'color':
                    continue
                valor, error = self._valor_celda(campo, datos[code], config)
                if error:
                    errores.append('Fila %d, %s: %s' % (num, campo['label'], error))
                elif valor is not None:
                    form['%s_%d' % (code, idx)] = valor
                    if campo['type'] == 'fabric':
                        telas[code] = int(valor)
            # El color se busca entre los de su referencia (fabric_id ↔ color_id).
            for campo in campos:
                code = campo['code']
                if campo['type'] != 'color' or code not in datos:
                    continue
                tela = telas.get(code.replace('color_id', 'fabric_id'))
                valor = self._color_celda(tela, datos[code], system)
                if valor:
                    form['%s_%d' % (code, idx)] = valor
                else:
                    errores.append('Fila %d, %s: «%s» no es un color de la referencia elegida.'
                                   % (num, campo['label'], _texto(datos[code])))
            if 'fabric_id_%d' % idx not in form:
                # Sin referencia el formulario no toma la persiana.
                errores.append('Fila %d: falta la Referencia.' % num)
                for key in [k for k in form if k.endswith('_%d' % idx)]:
                    del form[key]
                continue
            self._maximo_lamas(form, idx, system, config)
            filas_excel.append(num)
        return form, filas_excel, errores

    def _valor_celda(self, campo, valor, config):
        tipo = campo['type']
        texto = _texto(valor)
        if tipo == 'boolean':
            return ('on' if texto.lower() in SI else None), None
        if tipo in ('integer', 'float'):
            try:
                numero = float(texto.replace(',', '.'))
            except ValueError:
                return None, '«%s» no es un número.' % texto
            return (str(int(numero)) if tipo == 'integer' else str(numero)), None
        if tipo == 'fabric':
            for f in config.get('fabrics') or []:
                if _clave(f['name']) == texto.lower() or _clave(f.get('code')) == texto.lower():
                    return str(f['id']), None
            return None, '«%s» no es una referencia de este sistema.' % texto
        if tipo in ('selection', 'ref_categoria', 'design'):
            opciones = campo.get('options') or []
            if not opciones:
                return texto, None
            for o in opciones:
                if texto.lower() in (_clave(o.get('value')), _clave(o.get('label'))):
                    return str(o.get('value')), None
            return None, '«%s» no es una opción válida (vea la hoja Opciones de la plantilla).' % texto
        return texto, None

    def _color_celda(self, fabric_id, valor, system):
        if not fabric_id:
            return None
        texto = _texto(valor).lower()
        for c in self.ajax_colores(fabric_id=fabric_id, system_id=system.id):
            if texto in (_clave(c['name']), _clave(c.get('code')), str(c['id'])):
                return str(c['id'])
        return None

    def _maximo_lamas(self, form, idx, system, config):
        """En Vertical y Vintage el portal llena la cantidad de lamas con el
        máximo de la fórmula; en el cargue también, si viene vacía."""
        key = 'quantity_lamas_%d' % idx
        if not config.get('max_lamas') or form.get(key):
            return
        try:
            ancho = float(form.get('width_%d' % idx) or 0)
        except ValueError:
            return
        apertura = {'1': 'derecha', '2': 'izquierda', '3': 'extremos', '4': 'centro'}.get(
            form.get('apertura_%d' % idx), form.get('apertura_%d' % idx))
        motor = form.get('motor_%d' % idx)
        maximo = request.env['safra.lamas.rule'].sudo().compute_max(
            system, ancho, apertura, motorized=bool(form.get('has_motor_%d' % idx)) or bool(
                motor and motor not in ('0', 'sin')))
        if maximo is not None:
            form[key] = str(maximo)
