# Entrega a QA — Cotizador Web Safra (`website_quotes_safra`)

**Objetivo:** réplica del cotizador del portal de pedidos del cliente dentro de Odoo,
con paridad **visual** y **funcional** (habilitación dinámica de campos por sistema).

---

## 1. Cómo acceder y probar

| | |
|---|---|
| **URL del cotizador (Odoo)** | `/cotizador` (requiere usuario autenticado) |
| **Base de datos de prueba** | `safra_05` |
| **Portal del cliente (referencia de comparación)** | https://portal.safrasas.com/ → menú *Pedidos y Cotizaciones* → **Agregar Producto** (`/Order/AddProduct?reset=True`) |
| **Flujo de prueba** | Seleccionar **Sistema** → llenar Ancho/Alto/Cantidad → elegir Referencia y Color → revisar accesorios, ficha técnica, totales |

> **La forma de validar es comparar lado a lado**: misma selección en el portal del cliente
> y en `/cotizador` de Odoo, y verificar que coincidan campos, opciones, orden y habilitación.

---

## 2. Qué se construyó (alcance de esta entrega)

- **Los 33 sistemas** del portal, configurados y funcionando:
  - *Enrollable:* Enrollable, Premium, 2 en 1
  - *Romana:* Tradicional, Top Down, Premium
  - *Sheer:* Sheer Elegance, Sheer 2 en 1
  - *Vertical:* Vertical, Vertical Premium, Vertical Irregular, Lama Vertical, Lama Vintage
  - *Vintage:* Vintage, Vintage Sencilla, Hanas
  - *Panel:* Panel Japonés, Panel Dúo
  - *Cortina:* Onda Moderna, Pliegue Francés, Abrazadera
  - *Riel armado:* Riel Armado, Riel Armado Cortina, Riel Armado Verticales
  - *Motor ensamblado:* Tubular, Panel
  - *Especiales:* Veneciana, Telos, Cenefa PVC, Papel Colgadura, Película, Lienzo
- **Paridad visual** con el portal: layout de una columna (etiqueta / control / ayuda / precio),
  toggles Sí/No, addons de unidad (mts/und/metros), bloque de **Producto + Ficha técnica + Disponibilidad
  + Precio Base/Descuento**, encabezado "Accesorios", totales (Subtotal / IVA / Total).
- **Habilitación dinámica de campos** igual que el cliente (p. ej. al elegir Motor aparecen
  Control/Canal/Soporte; al elegir Cenefa aparecen sus sub-opciones).
- **Catálogo de telas** (146 telas con sus colores) **filtrado por sistema**: el desplegable de
  Referencia cambia según el sistema elegido.
- **Imagen de producto** (círculo sobre textura) + **ficha técnica** (ancho/alto mín-máx, mecanismo) por sistema.

---

## 3. Cómo está configurado (para entender qué es "configurable")

Todo el cotizador es **configurable por datos** (config-as-code), no está "quemado" en código:

- **`safra.system`** — cada sistema (código, nombre, ficha técnica: ancho/alto mín-máx, mecanismo).
- **`safra.field`** + **`safra.field.option`** — catálogo global de campos y sus opciones.
- **`safra.system.field`** — qué campos aplica cada sistema, su **orden**, y **overrides por sistema**
  (etiqueta, opciones, dependencias) — así un mismo campo (p. ej. "Cenefa") se llama y se comporta
  distinto en cada sistema sin duplicarlo.
- **`safra.fabric` / `safra.fabric.color`** — telas, colores, imagen, y a qué sistemas pertenece cada tela.

> **Implicación para QA:** si un campo, opción, etiqueta u orden no coincide con el portal,
> es un **ajuste de datos** (no de programa). Reportarlo con detalle permite corregirlo rápido.

---

## 4. Plan de pruebas sugerido (checklist por sistema)

Recomendado empezar por la familia **Enrollable** (la más madura) y avanzar por familias.

Para **cada sistema**, comparar contra el portal:

- [ ] **Campos presentes** y su **orden** coinciden con el portal.
- [ ] **Nombres** de los campos coinciden (p. ej. "Tipo de Perfil", "Cenefa PVC").
- [ ] **Opciones** de cada lista desplegable coinciden.
- [ ] **Habilitación dinámica**: al cambiar un campo "padre" aparecen/desaparecen los dependientes
      (Motor → Control/Canal/Soporte/Interruptor; Cenefa → Laterales/Dividida/Forrada; etc.).
- [ ] **Ficha técnica**: ancho/alto mínimo y máximo, y mecanismo (si aplica).
- [ ] **Telas (Referencia)**: el listado corresponde al sistema; al elegir tela se cargan sus **colores**.
- [ ] **Imagen** del producto (si la tela tiene imagen) o el marcador "imagen no encontrada".
- [ ] **Producto** (nombre calculado) se arma con sistema + referencia + color.

---

## 5. Fuera de alcance de ESTA entrega (NO reportar como bug)

Estos puntos están identificados y planificados para fases siguientes:

1. **Precios**: el cálculo es **provisional** (`ancho × alto × 1000`). Precio Base, Descuento
   y Total **no reflejan listas reales** todavía.
2. **Imágenes de producto**: cargadas para las **telas de Enrollable**; el resto de telas muestran
   el marcador "imagen no encontrada" (igual que el cliente cuando no existe la imagen).
3. **Guardado y validaciones**: el botón *Guardar* crea la cotización, pero **no está validado
   end-to-end** (requeridos, ancho/alto máximo por producto, mensajes de error).
4. **Diferencias menores por sistema**: pueden existir pequeñas diferencias de etiqueta u opciones
   en sistemas distintos de Enrollable/Romana/Premium (replicados con mayor detalle). Reportarlas
   igual; son ajustes de datos.

---

## 6. Cómo reportar hallazgos (para corrección ágil)

Por cada hallazgo, incluir:

- **Sistema** (ej. "Vertical Premium").
- **Campo** afectado.
- **Esperado** (cómo está en el portal del cliente) vs **Obtenido** (en Odoo).
- **Tipo**: campo faltante / campo de más / nombre / opción / orden / habilitación / ficha / tela / imagen.
- **Captura de pantalla** de ambos (portal y Odoo) si es posible.

---

## 7. Nota técnica de despliegue

- El módulo aplica su configuración vía **migraciones** (`migrations/19.0.0.0.x/`) que permiten
  reaplicar los datos en bases ya instaladas. Al actualizar (`-u website_quotes_safra`) la config
  queda como la fuente de verdad.
- En el ambiente de prueba local se fijó temporalmente la contraseña del admin para visualización;
  **debe usarse el acceso/credenciales propios del ambiente de QA**.
