# Storage Analyzer - Módulo Odoo 16

Módulo para análisis y monitoreo del consumo de almacenamiento en instancias Odoo SH.

## Características

- **Análisis de Base de Datos**: Tamaño total de PostgreSQL con desglose por tablas
- **Análisis de Filestore**: Cálculo del espacio ocupado por archivos adjuntos
- **Detalle por Modelos**: Conteo de registros y tamaño por tabla
- **Dashboard Visual**: Gráficos interactivos con OWL (pie chart, barras, tendencias)
- **Histórico de Crecimiento**: Seguimiento de evolución del almacenamiento
- **Alertas Configurables**: Notificaciones por umbral (advertencia/crítico)
- **Análisis Automático**: Cron job para ejecución diaria

## Instalación

1. Copiar el módulo a la carpeta de addons:
   ```bash
   cp -r storage_analyzer /ruta/a/odoo/addons/
   ```

2. Actualizar lista de aplicaciones en Odoo

3. Instalar el módulo "Storage Analyzer"

## Configuración

Ir a **Ajustes > General Settings > Storage Analyzer**:

- **Límite de Almacenamiento (GB/MB)**: Capacidad contratada para cálculo de porcentajes
- **Umbral de Advertencia (%)**: Nivel para alertas de precaución (default: 70%)
- **Umbral Crítico (%)**: Nivel para alertas críticas (default: 85%)
- **Análisis Automático Diario**: Activar/desactivar cron
- **Días de Retención**: Período de conservación de análisis históricos

## Uso

### Dashboard
- Menú: **Storage Analyzer > Dashboard**
- Vista general con KPIs, gráficos y tendencias
- Ejecutar nuevo análisis desde el dashboard

### Análisis Manual
- Menú: **Storage Analyzer > Análisis > Crear**
- Configurar fecha y ejecutar
- Revisar resultados en pestañas: Resumen, Tablas, Adjuntos

### Análisis Automático
El cron job `Storage Analyzer: Análisis Diario Automático` se ejecuta diariamente a las 00:00.

### Detalles
- **Tablas**: Listado completo con filtros por categoría y tamaño
- **Adjuntos**: Top 100 archivos más grandes con tipo y ubicación
- **Tendencias**: Evolución histórica con proyecciones

## Estructura del Módulo

```
storage_analyzer/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── storage_analysis.py           # Modelo principal
│   ├── storage_analysis_table.py     # Detalle por tabla
│   ├── storage_analysis_attachment.py # Detalle de adjuntos
│   ├── storage_analysis_trend.py     # Tendencias históricas
│   └── res_config_settings.py        # Configuración
├── views/
│   ├── storage_analysis_views.xml
│   ├── storage_analysis_table_views.xml
│   ├── storage_analysis_attachment_views.xml
│   ├── storage_analysis_trend_views.xml
│   ├── storage_config_settings_views.xml
│   └── storage_menus.xml
├── data/
│   ├── sequence.xml
│   └── cron_jobs.xml
├── security/
│   ├── storage_security.xml
│   └── ir.model.access.csv
└── static/src/components/
    ├── dashboard/
    │   ├── dashboard.js              # Componente OWL principal
    │   ├── dashboard.xml
    │   └── dashboard.scss
    └── charts/
        ├── storage_charts.js         # Gráficos reutilizables
        ├── storage_charts.xml
        └── storage_charts.scss
```

## Modelos

### storage.analysis
Análisis completo de almacenamiento con:
- Tamaño total de BD (MB)
- Tamaño de filestore (MB)
- Total de adjuntos
- Líneas de detalle por tabla
- Líneas de detalle de adjuntos

### storage.analysis.table
Detalle por tabla de PostgreSQL:
- Nombre de tabla
- Modelo Odoo relacionado
- Cantidad de registros
- Tamaño de datos, índices, TOAST
- Porcentaje del total

### storage.analysis.attachment
Top 100 adjuntos más grandes:
- Nombre y tipo MIME
- Tamaño en MB
- Tipo de almacenamiento (DB/Filestore)
- Modelo relacionado

### storage.analysis.trend
Resumen diario para gráficos de tendencia:
- Tamaños por día
- Tasa de crecimiento
- Fecha proyectada de llenado

## Seguridad

Grupos:
- **Usuario de Análisis de Almacenamiento**: Lectura de todos los análisis
- **Administrador de Análisis de Almacenamiento**: CRUD completo

## Compatibilidad

- Odoo 16 Community y Enterprise
- Compatible con Odoo SH (sin modificaciones de servidor)
- No requiere dependencias externas

## Limitaciones en Odoo SH

El módulo está diseñado para funcionar dentro de las restricciones de Odoo SH:
- No modifica configuraciones del servidor PostgreSQL
- Acceso al filestore mediante rutas estándar de Odoo
- Consultas SQL solo de lectura a vistas del sistema PostgreSQL

## Licencia

LGPL-3

## Autor

Odone - https://www.odone.com
