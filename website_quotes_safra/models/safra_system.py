# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SafraSystem(models.Model):
    _name = 'safra.system'
    _description = 'Sistema de Persiana Safra'
    _order = 'name'

    _code_uniq = models.Constraint(
        'UNIQUE(code)',
        'El código del sistema debe ser único.',
    )

    code = fields.Char(string='Código', required=True, index=True)
    name = fields.Char(string='Sistema', required=True)
    active = fields.Boolean(default=True)
    # Relación al maestro de productos: el producto terminado que representa
    # este sistema (grupo de asociación SAP). El menú se conserva como guía;
    # el producto aporta la parametrización (pestaña Parametrización).
    product_tmpl_id = fields.Many2one(
        'product.template', string='Producto terminado', ondelete='set null',
        domain=[('safra_is_system', '=', True)],
        help='Producto del maestro (marcado "Es sistema del cotizador") '
             'asociado a este sistema del portal.')
    # Pendientes 24-sep (1.1): sistemas restringidos por grupos de usuarios
    # (p. ej. estructuras de exportación que no aplican para todos).
    group_ids = fields.Many2many(
        'res.groups', 'safra_system_group_rel', 'system_id', 'group_id',
        string='Grupos que lo ven',
        help='Si se definen, el sistema solo aparece en el cotizador para '
             'los usuarios de estos grupos; vacío = todos.')

    def _visible_for_user(self, user):
        self.ensure_one()
        return not self.group_ids or bool(self.group_ids & user.all_group_ids)
    # Campos habilitados en este sistema, editables desde el formulario.
    mapping_ids = fields.One2many('safra.system.field', 'system_id', string='Campos del sistema')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_products()
        return records

    def _ensure_products(self):
        """Todo sistema del portal debe existir en el maestro de productos.

        El selector del cotizador solo muestra sistemas cuyo producto tiene el
        check "Es sistema del cotizador"; aquí se crea y vincula el producto
        faltante (idempotente: también corre en cada actualización del módulo
        para las bases ya instaladas).
        """
        Product = self.env['product.template'].sudo()
        systems = self if self else self.with_context(active_test=False).search([])
        for system in systems:
            if system.product_tmpl_id:
                continue
            system.product_tmpl_id = Product.create({
                'name': system.name,
                'default_code': system.code,
                'safra_code': system.code,
                'safra_is_system': True,
                'sale_ok': True,
                'purchase_ok': False,
            }).id

    # === Ficha técnica (datos del producto terminado, mostrados en el portal) ===
    tech_width_min = fields.Float(string='Ancho mínimo (m)', digits=(12, 2))
    tech_width_max = fields.Float(string='Ancho máximo (m)', digits=(12, 2))
    tech_height_min = fields.Float(string='Alto mínimo (m)', digits=(12, 2))
    tech_height_max = fields.Float(string='Alto máximo (m)', digits=(12, 2))
    # Reunión 28-sep (fila 3): una persiana de exhibición tiene su propia
    # ficha de mínimos y máximos; un valor vacío usa el de la ficha normal.
    exh_width_min = fields.Float(string='Ancho mínimo exhibición (m)', digits=(12, 2))
    exh_width_max = fields.Float(string='Ancho máximo exhibición (m)', digits=(12, 2))
    exh_height_min = fields.Float(string='Alto mínimo exhibición (m)', digits=(12, 2))
    exh_height_max = fields.Float(string='Alto máximo exhibición (m)', digits=(12, 2))
    # Reunión 28-sep (fila 70): ya no se configura ni se muestra; el
    # mecanismo se calcula con la tabla de estructura. Se conserva la
    # columna para no perder lo que estuviera diligenciado.
    tech_mechanism = fields.Char(
        string='Mecanismo (texto anterior)',
        help='Texto de la ficha técnica, p. ej. "Tubo: R8 - Mecanismo: R8SL - Cabezal: No Aplica".',
    )

    def _tech_limits(self, exhibition=False):
        """Límites efectivos de la ficha técnica (revisión sprint 1,
        f63-f66): si el producto terminado asociado tiene U_AnchoMin /
        U_AnchoMax / U_AltoMin / U_AltoMax, esos valores mandan; si no, se
        usan los del sistema. Con exhibición mandan los límites de
        exhibición del sistema que estén diligenciados."""
        self.ensure_one()
        p = self.product_tmpl_id
        lim = {
            'wmin': (p and p.safra_u_ancho_min) or self.tech_width_min or 0.0,
            'wmax': (p and p.safra_u_ancho_max) or self.tech_width_max or 0.0,
            'hmin': (p and p.safra_u_alto_min) or self.tech_height_min or 0.0,
            'hmax': (p and p.safra_u_alto_max) or self.tech_height_max or 0.0,
        }
        if exhibition:
            lim['wmin'] = self.exh_width_min or lim['wmin']
            lim['wmax'] = self.exh_width_max or lim['wmax']
            lim['hmin'] = self.exh_height_min or lim['hmin']
            lim['hmax'] = self.exh_height_max or lim['hmax']
        return lim
    # Carpeta de imágenes de producto en el repositorio de imágenes del cliente.
    img_group = fields.Char(string='Grupo de imágenes', help='Carpeta en Images/SafraImages, p. ej. "06".')
    # Multiplicador del peso de tela en las fórmulas (hoja 4: "Para Sheer,
    # Alto × 2" — la tela va doblada). 1.0 para los demás sistemas.
    weight_factor = fields.Float(string='Factor de peso de tela', default=1.0, digits=(4, 1))
