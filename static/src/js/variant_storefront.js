/** @odoo-module **/
import publicWidget from 'web.public.widget';
import 'website_sale.website_sale';

publicWidget.registry.WebsiteSale.include({
    _bpiVariantRoot() { return this.el.matches('[data-bpi-variant-workspace]') ? this.el : this.el.querySelector('[data-bpi-variant-workspace]'); },
    start() {
        // SSR already establishes a valid history entry. A customer's first
        // click can beat the startup RPC; it must not replace that entry.
        const initialRoot = this._bpiVariantRoot();
        const initialUrl = new URL(window.location.href);
        this._bpiVariantInitialized = Boolean(initialRoot &&
            (initialUrl.searchParams.has('variant') || !initialUrl.hash));
        const result = this._super.apply(this, arguments);
        if (this._bpiVariantRoot()) {
            this._bpiVariantPop = () => window.location.reload();
            window.addEventListener('popstate', this._bpiVariantPop);
        }
        return result;
    },
    destroy() {
        if (this._bpiVariantPop) window.removeEventListener('popstate', this._bpiVariantPop);
        return this._super.apply(this, arguments);
    },
    _getCombinationInfo(ev) {
        const pending = this._super.apply(this, arguments);
        const root = this._bpiVariantRoot(), $parent = $(ev.target).closest('.js_main_product');
        if (!root || !$parent.length || ev.target.classList.contains('variant_custom_value')) return pending;
        const token = root.dataset.bpiVariantRequest;
        return Promise.resolve(pending).then(result => {
            if (root.isConnected && root.dataset.bpiVariantRequest === token && root.hasAttribute('aria-busy')) {
                this._bpiVariantFailure(root, $parent);
            }
            return result;
        }, () => {
            if (root.isConnected && root.dataset.bpiVariantRequest === token) this._bpiVariantFailure(root, $parent);
        });
    },
    _bpiVariantFailure(root, $parent) {
        root.removeAttribute('aria-busy');
        root.dataset.bpiVariantError = '1';
        this._toggleDisable($parent, false);
        root.querySelector('.bpi-variant-status')?.remove();
        const message = document.createElement('div');
        message.className = 'bpi-variant-status alert alert-warning';
        message.setAttribute('role', 'alert');
        message.textContent = 'No se pudo cargar esta edición. No añadiremos otra variante a la cesta. ';
        const retry = document.createElement('button');
        retry.type = 'button'; retry.className = 'btn btn-outline-dark'; retry.textContent = 'Reintentar';
        retry.addEventListener('click', () => this.triggerVariantChange($parent));
        message.appendChild(retry); $parent[0].prepend(message);
    },
    _onClickAdd(ev) {
        const root = this._bpiVariantRoot();
        if (root && (root.hasAttribute('aria-busy') || root.dataset.bpiVariantError)) {
            ev.preventDefault(); ev.stopImmediatePropagation(); return Promise.resolve();
        }
        return this._super.apply(this, arguments);
    },
    _onClickConfirmOrder(ev) {
        // Native implicit form submission (Enter) does not use _onClickAdd.
        // Preserve checkout/search handlers outside this main-product form.
        const root = this._bpiVariantRoot(), form = ev.target;
        if (root && root.contains(form) && form.matches('form') && form.querySelector('input.product_id') &&
                (root.hasAttribute('aria-busy') || root.dataset.bpiVariantError)) {
            ev.preventDefault(); ev.stopImmediatePropagation(); return;
        }
        return this._super.apply(this, arguments);
    },
    _checkExclusions($parent, combination) {
        if (this._bpiVariantRoot() && $parent.hasClass('js_main_product')) {
            const selected = this.getSelectedVariantValues($parent).map(Number).sort((a,b)=>a-b);
            if (JSON.stringify(selected) !== JSON.stringify([...combination].map(Number).sort((a,b)=>a-b))) return;
        }
        return this._super.apply(this, arguments);
    },
    _applyHashFromSearch() {
        // An explicit valid query variant is server-rendered and takes priority
        // over a stale hash copied from another edition. Legacy hash-only URLs
        // keep the unmodified native behavior.
        const root = this._bpiVariantRoot(), url = new URL(window.location.href);
        if (root && url.searchParams.get('variant') === root.dataset.bpiSelectedVariant && url.hash) {
            url.hash = ''; window.history.replaceState(window.history.state, '', url);
        }
        return this._super.apply(this, arguments);
    },
    _setUrlHash($parent) {
        if (!this._bpiVariantRoot()) return this._super.apply(this, arguments);
        this._bpiVariantHash = '#attr=' + $parent.find('input.js_variant_change:checked, select.js_variant_change option:selected')
            .toArray().map(element => element.dataset.value_id).filter(Boolean).join(',');
    },
    _getOptionalCombinationInfoParam($parent) {
        const params = this._super.apply(this, arguments), root = this._bpiVariantRoot();
        if (!root || !$parent.hasClass('js_main_product')) return params;
        root.dataset.bpiVariantRequest = String((this._bpiVariantSequence || 0) + 1);
        this._bpiVariantSequence = Number(root.dataset.bpiVariantRequest);
        return {...params, bpi_variant_token:root.dataset.bpiVariantRequest};
    },
    onChangeVariant(ev) {
        const root = this._bpiVariantRoot();
        if (root && !ev.target.classList.contains('variant_custom_value') && ev.target.closest('.js_main_product')) {
            root.dataset.bpiVariantRequest = '';
            delete root.dataset.bpiVariantError;
            root.querySelector('.bpi-variant-status')?.remove();
            root.setAttribute('aria-busy','true');
            this._toggleDisable($(ev.target).closest('.js_main_product'), false);
            root.querySelectorAll('video').forEach(video=>video.pause());
            root.querySelectorAll('.bpi-variant-editorial iframe').forEach(frame=>frame.remove());
            const galleryPlayers = root.querySelectorAll('.o_wsale_product_images iframe');
            if (galleryPlayers.length) {
                // Removing the browsing context stops cross-origin audio too.
                // Force the next winning native callback to rebuild the carousel,
                // including retry or A→B→A where the final SKU is unchanged.
                galleryPlayers.forEach(frame=>frame.remove());
                this.last_product_id = false;
            }
            root.querySelectorAll('.bpi-variant-short,.bpi-variant-editorial,.o_wsale_product_images,#product_details .product_price').forEach(node=>{node.style.visibility='hidden';});
        }
        return this._super.apply(this, arguments);
    },
    _onChangeCombination(ev, $parent, combination) {
        const root = this._bpiVariantRoot(), data = combination.bpi_variant_content;
        const main = root && $parent.hasClass('js_main_product');
        // Guard BEFORE native callbacks: a dropped response must not update
        // price, product_id, availability or the native carousel either.
        if (main && (!data || data.token !== root.dataset.bpiVariantRequest || Number(root.dataset.bpiVariantWorkspace) !== data.productId)) return;
        this._super.apply(this, arguments);
        if (!main) return;
        const short = root.querySelector('.bpi-variant-short'), editorial = root.querySelector('.bpi-variant-editorial');
        if (short) { short.innerHTML = data.short; short.style.visibility=''; }
        if (editorial) { editorial.innerHTML = data.html; editorial.style.visibility=''; }
        const heading = root.querySelector('.bpi-variant-name');
        if (heading && data.name) heading.textContent = data.name;
        root.querySelectorAll('.o_wsale_product_images,#product_details .product_price').forEach(node=>{node.style.visibility='';});
        root.removeAttribute('aria-busy');
        delete root.dataset.bpiVariantError;
        root.querySelector('.bpi-variant-status')?.remove();
        if (!data.variantId) return;
        const url = new URL(data.url, window.location.origin); url.hash = this._bpiVariantHash || '';
        if (url.origin !== window.location.origin) return;
        const method = this._bpiVariantInitialized && root.dataset.bpiSelectedVariant !== String(data.variantId) ? 'pushState' : 'replaceState';
        window.history[method](window.history.state, '', url);
        this._bpiVariantInitialized = true; root.dataset.bpiSelectedVariant = String(data.variantId);
        document.title = data.title;
        for (const [attribute,key,value] of [['name','description',data.description],['name','keywords',data.keywords],['property','og:title',data.title],['property','og:description',data.description],['property','og:url',url.origin+url.pathname+url.search],['property','og:image',data.image ? new URL(data.image,url.origin).href : ''],['name','twitter:title',data.title],['name','twitter:description',data.description],['name','twitter:image',data.image ? new URL(data.image,url.origin).href : '']]) {
            let meta = document.head.querySelector(`meta[${attribute}="${key}"]`);
            if (!meta) {meta=document.createElement('meta'); meta.setAttribute(attribute,key); document.head.appendChild(meta);}
            meta.content = value;
        }
        const canonical = document.head.querySelector('link[rel="canonical"]');
        if (canonical) canonical.href=url.origin+url.pathname+url.search;
        const structured = document.head.querySelector('[data-bpi-product-group]');
        if (structured) structured.textContent=data.jsonld;
        // Native public widgets in replaced content (video click handler).
        this.trigger_up('widgets_start_request', {$target:$(editorial)});
    },
});
