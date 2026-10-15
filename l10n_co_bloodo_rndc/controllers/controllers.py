# -*- coding: utf-8 -*-
# from odoo import http


# class L10nCoBloodoRndc(http.Controller):
#     @http.route('/l10n_co_bloodo_rndc/l10n_co_bloodo_rndc', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/l10n_co_bloodo_rndc/l10n_co_bloodo_rndc/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('l10n_co_bloodo_rndc.listing', {
#             'root': '/l10n_co_bloodo_rndc/l10n_co_bloodo_rndc',
#             'objects': http.request.env['l10n_co_bloodo_rndc.l10n_co_bloodo_rndc'].search([]),
#         })

#     @http.route('/l10n_co_bloodo_rndc/l10n_co_bloodo_rndc/objects/<model("l10n_co_bloodo_rndc.l10n_co_bloodo_rndc"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('l10n_co_bloodo_rndc.object', {
#             'object': obj
#         })
