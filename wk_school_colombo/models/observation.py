# -*- coding: utf-8 -*-
from odoo import api, fields, models


class WkSchoolColomboObservation(models.Model):
    """Histórico único de observaciones del estudiante.

    Requerimiento de campos académicos, sección "Histórico de comentarios /
    observaciones": consolida en un solo modelo las notas que hoy se
    generarían desde distintos procesos (inscripción, clase, facturación,
    gestión administrativa o comentarios manuales), conservando cada registro
    como una entrada independiente -nunca se reemplaza ni se edita el
    histórico previo-. La inmutabilidad para el perfil Staff se controla por
    permisos (security/ir.model.access.csv), no con un campo "active": un
    registro archivado dejaría de listarse en el histórico, que es justo lo
    que no debe pasar.

    Toda observación queda ligada a una inscripción concreta (enrollment_id
    es obligatorio): la captura de referencia muestra la misma tabla única y
    editable en la pestaña Observaciones de la Inscripción para notas de
    cualquier origen, con "Referencia" mostrando el número de la propia
    inscripción (p. ej. "SE00011"). student_id se deriva siempre de
    enrollment_id (related+store) para no poder desincronizarse.

    Las automatizaciones que generarían una observación automáticamente desde
    otro proceso (por ejemplo, al confirmar una factura) quedan fuera de esta
    tarea; aquí solo se deja lista la estructura y la carga manual asistida
    por los valores por defecto de contexto de cada pestaña de origen.
    """

    _name = 'wk.school.colombo.observation'
    _inherit = ['mail.thread']
    _description = 'Observación del estudiante'
    _order = 'create_date desc'

    enrollment_id = fields.Many2one(
        'student.enrollment', string="Inscripción", required=True,
        ondelete='cascade', index=True, tracking=True)
    student_id = fields.Many2one(
        'student.student', string="Estudiante", related='enrollment_id.student_id',
        store=True, index=True, readonly=True)
    school_class_id = fields.Many2one(
        'wk.school.class', string="Clase", ondelete='set null', tracking=True,
        domain="[('is_active_class', '=', True)]")
    move_id = fields.Many2one(
        'account.move', string="Factura", ondelete='set null',
        domain="[('move_type', 'in', ('out_invoice', 'out_refund'))]",
        tracking=True)
    origin = fields.Selection([
        ('enrollment', 'Inscripción'),
        ('class', 'Clase'),
        ('billing', 'Facturación'),
        ('administrative', 'Gestión administrativa'),
        ('other', 'Comentario adicional'),
    ], string="Origen", required=True, default='other', tracking=True)
    # Categoría de negocio de la observación, pedida como dato independiente
    # del origen técnico en el requerimiento ("Tipo de observación." y
    # "Origen." son dos líneas separadas). Los valores son una propuesta
    # inicial; el listado exacto debe confirmarse con el negocio.
    observation_type = fields.Selection([
        ('class', 'Clase'),
        ('billing', 'Pago / Factura'),
        ('administrative', 'Administrativo'),
        ('discipline', 'Disciplina'),
        ('general', 'Comentario general'),
    ], string="Tipo", required=True, default='general', tracking=True)
    user_id = fields.Many2one(
        'res.users', string="Registrado por",
        default=lambda self: self.env.user, required=True, tracking=True)
    comment = fields.Text(string="Observación", required=True)
    company_id = fields.Many2one(
        'res.company', string="Sede", related='student_id.company_id',
        store=True, readonly=True)
    reference_display = fields.Char(
        string="Referencia", compute='_compute_reference_display')

    @api.depends('enrollment_id.name', 'school_class_id.name')
    def _compute_reference_display(self):
        for observation in self:
            observation.reference_display = (
                observation.school_class_id.name
                or observation.enrollment_id.name
                or False)
