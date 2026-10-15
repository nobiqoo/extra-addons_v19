# -*- coding: utf-8 -*-
# from odoo import http


# class BaseDataBaseline(http.Controller):
#     @http.route('/base_data_baseline/base_data_baseline', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/base_data_baseline/base_data_baseline/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('base_data_baseline.listing', {
#             'root': '/base_data_baseline/base_data_baseline',
#             'objects': http.request.env['base_data_baseline.base_data_baseline'].search([]),
#         })

#     @http.route('/base_data_baseline/base_data_baseline/objects/<model("base_data_baseline.base_data_baseline"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('base_data_baseline.object', {
#             'object': obj
#         })
