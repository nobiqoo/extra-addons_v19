(function () {
    'use strict';

    var systems = [];
    var currentFabrics = [];
    // Reunión 09-oct (fila 20): familia que exige cada campo de referencia
    // del sistema (Sheer 2 en 1: Referencia 1 Blackout, Referencia 2 Sheer).
    var currentFamilias = {};
    var fabricsById = {};
    var defaultConfig = { fields: [] };
    var defaultSystemId = 0;
    var lineCount = 0;

    var UNIT = { width: 'mts', height: 'mts', width2: 'mts', height2: 'mts', quantity: 'und', extra_chain: 'metros', print_m2: 'm²' };
    var IMG_BASE = '/website_quotes_safra/static/src/img';
    var IMG_NOTFOUND = IMG_BASE + '/imagenotfound.jpg';

    function esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }
    function opt(value, label, selected) {
        return '<option value="' + esc(value) + '"' + (selected ? ' selected' : '') + '>' + esc(label) + '</option>';
    }
    function money(n) { return '$ ' + Math.round(n || 0).toLocaleString('es-CO'); }

    function rpc(url, params) {
        return fetch(url, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: params }),
        }).then(function (r) { return r.json(); }).then(function (d) { return d.result; });
    }

    function buildSystemOptions(selectedId) {
        var html = opt('', '-- Seleccione --', false);
        systems.forEach(function (s) { html += opt(s.id, s.name, String(s.id) === String(selectedId)); });
        return html;
    }
    function fabricOptions(code) {
        // Sprint1-rev: las telas sin stock se muestran en gris (deshabilitadas)
        // en lugar de ocultarse, para que el cliente sepa que existen.
        var html = opt('', '-- Seleccione --', false);
        var familia = currentFamilias[code];
        currentFabrics.forEach(function (f) {
            if (familia && !f[familia]) return;
            if (f.available === false) {
                html += '<option value="' + esc(f.id) + '" disabled>' + esc(f.name) + ' (sin stock)</option>';
            } else {
                html += opt(f.id, f.name, false);
            }
        });
        return html;
    }

    // --- Render de un control según tipo (estilo cliente) ---
    function renderControl(f, idx) {
        var name = f.code + '_' + idx;
        var req = f.required ? ' required' : '';
        var ph = f.placeholder ? ' placeholder="' + esc(f.placeholder) + '"' : '';
        var unit = UNIT[f.code];
        // Fase 5.4a: Tela Cabezal Forrado y Tela de Cenefa se llenan con las
        // telas ya elegidas en el pedido (sin importar el tipo del campo).
        if (f.code === 'cabezal_tela' || f.code === 'cenefa_tela') {
            return '<select name="' + name + '" class="form-select fld-input sel-telas-pedido"' + req + '>' +
                '<option value="">-- Seleccione la tela --</option></select>';
        }
        switch (f.type) {
            case 'fabric':
                var target = f.code.replace('fabric_id', 'color_id');
                return '<select name="' + name + '" class="form-select sel-fabric" data-color-target="' + target + '"' + req + '>' + fabricOptions(f.code) + '</select>';
            case 'color':
                return '<select name="' + name + '" class="form-select sel-color"' + req + ' disabled><option value="">-- Seleccione referencia --</option></select>';
            case 'boolean':
                return renderToggle(name, f.default === '1' || f.default === true);
            case 'design':
                // Puntos 10-11: el diseño se elige directo en la galería con
                // imágenes (sin select); el input oculto guarda el código.
                // OBS 11-sep: el check «Diseño propio» solo aplica al diseño
                // de impresión (custom_design); la textura es solo catálogo.
                designOptionsByIdx[idx + ':' + f.code] = f.options || [];
                return '<input type="hidden" name="' + name + '" class="fld-input">' +
                    '<button type="button" class="btn-design-gallery"><i class="fa fa-th"></i> Ver catálogo con imágenes</button>' +
                    (f.code === 'custom_design'
                        ? '<label class="design-own-check"><input type="checkbox" class="chk-design-own"> Diseño propio (subir mi imagen sin buscar en el catálogo)</label>'
                        : '') +
                    '<div class="design-preview d-none"><img alt="Diseño elegido"/><span class="dp-name"></span>' +
                    '  <a href="#" class="dp-clear" title="Quitar el diseño elegido">Quitar</a></div>' +
                    '<div class="design-gallery d-none"></div>';
            case 'ref_categoria': // P16/5.1: tabla de productos de la categoría
            case 'selection':
                var o = '<option value="">-- Seleccione uno --</option>';
                (f.options || []).forEach(function (it) {
                    // Fase 5.1: dmax = densidad máxima de tela que soporta el
                    // insumo; 5.4a: forrado/cargador gobiernan campos
                    // dependientes del cabezal y el motor.
                    o += '<option value="' + esc(it.value) + '"' +
                        (it.img ? ' data-img="' + esc(it.img) + '"' : '') +
                        (it.seg ? ' data-seg="' + esc(it.seg) + '"' : '') +
                        (it.dmax ? ' data-dmax="' + esc(it.dmax) + '"' : '') +
                        (it.forrado !== undefined ? ' data-forrado="' + esc(it.forrado) + '"' : '') +
                        (it.cargador !== undefined ? ' data-cargador="' + esc(it.cargador) + '"' : '') +
                        (it.sin ? ' data-sin="1"' : '') +
                        (it.value === f.default ? ' selected' : '') + '>' +
                        esc(it.label) + '</option>';
                });
                // Revisión 17-sep: opciones con imagen (aperturas, planos,
                // perfiles) — miniaturas elegibles bajo el desplegable.
                // Pendientes 24-sep (8.2/8.3): modo de presentación por
                // campo — lista / lista+miniaturas / lista+foto grande /
                // solo botones; en automático, solo botones cuando TODAS
                // las opciones tienen imagen.
                var withImg = (f.options || []).filter(function (it) { return it.img; });
                var mode = f.display || 'auto';
                if (mode === 'auto') {
                    mode = !withImg.length ? 'list'
                        : (withImg.length === (f.options || []).length ? 'buttons' : 'list_thumbs');
                }
                if (!withImg.length) mode = 'list';
                var hideSel = mode === 'buttons' || mode === 'list_thumbs';
                var selHtml = '<select name="' + name + '" class="form-select fld-input' +
                    (hideSel ? ' sel-img-only' : '') + '"' +
                    ' data-display="' + mode + '"' + req + '>' + o + '</select>';
                if (mode === 'buttons') {
                    selHtml += '<div class="opt-thumbs" data-for="' + name + '">' +
                        (f.options || []).filter(function (it) { return it.value; }).map(function (it) {
                            return '<div class="opt-thumb' + (it.img ? '' : ' opt-thumb-text') + '" data-value="' + esc(it.value) + '" title="' + esc(it.label) + '">' +
                                (it.img ? '<img loading="lazy" src="' + esc(it.img) + '" alt=""/>' : '') +
                                '<span>' + esc(it.label) + '</span></div>';
                        }).join('') + '</div>';
                }
                // 29-sep (8.3): «Lista con foto pequeña» = desplegable
                // propio con la miniatura JUNTO a cada opción (el select
                // nativo no pinta imágenes); el select oculto conserva el
                // valor y la validación, y el menú se regenera desde sus
                // opciones al abrir (respeta kits/densidad/filtros).
                if (mode === 'list_thumbs') {
                    selHtml += '<div class="sel-imgdrop" data-for="' + name + '">' +
                        '<button type="button" class="sid-toggle">' +
                        '<span class="sid-thumb"></span>' +
                        '<span class="sid-label">-- Seleccione uno --</span>' +
                        '<span class="sid-caret">▾</span></button>' +
                        '<div class="sid-menu d-none"></div></div>';
                }
                return selHtml;
            case 'integer':
            case 'float':
                var step = f.type === 'integer' ? '1' : '0.001';
                var dimClass = (f.code === 'width' || f.code === 'height') ? ' inp-dim' : '';
                // M² de impresión: calculado (ancho × alto), no digitable.
                var ro = (f.code === 'print_m2' || f.code === 'ancho_telo' ||
                    (f.code === 'quantity_lamas' && f.max_lamas)) ? ' readonly' : '';
                // Pendientes 24-sep (9.1): el máximo de lamas se calcula
                // con ancho + apertura — mientras falten, el campo lo dice
                // en vez de quedar vacío sin explicación.
                if (f.code === 'quantity_lamas' && f.max_lamas && !ph) {
                    ph = ' placeholder="Se calcula al digitar ancho y elegir apertura"';
                }
                // Pendientes 24-sep (5.1): los enteros (Cantidad, lamas…)
                // no aceptan decimales ni desde el teclado.
                var intAttr = f.type === 'integer' ? ' inputmode="numeric" data-int="1"' : '';
                var inp = '<input type="number" step="' + step + '" min="0" name="' + name + '" class="form-control fld-input' + dimClass + '" value="' + esc(f.default || '') + '"' + req + ph + ro + intAttr + '>';
                if (unit) {
                    return '<div class="input-group">' + inp + '<span class="input-group-text">' + esc(unit) + '</span></div>';
                }
                return inp;
            default: // char
                // Localización y Nombre secuencia: lista desplegable que
                // también acepta texto libre (F14 / F6 de la matriz).
                var listAttr = '';
                if (f.code === 'location') listAttr = ' list="safra-espacios"';
                if (f.code === 'sequence_name') listAttr = ' list="safra-secuencias"';
                // Revisión 17-sep: el Ancho del Telo lo fija la combinación
                // elegida en la tabla, no se digita.
                var roChar = f.code === 'ancho_telo' ? ' readonly' : '';
                // 29-sep (16.2): los campos de comentarios se escriben en
                // área de texto, no en una línea.
                if ((f.code || '').indexOf('comentario') !== -1) {
                    return '<textarea name="' + name + '" class="form-control fld-input" rows="2"' + req + ph + '></textarea>';
                }
                return '<input type="text" name="' + name + '" class="form-control fld-input" value="' + esc(f.default || '') + '"' + req + ph + listAttr + roChar + '>';
        }
    }

    function renderToggle(name, on) {
        return '<span class="safra-toggle' + (on ? ' on' : '') + '" data-toggle-for="' + name + '" role="switch" tabindex="0">' +
            '<span class="safra-toggle-knob"></span>' +
            '<span class="safra-toggle-text">' + (on ? 'Sí' : 'No') + '</span>' +
            '<input type="checkbox" name="' + name + '" value="1" class="fld-input" hidden' + (on ? ' checked' : '') + '>' +
            '</span>';
    }

    // --- Una fila etiqueta | control | precio ---
    function renderField(f, idx) {
        var dataset =
            ' data-field="' + esc(f.code) + '"' +
            (f._flowlock ? ' data-flowlock="1"' : '') +
            (f.depends ? ' data-depends-field="' + esc(f.depends.field) + '" data-depends-value="' + esc(f.depends.value == null ? '' : f.depends.value) + '"' : '') +
            (f.flag ? ' data-flag="' + esc(f.flag) + '"' : '');
        var help = f.help ? '<span class="safra-help">' + esc(f.help) + '</span>' : '';
        var note = f.note ? '<div class="safra-note">' + esc(f.note) + '</div>' : '';
        var cls = 'safra-row safra-field' + (f.required ? ' req' : '') + (f.highlight ? ' highlight' : '');
        return '<div class="' + cls + '"' + dataset + '>' +
            '  <div class="safra-label">' + esc(f.label) + '</div>' +
            '  <div class="safra-control">' + renderControl(f, idx) + help + note + '</div>' +
            '  <div class="safra-price" data-price-for="' + esc(f.code) + '"></div>' +
            '</div>';
    }

    // Opciones del catálogo de diseños por tarjeta (para preview y galería).
    var designOptionsByIdx = {};

    // Selector visual del diseño (sin select): check "Diseño propio" (OTROS
    // directo), galería de imágenes del catálogo (como el portal del
    // cliente) y vista previa del diseño elegido con opción de quitarlo.
    // Códigos de los campos tipo diseño presentes en la tarjeta.
    function designFieldCodes(card) {
        var codes = [];
        card.querySelectorAll('.safra-field .design-gallery').forEach(function (g) {
            var row = g.closest('.safra-field');
            if (row) codes.push(row.getAttribute('data-field'));
        });
        return codes;
    }

    function updateDesignPreview(card, idx, code) {
        var row = card.querySelector('.safra-field[data-field="' + code + '"]');
        var input = card.querySelector('[name="' + code + '_' + idx + '"]');
        var prev = row && row.querySelector('.design-preview');
        if (!input || !prev) return;
        var opts = designOptionsByIdx[idx + ':' + code] || [];
        var opt = opts.filter(function (o) { return o.value === input.value; })[0];
        var img = prev.querySelector('img');
        if (opt && opt.img) {
            img.src = opt.img;
            img.onerror = function () { img.removeAttribute('src'); };
            prev.querySelector('.dp-name').textContent = opt.label;
            prev.classList.remove('d-none');
        } else {
            prev.classList.add('d-none');
        }
    }

    // Refleja el valor actual en los pickers (al duplicar una persiana).
    function syncDesignPicker(card, idx) {
        designFieldCodes(card).forEach(function (code) {
            var row = card.querySelector('.safra-field[data-field="' + code + '"]');
            var input = card.querySelector('[name="' + code + '_' + idx + '"]');
            if (!row || !input) return;
            var chk = row.querySelector('.chk-design-own');
            var btn = row.querySelector('.btn-design-gallery');
            var own = input.value === 'OTROS';
            if (chk) chk.checked = own;
            if (btn && chk) btn.classList.toggle('d-none', own);
            updateDesignPreview(card, idx, code);
        });
    }

    function bindDesignPicker(card, idx) {
        designFieldCodes(card).forEach(function (code) {
            bindOneDesignPicker(card, idx, code);
        });
    }

    function bindOneDesignPicker(card, idx, code) {
        var row = card.querySelector('.safra-field[data-field="' + code + '"]');
        if (!row) return;
        var input = card.querySelector('[name="' + code + '_' + idx + '"]');
        var chk = row.querySelector('.chk-design-own');
        var btn = row.querySelector('.btn-design-gallery');
        var gallery = row.querySelector('.design-gallery');
        var prev = row.querySelector('.design-preview');
        if (!input) return;

        var setValue = function (value) {
            input.value = value;
            updateDesignPreview(card, idx, code);
            evalConditionals(card);
            updateSummary(card);
        };

        if (chk) {
            chk.addEventListener('change', function () {
                btn.classList.toggle('d-none', chk.checked);
                gallery.classList.add('d-none');
                setValue(chk.checked ? 'OTROS' : '');
            });
        }

        prev.querySelector('.dp-clear').addEventListener('click', function (e) {
            e.preventDefault();
            setValue('');
        });

        btn.addEventListener('click', function () {
            if (!gallery.classList.contains('d-none')) { gallery.classList.add('d-none'); return; }
            if (!gallery.innerHTML) {
                // Galería perezosa: solo se construye la primera vez; las
                // imágenes cargan lazy y las rotas se ocultan solas.
                var html = '';
                (designOptionsByIdx[idx + ':' + code] || []).forEach(function (o) {
                    if (!o.value || !o.img) return;
                    html += '<div class="dg-item" data-value="' + esc(o.value) + '" title="' + esc(o.label) + '">' +
                        '<img loading="lazy" src="' + esc(o.img) + '" alt="" onerror="this.closest(\'.dg-item\').remove()"/>' +
                        '<span>' + esc(o.label) + '</span></div>';
                });
                gallery.innerHTML = html || '<div class="text-muted small">El catálogo no tiene imágenes.</div>';
                gallery.addEventListener('click', function (e) {
                    var item = e.target.closest('.dg-item');
                    if (!item) return;
                    gallery.classList.add('d-none');
                    setValue(item.getAttribute('data-value'));
                });
            }
            gallery.classList.remove('d-none');
        });
    }

    // Diseño personalizado (puntos 10-11): archivo + comentario + análisis
    // de dimensiones en vivo. Visible solo con "Diseño Impresión" activo y
    // tela estampable (mismos mecanismos depends/flag del resto de campos).
    function designUploadBlock(idx) {
        // Ajuste de pruebas (10-sep): el archivo solo aplica al «Diseño
        // propio» (OTROS) — los diseños del catálogo ya tienen su imagen.
        return '<div class="safra-row safra-field safra-design-block" data-field="design_upload"' +
            ' data-depends-field="custom_design" data-depends-value="OTROS" data-flag="printable">' +
            '  <div class="safra-label">Archivo del diseño</div>' +
            '  <div class="safra-control">' +
            '    <input type="file" name="design_file_' + idx + '" class="form-control safra-design-file" accept=".jpg,.jpeg,.png,.pdf">' +
            '    <span class="safra-help">Adjunte la imagen o PDF del diseño a imprimir (formato de aprobación)</span>' +
            '    <div class="safra-design-analysis"></div>' +
            '    <textarea name="design_comment_' + idx + '" class="form-control mt-2" rows="2" placeholder="Comentario para el área de diseño (opcional)"></textarea>' +
            '  </div>' +
            '  <div class="safra-price"></div>' +
            '</div>';
    }

    // Análisis de dimensiones en vivo: resolución de la imagen vs medidas
    // reales de la persiana (DPI efectivo) y proporción. El backend repite
    // el análisis con la imagen ya guardada (versión autoritativa).
    var DESIGN_DPI_MIN = 40, DESIGN_DPI_GOOD = 80;
    function updateDesignAnalysis(card, idx) {
        var input = card.querySelector('[name="design_file_' + idx + '"]');
        var out = card.querySelector('.safra-design-analysis');
        if (!input || !out) return;
        var file = input.files && input.files[0];
        if (!file) { out.innerHTML = ''; return; }
        if (!/^image\//.test(file.type)) {
            out.innerHTML = '<div class="alert alert-info py-1 px-2 mt-1 mb-0">PDF adjunto: la resolución la validará el área de diseño.</div>';
            return;
        }
        var w = parseFloat((card.querySelector('[name="width_' + idx + '"]') || {}).value) || 0;
        var h = parseFloat((card.querySelector('[name="height_' + idx + '"]') || {}).value) || 0;
        var url = URL.createObjectURL(file);
        var img = new Image();
        img.onload = function () {
            URL.revokeObjectURL(url);
            var msgs = ['Imagen de ' + img.naturalWidth + ' × ' + img.naturalHeight + ' px.'];
            var cls = 'alert-success';
            if (w && h) {
                var dpi = Math.min(img.naturalWidth / (w * 39.3701), img.naturalHeight / (h * 39.3701));
                msgs.push('Resolución efectiva para ' + w.toFixed(2) + ' × ' + h.toFixed(2) + ' m: ' + Math.round(dpi) + ' DPI.');
                if (dpi < DESIGN_DPI_MIN) {
                    cls = 'alert-danger';
                    msgs.push('Resolución baja para el tamaño de la persiana (mínimo recomendado ' + DESIGN_DPI_MIN + ' DPI): la impresión puede verse pixelada.');
                } else if (dpi < DESIGN_DPI_GOOD) {
                    cls = 'alert-warning';
                    msgs.push('Resolución aceptable (recomendado ' + DESIGN_DPI_GOOD + ' DPI o más).');
                } else {
                    msgs.push('Resolución óptima para impresión.');
                }
                var ratioImg = img.naturalHeight ? img.naturalWidth / img.naturalHeight : 0;
                var ratioBlind = w / h;
                if (ratioBlind && Math.abs(ratioImg - ratioBlind) / ratioBlind > 0.10) {
                    if (cls === 'alert-success') cls = 'alert-warning';
                    msgs.push('La proporción de la imagen (' + ratioImg.toFixed(2) + ') no coincide con la de la persiana (' + ratioBlind.toFixed(2) + '): el diseño se recortará o deformará.');
                }
            } else {
                msgs.push('Digite ancho y alto para calcular la resolución efectiva.');
            }
            out.innerHTML = '<div class="alert ' + cls + ' py-1 px-2 mt-1 mb-0">' + msgs.map(esc).join('<br>') + '</div>';
        };
        img.onerror = function () {
            URL.revokeObjectURL(url);
            out.innerHTML = '<div class="alert alert-warning py-1 px-2 mt-1 mb-0">No fue posible leer la imagen; el área de diseño la validará.</div>';
        };
        img.src = url;
    }

    // Punto 15 (OBS REU TELAS) + reunión 11-sep: en los sistemas con varias
    // telas (Panel, Vertical, Vintage) las telas 2..5 NO repintan controles
    // en el formulario: se agregan en un MODAL (como el «Agregar producto
    // Combinado» del portal del cliente) y queda un resumen informativo con
    // Editar/Eliminar. Los pares ocultos siguen siendo el almacenamiento que
    // viaja en el submit. Los pares requeridos (2 en 1) quedan fijos inline.
    function setupDynamicTelas(card) {
        var idx = card.getAttribute('data-idx');
        var slots = [];
        for (var n = 2; n <= 5; n++) {
            var wrapF = card.querySelector('.safra-field[data-field="fabric_id_' + n + '"]');
            var wrapC = card.querySelector('.safra-field[data-field="color_id_' + n + '"]');
            if (!wrapF || !wrapC || wrapF.classList.contains('req')) continue;
            slots.push({
                n: n, wrapF: wrapF, wrapC: wrapC,
                wrapCoord: card.querySelector('.safra-field[data-field="coordinado_tela_' + n + '"]'),
                wrapLamas: card.querySelector('.safra-field[data-field="lamas_tela_' + n + '"]'),
                wrapSesgo: card.querySelector('.safra-field[data-field="sesgo_tela_' + n + '"]'),
            });
        }
        var oldBox = card.querySelector('.safra-telas-box');
        if (oldBox) oldBox.remove();
        if (!slots.length) return;

        function inp(code) { return card.querySelector('[name="' + code + '_' + idx + '"]'); }
        function slotInp(s, base) { return inp(base + '_' + s.n); }
        function optText(sel) {
            return (sel && sel.value && sel.options[sel.selectedIndex]) ? sel.options[sel.selectedIndex].text : '';
        }

        // Los pares 2..5 son solo almacenamiento: nunca se pintan inline.
        slots.forEach(function (s) {
            [s.wrapF, s.wrapC, s.wrapCoord, s.wrapLamas, s.wrapSesgo].forEach(function (w) {
                if (w) w.classList.add('tela-hidden');
            });
        });

        // Caja de resumen + botón, en el lugar del primer par oculto.
        var box = document.createElement('div');
        box.className = 'safra-row safra-telas-box';
        box.innerHTML = '<div class="safra-label">Telas adicionales</div>' +
            '<div class="safra-control">' +
            '  <div class="telas-resumen"></div>' +
            '  <button type="button" class="btn-add-tela"><i class="fa fa-plus"></i> Agregar tela</button>' +
            '</div><div></div>';
        slots[0].wrapF.parentNode.insertBefore(box, slots[0].wrapF);
        var resumen = box.querySelector('.telas-resumen');
        var btnAdd = box.querySelector('.btn-add-tela');

        function filledSlots() {
            return slots.filter(function (s) { var f = slotInp(s, 'fabric_id'); return f && f.value; });
        }
        function renderResumen() {
            var rows = '';
            filledSlots().forEach(function (s) {
                var fSel = slotInp(s, 'fabric_id');
                var cSel = slotInp(s, 'color_id');
                var coordSel = slotInp(s, 'coordinado_tela');
                var lamasEl = slotInp(s, 'lamas_tela');
                var sesgoSel = slotInp(s, 'sesgo_tela');
                var parts = [optText(fSel), optText(cSel)];
                if (coordSel && coordSel.value) parts.push('Coordinado ' + optText(coordSel));
                if (sesgoSel && sesgoSel.value) parts.push('Sesgo ' + optText(sesgoSel));
                if (lamasEl && lamasEl.value) parts.push(lamasEl.value + ' lamas');
                rows += '<div class="tela-res-item" data-n="' + s.n + '">' +
                    '<span class="tri-text">' + esc(parts.filter(Boolean).join(' · ')) + '</span>' +
                    '<span class="tri-actions">' +
                    '<button type="button" class="btn-line tri-edit" title="Editar esta tela"><i class="fa fa-pencil"></i></button>' +
                    '<button type="button" class="btn-line tri-del" title="Eliminar esta tela"><i class="fa fa-trash"></i></button>' +
                    '</span></div>';
            });
            resumen.innerHTML = rows;
            btnAdd.style.display = filledSlots().length < slots.length ? '' : 'none';
        }

        function afterChange() {
            renderResumen();
            evalConditionals(card);
            fetchPrice(card);
            updateSummary(card);
        }

        // ---- Modal (uno global, se reconstruye por uso) ----
        function openTelaModal(editN) {
            var slot = editN
                ? slots.filter(function (s) { return s.n === editN; })[0]
                : slots.filter(function (s) { var f = slotInp(s, 'fabric_id'); return f && !f.value; })[0];
            if (!slot) return;
            var fSel = slotInp(slot, 'fabric_id');
            var coordSel = slotInp(slot, 'coordinado_tela');
            var lamasEl = slotInp(slot, 'lamas_tela');
            var sesgoSel = slotInp(slot, 'sesgo_tela');

            var old = document.getElementById('safra-tela-overlay');
            if (old) old.remove();
            // Revisión 17-sep: la misma referencia se puede repetir con otro
            // color, así que el modal ofrece todas las referencias.
            var refOpts = '<option value="">-- Seleccione --</option>';
            Array.prototype.forEach.call(fSel.options, function (o) {
                if (!o.value) return;
                refOpts += '<option value="' + esc(o.value) + '"' + (o.disabled ? ' disabled' : '') +
                    (o.value === fSel.value ? ' selected' : '') + '>' + esc(o.text) + '</option>';
            });
            var coordHtml = '';
            if (coordSel) {
                var co = '';
                Array.prototype.forEach.call(coordSel.options, function (o) {
                    co += '<option value="' + esc(o.value) + '"' + (o.value === coordSel.value ? ' selected' : '') + '>' + esc(o.text) + '</option>';
                });
                coordHtml = '<label>Coordinado<select id="tm-coord" class="form-select">' + co + '</select></label>';
            }
            // Revisión 17-sep: sesgo por tela — solo si la tela elegida en
            // el modal es sesgable (flag de la referencia).
            var sesgoHtml = '';
            if (sesgoSel) {
                var so = '';
                Array.prototype.forEach.call(sesgoSel.options, function (o) {
                    so += '<option value="' + esc(o.value) + '"' + (o.value === sesgoSel.value ? ' selected' : '') + '>' + esc(o.text) + '</option>';
                });
                sesgoHtml = '<label id="tm-sesgo-row" class="d-none">Sesgo<select id="tm-sesgo" class="form-select">' + so + '</select></label>';
            }
            var lamasHtml = lamasEl
                ? '<label>Cantidad de Lamas<input type="number" id="tm-lamas" class="form-control" min="0" step="1" value="' + esc(lamasEl.value || '') + '">' +
                  '<span class="safra-help">Aplica solo para la tela seleccionada</span></label>'
                : '';

            var ov = document.createElement('div');
            ov.id = 'safra-tela-overlay';
            ov.innerHTML = '<div class="safra-tela-modal">' +
                '<h3>' + (editN ? 'Editar tela' : 'Agregar tela') + '</h3>' +
                '<label>Referencia<select id="tm-ref" class="form-select">' + refOpts + '</select></label>' +
                '<label>Color<select id="tm-color" class="form-select" disabled><option value="">-- Seleccione referencia --</option></select></label>' +
                coordHtml + sesgoHtml + lamasHtml +
                '<div class="tm-error"></div>' +
                '<div class="tm-footer">' +
                '  <button type="button" class="btn-safra-light tm-cancel">Cancelar</button>' +
                '  <button type="button" class="btn-safra tm-ok"><i class="fa fa-check"></i> Combinar</button>' +
                '</div></div>';
            // Dentro del contenedor del cotizador para heredar los estilos
            // de botones (scoped a .safra-quoter); el overlay es fixed.
            (document.querySelector('.safra-quoter') || document.body).appendChild(ov);
            var tmRef = ov.querySelector('#tm-ref');
            var tmColor = ov.querySelector('#tm-color');

            function loadModalColors(selected) {
                if (!tmRef.value) {
                    tmColor.innerHTML = '<option value="">-- Seleccione referencia --</option>';
                    tmColor.disabled = true; return;
                }
                tmColor.innerHTML = '<option value="">Cargando...</option>';
                tmColor.disabled = true;
                rpc('/cotizador/ajax/colores', { fabric_id: tmRef.value, system_id: (card.querySelector('.sel-system') || {}).value || null }).then(function (colors) {
                    var html = '<option value="">-- Seleccione color --</option>';
                    (colors || []).forEach(function (c) {
                        var off = c.available === false;
                        html += '<option value="' + esc(c.id) + '" data-code="' + esc(c.code || '') + '"' +
                            (off ? ' disabled' : '') + '>' + esc(c.name) + (off ? ' (sin stock)' : '') + '</option>';
                    });
                    tmColor.innerHTML = html;
                    tmColor.disabled = false;
                    if (selected != null) tmColor.value = String(selected);
                    syncColorUnique(card);
                });
            }
            function syncModalSesgo() {
                var row = ov.querySelector('#tm-sesgo-row');
                if (!row) return;
                var fb = fabricsById[tmRef.value] || {};
                row.classList.toggle('d-none', !fb.sesgable);
                if (!fb.sesgable) { var ss = ov.querySelector('#tm-sesgo'); if (ss) ss.value = ''; }
            }
            tmRef.addEventListener('change', function () { loadModalColors(null); syncModalSesgo(); });
            syncModalSesgo();
            if (editN && fSel.value) {
                var cSel = slotInp(slot, 'color_id');
                loadModalColors(cSel ? cSel.value : null);
            }

            ov.querySelector('.tm-cancel').addEventListener('click', function () { ov.remove(); });
            ov.addEventListener('click', function (e) { if (e.target === ov) ov.remove(); });
            ov.querySelector('.tm-ok').addEventListener('click', function () {
                if (!tmRef.value || !tmColor.value) {
                    ov.querySelector('.tm-error').innerHTML =
                        '<div class="alert alert-danger py-1 px-2">Seleccione la referencia y el color.</div>';
                    return;
                }
                fSel.value = tmRef.value;
                var cSel = slotInp(slot, 'color_id');
                if (cSel) { cSel.innerHTML = tmColor.innerHTML; cSel.value = tmColor.value; cSel.disabled = false; }
                if (coordSel) coordSel.value = (ov.querySelector('#tm-coord') || {}).value || '';
                if (sesgoSel) sesgoSel.value = (ov.querySelector('#tm-sesgo') || {}).value || '';
                if (lamasEl) lamasEl.value = (ov.querySelector('#tm-lamas') || {}).value || '';
                ov.remove();
                afterChange();
            });
        }

        function clearSlot(s) {
            var f = slotInp(s, 'fabric_id');
            var c = slotInp(s, 'color_id');
            if (f) f.value = '';
            if (c) { c.innerHTML = '<option value="">-- Seleccione referencia --</option>'; c.disabled = true; }
            ['coordinado_tela', 'sesgo_tela', 'lamas_tela'].forEach(function (base) {
                var el = slotInp(s, base);
                if (el) el.value = '';
            });
        }

        function deleteSlot(n) {
            // Compacta: cada tela posterior baja un slot (contigüidad).
            var pos = slots.findIndex(function (s) { return s.n === n; });
            for (var i = pos; i < slots.length - 1; i++) {
                var cur = slots[i], next = slots[i + 1];
                var fN = slotInp(next, 'fabric_id');
                if (!fN || !fN.value) break;
                var fC = slotInp(cur, 'fabric_id'), cC = slotInp(cur, 'color_id'), cN = slotInp(next, 'color_id');
                fC.value = fN.value;
                if (cC && cN) { cC.innerHTML = cN.innerHTML; cC.value = cN.value; cC.disabled = cN.disabled; }
                ['coordinado_tela', 'sesgo_tela', 'lamas_tela'].forEach(function (base) {
                    var eC = slotInp(cur, base), eN = slotInp(next, base);
                    if (eC && eN) eC.value = eN.value;
                });
                pos = i + 1;
            }
            clearSlot(slots[pos]);
            afterChange();
        }

        btnAdd.addEventListener('click', function () { openTelaModal(null); });
        resumen.addEventListener('click', function (e) {
            var item = e.target.closest('.tela-res-item');
            if (!item) return;
            var n = parseInt(item.getAttribute('data-n'), 10);
            if (e.target.closest('.tri-edit')) openTelaModal(n);
            else if (e.target.closest('.tri-del')) deleteSlot(n);
        });
        renderResumen();
    }

    // P19 (fórmula Best Fit): tabla de combinaciones válidas de Panel
    // Track según ancho, traslape y telos. Elegir una fila fija la cantidad
    // de lamas, la apertura y el ancho del telo.
    function lamasTableBlock(idx) {
        return '<div class="safra-row safra-field safra-lamas-block" data-field="lamas_table">' +
            '  <div class="safra-label"></div>' +
            '  <div class="safra-control">' +
            '    <button type="button" class="btn-lamas-table"><i class="fa fa-table"></i> Ver combinaciones posibles</button>' +
            '    <span class="safra-help">Según el ancho digitado; elija una fila para aplicar la combinación</span>' +
            '    <div class="lamas-table-wrap"></div>' +
            '  </div>' +
            '  <div></div>' +
            '</div>';
    }

    // La opción se busca por etiqueta: los valores del select cambian por
    // sistema (globales 'derecha'/'extremos'…, Panel Japonés usa los códigos
    // numéricos 1..5 del portal del cliente).
    var APERTURA_MAP = { unilateral_derecha: 'derecha', unilateral_izquierda: 'izquierda', centro: 'centro', extremos: 'extremos' };

    function selectByLabel(sel, keyword) {
        if (!sel || !keyword) return;
        for (var i = 0; i < sel.options.length; i++) {
            var txt = (sel.options[i].text || '').toLowerCase();
            if (txt.indexOf(keyword) !== -1) { sel.value = sel.options[i].value; return; }
        }
        sel.value = keyword; // respaldo: valor directo (opciones globales)
    }

    // Reunión 28-sep (fila 16): las fórmulas (combinaciones y máximo de
    // lamas) pueden usar cualquier campo de la línea por su código técnico:
    // se envían todos los valores de la persiana como {código: valor}.
    function camposLinea(card) {
        var suf = '_' + card.getAttribute('data-idx');
        var out = {};
        card.querySelectorAll('[name]').forEach(function (el) {
            var n = el.name || '';
            if (n.slice(-suf.length) !== suf || el.type === 'file') return;
            out[n.slice(0, -suf.length)] = el.type === 'checkbox' ? (el.checked ? 1 : 0) : el.value;
        });
        return out;
    }

    function refreshLamasTable(card, idx) {
        var wrap = card.querySelector('.lamas-table-wrap');
        if (!wrap) return;
        var w = parseFloat((card.querySelector('[name="width_' + idx + '"]') || {}).value) || 0;
        // 13-oct: la fórmula de combinaciones puede usar el alto (en develop
        // Centro cambia con 3 m); sin él la tabla salía vacía con un aviso
        // de «sin combinaciones» que no explicaba la causa.
        var hEl = card.querySelector('[name="height_' + idx + '"]');
        var h = hEl ? (parseFloat(hEl.value) || 0) : 1;
        if (!w || !h) {
            wrap.innerHTML = '<div class="alert alert-warning py-1 px-2 mt-1 mb-0">Digite el ancho y el alto para calcular las combinaciones.</div>';
            return;
        }
        var traslape = (card.querySelector('[name="tamano_traslape_' + idx + '"]') || {}).value || '';
        // Revisión 17-sep: con lamas digitadas, la tabla muestra SOLO las
        // configuraciones viables para esa cantidad (sin lamas, todas).
        var lamasVal = (card.querySelector('[name="quantity_lamas_' + idx + '"]') || {}).value || '';
        wrap.innerHTML = '<div class="text-muted small mt-1">Calculando…</div>';
        rpc('/cotizador/ajax/panel_lamas', { width: w, traslape: traslape, lamas: lamasVal || null, campos: camposLinea(card),
                                             system_id: (card.querySelector('.sel-system') || {}).value || null }).then(function (res) {
            // Compatibilidad: respuesta nueva {rows, rango} o lista simple.
            var rows = (res && res.rows) || (Array.isArray(res) ? res : []);
            if (!rows.length) {
                var detalle = '';
                if (res && res.rango) {
                    // El rango sale del mismo cálculo de la tabla (rieles y
                    // fórmulas) y, con telos digitados, es el de esa cantidad.
                    var rg = res.rango, m = function (v) { return v.toFixed(2).replace('.', ','); };
                    var tras = Math.round((res.traslape || 0.08) * 100);
                    if (rg.sin_riel) {
                        detalle = rg.telos
                            ? ' Con ' + rg.telos + ' telos no hay ninguna combinación posible con los rieles disponibles; pruebe con otra cantidad.'
                            : ' No hay combinaciones posibles con los rieles configurados.';
                    } else {
                        detalle = (rg.telos ? ' Para ' + rg.telos + ' telos, con traslape de ' : ' Con traslape de ') + tras +
                            ' cm, el ancho debe estar entre <b>' + m(rg.wmin) + ' m</b> y <b>' + m(rg.wmax) +
                            ' m</b> (cada telo debe quedar entre ' + m(rg.telo_min) + ' y ' + m(rg.telo_max) + ' m).';
                    }
                }
                var quien = lamasVal ? ('para ' + lamasVal + ' lamas con el ancho digitado') : 'para el ancho digitado';
                wrap.innerHTML = '<div class="alert alert-danger py-1 px-2 mt-1 mb-0">Sin configuraciones válidas ' + quien + '.' + detalle + '</div>';
                return;
            }
            var html = '<div class="lamas-table-scroll"><table class="lamas-table">' +
                '<thead><tr><th>Telos</th><th>Riel (canales)</th><th>Izq + Der</th><th>Ancho telo</th><th>Apertura</th><th>Condición</th><th></th></tr></thead><tbody>';
            rows.forEach(function (r, i) {
                html += '<tr data-row="' + i + '" class="' + (r.codigo_condicion === 'riel_velcrado' ? 'velcrado' : '') + '">' +
                    '<td>' + r.total_telos + '</td>' +
                    '<td>' + r.canales + '</td>' +
                    '<td>' + (r.telos_izquierda == null ? 'Libre' : r.telos_izquierda + ' + ' + r.telos_derecha) + '</td>' +
                    '<td>' + r.ancho_telo_cm.toFixed(2) + ' cm</td>' +
                    '<td>' + esc(r.tipo_apertura) + '</td>' +
                    '<td>' + esc(r.condicion_especial) + '</td>' +
                    '<td><button type="button" class="btn-lamas-pick" data-row="' + i + '">Elegir</button></td>' +
                    '</tr>';
            });
            html += '</tbody></table></div>';
            wrap.innerHTML = html;
            wrap.querySelectorAll('.btn-lamas-pick').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    var r = rows[parseInt(btn.getAttribute('data-row'), 10)];
                    var setVal = function (code, value) {
                        var el = card.querySelector('[name="' + code + '_' + idx + '"]');
                        if (el && value != null) el.value = value;
                    };
                    setVal('quantity_lamas', r.total_telos);
                    var apSel = card.querySelector('[name="apertura_' + idx + '"]');
                    selectByLabel(apSel, APERTURA_MAP[r.codigo_apertura] || r.codigo_apertura);
                    // El botón de la apertura elegida queda resaltado y las
                    // demás se re-evalúan para la nueva cantidad de telos.
                    var apStrip = card.querySelector('.opt-thumbs[data-for="apertura_' + idx + '"]');
                    if (apSel && apStrip) apStrip.querySelectorAll('.opt-thumb').forEach(function (t) {
                        t.classList.toggle('sel', t.getAttribute('data-value') === apSel.value);
                    });
                    if (apSel) apSel.dispatchEvent(new Event('change', { bubbles: true }));
                    restrictAperturaByCombos(card, idx);
                    // Fila 16 (09-oct): la combinación elegida fija su riel.
                    card._combos = rows.filter(function (x) { return x.total_telos === r.total_telos; });
                    restrictRiel(card, idx, true);
                    setVal('ancho_telo', r.ancho_telo_cm.toFixed(2) + ' cm');
                    wrap.querySelectorAll('tr.selected').forEach(function (tr) { tr.classList.remove('selected'); });
                    var tr = wrap.querySelector('tr[data-row="' + btn.getAttribute('data-row') + '"]');
                    if (tr) tr.classList.add('selected');
                    evalConditionals(card);
                    updateSummary(card);
                });
            });
        }).catch(function () {
            wrap.innerHTML = '<div class="alert alert-warning py-1 px-2 mt-1 mb-0">No fue posible calcular las combinaciones.</div>';
        });
    }

    // Bloque fijo: Producto + Ficha técnica + Disponibilidad + Precios
    // Orden de la sección FICHA TÉCNICA (después de Estructura, Motor y
    // Cabezal): antes de ella va el Mecanismo calculado.
    var SECCION_FICHA_SEQ = 70;
    function mecanismoBlock() {
        return '<div class="safra-row safra-field safra-mech" data-field="__mecanismo">' +
            '  <div class="safra-label">Mecanismo</div>' +
            '  <div class="safra-control"><div class="safra-producto pi-mech pi-mech-pend">' + MECH_PEND + '</div>' +
            '    <span class="safra-help">Se calcula con el ancho, el motor y el cabezal elegidos (tabla de estructura).</span></div>' +
            '  <div class="safra-price"></div>' +
            '</div>';
    }
    var MECH_PEND = 'Se calcula al completar las medidas';

    function productInfoBlock() {
        return '' +
            '<div class="safra-row"><div class="safra-label">Producto</div>' +
            '  <div class="safra-control"><div class="safra-producto pi-producto">&#8203;</div></div><div></div></div>' +
            '<div class="safra-row pi-ficharow d-none"><div class="safra-label"></div>' +
            '  <div class="safra-control"><div class="safra-ficha">' +
            '    <div class="ficha-img"><img class="pi-img is-placeholder" src="' + IMG_NOTFOUND + '" alt="Producto"/></div>' +
            '    <div><span class="ficha-badge">Ficha técnica Producto</span>' +
            '      <div class="ficha-data">' +
            '        <div><strong>Ancho mínimo:</strong> <span class="pi-wmin">—</span></div>' +
            '        <div><strong>Ancho máximo:</strong> <span class="pi-wmax">—</span></div>' +
            '        <div><strong>Alto mínimo:</strong> <span class="pi-hmin">—</span></div>' +
            '        <div><strong>Alto máximo:</strong> <span class="pi-hmax">—</span></div>' +
            '      </div></div>' +
            '  </div></div><div></div></div>' +
            '<div class="safra-row pi-warnrow d-none"><div class="safra-label"></div>' +
            '  <div class="safra-control"><div class="pi-warnings"></div></div><div></div></div>';
    }

    // Disponibilidad y precios: al final de la persiana, después de todo
    // lo que los afecta (Sprint 1.3).
    function priceInfoBlock() {
        return '' +
            '<div class="safra-row pi-availrow d-none"><div class="safra-label">Disponibilidad</div>' +
            '  <div class="safra-control safra-availability pi-avail">Disponible</div><div></div></div>' +
            '<div class="safra-row pi-pricerow d-none"><div class="safra-label">Precio Base</div>' +
            '  <div class="safra-control"></div><div class="safra-price pi-base">$ 0</div></div>' +
            '<div class="safra-row pi-discrow d-none"><div class="safra-label">Precio con Descuento</div>' +
            '  <div class="safra-control"><span class="discount-badge pi-discbadge">Descuento 0 %</span></div>' +
            '  <div class="safra-price pi-final">$ 0</div></div>';
    }

    function renderConfig(config, idx) {
        var fields = config.fields || [];
        // P19: los sistemas Panel/Riel con tabla de lamas (tienen Tamaño del
        // Traslape configurado) muestran la tabla de combinaciones.
        var hasLamasTable = fields.some(function (f) { return f.code === 'tamano_traslape'; });
        // Separadores de la hoja «Matriz Unificada»: título cada vez que
        // cambia la sección; la ficha técnica / disponibilidad / precios van
        // justo después de la sección TELA (como en la matriz).
        // Sin tabla de estructura (p. ej. paneles), no hay mecanismo que calcular.
        // Sprint 1.3 (filas 63-67, reunión 17-sep): Producto y Ficha técnica
        // van en la sección FICHA TÉCNICA, después de Motor y Cabezal (de los
        // que depende el cálculo), seguidos del Mecanismo calculado.
        var fichaHtml = productInfoBlock() + (config.has_structure ? mecanismoBlock() : '');
        var html = '', prevSection = null, lockNotePlaced = false, mechPlaced = false;
        // Revisión 17-sep (bloqueo de flujo): lo que viene DESPUÉS de la
        // sección TELA se deshabilita hasta que la tela esté completa.
        var telaSeq = null;
        fields.forEach(function (f) { if (f.section_code === 'tela') telaSeq = f.section_seq; });
        fields.forEach(function (f) {
            f._flowlock = telaSeq !== null && f.section_seq > telaSeq;
            // Revisión 17-sep (#19): la cantidad de lamas la calcula la
            // fórmula del máximo — el campo queda de solo lectura.
            if (f.code === 'quantity_lamas' && config.max_lamas) f.max_lamas = true;
            if (f.section_code !== prevSection) {
                // Reunión 28-sep (fila 70): el Mecanismo es un cálculo que se
                // muestra en la Ficha técnica, después de Motor y Cabezal
                // (de los que depende). Sin campos propios de Ficha técnica
                // en el sistema, la sección se abre igual para mostrarlo.
                if (!mechPlaced && f.section_seq > SECCION_FICHA_SEQ) {
                    html += '<h3 class="safra-section-title">FICHA TÉCNICA</h3>' + fichaHtml;
                    mechPlaced = true;
                }
                if (prevSection === 'tela' && !lockNotePlaced) {
                    html += '<div class="flow-lock-note d-none"><i class="fa fa-lock"></i> Complete la tela (referencia y color disponibles) para habilitar el resto de la configuración.</div>';
                    lockNotePlaced = true;
                }
                if (f.section) html += '<h3 class="safra-section-title">' + esc(f.section) + '</h3>';
                if (f.section_code === 'ficha' && !mechPlaced) {
                    html += fichaHtml;
                    mechPlaced = true;
                }
                prevSection = f.section_code;
            }
            var htmlF = renderField(f, idx);
            // Puntos 10-11: bloque de subida (archivo con formato de
            // aprobación + comentario) justo debajo del selector de diseño.
            if (f.code === 'custom_design') htmlF += designUploadBlock(idx);
            // P19: tabla de combinaciones bajo Cantidad de Lamas.
            // Reunión 24-sep (comentario I23): el orden es Cantidad de
            // Lamas -> Tamaño del Traslape -> Ver combinaciones posibles —
            // la tabla se calcula CON el traslape, así que va después de él.
            if (f.code === 'tamano_traslape' && hasLamasTable) htmlF += lamasTableBlock(idx);
            html += htmlF;
        });
        if (!mechPlaced) html += '<h3 class="safra-section-title">FICHA TÉCNICA</h3>' + fichaHtml;
        html += priceInfoBlock();
        // Comentarios (Safra Express pasó a nivel de pedido, revisión sprint 1)
        html +=
            '<div class="safra-row"><div class="safra-label">Comentarios</div>' +
            '  <div class="safra-control"><textarea name="description_' + idx + '" class="form-control" rows="2"></textarea></div><div></div></div>';
        return html;
    }

    function buildLineHtml(idx) {
        // Tarjeta colapsable (hoja 1 / F134): encabezado con resumen y
        // acciones; el sistema arranca SIN valor por defecto (F3).
        return [
            '<div class="safra-line" data-idx="' + idx + '">',
            '  <div class="line-header" role="button" tabindex="0" title="Mostrar / ocultar esta línea">',
            '    <span class="line-caret" aria-hidden="true"></span>',
            '    <span class="line-title">Línea <span class="line-number"></span></span>',
            '    <span class="line-summary"></span>',
            '    <span class="line-actions">',
            '      <button type="button" class="btn-line btn-duplicate-line" title="Duplicar esta línea"><i class="fa fa-copy"></i> Duplicar</button>',
            '      <button type="button" class="btn-line btn-remove-line" title="Eliminar esta línea"><i class="fa fa-trash"></i></button>',
            '    </span>',
            '  </div>',
            '  <div class="line-content">',
            '    <div class="safra-row req"><div class="safra-label">Sistema</div>',
            '      <div class="safra-control"><select name="system_id_' + idx + '" class="form-select sel-system" required>' + buildSystemOptions('') + '</select></div><div></div>',
            '    </div>',
            '    <div class="line-body"><div class="safra-empty">Seleccione un sistema para configurar la línea.</div></div>',
            // Fase 5.4b (hoja 1): al terminar la persiana, Guardar la valida
            // y la colapsa; los errores salen aquí mismo.
            '    <div class="line-errors"></div>',
            '    <div class="line-footer">',
            '      <button type="button" class="btn-safra btn-save-line"><i class="fa fa-check"></i> Guardar línea</button>',
            '    </div>',
            '  </div>',
            '</div>',
        ].join('\n');
    }

    // Fase 5.4b: valida SOLO esta persiana contra el motor del servidor
    // (remapeando sus campos al índice 0, que es lo que espera el parser).
    function validateCard(card, done) {
        var idx = card.getAttribute('data-idx');
        var suffix = new RegExp('_' + idx + '$');
        var data = {};
        new FormData(document.getElementById('safra-quoter-form')).forEach(function (value, key) {
            if (value instanceof File) return;
            if (suffix.test(key)) data[key.replace(suffix, '_0')] = value;
        });
        // Validación de UNA línea: sin reglas cruzadas del pedido (el
        // alineado/secuencias/canales se validan al finalizar).
        data.single = 1;
        rpc('/cotizador/ajax/validar', data).then(function (issues) {
            done(issues || []);
        }).catch(function () { done([]); });
    }

    function saveLine(card) {
        var box = card.querySelector('.line-errors');
        // Requeridos básicos primero (mismo criterio del navegador)
        var missing = [];
        card.querySelectorAll('[required]').forEach(function (el) {
            var wrap = el.closest('.safra-field');
            var hidden = wrap && (wrap.classList.contains('d-none') || wrap.classList.contains('tela-hidden'));
            if (!hidden && !el.value) {
                var label = wrap && wrap.querySelector('.safra-label');
                missing.push(label ? label.textContent.trim() : el.name);
            }
        });
        if (missing.length) {
            box.innerHTML = '<div class="alert alert-danger">Complete los campos: ' + esc(missing.join(', ')) + '</div>';
            box.scrollIntoView({ behavior: 'smooth', block: 'center' });
            return;
        }
        validateCard(card, function (issues) {
            var errors = issues.filter(function (i) { return i.severity === 'error'; });
            var warnings = issues.filter(function (i) { return i.severity !== 'error'; });
            var html = '';
            if (errors.length) {
                html += '<div class="alert alert-danger"><ul class="mb-0">' +
                    errors.map(function (i) { return '<li>' + esc(i.message) + '</li>'; }).join('') + '</ul></div>';
            }
            if (warnings.length) {
                html += '<div class="alert alert-warning"><ul class="mb-0">' +
                    warnings.map(function (i) { return '<li>' + esc(i.message) + '</li>'; }).join('') + '</ul></div>';
            }
            box.innerHTML = html;
            if (errors.length) {
                box.scrollIntoView({ behavior: 'smooth', block: 'center' });
                return;
            }
            card.classList.add('line-saved');
            card.classList.add('collapsed');
            updateSummary(card);
            showNextPrompt(card);
        });
    }

    // «…debe agregarla al pedido y preguntar» (hoja 1): tras guardar una
    // persiana se ofrece seguir agregando o finalizar el pedido.
    function showNextPrompt(card) {
        var old = document.getElementById('line-next-prompt');
        if (old) old.remove();
        var bar = document.createElement('div');
        bar.id = 'line-next-prompt';
        bar.innerHTML = '<span>Línea guardada. ¿Qué desea hacer?</span>' +
            '<button type="button" class="btn-safra-light" id="np-add"><i class="fa fa-plus"></i> Agregar otra línea</button>' +
            '<button type="button" class="btn-safra" id="np-finish"><i class="fa fa-paper-plane"></i> Finalizar pedido</button>';
        card.parentNode.insertBefore(bar, card.nextSibling);
        bar.querySelector('#np-add').addEventListener('click', function () { bar.remove(); addLine(); });
        bar.querySelector('#np-finish').addEventListener('click', function () {
            bar.remove();
            validateAndSubmit(document.getElementById('safra-quoter-form'));
        });
        bar.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    function updateSummary(card) {
        var idx = card.getAttribute('data-idx');
        var el = card.querySelector('.line-summary');
        if (!el) return;
        var parts = [];
        var sysSel = card.querySelector('.sel-system');
        if (sysSel && sysSel.value) parts.push((sysSel.options[sysSel.selectedIndex] || {}).text || '');
        // Reunión 09-oct (fila 20): el encabezado muestra todas las telas
        // de la persiana (las dos de un 2 en 1, o las adicionales).
        var telas = [];
        ['', '_2', '_3', '_4', '_5'].forEach(function (suf) {
            var f = card.querySelector('[name="fabric_id' + suf + '_' + idx + '"]');
            var c = card.querySelector('[name="color_id' + suf + '_' + idx + '"]');
            if (!f || !f.value) return;
            var tela = (f.options[f.selectedIndex] || {}).text || '';
            if (c && c.value) tela += ' ' + ((c.options[c.selectedIndex] || {}).text || '');
            telas.push(tela);
        });
        if (telas.length) parts.push(telas.join(' + '));
        var w = card.querySelector('[name="width_' + idx + '"]');
        var h = card.querySelector('[name="height_' + idx + '"]');
        if (w && w.value && h && h.value) parts.push(w.value + ' × ' + h.value + ' m');
        var pf = card.querySelector('.pi-final');
        if (pf && parseFloat(pf.dataset.price || 0)) parts.push(money(parseFloat(pf.dataset.price)));
        // OBS REU GENERALES 11-sep: que salga la secuencia de cada persiana
        // en el encabezado (nombre + soportes asignados por el configurador).
        var seqName = fieldValue(card, 'sequence_name');
        var izq = fieldValue(card, 'soporte_izq');
        var der = fieldValue(card, 'soporte_der');
        if (seqName || izq || der) {
            var seq = 'Sec. ' + (seqName || 'sin nombre');
            if (izq || der) seq += ' [' + (izq || '·') + ' | ' + (der || '·') + ']';
            parts.push(seq);
        }
        el.textContent = parts.filter(Boolean).join(' · ');
    }

    function updateLineNumbers() {
        document.querySelectorAll('#lines-container .safra-line').forEach(function (c, n) {
            var el = c.querySelector('.line-number');
            if (el) el.textContent = n + 1;
        });
    }
    function updateTotal() {
        var subtotal = 0;
        document.querySelectorAll('.pi-final').forEach(function (el) { subtotal += parseFloat(el.dataset.price || 0); });
        var iva = subtotal * 0.19;
        var set = function (sel, val) { var e = document.querySelector(sel); if (e) e.textContent = money(val); };
        set('#total-subtotal', subtotal);
        set('#total-iva', iva);
        set('#total-grand', subtotal + iva);
        var pf = document.getElementById('total-grand');
        if (pf) pf.dataset.price = subtotal + iva;
    }

    function fieldValue(card, code) {
        var idx = card.getAttribute('data-idx');
        var el = card.querySelector('[name="' + code + '_' + idx + '"]');
        if (!el) return '';
        if (el.type === 'checkbox') return el.checked ? '1' : '';
        return el.value;
    }

    // depends_value admite lista separada por comas; prefijo '!' = distinto de; vacío = cualquier valor
    function dependsMatch(actual, depVal) {
        actual = String(actual == null ? '' : actual);
        if (depVal == null || depVal === '') return actual !== '' && actual !== '0';
        if (depVal.charAt(0) === '!') return actual !== depVal.slice(1);
        return depVal.split(',').some(function (v) {
            v = v.trim();
            if (v === 'not-selected') return actual === '';
            return v === actual;
        });
    }

    // ---- Fase 5.4a: dependencias inteligentes (obs f55/f58-f60/f93/f96/f113) ----
    function normaliza(s) {
        return String(s || '').toLowerCase()
            .normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    }

    function selectedOption(card, code) {
        var idx = card.getAttribute('data-idx');
        var sel = card.querySelector('select[name="' + code + '_' + idx + '"]');
        if (!sel || !sel.value) return null;
        return sel.options[sel.selectedIndex] || null;
    }

    // Rellena un select preservando el valor actual si sigue disponible.
    function fillSelect(sel, labels, placeholder) {
        var current = sel.value;
        var html = '<option value="">' + esc(placeholder) + '</option>';
        labels.forEach(function (l) { html += opt(l, l, l === current); });
        sel.innerHTML = html;
        if (labels.indexOf(current) === -1) sel.value = '';
    }

    function smartDependencies(card) {
        var idx = card.getAttribute('data-idx');

        // (f60/f93) Tela Cabezal Forrado: telas de TODO el pedido; Tela de
        // Cenefa: telas elegidas en esta persiana.
        card.querySelectorAll('.sel-telas-pedido').forEach(function (sel) {
            var isCabezal = sel.name.indexOf('cabezal_tela_') === 0;
            var scope = isCabezal ? document : card;
            var labels = [];
            scope.querySelectorAll('.sel-fabric').forEach(function (f) {
                if (!f.value) return;
                var label = f.options[f.selectedIndex] && f.options[f.selectedIndex].text;
                if (label && labels.indexOf(label) === -1) labels.push(label);
            });
            fillSelect(sel, labels, labels.length ? '-- Seleccione la tela --' : '-- Elija primero la tela de la persiana --');
            // Sprint 1.3 (fila 62): al habilitarse, la tela del forrado
            // arranca con la primera del pedido (se puede cambiar). Solo si
            // el campo está a la vista: oculto no debe viajar con valor.
            var wrap = sel.closest('.safra-field');
            if (isCabezal && !sel.value && labels.length && wrap && !wrap.classList.contains('d-none')) {
                sel.value = labels[0];
            }
        });

        // (f58/f96/f113) Colores de cabezal/cenefa/cordón: solo los
        // coordinados escogidos en la persiana. Sin coordinado elegido se
        // ofrecen todos (no bloquear).
        var coordinados = [];
        card.querySelectorAll('select[name^="coordinado"]').forEach(function (c) {
            if (c.name.indexOf('_' + idx) === -1 || !c.value) return;
            var label = c.options[c.selectedIndex] && c.options[c.selectedIndex].text;
            if (label) coordinados.push(normaliza(label));
        });
        ['color_cabezal', 'color_cenefa', 'color_cordon'].forEach(function (code) {
            var sel = card.querySelector('select[name="' + code + '_' + idx + '"]');
            if (!sel) return;
            Array.prototype.forEach.call(sel.options, function (o) {
                if (!o.value) { o.hidden = false; return; }
                var visible = !coordinados.length || coordinados.some(function (k) {
                    return normaliza(o.text).indexOf(k) !== -1;
                });
                o.hidden = !visible;
                o.disabled = !visible;
                if (!visible && o.selected) sel.value = '';
            });
        });

        // (f59) ¿Cabezal Forrado?: solo si hay cabezal elegido y permite
        // forrado (U_Forrado del producto; opciones sin dato = permitido).
        var wrapForrado = card.querySelector('.safra-field[data-field="cabezal_forrado"]');
        if (wrapForrado && !wrapForrado.classList.contains('d-none')) {
            var optCabezal = selectedOption(card, 'cabezal_tipo');
            var permite = optCabezal && optCabezal.getAttribute('data-forrado') !== '0';
            wrapForrado.classList.toggle('d-none', !permite);
        }

        // (f55) ¿Requiere Cargador?: si el motor viene del maestro, manda su
        // U_Requiere cargador (los motores de catálogo conservan la lógica
        // de kits existente).
        var wrapCargador = card.querySelector('.safra-field[data-field="requires_charger"]');
        if (wrapCargador && !wrapCargador.classList.contains('d-none')) {
            var optMotor = selectedOption(card, 'motor');
            if (optMotor && optMotor.hasAttribute('data-cargador')) {
                wrapCargador.classList.toggle('d-none', optMotor.getAttribute('data-cargador') !== '1');
            }
        }
    }

    // Revisión 17-sep: lo que no se repite es la COMBINACIÓN referencia +
    // color — la misma referencia con colores distintos sí se permite (p.
    // ej. un panel que combina dos colores del mismo blackout).
    function syncColorUnique(card) {
        // Reunión 24-sep: sin la regla V_TELAS_REPETIDAS activa no se
        // filtra nada — el cliente puede repetir referencia y color.
        if (!(card._safraConfig || {}).dup_pairs) return;
        var idx = card.getAttribute('data-idx');
        var slots = [];
        ['', '_2', '_3', '_4', '_5'].forEach(function (sfx) {
            var f = card.querySelector('select[name="fabric_id' + sfx + '_' + idx + '"]');
            var c = card.querySelector('select[name="color_id' + sfx + '_' + idx + '"]');
            if (f && c) slots.push({ f: f, c: c });
        });
        if (slots.length < 2) return;
        var pairs = slots.map(function (s) { return s.f.value && s.c.value ? s.f.value + '|' + s.c.value : null; });
        slots.forEach(function (s, i) {
            if (!s.f.value) return;
            var others = pairs.filter(function (p, j) { return j !== i && p; });
            Array.prototype.forEach.call(s.c.options, function (op) {
                if (!op.value) return;
                var blocked = others.indexOf(s.f.value + '|' + op.value) !== -1;
                op.hidden = blocked;
                if (blocked) op.disabled = true;
                else if (op.textContent.indexOf('(sin stock)') === -1) op.disabled = false;
            });
        });
        // El modal de tela adicional también respeta la combinación usada.
        var ov = document.getElementById('safra-tela-overlay');
        if (ov) {
            var tmRef = ov.querySelector('#tm-ref'), tmColor = ov.querySelector('#tm-color');
            if (tmRef && tmColor && tmRef.value) {
                var used = pairs.filter(Boolean);
                Array.prototype.forEach.call(tmColor.options, function (op) {
                    if (!op.value) return;
                    var blocked = used.indexOf(tmRef.value + '|' + op.value) !== -1;
                    op.hidden = blocked;
                    if (blocked) op.disabled = true;
                });
            }
        }
    }

    // Revisión 17-sep: las secciones posteriores a TELA solo se habilitan
    // cuando la tela quedó completa (referencia + color elegidos, es decir,
    // con disponibilidad — los agotados no se pueden elegir).
    function syncFlowLock(card) {
        var hasFabric = !!card.querySelector('select.sel-fabric');
        var ready = !hasFabric || (!!fieldValue(card, 'fabric_id') && !!fieldValue(card, 'color_id'));
        card.querySelectorAll('.safra-field[data-flowlock]').forEach(function (wrap) {
            wrap.classList.toggle('flow-locked', !ready);
            wrap.querySelectorAll('input, select, textarea, button').forEach(function (el) {
                if (!ready) {
                    // La marca se estampa UNA sola vez: en pasadas siguientes el
                    // campo ya está disabled por este mismo candado y volver a
                    // estampar lo dejaría marcado como "disabled por otro".
                    if (el.dataset.flowDisabled === undefined) {
                        el.dataset.flowDisabled = el.disabled ? '' : '1';
                    }
                    el.disabled = true;
                } else if (el.dataset.flowDisabled !== undefined) {
                    if (el.dataset.flowDisabled === '1') el.disabled = false;
                    delete el.dataset.flowDisabled;
                }
            });
        });
        var note = card.querySelector('.flow-lock-note');
        if (note) note.classList.toggle('d-none', ready);
    }

    // Pendientes 24-sep (7.2/8.1): en los sistemas de Panel Track la
    // apertura solo puede ser una de las combinaciones fabricables para el
    // ancho/traslape/telos digitados — las demás quedan deshabilitadas (se
    // ven, pero explican por qué no aplican). El servidor bloquea de todas
    // formas al guardar (E20014).
    var AP_COMBO = { derecha: 'unilateral_derecha', 1: 'unilateral_derecha',
                     izquierda: 'unilateral_izquierda', 2: 'unilateral_izquierda',
                     extremos: 'extremos', 3: 'extremos',
                     centro: 'centro', 4: 'centro',
                     libre: 'libre', 5: 'libre' };
    function restrictAperturaByCombos(card, idx) {
        if (!card.querySelector('[name="tamano_traslape_' + idx + '"]')) return;
        var sel = card.querySelector('[name="apertura_' + idx + '"]');
        if (!sel) return;
        var strip = card.querySelector('.opt-thumbs[data-for="apertura_' + idx + '"]');
        // Pendiente 2 (Safra, 5-oct): una apertura sin fórmula configurada
        // (hoy la Apertura Libre) no se muestra; las que sí tienen fórmula
        // se muestran y quedan en gris cuando no salen en las combinaciones.
        var conFormula = (card._safraConfig || {}).aperturas_formula;
        var sinFormula = function (code) { return !!(code && conFormula && conFormula.indexOf(code) === -1); };
        var apply = function (allowed) {
            Array.prototype.forEach.call(sel.options, function (op) {
                var code = AP_COMBO[op.value];
                if (!code) return;
                op.hidden = sinFormula(code);
                op.disabled = op.hidden || !!(allowed && allowed.indexOf(code) === -1);
            });
            if (strip) strip.querySelectorAll('.opt-thumb').forEach(function (t) {
                var code = AP_COMBO[t.getAttribute('data-value')];
                t.hidden = sinFormula(code);
                var off = !!(code && allowed && allowed.indexOf(code) === -1);
                t.classList.toggle('opt-thumb-disabled', off);
                if (off) t.title = 'No se puede fabricar con estas medidas y telos';
            });
            var cur = AP_COMBO[sel.value];
            if ((allowed && cur && allowed.indexOf(cur) === -1) || sinFormula(cur)) {
                sel.value = '';
                if (strip) strip.querySelectorAll('.opt-thumb.sel').forEach(function (t) { t.classList.remove('sel'); });
                sel.dispatchEvent(new Event('change', { bubbles: true }));
            }
        };
        var w = parseFloat((card.querySelector('[name="width_' + idx + '"]') || {}).value) || 0;
        var lamas = parseInt((card.querySelector('[name="quantity_lamas_' + idx + '"]') || {}).value, 10) || 0;
        if (!w || !lamas) { card._combos = []; apply(null); restrictRiel(card, idx); return; }
        var traslape = (card.querySelector('[name="tamano_traslape_' + idx + '"]') || {}).value || '';
        rpc('/cotizador/ajax/panel_lamas', { width: w, traslape: traslape, lamas: lamas, campos: camposLinea(card),
                                             system_id: (card.querySelector('.sel-system') || {}).value || null }).then(function (res) {
            var rows = (res && res.rows) || (Array.isArray(res) ? res : []);
            card._combos = rows;
            apply(rows.length ? rows.map(function (r) { return r.codigo_apertura; }) : null);
            restrictRiel(card, idx);
        }).catch(function () { card._combos = []; apply(null); restrictRiel(card, idx); });
    }

    // Reunión 09-oct (fila 16): el «Tipo de Riel» queda limitado al riel de
    // la combinación (telos + apertura): «N Vías» o «Riel Velcrado». «Auto»
    // y los rieles sin canales en la etiqueta (Riel Suizo) no se tocan. Solo
    // aplica a los sistemas cuyo Tipo de Riel se expresa en vías; el
    // servidor hace el mismo cruce al guardar (E20029).
    function rielInfo(label) {
        var t = (label || '').toLowerCase();
        if (t.indexOf('velcrado') !== -1) return 'velcrado';
        var m = t.match(/(\d+)\s*v[ií]as/);
        return m ? parseInt(m[1], 10) : null;
    }
    function restrictRiel(card, idx, pick) {
        var sel = card.querySelector('[name="riel_tipo_' + idx + '"]');
        if (!sel || sel.tagName !== 'SELECT' || !card.querySelector('[name="tamano_traslape_' + idx + '"]')) return;
        var opts = Array.prototype.slice.call(sel.options).filter(function (o) { return o.value; });
        if (!opts.some(function (o) { return typeof rielInfo(o.text) === 'number'; })) return;
        var ap = AP_COMBO[fieldValue(card, 'apertura')];
        var fila = ap && (card._combos || []).filter(function (r) { return r.codigo_apertura === ap; })[0];
        var riel = fila ? (fila.codigo_condicion === 'riel_velcrado' ? 'velcrado' : fila.canales) : null;
        var fuera = function (op) {
            var info = rielInfo(op.text);
            return !!(riel && info !== null && info !== riel);
        };
        opts.forEach(function (op) { op.disabled = fuera(op); });
        var strip = card.querySelector('.opt-thumbs[data-for="riel_tipo_' + idx + '"]');
        if (strip) strip.querySelectorAll('.opt-thumb').forEach(function (t) {
            var op = opts.filter(function (o) { return o.value === t.getAttribute('data-value'); })[0];
            var off = !!(op && op.disabled);
            t.classList.toggle('opt-thumb-disabled', off);
            t.title = off ? 'No corresponde al riel de la combinación' : '';
        });
        var cur = opts.filter(function (o) { return o.value === sel.value; })[0];
        var target = riel && opts.filter(function (o) { return rielInfo(o.text) === riel; })[0];
        if ((cur && cur.disabled) || (pick && target) || (!sel.value && target)) {
            var nuevo = target ? target.value : '';
            if (nuevo !== sel.value) {
                sel.value = nuevo;
                if (strip) strip.querySelectorAll('.opt-thumb').forEach(function (t) {
                    t.classList.toggle('sel', t.getAttribute('data-value') === nuevo);
                });
                sel.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }
    }

    // Pendientes 24-sep (12.1/12.2): con tela atravesable y ancho mayor al
    // rollo, se avisa el corte atravesado y aparece la aceptación; en
    // cualquier otro caso el campo permanece oculto.
    function syncCorteAtravesado(card) {
        var idx = card.getAttribute('data-idx');
        var wrap = card.querySelector('.safra-field[data-field="acepta_atravesado"]');
        if (!wrap) return;
        var f = fabricsById[fieldValue(card, 'fabric_id')] || {};
        var w = parseFloat((card.querySelector('[name="width_' + idx + '"]') || {}).value) || 0;
        var cond = (f.pierceable_type === 'si' || f.pierceable_type === 'si_cliente') &&
            f.rollo > 0 && w > f.rollo;
        wrap.dataset.forceHide = cond ? '0' : '1';
        var note = wrap.querySelector('.corte-atravesado-note');
        if (cond) {
            if (!note) {
                note = document.createElement('div');
                note.className = 'corte-atravesado-note safra-warn';
                wrap.appendChild(note);
            }
            note.innerHTML = '<span class="safra-warn-ico">⚠</span><span>' +
                'Con este ancho la tela <b>se cortará atravesada</b> ' +
                '(ancho del rollo: ' + f.rollo.toFixed(2).replace('.', ',') + ' m). ' +
                'Marque la aceptación para continuar.</span>';
        } else if (note) {
            note.remove();
        }
    }

    // 29-sep (8.3): visor de imagen — toda opción con imagen se puede
    // ampliar (clic abre, clic cierra).
    function openLightbox(src) {
        if (!src) return;
        var ov = document.createElement('div');
        ov.className = 'safra-lightbox';
        ov.innerHTML = '<img src="' + src + '" alt=""/>';
        ov.addEventListener('click', function () { ov.remove(); });
        document.body.appendChild(ov);
    }

    // 29-sep (8.3): desplegable con miniaturas por ítem. El menú se arma
    // desde las opciones del select oculto cada vez que se abre, así
    // refleja cualquier filtro (kits, densidad, combinaciones…).
    function sidSync(drop) {
        var sel = document.querySelector('[name="' + drop.getAttribute('data-for') + '"]');
        if (!sel) return;
        var op = sel.selectedIndex >= 0 ? sel.options[sel.selectedIndex] : null;
        var img = op && sel.value ? op.getAttribute('data-img') : null;
        var thumb = drop.querySelector('.sid-thumb');
        var label = drop.querySelector('.sid-label');
        thumb.innerHTML = img ? '<img src="' + esc(img) + '" alt="" title="Clic para ampliar"/>' : '';
        label.textContent = (op && sel.value) ? op.text : ((sel.options[0] || {}).text || '-- Seleccione uno --');
        drop.classList.toggle('sid-empty', !sel.value);
    }
    function sidBuildMenu(drop) {
        var sel = document.querySelector('[name="' + drop.getAttribute('data-for') + '"]');
        var menu = drop.querySelector('.sid-menu');
        if (!sel || !menu) return;
        menu.innerHTML = Array.prototype.map.call(sel.options, function (op) {
            if (op.hidden) return '';
            var img = op.getAttribute('data-img');
            return '<div class="sid-item' + (op.disabled ? ' sid-off' : '') +
                (op.value === sel.value ? ' sid-sel' : '') +
                '" data-value="' + esc(op.value) + '">' +
                '<span class="sid-thumb">' + (img ? '<img loading="lazy" src="' + esc(img) + '" alt=""/>' : '') + '</span>' +
                '<span>' + esc(op.text) + '</span></div>';
        }).join('');
    }
    document.addEventListener('click', function (e) {
        var openMenus = document.querySelectorAll('.sel-imgdrop .sid-menu:not(.d-none)');
        var drop = e.target.closest && e.target.closest('.sel-imgdrop');
        openMenus.forEach(function (m) { if (!drop || !drop.contains(m)) m.classList.add('d-none'); });
        if (!drop) return;
        var sel = document.querySelector('[name="' + drop.getAttribute('data-for') + '"]');
        if (!sel || sel.disabled) return;
        // Zoom: clic sobre la miniatura del elegido (no abre el menú).
        var thumbImg = e.target.closest('.sid-toggle .sid-thumb img');
        if (thumbImg) { openLightbox(thumbImg.src); return; }
        var item = e.target.closest('.sid-item');
        if (item) {
            if (item.classList.contains('sid-off')) return;
            sel.value = item.getAttribute('data-value');
            sel.dispatchEvent(new Event('change', { bubbles: true }));
            drop.querySelector('.sid-menu').classList.add('d-none');
            sidSync(drop);
            return;
        }
        if (e.target.closest('.sid-toggle')) {
            var menu = drop.querySelector('.sid-menu');
            if (menu.classList.contains('d-none')) { sidBuildMenu(drop); menu.classList.remove('d-none'); }
            else menu.classList.add('d-none');
        }
    });
    // El valor puede cambiar por fuera (applyValues, filtros): reflejarlo.
    document.addEventListener('change', function (e) {
        if (e.target.getAttribute && e.target.getAttribute('data-display') === 'list_thumbs') {
            var drop = document.querySelector('.sel-imgdrop[data-for="' + e.target.name + '"]');
            if (drop) sidSync(drop);
        }
    });

    // Pendientes 24-sep (11.6): con referencia texturizable el campo Color
    // se oculta (el color base va por debajo); se elige el diseño textura.
    function syncTexturable(card) {
        var f = fabricsById[fieldValue(card, 'fabric_id')] || {};
        var wrapC = card.querySelector('.safra-field[data-field="color_id"]');
        if (wrapC) {
            wrapC.dataset.forceHide = f.texturable ? '1' : '0';
            wrapC.dataset.keepValue = f.texturable ? '1' : '0';
        }
    }

    // Bloque 3 (acuerdos 17-sep y 28-sep): con «Mismo cabezal» activo el
    // Tipo de Plano y el Segmento son de la secuencia y se diligencian en
    // el configurador — la card los oculta pero conserva sus valores (el
    // modal los escribe ahí). Sin Mismo cabezal, una persiana individual
    // también puede ir en un plano: los dos campos aparecen en su línea.
    function syncPlanoFields(card) {
        var idx = card.getAttribute('data-idx');
        var sh = card.querySelector('[name="same_header_' + idx + '"]');
        if (!sh) return;
        ['tipo_plano', 'num_segmento'].forEach(function (code) {
            var wrap = card.querySelector('.safra-field[data-field="' + code + '"]');
            if (wrap) {
                wrap.dataset.forceHide = sh.checked ? '1' : '0';
                wrap.dataset.keepValue = sh.checked ? '1' : '0';
            }
        });
    }

    // Reunión 28-sep (fila 112): en una persiana individual el Segmento
    // ofrece 1..N según el plano elegido (data-seg), sin los segmentos que
    // ya usa otra secuencia o persiana del pedido con el mismo plano.
    function syncSegmentoLinea(card) {
        var idx = card.getAttribute('data-idx');
        var sh = card.querySelector('[name="same_header_' + idx + '"]');
        var tp = card.querySelector('[name="tipo_plano_' + idx + '"]');
        var ns = card.querySelector('[name="num_segmento_' + idx + '"]');
        if (!tp || !ns || ns.tagName !== 'SELECT' || (sh && sh.checked)) return;
        var op = tp.options[tp.selectedIndex];
        var total = tp.value ? parseInt((op && op.getAttribute('data-seg')) || '0', 10) : 0;
        var plano = (tp.value || '').toUpperCase();
        var tomados = {};
        document.querySelectorAll('#lines-container .safra-line').forEach(function (otra) {
            if (otra === card || !plano) return;
            var oi = otra.getAttribute('data-idx');
            var otp = otra.querySelector('[name="tipo_plano_' + oi + '"]');
            var ons = otra.querySelector('[name="num_segmento_' + oi + '"]');
            if (otp && ons && ons.value && (otp.value || '').toUpperCase() === plano) tomados[ons.value] = true;
        });
        var cur = ns.value;
        var vacio = (ns.options[0] && !ns.options[0].value) ? ns.options[0].text : '-- Seleccione uno --';
        var html = '<option value="">' + esc(vacio) + '</option>';
        for (var i = 1; i <= total; i++) {
            if (tomados[i] && String(i) !== cur) continue;
            html += '<option value="' + i + '"' + (String(i) === cur ? ' selected' : '') + '>' + i + '</option>';
        }
        ns.innerHTML = html;
    }
    function syncSegmentosPedido() {
        document.querySelectorAll('#lines-container .safra-line').forEach(syncSegmentoLinea);
    }
    // Un cambio de plano, segmento o Mismo cabezal en cualquier persiana
    // cambia lo disponible en las demás.
    document.addEventListener('change', function (e) {
        var n = (e.target && e.target.name) || '';
        if (/^(tipo_plano|num_segmento)_\d+$/.test(n)) syncSegmentosPedido();
    });
    document.addEventListener('safra:toggle', function (e) {
        if (/^same_header_\d+$/.test((e.detail && e.detail.name) || '')) syncSegmentosPedido();
    });

    function evalConditionals(card) {
        syncColorUnique(card);
        syncFlowLock(card);
        syncCorteAtravesado(card);
        syncTexturable(card);
        syncPlanoFields(card);
        syncSegmentoLinea(card);
        var fabFlags = (fabricsById[fieldValue(card, 'fabric_id')]) || {};
        var cleared = false;
        card.querySelectorAll('.safra-field').forEach(function (wrap) {
            var show = true;
            var depField = wrap.getAttribute('data-depends-field');
            if (depField) show = dependsMatch(fieldValue(card, depField), wrap.getAttribute('data-depends-value'));
            var flag = wrap.getAttribute('data-flag');
            if (show && flag) show = !!fabFlags[flag];
            // Ocultamiento forzado por lógica propia (corte atravesado).
            if (wrap.dataset.forceHide === '1') show = false;
            // Revisión 17-sep: al ocultarse un campo, su valor se limpia
            // para que no viajen datos huérfanos de una configuración previa
            // (p. ej. cambiar de tela estampable a una que no lo es).
            // Pendientes 24-sep (11.6): keepValue preserva el valor de los
            // campos ocultos por lógica propia (el color base texturizable).
            if (!show && wrap.dataset.vis === '1' && wrap.dataset.keepValue !== '1') {
                wrap.querySelectorAll('input, select, textarea').forEach(function (el) {
                    if (el.type === 'checkbox') {
                        if (el.checked) {
                            el.checked = false; cleared = true;
                            var tg = el.closest('.safra-toggle');
                            if (tg) {
                                tg.classList.remove('on');
                                var txt = tg.querySelector('.safra-toggle-text');
                                if (txt) txt.textContent = 'No';
                            }
                        }
                    } else if (el.value) {
                        el.value = ''; cleared = true;
                    }
                });
            }
            wrap.dataset.vis = show ? '1' : '0';
            wrap.classList.toggle('d-none', !show);
        });
        // Las limpiezas pueden destapar otras dependencias en cadena.
        if (cleared && !card._safraReeval) {
            card._safraReeval = true;
            try { evalConditionals(card); } finally { card._safraReeval = false; }
            return;
        }
        // Fase 5.4a: dependencias inteligentes entre campos.
        smartDependencies(card);
        // Fase 5.1 (Sheer Deluxe): los insumos con densidad máxima se
        // ocultan cuando la densidad de la tela elegida la supera.
        var densidad = (fabricsById[fieldValue(card, 'fabric_id')] || {}).densidad || 0;
        card.querySelectorAll('option[data-dmax]').forEach(function (op) {
            var dmax = parseFloat(op.getAttribute('data-dmax')) || 0;
            var blocked = densidad > 0 && dmax > 0 && densidad > dmax;
            op.hidden = blocked;
            op.disabled = blocked;
            if (blocked && op.selected) op.parentNode.value = '';
        });
        // Un título de sección se oculta si todos sus campos quedaron ocultos
        // (ej: DISEÑO DE IMPRESIÓN con una tela no estampable).
        card.querySelectorAll('.safra-section-title').forEach(function (title) {
            var el = title.nextElementSibling, any = false;
            while (el && !el.classList.contains('safra-section-title')) {
                if (el.classList.contains('safra-field') &&
                    !el.classList.contains('d-none') && !el.classList.contains('tela-hidden')) {
                    any = true; break;
                }
                el = el.nextElementSibling;
            }
            title.classList.toggle('d-none', !any);
        });
    }

    function loadColorsFor(card, selFabric) {
        var idx = card.getAttribute('data-idx');
        var target = selFabric.getAttribute('data-color-target');
        var selColor = card.querySelector('[name="' + target + '_' + idx + '"]');
        if (!selColor) return Promise.resolve();
        var fid = selFabric.value;
        if (!fid) {
            selColor.innerHTML = '<option value="">-- Seleccione referencia --</option>';
            selColor.disabled = true; return Promise.resolve();
        }
        selColor.innerHTML = '<option value="">Cargando...</option>';
        selColor.disabled = true;
        var sysId = (card.querySelector('.sel-system') || {}).value || null;
        return rpc('/cotizador/ajax/colores', { fabric_id: fid, system_id: sysId }).then(function (colors) {
            var html = '<option value="">-- Seleccione color --</option>';
            (colors || []).forEach(function (c) {
                var off = c.available === false;
                html += '<option value="' + esc(c.id) + '" data-code="' + esc(c.code || '') + '"' +
                    (off ? ' disabled' : '') + '>' + esc(c.name) + (off ? ' (sin stock)' : '') + '</option>';
            });
            selColor.innerHTML = html; selColor.disabled = false;
            // Pendientes 24-sep (11.6): en una referencia texturizable
            // (Blackout Texturizado) el cliente NO elige color — se toma
            // automáticamente el color base (primera línea disponible, el
            // artículo blanco que respalda el stock) y el campo se oculta;
            // lo que elige es el diseño de textura.
            var fData = fabricsById[String(fid)] || {};
            if (fData.texturable && target === 'color_id' && !selColor.value) {
                var first = Array.prototype.find
                    ? Array.prototype.find.call(selColor.options, function (o) { return o.value && !o.disabled; })
                    : null;
                if (!first) {
                    for (var i = 0; i < selColor.options.length; i++) {
                        if (selColor.options[i].value && !selColor.options[i].disabled) { first = selColor.options[i]; break; }
                    }
                }
                if (first) {
                    selColor.value = first.value;
                    selColor.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }
        }).catch(function () { selColor.innerHTML = '<option value="">Error</option>'; });
    }

    // Producto: nombre calculado (sistema + referencias + colores) y los
    // límites de la ficha técnica configurados (producto terminado).
    function updateProductName(card) {
        var idx = card.getAttribute('data-idx');
        var f = card.querySelector('[name="fabric_id_' + idx + '"]');
        var c = card.querySelector('[name="color_id_' + idx + '"]');
        var pi = card.querySelector('.pi-producto');
        if (!f || !c || !pi) return;
        var sysSel = card.querySelector('.sel-system');
        var sysTxt = sysSel ? (sysSel.options[sysSel.selectedIndex] || {}).text : '';
        var refTxt = (f.options[f.selectedIndex] || {}).text || '';
        var colTxt = (c.options[c.selectedIndex] || {}).text || '';
        // Revisión 17-sep: el producto refleja la combinación completa de
        // telas («… Blackout Melisa Blanco + Ébano Beige»).
        var combos = '';
        for (var n = 2; n <= 5; n++) {
            var fN = card.querySelector('[name="fabric_id_' + n + '_' + idx + '"]');
            var cN = card.querySelector('[name="color_id_' + n + '_' + idx + '"]');
            if (fN && fN.value) {
                var refN = (fN.options[fN.selectedIndex] || {}).text || '';
                var colN = (cN && cN.value) ? ((cN.options[cN.selectedIndex] || {}).text || '') : '';
                combos += ' + ' + (refN + ' ' + colN).trim();
            }
        }
        pi.textContent = ('Persiana ' + (sysTxt || '') + ' ' + refTxt + ' ' + colTxt + combos).replace(/\s+/g, ' ').trim();
        var ficha = fichaLimits(card);
        var q = function (sel) { return card.querySelector(sel); };
        if (q('.pi-wmin')) {
            q('.pi-wmin').textContent = (ficha.wmin || 0) + ' mts';
            q('.pi-wmax').textContent = (ficha.wmax || 0) + ' mts';
            q('.pi-hmin').textContent = (ficha.hmin || 0) + ' mts';
            q('.pi-hmax').textContent = (ficha.hmax || 0) + ' mts';
        }
        var row = q('.pi-ficharow');
        if (row) row.classList.remove('d-none');
    }

    // Límites configurados de la ficha (con Exhibición, los de exhibición).
    function fichaLimits(card) {
        var idx = card.getAttribute('data-idx');
        var cfg = card._safraConfig || {};
        var ficha = cfg.ficha || {};
        // Reunión 28-sep (fila 3): marcada como Exhibición, la ficha
        // muestra los mínimos y máximos de exhibición del sistema.
        var exh = card.querySelector('[name="exhibition_' + idx + '"]');
        if (exh && exh.checked && cfg.ficha_exh) ficha = Object.assign({}, ficha, cfg.ficha_exh);
        return ficha;
    }

    function fetchPrice(card) {
        var idx = card.getAttribute('data-idx');
        var f = card.querySelector('[name="fabric_id_' + idx + '"]');
        var c = card.querySelector('[name="color_id_' + idx + '"]');
        var w = card.querySelector('[name="width_' + idx + '"]');
        var h = card.querySelector('[name="height_' + idx + '"]');
        // Sprint 1.3 (fila 63): el nombre del producto y la ficha se muestran
        // con la tela elegida, aunque el sistema no pida ancho y alto
        // (Cuadro Lienzo usa «Dimensiones»).
        if (!f || !c || !f.value || !c.value) return;
        updateProductName(card);
        if (!w || !h || !w.value || !h.value) return;
        var sysSel = card.querySelector('.sel-system');
        var cfg = card._safraConfig || {};
        // Estructura por ancho: sistema + accionamiento + tipo de cabezal.
        var motorCb = card.querySelector('[name="has_motor_' + idx + '"]');
        var cabSel = card.querySelector('[name="cabezal_tipo_' + idx + '"]');
        var cabTxt = cabSel && cabSel.value ? ((cabSel.options[cabSel.selectedIndex] || {}).text || '') : '';
        // Perfil seleccionado (peso del perfil para la fórmula de peso máximo).
        var perfilVal = '';
        ['perfil_', 'perfil_sheer_', 'perfileria2_'].some(function (p) {
            var el = card.querySelector('[name="' + p + idx + '"]');
            if (el && el.value) { perfilVal = el.value; return true; }
            return false;
        });
        var motorSel = card.querySelector('[name="motor_' + idx + '"]');
        var unifSel = card.querySelector('select[name="unificacion_mando_' + idx + '"]');
        var unifSent = unifSel ? unifSel.value : '';
        rpc('/cotizador/ajax/precio', {
            fabric_id: f.value, color_id: c.value,
            width: parseFloat(w.value), height: parseFloat(h.value),
            system_id: sysSel ? sysSel.value : null,
            has_motor: !!(motorCb && motorCb.checked),
            cabezal: cabTxt,
            perfil: perfilVal,
            motor: motorSel ? motorSel.value : '',
            unificacion: unifSent,
        })
            .then(function (res) {
                res = res || {};
                var base = res.base != null ? res.base : (res.price || 0);
                var disc = res.discount_pct || 0;
                var final = res.price != null ? res.price : base;
                var q = function (sel) { return card.querySelector(sel); };
                card.querySelectorAll('.pi-ficharow, .pi-availrow, .pi-pricerow, .pi-discrow').forEach(function (e) { e.classList.remove('d-none'); });
                // Imagen del producto almacenada en Odoo (círculo); si no hay, placeholder.
                var imgEl = q('.pi-img');
                if (imgEl) {
                    imgEl.onerror = function () {
                        imgEl.onerror = null;
                        imgEl.classList.add('is-placeholder');
                        imgEl.src = IMG_NOTFOUND;
                    };
                    if (res.image_url) {
                        imgEl.classList.remove('is-placeholder');
                        imgEl.src = res.image_url;
                    } else {
                        imgEl.classList.add('is-placeholder');
                        imgEl.src = IMG_NOTFOUND;
                    }
                }
                var ficha = fichaLimits(card);
                if (!cfg.ficha && res.ficha) ficha = res.ficha;
                var limits = res.limits || {};
                q('.pi-wmin').textContent = (ficha.wmin || 0) + ' mts';
                q('.pi-wmax').textContent = (ficha.wmax || 0) + ' mts';
                q('.pi-hmin').textContent = (ficha.hmin || 0) + ' mts';
                // Sprint 1.3 (fila 66): el alto máximo es el MENOR entre el
                // del producto terminado y el calculado por las fórmulas
                // (espacio al techo / carga del mecanismo).
                var hmaxes = [ficha.hmax, limits.alto_maximo].filter(function (v) { return v != null && v > 0; });
                q('.pi-hmax').textContent = (hmaxes.length ? Math.min.apply(null, hmaxes) : 0) + ' mts';
                // Avisos de las fórmulas de alto/peso máximo.
                var warns = [];
                if (limits.alto_ok === false) {
                    warns.push('El alto digitado supera el alto máximo calculado de ' + limits.alto_maximo + ' mts para esta configuración.');
                }
                if (limits.requiere_motor === true) {
                    warns.push('Por el peso calculado (' + limits.peso_total + ' g), la persiana debe ir motorizada: marque "Con Motor".');
                } else if (limits.peso_ok === false) {
                    warns.push('El peso calculado (' + limits.peso_total + ' g) supera la carga máxima del mecanismo (' + limits.carga_maxima + ' g).');
                }
                var warnRow = q('.pi-warnrow');
                // Nota informativa del kit motorizado (Somfy: se compra completo).
                if (res.kit && res.kit.nota) {
                    warns.push('__NOTE__' + res.kit.nota);
                }
                if (warns.length) {
                    q('.pi-warnings').innerHTML = warns.map(function (t) {
                        var isNote = t.indexOf('__NOTE__') === 0;
                        return '<div class="' + (isNote ? 'pi-kitnote' : 'pi-warning') + '">' + esc(isNote ? t.slice(8) : t) + '</div>';
                    }).join('');
                    warnRow.classList.remove('d-none');
                } else {
                    q('.pi-warnings').innerHTML = '';
                    warnRow.classList.add('d-none');
                }
                applyKit(card, idx, res.kit);
                // Sprint 1.3 (fila 73): tubos mayores para la unificación;
                // si la elegida dejó de aplicar, se recalcula sin ella.
                if (syncUnificacion(card, idx, res.tubo) !== unifSent) fetchPrice(card);
                updateSummary(card);
                // Reunión 28-sep (fila 70): el Mecanismo es solo el cálculo de
                // la tabla de estructura (ancho, motor, cabezal); ya no hay
                // texto fijo configurado en el sistema.
                var mechEl = q('.pi-mech');
                if (mechEl) {
                    mechEl.textContent = res.mechanism || 'Sin estructura para estas medidas';
                    mechEl.classList.toggle('pi-mech-pend', !res.mechanism);
                }
                q('.pi-base').innerHTML = disc ? '<span class="price-strike">' + money(base) + '</span>' : money(base);
                q('.pi-discbadge').textContent = 'Descuento ' + disc + ' %';
                var pf = q('.pi-final'); pf.textContent = money(final); pf.dataset.price = final;
                updateTotal();
            });
    }

    // Sprint 1.3 (fila 73, reunión 17-sep): la Unificación Mando solo ofrece
    // tubos MAYORES al calculado por el ancho (orden de la tabla de
    // estructura del sistema); al elegir uno se recalculan Tubo, Soporte,
    // Mecanismo y límites. Devuelve el valor que quedó.
    function syncUnificacion(card, idx, tubo) {
        card._tubo = tubo || null;
        var sel = card.querySelector('select[name="unificacion_mando_' + idx + '"]');
        if (!sel) return '';
        var mayores = (tubo && tubo.mayores) || [];
        var cur = sel.value;
        var vacio = !tubo ? 'Se calcula con las medidas'
            : (mayores.length ? 'Sin unificar (tubo ' + tubo.base + ')' : 'No hay tubos mayores a ' + tubo.base);
        var html = '<option value="">' + esc(vacio) + '</option>';
        mayores.forEach(function (t) { html += '<option value="' + esc(t) + '">' + esc(t) + '</option>'; });
        sel.innerHTML = html;
        sel.value = mayores.indexOf(cur) !== -1 ? cur : '';
        syncUnificacionSecuencias();
        return sel.value;
    }

    // En persianas con Mismo cabezal la unificación es obligatoria y
    // automática: toda la secuencia va con el tubo mayor de sus persianas
    // (el servidor aplica la misma regla al validar y guardar).
    function syncUnificacionSecuencias() {
        var grupos = {};
        document.querySelectorAll('#lines-container .safra-line').forEach(function (card) {
            var idx = card.getAttribute('data-idx');
            var sel = card.querySelector('select[name="unificacion_mando_' + idx + '"]');
            if (!sel) return;
            var sh = card.querySelector('[name="same_header_' + idx + '"]');
            var nombre = ((card.querySelector('[name="sequence_name_' + idx + '"]') || {}).value || '').trim().toLowerCase();
            var enSec = !!(sh && sh.checked && nombre);
            sel.classList.toggle('unif-auto', enSec);
            sel.tabIndex = enSec ? -1 : 0;
            sel.title = enSec ? 'En secuencia, todas las persianas se unifican al tubo mayor automáticamente.' : '';
            if (!enSec || !card._tubo) return;
            (grupos[nombre] = grupos[nombre] || []).push({ card: card, sel: sel });
        });
        Object.keys(grupos).forEach(function (k) {
            var g = grupos[k], orden = [], mayor = null;
            g.forEach(function (x) { if ((x.card._tubo.orden || []).length > orden.length) orden = x.card._tubo.orden; });
            g.forEach(function (x) { if (orden.indexOf(x.card._tubo.base) > orden.indexOf(mayor)) mayor = x.card._tubo.base; });
            g.forEach(function (x) {
                var want = (mayor && x.card._tubo.base !== mayor) ? mayor : '';
                if (x.sel.value === want) return;
                if (want && !Array.prototype.some.call(x.sel.options, function (o) { return o.value === want; })) {
                    x.sel.add(new Option(want, want));
                }
                x.sel.value = want;
                fetchPrice(x.card);
            });
        });
    }

    function applyKit(card, idx, kit) {
        // Pendientes 24-sep (15.1): la asociación del MAESTRO del motor
        // (U_Controles compatibles) manda; el kit queda como respaldo
        // mientras se termina la parametrización.
        card._lastKit = kit || card._lastKit || null;
        kit = card._lastKit;
        var mm = card._motorMaestro;
        var ctrl = card.querySelector('[name="control_' + idx + '"]');
        if (ctrl) {
            if (!ctrl._allOptions) {
                ctrl._allOptions = Array.prototype.map.call(ctrl.options, function (o) {
                    return { value: o.value, text: o.text };
                });
            }
            var current = ctrl.value;
            // Pendientes 24-sep (16.2): siempre se ofrece «Sin control»
            // para tomar un canal libre del control de otra persiana.
            var sinControl = '<option value="0">Sin control (canal de otra persiana)</option>';
            if (mm && ((mm.controls && mm.controls.length) || mm.desde_referencias)) {
                // Reunión 13-oct (fila 56): con la referencia de controles,
                // una línea sin producto es «Sin control» con su etiqueta.
                var propios = (mm.controls || []).filter(function (c) { return c.value !== '0'; });
                var sinRef = (mm.controls || []).filter(function (c) { return c.value === '0'; })[0];
                ctrl.innerHTML = '<option value="">-- Seleccione uno --</option>' +
                    (sinRef ? '<option value="0">' + esc(sinRef.label) + '</option>' : sinControl) +
                    propios.map(function (c) {
                        return '<option value="' + esc(c.value) + '" data-canales="' + (c.canales || 0) + '">' +
                            esc(c.label) + '</option>';
                    }).join('');
            } else {
                var allowed = (kit && kit.controls && kit.controls.length) ? kit.controls : null;
                ctrl.innerHTML = ctrl._allOptions.filter(function (o) {
                    return !allowed || !o.value || o.value === '0' || allowed.indexOf(o.value) !== -1;
                }).map(function (o) {
                    return '<option value="' + esc(o.value) + '">' + esc(o.text) + '</option>';
                }).join('');
                if (!Array.prototype.some.call(ctrl.options, function (o) { return o.value === '0'; })) {
                    ctrl.insertAdjacentHTML('beforeend', sinControl);
                }
            }
            if (!current && card._pendingControl) current = card._pendingControl;
            ctrl.value = Array.prototype.some.call(ctrl.options, function (o) { return o.value === current; }) ? current : '';
            if (ctrl.value && ctrl.value === card._pendingControl) card._pendingControl = null;
        }
        // Interruptor solo cuando el motor lo trae; pregunta de cargador
        // solo para motores de batería (maestro primero, kit de respaldo).
        var toggleKit = function (code, show) {
            var wrap = card.querySelector('.safra-field[data-field="' + code + '"]');
            if (!wrap) return;
            wrap.classList.toggle('kit-hidden', !show);
            // 13-oct: lo que el motor oculta no viaja con valor (p. ej. un
            // «sin» por defecto en el Módulo RF de un motor que no lo usa).
            if (!show) {
                wrap.querySelectorAll('select, input').forEach(function (el) {
                    if (el.type === 'checkbox') el.checked = false;
                    else if (el.value) el.value = '';
                });
            }
        };
        // Revisión 17-sep: sin motor elegido ni interruptor ni cargador.
        var motorVal = fieldValue(card, 'motor');
        if (mm) {
            toggleKit('interruptor_rf', !!motorVal && !!mm.interruptor);
            toggleKit('requires_charger', !!motorVal && !!mm.cargador);
        } else {
            toggleKit('interruptor_rf', !!motorVal && (!kit || !!kit.interruptor));
            toggleKit('requires_charger', !!motorVal && (!kit || !!kit.aplica_cargador));
        }
        // Reunión 13-oct (filas 56-57): Control y Canal van con el motor y
        // solo se ocultan si el Módulo de Control RF responde «Sin
        // interruptor» (cuando el motor hace esa pregunta).
        var conMotor = !!motorVal && motorVal !== '0' && motorVal !== 'sin';
        var verControl = conMotor && !rfSinInterruptor(card, idx);
        ['control', 'control_channel'].forEach(function (code) { toggleKit(code, verControl); });
        syncAllChannels();
    }

    // ¿El Módulo de Control RF está a la vista y respondido «Sin
    // interruptor»? (valor 'sin' del catálogo o línea de referencia sin
    // producto).
    function rfSinInterruptor(card, idx) {
        var wrap = card.querySelector('.safra-field[data-field="interruptor_rf"]');
        if (!wrap || wrap.classList.contains('kit-hidden') || wrap.classList.contains('d-none')) return false;
        var op = selectedOption(card, 'interruptor_rf');
        return !!(op && op.value && (op.value === 'sin' || op.getAttribute('data-sin') === '1'));
    }

    // Pendientes 24-sep (16.2): control/canal son estado compartido del
    // pedido — al cambiar uno, o al borrar o cambiar de sistema una
    // persiana, se refrescan los canales de TODAS.
    function syncAllChannels() {
        document.querySelectorAll('#lines-container .safra-line').forEach(function (c2) {
            syncControlChannel(c2, c2.getAttribute('data-idx'));
        });
    }

    // Pendientes 24-sep (16.1): el Canal del Control lista 1..N según la
    // U_Cantidad de canales del control elegido; sin dato, se conserva la
    // lista estática del catálogo.
    function syncControlChannel(card, idx) {
        var chan = card.querySelector('[name="control_channel_' + idx + '"]');
        if (!chan) return;
        chan.disabled = false;
        var ctrl = card.querySelector('[name="control_' + idx + '"]');
        // Pendientes 24-sep (16.2): «Sin control» toma un canal LIBRE del
        // control de otra persiana del mismo sistema; los tomados se
        // muestran deshabilitados indicando quién los usa.
        // Canales del pedido (mismo sistema): el máximo de los controles
        // multicanal y quién tomó cada canal. 13-oct: la persiana se nombra
        // por su posición en pantalla (el índice interno se descuadra al
        // borrar líneas).
        var mySys = (card.querySelector('.sel-system') || {}).value;
        var maxN = 0, taken = {}, takenSin = {};
        document.querySelectorAll('#lines-container .safra-line').forEach(function (c2, pos) {
            if (((c2.querySelector('.sel-system') || {}).value) !== mySys) return;
            var i2 = c2.getAttribute('data-idx');
            var ct2 = c2.querySelector('[name="control_' + i2 + '"]');
            var ch2 = c2.querySelector('[name="control_channel_' + i2 + '"]');
            if (ct2 && ct2.value && ct2.value !== '0' && ct2.selectedIndex >= 0) {
                // Solo un control MULTICANAL presta canales (13-oct).
                var op2 = ct2.options[ct2.selectedIndex];
                var n2 = parseInt(op2 && op2.getAttribute('data-canales'), 10) || 0;
                if (n2 > 1) maxN = Math.max(maxN, n2);
            }
            if (c2 !== card && ch2 && ch2.value && ch2.value !== '0') {
                taken[ch2.value] = pos + 1;
                if (ct2 && ct2.value === '0') takenSin[ch2.value] = pos + 1;
            }
        });
        if (ctrl && ctrl.value === '0') {
            var cur0 = chan.value;
            if (!maxN) {
                chan.innerHTML = '<option value="">Asigne primero un control multicanal a otra persiana del pedido</option>';
                return;
            }
            var h = '<option value="">-- Seleccione canal libre --</option>';
            for (var k = 1; k <= maxN; k++) {
                h += taken[k]
                    ? '<option value="' + k + '" disabled>Canal ' + k + ' — tomado por Persiana ' + taken[k] + '</option>'
                    : '<option value="' + k + '">Canal ' + k + '</option>';
            }
            chan.innerHTML = h;
            chan.value = (cur0 && !taken[cur0] && parseInt(cur0, 10) <= maxN) ? cur0 : '';
            return;
        }
        // Reunión 13-oct (fila 57): los canales salen del control elegido
        // (columna Canales de su línea en Referencias). Monocanal: no se
        // pide canal; multicanal: canal obligatorio 1..N. Ya no existe
        // «Sin canal».
        var canales = 0;
        if (ctrl && ctrl.value && ctrl.selectedIndex >= 0) {
            var op = ctrl.options[ctrl.selectedIndex];
            canales = parseInt(op && op.getAttribute('data-canales'), 10) || 0;
        }
        var current = chan.value;
        if (!ctrl || !ctrl.value) {
            chan.innerHTML = '<option value="">Elija primero el control</option>';
            chan.disabled = true;
            return;
        }
        if (canales <= 1) {
            chan.innerHTML = '<option value="">Monocanal: no requiere canal</option>';
            chan.disabled = true;
            return;
        }
        var html = '<option value="">-- Seleccione el canal --</option>';
        for (var i = 1; i <= canales; i++) {
            html += (takenSin[i] && String(i) !== current)
                ? '<option value="' + i + '" disabled>Canal ' + i + ' — tomado por Persiana ' + takenSin[i] + '</option>'
                : '<option value="' + i + '">Canal ' + i + '</option>';
        }
        chan.innerHTML = html;
        chan.value = Array.prototype.some.call(chan.options, function (o) { return o.value === current && !o.disabled; }) ? current : '';
    }

    // Pendientes 24-sep (14.1/15.1/17.1): al elegir motor se consultan sus
    // asociaciones del maestro (controles, módulo RF, cargador).
    function applyMotorMaestro(card, idx) {
        var motorVal = fieldValue(card, 'motor');
        card._motorMaestro = null;
        if (!motorVal || motorVal === '0' || motorVal === 'sin') {
            applyKit(card, idx, null);
            return;
        }
        rpc('/cotizador/ajax/motor_extras', { motor: motorVal,
                system_id: (card.querySelector('.sel-system') || {}).value || null }).then(function (res) {
            if (res && (res.interruptor !== undefined || (res.controls && res.controls.length))) {
                card._motorMaestro = res;
            }
            applyKit(card, idx, null);
        }).catch(function () { applyKit(card, idx, null); });
    }

    // Revisión sprint 1 (f15/f76): al marcar «Mismo cabezal o soporte
    // intermedio», Alineado se marca por defecto y la Posición del mando
    // queda inhabilitada (la define la secuencia).
    // Reunión 09-oct (fila 13): con Mismo cabezal todo va alineado (misma
    // tela, mismos cálculos de tubo) — Alineado queda marcado y bloqueado.
    function syncSameHeader(card, idx) {
        var sh = card.querySelector('[name="same_header_' + idx + '"]');
        if (!sh) return;
        var on = sh.checked;
        var al = card.querySelector('[name="aligned_' + idx + '"]');
        var altg = al && al.closest('.safra-toggle');
        if (on && al && !al.checked) {
            al.checked = true;
            if (altg) {
                altg.classList.add('on');
                var txt = altg.querySelector('.safra-toggle-text');
                if (txt) txt.textContent = 'Sí';
            }
        }
        if (altg) {
            altg.classList.toggle('locked', on);
            altg.setAttribute('aria-disabled', on ? 'true' : 'false');
            altg.title = on ? 'Con «Mismo cabezal» la persiana siempre va alineada.' : '';
        }
        var mp = card.querySelector('[name="mando_position_' + idx + '"]');
        if (mp) {
            mp.disabled = on;
            if (on) mp.value = '';
        }
        // Pendientes 24-sep (4.2): con Mismo cabezal el nombre de la
        // secuencia es obligatorio.
        var sq = card.querySelector('[name="sequence_name_' + idx + '"]');
        if (sq) {
            if (on) sq.setAttribute('required', 'required');
            else sq.removeAttribute('required');
            var wrap = sq.closest('.safra-field');
            if (wrap) wrap.classList.toggle('req', on);
        }
    }

    // M² de impresión = ancho × alto (solo informativo; el backend recalcula).
    function updatePrintM2(card, idx) {
        var pm = card.querySelector('[name="print_m2_' + idx + '"]');
        if (!pm) return;
        var w = parseFloat((card.querySelector('[name="width_' + idx + '"]') || {}).value) || 0;
        var h = parseFloat((card.querySelector('[name="height_' + idx + '"]') || {}).value) || 0;
        pm.value = (w * h) ? (w * h).toFixed(2) : '';
    }

    // Revisión 17-sep (#19): máximo total de lamas/pantógrafos — con la
    // fórmula configurada, el total se calcula solo (ancho + apertura +
    // accionamiento) y la cantidad queda fija en ese valor.
    function updateMaxLamas(card) {
        var cfg = card._safraConfig || {};
        if (!cfg.max_lamas) return;
        var idx = card.getAttribute('data-idx');
        var el = card.querySelector('[name="quantity_lamas_' + idx + '"]');
        if (!el) return;
        var w = parseFloat(fieldValue(card, 'width')) || 0;
        var ap = fieldValue(card, 'apertura');
        var sys = (card.querySelector('.sel-system') || {}).value;
        if (!w || !ap) { return; }
        var motorVal = fieldValue(card, 'motor');
        var esMotor = fieldValue(card, 'has_motor') === '1' ||
            (!!motorVal && motorVal !== '0' && motorVal !== 'sin');
        rpc('/cotizador/ajax/max_lamas', {
            system_id: sys, width: w, apertura: ap,
            motorized: esMotor, campos: camposLinea(card),
        }).then(function (res) {
            if (res && res.max != null && String(res.max) !== el.value) {
                el.value = res.max;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                evalConditionals(card);
                updateSummary(card);
            }
        });
    }

    function bindBody(card) {
        var idx = card.getAttribute('data-idx');
        // Miniaturas de opciones con imagen: clic elige en el select.
        card.querySelectorAll('.opt-thumbs').forEach(function (strip) {
            strip.addEventListener('click', function (e) {
                var item = e.target.closest('.opt-thumb');
                if (!item || item.classList.contains('opt-thumb-disabled')) return;
                // 29-sep (8.3): la imagen del botón YA elegido se amplía
                // con un segundo clic (toda opción con imagen es ampliable).
                if (item.classList.contains('sel') && e.target.tagName === 'IMG') {
                    openLightbox(e.target.src);
                    return;
                }
                var sel = card.querySelector('[name="' + strip.getAttribute('data-for') + '"]');
                if (!sel) return;
                sel.value = item.getAttribute('data-value');
                strip.querySelectorAll('.opt-thumb').forEach(function (t) { t.classList.toggle('sel', t === item); });
                sel.dispatchEvent(new Event('change', { bubbles: true }));
            });
        });
        // Puntos 10-11: selector visual del catálogo de diseños.
        bindDesignPicker(card, idx);
        // P19: botón de la tabla de combinaciones de Panel Track.
        var btnLamas = card.querySelector('.btn-lamas-table');
        btnLamas && btnLamas.addEventListener('click', function () {
            refreshLamasTable(card, idx);
        });
        // Toggles
        card.querySelectorAll('.safra-toggle').forEach(function (tg) {
            var flip = function () {
                // Fila 13 (09-oct): un interruptor bloqueado no se mueve.
                if (tg.classList.contains('locked')) return;
                var on = !tg.classList.contains('on');
                tg.classList.toggle('on', on);
                var cb = tg.querySelector('input[type=checkbox]');
                if (cb) cb.checked = on;
                var txt = tg.querySelector('.safra-toggle-text');
                if (txt) txt.textContent = on ? 'Sí' : 'No';
                evalConditionals(card);
                // Exhibición cambia los límites de la ficha técnica.
                if (cb && cb.name && cb.name.indexOf('exhibition_') === 0) fetchPrice(card);
                // "Con Motor" cambia la tabla de estructura de la ficha
                // técnica y el máximo de lamas (fórmula manual vs motor).
                if (cb && cb.name && cb.name.indexOf('has_motor_') === 0) {
                    fetchPrice(card);
                    updateMaxLamas(card);
                    // 13-oct: Control, Canal y Módulo RF esperan al motor.
                    applyMotorMaestro(card, idx);
                }
                // Mismo cabezal: alinea por defecto e inhabilita el mando.
                if (cb && cb.name && cb.name.indexOf('same_header_') === 0) {
                    syncSameHeader(card, idx);
                    syncUnificacionSecuencias();
                }
                // El interruptor no dispara «change»: se avisa con un evento
                // propio a quien dependa del pedido completo (segmentos de
                // plano, revalidación en línea).
                tg.dispatchEvent(new CustomEvent('safra:toggle', { bubbles: true, detail: { name: cb ? cb.name : '' } }));
            };
            tg.addEventListener('click', flip);
            tg.addEventListener('keydown', function (e) {
                if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); flip(); }
            });
        });
        // Referencias → colores
        card.querySelectorAll('.sel-fabric').forEach(function (selFabric) {
            selFabric.addEventListener('change', function () {
                // Fase 5.4a: Tela Cabezal Forrado lista las telas de TODO el
                // pedido — refrescar las demás persianas también.
                document.querySelectorAll('#lines-container .safra-line').forEach(function (c) {
                    if (c !== card) smartDependencies(c);
                });
                loadColorsFor(card, selFabric);
                if (selFabric.getAttribute('data-color-target') === 'color_id') {
                    evalConditionals(card); fetchPrice(card);
                }
            });
        });
        var mainColor = card.querySelector('[name="color_id_' + idx + '"]');
        mainColor && mainColor.addEventListener('change', function () { fetchPrice(card); });

        card.querySelectorAll('.line-body').forEach(function (body) {
            body.addEventListener('change', function (e) {
                // Fase 5.4b: cualquier cambio invalida el "guardado" visual.
                card.classList.remove('line-saved');
                evalConditionals(card);
                if (e.target.classList.contains('inp-dim')) { updatePrintM2(card, idx); updateDesignAnalysis(card, idx); fetchPrice(card); }
                if (e.target.classList.contains('safra-design-file')) updateDesignAnalysis(card, idx);
                // Revisión 17-sep (#19): ancho/apertura/motor recalculan
                // el máximo total de lamas en los sistemas con fórmula.
                if (e.target.classList.contains('inp-dim') ||
                    e.target.name === 'apertura_' + idx ||
                    e.target.name === 'has_motor_' + idx ||
                    e.target.name === 'motor_' + idx) {
                    updateMaxLamas(card);
                }
                // P19: la tabla se recalcula al cambiar ancho, traslape o
                // cantidad de lamas (filtra solo viables). Reunión 09-oct
                // (fila 16): con ancho digitado se muestra sola, sin tener
                // que pulsar «Ver combinaciones posibles».
                // Ancho y alto: la fórmula del sistema puede usar el alto.
                if ((e.target.classList.contains('inp-dim') || e.target.name === 'tamano_traslape_' + idx ||
                    e.target.name === 'quantity_lamas_' + idx) && card.querySelector('.lamas-table-wrap') &&
                    (card.querySelector('.lamas-table-wrap').innerHTML || parseFloat(fieldValue(card, 'width')) > 0)) {
                    refreshLamasTable(card, idx);
                }
                if (e.target.name === 'apertura_' + idx || e.target.name === 'riel_tipo_' + idx) restrictRiel(card, idx);
                // Pendientes 24-sep (7.2/8.1): esos mismos cambios acotan
                // la apertura a las combinaciones fabricables.
                if (e.target.classList.contains('inp-dim') || e.target.name === 'tamano_traslape_' + idx ||
                    e.target.name === 'quantity_lamas_' + idx) {
                    restrictAperturaByCombos(card, idx);
                }
                // El tipo de cabezal y el perfil cambian estructura/fórmulas;
                // el motor cambia el kit (controles, interruptor, cargador).
                if (e.target.name && e.target.name.indexOf('sequence_name_') === 0) syncUnificacionSecuencias();
                if (e.target.name && (e.target.name.indexOf('cabezal_tipo_') === 0 ||
                    e.target.name.indexOf('unificacion_mando_') === 0 ||
                    e.target.name.indexOf('perfil') === 0 ||
                    e.target.name === 'motor_' + idx)) fetchPrice(card);
                // Pendientes 24-sep (11.5): en los 2 en 1 la Referencia 2 y
                // su color también refrescan el nombre del producto.
                if (e.target.name && /^(fabric_id|color_id)_[2-5]_/.test(e.target.name)) fetchPrice(card);
                // Pendientes 24-sep (14-17): el motor consulta el maestro y
                // el control define los canales disponibles.
                if (e.target.name === 'motor_' + idx) applyMotorMaestro(card, idx);
                // Reunión 13-oct: «Sin interruptor» oculta Control y Canal.
                if (e.target.name === 'interruptor_rf_' + idx) applyKit(card, idx, null);
                // Pendientes 24-sep (16.2): control/canal son estado
                // compartido del pedido — refresca TODAS las persianas.
                if (e.target.name === 'control_' + idx ||
                    e.target.name === 'control_channel_' + idx) syncAllChannels();
                updateSummary(card);
            });
            // Pendientes 24-sep (5.1): bloquear el punto/coma/exponente en
            // los campos enteros y sanear lo pegado.
            body.addEventListener('keydown', function (e) {
                if (e.target.getAttribute && e.target.getAttribute('data-int') === '1' &&
                    ['.', ',', 'e', 'E', '+', '-'].indexOf(e.key) !== -1) e.preventDefault();
            });
            body.addEventListener('input', function (e) {
                if (e.target.getAttribute && e.target.getAttribute('data-int') === '1' &&
                    e.target.value && e.target.value.indexOf('.') !== -1) {
                    e.target.value = e.target.value.split('.')[0];
                }
                if (e.target.classList.contains('fld-input')) evalConditionals(card);
                if (e.target.name && e.target.name.indexOf('sequence_name_') === 0) refreshSequenceList();
            });
        });
    }

    function renderBody(card, config) {
        var body = card.querySelector('.line-body');
        var idx = card.getAttribute('data-idx');
        config = config || {};
        card._safraConfig = config;
        // Telas filtradas por el sistema seleccionado; merge para los flags de tela.
        currentFabrics = config.fabrics || [];
        currentFamilias = config.familias_ref || {};
        currentFabrics.forEach(function (f) { fabricsById[String(f.id)] = f; });
        body.innerHTML = renderConfig(config, idx);
        bindBody(card);
        evalConditionals(card);
        // Las aperturas sin fórmula (hoy la Apertura Libre) se ocultan desde
        // que se pinta el formulario, no solo al digitar medidas.
        restrictAperturaByCombos(card, idx);
        // Sprint 1.3: la Unificación Mando se llena con los tubos del cálculo.
        syncUnificacion(card, idx, null);
        setupDynamicTelas(card);
        // 29-sep (8.3): estado inicial de los desplegables con miniatura.
        card.querySelectorAll('.sel-imgdrop').forEach(sidSync);
    }

    function bindCard(card) {
        var selSystem = card.querySelector('.sel-system');
        selSystem && selSystem.addEventListener('change', function () {
            var sid = selSystem.value;
            var body = card.querySelector('.line-body');
            if (!sid) {
                if (body) body.innerHTML = '<div class="safra-empty">Seleccione un sistema para configurar la línea.</div>';
                updateSummary(card);
                return;
            }
            rpc('/cotizador/ajax/config', { system_id: sid }).then(function (config) {
                renderBody(card, config || { fields: [] });
                updateSummary(card);
                syncAllChannels();
            });
        });
        var btnRemove = card.querySelector('.btn-remove-line');
        btnRemove && btnRemove.addEventListener('click', function () {
            var form = card.closest('form');
            card.remove(); updateLineNumbers(); updateTotal();
            // Los segmentos libres, los canales tomados y los errores del
            // pedido cambian.
            syncSegmentosPedido();
            syncAllChannels();
            if (form) revalidarEnLinea(form);
        });
        var btnDup = card.querySelector('.btn-duplicate-line');
        btnDup && btnDup.addEventListener('click', function () { duplicateLine(card); });
        // Colapsar / expandir con el encabezado (clic o teclado), sin
        // interferir con los botones de acciones.
        var header = card.querySelector('.line-header');
        var toggleCollapse = function (e) {
            if (e.target.closest('.line-actions')) return;
            // Fase 5.4b: una persiana a la vez — al abrir esta, las demás
            // se colapsan (acordeón).
            if (card.classList.contains('collapsed')) {
                document.querySelectorAll('#lines-container .safra-line').forEach(function (c) {
                    if (c !== card) c.classList.add('collapsed');
                });
            }
            card.classList.toggle('collapsed');
        };
        // Botón Guardar persiana (fase 5.4b)
        var btnSave = card.querySelector('.btn-save-line');
        btnSave && btnSave.addEventListener('click', function () { saveLine(card); });
        header && header.addEventListener('click', toggleCollapse);
        header && header.addEventListener('keydown', function (e) {
            if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); toggleCollapse(e); }
        });
    }

    function addLine() {
        var container = document.getElementById('lines-container');
        if (!container) return null;
        // El formulario se hace muy extenso (F134): al agregar una persiana
        // se colapsan las anteriores; el encabezado conserva el resumen.
        container.querySelectorAll('.safra-line').forEach(function (c) { c.classList.add('collapsed'); });
        var wrapper = document.createElement('div');
        wrapper.innerHTML = buildLineHtml(lineCount);
        var card = wrapper.firstElementChild;
        card.setAttribute('data-idx', lineCount);
        container.appendChild(card);
        bindCard(card);
        updateLineNumbers();
        lineCount++;
        card.scrollIntoView({ behavior: 'smooth', block: 'start' });
        return card;
    }

    // Duplicar persiana (hoja 1): clona todos los valores de la tarjeta y
    // deja la copia lista para cambiar solo lo necesario.
    function duplicateLine(srcCard) {
        var srcIdx = srcCard.getAttribute('data-idx');
        var suffix = new RegExp('^(.*)_' + srcIdx + '$');
        var values = {};
        srcCard.querySelectorAll('[name]').forEach(function (el) {
            var m = el.name.match(suffix);
            if (m) values[m[1]] = (el.type === 'checkbox') ? el.checked : el.value;
        });
        var card = addLine();
        if (!card || !values.system_id) return;
        // Reunión 13-oct: el canal es único por persiana — la copia lo
        // deja por elegir. El control se aplica cuando el motor cargue sus
        // controles (sus opciones llegan después).
        delete values.control_channel;
        card._pendingControl = values.control || null;
        var idx = card.getAttribute('data-idx');
        var sel = card.querySelector('.sel-system');
        if (sel) sel.value = values.system_id;
        rpc('/cotizador/ajax/config', { system_id: values.system_id }).then(function (config) {
            renderBody(card, config || { fields: [] });
            applyValues(card, idx, values);
        });
    }

    function applyValues(card, idx, values) {
        var colorJobs = [];
        Object.keys(values).forEach(function (code) {
            if (code === 'system_id') return;
            var el = card.querySelector('[name="' + code + '_' + idx + '"]');
            if (!el) return;
            if (el.type === 'checkbox') {
                el.checked = !!values[code];
                var tg = el.closest('.safra-toggle');
                if (tg) {
                    tg.classList.toggle('on', el.checked);
                    var txt = tg.querySelector('.safra-toggle-text');
                    if (txt) txt.textContent = el.checked ? 'Sí' : 'No';
                }
            } else if (el.classList.contains('sel-fabric')) {
                el.value = values[code];
                var target = el.getAttribute('data-color-target');
                colorJobs.push(loadColorsFor(card, el).then(function () {
                    var c = card.querySelector('[name="' + target + '_' + idx + '"]');
                    if (c && values[target] != null) c.value = values[target];
                }));
            } else if (!el.classList.contains('sel-color')) {
                el.value = values[code];
            }
        });
        Promise.all(colorJobs).then(function () {
            evalConditionals(card);
            // Reabre los pares de tela que traían valor en el duplicado.
            setupDynamicTelas(card);
            // Refleja el diseño elegido (check propio / vista previa).
            syncDesignPicker(card, idx);
            syncSameHeader(card, idx);
            updateMaxLamas(card);
            fetchPrice(card);
            updateSummary(card);
            applyMotorMaestro(card, idx);
        });
    }

    function parseJSON(id, fallback) {
        var el = document.getElementById(id);
        if (!el) return fallback;
        try { return JSON.parse(el.textContent || ''); } catch (e) { return fallback; }
    }

    // Listas desplegables con texto libre (F14 / F6): espacios sugeridos y
    // secuencias ya digitadas en otras persianas.
    function ensureDatalists() {
        if (!document.getElementById('safra-espacios')) {
            var dl = document.createElement('datalist');
            dl.id = 'safra-espacios';
            var html = '';
            for (var i = 1; i <= 10; i++) html += '<option value="Espacio ' + i + '"></option>';
            dl.innerHTML = html;
            document.body.appendChild(dl);
        }
        if (!document.getElementById('safra-secuencias')) {
            var dl2 = document.createElement('datalist');
            dl2.id = 'safra-secuencias';
            document.body.appendChild(dl2);
        }
        refreshSequenceList();
    }

    function refreshSequenceList() {
        var dl = document.getElementById('safra-secuencias');
        if (!dl) return;
        var seen = {}, html = '';
        document.querySelectorAll('[name^="sequence_name_"]').forEach(function (el) {
            var v = (el.value || '').trim();
            if (v && !seen[v]) { seen[v] = 1; html += '<option value="' + esc(v) + '"></option>'; }
        });
        for (var i = 1; i <= 10; i++) {
            var s = 'Secuencia ' + i;
            if (!seen[s]) html += '<option value="' + s + '"></option>';
        }
        dl.innerHTML = html;
    }

    // Resumen de pedido (F135): todas las persianas con imagen, descripción,
    // medidas y precio antes de guardar.
    function openSummary() {
        var overlay = document.getElementById('safra-summary-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = 'safra-summary-overlay';
            document.body.appendChild(overlay);
            overlay.addEventListener('click', function (e) {
                if (e.target === overlay) overlay.classList.remove('open');
            });
        }
        var rows = '';
        document.querySelectorAll('#lines-container .safra-line').forEach(function (card, n) {
            var idx = card.getAttribute('data-idx');
            var get = function (code) {
                var el = card.querySelector('[name="' + code + '_' + idx + '"]');
                return el ? (el.value || '') : '';
            };
            var img = card.querySelector('.pi-img');
            var prod = card.querySelector('.pi-producto');
            var pf = card.querySelector('.pi-final');
            var price = pf ? parseFloat(pf.dataset.price || 0) : 0;
            rows += '<tr>' +
                '<td>' + (n + 1) + '</td>' +
                '<td class="s-img">' + (img && img.src ? '<img src="' + esc(img.src) + '" alt=""/>' : '') + '</td>' +
                '<td>' + esc((prod && prod.textContent.trim()) || 'Persiana sin configurar') +
                    (get('location') ? '<br/><small>' + esc(get('location')) + '</small>' : '') + '</td>' +
                '<td>' + esc(get('width') || '—') + ' × ' + esc(get('height') || '—') + ' m</td>' +
                '<td>' + esc(get('quantity') || '1') + '</td>' +
                '<td class="s-num">' + money(price) + '</td></tr>';
        });
        var total = document.getElementById('total-grand');
        overlay.innerHTML = '<div class="safra-summary-modal">' +
            '<h3>Resumen de pedido</h3>' +
            '<div class="s-tablewrap"><table>' +
            '<thead><tr><th>#</th><th></th><th>Producto</th><th>Medidas</th><th>Cant.</th><th>Total</th></tr></thead>' +
            '<tbody>' + rows + '</tbody></table></div>' +
            '<div class="s-total">Total (IVA incluido): <strong>' + (total ? total.textContent : '$ 0') + '</strong></div>' +
            '<div class="s-actions">' +
            '<button type="button" class="btn-safra-light" id="btn-summary-close">Seguir editando</button>' +
            '<button type="button" class="btn-safra" id="btn-summary-save">Guardar pedido</button>' +
            '</div></div>';
        overlay.classList.add('open');
        overlay.querySelector('#btn-summary-close').addEventListener('click', function () {
            overlay.classList.remove('open');
        });
        overlay.querySelector('#btn-summary-save').addEventListener('click', function () {
            overlay.classList.remove('open');
            validateAndSubmit(document.getElementById('safra-quoter-form'));
        });
    }

    // Prevalidación del pedido: corre el motor de validaciones del servidor
    // antes del submit. Los errores bloquean; las advertencias solo informan.
    // Reúne los datos del formulario y pide la validación del pedido; las
    // validaciones locales (archivo del diseño propio) van primero.
    function collectIssues(form) {
        var data = {};
        new FormData(form).forEach(function (value, key) {
            // Los archivos no viajan por jsonrpc; van en el POST multipart.
            if (value instanceof File) return;
            data[key] = value;
        });
        // Diseño elegido exige el archivo con formato de aprobación (el
        // servidor también lo bloquea; esto solo evita el viaje).
        var localIssues = [];
        form.querySelectorAll('.safra-line').forEach(function (card, pos) {
            var i = card.getAttribute('data-idx');
            var sel = card.querySelector('[name="custom_design_' + i + '"]');
            var block = card.querySelector('.safra-design-block');
            var fi = card.querySelector('[name="design_file_' + i + '"]');
            // El archivo solo es obligatorio para «Diseño propio» (OTROS).
            if (sel && sel.value === 'OTROS' && block && !block.classList.contains('d-none') &&
                fi && !(fi.files && fi.files.length)) {
                localIssues.push({ line: pos + 1, severity: 'error', message: 'Diseño propio: adjunte el archivo del diseño a imprimir (JPG, PNG o PDF).' });
            }
        });
        return rpc('/cotizador/ajax/validar', data).then(function (issues) {
            return localIssues.concat(issues || []);
        });
    }

    // Pinta todos los errores (rojo) y advertencias (amarillo) del pedido.
    function renderIssues(form, issues) {
        var banner = document.getElementById('safra-val-banner');
        if (!banner) {
            banner = document.createElement('div');
            banner.id = 'safra-val-banner';
            form.parentNode.insertBefore(banner, form);
        }
        var errors = issues.filter(function (i) { return i.severity === 'error'; });
        var others = issues.filter(function (i) { return i.severity !== 'error'; });
        var html = '';
        if (errors.length) {
            html += '<div class="alert alert-danger"><strong>Corrija los siguientes errores:</strong><ul class="mb-0">' +
                errors.map(function (i) { return '<li>Persiana ' + i.line + ': ' + esc(i.message) + '</li>'; }).join('') +
                '</ul></div>';
        }
        if (others.length) {
            // Acuerdo de la reunión: las advertencias no bloquean, pero
            // el cliente debe VERLAS y decidir — sin este alto el submit
            // navegaba de inmediato y el aviso desaparecía sin leerse.
            html += '<div class="alert alert-warning"><ul class="mb-0">' +
                others.map(function (i) { return '<li>Persiana ' + i.line + ': ' + esc(i.message) + '</li>'; }).join('') +
                '</ul>' +
                (errors.length ? '' :
                    '<button type="button" class="btn btn-warning btn-sm mt-2" id="btn-warn-continue">' +
                    'Entiendo, enviar el pedido de todos modos</button>') +
                '</div>';
        }
        // Reunión 09-oct (fila 4): el aviso de arriba se conserva y abre de
        // nuevo la ventana con el detalle.
        if (html) {
            html += '<button type="button" class="btn btn-link btn-sm p-0 mb-2" id="btn-val-detalle">' +
                '<i class="fa fa-external-link"></i> Ver los mensajes en una ventana</button>';
        }
        banner.innerHTML = html;
        form._safraIssues = issues;
        var go = banner.querySelector('#btn-warn-continue');
        if (go) go.addEventListener('click', function () { form.submit(); });
        var det = banner.querySelector('#btn-val-detalle');
        if (det) det.addEventListener('click', function () { openIssuesModal(form, form._safraIssues || []); });
        return { banner: banner, total: errors.length + others.length };
    }

    // Reunión 09-oct (fila 4): al Finalizar con errores o advertencias se
    // abre una ventana con TODOS los mensajes — el aviso de arriba quedaba
    // fuera de la vista y el cliente no sabía por qué no avanzaba. Con solo
    // advertencias, la ventana ofrece enviar el pedido de todos modos.
    function openIssuesModal(form, issues) {
        var overlay = document.getElementById('safra-issues-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = 'safra-issues-overlay';
            document.body.appendChild(overlay);
            overlay.addEventListener('click', function (e) {
                if (e.target === overlay) overlay.classList.remove('open');
            });
        }
        var errors = issues.filter(function (i) { return i.severity === 'error'; });
        var others = issues.filter(function (i) { return i.severity !== 'error'; });
        var lista = function (items) {
            return '<ul>' + items.map(function (i) {
                return '<li><strong>Persiana ' + i.line + ':</strong> ' + esc(i.message) + '</li>';
            }).join('') + '</ul>';
        };
        overlay.innerHTML = '<div class="safra-summary-modal safra-issues-modal" role="dialog" aria-modal="true">' +
            '<h3>' + (errors.length ? 'El pedido tiene errores por corregir' : 'Revise las advertencias del pedido') + '</h3>' +
            (errors.length ? '<div class="alert alert-danger"><strong>Errores (' + errors.length + '):</strong> no permiten enviar el pedido.' + lista(errors) + '</div>' : '') +
            (others.length ? '<div class="alert alert-warning"><strong>Advertencias (' + others.length + '):</strong> no bloquean, pero revíselas antes de enviar.' + lista(others) + '</div>' : '') +
            '<div class="s-actions">' +
            '<button type="button" class="btn-safra-light" id="btn-issues-close">' + (errors.length ? 'Corregir' : 'Seguir editando') + '</button>' +
            (errors.length ? '' : '<button type="button" class="btn-safra" id="btn-issues-send">Entiendo, enviar el pedido de todos modos</button>') +
            '</div></div>';
        overlay.classList.add('open');
        overlay.querySelector('#btn-issues-close').addEventListener('click', function () {
            overlay.classList.remove('open');
            var banner = document.getElementById('safra-val-banner');
            if (banner) banner.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
        var send = overlay.querySelector('#btn-issues-send');
        if (send) send.addEventListener('click', function () {
            overlay.classList.remove('open');
            form.submit();
        });
    }

    function validateAndSubmit(form) {
        collectIssues(form).then(function (issues) {
            var r = renderIssues(form, issues);
            if (r.total) {
                // Desde este intento el aviso se mantiene al día solo.
                form._safraLiveVal = true;
                openIssuesModal(form, issues);
                return;
            }
            form._safraLiveVal = false;
            form.submit();
        }).catch(function () {
            // Si la prevalidación falla, el respaldo del servidor decide.
            form.submit();
        });
    }

    // Reunión 28-sep (fila 13): tras un «Finalizar» con errores, cada
    // cambio del cliente vuelve a validar el pedido (con una pausa para no
    // consultar al servidor en cada tecla) y el aviso se actualiza: lo
    // corregido desaparece sin tener que pulsar Finalizar otra vez.
    var liveValTimer = null;
    function revalidarEnLinea(form) {
        if (!form._safraLiveVal) return;
        clearTimeout(liveValTimer);
        liveValTimer = setTimeout(function () {
            collectIssues(form).then(function (issues) {
                if (!renderIssues(form, issues).total) {
                    form._safraLiveVal = false;
                    var ov = document.getElementById('safra-issues-overlay');
                    if (ov) ov.classList.remove('open');
                }
            }).catch(function () {});
        }, 800);
    }

    function init() {
        var form = document.getElementById('safra-quoter-form');
        if (!form) return;
        systems = parseJSON('safra-systems-data', []);
        defaultConfig = parseJSON('safra-default-config', { fields: [] });
        defaultSystemId = form.getAttribute('data-default-system') || 0;
        var btnAdd = document.getElementById('btn-add-line');
        if (btnAdd) btnAdd.addEventListener('click', function () { addLine(); });
        var btnSummary = document.getElementById('btn-summary');
        if (btnSummary) btnSummary.addEventListener('click', openSummary);
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            validateAndSubmit(form);
        });
        ['input', 'change', 'safra:toggle'].forEach(function (ev) {
            form.addEventListener(ev, function () { revalidarEnLinea(form); });
        });
        ensureDatalists();
        // Revisión 17-sep: la rueda del mouse sobre un campo numérico
        // cambiaba medidas sin querer — al detectar la rueda se quita el
        // foco y el scroll sigue normal.
        form.addEventListener('wheel', function (e) {
            var t = e.target;
            if (t && t.tagName === 'INPUT' && t.type === 'number') t.blur();
        }, { passive: true });
        addLine();
    }

    // El configurador de secuencia (safra_secuencia.js) refresca el
    // encabezado de las persianas después de asignar los soportes.
    window.safraUpdateSummary = updateSummary;
    // Bloque 3: el modal de secuencia amplía la imagen del plano con el
    // mismo lightbox del cotizador.
    window.safraOpenLightbox = openLightbox;

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
}());
