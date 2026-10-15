# -*- coding: utf-8 -*-

import hmac
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MISSING = object()  # sentinel para distinguir None de campo ausente


def _require(payload, field, prefix=''):
    """Retorna el valor del campo o agrega error a la lista."""
    value = payload.get(field, _MISSING)
    if value is _MISSING or value is None or value == '':
        return None, f"{prefix}.{field} es obligatorio." if prefix else f"'{field}' es obligatorio."
    return value, None


def _json_error(message, errors=None, status=400):
    body = {'status': 'error', 'message': message}
    if errors:
        body['errors'] = errors
    return request.make_json_response(body, status=status)


def _json_success(data, status=201):
    return request.make_json_response({'status': 'success', 'data': data}, status=status)


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------

class AccountMoveApiController(http.Controller):
    """
    Endpoint REST para la creación de asientos contables en Odoo.

    Autenticación: Header HTTP  →  X-API-Key: <clave configurada en la compañía>
    Ruta: POST /api/v1/account/moves

    Payload de entrada (application/json):
    {
        "entries": [
            {
                "date": "2024-01-01",          // Fecha del asiento (YYYY-MM-DD)
                "reference": "REF-001",        // Referencia del asiento
                "post": true,                  // Si se publica el asiento
                "lines": [
                    {
                        "account": "1110",          // Código de cuenta contable
                        "description": "Descripción de la línea",
                        "partner_vat": "900123456-1", // NIT/VAT del tercero
                        "cost_center": "CC-001",     // Código del centro de costo
                        "debit": 1000.00,
                        "credit": 0.00
                    },
                    ...
                ]
            },
            ...
        ]
    }

    Respuesta exitosa (HTTP 201):
    {
        "status": "success",
        "data": [
            {
                "id": 123,
                "name": "MISC/2024/01/0001",
                "date": "2024-01-01",
                "reference": "REF-001",
                "state": "posted",
                "journal": "Diario de Operaciones Diversas"
            },
            ...
        ]
    }

    Respuesta de error (HTTP 400/422/500):
    {
        "status": "error",
        "message": "Descripción general del error.",
        "errors": ["detalle 1", "detalle 2", ...]
    }
    """

    @http.route(
        '/api/v1/account/moves',
        type='http',
        auth='public',
        methods=['POST'],
        csrf=False,
        cors='*',
        save_session=False,
    )
    def create_account_moves(self, **kwargs):  # noqa: C901
        """Crea uno o más asientos contables a partir del payload JSON recibido."""

        # ---------------------------------------------------------------
        # 1. Validar API Key (header X-API-Key)
        # ---------------------------------------------------------------
        api_key_header = request.httprequest.headers.get('X-API-Key', '')
        if not api_key_header:
            return _json_error(
                'Autenticación requerida. Envíe el header X-API-Key: <clave>.',
                status=401,
            )

        # Buscar compañía que tenga esta API Key configurada.
        # Se usa sudo() para acceder al campo aunque el usuario sea público.
        companies = request.env['res.company'].sudo().search(
            [('api_rest_api_key', '!=', False)],
        )
        company = next(
            (
                c for c in companies
                if c.api_rest_api_key
                and hmac.compare_digest(
                    c.api_rest_api_key.encode(),
                    api_key_header.encode(),
                )
            ),
            None,
        )
        if not company:
            _logger.warning(
                "API REST asientos: intento de acceso con API Key inválida desde %s",
                request.httprequest.remote_addr,
            )
            return _json_error('API Key inválida o no autorizada.', status=401)

        # ---------------------------------------------------------------
        # 2. Parsear cuerpo JSON
        # ---------------------------------------------------------------
        try:
            payload = request.get_json_data()
        except (ValueError, AttributeError):
            return _json_error('El cuerpo de la solicitud debe ser JSON válido (Content-Type: application/json).')

        if not isinstance(payload, dict):
            return _json_error('El cuerpo de la solicitud debe ser un objeto JSON.')

        entries = payload.get('entries')
        if not isinstance(entries, list) or not entries:
            return _json_error("El campo 'entries' es obligatorio y debe ser una lista no vacía.")

        # ---------------------------------------------------------------
        # 3. Validar que el diario de integración esté configurado
        # ---------------------------------------------------------------
        # Usamos superusuario con el contexto de la compañía autenticada.
        env = request.env(
            su=True,
            context=dict(request.env.context, allowed_company_ids=[company.id]),
        )
        journal = company.api_integration_journal_id
        if not journal:
            return _json_error(
                'El diario de integración API no está configurado en la compañía. '
                'Configure el diario en Ajustes → Contabilidad → Integración API REST.',
                status=500,
            )

        # ---------------------------------------------------------------
        # 4. Validar y preparar cada asiento
        # ---------------------------------------------------------------
        all_errors = []
        moves_to_create = []
        seen_references = set()  # para detectar duplicados dentro del mismo payload

        for idx, entry in enumerate(entries):
            prefix = f'entries[{idx}]'
            entry_errors = []

            if not isinstance(entry, dict):
                all_errors.append(f'{prefix}: debe ser un objeto JSON.')
                continue

            # -- Campos de cabecera --
            entry_date, err = _require(entry, 'date', prefix)
            if err:
                entry_errors.append(err)

            reference, err = _require(entry, 'reference', prefix)
            if err:
                entry_errors.append(err)
            elif reference:
                # Validar duplicado dentro del mismo payload
                if reference in seen_references:
                    entry_errors.append(
                        f"{prefix}.reference: La referencia '{reference}' está duplicada "
                        f"en este mismo payload."
                    )
                else:
                    # Validar duplicado en la base de datos (mismo diario + compañía)
                    existing = env['account.move'].search(
                        [
                            ('ref', '=', reference),
                            ('journal_id', '=', journal.id),
                            ('company_id', '=', company.id),
                            ('move_type', '=', 'entry'),
                        ],
                        limit=1,
                    )
                    if existing:
                        entry_errors.append(
                            f"{prefix}.reference: Ya existe un asiento con la referencia "
                            f"'{reference}' en el diario '{journal.name}' "
                            f"(ID: {existing.id}, Nombre: {existing.name})."
                        )
                    else:
                        seen_references.add(reference)

            post = entry.get('post', _MISSING)
            if post is _MISSING or not isinstance(post, bool):
                entry_errors.append(f"{prefix}.post es obligatorio y debe ser un booleano (true/false).")
                post = False

            lines = entry.get('lines')
            if not isinstance(lines, list) or not lines:
                entry_errors.append(f"{prefix}.lines es obligatorio y debe ser una lista no vacía.")

            # Validar formato de fecha antes de continuar con líneas
            if entry_date:
                try:
                    from datetime import date as _date
                    _date.fromisoformat(str(entry_date))
                except ValueError:
                    entry_errors.append(f"{prefix}.date tiene formato inválido. Use YYYY-MM-DD.")
                    entry_date = None

            if entry_errors:
                all_errors.extend(entry_errors)
                continue

            # -- Líneas del asiento --
            prepared_lines = []
            for line_idx, line in enumerate(lines):
                lprefix = f'{prefix}.lines[{line_idx}]'

                if not isinstance(line, dict):
                    entry_errors.append(f'{lprefix}: debe ser un objeto JSON.')
                    continue

                account_code, err = _require(line, 'account', lprefix)
                if err:
                    entry_errors.append(err)

                description, err = _require(line, 'description', lprefix)
                if err:
                    entry_errors.append(err)

                partner_vat, err = _require(line, 'partner_vat', lprefix)
                if err:
                    entry_errors.append(err)

                cost_center_code, err = _require(line, 'cost_center', lprefix)
                if err:
                    entry_errors.append(err)

                debit = line.get('debit', _MISSING)
                if debit is _MISSING or debit is None:
                    entry_errors.append(f"{lprefix}.debit es obligatorio.")
                    debit = None

                credit = line.get('credit', _MISSING)
                if credit is None or credit is _MISSING:
                    entry_errors.append(f"{lprefix}.credit es obligatorio.")
                    credit = None

                # Si hay campos faltantes no tiene sentido hacer búsquedas
                if any(v is None for v in [account_code, description, partner_vat, cost_center_code]):
                    continue

                # Validar tipos numéricos
                try:
                    debit = float(debit) if debit is not None else None
                    credit = float(credit) if credit is not None else None
                except (TypeError, ValueError):
                    entry_errors.append(f"{lprefix}: debit y credit deben ser valores numéricos.")
                    continue

                # Validar cuenta contable
                account = env['account.account'].search(
                    [('code', '=', account_code), ('company_ids', 'in', company.id)],
                    limit=1,
                )
                if not account:
                    entry_errors.append(
                        f"{lprefix}.account: No existe cuenta contable con código '{account_code}' "
                        f"en la compañía '{company.name}'."
                    )

                # Validar tercero por NIT/VAT
                partner = env['res.partner'].search(
                    [('vat', '=', partner_vat)],
                    limit=1,
                )
                if not partner:
                    entry_errors.append(
                        f"{lprefix}.partner_vat: No existe tercero con NIT/VAT '{partner_vat}'."
                    )

                # Validar centro de costo (cuenta analítica)
                analytic = env['account.analytic.account'].search(
                    [
                        ('code', '=', cost_center_code),
                        ('company_id', 'in', [company.id, False]),
                    ],
                    limit=1,
                )
                if not analytic:
                    entry_errors.append(
                        f"{lprefix}.cost_center: No existe centro de costo con código '{cost_center_code}'."
                    )

                if not entry_errors:
                    prepared_lines.append({
                        'account_id': account.id,
                        'name': description,
                        'partner_id': partner.id,
                        'analytic_distribution': {str(analytic.id): 100},
                        'debit': debit,
                        'credit': credit,
                    })

            if entry_errors:
                all_errors.extend(entry_errors)
            else:
                moves_to_create.append({
                    'journal_id': journal.id,
                    'date': entry_date,
                    'ref': reference,
                    '_post': post,
                    'line_ids': [(0, 0, line_vals) for line_vals in prepared_lines],
                })

        # ---------------------------------------------------------------
        # 5. Retornar errores de validación si los hay (422 Unprocessable)
        # ---------------------------------------------------------------
        if all_errors:
            return _json_error(
                'Se encontraron errores de validación. No se creó ningún asiento.',
                errors=all_errors,
                status=422,
            )

        # ---------------------------------------------------------------
        # 6. Crear los asientos contables
        # ---------------------------------------------------------------
        AccountMove = env['account.move']
        created = []

        for move_vals in moves_to_create:
            should_post = move_vals.pop('_post')
            try:
                move = AccountMove.create(move_vals)
                if should_post:
                    move.action_post()
                created.append({
                    'id': move.id,
                    'name': move.name,
                    'date': str(move.date),
                    'reference': move.ref or '',
                    'state': move.state,
                    'journal': move.journal_id.name,
                })
            except Exception as exc:  # noqa: BLE001
                _logger.exception("Error al crear asiento contable vía API REST.")
                return _json_error(
                    f'Error interno al crear el asiento: {exc}',
                    status=500,
                )

        return _json_success(created, status=201)
