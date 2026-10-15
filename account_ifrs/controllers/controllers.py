# -*- coding: utf-8 -*-
# from odoo import http


# class AccountIfrs(http.Controller):
#     @http.route('/account_ifrs/account_ifrs', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/account_ifrs/account_ifrs/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('account_ifrs.listing', {
#             'root': '/account_ifrs/account_ifrs',
#             'objects': http.request.env['account_ifrs.account_ifrs'].search([]),
#         })

#     @http.route('/account_ifrs/account_ifrs/objects/<model("account_ifrs.account_ifrs"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('account_ifrs.object', {
#             'object': obj
#         })
