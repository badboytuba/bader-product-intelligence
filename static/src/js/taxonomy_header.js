/** @odoo-module **/
import publicWidget from 'web.public.widget';

let searchId = 0;
const text = value => new DOMParser().parseFromString(String(value || ''), 'text/html').body.textContent || '';
const localUrl = value => {
    if (!value) return '';
    try {
        const url = new URL(value, window.location.origin);
        return url.origin === window.location.origin && !url.username && !url.password ? url.href : '';
    } catch (_) { return ''; }
};

// Odoo 16 returns an image URL, not an <img>. Tolerate legacy HTML without
// ever inserting server HTML into the page or loading third-party resources.
export function searchImage(value) {
    const raw = String(value || '').trim();
    const source = raw.startsWith('<') ? new DOMParser().parseFromString(raw, 'text/html').querySelector('img')?.getAttribute('src') : text(raw);
    const url = localUrl(source);
    return url && new URL(url).pathname.startsWith('/web/image/') ? url : '';
}

export const BpiTaxonomySearch = publicWidget.Widget.extend({
    selector: '.bpi-header-search',
    events: {
        'input input[name="search"]': '_onInput',
        'focus input[name="search"]': '_onFocus',
        'keydown input[name="search"]': '_onKeydown',
        'submit form': '_onSubmit',
        'click .bpi-hs-clear': '_onClear',
        'focusout': '_onFocusOut',
    },
    start() {
        this.input = this.el.querySelector('input[name="search"]');
        this.popup = this.el.querySelector('.bpi-hs-results');
        this.list = this.el.querySelector('.bpi-hs-list');
        this.summary = this.el.querySelector('.bpi-hs-summary');
        this.all = this.el.querySelector('.bpi-hs-all');
        this.live = this.el.querySelector('.bpi-hs-live');
        this.clear = this.el.querySelector('.bpi-hs-clear');
        this.list.id = 'bpi-hs-list-' + (++searchId);
        this.input.setAttribute('aria-controls', this.list.id);
        this.sequence = 0; this.active = -1; this.rows = [];
        this.input.value = new URL(window.location.href).searchParams.get('search') || '';
        this.clear.hidden = !this.input.value;
        this.outside = ev => { if (!this.el.contains(ev.target)) this.closeResults(); };
        document.addEventListener('click', this.outside);
        return this._super(...arguments);
    },
    shopUrl() {
        const url = new URL(window.location.href);
        // Never retain product slugs, paging or unrelated tracking parameters.
        const list = /^\/shop(?:\/category\/[^/]+)?(?:\/page\/\d+)?\/?$/.test(url.pathname);
        const params = new URLSearchParams();
        for (const key of ['bpi_terms', 'min_price', 'max_price', 'attrib', 'order']) {
            for (const value of url.searchParams.getAll(key)) params.append(key, value);
        }
        url.pathname = list ? url.pathname.replace(/\/page\/\d+\/?$/, '') : '/shop';
        url.search = params.toString(); url.hash = '';
        return url;
    },
    queryUrl() { const url = this.shopUrl(); url.searchParams.set('search', this.input.value.trim()); return url; },
    _onSubmit(ev) {
        ev.preventDefault();
        if (this.input.value.trim()) window.location.assign(this.queryUrl().href);
    },
    _onInput() {
        this.closeResults(); // also clears stale keyboard targets immediately
        this.clear.hidden = !this.input.value;
        if (this.input.value.trim().length >= 2) this.timer = setTimeout(() => this.search(), 180);
    },
    _onFocus() {
        if (this.popup.hidden && this.input.value.trim().length >= 2) this._onInput();
    },
    _onClear() { this.input.value = ''; this._onInput(); this.input.focus(); },
    _onFocusOut(ev) { if (!this.el.contains(ev.relatedTarget)) this.closeResults(); },
    _onKeydown(ev) {
        if (ev.key === 'Escape') { this.closeResults(); return; }
        if (['ArrowDown', 'ArrowUp'].includes(ev.key) && this.rows.length && !this.popup.hidden) {
            ev.preventDefault();
            this.active = this.active < 0 ? (ev.key === 'ArrowDown' ? 0 : this.rows.length - 1) :
                (this.active + (ev.key === 'ArrowDown' ? 1 : -1) + this.rows.length) % this.rows.length;
            this.selectActive();
            this.list.children[this.active]?.scrollIntoView({block: 'nearest'});
        }
        if (ev.key === 'Enter' && !this.popup.hidden && this.active >= 0 && this.rows[this.active]) {
            ev.preventDefault(); window.location.assign(this.rows[this.active].url);
        }
    },
    closeResults() {
        this.sequence++; this.controller?.abort(); clearTimeout(this.timer); clearTimeout(this.deadline);
        this.popup.hidden = true; this.rows = []; this.active = -1;
        this.input.setAttribute('aria-expanded', 'false'); this.input.removeAttribute('aria-activedescendant');
        this.list.removeAttribute('aria-busy');
    },
    showStatus(message) {
        this.list.replaceChildren(); this.rows = []; this.active = -1;
        this.input.removeAttribute('aria-activedescendant');
        this.summary.textContent = message; this.live.textContent = message;
        this.popup.hidden = false; this.input.setAttribute('aria-expanded', 'true');
        this.all.href = this.queryUrl().href;
    },
    async search() {
        const query = this.input.value.trim(), seq = ++this.sequence;
        if (query.length < 2) return this.closeResults();
        this.controller?.abort(); const controller = new AbortController(); this.controller = controller;
        let timedOut = false;
        this.deadline = setTimeout(() => { timedOut = true; controller.abort(); }, 10000);
        const deadline = this.deadline;
        this.showStatus('Buscando en el catálogo…'); this.list.setAttribute('aria-busy', 'true');
        const url = this.shopUrl(), category = url.pathname.match(/\/category\/([^/]+)/);
        const options = {displayDescription: false, displayDetail: true, displayExtraDetail: false, displayExtraLink: false, displayImage: true, allowFuzzy: false,
            bpiTermIds: (url.searchParams.get('bpi_terms') || '').split(',').filter(Boolean).map(Number),
            category: category ? category[1] : false,
            min_price: Number(url.searchParams.get('min_price') || 0), max_price: Number(url.searchParams.get('max_price') || 0),
            attrib_values: url.searchParams.getAll('attrib').filter(x => /^\d+-\d+$/.test(x)).map(x => x.split('-').map(Number))};
        try {
            const response = await fetch('/website/snippet/autocomplete', {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json'}, signal: controller.signal,
                body: JSON.stringify({jsonrpc: '2.0', method: 'call', params: {search_type: 'products_only', term: query, order: 'name asc', limit: 8, max_nb_chars: 180, options}})});
            if (!response.ok) throw new Error('request');
            const json = await response.json();
            if (json.error || !Array.isArray(json.result?.results)) throw new Error('rpc');
            if (seq !== this.sequence || query !== this.input.value.trim()) return;
            this.rows = json.result.results.map(row => {
                const target = localUrl(text(row.website_url));
                const productUrl = target && new URL(target);
                if (productUrl) {
                    for (const [key, value] of this.queryUrl().searchParams) productUrl.searchParams.append(key, value);
                }
                return {name: text(row.name), sku: text(row.default_code), url: productUrl?.href || '', image: searchImage(row.image_url), price: text(row.detail)};
            }).filter(row => row.name && row.url);
            const count = Number(json.result.results_count) || this.rows.length;
            this.render(count);
        } catch (error) {
            if (seq === this.sequence && (timedOut || error.name !== 'AbortError')) {
                this.showStatus('No pudimos cargar las sugerencias. Pulsa Buscar para abrir la tienda.');
            }
        } finally {
            clearTimeout(deadline);
            if (seq === this.sequence) this.list.removeAttribute('aria-busy');
        }
    },
    selectActive() {
        [...this.list.children].forEach((row, index) => {
            row.classList.toggle('is-active', index === this.active);
            row.setAttribute('aria-selected', String(index === this.active));
        });
        if (this.active >= 0) this.input.setAttribute('aria-activedescendant', this.list.children[this.active].id);
    },
    render(count) {
        this.list.replaceChildren(); this.active = -1;
        this.summary.textContent = this.rows.length ? `${count} ${count === 1 ? 'producto' : 'productos'} · Mostrando ${this.rows.length}` : 'Sin resultados. Prueba otro nombre, SKU o aplicación.';
        this.live.textContent = this.summary.textContent;
        this.rows.forEach((row, index) => {
            const a = document.createElement('a'); a.href = row.url; a.className = 'bpi-hs-row';
            a.id = this.list.id + '-option-' + index; a.setAttribute('role', 'option'); a.setAttribute('aria-selected', 'false');
            const frame = document.createElement('span'); frame.className = 'bpi-hs-image'; frame.setAttribute('aria-hidden', 'true');
            const fallback = document.createElement('span'); fallback.textContent = 'B.'; frame.append(fallback);
            if (row.image) {
                const img = document.createElement('img'); img.alt = ''; img.width = 64; img.height = 64; img.decoding = 'async';
                img.addEventListener('error', () => img.remove(), {once: true}); img.src = row.image; frame.append(img);
            }
            const copy = document.createElement('span'); copy.className = 'bpi-hs-copy';
            const name = document.createElement('strong'); name.textContent = row.name; copy.append(name);
            if (row.sku) { const sku = document.createElement('small'); sku.textContent = 'SKU ' + row.sku; copy.append(sku); }
            const price = document.createElement('span'); price.className = 'bpi-hs-price'; price.textContent = row.price;
            a.append(frame, copy, price); this.list.append(a);
        });
    },
    destroy() {
        clearTimeout(this.timer); clearTimeout(this.deadline); this.sequence++; this.controller?.abort();
        document.removeEventListener('click', this.outside);
        // Server-rendered form remains usable even without JS.
        this._super(...arguments);
    },
});
publicWidget.registry.BpiTaxonomySearch = BpiTaxonomySearch;

publicWidget.registry.BpiTaxonomyFacets = publicWidget.Widget.extend({
    selector: '[data-bpi-facet-form]',
    events: {'submit': '_onSubmit'},
    _onSubmit() {
        this.el.querySelector('[name="bpi_terms"]').value = [...this.el.querySelectorAll('[data-bpi-term]:checked')].map(e => e.value).join(',');
    },
});
