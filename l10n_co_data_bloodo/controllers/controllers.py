# -*- coding: utf-8 -*-
# from odoo import http


# class L10nCoDataBloodo(http.Controller):
#     @http.route('/l10n_co_data_bloodo/l10n_co_data_bloodo', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/l10n_co_data_bloodo/l10n_co_data_bloodo/objects',
#                 auth='public')
#     def list(self, **kw):
#         return http.request.render('l10n_co_data_bloodo.listing', {
#             'root': '/l10n_co_data_bloodo/l10n_co_data_bloodo',
#             'objects': http.request.env[
#                   'l10n_co_data_bloodo.l10n_co_data_bloodo'].search([]),
#         })

#     @http.route('/l10n_co_data_bloodo/l10n_co_data_bloodo/objects/'
#                 '<model("l10n_co_data_bloodo.l10n_co_data_bloodo"):obj>',
#                 auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('l10n_co_data_bloodo.object', {
#             'object': obj
#         })
