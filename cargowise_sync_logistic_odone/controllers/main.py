# -*- coding: utf-8 -*-
import os

from odoo import http
from odoo.http import request


class CargoWiseDocsController(http.Controller):
    @http.route(
        ['/account_cargowise_sync/docs/openapi.yml'],
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False,
    )
    def openapi_yaml(self, **kwargs):
        current_dir = os.path.dirname(__file__)
        docs_path = os.path.abspath(
            os.path.join(current_dir, '..', 'docs', 'integration-openapi.yml')
        )
        try:
            with open(docs_path, 'rb') as file:
                content = file.read()
        except OSError:
            return request.make_response(
                'OpenAPI documentation file not found.',
                headers=[('Content-Type', 'text/plain; charset=utf-8')],
                status=404,
            )
        return request.make_response(
            content,
            headers=[
                ('Content-Type', 'application/x-yaml; charset=utf-8'),
                ('Content-Disposition', 'inline; filename=integration-openapi.yml'),
            ],
        )

    @http.route(
        ['/account_cargowise_sync/docs'],
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False,
    )
    def docs_page(self, **kwargs):
        yaml_url = '/account_cargowise_sync/docs/openapi.yml'
        ui_url = '/account_cargowise_sync/docs/ui'
        html = (
            '<html><head><title>CargoWise Integration Docs</title></head><body>'
            '<h1>CargoWise Integration Docs</h1>'
            '<p>Especificación OpenAPI pública para el módulo <strong>account_cargowise_sync</strong>.</p>'
            '<ul>'
            '<li><a href="%s">Descargar YAML</a></li>'
            '<li><a href="%s">Ver Swagger UI embebido</a></li>'
            '</ul>'
            '</body></html>'
        ) % (yaml_url, ui_url)
        return request.make_response(html, headers=[('Content-Type', 'text/html; charset=utf-8')])

    @http.route(
        ['/account_cargowise_sync/docs/ui'],
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False,
    )
    def docs_ui(self, **kwargs):
        yaml_url = '/account_cargowise_sync/docs/openapi.yml'
        html = f"""
        <!DOCTYPE html>
        <html>
          <head>
            <meta charset="utf-8"/>
            <title>CargoWise Swagger UI</title>
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/4.15.5/swagger-ui.min.css"/>
            <style>
              body {{ margin: 0; padding: 0; }}
              #swagger-ui {{ width: 100%; height: 100vh; }}
            </style>
          </head>
          <body>
            <div id="swagger-ui"></div>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/4.15.5/swagger-ui-bundle.min.js"></script>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/4.15.5/swagger-ui-standalone-preset.min.js"></script>
            <script>
              window.onload = function() {{
                SwaggerUIBundle({{
                  url: '{yaml_url}',
                  dom_id: '#swagger-ui',
                  deepLinking: true,
                  presets: [
                    SwaggerUIBundle.presets.apis,
                  ],
                  layout: 'BaseLayout'
                }});
              }};
            </script>
          </body>
        </html>
        """
        return request.make_response(html, headers=[('Content-Type', 'text/html; charset=utf-8')])
