# -*- coding: utf-8 -*-
# from odoo import http


# class AccountAnalytic(http.Controller):
#     @http.route('/account_analytic/account_analytic', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/account_analytic/account_analytic/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('account_analytic.listing', {
#             'root': '/account_analytic/account_analytic',
#             'objects': http.request.env['account_analytic.account_analytic'].search([]),
#         })

#     @http.route('/account_analytic/account_analytic/objects/<model("account_analytic.account_analytic"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('account_analytic.object', {
#             'object': obj
#         })
