# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class PosSession(models.Model):
    _inherit = 'pos.session'

    # # Lista de modelos a cargar en el pos
    # @api.model
    # def _pos_ui_models_to_load(self):
    #     models = super()._pos_ui_models_to_load()
    #     models += [
    #         'l10n_latam.identification.type',
    #         'res.city',
    #     ]
    #     return models
    
    # # Define los campos y filtro del res.partner 
    # # a concultar para la data del PosStore
    # def _loader_params_res_partner(self):
    #     res = super()._loader_params_res_partner()
    #     res['search_params']['fields'] += [
    #         'company_type',
    #         'name1',
    #         'name2',
    #         'lastname1',
    #         'lastname2',
    #         'l10n_latam_identification_type_id',
    #         'property_account_position_id',
    #         'edi_email',
    #         'city_id',
    #     ]
    #     return res
    
    # def _loader_params_l10n_latam_identification_type(self):
    #     return {
    #         'search_params': {
    #             'domain': [('dian_code', '!=', False)], 
    #             'fields': ['name', 'dian_code']
    #         }
    #     }

    # def _get_pos_ui_l10n_latam_identification_type(self, params):
    #     return self.env['l10n_latam.identification.type'].search_read(**params['search_params'])
    
    # def _loader_params_res_city(self):
    #     return {
    #         'search_params': {
    #             'domain': [('dian_code', '!=', False)], 
    #             'fields': ['name', 'dian_code', 'state_id']
    #         }
    #     }

    # def _get_pos_ui_res_city(self, params):
    #     return self.env['res.city'].search_read(**params['search_params'])
