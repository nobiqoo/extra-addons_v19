/* Fase 5.4c — Configurador de persianas en secuencia.
 *
 * Réplica del programa HTML entregado por el cliente
 * (Configuracion_visual_mismo_cabezal_misma_ventana_3.html): las persianas
 * con «Mismo cabezal» del mismo nombre de secuencia se dibujan lado a lado
 * y el cliente asigna piezas a los soportes (MANDO, MOTOR, DEP, INDEP,
 * TERMINAL) en orden de izquierda a derecha. Las reglas de negocio se
 * portaron 1:1; la colocación es por clic (la pieza cae en el soporte
 * activo), con deshacer y borrar todo.
 */
(function () {
    'use strict';

    var IMG = '/website_quotes_safra/static/src/img/secuencia/';
    var PIEZAS = [
        { value: 'MANDO', title: 'Mando' },
        { value: 'MOTOR', title: 'Motor' },
        { value: 'DEP', title: 'Soporte central dependiente' },
        { value: 'INDEP', title: 'Soporte central independiente' },
        { value: 'TERMINAL', title: 'Terminal' },
    ];

    // Estado del configurador abierto
    var seqCards = [];      // tarjetas (en orden) de la secuencia activa
    var sequence = [];      // 3 posiciones por persiana [izq, persiana, der]
    var historial = [];

    function esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    // ==================== REGLAS (porte 1:1 del programa del cliente) ====
    function cantPersianas() { return seqCards.length; }
    function getPersianaIndex(index) { return Math.floor(index / 3); }
    function getPosEnGrupo(index) { return index % 3; }
    function esExtremo(index) { return index === 0 || index === sequence.length - 1; }

    function getSoportePareja(index) {
        var p = getPersianaIndex(index), pos = getPosEnGrupo(index);
        if (pos === 2 && p < cantPersianas() - 1) return index + 1;
        if (pos === 0 && p > 0) return index - 1;
        return -1;
    }
    function getOtroSoportePropio(index) {
        var p = getPersianaIndex(index), li = p * 3, ri = p * 3 + 2;
        return (index === li) ? ri : li;
    }
    function esFuenteTraccion(value) { return value === 'MANDO' || value === 'MOTOR'; }

    function getIndicesSoporte() {
        var indices = [];
        for (var p = 0; p < cantPersianas(); p++) { indices.push(p * 3); indices.push(p * 3 + 2); }
        return indices;
    }
    function getPrimerIndiceVacio() {
        var indices = getIndicesSoporte();
        for (var i = 0; i < indices.length; i++) {
            if (sequence[indices[i]] === '') return indices[i];
        }
        return -1;
    }
    function grupoCompleto(seq, grupo) {
        for (var i = 0; i < grupo.length; i++) {
            var p = grupo[i];
            if (seq[p * 3] === '' || seq[p * 3 + 2] === '') return false;
        }
        return true;
    }
    function calcularCadenas(seq) {
        var n = cantPersianas(), padre = [];
        for (var i = 0; i < n; i++) padre[i] = i;
        function encontrar(x) { while (padre[x] !== x) x = padre[x]; return x; }
        function unir(a, b) { var ra = encontrar(a), rb = encontrar(b); if (ra !== rb) padre[ra] = rb; }
        for (var p = 0; p < n - 1; p++) {
            if (seq[p * 3 + 2] === 'DEP' && seq[(p + 1) * 3] === 'DEP') unir(p, p + 1);
        }
        var grupos = {};
        for (var j = 0; j < n; j++) {
            var raiz = encontrar(j);
            (grupos[raiz] = grupos[raiz] || []).push(j);
        }
        return Object.keys(grupos).map(function (k) { return grupos[k]; });
    }
    function contarMandosEnGrupo(seq, grupo) {
        var total = 0;
        grupo.forEach(function (p) {
            if (esFuenteTraccion(seq[p * 3])) total++;
            if (esFuenteTraccion(seq[p * 3 + 2])) total++;
        });
        return total;
    }

    function validarColocacion(index, value) {
        if (!value) return { valido: true, resultado: sequence.slice() };
        var clone = sequence.slice();

        if (esExtremo(index) && (value === 'DEP' || value === 'INDEP')) {
            return { valido: false, mensaje: 'La secuencia no puede iniciar ni terminar con un soporte dependiente/independiente.' };
        }
        var pareja = getSoportePareja(index);
        if (pareja !== -1) {
            var valorVecino = clone[pareja];
            var esConectorNuevo = (value === 'DEP' || value === 'INDEP');
            var esConectorVecino = (valorVecino === 'DEP' || valorVecino === 'INDEP');
            if (valorVecino !== '' && (esConectorNuevo || esConectorVecino) && valorVecino !== value) {
                return { valido: false, mensaje: 'Los soportes que se enfrentan en esta unión deben coincidir. El soporte opuesto ya tiene "' + valorVecino + '".' };
            }
            if (esFuenteTraccion(value) && esFuenteTraccion(valorVecino)) {
                return { valido: false, mensaje: 'No puede haber dos fuentes de tracción (mando/motor) enfrentadas en la misma unión.' };
            }
        }
        if (esFuenteTraccion(value) && esFuenteTraccion(clone[getOtroSoportePropio(index)])) {
            return { valido: false, mensaje: 'Esta persiana ya tiene una fuente de tracción (mando/motor) en su otro soporte; una persiana no puede tener dos.' };
        }
        clone[index] = value;
        // Espejo automático DEP/INDEP hacia el soporte de enfrente vacío
        if (pareja !== -1 && (value === 'DEP' || value === 'INDEP') && clone[pareja] === '') {
            clone[pareja] = value;
        }
        var cadenas = calcularCadenas(clone);
        for (var i = 0; i < cadenas.length; i++) {
            var grupo = cadenas[i];
            var mandos = contarMandosEnGrupo(clone, grupo);
            var nombres = grupo.map(function (p) { return 'Persiana ' + (p + 1); }).join(', ');
            if (mandos > 1) {
                return { valido: false, mensaje: 'Conflicto de tracción: ' + nombres + ' quedarían unidas por soportes dependientes y no pueden tener más de un mando entre todas.' };
            }
            if (mandos === 0 && grupoCompleto(clone, grupo)) {
                return { valido: false, mensaje: 'Falta una fuente de tracción: ' + nombres + ' quedarían sin ningún mando ni motor.' };
            }
        }
        return { valido: true, resultado: clone };
    }

    // ==================== UI =============================================
    function overlay() {
        var ov = document.getElementById('safra-seq-overlay');
        if (!ov) {
            ov = document.createElement('div');
            ov.id = 'safra-seq-overlay';
            document.body.appendChild(ov);
            ov.addEventListener('click', function (e) {
                if (e.target === ov) ov.classList.remove('open');
            });
        }
        return ov;
    }

    function cardValue(card, code) {
        var el = card.querySelector('[name="' + code + '_' + card.getAttribute('data-idx') + '"]');
        if (!el) return '';
        return el.type === 'checkbox' ? (el.checked ? '1' : '') : (el.value || '');
    }

    function cardLabel(card, n) {
        var prod = card.querySelector('.pi-producto');
        var name = prod && prod.textContent.trim();
        return 'Persiana ' + n + (name && name !== '​' ? '<br/><small>' + esc(name) + '</small>' : '');
    }

    // Grupos de secuencia: tarjetas con Mismo cabezal, por nombre de secuencia
    function collectGroups() {
        var groups = {};
        document.querySelectorAll('#lines-container .safra-line').forEach(function (card) {
            if (cardValue(card, 'same_header') !== '1') return;
            var key = (cardValue(card, 'sequence_name') || 'Sin nombre').trim() || 'Sin nombre';
            (groups[key] = groups[key] || []).push(card);
        });
        return groups;
    }

    function pintarSoporte(index) {
        var valor = sequence[index];
        var primerVacio = getPrimerIndiceVacio();
        var cls = 'seq-sop';
        var title = '';
        if (valor === '' && index === primerVacio) {
            cls += ' seq-sop-activo';
            title = 'Siguiente soporte a configurar: elija una pieza abajo';
        } else if (valor === '') {
            cls += ' seq-sop-futuro';
            title = 'Complete los soportes anteriores primero (de izquierda a derecha)';
        }
        return '<div class="' + cls + '" title="' + esc(title) + '">' +
            (valor ? '<img src="' + IMG + valor.toLowerCase() + '.png" alt="' + esc(valor) + '"/>' : '') +
            '</div>';
    }

    function pintarCanvas() {
        var canvas = document.getElementById('seq-canvas');
        if (!canvas) return;
        var html = '';
        for (var p = 0; p < cantPersianas(); p++) {
            html += '<div class="seq-unit">' +
                '<div class="seq-sops">' + pintarSoporte(p * 3) + pintarSoporte(p * 3 + 2) + '</div>' +
                '<div class="seq-per"><img src="' + IMG + 'persiana.png" alt="Persiana"/><br/>' +
                '<span>' + cardLabel(seqCards[p], p + 1) + '</span></div>' +
                '</div>';
        }
        canvas.innerHTML = html;
        // Paleta habilitada solo si queda un soporte por llenar
        var done = getPrimerIndiceVacio() === -1;
        document.querySelectorAll('.seq-pieza').forEach(function (b) { b.disabled = done; });
        var msg = document.getElementById('seq-msg');
        if (msg && done) { msg.textContent = 'Secuencia completa. Pulse «Aplicar» para guardarla en el pedido.'; msg.className = 'seq-msg ok'; }
    }

    function setMsg(text, bad) {
        var msg = document.getElementById('seq-msg');
        if (msg) { msg.textContent = text || ''; msg.className = 'seq-msg' + (bad ? ' bad' : ''); }
    }

    function colocar(value) {
        var index = getPrimerIndiceVacio();
        if (index === -1) return;
        var v = validarColocacion(index, value);
        if (!v.valido) { setMsg(v.mensaje, true); return; }
        historial.push(sequence.slice());
        sequence = v.resultado;
        setMsg('Colocado ' + value + ' en la persiana ' + (getPersianaIndex(index) + 1) + '.');
        pintarCanvas();
    }

    function deshacer() {
        if (!historial.length) { setMsg('No hay ningún paso para deshacer.', true); return; }
        sequence = historial.pop();
        setMsg('Se deshizo el último paso.');
        pintarCanvas();
    }

    function borrarTodo() {
        sequence = sequence.map(function () { return ''; });
        historial = [];
        setMsg('Se borró toda la configuración.');
        pintarCanvas();
    }

    function cargarGrupo(cards) {
        seqCards = cards;
        historial = [];
        sequence = [];
        for (var p = 0; p < cards.length; p++) {
            sequence.push(cardValue(cards[p], 'soporte_izq'));
            sequence.push('');
            sequence.push(cardValue(cards[p], 'soporte_der'));
        }
        pintarCanvas();
        setMsg('');
        // Reunión 28-sep (fila 5): no se configura una secuencia de una
        // sola persiana.
        var unaSola = cards.length < 2;
        var btn = document.getElementById('seq-apply');
        if (btn) btn.disabled = unaSola;
        document.querySelectorAll('.seq-pieza').forEach(function (b) { b.disabled = unaSola; });
        if (unaSola) {
            setMsg('Esta secuencia tiene una sola persiana. Una secuencia necesita al menos dos: ' +
                'agregue otra persiana con el mismo Nombre de secuencia o desmarque «Mismo cabezal».', true);
        }
    }

    function ensureHidden(card, code) {
        var idx = card.getAttribute('data-idx');
        var el = card.querySelector('[name="' + code + '_' + idx + '"]');
        if (!el) {
            el = document.createElement('input');
            el.type = 'hidden';
            el.name = code + '_' + idx;
            card.querySelector('.line-body').appendChild(el);
        }
        return el;
    }

    function aplicar() {
        if (seqCards.length < 2) return;
        // Reporte 28-sep: «Aplicar» sin armar nada dejaba pasar la
        // secuencia vacía (y el pedido se guardaba). Todos los soportes
        // izq/der deben estar asignados antes de aplicar.
        var faltantes = [];
        for (var q = 0; q < seqCards.length; q++) {
            if (!sequence[q * 3] || !sequence[q * 3 + 2]) faltantes.push(q + 1);
        }
        if (faltantes.length) {
            setMsg('Complete los soportes de ' +
                (faltantes.length === 1 ? 'la persiana ' : 'las persianas ') +
                faltantes.join(', ') + ' antes de aplicar (o use Cancelar).', true);
            return;
        }
        for (var p = 0; p < seqCards.length; p++) {
            var card = seqCards[p];
            var izq = sequence[p * 3], der = sequence[p * 3 + 2];
            ensureHidden(card, 'soporte_izq').value = izq;
            ensureHidden(card, 'soporte_der').value = der;
            // Coherencia con «Con Motor»: si la secuencia le asigna motor,
            // el check de la persiana se activa solo.
            if (izq === 'MOTOR' || der === 'MOTOR') {
                var cb = card.querySelector('[name="has_motor_' + card.getAttribute('data-idx') + '"]');
                if (cb && !cb.checked) {
                    var tg = cb.closest('.safra-toggle');
                    if (tg) tg.click(); else cb.checked = true;
                }
            }
        }
        // Bloque 3 (reunión 28-sep): la secuencia es UN segmento de cabezal:
        // su Tipo de Plano y su Segmento se copian a todas sus persianas.
        var ovEl = overlay();
        var planoSel = ovEl.querySelector('#seq-tipo_plano');
        if (planoSel) {
            var plano = planoSel.value;
            var segSel = ovEl.querySelector('#seq-segmento');
            var op = planoSel.options[planoSel.selectedIndex];
            var total = parseInt((op && op.getAttribute('data-seg')) || '0', 10);
            var seg = plano && segSel ? segSel.value : '';
            if (plano && total && !seg) {
                setMsg('Con Tipo de Plano ' + plano + ' elija el Segmento de esta secuencia.', true);
                return;
            }
            seqCards.forEach(function (card) {
                var idx = card.getAttribute('data-idx');
                [['tipo_plano', plano], ['num_segmento', seg]].forEach(function (par) {
                    var el = card.querySelector('[name="' + par[0] + '_' + idx + '"]');
                    if (el && el.value !== par[1]) {
                        if (el.tagName === 'SELECT' && par[1] &&
                            !el.querySelector('option[value="' + par[1] + '"]')) {
                            el.insertAdjacentHTML('beforeend', '<option value="' + esc(par[1]) + '">' + esc(par[1]) + '</option>');
                        }
                        el.value = par[1];
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                });
            });
        }
        // OBS REU GENERALES 11-sep: que la secuencia asignada salga en el
        // encabezado de cada persiana.
        if (window.safraUpdateSummary) seqCards.forEach(window.safraUpdateSummary);
        overlay().classList.remove('open');
    }

    // ---- Bloque 3: Tipo de Plano y Segmento de la secuencia ---------------
    // Acuerdos 17-sep y 28-sep: con «Mismo cabezal» se diligencian AQUÍ, una
    // sola vez para toda la secuencia (un cabezal = un segmento del plano).
    // El plano se muestra como «Lista con foto pequeña» con su croquis
    // ampliable; el Segmento ofrece 1..N según el plano (data-seg) sin los
    // que ya usa otro cabezal del pedido con el mismo plano.
    function segmentosTomados(plano) {
        var tomados = {};
        if (!plano) return tomados;
        document.querySelectorAll('#lines-container .safra-line').forEach(function (card) {
            if (seqCards.indexOf(card) !== -1) return;
            if (cardValue(card, 'tipo_plano').toUpperCase() !== plano.toUpperCase()) return;
            var seg = cardValue(card, 'num_segmento');
            if (seg) tomados[seg] = true;
        });
        return tomados;
    }

    function renderExtra(ov) {
        var extra = ov.querySelector('.seq-extra');
        if (!extra) return;
        var first = seqCards[0];
        var src = first && first.querySelector('[name="tipo_plano_' + first.getAttribute('data-idx') + '"]');
        if (!src || src.tagName !== 'SELECT') { extra.innerHTML = ''; return; }
        var opts = '';
        Array.prototype.forEach.call(src.options, function (o) {
            opts += '<option value="' + esc(o.value) + '"' +
                (o.getAttribute('data-seg') ? ' data-seg="' + esc(o.getAttribute('data-seg')) + '"' : '') +
                (o.getAttribute('data-img') ? ' data-img="' + esc(o.getAttribute('data-img')) + '"' : '') +
                (o.value === src.value ? ' selected' : '') + '>' + esc(o.text) + '</option>';
        });
        // El plano usa el modo «Lista con foto pequeña» del cotizador
        // (sel-imgdrop): la delegación global de safra_quoter.js maneja
        // abrir/elegir/zoom buscando el select por su name.
        extra.innerHTML =
            '<div class="seq-plano">' +
            '<label class="seq-shared"><span>Tipo de Plano</span>' +
            '<select id="seq-tipo_plano" name="seq_tipo_plano" class="form-select sel-img-only" data-display="list_thumbs">' + opts + '</select>' +
            '<div class="sel-imgdrop" data-for="seq_tipo_plano">' +
            '<button type="button" class="sid-toggle">' +
            '<span class="sid-thumb"></span>' +
            '<span class="sid-label">-- Seleccione uno --</span>' +
            '<span class="sid-caret">▾</span></button>' +
            '<div class="sid-menu d-none"></div></div></label>' +
            '<img id="seq-plano-img" alt="Plano de instalación" title="Clic para ampliar"/>' +
            '</div>' +
            '<div class="seq-segs" id="seq-segs">' +
            '<label class="seq-seg-row"><span>Segmento</span>' +
            '<select class="form-select" id="seq-segmento"></select></label>' +
            '<span class="seq-segs-title">Segmento del plano que ocupa esta secuencia. ' +
            'No aparecen los segmentos que ya tiene otra secuencia o persiana del pedido con este plano.</span>' +
            '</div>';
        var planoSel = extra.querySelector('#seq-tipo_plano');
        planoSel.addEventListener('change', function () {
            refreshSegmentos(extra);
        });
        var img = extra.querySelector('#seq-plano-img');
        img.addEventListener('click', function () {
            if (!img.src) return;
            if (window.safraOpenLightbox) window.safraOpenLightbox(img.src);
            else window.open(img.src, '_blank');
        });
        refreshSegmentos(extra, true);
        // Sincroniza el botón del desplegable (miniatura + etiqueta) con el
        // valor inicial: el listener global de change hace el sidSync.
        planoSel.dispatchEvent(new Event('change', { bubbles: true }));
    }

    function refreshSegmentos(extra, initial) {
        var planoSel = extra.querySelector('#seq-tipo_plano');
        var op = planoSel.options[planoSel.selectedIndex];
        var total = parseInt((op && op.getAttribute('data-seg')) || '0', 10);
        var imgSrc = (op && op.getAttribute('data-img')) || '';
        var img = extra.querySelector('#seq-plano-img');
        img.style.display = imgSrc ? '' : 'none';
        if (imgSrc) img.src = imgSrc;
        extra.querySelector('#seq-segs').style.display = planoSel.value && total ? '' : 'none';
        var sel = extra.querySelector('#seq-segmento');
        // En el primer render se rescata el segmento ya guardado.
        var cur = initial && seqCards[0] ? cardValue(seqCards[0], 'num_segmento') : sel.value;
        var tomados = segmentosTomados(planoSel.value);
        var html = '<option value="">-- Seleccione --</option>';
        for (var i = 1; i <= total; i++) {
            if (tomados[i] && String(i) !== cur) continue;
            html += '<option value="' + i + '"' + (String(i) === cur ? ' selected' : '') + '>' + i + '</option>';
        }
        sel.innerHTML = html;
    }

    function open() {
        var groups = collectGroups();
        var keys = Object.keys(groups);
        if (!keys.length) {
            alert('Para configurar una secuencia, marque «Mismo cabezal o Soporte intermedio» en las persianas que la componen (y dales el mismo Nombre de secuencia).');
            return;
        }
        var ov = overlay();
        var selector = '';
        if (keys.length > 1) {
            selector = '<label class="seq-shared"><span>Secuencia</span><select id="seq-group">' +
                keys.map(function (k) { return '<option value="' + esc(k) + '">' + esc(k) + ' (' + groups[k].length + (groups[k].length === 1 ? ' persiana' : ' persianas') + ')</option>'; }).join('') +
                '</select></label>';
        }
        ov.innerHTML = '<div class="safra-seq-modal">' +
            '<h3>Configurador de persianas en secuencia</h3>' +
            '<p class="seq-help">Asigne las piezas a los soportes en orden, de izquierda a derecha. Al colocar un soporte dependiente o independiente, el del frente se llena solo.</p>' +
            selector +
            '<div class="seq-canvas-wrap"><div id="seq-canvas"></div></div>' +
            '<div class="seq-palette">' +
            PIEZAS.map(function (pz) {
                return '<button type="button" class="seq-pieza" data-value="' + pz.value + '" title="' + esc(pz.title) + '">' +
                    '<img src="' + IMG + pz.value.toLowerCase() + '.png" alt=""/><span>' + esc(pz.title) + '</span></button>';
            }).join('') +
            '</div>' +
            '<div id="seq-msg" class="seq-msg"></div>' +
            '<div class="seq-extra"></div>' +
            '<div class="seq-actions">' +
            '<button type="button" class="btn-safra-light" id="seq-undo">Deshacer último paso</button>' +
            '<button type="button" class="btn-safra-light" id="seq-clear">Borrar todo</button>' +
            '<button type="button" class="btn-safra-light" id="seq-close">Cancelar</button>' +
            '<button type="button" class="btn-safra" id="seq-apply">Aplicar</button>' +
            '</div></div>';

        cargarGrupo(groups[keys[0]]);
        // El bloque de plano/segmentos depende del grupo cargado
        renderExtra(ov);

        var groupSel = ov.querySelector('#seq-group');
        groupSel && groupSel.addEventListener('change', function () {
            cargarGrupo(groups[groupSel.value]);
            renderExtra(ov);
        });
        ov.querySelectorAll('.seq-pieza').forEach(function (b) {
            b.addEventListener('click', function () { colocar(b.getAttribute('data-value')); });
        });
        ov.querySelector('#seq-undo').addEventListener('click', deshacer);
        ov.querySelector('#seq-clear').addEventListener('click', borrarTodo);
        ov.querySelector('#seq-close').addEventListener('click', function () { ov.classList.remove('open'); });
        ov.querySelector('#seq-apply').addEventListener('click', aplicar);
        ov.classList.add('open');
    }

    function init() {
        var btn = document.getElementById('btn-secuencia');
        if (btn) btn.addEventListener('click', open);
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
}());
