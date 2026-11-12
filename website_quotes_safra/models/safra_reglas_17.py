# -*- coding: utf-8 -*-
"""Sprint 1.7: validaciones del archivo «Restricciones y Validaciones de
Productos» de Safra escritas como reglas del portal (Configuración >
Validaciones). Se siembran una sola vez por base
(safra.validation.rule._seed_sprint17_safra); después las administra el
funcional y el módulo no las vuelve a tocar."""

# Reunión 09-nov (fila 68): V_REQUIERE_MOTOR sale cuando la persiana no se
# puede fabricar manual (ancho, alto o peso) pero sí con motor, y pide marcarlo.
MENSAJE_REQUIERE_MOTOR_ANTERIOR = (
    'E13095: Por la medida de la persiana y el peso de la tela, la persiana debe ir motorizada.')
MENSAJE_REQUIERE_MOTOR = (
    'E13095: Por la medida y el peso de la persiana no se puede fabricar manual, pero sí con '
    'motor ({tubo_motor}): marque «Con motor» para fabricarla.')

# Reglas nuevas: código, función del archivo de Safra, severidad, momento,
# campo que la dispara, sistemas, condición y mensaje.
REGLAS = [
    {
        'code': 'V_ESTAMPADO_FUERA_SERVICIO',
        'name': 'Estampado fuera de servicio (interruptor)',
        'funcion_safra': 'ValidaEstampado',
        'severity': 'error', 'momento': 'campo', 'trigger_field': 'design_print',
        'systems': (), 'active': False,
        'condition': 'design_print',
        'message': (
            'E13095: Temporalmente, los estampados están FUERA DE SERVICIO. Agradecemos su comprensión.'),
        'description': (
            'Fila [0] #1. Safra: poder restringir el servicio cuando falla la máquina sin quitar la marca «estampable» de la tela. Se entrega INACTIVA: el funcional la activa cuando la impresora falle y la desactiva al volver el servicio.'),
    },
    {
        'code': 'V_ESTAMPADO_TELA',
        'name': 'Estampado solo en telas estampables',
        'funcion_safra': 'ValidaEstampado',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': (), 'active': True,
        'condition': 'design_print and tela and not tela.is_printable',
        'message': 'E10034: La tela «{tela.name}» no es estampable.',
        'description': (
            'Fila [0] #1. El portal ya oculta y limpia «Diseño de impresión» si la tela no es estampable (flag printable); esta regla es el respaldo del servidor para un valor que quede pegado al editar el pedido o cambiar la tela.'),
    },
    {
        'code': 'V_ESTAMPADO_SHEER',
        'name': (
            'Sin impresión sobre telas SHEER (Enrollable, Premium, Panel, Panel Duo)'),
        'funcion_safra': 'ValidaEstampado',
        'severity': 'error', 'momento': 'campo', 'trigger_field': 'design_print',
        'systems': ('01', '06', '11', '54'), 'active': True,
        'condition': "design_print and tela and 'SHEER' in (tela.name or '').upper()",
        'message': (
            'E13095: En este sistema de persiana, no se permite impresión sobre tela «{tela.name}».'),
        'description': (
            'Fila [0] #1. Safra: si el nombre de la tela incluye SHEER y se fabrica en Enrollable/Premium/Panel/Panel Duo, bloquear. Hoy bloquea «Sheer Screen» (0504058), la única tela Sheer marcada estampable. Panel Duo (54) hoy no tiene el campo de impresión.'),
    },
    {
        'code': 'V_ESTAMPADO_ANADIDO',
        'name': 'Sin estampado en tela añadida más ancha que el rollo',
        'funcion_safra': 'ValidaEstampado',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('01', '06'), 'active': True,
        'condition': (
            'design_print and tela and tela.is_anadido and ancho_rollo and ancho > ancho_rollo'),
        'message': (
            'E13095: No se permite estampar telas añadidas cuando el ancho real de la persiana supera el ancho del rollo. Por favor seleccione un ancho de tela mayor.'),
        'description': (
            'Fila [0] #1 (Safra: Mantener). Usa la marca «Añadido» (U_Añadido) de la referencia: hoy ninguna tela la tiene, así que no dispara hasta que Safra marque las telas añadibles.'),
    },
    {
        'code': 'V_ESTAMPADO_SHEER_ELEGANCE',
        'name': 'Sheer Elegance: ancho máximo para estampar',
        'funcion_safra': 'ValidaEstampado',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('02',), 'active': True,
        'condition': (
            'maximo = ancho_max_impresion\n'
            'result = design_print and ancho > maximo'),
        'message': (
            'E13095: Para el Sistema Sheer Elegance, el ancho máximo que debe tener la persiana para estampación es de {maximo} metros.'),
        'description': (
            'Fila [0] #1. Safra: 2,5 m, parametrizable porque depende de la impresora: el valor se cambia en Ajustes → Cotizador Safra → Estampación → Ancho máximo de impresión.'),
    },
    {
        'code': 'V_PLANO_COORDINADO',
        'name': 'Tipo de plano: mismo coordinado por plano y localización',
        'funcion_safra': 'ValidaTipoPlanoImplementacion',
        'severity': 'error', 'momento': 'pedido', 'trigger_field': None,
        'systems': ('02', '06', '10', '55'), 'active': True,
        'condition': (
            "mismo_plano = [l for l in otras_lineas if l['atributos'].get('tipo_plano') == tipo_plano\n"
            "               and l['localizacion'].strip().lower() == localizacion.strip().lower()]\n"
            "result = bool(tipo_plano) and any((l['linea'].coordinado or '') != (coordinado or '') for l in mismo_plano)"),
        'message': (
            'E13095: Los productos del tipo de plano [{tipo_plano}] y Localización [{localizacion}] contienen diferentes valores de Coordinado. Verificar que correspondan al mismo valor.'),
        'description': (
            'Fila [1] #2 (Mantener). Compara el Coordinado de las persianas con el mismo Tipo de Plano en la misma Localización. Sistemas donde hoy está el campo Tipo de Plano.'),
    },
    {
        'code': 'V_ALINEADO_MAXIMO',
        'name': 'Alineado: máximo de persianas por localización (enrollables)',
        'funcion_safra': 'ValidaAlineadoImplements',
        'severity': 'error', 'momento': 'pedido', 'trigger_field': None,
        'systems': ('01', '02', '06', '32', '61'), 'active': True,
        'condition': (
            'maximo = 4\n'
            "misma_loc = [l for l in lineas if l['alineado'] and l['sistema'] in ('01', '02', '06', '32', '61')\n"
            "             and l['localizacion'].strip().lower() == localizacion.strip().lower()]\n"
            "unidades = sum(l['cantidad'] for l in misma_loc)\n"
            'result = alineado and unidades > maximo'),
        'message': (
            'E13095: No se permite alinear más de {maximo} persianas en el mismo espacio. Localización: [{localizacion}]. Desmarque la opción Alineado en las persianas que sobran.'),
        'description': (
            'Fila [3] #4, regla 5 de la simplificación de Safra: máximo 4 persianas enrollables alineadas por localización. Cuenta unidades (suma de cantidades).'),
    },
    {
        'code': 'V_PERFIL_TELA',
        'name': 'Perfilería compatible con la tela (restricción unificada)',
        'funcion_safra': 'ValidaReferenciaPerfileria / ValidaPerfileria / ValidaInventario',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': (), 'active': True,
        'condition': (
            '# Códigos de las líneas de la referencia PERFIL\n'
            "ESTANDAR = ('I100000440',)\n"
            "DELUXE = ('I100003081', 'I100003083', 'I100003084')\n"
            'elegido = perfil or perfil_sheer\n'
            "sheer_screen = [t for t in (tela, tela_2) if t and 'SHEER SCREEN' in (t.name or '').upper()\n"
            "                and t.code not in ('054304', '054305')]\n"
            "cristal = tela.code == '0504207' and elegido in ESTANDAR and sistema != '16'\n"
            "poliester = tela.code == '0504063' and elegido in ESTANDAR and sistema == '02'\n"
            "deluxe = sistema in ('02', '61') and bool(sheer_screen) and elegido in DELUXE\n"
            "mensaje = ('La referencia Screen Jacquard Cristal no aplica para perfil Standard.' if cristal\n"
            "           else 'Para la referencia de la tela seleccionada no se permite el ingreso de pedidos con el tipo de perfil Estandar.' if poliester\n"
            "           else 'El perfil Deluxe no está disponible para la referencia de tela seleccionada, por favor seleccione otro perfil.')\n"
            'result = bool(tela) and (cristal or poliester or deluxe)'),
        'message': 'E13095: {mensaje}',
        'description': (
            'Filas [6] #7, [7] #8 y [14] #15 («unificar en una sola restricción»). Tres casos con su mensaje: Screen Jacquard Cristal (0504207) con perfil Estándar fuera de Telos (16); Sheer Poliester Blackout (0504063) con Estándar en Sheer Elegance; perfil Deluxe con Sheer Screen (salvo Emely 054304 y Parma 054305) en Sheer Elegance y Sheer 2 en 1. Para agregar un caso se añade una línea a la condición. El aviso W13044 (Blackout con Estándar/Lujo) queda pendiente de la lista de Safra.'),
    },
    {
        'code': 'V_PERFIL_COSTURA',
        'name': 'Aviso: costura en el perfil por ancho o añadido',
        'funcion_safra': 'ValidaTelaVsPerfil',
        'severity': 'info', 'momento': 'linea', 'trigger_field': None,
        'systems': ('01', '06'), 'active': True,
        'condition': (
            "ESTANDAR = ('I100000440',)\n"
            "LUJO_CUADRADO = ('I100000442', 'I100001746', 'I100001852', 'I100001896')\n"
            "screen = bool(tela) and 'SCREEN' in (tela.name or '').upper()\n"
            'anadido = bool(tela) and tela.is_anadido and bool(ancho_rollo) and ancho > ancho_rollo\n'
            'costura_estandar = screen and perfil in ESTANDAR and ancho > 3.90\n'
            'costura_lujo = screen and perfil in LUJO_CUADRADO and ancho > 3.17\n'
            'costura_anadido = anadido and perfil in LUJO_CUADRADO\n'
            "mensaje = ('La persiana con añadido, llevará costura en el perfil Lujo ó Cuadrado.' if costura_anadido\n"
            "           else 'La persiana por su ancho superior a 3.90m, llevará costura en el perfil Estándar.' if costura_estandar\n"
            "           else 'La persiana por su ancho superior a 3.17m, llevará costura en el perfil (Lujo ó Cuadrado).')\n"
            'result = costura_estandar or costura_lujo or costura_anadido'),
        'message': 'I13095: {mensaje}',
        'description': (
            'Fila [39] #40 (unificada). Avisos informativos de costura del perfil en telas Screen de Enrollable y Premium: Estándar > 3,90 m; Lujo/Cuadrado > 3,17 m; con añadido (marca «Añadido» de la tela, hoy sin datos). El aviso W13044 de arrugas con Perfil Lujo queda pendiente de la lista de telas Screen de Safra.'),
    },
    {
        'code': 'V_MANDO_MOTOR_VINTAGE',
        'name': 'Vintage motorizada: mando derecho',
        'funcion_safra': 'ValidaMando',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('42', '63'), 'active': True,
        'condition': "con_motor and mando_position == '2'",
        'message': (
            'E13095: El Motor debe ir [mando derecho] para que estéticamente no sea visible. El Motor siempre se instala al lado derecho en Vintage motorizadas.'),
        'description': (
            'Fila [10] #11. Respaldo del servidor: con el mando activo en Vintage (ver required_fields) y la opción «Derecho» que se elige sola con motor (otros_ajustes_config), esta regla bloquea si queda Izquierdo. Valores del mando en 42/63: 1 Derecho, 2 Izquierdo.'),
    },
    {
        'code': 'V_MANDO_MOTOR_VERTICAL',
        'name': 'Vertical/Hanas motorizada: sin mando izquierdo',
        'funcion_safra': 'ValidaMando (verticales)',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('40', '41', '53', '55'), 'active': True,
        'condition': "con_motor and mando_position == '2'",
        'message': 'E13095: No se permite mando izquierdo si la persiana es motorizada.',
        'description': (
            'Fila [78] #22 (Mantener). Solo tiene efecto cuando se active el campo Mando en estos sistemas (hoy inactivo; ver required_fields). Valores: 1 Derecho, 2 Izquierdo. Vintage (42/63) va en V_MANDO_MOTOR_VINTAGE con el mensaje de la fila [10].'),
    },
    {
        'code': 'V_CENEFA_PVC_DIVIDIDA',
        'name': 'Cenefa PVC de más de 3 m: va dividida (advertencia)',
        'funcion_safra': 'ValidaCenefaPvc / ValidaAnchoCenefaPvc',
        'severity': 'warning', 'momento': 'linea', 'trigger_field': None,
        'systems': (), 'active': True,
        'condition': (
            'maximo = 3.0\n'
            "result = cenefa_panel == '054328' and ancho > maximo"),
        'message': (
            'E13095: El ancho solicitado supera los {maximo:g} metros, debe ir dividida.'),
        'description': (
            'Filas [13] #14 y [82] #20: de error a advertencia y un solo mensaje (la unión es imperceptible). 054328 = línea PVC CLASICA de la referencia Cenefas. El mínimo de 0,30 m ya lo da V_RANGO_ANCHO. La opción «¿Cenefa dividida? = Si» se sigue eligiendo sola; para que forzar «No» no bloquee (V_OPCION_AUTO es error) ver needs_code.'),
    },
    {
        'code': 'V_HANAS_COORDINADO',
        'name': 'Hanas: solo coordinado Blanco',
        'funcion_safra': 'ValidaInventario',
        'severity': 'error', 'momento': 'campo', 'trigger_field': 'coordinado',
        'systems': ('41',), 'active': True,
        'condition': "coordinado and coordinado != 'blanco'",
        'message': (
            'E13095: Para este producto solo se permite color de Coordinado Blanco. Cambie el color de coordinado.'),
        'description': (
            'Fila [14] #15. Además conviene dejar en Hanas solo la opción Blanco del Coordinado (otros_ajustes_config); la regla es el respaldo.'),
    },
    {
        'code': 'V_ESTRUCTURA_CABEZAL',
        'name': 'Componentes: cabezal obligatorio (Premium)',
        'funcion_safra': 'ValidaComponentes',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('06',), 'active': True,
        'condition': 'not cabezal_tipo',
        'message': 'E13095: No se ha identificado el componente [Cabezal].',
        'description': (
            'Fila [18] #19: el mensaje de cabezal solo para productos con cabezal (ej. Enrollable Premium). Sin cabezal elegido la tabla de estructura toma la primera regla sin avisar. Sheer Elegance (02) también lleva cabezal pero hoy no tiene líneas de Cabezal asignadas (pendiente_safra).'),
    },
    {
        'code': 'V_COVERLIGHT_LUJO',
        'name': 'Cover Light no compatible con Perfil de Lujo',
        'funcion_safra': 'ValidaCoverLight',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('01', '06', '32', '61'), 'active': True,
        'condition': (
            "LUJO = ('I100000442', 'I100001746')\n"
            "result = cover_light_profile not in ('', 'sin', '0') and (perfil in LUJO or perfil_sheer in LUJO or perfileria2 in LUJO)"),
        'message': (
            'E13095: El Perfil CoverLight no es compatible con Perfil de Lujo. Por favor seleccione otra opción de perfil.'),
        'description': (
            'Fila [25] #26 (Safra mantiene esta parte; la de 6 m se quita). Perfil Lujo = líneas I100000442 (Ivory) e I100001746 (Gris) de la referencia PERFIL.'),
    },
    {
        'code': 'V_ALINEADO_ORIENTACION',
        'name': 'Alineado: misma orientación del enrollado',
        'funcion_safra': 'ValidaEnrolleVsAlineado',
        'severity': 'error', 'momento': 'pedido', 'trigger_field': None,
        'systems': ('01', '02', '06', '32', '61'), 'active': True,
        'condition': (
            "misma_loc = [l for l in otras_lineas if l['alineado'] and l['sistema'] in ('01', '02', '06', '32', '61')\n"
            "             and l['localizacion'].strip().lower() == localizacion.strip().lower()]\n"
            "result = alineado and any(l['linea'].orientation != orientation for l in misma_loc)"),
        'message': (
            "E13066: Sólo se pueden 'Alinear' las persianas donde la [Orientación del enrollado] va en el mismo sentido. Localización [{localizacion}]."),
        'description': (
            'Fila [26] #27: Safra mantiene solo la validación de enrollado (las otras ya están en Alineado). Compara las alineadas de la misma localización.'),
    },
    {
        'code': 'V_ALINEADO_AMBIENTE',
        'name': 'Misma tela y color en la misma localización: deben ir alineadas',
        'funcion_safra': 'ValidaAlineadoMismoAmbiente',
        'severity': 'error', 'momento': 'pedido', 'trigger_field': None,
        'systems': ('01', '02', '06', '32', '61'), 'active': True,
        'condition': (
            "iguales = [l for l in otras_lineas if l['sistema'] == sistema and l['tela'] == tela and l['color'] == color\n"
            "           and l['localizacion'].strip().lower() == localizacion.strip().lower()]\n"
            "result = bool(tela) and bool(localizacion) and not alineado and any(round(l['alto'], 3) == round(alto, 3) for l in iguales)"),
        'message': (
            'E13039: Las persianas que van en un mismo ambiente y son de la misma tela deben ir Alineadas. Localización [{localizacion}], tela «{tela.name}»: marque la opción Alineado.'),
        'description': (
            'Fila [28] #29. Safra quiere que el portal marque Alineado solo (needs_code); mientras tanto, y como respaldo, el servidor lo exige cuando hay otra persiana del mismo sistema, tela, color, localización y alto. Con altos distintos sale la advertencia W13042 (V_ALINEADO_AMBIENTE_ALTO) y no se exige, para no chocar con V_ALINEADO_FRANJAS.'),
    },
    {
        'code': 'V_ALINEADO_AMBIENTE_ALTO',
        'name': (
            'Misma tela en la misma localización con alto distinto: no saldrán alineadas'),
        'funcion_safra': 'ValidaAlineadoMismoAmbiente',
        'severity': 'warning', 'momento': 'pedido', 'trigger_field': None,
        'systems': ('01', '02', '06', '32', '61'), 'active': True,
        'condition': (
            "iguales = [l for l in otras_lineas if l['sistema'] == sistema and l['tela'] == tela and l['color'] == color\n"
            "           and l['localizacion'].strip().lower() == localizacion.strip().lower()]\n"
            "result = bool(tela) and bool(localizacion) and not alineado and bool(iguales) and all(round(l['alto'], 3) != round(alto, 3) for l in iguales)"),
        'message': (
            'W13042: Persianas no saldrán alineadas. Diferente alto. Localización [{localizacion}], tela «{tela.name}».'),
        'description': (
            'Fila [28] #29: advertencia cuando la misma tela y color van en la misma localización sin alinear y con alto distinto.'),
    },
    {
        'code': 'V_SECUENCIA_TUBO_DEP',
        'name': 'Soporte dependiente: tubo mínimo R16',
        'funcion_safra': 'ValidaTubo',
        'severity': 'error', 'momento': 'pedido', 'trigger_field': None,
        'systems': ('01', '02', '06'), 'active': True,
        'condition': (
            "(linea.soporte_izq == 'DEP' or linea.soporte_der == 'DEP') and estructura['tubo'] == 'R8'"),
        'message': (
            'E13035: Para usar soporte Dependiente, el tubo debe ser de calibre mínimo R16.'),
        'description': (
            'Fila [29] #30 (Safra: Mantener E13035). Al finalizar el pedido el tubo ya está unificado al mayor de la secuencia. Hoy R8 solo sale en la tabla manual de 0,30 a 2,00 m. Alternativa por código: que la unificación suba a R16 cuando hay DEP (needs_code).'),
    },
    {
        'code': 'V_SECUENCIA_ANCHO',
        'name': 'Mismo cabezal: ancho total máximo 5,80 m',
        'funcion_safra': 'AnchoMaximoPersianaMismoCabezal',
        'severity': 'error', 'momento': 'pedido', 'trigger_field': None,
        'systems': ('01', '02', '06'), 'active': True,
        'condition': (
            'maximo = 5.80\n'
            'nombre = sequence_name.strip().lower()\n'
            "total = sum(l['ancho'] for l in lineas if l['linea'].same_header and l['secuencia'].strip().lower() == nombre)\n"
            'result = same_header and bool(nombre) and total > maximo'),
        'message': (
            'E13040: Ancho Total de las persianas en un mismo Cabezal supera el tamaño máximo del Perfil: {maximo:.2f} m. Ancho Total del mismo cabezal: [{total:.2f}]m en la secuencia [{sequence_name}].'),
        'description': (
            'Fila [32] #33 (Mantener). Suma el ancho de las persianas con «Mismo cabezal» y el mismo nombre de secuencia. El máximo se cambia en la primera línea.'),
    },
    {
        'code': 'V_SECUENCIA_COORDINADO',
        'name': 'Secuencia: mismo coordinado',
        'funcion_safra': 'ValidaMismoAmbiente',
        'severity': 'error', 'momento': 'pedido', 'trigger_field': None,
        'systems': ('01', '02', '06', '08', '10', '39'), 'active': True,
        'condition': (
            'nombre = sequence_name.strip().lower()\n'
            "grupo = [l for l in otras_lineas if l['linea'].same_header and l['secuencia'].strip().lower() == nombre]\n"
            "result = same_header and bool(nombre) and any((l['linea'].coordinado or '') != (coordinado or '') for l in grupo)"),
        'message': (
            'E13073: Las persianas de una misma secuencia deben tener el mismo coordinado. Secuencia [{sequence_name}].'),
        'description': (
            'Fila [33] #34. Coherencia entre las persianas de un mismo cabezal (respaldo del servidor; la revisión dentro del configurador de secuencia es needs_code).'),
    },
    {
        'code': 'V_SECUENCIA_CABEZAL',
        'name': 'Secuencia: mismo cabezal',
        'funcion_safra': 'ValidaMismoAmbiente',
        'severity': 'error', 'momento': 'pedido', 'trigger_field': None,
        'systems': ('02', '06'), 'active': True,
        'condition': (
            'nombre = sequence_name.strip().lower()\n'
            "grupo = [l for l in otras_lineas if l['linea'].same_header and l['secuencia'].strip().lower() == nombre]\n"
            "result = same_header and bool(nombre) and any((l['atributos'].get('cabezal_tipo') or '') != cabezal_tipo for l in grupo)"),
        'message': (
            'E13074: Las persianas de una misma secuencia deben tener el mismo mecanismo, cabezal y tubo en todas sus componentes. Es necesario unificar. Secuencia [{sequence_name}].'),
        'description': (
            'Fila [33] #34. El tubo ya se unifica solo y el mecanismo sale de la tabla; lo que el cliente puede mezclar es el Cabezal, que es lo que se compara.'),
    },
    {
        'code': 'V_SECUENCIA_PERFIL',
        'name': 'Secuencia: misma perfilería',
        'funcion_safra': 'ValidaMismoAmbiente',
        'severity': 'error', 'momento': 'pedido', 'trigger_field': None,
        'systems': ('01', '02', '06', '08', '10', '39'), 'active': True,
        'condition': (
            'nombre = sequence_name.strip().lower()\n'
            "grupo = [l for l in otras_lineas if l['linea'].same_header and l['secuencia'].strip().lower() == nombre]\n"
            "result = same_header and bool(nombre) and any((l['atributos'].get('perfil') or '') != perfil for l in grupo)"),
        'message': (
            'E13095: La perfilería debe ser la misma en todas las persianas. Secuencia [{sequence_name}].'),
        'description': 'Fila [33] #34.',
    },
    {
        'code': 'V_SECUENCIA_CANTIDAD',
        'name': 'Secuencia: misma cantidad en todas las líneas',
        'funcion_safra': 'ValidaMismoAmbiente',
        'severity': 'error', 'momento': 'pedido', 'trigger_field': None,
        'systems': ('01', '02', '06', '08', '10', '39'), 'active': True,
        'condition': (
            'nombre = sequence_name.strip().lower()\n'
            "grupo = [l for l in otras_lineas if l['linea'].same_header and l['secuencia'].strip().lower() == nombre]\n"
            "result = same_header and bool(nombre) and any(l['cantidad'] != cantidad for l in grupo)"),
        'message': (
            'E13095: La cantidad de unidades solicitada debe ser la misma en todas las líneas de pedido de la secuencia [{sequence_name}].'),
        'description': 'Fila [33] #34.',
    },
    {
        'code': 'V_SECUENCIA_CONSECUTIVA',
        'name': 'Secuencia: líneas consecutivas',
        'funcion_safra': 'ValidaMismoAmbiente',
        'severity': 'error', 'momento': 'pedido', 'trigger_field': None,
        'systems': ('01', '02', '06', '08', '10', '39'), 'active': True,
        'condition': (
            'nombre = sequence_name.strip().lower()\n'
            "numeros = sorted(l['numero'] for l in lineas if l['linea'].same_header and l['secuencia'].strip().lower() == nombre)\n"
            "lista = ', '.join(str(n) for n in numeros)\n"
            'result = same_header and bool(nombre) and len(numeros) > 1 and numeros[-1] - numeros[0] + 1 != len(numeros)'),
        'message': (
            'E13027: Para establecer las persianas en un mismo cabezal, deben ser ingresadas una tras la siguiente. Las líneas {lista} de la secuencia [{sequence_name}] no son consecutivas.'),
        'description': 'Fila [33] #34.',
    },
    {
        'code': 'V_BOLSILLO_GARANTIA',
        'name': 'Bolsillo: producto transformado sin garantía',
        'funcion_safra': 'ValidaBolsillo',
        'severity': 'warning', 'momento': 'campo', 'trigger_field': 'bolsillo_size',
        'systems': ('01', '06'), 'active': True,
        'condition': "bolsillo_size not in ('', '0')",
        'message': 'W13043: Si el producto es transformado, se exonera de garantía.',
        'description': (
            'Fila [37] #38 (Mantener): advertencia si el tamaño del bolsillo es mayor que 0 (opciones 5, 8 y 10 cm).'),
    },
    {
        'code': 'V_SHEER2EN1_REF2',
        'name': 'Sheer 2 en 1: la segunda referencia debe ser Sheer',
        'funcion_safra': 'ValidaTelas',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('61',), 'active': True,
        'condition': (
            "tela_2 and not (tela_2.is_sheer or 'SHEER' in (tela_2.name or '').upper())"),
        'message': (
            'E13095: No se permite telas diferente a Sheer para la segunda referencia.'),
        'description': (
            'Fila [41] #42 (Mantener, tres reglas). Se acepta como Sheer la tela con la marca «Familia Sheer» o con «Sheer» en el nombre, porque hoy 32 de las 40 telas de 61 no tienen familia marcada. Va con el cambio de V_SHEER2EN1_REF (primera referencia no Sheer).'),
    },
    {
        'code': 'V_COORDINADOS',
        'name': 'Mismo coordinado en todas las telas de la persiana',
        'funcion_safra': 'ValidaCoordinados',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('01', '02', '06', '32', '61'), 'active': True,
        'condition': (
            'otros = [c for c in (coordinado_tela_2, coordinado_tela_3, coordinado_tela_4, coordinado_tela_5) if c]\n'
            'result = bool(coordinado) and any(c != coordinado for c in otros)'),
        'message': 'E13095: No se permite establecer coordinados diferentes.',
        'description': (
            'Fila [43] #44 (Mantener). Compara el Coordinado de la tela principal con el de las telas combinadas (Coordinado Tela 2 a 5).'),
    },
    {
        'code': 'V_SESGO_TELA',
        'name': 'Sesgo solo en telas sesgables',
        'funcion_safra': 'ValidaSesgo',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': (), 'active': True,
        'condition': (
            'pares = [(tela, sesgo), (tela_2, sesgo_tela_2), (tela_3, sesgo_tela_3),\n'
            '         (tela_4, sesgo_tela_4), (tela_5, sesgo_tela_5)]\n'
            "malas = [t.name for t, s in pares if t and s not in ('', '0') and not t.is_sesgable]\n"
            "nombres = ', '.join(malas)\n"
            'result = bool(malas)'),
        'message': (
            'E10033: La tela seleccionada ({nombres}) no se puede fabricar con Sesgo.'),
        'description': (
            'Fila [45] #19. El portal solo muestra el sesgo en telas sesgables; esta regla es el respaldo para un valor que quede pegado (al editar o cambiar la tela). Revisa las telas 1 a 3 (las telas 4 y 5 no llegan como registro a las condiciones: needs_code).'),
    },
    {
        'code': 'V_SESGO_TODAS',
        'name': 'Si una tela lleva sesgo, todas las sesgables deben llevarlo',
        'funcion_safra': 'ValidaSesgo',
        'severity': 'warning', 'momento': 'linea', 'trigger_field': None,
        'systems': ('11', '54'), 'active': True,
        'condition': (
            'pares = [(tela, sesgo), (tela_2, sesgo_tela_2), (tela_3, sesgo_tela_3),\n'
            '         (tela_4, sesgo_tela_4), (tela_5, sesgo_tela_5)]\n'
            "con_sesgo = [t for t, s in pares if t and s not in ('', '0')]\n"
            "faltan = ', '.join(t.name for t, s in pares if t and t.is_sesgable and s in ('', '0'))\n"
            'result = bool(con_sesgo) and bool(faltan)'),
        'message': (
            'W13037: Se ha detectado que una de las telas tiene sesgo, por sugerencia estética, todas las telas deben llevar sesgo. Por favor especifique un color para: {faltan}.'),
        'description': 'Fila [45] #19: mensaje W13037 modificado por Safra.',
    },
    {
        'code': 'V_PANEL_DUO_TELOS',
        'name': 'Panel Duo: solo 6 u 8 telos',
        'funcion_safra': 'ValidaApertura',
        'severity': 'error', 'momento': 'campo', 'trigger_field': 'quantity_lamas',
        'systems': ('54',), 'active': True,
        'condition': 'total_lamas and total_lamas not in (6, 8)',
        'message': 'E13095: Para Panel Duo solo se permiten 6 y 8 Telos.',
        'description': 'Fila [46] #20 (Mantener).',
    },
    {
        'code': 'V_APERTURA_EXTREMOS_TRASLAPE',
        'name': 'Aviso: Privacidad Zen / Cascada con apertura Extremos',
        'funcion_safra': 'ValidaApertura',
        'severity': 'warning', 'momento': 'linea', 'trigger_field': None,
        'systems': ('11',), 'active': True,
        'condition': (
            "especiales = [t.name for t in (tela, tela_2, tela_3, tela_4, tela_5)\n"
            "              if t and t.code in ('0504237', '0504219')]\n"
            "referencias = ', '.join(especiales)\n"
            "result = apertura == '3' and bool(especiales)"),
        'message': (
            'W13044: La apertura Extremos en referencia [{referencias}], tiene la característica que al traslapar en el centro, se puede presentar un choque y leve espacio.'),
        'description': (
            'Fila [46] #20. Referencias Privacidad Zen (0504237) y Cascada (0504219), como tela 1 a 3. Solo están asociadas a Panel Japonés entre los paneles.'),
    },
    {
        'code': 'V_TELOS_GARANTIA',
        'name': 'Telos: más de 90 cm sin garantía',
        'funcion_safra': 'ValidaTelos',
        'severity': 'warning', 'momento': 'campo', 'trigger_field': 'width',
        'systems': ('16',), 'active': True,
        'condition': 'ancho > 0.90',
        'message': (
            'W13044: El ancho solicitado para cada telo supera los 90 centímetros. Se fabricará sin garantía.'),
        'description': 'Fila [47] #21: producto Telos (16), el ancho digitado es el del telo.',
    },
    {
        'code': 'V_PANEL_JUNTO_SIGUIENTE',
        'name': 'Panel junto al siguiente: el siguiente debe ir junto al anterior',
        'funcion_safra': 'ValidaPanelJunto',
        'severity': 'error', 'momento': 'pedido', 'trigger_field': None,
        'systems': ('11', '15', '54'), 'active': True,
        'condition': (
            "siguiente = [l for l in lineas if l['numero'] == numero + 1]\n"
            "result = riel_junto == '1' and not (siguiente and siguiente[0]['atributos'].get('riel_junto') == '2')"),
        'message': (
            'E13030: Si la configuración del panel es Junto al panel Siguiente, El panel Siguiente debe tener la configuración Junto al Panel Anterior.'),
        'description': 'Fila [48] #22. «Siguiente» = la línea que sigue en el pedido.',
    },
    {
        'code': 'V_PANEL_JUNTO_ANTERIOR',
        'name': 'Panel junto al anterior: el anterior debe ir junto al siguiente',
        'funcion_safra': 'ValidaPanelJunto',
        'severity': 'error', 'momento': 'pedido', 'trigger_field': None,
        'systems': ('11', '15', '54'), 'active': True,
        'condition': (
            "anterior = [l for l in lineas if l['numero'] == numero - 1]\n"
            "result = riel_junto == '2' and not (anterior and anterior[0]['atributos'].get('riel_junto') == '1')"),
        'message': (
            'E13031: Si la configuración requerida es para dos Paneles Juntos, debe especificar parejas con el campo Panel siguiente y Panel Anterior Respectivamente en el campo [Panel junto a:].'),
        'description': 'Fila [48] #22.',
    },
    {
        'code': 'V_PANEL_JUNTO_DIVIDIDO',
        'name': 'Panel junto: sin riel dividido',
        'funcion_safra': 'ValidaPanelJunto',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('11', '15', '54'), 'active': True,
        'condition': "riel_junto in ('1', '2') and traslape_centro == '2'",
        'message': (
            'E13072: Si la configuración del panel es [Junto al Item Siguiente] o [Junto al Item Anterior] el campo [Riel Dividido - Traslape Al Centro] debe ir seleccionado en [No].'),
        'description': 'Fila [48] #22.',
    },
    {
        'code': 'V_PANEL_JUNTO_ANCHO',
        'name': 'Paneles juntos: mismo ancho',
        'funcion_safra': 'ValidaCaracteristicasPanelesJuntos',
        'severity': 'error', 'momento': 'pedido', 'trigger_field': None,
        'systems': ('11', '15', '54'), 'active': True,
        'condition': (
            'pareja = numero + 1\n'
            "siguiente = [l for l in lineas if l['numero'] == pareja and l['atributos'].get('riel_junto') == '2']\n"
            "result = riel_junto == '1' and bool(siguiente) and round(siguiente[0]['ancho'], 3) != round(ancho, 3)"),
        'message': (
            'E13032: Línea [{numero}] y Línea [{pareja}] deben tener el mismo tamaño en Ancho.'),
        'description': (
            'Fila [49] #23. Se revisa en la primera línea de la pareja (Junto al siguiente).'),
    },
    {
        'code': 'V_PANEL_JUNTO_APERTURA',
        'name': 'Paneles juntos: aperturas izquierda y derecha',
        'funcion_safra': 'ValidaCaracteristicasPanelesJuntos',
        'severity': 'error', 'momento': 'pedido', 'trigger_field': None,
        'systems': ('11', '15'), 'active': True,
        'condition': (
            'pareja = numero + 1\n'
            "siguiente = [l for l in lineas if l['numero'] == pareja and l['atributos'].get('riel_junto') == '2']\n"
            "result = riel_junto == '1' and bool(siguiente) and not (apertura == '2' and str(siguiente[0]['atributos'].get('apertura') or '') == '1')"),
        'message': (
            'E13033: La línea [{numero}] debe tener apertura Izquierda y línea [{pareja}] debe tener apertura Derecha.'),
        'description': (
            'Fila [49] #23. Apertura en 11 y 15: 1 Derecha, 2 Izquierda. No aplica a Panel Duo (54), que solo tiene apertura 6 Doble función.'),
    },
    {
        'code': 'V_PANEL_JUNTO_TELOS',
        'name': 'Paneles juntos: misma cantidad de telos',
        'funcion_safra': 'ValidaCaracteristicasPanelesJuntos',
        'severity': 'error', 'momento': 'pedido', 'trigger_field': None,
        'systems': ('11', '15', '54'), 'active': True,
        'condition': (
            'pareja = numero + 1\n'
            "siguiente = [l for l in lineas if l['numero'] == pareja and l['atributos'].get('riel_junto') == '2']\n"
            "result = riel_junto == '1' and bool(siguiente) and int(float(siguiente[0]['atributos'].get('quantity_lamas') or 0)) != total_lamas"),
        'message': (
            'E13034: La cantidad de telos de las Lineas [{numero}] y linea [{pareja}] deben ser iguales.'),
        'description': 'Fila [49] #23.',
    },
    {
        'code': 'V_RIEL_JUNTO_SIGUIENTE',
        'name': 'Vertical: Riel Junto «Item siguiente» con su pareja',
        'funcion_safra': 'ValidaRielJunto',
        'severity': 'error', 'momento': 'pedido', 'trigger_field': None,
        'systems': ('40',), 'active': True,
        'condition': (
            "siguiente = [l for l in lineas if l['numero'] == numero + 1]\n"
            'mensaje = ("\'Riel Junto\' no debe estar seleccionado en \'Item siguiente\'" if not siguiente\n'
            '           else "Se requiere que el campo \'Riel Junto\' de la línea %d este seleccionado con el valor \'Item anterior\'" % (numero + 1))\n'
            "result = riel_junto == '1' and not (siguiente and siguiente[0]['atributos'].get('riel_junto') == '2')"),
        'message': 'E13095: {mensaje}',
        'description': (
            "Fila [76] #20 (Mantener). Sin pareja en la última línea: «'Riel Junto' no debe estar seleccionado en 'Item siguiente'»; si la siguiente no va con «Item anterior», se le pide."),
    },
    {
        'code': 'V_RIEL_JUNTO_ANTERIOR',
        'name': 'Vertical: Riel Junto «Item anterior» con su pareja',
        'funcion_safra': 'ValidaRielJunto',
        'severity': 'error', 'momento': 'pedido', 'trigger_field': None,
        'systems': ('40',), 'active': True,
        'condition': (
            "anterior = [l for l in lineas if l['numero'] == numero - 1]\n"
            'mensaje = ("\'Riel Junto\' no debe estar seleccionado en \'Item anterior\'" if not anterior\n'
            '           else "Se requiere que el campo \'Riel Junto\' de la línea %d este seleccionado con el valor \'Item siguiente\'" % (numero - 1))\n'
            "result = riel_junto == '2' and not (anterior and anterior[0]['atributos'].get('riel_junto') == '1')"),
        'message': 'E13095: {mensaje}',
        'description': 'Fila [76] #20.',
    },
    {
        'code': 'V_RIEL_JUNTO_APERTURA',
        'name': (
            'Vertical: Riel Junto con apertura izquierda (siguiente) o derecha (anterior)'),
        'funcion_safra': 'ValidaRielJunto',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('40',), 'active': True,
        'condition': (
            'mensaje = ("Se requiere para \'Riel Junto\' que la \'Apertura\' y \'Mando\' sean Izquierdos" if riel_junto == \'1\'\n'
            '           else "Se requiere para \'Riel Junto\' que la \'Apertura\' y \'Mando\' sean Derechos")\n'
            "result = (riel_junto == '1' and apertura != '2') or (riel_junto == '2' and apertura != '1')"),
        'message': 'E13095: {mensaje}',
        'description': (
            'Fila [76] #20. Apertura de Vertical: 1 Derecha, 2 Izquierda. El mando no se revisa porque hoy el campo Mando está inactivo en Vertical (pendiente_safra [78]).'),
    },
    {
        'code': 'V_TELO_FIJO_MOTOR',
        'name': 'Panel motorizado: telo fijo al frente',
        'funcion_safra': 'ValidaTeloFijo',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('11', '15'), 'active': True,
        'condition': "con_motor and posicion_telo not in ('', '1', 'ninguno')",
        'message': (
            'E10036: Si el panel Japonés es Motorizado, el Telo Fijo debe ir Al Frente.'),
        'description': (
            'Fila [50] #24. Posición Telo Fijo: 1 Frente, 2 Atrás, 3 Centro frente, 4 Centro atrás, ninguno (apertura libre). Panel Duo solo ofrece Frente.'),
    },
    {
        'code': 'V_TELO_FIJO_TRASLAPE',
        'name': 'Telo fijo al centro: solo con traslape de 12 cm',
        'funcion_safra': 'ValidaTeloFijo',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('11',), 'active': True,
        'condition': "posicion_telo in ('3', '4') and traslape < 0.12",
        'message': (
            'E13095: Para la posición del Telo Fijo "Centro Frente" ó "Centro Atras" solo se permite "Traslape de 12 cm".'),
        'description': (
            'Fila [50] #24. «Solo con apertura Centro» ya lo cumple la dependencia de las opciones 3 y 4 de Posición Telo Fijo. En Riel Armado (15) el Tamaño del Traslape solo aparece con riel dividido, por eso la regla queda en Panel Japonés.'),
    },
    {
        'code': 'V_PANEL_RECOMIENDA_MOTOR',
        'name': 'Panel de más de 5 m sin motor: se recomienda motorizar',
        'funcion_safra': 'RestriccionAnchoMaximoPersiana (paneles)',
        'severity': 'warning', 'momento': 'campo', 'trigger_field': 'width',
        'systems': ('11', '15', '54'), 'active': True,
        'condition': 'ancho > 5 and not con_motor',
        'message': 'W12005: Por el ancho de la Persiana, se recomienda Motorizar.',
        'description': 'Fila [52] #26.',
    },
    {
        'code': 'V_RIEL_GARANTIA',
        'name': 'Productos con riel de más de 6 m: sin garantía',
        'funcion_safra': 'RestriccionAnchoMaximoPersiana (paneles)',
        'severity': 'warning', 'momento': 'campo', 'trigger_field': 'width',
        'systems': ('11', '15', '54', '49', '57', '58'), 'active': True,
        'condition': (
            'maximo = 6.0\n'
            'result = ancho > maximo'),
        'message': (
            'W13044: El ancho solicitado para este producto supera los {maximo:.1f} metros. Se fabricará sin garantía.'),
        'description': (
            'Fila [52] #26: Safra baja de 8 a 6 m y lo extiende «a todos los productos que usen riel» (paneles y cortinas). Verticales/Hanas/Vintage no pasan de 6 m. Confirmar cortinas en pendiente_safra.'),
    },
    {
        'code': 'V_CENEFA_PERFIL',
        'name': 'Cenefa en tela: perfil obligatorio',
        'funcion_safra': 'ValidaCenefa',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('11', '54'), 'active': True,
        'condition': "cenefa_panel == 'I100002014' and not perfil_cenefa",
        'message': 'E13069: Especifique el perfíl para la Cenefa.',
        'description': (
            'Fila [54] #28. I100002014 = línea «Cenefa en tela» de la referencia Cenefas.'),
    },
    {
        'code': 'V_CENEFA_TELA_FORRADA',
        'name': 'Cenefa forrada: tela de cenefa obligatoria',
        'funcion_safra': 'ValidaCenefa',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('11', '54'), 'active': True,
        'condition': 'cenefa_lined and not cenefa_tela.strip()',
        'message': "E13084: No ha especificado una referencia para la 'Tela de Cenefa'.",
        'description': (
            'Fila [54] #28. En 11/54 la «Tela de Cenefa» aparece al marcar la cenefa como forrada. E13083 (que la tela sea una de las del panel) necesita que el campo sea una lista de las telas de la línea (needs_code).'),
    },
    {
        'code': 'V_CENEFA_METALICA_COLOR',
        'name': 'Cenefa metálica: color obligatorio',
        'funcion_safra': 'ValidaCenefa',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('11', '54'), 'active': True,
        'condition': "cenefa_panel == '2815' and not color_cenefa",
        'message': "E13085: No ha especificado un color para la 'Cenefa Metálica'.",
        'description': 'Fila [54] #28. 2815 = línea METALICA de la referencia Cenefas.',
    },
    {
        'code': 'V_CENEFA_METALICA_COORDINADO',
        'name': 'Cenefa metálica: color entre los coordinados',
        'funcion_safra': 'ValidaCenefa',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('11', '54'), 'active': True,
        'condition': (
            'coordinados = [c for c in (coordinado, coordinado_tela_2, coordinado_tela_3, coordinado_tela_4, coordinado_tela_5) if c]\n'
            "result = cenefa_panel == '2815' and bool(color_cenefa) and bool(coordinados) and color_cenefa not in coordinados"),
        'message': (
            "E13086: El Color de la 'Cenefa Metálica' no coincide con los coordinados del producto. Por favor cambie el color de la Cenefa."),
        'description': (
            'Fila [54] #28: respaldo para un color que quede pegado al editar. Mismos valores que el Coordinado (blanco, ivory, cafe, negro, gris).'),
    },
    {
        'code': 'V_TELOS_LIBRE',
        'name': 'Apertura libre: máximo 6 telos',
        'funcion_safra': 'ValidaTelosApertura',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('11', '15'), 'active': True,
        'condition': "apertura == '5' and total_lamas > 6",
        'message': 'E13095: Apertura Libre, máximo 6 Telos.',
        'description': 'Fila [55] #29. Hoy la revisión de apertura libre admite hasta 12.',
    },
    {
        'code': 'V_TELOS_FIJOS_RIEL_SUIZO',
        'name': 'Aviso: 12 telos extremos con telo fijo atrás',
        'funcion_safra': 'ValidaTelosApertura',
        'severity': 'warning', 'momento': 'linea', 'trigger_field': None,
        'systems': ('11', '15'), 'active': True,
        'condition': "total_lamas == 12 and apertura == '3' and posicion_telo == '2'",
        'message': 'W13044: Los telos fijos van aparte con un RIEL SUIZO.',
        'description': 'Fila [55] #29.',
    },
    {
        'code': 'V_TRASLAPE_MINIMO',
        'name': 'Traslape mínimo de 8 cm',
        'funcion_safra': 'ValidaTraslape',
        'severity': 'error', 'momento': 'campo', 'trigger_field': 'tamano_traslape',
        'systems': ('11', '54'), 'active': True,
        'condition': (
            'cm = round(traslape * 100, 1)\n'
            'result = bool(traslape) and traslape < 0.08'),
        'message': (
            'E13080: La persiana no se puede fabricar porque el tamaño del traslape es menor a 8 cm. Tamaño Traslape: {cm:g} cm.'),
        'description': (
            'Fila [58] #32. La lista Tamaño del Traslape ofrece 7 cm; además se puede ocultar esa opción (otros_ajustes_config).'),
    },
    {
        'code': 'V_TRASLAPE_REFERENCIA',
        'name': 'Privacidad Zen / Cascada: traslape de 12 cm',
        'funcion_safra': 'ValidaTraslape',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('11',), 'active': True,
        'condition': (
            "especiales = [t.name for t in (tela, tela_2, tela_3, tela_4, tela_5)\n"
            "              if t and t.code in ('0504237', '0504219')]\n"
            "referencias = ', '.join(especiales)\n"
            'result = bool(especiales) and traslape < 0.12'),
        'message': 'E13095: La referencia {referencias} debe llevar traslape de 12cm.',
        'description': 'Fila [58] #32. Telas 1 a 3.',
    },
    {
        'code': 'V_PANEL_DUO_DOBLE_MANDO',
        'name': 'Panel Duo motorizado: sin doble mando',
        'funcion_safra': 'ValidaMandoVsApertura',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('54',), 'active': True,
        'condition': "con_motor and mando_position == '3'",
        'message': (
            "E13095: Para Panel Dúo Motorizado no se permite 'Doble mando'. Por favor seleccione un Mando diferente."),
        'description': (
            'Fila [59] #33. Mando de Panel Duo: 1 Derecho, 2 Izquierdo, 3 Doble Mando.'),
    },
    {
        'code': 'V_PANEL_MOTOR_MANDO',
        'name': 'Panel motorizado: solo mando izquierdo o derecho',
        'funcion_safra': 'ValidaMotorizacion (paneles)',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('11', '15', '54'), 'active': True,
        'condition': "con_motor and mando_position in ('3', '4', '5')",
        'message': 'E13095: Panel motorizado, aplica solamente mando Izquierdo o Derecho.',
        'description': (
            'Filas [60] #34 y [64] #38. Mandos: 1 Derecho, 2 Izquierdo, 3 Doble Mando, 4 Bastón, 5 Doble Bastón. En Motor Panel Ensamblado (34) el mando ya solo ofrece 1 y 2.'),
    },
    {
        'code': 'V_CORTINA_MOTOR_MANDO',
        'name': 'Cortina motorizada: solo mando izquierdo o derecho',
        'funcion_safra': 'ValidaMotorizacion (cortinas)',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('49', '57', '58'), 'active': True,
        'condition': "con_motor and mando_position in ('4', '5')",
        'message': (
            'E13095: Cortina Motorizada, aplica solamente mando Izquierdo o Derecho.'),
        'description': (
            'Fila [65] #19. Mandos de cortina: 1 Derecho, 2 Izquierdo, 4 Bastón, 5 Doble Bastón.'),
    },
    {
        'code': 'V_CORTINA_ALTO_BASTON',
        'name': 'Cortina con mando bastón: alto máximo 3,70 m',
        'funcion_safra': 'ValidaAltura (cortinas)',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('49', '57'), 'active': True,
        'condition': (
            'maximo = 3.70\n'
            "result = mando_position == '4' and alto > maximo"),
        'message': (
            "E13095: Máxima altura para cortinas con 'Mando Bastón': {maximo:.2f} metros."),
        'description': (
            'Fila [66] #20 (no aplica a Riel Armado Cortina 58). El tope de 5 m con cordón ya lo da V_RANGO_ALTO (alto máximo de la ficha 5,00).'),
    },
    {
        'code': 'V_CORTINA_ALTO_ONDATA',
        'name': 'Cortina con tela Ondata: alto máximo 2,70 m',
        'funcion_safra': 'ValidaAltura (cortinas)',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('49', '57'), 'active': True,
        'condition': (
            'maximo = 2.70\n'
            "result = tela.code == '0504037' and alto > maximo"),
        'message': (
            "E13095: Máxima altura para cortinas con referencia 'Ondata': {maximo:.2f} metros."),
        'description': 'Fila [66] #20. Ondata = referencia 0504037.',
    },
    {
        'code': 'V_ONDATA_SISTEMA',
        'name': 'Ondata solo en Cortina Onda Moderna',
        'funcion_safra': 'ValidaTelasEnCortina',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('57',), 'active': True,
        'condition': "tela.code == '0504037'",
        'message': "E13095: La referencia 'Ondata' solo aplica para Diseño Onda Moderna.",
        'description': (
            'Fila [69] #23. Hoy Ondata está asociada también a Pliegue Francés (57): conviene quitarla de 57 (otros_ajustes_config); la regla es el respaldo. Se deja fuera Abrazadera (64), que es el accesorio de la cortina.'),
    },
    {
        'code': 'V_PALOMINO_PROFUNDIDAD',
        'name': 'Blackout Palomino sin profundidad de onda 2.3',
        'funcion_safra': 'ValidaTelasEnCortina',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('49',), 'active': True,
        'condition': "tela.code == '054317' and profundidad_onda_c == '2.3'",
        'message': (
            "E13095: La referencia 'Blackout Palomino' no aplica para profundidad de onda de 2.3."),
        'description': 'Fila [69] #23. Blackout Palomino = 054317.',
    },
    {
        'code': 'V_VELO_RAIN_ALTO',
        'name': 'Velo Rain en Onda Moderna: alto máximo 3,0 m',
        'funcion_safra': 'ValidaTelasEnCortina',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('49',), 'active': True,
        'condition': (
            'maximo = 3.0\n'
            "result = tela.code == '054316' and alto > maximo"),
        'message': (
            'E13095: En el sistema Cortina Onda Moderna, la referencia Velo Rain solo se fabrica hasta un alto máximo de {maximo:.1f} metros.'),
        'description': 'Fila [69] #23. Velo Rain = 054316.',
    },
    {
        'code': 'V_CORTINA_CURVA_MANUAL',
        'name': 'Riel curvado: solo accionamiento manual',
        'funcion_safra': 'ValidaTipoPlanoCortinaCurvada',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('49', '57'), 'active': True,
        'condition': 'bool(tipoplano_cortina) and con_motor',
        'message': (
            'E13095: Cortina con riel curvado, solo está disponible para accionamiento manual.'),
        'description': 'Fila [74] #28 (no aplica a 58).',
    },
    {
        'code': 'V_CORTINA_CURVA_BASTON',
        'name': 'Riel curvado: solo con mando Bastón o Doble Bastón',
        'funcion_safra': 'ValidaTipoPlanoCortinaCurvada',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('49', '57'), 'active': True,
        'condition': "bool(tipoplano_cortina) and mando_position not in ('4', '5')",
        'message': (
            'E13095: Cortina con riel curvado, solo se permite con mando: Bastón y Doble Bastón.'),
        'description': 'Fila [74] #28.',
    },
    {
        'code': 'V_CORTINA_SEGMENTO_MIN',
        'name': 'Riel curvado: medida mínima por segmento',
        'funcion_safra': 'ValidaTipoPlanoCortinaCurvada',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('49', '57'), 'active': True,
        'condition': (
            "minimo = 0.50 if tipoplano_cortina == 'LID' else 0.30\n"
            "medidas = [segmento_1, segmento_2] if tipoplano_cortina == 'LID' else [segmento_2] if tipoplano_cortina == 'U' else []\n"
            'cm = round(minimo * 100)\n'
            'result = any(m and m < minimo for m in medidas)'),
        'message': 'E13095: La medida mínima válida para cada segmento, es de {cm} cms.',
        'description': (
            'Fila [74] #28: Plano L (LID) 50 cm en los segmentos 1 y 2; Plano U 30 cm en el segmento 2. Los segmentos de lista (30/50/Más de 50) van en V_CORTINA_SEGMENTO_MAS. Los 40 cm «generales» de SAP quedan en pendiente_safra.'),
    },
    {
        'code': 'V_CORTINA_SEGMENTO_MAS',
        'name': 'Riel curvado: segmento «Más de 50 cm» mayor a 50 cm',
        'funcion_safra': 'ValidaTipoPlanoCortinaCurvada',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('49', '57'), 'active': True,
        'condition': (
            "result = (segmento_1_u == 'mas' and 0 < segmento_1_u_m <= 0.50) or (segmento_3 == 'mas' and 0 < segmento_3_m <= 0.50)"),
        'message': (
            'E13095: Las medidas válidas por cada segmento, deben superar los 50 cms.'),
        'description': 'Fila [74] #28: Plano U, segmentos 1 y 3 con «Más de 50 cm».',
    },
    {
        'code': 'V_LAMA_VERTICAL_MAX',
        'name': 'Lama Vertical: máximo 12 lamas por línea',
        'funcion_safra': 'ValidaLamas',
        'severity': 'error', 'momento': 'campo', 'trigger_field': 'quantity',
        'systems': ('50',), 'active': True,
        'condition': 'cantidad > 12',
        'message': (
            'E13095: Sólo se permite un máximo de 12 Lamas por línea de pedido. Por favor digite una nueva línea en caso de necesitar más cantidad.'),
        'description': (
            'Fila [77] #21. En Lama Vertical (50) la cantidad de la línea es la cantidad de lamas.'),
    },
    {
        'code': 'V_LAMA_PESO',
        'name': 'Vertical: peso de la lama máximo 0,5 kg',
        'funcion_safra': 'ValidaLamas',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('40',), 'active': True,
        'condition': (
            'maximo = 0.5\n'
            'peso_lama = ancho * alto * (tela.peso_gm2 or 0) / 1000 / total_lamas if total_lamas else 0\n'
            'result = peso_lama > maximo'),
        'message': (
            'E13095: El peso de la lama excede el peso máximo soportado por el pantógrafo ({maximo} kg). Peso calculado: {peso_lama:.2f} kg.'),
        'description': (
            'Fila [77] #21: peso de cada lama = ancho × alto × peso de la tela (g/m²) / 1000 / número de lamas. Sin peso de tela en Referencias no dispara (hoy 21 de 43 telas de 40 lo tienen).'),
    },
    {
        'code': 'V_ALTO2_RANGO',
        'name': 'Vertical Irregular: Alto 2 dentro de la ficha y distinto del Alto 1',
        'funcion_safra': 'ValidaAltos',
        'severity': 'error', 'momento': 'campo', 'trigger_field': 'height2',
        'systems': ('55',), 'active': True,
        'condition': (
            "result = height2 >= 0.40 and (round(height2, 3) == round(alto, 3) or height2 < limites['hmin'])"),
        'message': (
            'E13095: El valor de alto mínimo está por fuera del rango permitido. Recuerde que el alto mínimo no puede ser superior o igual al Alto digitado ({alto}) y tampoco puede ser inferior al valor mínimo de la ficha técnica ({limites[hmin]}).'),
        'description': (
            'Fila [79] #23 (sin cambios). «Superior» al Alto 1 lo reporta V_ALTO1_MENOR y por debajo de 0,40 V_ALTO2_MINIMO, para no repetir mensajes.'),
    },
    {
        'code': 'V_ALTO2_MINIMO',
        'name': 'Vertical Irregular: Alto 2 mínimo 0,40 m',
        'funcion_safra': 'ValidaAltos',
        'severity': 'error', 'momento': 'campo', 'trigger_field': 'height2',
        'systems': ('55',), 'active': True,
        'condition': '0 < height2 < 0.40',
        'message': (
            'E13095: El valor de alto2 mínimo está por fuera del rango permitido. Recuerde que el alto mínimo no puede ser inferior a 40 cm (0.4 metros).'),
        'description': 'Fila [79] #23.',
    },
    {
        'code': 'V_ALTO1_MENOR',
        'name': 'Vertical Irregular: Alto 1 mayor que Alto 2',
        'funcion_safra': 'ValidaAltos',
        'severity': 'error', 'momento': 'campo', 'trigger_field': 'height2',
        'systems': ('55',), 'active': True,
        'condition': 'bool(height2) and bool(alto) and alto < height2',
        'message': (
            'E13095: El valor de Alto 1 ( {alto} ) es menor que el valor de Alto 2 ( {height2} ). Por favor, ingrese primero el valor mayor seguido del valor menor.'),
        'description': 'Fila [79] #23.',
    },
    {
        'code': 'V_CUADRO_DISENO',
        'name': 'Cuadro Lienzo: diseño de impresión obligatorio',
        'funcion_safra': 'ValidaDisenoImp',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('56',), 'active': True,
        'condition': 'not design_print',
        'message': (
            'E13095: No se detecto un diseño de impresion, por favor adjuntar un diseño.'),
        'description': (
            'Fila [83] #19. Con «Diseño de impresión» marcado y sin diseño ya bloquea V_DISENO_SELECCION; esta regla cubre el cuadro enviado sin marcar la impresión.'),
    },
    {
        'code': 'V_ANADIDO',
        'name': 'La persiana sale con añadido',
        'funcion_safra': 'Valida_Añadido',
        'severity': 'warning', 'momento': 'linea', 'trigger_field': None,
        'systems': ('01', '02', '06', '32', '61'), 'active': True,
        'condition': (
            "aumento = estructura.get('aumento_tela', 0)\n"
            "result = bool(tela) and tela.pierceable_type != 'no' and tela.is_anadido and bool(ancho_rollo) and ancho > ancho_rollo and alto > ancho_rollo - aumento"),
        'message': 'OB0003: La persiana sale con añadido.',
        'description': (
            "Fila [84] (regla adicionada): tela atravesable y añadible, ancho mayor que el rollo y alto mayor que (ancho del rollo − aumento de tela del tubo). El aumento del tubo no llega hoy a las condiciones (vale 0 hasta que se agregue estructura['aumento_tela'], needs_code) y ninguna tela tiene la marca «Añadido»: no dispara hasta completar ambos datos."),
    },
    {
        'code': 'V_MOTOR_TUBO',
        'name': 'Motor compatible con el tubo (kit motorizado)',
        'funcion_safra': 'V04_motor_requires_soporte (hoja Validaciones_Formulario fila 9)',
        'severity': 'error', 'momento': 'linea', 'trigger_field': None,
        'systems': ('01', '02', '06'), 'active': True,
        'condition': (
            "con_motor and bool(motor) and bool(estructura['tubo']) and bool(motor_kits) and not kit"),
        'message': (
            'E13095: El motor seleccionado no aplica para el tubo {estructura[tubo]}. Seleccione otro motor.'),
        'description': (
            'Hoja Validaciones_Formulario fila 9 (V04): la asociación motor ↔ tubo sale de la hoja KIT MOTORIZADO. Dispara si el motor tiene kits cargados pero ninguno para el tubo calculado (o unificado). Un motor sin ningún kit no se bloquea (falta de dato).'),
    },
]

# Cambios a reglas que ya existían (la condición y el mensaje solo se
# cambian si siguen como los dejó el módulo).
CAMBIOS = {
    'V_ANCHO_MIN_MOTOR': {
        'condition': 'con_motor and ancho and ancho < motor_ancho_min',
        'message': (
            'E13095: El ancho mínimo para el motor seleccionado es de {motor_ancho_min} metros.'),
    },
    'V_CADENA_EXTRA': {
        'active': False,
    },
    'V_ATRAVESADO': {
        'message': (
            'E13026: La tela seleccionada no se puede forzar el atravesado, por favor establecer el campo Atraviesa Tela en Predeterminado.'),
    },
    'V_CORTE_ATRAVESADO': {
        'systems': ('01', '02', '06', '32', '61'),
    },
    'V_ANCHO_ROLLO': {
        'message': (
            'E13095: OB0001 Medidas de la Persiana superan el Ancho de la tela ({ancho_rollo} Mts).'),
    },
    'V_ROLLO_ALINEADO': {
        'severity': 'error',
    },
    'V_ALINEADO_LOCALIZACION': {
        'condition': (
            "misma_loc = [l for l in otras_lineas if l['alineado']\n"
            "             and l['localizacion'].strip().lower() == localizacion.strip().lower()]\n"
            'result = alineado and not misma_loc and cantidad < 2'),
        'message': (
            'E13070: Revisar las líneas del pedido que pertenezcan a la Localización [{localizacion}]: para alinear se requieren mínimo 2 persianas alineadas en la misma localización. Si no, desmarque la opción Alineado.'),
    },
    'V_ALINEADO_MIN': {
        'condition': (
            "misma_loc = [l for l in otras_lineas if l['alineado']\n"
            "             and l['localizacion'].strip().lower() == localizacion.strip().lower()]\n"
            "iguales = [l for l in misma_loc if l['tela'] == tela and l['color'] == color]\n"
            'result = alineado and bool(misma_loc) and not iguales and cantidad < 2'),
        'message': (
            'E13067: La función de Alineado aplica para un mínimo de 2 persianas con la tela «{tela.name}» en la Localización [{localizacion}]. Solo se pueden alinear las telas que tengan la misma Referencia y Color. Si es solo una persiana por favor establecer el campo Alineado en NO.'),
    },
    'V_ALINEADO_ALTURA': {
        'message': (
            'W13038: Las persianas de la tela «{tela.name}» que son alineadas deben tener la misma altura. La persiana de menor altura no va a alinear. No se garantiza alineación.'),
    },
    'V_ESTRUCTURA': {
        'condition': "hallazgo and sistema not in ('32', '61')",
        'message': (
            'E13095: No se han identificado los componentes [Tubo, Mecanismo y Cabezal] para el ancho de {ancho} m. Revise la configuración de la persiana.'),
    },
    'V_ALTO_MAXIMO': {
        'message': (
            'E10004: Alto fuera de Rango para la fabricación de la persiana. Motivo Excede Limite de acumulacion o Limite de peso. Alto máximo calculado: {estructura[alto_maximo]:.2f} m.'),
    },
    'V_REQUIERE_MOTOR': {
        # Reunión 09-nov (fila 68): sale también por el alto, y pide marcar el motor.
        'message': MENSAJE_REQUIERE_MOTOR,
    },
    'V_SHEER2EN1_REF': {
        'condition': 'tela and tela.is_sheer',
        'message': (
            'E13095: No se permite telas Sheer para la primera referencia (dentro del cabezal).'),
        'name': 'Sheer 2 en 1: la primera referencia no puede ser Sheer',
    },
    'V_SEGUNDA_TELA': {
        'message': 'E13022: Por favor seleccione la segunda tela de la {sistema_nombre}.',
    },
    'V_CENEFA_ENTERA': {
        'condition': (
            "laterales = 2 if cenefa_lateral == 'ambos' else 1 if cenefa_lateral in ('izquierdo', 'derecho') else 0\n"
            'ancho_cenefa = ancho + 0.11 * laterales\n'
            "result = corte_cenefa == '2' and bool(tela) and not tela.permite_cenefa_entera and bool(ancho_rollo) and ancho_cenefa > ancho_rollo"),
        'message': (
            "E13079: Para la referencia [{tela.name}] no aplica el corte de Cenefa 'Cenefa Entera' (ancho con laterales {ancho_cenefa:.2f} m, rollo {ancho_rollo} m). Establezca este valor a 'Cenefa añadida'."),
    },
}

# Campos obligatorios por sistema (se activa el campo si estaba inactivo).
OBLIGATORIOS = [
    ('11', 'quantity_lamas'),
    ('15', 'quantity_lamas'),
    ('54', 'quantity_lamas'),
    ('49', 'profundidad_onda_c'),
    ('49', 'bajofalso'),
    ('57', 'bajofalso'),
    ('40', 'mando_position'),
    ('41', 'mando_position'),
    ('42', 'mando_position'),
    ('55', 'mando_position'),
    ('63', 'mando_position'),
    ('01', 'perfil'),
    ('06', 'perfil'),
    ('32', 'perfil_sheer'),
    ('32', 'perfileria2'),
]

# Opciones que solo se ofrecen con ciertos valores de otro campo
# (sistema = None: opción del Catálogo de campos).
DEPENDENCIAS_OPCION = [
    ('11', 'mando_position', '1', 'apertura', '!5'),
    ('11', 'mando_position', '2', 'apertura', '!5'),
    ('11', 'mando_position', '3', 'apertura', '3,4,5'),
    ('11', 'mando_position', '4', 'apertura', '1,2'),
    ('11', 'mando_position', '5', 'apertura', '3,5'),
    ('15', 'mando_position', '1', 'apertura', '!5'),
    ('15', 'mando_position', '2', 'apertura', '!5'),
    ('15', 'mando_position', '3', 'apertura', '3,4,5'),
    ('15', 'mando_position', '4', 'apertura', '1,2'),
    ('15', 'mando_position', '5', 'apertura', '3,5'),
    ('49', 'mando_position', '1', 'apertura', '!5'),
    ('49', 'mando_position', '2', 'apertura', '!5'),
    ('49', 'mando_position', '4', 'apertura', '1,2,4'),
    ('49', 'mando_position', '5', 'apertura', '3,4,5'),
    ('57', 'mando_position', '1', 'apertura', '!5'),
    ('57', 'mando_position', '2', 'apertura', '!5'),
    ('57', 'mando_position', '4', 'apertura', '1,2,4'),
    ('57', 'mando_position', '5', 'apertura', '3,4,5'),
    ('58', 'mando_position', '1', 'apertura', '!5'),
    ('58', 'mando_position', '2', 'apertura', '!5'),
    ('58', 'mando_position', '4', 'apertura', '1,2,4'),
    ('58', 'mando_position', '5', 'apertura', '3,4,5'),
    (None, 'tipoplano_cortina', 'LI', 'apertura', '1'),
    (None, 'tipoplano_cortina', 'LD', 'apertura', '2'),
    (None, 'tipoplano_cortina', 'LID', 'apertura', '1,2'),
]

# Fórmulas de opciones del Catálogo de campos: (campo, valor, «auto» = se
# elige sola si… / «formula» = se ofrece si…, fórmula nueva). Solo se
# reemplazan las que siguen como las sembró el Sprint 1.4/1.5.
FORMULAS_OPCION = [
    # Matriz 1.7 (cenefa): la metálica y la de tela se dividen por encima
    # de 5,75 m; la PVC por su U_AnchoMax (3 m).
    ('cenefa_dividida', '1', 'auto', (
        "# PVC: U_AnchoMax del producto (3 m). Metálica y cenefa en tela: 5,75 m.\n"
        "maximo = ancho_max_cenefa_panel or 5.75\n"
        "result = ancho > maximo")),
    # Matriz 1.7 (cenefa): cada lateral suma 11 cm al ancho de la cenefa.
    ('corte_cenefa', '1', 'auto', (
        "# El ancho de la cenefa (más 11 cm por lateral) supera el rollo y la\n"
        "# tela no permite cenefa entera: la cenefa va añadida.\n"
        "laterales = 2 if cenefa_lateral == 'ambos' else 1 if cenefa_lateral in ('izquierdo', 'derecho') else 0\n"
        "result = bool(ancho_rollo) and ancho + 0.11 * laterales > ancho_rollo and not tela_permite_cenefa_entera")),
    ('corte_cenefa', '2', 'formula', (
        "# Entera si el ancho de la cenefa (más 11 cm por lateral) no supera el\n"
        "# rollo, o si la tela permite cenefa entera.\n"
        "laterales = 2 if cenefa_lateral == 'ambos' else 1 if cenefa_lateral in ('izquierdo', 'derecho') else 0\n"
        "result = not ancho_rollo or ancho + 0.11 * laterales <= ancho_rollo or tela_permite_cenefa_entera")),
    # Matriz 1.7 (cortinas): un solo máximo de 5,80 m, también motorizada.
    ('traslape_centro', '2', 'auto', (
        "# Si el ancho supera el ancho máximo del riel, va dividido.\n"
        "# ancho_max_riel_tipo es el U_AnchoMax del riel elegido (paneles); en\n"
        "# las cortinas el riel no se elige: 5,80 m.\n"
        "riel_max = ancho_max_riel_tipo or (5.80 if sistema in ('49', '57', '58') else 0)\n"
        "result = bool(riel_max) and ancho > riel_max")),
]

# Vintage motorizada: el mando derecho se elige solo (el motor va a la derecha).
MANDO_VINTAGE = (('42', '63'), '1', 'result = motorizado',
                 'El Motor siempre se instala al lado derecho en Vintage motorizadas.')

# Hanas: solo coordinado Blanco.
COORDINADO_HANAS = ('41', 'blanco', 'Blanco')

# Panel Duo: ancho de cada telo entre 0,20 y 0,475 m.
TELO_PANEL_DUO = ('54', 0.20, 0.475)

# Catálogo único (archivo de Safra): estado de cada función, reglas del
# portal que la cubren y nota para el consultor.
CATALOGO = {
    'E10004': ('ValidaAlto', 'ValidaAlto', 'pendiente_safra', ('V_ALTO_MAXIMO', 'V_PESO_MAXIMO', 'V_RANGO_ALTO'),
           'V_ALTO_MAXIMO bloquea con el alto máximo de la fórmula (con el mensaje de Safra). Falta que Safra confirme si se deja de aplicar el alto máximo del producto terminado (V_RANGO_ALTO) y que complete peso y grosor de las telas, sin los cuales la fórmula no corre.'),
    'E10016': ('ValidaTelos [E10017, E10026, E13095]', 'ValidaTelos', 'pendiente_safra', ('V_LAMAS_TELA_SUMA', 'V_LAMAS_TELA', 'V_PANEL_LAMAS', 'V_TELOS_GARANTIA'),
           'Cubiertos la cantidad de telos por tela (con telos obligatorios en 11, 15 y 54), el ancho del telo (con rango propio de Panel Duo) y el aviso de telos de más de 90 cm. Falta el peso del telo contra el velcro (32 kg/m²): Safra debe dar la fórmula y las unidades.'),
    'E10027': ('ValidaEstampado [E10029]', 'ValidaEstampado', 'pendiente_safra', ('V_ESTAMPADO_M2',),
           'Los m² de impresión los cubre V_ESTAMPADO_M2. Falta E10029 (ancho máximo de tela para estampar): Safra debe dar el valor con tela atravesada y sin atravesar.'),
    'E10027-53': ('ValidaEstampado', 'ValidaEstampado', 'cubierta', ('V_ESTAMPADO_M2',),
           'En paneles los m² de impresión se calculan como ancho por alto y siempre cubren el mínimo de Safra; V_ESTAMPADO_M2 queda de respaldo.'),
    'E10030': ('ValidaMotorizacion [E10037, E13078, E13095]', 'ValidaMotorizacion', 'inactivada', ('V_ANCHO_MIN_MOTOR', 'V_PESO_MAXIMO', 'V_REQUIERE_MOTOR', 'V_CONTROL_MOTOR', 'V_MOTOR_TUBO'),
           'Safra la elimina: la reemplazan la fórmula de peso, el ancho mínimo para motorizar y el kit motorizado (motor, tubo, control y soporte), que son las reglas listadas.'),
    'E10033': ('ValidaSesgo', 'ValidaSesgo', 'pendiente_safra', ('V_SESGO_TELA', 'V_SESGO_TODAS'),
           'Cubiertos el sesgo en tela no sesgable (E10033) y el aviso W13037 en las cinco telas. W13040 («la tela incluye sesgo») espera que Safra indique qué telas lo incluyen.'),
    'E10034': ('ValidaEstampado [E13095]', 'ValidaEstampado', 'pendiente_safra', ('V_ESTAMPADO_FUERA_SERVICIO', 'V_ESTAMPADO_TELA', 'V_ESTAMPADO_SHEER', 'V_ESTAMPADO_ANADIDO', 'V_ESTAMPADO_SHEER_ELEGANCE'),
           'Reglas creadas para fuera de servicio (inactiva, se activa cuando falle la impresora), tela no estampable, Sheer, tela añadida y Sheer Elegance; la de 9 cm Safra la quita. V_ESTAMPADO_ANADIDO no dispara hasta que Safra marque las telas añadibles, y falta que confirme si «Appril Shower Vertical» es de 9 cm.'),
    'E10036': ('ValidaTeloFijo [E13095]', 'ValidaTeloFijo', 'cubierta', ('V_TELO_FIJO_MOTOR', 'V_TELO_FIJO_TRASLAPE', 'V_OPCION_DEPENDENCIA', 'V_TELO_FIJO'),
           'Motorizado con telo fijo al frente y Centro frente/atrás solo con traslape de 12 cm son reglas nuevas; apertura libre sin telo fijo y Centro solo con apertura Centro los dan las dependencias de opción.'),
    'E10039': ('ValidaApertura [E10040, E13021, E13063]', 'ValidaApertura', 'pendiente_safra', ('V_PANEL_APERTURA', 'V_PANEL_DUO_TELOS', 'V_APERTURA_EXTREMOS_TRASLAPE'),
           'Cubiertas la apertura según la tabla de combinaciones (incluida la Doble función de Panel Duo), Panel Duo con 6 u 8 telos y el aviso de Privacidad Zen/Cascada. Safra debe confirmar si se permite Centro con 3 o 5 telos.'),
    'E10041': ('ValidaEnrolleVsAlineado [E13038, E13066]', 'ValidaEnrolleVsAlineado', 'cubierta', ('V_ALINEADO_ORIENTACION', 'V_ALINEADO_MIN', 'V_ALINEADO_LOCALIZACION'),
           'La misma orientación del enrollado en las alineadas es regla nueva; el mínimo de dos y la misma referencia ya estaban en las reglas de Alineado.'),
    'E10042': ('RestriccionAnchoMaximoPersiana', 'RestriccionAnchoMaximoPersiana', 'cubierta', ('V_RANGO_ANCHO', 'V_ESTRUCTURA'),
           'El ancho máximo del producto terminado (5,5 m o menos según el sistema) y la tabla de estructura impiden pasar de 5,85 m; solo cambia el código del mensaje (OB0005).'),
    'E10044': ('ValidaCorte45', 'ValidaCorte45', 'inactivada', ('V_PLANO_SEGMENTOS',),
           'Safra la inactiva: el corte a 45° ahora se valida con el Tipo de Plano (V_PLANO_SEGMENTOS).'),
    'E12003': ('ValidaMismoAmbiente [E13001, E13002, E13003]', 'ValidaMismoAmbiente', 'pendiente', ('V_SECUENCIA', 'V_SECUENCIA_MIN', 'V_SECUENCIA_NOMBRE', 'V_SECUENCIA_PENDIENTE', 'V_SECUENCIA_COORDINADO', 'V_SECUENCIA_CABEZAL', 'V_SECUENCIA_PERFIL', 'V_SECUENCIA_CANTIDAD', 'V_SECUENCIA_CONSECUTIVA'),
           'Soportes, tracción y coherencia de la secuencia (coordinado, cabezal, perfil, cantidad, líneas consecutivas) quedan en el servidor. Falta desarrollo: la revisión dentro del configurador antes de «Aplicar», «secuencia motorizada sin persianas manuales» y la resistencia del soporte dependiente por peso.'),
    'E13022': ('ValidaSegundaTela', 'ValidaSegundaTela', 'cubierta', ('V_SEGUNDA_TELA',),
           'V_SEGUNDA_TELA exige la segunda tela en Enrollable 2 en 1 y Sheer 2 en 1, con el mensaje de Safra.'),
    'E13023': ('ValidaUnificaMando [E13095]', 'ValidaUnificaMando', 'pendiente_safra', (),
           'Los errores de unificación (tubo mayor, no unificar a uno inferior, R16 motorizado) no hacen falta: el servidor unifica la secuencia antes de validar; el de soporte R24 Safra lo quita. Falta que Safra defina la condición del aviso informativo I13095 («se recomienda unificar»).'),
    'E13026': ('ValidaAtravesadoCliente', 'ValidaAtravesadoCliente', 'cubierta', ('V_ATRAVESADO',),
           'V_ATRAVESADO bloquea forzar el atravesado en telas que no lo admiten, con el texto de Safra. La advertencia W13025 Safra la inactiva.'),
    'E13030': ('ValidaPanelJunto [E13031, E13072]', 'ValidaPanelJunto', 'cubierta', ('V_PANEL_JUNTO_SIGUIENTE', 'V_PANEL_JUNTO_ANTERIOR', 'V_PANEL_JUNTO_DIVIDIDO'),
           'Reglas nuevas para las parejas siguiente/anterior y para impedir riel dividido en paneles juntos.'),
    'E13032': ('ValidaCaracteristicasPanelesJuntos [E13033, E13034]', 'ValidaCaracteristicasPanelesJuntos', 'cubierta', ('V_PANEL_JUNTO_ANCHO', 'V_PANEL_JUNTO_APERTURA', 'V_PANEL_JUNTO_TELOS'),
           'Reglas nuevas: mismo ancho, aperturas izquierda y derecha y misma cantidad de telos en los paneles juntos.'),
    'E13035': ('ValidaTubo [E13095]', 'ValidaTubo', 'cubierta', ('V_SECUENCIA_TUBO_DEP', 'V_ESTRUCTURA', 'V_RANGO_ANCHO'),
           'Safra solo mantiene E13035 (soporte dependiente con tubo mínimo R16), que es regla nueva; el resto lo resuelven la fórmula y la unificación automática, o son motores que ya no existen.'),
    'E13037': ('ValidaSoportesIntermedios [E13049]', 'ValidaSoportesIntermedios', 'pendiente_safra', ('V_SECUENCIA_ALTO',),
           'E13037 no puede darse con el configurador de secuencia. Para E13049 Safra debe confirmar si el mismo alto se exige solo en persianas unidas por soporte dependiente (y advertencia en el resto); hoy se exige por referencia en toda la secuencia.'),
    'E13039': ('ValidaAlineadoMismoAmbiente', 'ValidaAlineadoMismoAmbiente', 'pendiente', ('V_ALINEADO_AMBIENTE', 'V_ALINEADO_AMBIENTE_ALTO', 'V_ALINEADO_ALTURA'),
           'El servidor exige alinear la misma tela y color en la misma localización (E13039) y avisa con alto distinto (W13042). Falta desarrollo para que el portal marque Alineado solo, que es lo que pide Safra.'),
    'E13040': ('AnchoMaximoPersianaMismoCabezal', 'AnchoMaximoPersianaMismoCabezal', 'cubierta', ('V_SECUENCIA_ANCHO',),
           'Regla nueva: la suma de anchos del mismo cabezal no puede pasar de 5,80 m (valor editable en la condición).'),
    'E13042': ('ValidaSoportesMotorMismoAmbiente [E13048, E13071, E13095]', 'ValidaSoportesMotorMismoAmbiente', 'inactivada', (),
           'Safra la inactiva: el cliente ya no elige el soporte de motor, lo define el kit motorizado.'),
    'E13051': ('ValidaAncho', 'ValidaAncho', 'pendiente_safra', ('V_CORTE_ATRAVESADO', 'V_ANCHO_ROLLO'),
           'Queda solo en enrollables (V_CORTE_ATRAVESADO) y la tela no atravesable más ancha que el rollo la bloquea V_ANCHO_ROLLO. Safra debe definir si el atravesado es error que exige autorización (E13051) o solo aviso OB0002 (hoja de formulario fila 14).'),
    'E13052': ('ValidaRiel [E13053, E13095]', 'ValidaRiel', 'pendiente_safra', ('V_PANEL_RIEL', 'V_PANEL_LAMAS', 'V_TELO_FIJO_MOTOR', 'V_OPCION_AUTO'),
           'Riel Velcrado con 7 y 12 telos, Automático con un telo y telo fijo al frente con motor están cubiertos; Riel Suizo y Easy Roman no existen en Referencias. Falta que Safra fije el umbral de riel dividido (5,7 o 6,0 m) y el ancho máximo de cada riel.'),
    'E13054': ('RestriccionAnchoMaximoPersiana', 'RestriccionAnchoMaximoPersiana', 'pendiente_safra', ('V_PANEL_RECOMIENDA_MOTOR', 'V_RIEL_GARANTIA'),
           'Reglas nuevas: recomendar motor por encima de 5 m y «sin garantía» por encima de 6 m. Safra debe confirmar si el aviso de 6 m aplica también a cortinas, que llegan a 11,80 m con riel dividido.'),
    'E13055': ('ValidaCenefa [E13069, E13079, E13083]', 'ValidaCenefa', 'pendiente', ('V_CENEFA_ENTERA', 'V_CENEFA_PERFIL', 'V_CENEFA_TELA_FORRADA', 'V_CENEFA_METALICA_COLOR', 'V_CENEFA_METALICA_COORDINADO', 'V_OPCION_AUTO'),
           'Cubiertos cenefa dividida por encima de 5,75 m, cenefa entera con laterales (11 cm por lateral), perfil, tela de cenefa y color de la metálica. Falta desarrollo para E13083: la tela de cenefa es texto libre y debe ser una lista de las telas de la línea.'),
    'E13067': ('ValidaAlineadoImplements (lógica detallada) [E13070, E13095]', 'ValidaAlineadoImplements', 'pendiente_safra', ('V_ALINEADO_LOCALIZACION', 'V_ALINEADO_MIN', 'V_ALINEADO_ALTURA', 'V_ALINEADO_MAXIMO', 'V_ROLLO_ALINEADO', 'V_ALINEADO_FRANJAS'),
           'Las cinco reglas de la simplificación de Safra quedan cubiertas (mínimo 2, misma tela y color, misma localización, material del rollo, máximo 4 en enrollables). Safra debe confirmar si se mantiene «corte a 45° debe ir alineado» y si hay máximo de alineadas en otros sistemas.'),
    'E13080': ('ValidaTraslape [E13095]', 'ValidaTraslape', 'cubierta', ('V_TRASLAPE_MINIMO', 'V_TRASLAPE_REFERENCIA'),
           'Cubiertos el traslape mínimo de 8 cm y los 12 cm para Privacidad Zen y Cascada.'),
    'E13082': ('ValidaCadenaExtra', 'ValidaCadenaExtra', 'pendiente', (),
           'Fuera del alcance del Sprint 1.7 (precios): Safra quita el aviso (V_CADENA_EXTRA se desactiva) y pide cobrar la extracadena fuera de rango.'),
    'E13083': ('ValidaTelaCenefa [E13095, E13096]', 'ValidaTelaCenefa', 'cubierta', (),
           'E13096 la inactiva Safra (la reemplaza E13083 de ValidaCenefa). «Perfil de cenefa estándar solo sin laterales» hoy no puede darse porque no existe perfil de cenefa estándar.'),
    'E13091': ('ValidaMandoVsApertura [E13095]', 'ValidaMandoVsApertura', 'pendiente_safra', ('V_OPCION_DEPENDENCIA', 'V_PANEL_DUO_DOBLE_MANDO'),
           'Las compatibilidades mando↔apertura quedan como dependencias de opción en 11 y 15, más la regla de Panel Duo motorizado sin doble mando. Safra debe confirmar la equivalencia Bastón/Doble Bastón y si se crea «Cuatro bastones».'),
    'E13091-73': ('ValidaMandoVsApertura', 'ValidaMandoVsApertura', 'cubierta', ('V_OPCION_DEPENDENCIA',),
           'Bastón y Doble Bastón según la apertura quedan como dependencias de opción del mando en 49, 57 y 58.'),
    'E13095': ('ValidaTipoPlanoImplementacion', 'ValidaTipoPlanoImplementacion', 'pendiente', ('V_PLANO_SEGMENTOS', 'V_PLANO_COORDINADO', 'V_ANCHO_MIN_MOTOR'),
           'Cubiertos los segmentos del plano, el mismo coordinado por plano y localización y el ancho mínimo motorizado. Falta desarrollo para agrupar los segmentos por localización, y Safra debe confirmar si «misma ventana» equivale a la Localización.'),
    'E13095-10': ('ValidaMoneda', 'ValidaMoneda', 'pendiente', (),
           'Fuera del alcance del Sprint 1.7 (moneda y listas de precios): depende de asociar la lista de precios del cliente, pendiente de revisar con Safra.'),
    'E13095-12': ('ValidaMando', 'ValidaMando', 'pendiente_safra', ('V_MANDO_MOTOR_VINTAGE', 'V_OPCION_AUTO'),
           'Se activa el mando obligatorio en verticales y en Vintage motorizado se elige «Derecho» solo, con aviso y regla de respaldo. Safra debe confirmar que el campo es mando_position y por qué estaba apagado.'),
    'E13095-13': ('ValidaControlEnMotor', 'ValidaControlEnMotor', 'pendiente_safra', ('V_CONTROL_MOTOR', 'V_CONTROL_PEDIDO'),
           'Safra no quiere mensajes sino mostrar solo las combinaciones parametrizadas: los motores tubulares se filtran por el kit y V_CONTROL_MOTOR queda de respaldo. Falta la matriz control↔motor de riel y la asignación de las referencias de motores y controles.'),
    'E13095-14': ('ValidaMaxCombinaciones', 'ValidaMaxCombinaciones', 'cubierta', (),
           'Cubierta por el formulario: solo hay tela principal y hasta 4 combinadas, y solo en paneles, verticales y vintage.'),
    'E13095-15': ('ValidaCenefaPvc', 'ValidaCenefaPvc', 'pendiente', ('V_CENEFA_PVC_DIVIDIDA', 'V_RANGO_ANCHO', 'V_OPCION_AUTO'),
           'La advertencia unificada de cenefa PVC de más de 3 m y el mínimo de 0,30 m están cubiertos. Falta desarrollo para que forzar «¿Cenefa dividida? = No» salga como advertencia y no como el error general de opción automática.'),
    'E13095-16': ('ValidaInventario', 'ValidaInventario', 'pendiente', ('V_RANGO_ANCHO', 'V_RANGO_ALTO', 'V_TUBO_SIN_INSUMO', 'V_HANAS_COORDINADO', 'V_PERFIL_TELA', 'V_REVALIDACION'),
           'Fuera del alcance del Sprint 1.7 (stock por coordinado de cabezal y cenefa). Cubiertos medidas fuera de rango, insumos sin stock, Hanas solo Blanco y perfil Estándar con 0504063; falta la lista de Blackout de Romanas (Safra) y la revisión consolidada de insumos al confirmar.'),
    'E13095-17': ('ValidaInventarioTela', 'ValidaInventarioTela', 'pendiente', ('V_ROLLO_DISPONIBLE',),
           'Fuera del alcance del Sprint 1.7 (fórmula KISS de consumo de tela contra inventario). Hoy V_ROLLO_DISPONIBLE solo avisa cuando una pieza no cabe en ningún rollo.'),
    'E13095-18': ('ValidaObservacionesTela', 'ValidaObservacionesTela', 'cubierta', ('V_ANCHO_ROLLO',),
           'V_ANCHO_ROLLO bloquea cuando la persiana supera el ancho de la tela (OB0001), con el texto de Safra.'),
    'E13095-19': ('ValidaLocalizacion', 'ValidaLocalizacion', 'cubierta', ('V_LOCALIZACION',),
           'V_LOCALIZACION exige la localización con los mismos sistemas exentos de SAP.'),
    'E13095-20': ('ValidaComponentes', 'ValidaComponentes', 'pendiente_safra', ('V_ESTRUCTURA', 'V_ESTRUCTURA_CABEZAL'),
           'Componentes no identificados (salvo 2 en 1) y cabezal obligatorio en Premium están cubiertos. Safra debe asignar el cabezal de Sheer Elegance y confirmar si la tabla motorizada de 02/06 debe empezar en 2,01 m.'),
    'E13095-26': ('ValidaRequiereMotor', 'ValidaRequiereMotor', 'pendiente', ('V_REQUIERE_MOTOR', 'V_PESO_MAXIMO'),
           'V_REQUIERE_MOTOR obliga a motorizar por peso (la recomendación W12001 Safra la quita). Falta desarrollo: cuando el ancho no está en la tabla manual pero sí en la motorizada, hoy sale «sin componentes» en vez de «debe ir motorizada».'),
    'E13095-27': ('ValidaCoverLight', 'ValidaCoverLight', 'cubierta', ('V_COVERLIGHT_LUJO',),
           'Regla nueva Cover Light incompatible con Perfil de Lujo; el máximo de 6 m Safra lo quita.'),
    'E13095-29': ('ValidaEnrolle', 'ValidaEnrolle', 'cubierta', ('V_ENROLLE_SHEER',),
           'V_ENROLLE_SHEER exige enrollado al frente en Sheer 2 en 1.'),
    'E13095-3': ('ValidaAlineado', 'ValidaAlineado', 'pendiente', ('V_ALINEADO_LOCALIZACION', 'V_ALINEADO_MIN', 'V_ALINEADO_FRANJAS', 'V_ROLLO_ALINEADO'),
           'Mínimo 2 de la misma referencia y color, franjas con la misma altura y el rollo para las alineadas (ahora error) están cubiertos. Falta desarrollo para marcar Alineado automáticamente; el rollo en colores sin control por lotes depende de la fórmula KISS, fuera del alcance del Sprint 1.7.'),
    'E13095-38': ('ValidaCabezal', 'ValidaCabezal', 'cubierta', (),
           'Cubierta por la tabla de estructura: «Unificar mando» solo ofrece los tubos válidos, y en Sheer Elegance y Premium no aparece el tubo de 3 pulgadas.'),
    'E13095-40': ('ValidaSoporteMotor', 'ValidaSoporteMotor', 'inactivada', (),
           'Safra la inactiva: el soporte de motor lo da el kit motorizado.'),
    'E13095-43': ('ValidaTelas', 'ValidaTelas', 'cubierta', ('V_SEGUNDA_TELA', 'V_SHEER2EN1_REF', 'V_SHEER2EN1_REF2'),
           'Las tres reglas de Safra para Sheer 2 en 1: segunda tela obligatoria, primera referencia no Sheer y segunda referencia Sheer.'),
    'E13095-44': ('ValidaMaximoAnchoMismoAmbiente', 'ValidaMaximoAnchoMismoAmbiente', 'pendiente', (),
           'Safra cambia el límite de ancho por peso: falta desarrollo para sumar el peso de las persianas que dependen de un motor, y Safra debe dar la carga máxima de cada motor (hoy en 0).'),
    'E13095-45': ('ValidaCoordinados', 'ValidaCoordinados', 'cubierta', ('V_COORDINADOS',),
           'Regla nueva: mismo coordinado en la tela principal y las combinadas.'),
    'E13095-46': ('ValidaAnchoMotor', 'ValidaAnchoMotor', 'cubierta', ('V_ANCHO_MIN_MOTOR',),
           'V_ANCHO_MIN_MOTOR usa el ancho mínimo del producto del motor (0,80 m si no tiene dato) y lo muestra en el mensaje.'),
    'E13095-57': ('ValidaTelosApertura', 'ValidaTelosApertura', 'cubierta', ('V_PANEL_APERTURA', 'V_PANEL_RIEL', 'V_TELOS_LIBRE', 'V_TELOS_FIJOS_RIEL_SUIZO'),
           'Los topes por vías y apertura salen de la fórmula de canales; apertura libre con máximo 6 telos y el aviso de telos fijos con riel suizo son reglas nuevas.'),
    'E13095-58': ('ValidaAperturaVsTelos', 'ValidaAperturaVsTelos', 'cubierta', ('V_PANEL_RIEL',),
           'V_PANEL_RIEL obliga al Riel Velcrado con 7 telos unilaterales y 12 telos a extremos.'),
    'E13095-62': ('ValidaMotorizacion', 'ValidaMotorizacion', 'pendiente_safra', ('V_PANEL_MOTOR_MANDO', 'V_CONTROL_REQUERIDO', 'V_CONTROL_PEDIDO'),
           'Panel motorizado solo con mando izquierdo o derecho es regla nueva. Safra debe confirmar si el motor Panel Lujo exige control propio o acepta compartir canal con otra persiana.'),
    'E13095-64': ('ValidaRielDivido', 'ValidaRielDivido', 'pendiente_safra', ('V_OPCION_AUTO',),
           'El riel dividido se elige solo según el ancho máximo del riel. Falta que Safra fije el umbral (6,0 m aquí, 5,7 m en ValidaRiel) y cargue el ancho máximo de los rieles de 5 y 6 vías y Velcrado.'),
    'E13095-65': ('ValidaCombinaciones', 'ValidaCombinaciones', 'cubierta', ('V_TELAS_REPETIDAS',),
           'Activa desde el 27-oct: el archivo de Safra la marca «Mantener» (en la reunión del 24-sep se había pedido quitarla).'),
    'E13095-66': ('ValidaMotorizacion', 'ValidaMotorizacion', 'cubierta', (),
           'Cubierta por las opciones del sistema: en Motor Panel Ensamblado (34) el mando solo ofrece Izquierdo y Derecho.'),
    'E13095-67': ('ValidaMotorizacion', 'ValidaMotorizacion', 'cubierta', ('V_CORTINA_MOTOR_MANDO',),
           'Regla nueva: cortina motorizada solo con mando izquierdo o derecho.'),
    'E13095-68': ('ValidaAltura', 'ValidaAltura', 'pendiente_safra', ('V_CORTINA_ALTO_BASTON', 'V_CORTINA_ALTO_ONDATA', 'V_RANGO_ALTO'),
           'Cubiertos los máximos con Bastón (3,70 m), Ondata (2,70 m) y el general de 5 m. Safra debe confirmar si los 3,70 m aplican también a Doble Bastón.'),
    'E13095-69': ('ValidaAncho', 'ValidaAncho', 'pendiente_safra', ('V_OPCION_AUTO',),
           'El riel dividido se elige solo por encima de 5,80 m, motorizada o no, sin exigir motor. Safra debe confirmar si el máximo es 5,80 o 5,85 m.'),
    'E13095-70': ('ValidaApertura', 'ValidaApertura', 'cubierta', ('V_OPCION_DEPENDENCIA',),
           'Apertura libre solo con Doble Bastón queda como dependencia de opción del mando en 49, 57 y 58.'),
    'E13095-71': ('ValidaTelasEnCortina', 'ValidaTelasEnCortina', 'pendiente_safra', ('V_ONDATA_SISTEMA', 'V_PALOMINO_PROFUNDIDAD', 'V_VELO_RAIN_ALTO'),
           'Reglas nuevas para Ondata solo en Onda Moderna, Blackout Palomino sin profundidad 2.3 y Velo Rain hasta 3,0 m. Safra debe confirmar si Ondata se deja en Abrazadera Cortina (64).'),
    'E13095-72': ('ValidaProfundidadOnda', 'ValidaProfundidadOnda', 'pendiente_safra', (),
           'La profundidad 2.5 no se ofrece y la profundidad pasa a obligatoria en Onda Moderna (49). Safra debe confirmar si también es obligatoria en Pliegue Francés (57) y Riel Armado Cortina (58).'),
    'E13095-74': ('ValidaBajos', 'ValidaBajos', 'cubierta', ('V_OPCION_FORMULA',),
           'Las fórmulas de las opciones de bajo cubren el bajo incorrecto y el alto que no alcanza; el bajo pasa a obligatorio en 49 y 57.'),
    'E13095-75': ('ValidaModoCorte', 'ValidaModoCorte', 'pendiente_safra', ('V_ANCHO_ROLLO',),
           'En Odoo no hay «modo de corte» que pueda dar «no aplica»; solo bloquea la tela no atravesable más ancha que el rollo. Safra debe indicar en qué casos la cortina no se puede fabricar.'),
    'E13095-76': ('ValidaTipoPlanoCortinaCurvada', 'ValidaTipoPlanoCortinaCurvada', 'pendiente_safra', ('V_SEGMENTOS_CORTINA', 'V_CORTINA_CURVA_MANUAL', 'V_CORTINA_CURVA_BASTON', 'V_CORTINA_SEGMENTO_MIN', 'V_CORTINA_SEGMENTO_MAS', 'V_OPCION_DEPENDENCIA'),
           'Cubiertos plano↔apertura, suma de segmentos, mínimos de LID y U, solo manual y solo con bastón. Safra debe indicar dónde aplica el mínimo general de 40 cm.'),
    'E13095-77': ('ValidaTipoPlano', 'ValidaTipoPlano', 'pendiente', ('V_PLANO_SEGMENTOS',),
           'V_PLANO_SEGMENTOS exige la cantidad y la posición de las persianas de cada plano. Falta desarrollo para agrupar por plano y localización: hoy dos ventanas con el mismo plano chocan entre sí.'),
    'E13095-78': ('ValidaRielJunto', 'ValidaRielJunto', 'pendiente_safra', ('V_RIEL_JUNTO_SIGUIENTE', 'V_RIEL_JUNTO_ANTERIOR', 'V_RIEL_JUNTO_APERTURA'),
           'Parejas siguiente/anterior y apertura cubiertas con reglas nuevas. El mando no se revisa hasta que Safra confirme si las verticales llevan mando.'),
    'E13095-79': ('ValidaLamas', 'ValidaLamas', 'cubierta', ('V_MAX_LAMAS', 'V_LAMA_VERTICAL_MAX', 'V_LAMA_PESO'),
           'Lamas iguales a las calculadas, máximo 12 en Lama Vertical y peso de la lama hasta 0,5 kg; esta última solo actúa en las telas con peso cargado.'),
    'E13095-8': ('ValidaReferenciaPerfileria', 'ValidaReferenciaPerfileria', 'pendiente_safra', ('V_PERFIL_TELA', 'V_OPCION_TELA'),
           'V_PERFIL_TELA unifica tela↔perfil (Screen Jacquard Cristal con Estándar, Deluxe con Sheer Screen, 0504063). Falta la lista de Blackout de Safra para el aviso de puntos de luz con perfil Estándar o Lujo.'),
    'E13095-80': ('ValidaMando', 'ValidaMando', 'pendiente_safra', ('V_MANDO_MOTOR_VERTICAL',),
           'La regla queda creada, pero solo actúa cuando se active el campo Mando en verticales, lo que espera la confirmación de Safra.'),
    'E13095-81': ('ValidaAltos', 'ValidaAltos', 'cubierta', ('V_ALTO2_RANGO', 'V_ALTO2_MINIMO', 'V_ALTO1_MENOR'),
           'Tres reglas nuevas para el Alto 2 de Vertical Irregular: dentro de la ficha, mínimo 0,40 m y menor que el Alto 1.'),
    'E13095-82': ('ValidaAnchos', 'ValidaAnchos', 'pendiente_safra', ('V_RANGO_ANCHO',),
           'El máximo de 6 m lo da el rango del sistema; los 4,5 m con apertura a un lado Safra los quita. Safra debe confirmar si Vertical Irregular (hoy 4,50 m) también llega a 6 m.'),
    'E13095-83': ('ValidaLateralesCenefaPvc', 'ValidaLateralesCenefaPvc', 'cubierta', (),
           'Los laterales tienen valor por defecto «Sin», así que nunca quedan vacíos; se asocia la línea PVC CLASICA a los sistemas con cenefa PVC para que el campo se vea.'),
    'E13095-84': ('ValidaAnchoCenefaPvc', 'ValidaAnchoCenefaPvc', 'pendiente', ('V_CENEFA_PVC_DIVIDIDA', 'V_OPCION_AUTO'),
           'La advertencia de más de 3 m está cubierta. Falta desarrollo para que forzar «¿Cenefa dividida? = No» no salga como error general de opción automática.'),
    'E13095-9': ('ValidaPerfileria', 'ValidaPerfileria', 'pendiente_safra', ('V_PERFIL_TELA',),
           'Perfil obligatorio en 01, 06 y 32 y Deluxe con Sheer Screen cubiertos. Safra debe confirmar la asignación de perfiles en Sheer Elegance, Sheer 2 en 1 y demás sistemas, que hoy no muestran perfiles.'),
    'SIN-CODIGO-06': ('ValidaAncho', 'ValidaAncho', 'pendiente_safra', ('V_CORTE_ATRAVESADO', 'V_ANCHO_ROLLO'),
           'Registro repetido de ValidaAncho en «Comunes»: Safra la pasa a Enrollables, ver E13051. Mismas reglas y misma pregunta a Safra sobre atravesado obligatorio o informativo.'),
    'SIN-CODIGO-21': ('ValidaAnchoX3', 'ValidaAnchoX3', 'cubierta', ('V_ALTO_3X_ANCHO',),
           'V_ALTO_3X_ANCHO avisa cuando el alto supera tres veces el ancho.'),
    'SIN-CODIGO-39': ('ValidaBolsillo', 'ValidaBolsillo', 'cubierta', ('V_BOLSILLO_GARANTIA',),
           'Regla nueva: advertencia de garantía cuando la persiana lleva bolsillo.'),
    'SIN-CODIGO-41': ('ValidaTelaVsPerfil', 'ValidaTelaVsPerfil', 'pendiente_safra', ('V_PERFIL_COSTURA',),
           'V_PERFIL_COSTURA reúne los avisos de costura por ancho y por añadido. Faltan la lista de telas Screen de Safra para el aviso de arrugas con Perfil Lujo y las telas añadibles.'),
    'SIN-CODIGO-59': ('ValidaNoAplicaGarantia', 'ValidaNoAplicaGarantia', 'cubierta', (),
           'Sheer Poliester Chiara no está asociada a ningún panel, así que no se puede elegir. Si Safra la asocia, basta una regla de advertencia.'),
}
# Funciones del archivo que no tenían registro en el catálogo.
CATALOGO_NUEVOS = [
    ('SIN-CODIGO-85', 'ValidaDisenoImp', 'ValidaDisenoImp', 'Cuadro Lienzo', 'cubierta', ('V_CUADRO_DISENO', 'V_DISENO_SELECCION'),
     'Cubierta: el Cuadro Lienzo exige el diseño de impresión y el diseño elegido.'),
    ('SIN-CODIGO-86', 'Valida_Añadido', 'Valida_Añadido', 'Enrollables', 'pendiente_safra', ('V_ANADIDO', 'V_ANADIDO_MAXIMO',),
     'La regla OB0003 existe, pero ninguna tela está marcada como añadible: Safra debe marcar las telas.'),
    ('SIN-CODIGO-87', '¿Solicita Safra Express?', 'SolicitaSafraExpress', 'Comunes', 'cubierta', ('V_EXPRESS_CANTIDAD',),
     'Cubierta: Safra Express hasta el tope de unidades del parámetro safra.express_max_unidades.'),
]
# Función del archivo de Safra que implementa cada regla del portal.
FUNCION_REGLA = {
    'V_ALINEADO_ALTURA': 'ValidaAlineadoImplements',
    'V_ALINEADO_AMBIENTE': 'ValidaAlineadoMismoAmbiente',
    'V_ALINEADO_AMBIENTE_ALTO': 'ValidaAlineadoMismoAmbiente',
    'V_ALINEADO_FRANJAS': 'ValidaAlineado',
    'V_ALINEADO_LOCALIZACION': 'ValidaAlineado',
    'V_ALINEADO_MAXIMO': 'ValidaAlineadoImplements',
    'V_ALINEADO_MIN': 'ValidaAlineadoImplements',
    'V_ALINEADO_ORIENTACION': 'ValidaEnrolleVsAlineado',
    'V_ALTO1_MENOR': 'ValidaAltos',
    'V_ALTO2_MINIMO': 'ValidaAltos',
    'V_ALTO2_RANGO': 'ValidaAltos',
    'V_ALTO_3X_ANCHO': 'ValidaAnchoX3',
    'V_ALTO_MAXIMO': 'ValidaAlto',
    'V_ANADIDO': 'Valida_Añadido',
    'V_ANCHO_MIN_MOTOR': 'ValidaAnchoMotor',
    'V_ANCHO_ROLLO': 'ValidaObservacionesTela',
    'V_APERTURA_EXTREMOS_TRASLAPE': 'ValidaApertura',
    'V_ATRAVESADO': 'ValidaAtravesadoCliente',
    'V_BOLSILLO_GARANTIA': 'ValidaBolsillo',
    'V_CADENA_EXTRA': 'ValidaCadenaExtra',
    'V_CENEFA_ENTERA': 'ValidaCenefa',
    'V_CENEFA_METALICA_COLOR': 'ValidaCenefa',
    'V_CENEFA_METALICA_COORDINADO': 'ValidaCenefa',
    'V_CENEFA_PERFIL': 'ValidaCenefa',
    'V_CENEFA_PVC_DIVIDIDA': 'ValidaAnchoCenefaPvc',
    'V_CENEFA_TELA_FORRADA': 'ValidaCenefa',
    'V_CONTROL_MOTOR': 'ValidaControlEnMotor',
    'V_CONTROL_PEDIDO': 'ValidaControlEnMotor',
    'V_CONTROL_REQUERIDO': 'V03 motor con control compatible (hoja Validaciones_Formulario fila 8)',
    'V_COORDINADOS': 'ValidaCoordinados',
    'V_CORTE_ATRAVESADO': 'ValidaAncho',
    'V_CORTINA_ALTO_BASTON': 'ValidaAltura',
    'V_CORTINA_ALTO_ONDATA': 'ValidaAltura',
    'V_CORTINA_CURVA_BASTON': 'ValidaTipoPlanoCortinaCurvada',
    'V_CORTINA_CURVA_MANUAL': 'ValidaTipoPlanoCortinaCurvada',
    'V_CORTINA_MOTOR_MANDO': 'ValidaMotorizacion',
    'V_CORTINA_SEGMENTO_MAS': 'ValidaTipoPlanoCortinaCurvada',
    'V_CORTINA_SEGMENTO_MIN': 'ValidaTipoPlanoCortinaCurvada',
    'V_COVERLIGHT_LUJO': 'ValidaCoverLight',
    'V_CUADRO_DISENO': 'ValidaDisenoImp',
    'V_DISENO_SELECCION': 'ValidaDisenoImp',
    'V_ENROLLE_SHEER': 'ValidaEnrolle',
    'V_ESTAMPADO_ANADIDO': 'ValidaEstampado',
    'V_ESTAMPADO_FUERA_SERVICIO': 'ValidaEstampado',
    'V_ESTAMPADO_M2': 'ValidaEstampado',
    'V_ESTAMPADO_SHEER': 'ValidaEstampado',
    'V_ESTAMPADO_SHEER_ELEGANCE': 'ValidaEstampado',
    'V_ESTAMPADO_TELA': 'ValidaEstampado',
    'V_ESTRUCTURA': 'ValidaComponentes',
    'V_ESTRUCTURA_CABEZAL': 'ValidaComponentes',
    'V_EXPRESS_CANTIDAD': '¿Solicita Safra Express?',
    'V_HANAS_COORDINADO': 'ValidaInventario',
    'V_LAMAS_TELA': 'ValidaTelos',
    'V_LAMAS_TELA_SUMA': 'ValidaTelos',
    'V_LAMA_PESO': 'ValidaLamas',
    'V_LAMA_VERTICAL_MAX': 'ValidaLamas',
    'V_LOCALIZACION': 'ValidaLocalizacion',
    'V_MANDO_MOTOR_VERTICAL': 'ValidaMando',
    'V_MANDO_MOTOR_VINTAGE': 'ValidaMando',
    'V_MAX_LAMAS': 'ValidaLamas',
    'V_MOTOR_TUBO': 'V04 motor compatible con el tubo (hoja Validaciones_Formulario fila 9)',
    'V_ONDATA_SISTEMA': 'ValidaTelasEnCortina',
    'V_PALOMINO_PROFUNDIDAD': 'ValidaTelasEnCortina',
    'V_PANEL_APERTURA': 'ValidaApertura',
    'V_PANEL_DUO_DOBLE_MANDO': 'ValidaMandoVsApertura',
    'V_PANEL_DUO_TELOS': 'ValidaApertura',
    'V_PANEL_JUNTO_ANCHO': 'ValidaCaracteristicasPanelesJuntos',
    'V_PANEL_JUNTO_ANTERIOR': 'ValidaPanelJunto',
    'V_PANEL_JUNTO_APERTURA': 'ValidaCaracteristicasPanelesJuntos',
    'V_PANEL_JUNTO_DIVIDIDO': 'ValidaPanelJunto',
    'V_PANEL_JUNTO_SIGUIENTE': 'ValidaPanelJunto',
    'V_PANEL_JUNTO_TELOS': 'ValidaCaracteristicasPanelesJuntos',
    'V_PANEL_LAMAS': 'ValidaTelos',
    'V_PANEL_MOTOR_MANDO': 'ValidaMotorizacion',
    'V_PANEL_RECOMIENDA_MOTOR': 'RestriccionAnchoMaximoPersiana',
    'V_PANEL_RIEL': 'ValidaRiel',
    'V_PERFIL_COSTURA': 'ValidaTelaVsPerfil',
    'V_PERFIL_TELA': 'ValidaReferenciaPerfileria',
    'V_PESO_MAXIMO': 'ValidaAlto',
    'V_PLANO_COORDINADO': 'ValidaTipoPlanoImplementacion',
    'V_PLANO_SEGMENTOS': 'ValidaTipoPlanoImplementacion',
    'V_RANGO_ALTO': 'V02 alto en rango (hoja Validaciones_Formulario fila 7)',
    'V_RANGO_ANCHO': 'V01 ancho en rango (hoja Validaciones_Formulario fila 6)',
    'V_REQUIERE_MOTOR': 'ValidaRequiereMotor',
    'V_REVALIDACION': 'Validar existencias antes de confirmar (hoja Validaciones_Formulario fila 16)',
    'V_RIEL_GARANTIA': 'RestriccionAnchoMaximoPersiana',
    'V_RIEL_JUNTO_ANTERIOR': 'ValidaRielJunto',
    'V_RIEL_JUNTO_APERTURA': 'ValidaRielJunto',
    'V_RIEL_JUNTO_SIGUIENTE': 'ValidaRielJunto',
    'V_ROLLO_ALINEADO': 'ValidaAlineado',
    'V_ROLLO_DISPONIBLE': 'ValidaInventarioTela',
    'V_SECUENCIA': 'ValidaMismoAmbiente',
    'V_SECUENCIA_ALTO': 'ValidaSoportesIntermedios',
    'V_SECUENCIA_ANCHO': 'AnchoMaximoPersianaMismoCabezal',
    'V_SECUENCIA_CABEZAL': 'ValidaMismoAmbiente',
    'V_SECUENCIA_CANTIDAD': 'ValidaMismoAmbiente',
    'V_SECUENCIA_CONSECUTIVA': 'ValidaMismoAmbiente',
    'V_SECUENCIA_COORDINADO': 'ValidaMismoAmbiente',
    'V_SECUENCIA_MIN': 'ValidaMismoAmbiente',
    'V_SECUENCIA_NOMBRE': 'ValidaMismoAmbiente',
    'V_SECUENCIA_PENDIENTE': 'ValidaMismoAmbiente',
    'V_SECUENCIA_PERFIL': 'ValidaMismoAmbiente',
    'V_SECUENCIA_TUBO_DEP': 'ValidaTubo',
    'V_SEGMENTOS_CORTINA': 'ValidaTipoPlanoCortinaCurvada',
    'V_SEGUNDA_TELA': 'ValidaSegundaTela',
    'V_SESGO_TELA': 'ValidaSesgo',
    'V_SESGO_TODAS': 'ValidaSesgo',
    'V_SHEER2EN1_REF': 'ValidaTelas',
    'V_SHEER2EN1_REF2': 'ValidaTelas',
    'V_TELAS_REPETIDAS': 'ValidaCombinaciones',
    'V_TELOS_FIJOS_RIEL_SUIZO': 'ValidaTelosApertura',
    'V_TELOS_GARANTIA': 'ValidaTelos',
    'V_TELOS_LIBRE': 'ValidaTelosApertura',
    'V_TELO_FIJO': 'ValidaTeloFijo',
    'V_TELO_FIJO_MOTOR': 'ValidaTeloFijo',
    'V_TELO_FIJO_TRASLAPE': 'ValidaTeloFijo',
    'V_TRASLAPE_MINIMO': 'ValidaTraslape',
    'V_TRASLAPE_REFERENCIA': 'ValidaTraslape',
    'V_TUBO_SIN_INSUMO': 'ValidaInventario',
    'V_VELO_RAIN_ALTO': 'ValidaTelasEnCortina',
}

# Fila 142 (reunión 17-09): con una tela marcada «Añadido», cuando no se
# puede fabricar atravesando la tela (no es atravesable o el alto no cabe en
# el rollo), la persiana se fabrica añadida con alerta; bloquea si necesita
# más añadidos que el máximo de la referencia (0 = sin máximo).
_NO_ATRAVIESA = ("atravesable = tela.pierceable_type != 'no' "
                 "and alto <= ancho_rollo - estructura['aumento_tela']\n")
ANADIDOS = {
    # código: (condiciones anteriores, condición nueva, mensaje nuevo)
    'V_ANCHO_ROLLO': (
        ("tela and tela.pierceable_type == 'no' and ancho_rollo and ancho > ancho_rollo",),
        "tela and tela.pierceable_type == 'no' and not tela.is_anadido "
        "and ancho_rollo and ancho > ancho_rollo",
        None),
    'V_ANADIDO': (
        ("aumento = estructura.get('aumento_tela', 0)\n"
         "result = bool(tela) and tela.pierceable_type != 'no' and tela.is_anadido and bool(ancho_rollo) "
         "and ancho > ancho_rollo and alto > ancho_rollo - aumento",),
        _NO_ATRAVIESA + "maximo = tela.max_anadidos\n"
        "result = bool(tela) and tela.is_anadido and anadidos > 0 and not atravesable "
        "and (not maximo or anadidos <= maximo)",
        'OB0003: La persiana sale con añadido: el ancho supera el rollo de {ancho_rollo} m '
        'y necesita {anadidos} añadido(s).'),
    'V_CORTE_ATRAVESADO': (
        ("tela and tela.pierceable_type in ('si', 'si_cliente') and ancho_rollo "
         "and ancho > ancho_rollo and not linea.acepta_atravesado",),
        "tela and tela.pierceable_type in ('si', 'si_cliente') and ancho_rollo "
        "and ancho > ancho_rollo and not linea.acepta_atravesado "
        "and not (tela.is_anadido and alto > ancho_rollo - estructura['aumento_tela'])",
        None),
}
ANADIDO_MAXIMO = {
    'code': 'V_ANADIDO_MAXIMO',
    'name': 'Añadidos: no superar el máximo de la referencia',
    'funcion_safra': 'Valida_Añadido',
    'severity': 'error', 'momento': 'linea', 'trigger_field': None,
    'systems': ('01', '02', '06', '32', '61'), 'active': True,
    'condition': _NO_ATRAVIESA + "maximo = tela.max_anadidos\n"
                 "result = bool(tela) and tela.is_anadido and bool(maximo) and anadidos > maximo "
                 "and not atravesable",
    'message': ('E13095: La persiana necesita {anadidos} añadidos (rollo de {ancho_rollo} m) y la '
                'referencia {tela.name} permite máximo {maximo}. Reduzca el ancho o elija otra tela.'),
    'description': ('Fila 142 (reunión 17-09): la cantidad de añadidos no puede superar el Máximo '
                    'de añadidos de la referencia (Referencias / Telas › Parametrización).'),
}

# Archivos de Safra «Tipos de corte tela» (26-oct): las reglas del corte de
# la tela miran el tipo de corte que calcula la línea (tipo_corte).
SISTEMAS_PERSIANA = ('01', '06', '08', '10', '39', '32', '61')
SISTEMAS_CORTINA = ('49', '57')
CORTE_TELA = {
    # código: (nombre, condiciones anteriores, condición, mensajes anteriores,
    #          mensaje, sistemas anteriores, sistemas)
    'V_ANCHO_ROLLO': (
        'Corte de la tela: la configuración no se puede fabricar',
        ("tela and tela.pierceable_type == 'no' and ancho_rollo and ancho > ancho_rollo",
         ANADIDOS['V_ANCHO_ROLLO'][1]),
        "tipo_corte == 'no_fabricable'",
        ('E20007: El ancho digitado ({ancho} m) supera el ancho del rollo ({ancho_rollo} m) y '
         'la tela no es atravesable; no es posible fabricarla.',
         CAMBIOS['V_ANCHO_ROLLO']['message']),
        'E13095: La configuración NO se puede fabricar con la tela {tela.name}: {motivo_corte}.',
        ('01', '02', '06', '32', '61'), SISTEMAS_PERSIANA + SISTEMAS_CORTINA),
    'V_CORTE_ATRAVESADO': (
        'Corte de la tela: la persiana se corta atravesada',
        ANADIDOS['V_CORTE_ATRAVESADO'][0] + (ANADIDOS['V_CORTE_ATRAVESADO'][1],),
        "tipo_corte == 'atravesado' and not linea.acepta_atravesado",
        ('E20017: Con el ancho digitado ({ancho} m) la tela {tela.name} se cortará '
         'atravesada (rollo de {ancho_rollo} m); marque la aceptación del corte '
         'atravesado para continuar.',),
        'E20017: Por las medidas de la persiana y el ancho del rollo ({ancho_rollo} m), la tela '
        '{tela.name} se cortará atravesada; marque la aceptación del corte atravesado para continuar.',
        ('01', '02', '06', '32', '61'), SISTEMAS_PERSIANA),
    'V_ANADIDO': (
        'Corte de la tela: la persiana sale con añadido',
        ANADIDOS['V_ANADIDO'][0] + (ANADIDOS['V_ANADIDO'][1],),
        "tipo_corte == 'anadido'",
        ('OB0003: La persiana sale con añadido.', ANADIDOS['V_ANADIDO'][2]),
        'OB0003: Por las medidas de la persiana y el ancho del rollo, la persiana saldrá con añadido.',
        ('01', '02', '06', '32', '61'), SISTEMAS_PERSIANA),
    'V_ANADIDO_MAXIMO': (
        'Corte de la tela: no superar el máximo de añadidos',
        (ANADIDO_MAXIMO['condition'],),
        "tipo_corte == 'anadido_excede'",
        (ANADIDO_MAXIMO['message'],),
        'E13095: La persiana necesita {anadidos} añadidos y la tela {tela.name} permite máximo '
        '{maximo_anadidos}. Reduzca el alto o elija otra tela.',
        ('01', '02', '06', '32', '61'), SISTEMAS_PERSIANA),
}

# Revisión 30-oct (U_Ancho): sin ancho del rollo en el color (vale 0) no se
# puede calcular el corte; Error por ahora, Safra puede dejarla en Advertencia.
SIN_ANCHO_ROLLO = {
    'code': 'V_SIN_ANCHO_ROLLO', 'name': 'Corte de la tela: el color no tiene ancho del rollo',
    'funcion_safra': 'ValidaObservacionesTela', 'severity': 'error', 'momento': 'linea',
    'systems': SISTEMAS_PERSIANA + SISTEMAS_CORTINA,
    'condition': "tipo_corte == 'sin_ancho_rollo'",
    'message': 'E13095: La configuración NO se puede fabricar con la tela {tela.name}: '
               '{motivo_corte}.',
    'description': 'Revisión 30-oct: el ancho del rollo es el U_Ancho del producto del color; '
                   'sin dato vale 0 y la restricción del corte se toma desde ese valor.',
}

# Cortinas: el Dobladillo o Bajo falso sigue el tipo de corte (opción:
# (se ofrece si, se elige sola si, aviso)).
_DOBLADILLO_17 = (
    "# Archivo de Safra «Cortinas Cálculo Tipo de Corte Tela» (26-oct): con corte\n"
    "# normal o por paños se ofrecen los dobladillos; con bajo falso, solo el bajo falso.\n"
    "result = tipo_corte != 'bajo_falso'")
DOBLADILLO_CORTE = {
    'BN_FLTE': (_DOBLADILLO_17, None, None),
    'BN_03': (_DOBLADILLO_17, None, None),
    'BN_10': (_DOBLADILLO_17, None, None),
    'BN_15': (_DOBLADILLO_17, None, None),
    'BN_FALSO': (
        "# Alto ≤ ancho del rollo + 12 cm y tela sin diseño (Ajustes › Corte de la tela).\n"
        "result = tipo_corte == 'bajo_falso'",
        "result = tipo_corte == 'bajo_falso'",
        'Su cortina saldrá con bajo falso de 15 centímetros.'),
    'BN_PANOS': (
        "# La tela permite paños (Añadido) y el rollo alcanza (Ajustes › Corte de la tela).\n"
        "result = tipo_corte == 'panos'",
        None,
        'OB0006: Por el alto solicitado, se utilizarán paños del ancho de la tela y va con '
        'añadido vertical.'),
}

# Revisión 30-oct (Dobladillo o Bajo falso): cada dobladillo tiene su consumo
# (hoja Parametros del Excel de cortinas) y se ofrece si el alto pedido cabe
# con él; con corte por paños el alto sale del largo del rollo y van todos.
DOBLADILLO_CONSUMO = {'BN_FLTE': 0.06, 'BN_03': 0.07, 'BN_10': 0.15, 'BN_15': 0.21}
DOBLADILLO_30OCT = (
    "# Revisión 30-oct: el dobladillo aplica si el alto cabe con su consumo\n"
    "# (alto_maximo_opcion = ancho del rollo + riel − dobladillo superior − consumo).\n"
    "# Con corte por paños el alto sale del largo del rollo y aplican todos.\n"
    "result = tipo_corte in ('', 'panos') or alto <= alto_maximo_opcion")

# Revisión 30-oct: las fórmulas del corte de las cortinas se ven y se cambian
# en Ajustes › Corte de la tela (parámetro: fórmula por defecto).
FORMULAS_CORTE_CORTINA = {
    'safra.formula.alto_maximo_dobladillo': (
        "# Alto máximo de la cortina con un dobladillo (Excel de Safra, hoja Parametros).\n"
        "result = ancho_rollo + riel - dobladillo_superior - consumo"),
    'safra.formula.cortina_normal': (
        "# Corte normal: el alto cabe con el dobladillo que más alto permite.\n"
        "result = alto <= alto_maximo_dobladillo"),
    'safra.formula.cortina_bajo_falso': (
        "# Bajo falso: hasta el ancho del rollo + el bajo falso. Reunión 30-oct (fila 143,\n"
        "# punto 5): también con tela atravesable (con diseño) se evalúa primero el bajo\n"
        "# falso y, si no alcanza, los paños.\n"
        "result = alto <= ancho_rollo + tolerancia_bajo_falso"),
}
# Fórmula del bajo falso hasta la reunión 30-oct: si quedó guardada así en
# Ajustes, el ajuste la cambia por la nueva.
CORTINA_BAJO_FALSO_ANTERIOR = (
    "# Bajo falso: hasta el ancho del rollo + el bajo falso, y la tela sin diseño.\n"
    "result = alto <= ancho_rollo + tolerancia_bajo_falso and not tela_con_diseno")

# Reunión 30-oct (fila 143, puntos 4 y 6): en cortinas la tela atravesable se
# corta por paños; siempre que el corte sea por paños, el cliente lo acepta
# (check «Acepto que la tela se corte por paños») o no se guarda la línea ni se cierra el pedido.
CORTE_PANOS = {
    'code': 'V_CORTE_PANOS', 'name': 'Corte de la tela: la cortina se corta por paños',
    'funcion_safra': 'ValidaObservacionesTela', 'severity': 'error', 'momento': 'linea',
    'systems': SISTEMAS_CORTINA,
    'condition': "tipo_corte == 'panos' and not linea.acepta_atravesado",
    'message': 'E20017: Con este ancho la tela se cortará a paños (ancho del rollo: '
               '{ancho_rollo} m). Marque la aceptación para continuar.',
    'description': 'Reunión 30-oct (fila 143, puntos 4 a 6): cortinas con corte por paños '
                   '(alto mayor que el bajo falso y tela con Añadido o atravesable). Sale junto a '
                   'la tela y no deja guardar la persiana ni cerrar el pedido hasta marcar '
                   '«Acepto que la tela se corte por paños».',
}
# Barrido de la matriz (03-nov): reglas nuevas con su condición en
# Validaciones (el código solo calcula las variables).
MANDO_OBLIGATORIO = {
    'code': 'V_MANDO_OBLIGATORIO', 'name': 'Posición del mando obligatoria sin Mismo cabezal',
    'funcion_safra': 'ValidaComponentes', 'severity': 'error', 'momento': 'linea',
    'systems': (),
    'condition': "'mando_position' in campos and not same_header and not mando_position",
    'message': 'E13095: Seleccione la Posición del mando.',
    'description': 'Reunión 30-oct (fila 77): sin «Mismo cabezal» la Posición del mando es '
                   'obligatoria. Con Mismo cabezal el campo queda bloqueado: el mando lo define '
                   'la secuencia. Solo en los sistemas que tienen el campo («\'mando_position\' in '
                   'campos»).',
}
DESPACHO_DATOS = {
    'code': 'V_DESPACHO_DATOS', 'name': 'Datos de despacho: país, ciudad y destinatario',
    'funcion_safra': 'ValidaDespacho', 'severity': 'error', 'momento': 'pedido',
    'systems': (),
    'condition': ("pedido['pide_despacho'] and not pedido['recoge_fabrica'] "
                  "and not (pedido['pais'] and pedido['ciudad'] and pedido['destinatario'])"),
    'message': 'E13095: Complete los datos de despacho: país, ciudad y nombre del destinatario '
               '(o marque «Recoge en fábrica»).',
    'description': 'Matriz, Datos de despacho (filas 184-188): si el pedido no se recoge en '
                   'fábrica, pide país, ciudad y destinatario al finalizar. pedido[\'pide_despacho\'] '
                   'es verdadero cuando el formulario trae los datos de despacho: las cotizaciones '
                   'guardadas antes de este cambio no se revisan.',
}
# Reunión 28-oct (fila 89, min 2:09-2:17 de la grabación): en Panel Japonés y
# Panel Duo hay varias telas; con «Cenefa en tela» hay que elegir con cuál se
# hace la cenefa. «Tela de Cenefa» sigue atada a «¿Cenefa forrada?» (la
# metálica forrada); este campo aparece con Cenefa en tela y lista las telas
# elegidas en el pedido (como «Tela de Cenefa»).
CENEFA_EN_TELA_CAMPO = {
    'code': 'cenefa_tela_panel', 'name': 'Tela de la cenefa en tela',
    'systems': ('11', '54'),
    'help': 'Cuál de las telas elegidas en el pedido se usa para la cenefa en tela.',
}
CENEFA_EN_TELA_TELA = {
    'code': 'V_CENEFA_EN_TELA_TELA', 'name': 'Cenefa en tela: elegir la tela de la cenefa',
    'funcion_safra': 'ValidaCenefa', 'severity': 'error', 'momento': 'linea',
    'systems': CENEFA_EN_TELA_CAMPO['systems'],
    'condition': ("cenefa_panel == 'I100002014' and 'cenefa_tela_panel' in campos "
                  "and not cenefa_tela_panel.strip()"),
    'message': 'E13084: Seleccione la tela de la cenefa en tela.',
    'description': 'Reunión 28-oct (fila 89): con «Cenefa en tela» (I100002014, línea de la '
                   'referencia Cenefas) hay que elegir cuál de las telas de la persiana lleva la '
                   'cenefa. Solo en los sistemas que tienen el campo «Tela de la cenefa en tela».',
}
# Revisión 10-nov: reglas con la condición escrita en Validaciones (no en el
# código); el cálculo interno solo deja las variables.
# Dato del maestro sin digitar: `datos_sin_digitar` = [{'dato', 'usos'}].
DATO_SIN_DIGITAR = {
    'code': 'V_DATO_SIN_DIGITAR', 'name': 'Dato del maestro sin digitar',
    'funcion_safra': '', 'severity': 'warning', 'momento': 'linea',
    'systems': (),
    'condition': ("faltan = '; '.join([d['dato'] + ' (lo usa ' + d['usos'] + ')' "
                  "for d in datos_sin_digitar])\n"
                  "result = bool(datos_sin_digitar)"),
    'message': 'Falta digitar {faltan}. Mientras esté vacío no se calcula bien.',
    'description': 'Una validación o una fórmula (tubo, lamas, opciones…) usa un dato del maestro, '
                   'de Referencias o de la Estructura por Ancho que está vacío (sin digitar; un 0 '
                   'digitado no avisa). datos_sin_digitar trae cada dato: d[\'dato\'] = qué falta y '
                   'dónde, d[\'usos\'] = qué validaciones o fórmulas lo usan. Con severidad Error '
                   'no deja finalizar el pedido hasta que se digite.',
}
# Fila 68 (punto 2): el peso de la persiana contra la carga máxima (del motor
# elegido o del mecanismo). Si manual no se puede pero con motor sí, sale
# V_REQUIERE_MOTOR (estructura['tubo_motor']) y esta no.
PESO_MAXIMO_CONDICION = (
    "quien = 'el motor elegido' if estructura['motor_elegido'] else 'el mecanismo'\n"
    "result = estructura['peso'] > 0 and not vacio(estructura['carga']) "
    "and estructura['peso'] > estructura['carga'] and not estructura['tubo_motor']")
PESO_MAXIMO_MENSAJE = (
    'E13095: La persiana no se puede fabricar: {quien} no soporta el peso de la persiana '
    '(peso calculado {estructura[peso]:.0f} g; carga máxima {estructura[carga]:.0f} g). '
    '{estructura[carga_detalle]}')
# Revisión 10-nov: las demás reglas del tubo, también con la condición escrita
# (antes «hallazgo»). Mismo funcionamiento que el cálculo interno.
REQUIERE_MOTOR_CONDICION = (
    "tubo_motor = estructura['tubo_motor']\n"
    "result = bool(tubo_motor)")
ALTO_MAXIMO_CONDICION = (
    "alto and not vacio(estructura['alto_maximo']) and alto > estructura['alto_maximo']")
ESTRUCTURA_CONDICION = (
    "estructura['tabla'] and ancho and not estructura['encontrada'] "
    "and not estructura['tubo_motor'] and sistema not in ('32', '61')")
PESO_SIN_CARGA = {
    'code': 'V_PESO_SIN_CARGA', 'name': 'Motor sin Torque ni Carga máxima en el maestro',
    'funcion_safra': 'ValidaAlto', 'severity': 'error', 'momento': 'linea',
    'systems': (),
    'condition': "estructura['motor_elegido'] and estructura['peso'] > 0 and vacio(estructura['carga'])",
    'message': ('E13095: El motor elegido no tiene Torque ni Carga máxima en el maestro de '
                'productos: no hay con qué comparar el peso de la persiana '
                '({estructura[peso]:.0f} g). {estructura[carga_detalle]}'),
    'description': 'Reunión 09-nov (fila 68): con un motor elegido la carga máxima sale solo de su '
                   'maestro (Torque o Carga maxima); si los dos están vacíos no hay con qué comparar '
                   'el peso. estructura[\'carga_detalle\'] dice cómo está cada dato.',
}
REGLAS_BARRIDO = (MANDO_OBLIGATORIO, DESPACHO_DATOS, CENEFA_EN_TELA_TELA, DATO_SIN_DIGITAR,
                  PESO_SIN_CARGA)
# Barrido de la matriz (fila 124, captura del portal actual de Safra del
# 4-nov): orden de las características en el resumen del pedido. Cada grupo
# es un renglón de esa captura con los campos que en este portal dicen lo
# mismo (p. ej. las perfilerías de los 2 en 1 junto a «Tipo de Perfil»). Lo
# que la captura no muestra va después, en el orden del formulario.
ORDEN_RESUMEN = (
    ('perfil', 'perfil_sheer', 'perfileria2'),            # Tipo de Perfil
    ('coordinado',),                                      # Coordinado
    ('mando_position', 'mando_position_back', 'mando2', 'mando_panel',
     'mando_vertical', 'mando_cortina'),                  # Posición del mando
    ('aligned',),                                         # Alineado
    ('orientation',),                                     # Orientación del Enrollado
    ('has_motor', 'motor', 'interruptor_rf', 'interruptor_panel'),  # Motor
    ('control',),                                         # Control
    ('motor_support_type',),                              # Tipo de Soporte Motor
    ('cenefa_type', 'cenefa_panel', 'cenefa_corte', 'perfil_cenefa', 'cenefa_lateral',
     'cenefa_longitud', 'cenefa_dividida', 'cenefa_lined', 'cenefa_tela', 'Tela_Cenefa2',
     'cenefa_tela_panel', 'corte_cenefa', 'color_cenefa'),  # Cenefa PVC
    ('control_channel', 'requires_charger'),              # Canal del Control
    ('unificacion_mando',),                               # Unificación Mando
    ('escuadras',),                                       # Escuadras
    ('location',),                                        # Localización
    ('atravesar_tela', 'acepta_atravesado'),              # Atravesar Tela
    ('enclosed',),                                        # Persiana Encajonada
    ('bolsillo_size',),                                   # Tamaño del bolsillo
)
# Reunión 3-nov: el check dice que es el cliente quien acepta los paños.
CORTE_PANOS_ETIQUETA = 'Acepto que la tela se corte por paños'
CORTE_PANOS_ETIQUETA_ANTERIOR = 'Acepta corte por paños'
CORTE_PANOS_AYUDA = ('Marque Sí para confirmar que acepta que su cortina se fabrique uniendo paños de '
                     'tela, porque el alto supera el ancho del rollo. Sin esta aceptación no se puede '
                     'guardar la persiana ni enviar el pedido.')

# Variables de esas fórmulas, con un valor de ejemplo para revisarlas al guardar.
VARIABLES_CORTE_CORTINA = {
    'alto': 2.5, 'ancho': 2.0, 'ancho_rollo': 2.8, 'riel': 0.035, 'dobladillo_superior': 0.06,
    'dobladillo_inferior_max': 0.21, 'tolerancia_bajo_falso': 0.12, 'consumo': 0.06,
    'alto_maximo_dobladillo': 2.715, 'tela_con_diseno': False, 'tela_permite_panos': False,
}

# Revisión 30-oct: fórmulas de alto y peso máximo del tubo (hojas 3/4 del Excel
# de la matriz), visibles y editables en Ajustes › Tubo: alto y peso máximo.
FORMULAS_TUBO = {
    'safra.formula.tubo_alto_espacio': (
        "# Alto máximo por espacio: cuántas vueltas de tela caben entre el tubo y el techo.\n"
        "# Sin grosor de la tela o sin datos del tubo no se calcula (None).\n"
        "result = None\n"
        "if grosor_tela and espacio_eje_techo and diametro_tubo:\n"
        "    result = ((espacio_eje_techo - diametro_tubo / 2) / grosor_tela) * (pi * diametro_tubo) / 1000"),
    'safra.formula.tubo_alto_carga': (
        "# Alto máximo por carga: lo que soporta el mecanismo o el motor, menos el perfil,\n"
        "# repartido en el peso de la tela.\n"
        "result = None\n"
        "if peso_tela and ancho and carga_maxima:\n"
        "    result = (carga_maxima - ancho * peso_perfil) / (peso_tela * factor * ancho)"),
    'safra.formula.tubo_peso_total': (
        "# Peso total de la persiana (g): la tela más el perfil.\n"
        "result = None\n"
        "if peso_tela and ancho and alto:\n"
        "    result = ancho * alto * peso_tela * factor + peso_perfil * ancho"),
    # Reunión 30-oct (fila 168): carga máxima del motor según su torque.
    'safra.formula.tubo_carga_motor': (
        "# Carga máxima (g) del motor sobre el tubo: torque (N·m) × 100 ÷ diámetro externo\n"
        "# del tubo (mm) × 1000. Sin torque no se calcula y se usa la Carga máxima del motor.\n"
        "result = None\n"
        "if torque and diametro_tubo:\n"
        "    result = torque * 100 / diametro_tubo * 1000"),
}
VARIABLES_TUBO = {
    'ancho': 1.5, 'alto': 1.8, 'peso_tela': 300.0, 'grosor_tela': 0.5, 'peso_perfil': 136.0,
    'factor': 1.0, 'espacio_eje_techo': 40.0, 'diametro_tubo': 32.0, 'carga_maxima': 3500.0,
    'torque': 6.0, 'pi': 3.141592653589793,
}

# Factor de confección del Excel de Safra (valor de ejemplo, Safra lo ajusta).
FACTOR_CONFECCION = {'49': 2.8, '57': 2.8}

# Reunión 28-oct (fila 91): la cenefa en tela no tiene producto en el
# maestro; se hace con la tela de la persiana y sigue las reglas del
# atravesable. El programa calcula tipo_corte_cenefa ('entera': cabe en el
# rollo; 'atravesada': lo supera y la tela es atravesable; 'anadida': lo
# supera y la tela no es atravesable). Opción: (campo de la fórmula, fórmula).
CORTE_CENEFA_TELA = {
    ('corte_cenefa', '2', 'auto_formula'): (
        "# Reunión 28-oct (fila 91): la cenefa (con laterales) cabe en el rollo: va entera.\n"
        "result = tipo_corte_cenefa == 'entera'"),
    ('corte_cenefa', '2', 'formula'): (
        "# Reunión 28-oct (fila 91): si supera el rollo, entera solo con tela atravesable\n"
        "# (se corta atravesada, con costo adicional).\n"
        "result = tipo_corte_cenefa != 'anadida'"),
    ('corte_cenefa', '1', 'auto_formula'): (
        "# Reunión 28-oct (fila 91): supera el rollo y la tela no es atravesable: va añadida.\n"
        "result = tipo_corte_cenefa == 'anadida'"),
}
CORTE_CENEFA_AVISO = ('La tela no se puede atravesar y la cenefa supera el ancho del rollo: '
                      'la cenefa va añadida.')
CENEFA_ENTERA_28OCT = (
    "# Reunión 28-oct (fila 91): cenefa entera con tela no atravesable que supera el rollo.\n"
    "result = corte_cenefa == '2' and tipo_corte_cenefa == 'anadida'",
    "E13079: La referencia [{tela.name}] no se puede atravesar y la cenefa (ancho con laterales "
    "{ancho_cenefa:.2f} m) supera el rollo ({ancho_rollo} m). Establezca el corte en 'Cenefa añadida'.")
