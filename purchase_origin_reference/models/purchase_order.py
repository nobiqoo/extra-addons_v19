from odoo import models, fields, api
from datetime import timedelta

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'
    
    
    origin_document_html = fields.Html(
        string='Documentos Origen',
        compute='_compute_origin_document_html',
        sanitize=False
    )
    
    def _get_origin_document_types(self):
        return [
            ('approval.request', 'Solicitud de Aprobación'),
            ('sale.order', 'Pedido de Venta'),
            ('mrp.production', 'Orden de Producción'),
            ('res.partner', 'Transportista/Proveedor Logístico'), 
            ('stock.picking', 'Albarán/Transferencia'),  
            ('approval.request', 'Solicitud de Aprobación'),
            ('account.move', 'Factura'),
        ]
    
    @api.depends('origin', 'date_order')
    def _compute_origin_document_html(self):
        for order in self:
            try:
                if not order.origin:
                    order.origin_document_html = ''
                    continue

                links = []
                origin_parts = [op.strip() for op in order.origin.split(',') if op.strip()]
                
                for origin_part in origin_parts:
                    doc_id = None
                    if '[ID:' in origin_part and ']' in origin_part:
                        try:
                            doc_name = origin_part.split('[ID:')[0].strip()
                            doc_id = int(origin_part.split('[ID:')[1].split(']')[0])
                            origin_part = doc_name
                        except:
                            pass

                    document_found = False
                    for model, _ in self._get_origin_document_types():
                        domain = [('name', '=', origin_part)]
                        
                        if doc_id:
                            domain.append(('id', '=', doc_id))
                        else:
                            domain.append(('create_date', '<=', order.date_order + timedelta(minutes=5)))
                        
                        document = self.env[model].search(domain, order='create_date DESC', limit=1)
                        
                        if document:
                            url = f"/web#id={document.id}&model={model}&view_type=form"
                            links.append(f'<a href="{url}" target="_blank">{origin_part}</a>')
                            document_found = True
                            break
                    
                    if not document_found:
                        links.append(origin_part)

                order.origin_document_html = ', '.join(links) if links else order.origin
            except Exception as e:
                order.origin_document_html = f"Error al procesar documentos origen: {str(e)}"