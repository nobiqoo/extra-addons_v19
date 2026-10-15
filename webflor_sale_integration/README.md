# webflor_sale_integration

Módulo Odoo 19 que extiende `sale.order` y `sale.order.line` con los campos
comerciales, logísticos y de integración requeridos por WebFlor.

## Estructura en el formulario

- **Pestaña "WebFlor"** (nueva, al lado de "Otra información"): agrupa
  - **Información WebFlor**: N° Pedido WebFlor, N° Invoice WebFlor, Tipo de
    Venta, Término de Negociación, Tipo de Orden.
  - **Logística WebFlor - Despacho Internacional**: Agencia de Carga,
    Aerolínea, Fecha de Entrega WebFlor, Fecha de Despacho WebFlor, Número
    de Guía Madre (MAWB), Número de Guía Hija (HAWB), Número de Guía Nieta.
- **Líneas de la orden**: columnas opcionales "Id Producto WebFlor" y
  "Referente" (visibles por defecto, se pueden ocultar desde el ícono de
  columnas opcionales de la lista).

## Decisiones de diseño

- **Tipo de Venta / Término de Negociación / Tipo de Orden → `Char`.**
  Se completan vía integración con WebFlor (no manualmente desde una lista
  configurable en Odoo), así que se implementan como texto libre. *(Versión
  anterior de este módulo los manejaba como `Many2one` a un modelo
  configurable; se revirtió tras la revisión porque no aplica al flujo real
  de estos campos.)*
- **Agencia de Carga / Aerolínea → `Char`.** Igual que los 3 campos de
  clasificación, se completan vía integración con WebFlor, así que se
  implementan como texto libre. *(Versión anterior los manejaba como
  `Many2one` a `res.partner`; se revirtió por el mismo motivo.)*
- **Guías (MAWB/HAWB/Nieta)**: `Char`, sin formato/validación específica (no
  se especificó una estructura de dígitos a validar).
- **N° Pedido / Invoice WebFlor**: `copy=False` — al duplicar una cotización
  en Odoo no tiene sentido arrastrar el identificador externo del pedido
  original.
- **Fecha de Entrega WebFlor / Fecha de Despacho WebFlor**: se les agregó el
  sufijo "WebFlor" en la etiqueta porque la pestaña "Otra información" ya
  trae de fábrica un campo "Fecha de Entrega" (grupo Entrega) — con el mismo
  nombre se prestaba a confusión al ver dos campos idénticos en el mismo
  formulario.
- Todos los campos son campos reales y persistentes del modelo (no
  computados ni relacionados), por lo que quedan disponibles de forma
  automática para importación/exportación, API externa, automatizaciones y
  reportería estándar (vistas pivot, agrupaciones, etc.) sin trabajo
  adicional.
- No se modifica ningún método ni comportamiento estándar de `sale` — solo se
  agregan campos y vistas heredadas, por lo que el flujo estándar de Ventas
  no se ve afectado.

## Sobre las columnas de línea (Id Producto WebFlor / Referente)

En una revisión previa estas dos columnas no aparecían en la lista de líneas
ni como columna opcional oculta. El modelo ya las traía correctamente; el
xpath de la vista se reescribió para anclarse directamente al `<tree>`/`<list>`
del campo `order_line` (con `position="inside"`) en lugar de a un `<field>`
puntual como `product_id`, para que no dependa de la estructura interna
exacta de esa lista ni de si esta instancia usa la etiqueta `<tree>` o
`<list>`. Si tras actualizar el módulo siguen sin aparecer, lo más probable
es que otro módulo ya instalado también herede ese mismo `<tree>`/`<list>`
con un `position="replace"` completo y esté pisando esta herencia — en ese
caso hay que localizar esa vista (Ajustes > Técnico > Vistas, filtrando por
modelo `sale.order.line` o por el modelo del campo `order_line`) y coordinar
el orden/contenido de ambas herencias.

## Supuesto a verificar en la instancia real

El anclaje `//page[@name='other_information']` para insertar la pestaña
"WebFlor" a continuación es estable en Odoo estándar. Si la localización
colombiana u otro módulo ya instalado renombra o reestructura esa página,
el `xpath` puede requerir un ajuste puntual (se vería como error al
instalar/actualizar el módulo).

## Fuera de alcance (no pedido, próximos pasos posibles)

- Propagar `webflor_referente` / `webflor_product_code` a las líneas de
  factura (`account.move.line`) al facturar. Si lo necesitan, se agrega
  sobrescribiendo `_prepare_invoice_line()`.
- Columnas de estos campos en la vista lista de cotizaciones/pedidos, y
  filtros/agrupaciones en la vista de búsqueda.
