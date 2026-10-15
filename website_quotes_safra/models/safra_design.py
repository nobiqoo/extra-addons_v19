# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SafraDesign(models.Model):
    """Catálogo de diseños de impresión (puntos 10-11, retoque).

    Réplica configurable del select «Diseño Impresión» del portal del
    cliente: el campo del cotizador ofrece estos diseños y la opción
    «OTROS» para subir un diseño propio.
    """
    _name = 'safra.design'
    _description = 'Diseño de Impresión'
    _order = 'sequence, code'

    _code_uniq = models.Constraint('UNIQUE(code)', 'El código del diseño debe ser único.')

    code = fields.Char(string='Código', required=True, index=True)
    name = fields.Char(string='Nombre', required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    # OBS REU GENERALES 11-sep: el mismo catálogo sirve los diseños de
    # impresión y los diseños de TEXTURA del Blackout Texturizado (cada
    # campo del portal ofrece solo los de su tipo).
    dtype = fields.Selection([
        ('impresion', 'Diseño de impresión'),
        ('textura', 'Diseño de textura'),
    ], string='Tipo', required=True, default='impresion', index=True)
    # Imagen del diseño: la propia (subida aquí) manda; si no hay, se usa la
    # URL del repositorio público del cliente (sembrada automáticamente).
    image = fields.Image(string='Imagen', max_width=512, max_height=512)
    image_url = fields.Char(
        string='URL de imagen',
        help='Imagen pública del diseño (repositorio del portal del '
             'cliente). Se usa cuando no se ha subido una imagen propia.')

    def _image_src(self):
        """URL que muestra el portal: imagen propia > URL del cliente."""
        self.ensure_one()
        if self.image:
            return '/web/image?model=safra.design&id=%d&field=image' % self.id
        return self.image_url or ''

    @api.model
    def _seed_defaults(self, _ids=None):
        """Siembra el catálogo actual del portal del cliente (idempotente:
        solo crea los códigos faltantes)."""
        # Familias y rangos vigentes en portal.safrasas.com (sep-2026).
        codes = []
        for prefix, ranges in [
            ('DSDEP', [(1, 24)]),
            ('DSFLO', [(1, 138), (202, 202)]),
            ('DSINF', [(1, 134), (138, 138), (146, 146)]),
            ('DSMUS', [(1, 10)]),
            ('DSPAI', [(1, 160)]),
            ('DSPOP', [(1, 6)]),
            ('DSTEE', [(1, 34)]),
        ]:
            for start, end in ranges:
                codes += ['%s%03d' % (prefix, n) for n in range(start, end + 1)]
        def _url(code):
            # Repositorio público del cliente: /Images/DisImp/<FAMILIA>/<COD>.png
            return 'https://portal.safrasas.com/Images/DisImp/%s/%s.png' % (code[:5], code)

        recs = self.with_context(active_test=False).search([])
        existing = set(recs.mapped('code'))
        vals = [{'code': c, 'name': c, 'image_url': _url(c)} for c in codes if c not in existing]
        if 'OTROS' not in existing:
            vals.append({'code': 'OTROS', 'name': 'OTROS (diseño propio)', 'sequence': 9999})
        if vals:
            self.create(vals)
        # Rellena la URL en los ya existentes que no la tengan (idempotente).
        for rec in recs.filtered(lambda r: not r.image_url and r.code != 'OTROS'):
            rec.image_url = _url(rec.code)
        return True
