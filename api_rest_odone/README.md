# API REST OdOne — Asientos Contables

## Descripción general

Este documento describe la API REST desarrollada por OdOne S.A.S. para la integración de sistemas externos con el módulo de contabilidad de Odoo. Permite crear asientos contables directamente en Odoo mediante peticiones HTTP, sin necesidad de acceso a la interfaz web ni credenciales de usuario.

La API recibe los datos del asiento en formato JSON, valida cada campo contra la información registrada en Odoo (cuentas contables, terceros, centros de costo) y, si todo es correcto, crea el asiento en el diario configurado. Si se detecta algún error, no se crea ningún registro y la respuesta detalla todos los problemas encontrados.

La autenticación se realiza mediante una API Key única por compañía, que debe enviarse en cada petición a través del header `X-API-Key`.

| Parámetro | Valor |
|---|---|
| **URL base** | `https://test-interejecutiva.odoo.com` |
| **API Key** | `WWjz_e0uOneyKLCYDfLv5qYma2zGOC9SV68_PLamJqQ` |

---

## Configuración

### 1. Diario de integración

Es el diario contable que se usará para todos los asientos creados por el endpoint. Debe configurarse antes de hacer la primera llamada.

**Ruta:** `Ajustes → Contabilidad → Integración API REST → Diario para Integración API`

También puede configurarse desde el formulario de la compañía:  
`Ajustes → Usuarios y compañías → Compañías → [Compañía] → Pestaña "Integración API REST"`

### 2. API Key

Clave secreta que deben enviar los sistemas externos para autenticarse.

**Ruta:** `Ajustes → Contabilidad → Integración API REST → API Key de Integración`

- Haga clic en **"Generar nueva API Key"** para crear una clave segura automáticamente.
- Al regenerar la clave, la anterior queda **inmediatamente inválida**.

> Guarde la clave en un lugar seguro. Una vez cerrada la ventana, no puede recuperarse (solo regenerarse).

---

## Endpoint

### `POST /api/v1/account/moves`

Crea uno o más asientos contables.

#### Headers requeridos

| Header | Valor | Descripción |
|---|---|---|
| `Content-Type` | `application/json` | Tipo de contenido del body |
| `X-API-Key` | `<clave>` | API Key configurada en la compañía |

#### Body (JSON)

```json
{
    "entries": [
        {
            "date": "2026-05-13",
            "reference": "INT-TEST-002",
            "post": true,
            "lines": [
                {
                    "account": "11050501",
                    "description": "Registro ingreso por integración API",
                    "partner_vat": "890100577",
                    "cost_center": "CC-001",
                    "debit": 1000000.00,
                    "credit": 0.00
                },
                {
                    "account": "11051002",
                    "description": "Contrapartida pasivo integración API",
                    "partner_vat": "890100577",
                    "cost_center": "CC-001",
                    "debit": 0.00,
                    "credit": 1000000.00
                }
            ]
        }
    ]
}
```

#### Campos de la cabecera del asiento (`entries[]`)

| Campo | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `date` | `string` | Si | Fecha del asiento en formato `YYYY-MM-DD` |
| `reference` | `string` | Si | Referencia / número externo del asiento. Debe ser único por diario y compañía |
| `post` | `boolean` | Si | `true` para publicar el asiento, `false` para dejarlo en borrador |
| `lines` | `array` | Si | Lista de líneas del asiento (mínimo una) |

#### Campos de cada línea (`entries[].lines[]`)

| Campo | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `account` | `string` | Si | Código de la cuenta contable (ej: `"11050501"`) |
| `description` | `string` | Si | Descripción / nombre de la línea |
| `partner_vat` | `string` | Si | NIT o VAT del tercero (ej: `"890100577"`) |
| `cost_center` | `string` | Si | Código del centro de costo / cuenta analítica (ej: `"CC-001"`) |
| `debit` | `number` | Si | Valor débito. Usar `0.00` si la línea es crédito |
| `credit` | `number` | Si | Valor crédito. Usar `0.00` si la línea es débito |

---

## Respuestas

### HTTP 201 — Creado exitosamente

```json
{
    "status": "success",
    "data": [
        {
            "id": 1234,
            "name": "INTEG/2026/05/0001",
            "date": "2026-05-13",
            "reference": "INT-TEST-002",
            "state": "posted",
            "journal": "Diario de Integración"
        }
    ]
}
```

| Campo | Descripción |
|---|---|
| `id` | ID interno del asiento en Odoo |
| `name` | Nombre secuencial asignado por Odoo |
| `date` | Fecha del asiento |
| `reference` | Referencia enviada en el request |
| `state` | `posted` si fue publicado, `draft` si quedó en borrador |
| `journal` | Nombre del diario utilizado |

---

### HTTP 401 — No autorizado

```json
{
    "status": "error",
    "message": "Autenticación requerida. Envíe el header X-API-Key: <clave>."
}
```

```json
{
    "status": "error",
    "message": "API Key inválida o no autorizada."
}
```

---

### HTTP 422 — Error de validación

Se retorna cuando uno o más campos no pasan las validaciones. **No se crea ningún asiento** si hay al menos un error.

```json
{
    "status": "error",
    "message": "Se encontraron errores de validación. No se creó ningún asiento.",
    "errors": [
        "entries[0].account: No existe cuenta contable con código '9999' en la compañía 'Mi Empresa'.",
        "entries[0].partner_vat: No existe tercero con NIT/VAT '000000000'.",
        "entries[1].reference: La referencia 'INT-TEST-002' está duplicada en este mismo payload."
    ]
}
```

---

### HTTP 400 — Solicitud malformada

```json
{
    "status": "error",
    "message": "El cuerpo de la solicitud debe ser JSON válido (Content-Type: application/json)."
}
```

---

### HTTP 500 — Error de configuración

```json
{
    "status": "error",
    "message": "El diario de integración API no está configurado en la compañía. Configure el diario en Ajustes → Contabilidad → Integración API REST."
}
```

---

## Validaciones

| Validación | Descripción |
|---|---|
| **API Key** | Debe coincidir con la clave configurada en la compañía |
| **Referencia duplicada (payload)** | Si el mismo `reference` aparece dos veces en el payload, el segundo falla |
| **Referencia duplicada (BD)** | Se verifica que no exista ya un asiento con el mismo `reference` en el diario y compañía |
| **Cuenta contable** | Debe existir y pertenecer a la compañía |
| **Tercero (NIT/VAT)** | Debe existir un tercero registrado con ese NIT/VAT |
| **Centro de costo** | Debe existir una cuenta analítica con ese código |
| **Formato de fecha** | Debe ser `YYYY-MM-DD` (ISO 8601) |
| **Tipos numéricos** | `debit` y `credit` deben ser valores numéricos válidos |
| **Campos obligatorios** | Todos los campos de cabecera y línea son requeridos |

Todos los errores se acumulan antes de responder: si hay varios errores en el payload, la respuesta los incluye todos en una sola llamada.

---

## Ejemplo con curl

```bash
curl -X POST https://test-interejecutiva.odoo.com/api/v1/account/moves \
  -H "Content-Type: application/json" \
  -H "X-API-Key: WWjz_e0uOneyKLCYDfLv5qYma2zGOC9SV68_PLamJqQ" \
  -d '{
    "entries": [
        {
            "date": "2026-05-13",
            "reference": "INT-TEST-002",
            "post": true,
            "lines": [
                {
                    "account": "11050501",
                    "description": "Registro ingreso por integración API",
                    "partner_vat": "890100577",
                    "cost_center": "CC-001",
                    "debit": 1000000.00,
                    "credit": 0.00
                },
                {
                    "account": "11051002",
                    "description": "Contrapartida pasivo integración API",
                    "partner_vat": "890100577",
                    "cost_center": "CC-001",
                    "debit": 0.00,
                    "credit": 1000000.00
                }
            ]
        }
    ]
}'
```

---

## Ejemplo con Python (requests)

```python
import requests

url = "https://test-interejecutiva.odoo.com/api/v1/account/moves"
headers = {
    "Content-Type": "application/json",
    "X-API-Key": "WWjz_e0uOneyKLCYDfLv5qYma2zGOC9SV68_PLamJqQ",
}
payload = {
    "entries": [
        {
            "date": "2026-05-13",
            "reference": "INT-TEST-002",
            "post": True,
            "lines": [
                {
                    "account": "11050501",
                    "description": "Registro ingreso por integración API",
                    "partner_vat": "890100577",
                    "cost_center": "CC-001",
                    "debit": 1000000.00,
                    "credit": 0.00,
                },
                {
                    "account": "11051002",
                    "description": "Contrapartida pasivo integración API",
                    "partner_vat": "890100577",
                    "cost_center": "CC-001",
                    "debit": 0.00,
                    "credit": 1000000.00,
                },
            ],
        }
    ]
}

response = requests.post(url, json=payload, headers=headers)
print(response.status_code)
print(response.json())
```


