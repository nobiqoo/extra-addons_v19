from . import models


def _post_init_hook(env):
    env['res.partner'].search([
        ('city', '!=', False),
        ('country_id', '!=', False),
        ('city_id', '=', False),
    ])._ensure_city_id()
