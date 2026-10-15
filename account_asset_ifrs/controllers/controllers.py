# -*- coding: utf-8 -*-
# from odoo import http


# class AccountAssetIfrs(http.Controller):
#     @http.route('/account_asset_ifrs/account_asset_ifrs', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/account_asset_ifrs/account_asset_ifrs/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('account_asset_ifrs.listing', {
#             'root': '/account_asset_ifrs/account_asset_ifrs',
#             'objects': http.request.env['account_asset_ifrs.account_asset_ifrs'].search([]),
#         })

#     @http.route('/account_asset_ifrs/account_asset_ifrs/objects/<model("account_asset_ifrs.account_asset_ifrs"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('account_asset_ifrs.object', {
#             'object': obj
#         })
