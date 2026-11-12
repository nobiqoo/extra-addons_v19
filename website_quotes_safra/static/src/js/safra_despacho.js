/* Matriz, Datos de despacho (filas 184-188, reunión 26-oct): bloque para
   todo el pedido en el cotizador y en el cargue masivo. «Recoge en fábrica»
   oculta país, ciudad, dirección y destinatario; la ciudad se elige de las
   del país (res.city). Las reglas (V_DESPACHO_DATOS) las revisa el servidor
   al finalizar. */
(function () {
    'use strict';

    function rpc(url, params) {
        return fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: params || {} }),
        }).then(function (r) { return r.json(); }).then(function (d) {
            if (d.error) throw d.error;
            return d.result;
        });
    }

    function esc(s) {
        return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
        });
    }

    function syncRecoge(block) {
        var recoge = block.querySelector('[name="recoge_fabrica"]');
        var envio = block.querySelector('.safra-despacho-envio');
        if (envio) envio.classList.toggle('d-none', !!(recoge && recoge.checked));
    }

    function cargarCiudades(block) {
        var pais = block.querySelector('[name="despacho_country_id"]');
        var ciudad = block.querySelector('[name="despacho_city_id"]');
        if (!pais || !ciudad) return Promise.resolve();
        var quiere = ciudad.dataset.selected || ciudad.value || '';
        if (!pais.value) {
            ciudad.innerHTML = '<option value="">-- Seleccione uno --</option>';
            return Promise.resolve();
        }
        var turno = (ciudad._turno || 0) + 1;
        ciudad._turno = turno;
        return rpc('/cotizador/ajax/ciudades', { country_id: pais.value }).then(function (lista) {
            if (ciudad._turno !== turno) return;
            ciudad.innerHTML = '<option value="">-- Seleccione uno --</option>' + (lista || []).map(function (c) {
                return '<option value="' + c.id + '">' + esc(c.name) + '</option>';
            }).join('');
            ciudad.value = quiere && ciudad.querySelector('option[value="' + quiere + '"]') ? quiere : '';
            delete ciudad.dataset.selected;
        }).catch(function () { /* sin respuesta: la lista queda como estaba */ });
    }

    function init(block) {
        if (block._despachoListo) return;
        block._despachoListo = true;
        var recoge = block.querySelector('[name="recoge_fabrica"]');
        if (recoge) recoge.addEventListener('change', function () { syncRecoge(block); });
        var pais = block.querySelector('[name="despacho_country_id"]');
        if (pais) pais.addEventListener('change', function () { cargarCiudades(block); });
        syncRecoge(block);
        cargarCiudades(block);
    }

    // Al editar una cotización: lo que trae guardado (controlador
    // _datos_edicion, clave «despacho»).
    window.safraDespachoCargar = function (datos) {
        var block = document.querySelector('.safra-despacho');
        if (!block || !datos) return;
        init(block);
        var set = function (name, value) {
            var el = block.querySelector('[name="' + name + '"]');
            if (el) el.value = value || '';
        };
        var recoge = block.querySelector('[name="recoge_fabrica"]');
        if (recoge) recoge.checked = !!datos.recoge_fabrica;
        if (datos.country_id) set('despacho_country_id', String(datos.country_id));
        var ciudad = block.querySelector('[name="despacho_city_id"]');
        if (ciudad) ciudad.dataset.selected = datos.city_id ? String(datos.city_id) : '';
        set('despacho_direccion', datos.direccion);
        set('despacho_destinatario', datos.destinatario);
        set('despacho_fecha', datos.fecha);
        syncRecoge(block);
        cargarCiudades(block);
    };

    function start() {
        document.querySelectorAll('.safra-despacho').forEach(init);
        // Lo que el cotizador dejó pendiente al editar (arrancó antes).
        if (window.safraDespachoPendiente) {
            var datos = window.safraDespachoPendiente;
            window.safraDespachoPendiente = null;
            window.safraDespachoCargar(datos);
        }
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
    else start();
}());
