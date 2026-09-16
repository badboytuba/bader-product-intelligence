/** @odoo-module **/
import publicWidget from 'web.public.widget';

publicWidget.registry.BpiTaxonomySearch = publicWidget.Widget.extend({
    selector: '[data-bpi-header-search]',
    start() {
        if (document.querySelector('.bpi-header-search')) return this._super(...arguments);
        this.root = document.createElement('li');
        this.root.className = 'bpi-header-search nav-item bader-brand';
        this.root.innerHTML = '<button type="button" class="bpi-hs-toggle" aria-label="Abrir búsqueda" aria-expanded="false"><i class="fa fa-search" aria-hidden="true"></i></button><form action="/shop" method="get"><input type="search" name="search" maxlength="200" autocomplete="off" placeholder="Producto, SKU o aplicación…" aria-label="Buscar productos" role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="bpi-hs-results"></form><div id="bpi-hs-results" class="bpi-hs-results" role="listbox" hidden></div><span class="sr-only" aria-live="polite"></span>';
        const cart = document.querySelector('li.o_wsale_my_cart');
        const nav = document.querySelector('header ul.navbar-nav');
        if (cart) cart.after(this.root); else if (nav) nav.append(this.root); else return this._super(...arguments);
        this.input = this.root.querySelector('input'); this.popup = this.root.querySelector('.bpi-hs-results');
        this.sequence = 0; this.active = -1; this.rows = [];
        this.root.querySelector('button').addEventListener('click', () => {
            const open = this.root.classList.toggle('is-open');
            this.root.querySelector('button').setAttribute('aria-expanded',String(open));
            if (open) this.input.focus(); else this.closeResults();
        });
        this.input.addEventListener('input', () => {
            this.sequence++; this.controller?.abort(); clearTimeout(this.timer);
            if (this.input.value.trim().length < 2) { this.closeResults(); return; }
            this.timer = setTimeout(() => this.search(), 150);
        });
        this.input.addEventListener('keydown', ev => {
            if (ev.key === 'Escape') { this.closeResults(); return; }
            if (['ArrowDown','ArrowUp'].includes(ev.key) && this.rows.length) {
                ev.preventDefault(); this.active = (this.active + (ev.key === 'ArrowDown' ? 1 : -1) + this.rows.length) % this.rows.length;
                this.render(); this.popup.children[this.active]?.scrollIntoView({block:'nearest'});
            }
            if (ev.key === 'Enter' && !this.popup.hidden && this.active >= 0 && this.rows[this.active]) {
                ev.preventDefault(); window.location.assign(this.rows[this.active].url);
            }
        });
        this.root.querySelector('form').addEventListener('submit', ev => {
            ev.preventDefault(); const q = this.input.value.trim(); if (!q) return;
            const url = this.shopUrl(); url.searchParams.set('search',q); window.location.assign(url.href);
        });
        this.outside = ev => { if (!this.root.contains(ev.target)) this.closeResults(); };
        document.addEventListener('click',this.outside);
        document.querySelectorAll('[data-bpi-facet-form]').forEach(form => {
            form.addEventListener('submit', () => { form.querySelector('[name="bpi_terms"]').value = [...form.querySelectorAll('[data-bpi-term]:checked')].map(e=>e.value).join(','); });
        });
        return this._super(...arguments);
    },
    shopUrl() {
        const url = new URL(window.location.href);
        if (!/^\/shop(?:\/category\/[^/]+)?(?:\/page\/\d+)?\/?$/.test(url.pathname)) { url.pathname='/shop'; url.search=''; }
        url.pathname=url.pathname.replace(/\/page\/\d+\/?$/,'');url.searchParams.delete('page');url.hash='';return url;
    },
    text(html) { return new DOMParser().parseFromString(String(html || ''),'text/html').body.textContent || ''; },
    localUrl(value) { if (!value) return ''; try { const u=new URL(value,window.location.origin); return u.origin===window.location.origin && u.protocol===window.location.protocol ? u.href : ''; } catch (_) { return ''; } },
    closeResults() {
        this.sequence++; this.controller?.abort();clearTimeout(this.timer);
        this.popup.hidden=true;this.input.setAttribute('aria-expanded','false');this.input.removeAttribute('aria-activedescendant');this.active=-1;
    },
    async search() {
        const query=this.input.value.trim(), seq=++this.sequence;
        this.controller?.abort();this.controller=new AbortController();
        this.popup.textContent='Buscando…';this.popup.hidden=false;this.input.setAttribute('aria-expanded','true');
        const url=this.shopUrl(), category=url.pathname.match(/\/category\/([^/]+)/);
        const options={displayDescription:false,displayDetail:true,displayExtraDetail:false,displayExtraLink:false,displayImage:true,allowFuzzy:false,
            bpiTermIds:(url.searchParams.get('bpi_terms') || '').split(',').filter(Boolean).map(Number),
            category:category ? category[1] : false,
            min_price:Number(url.searchParams.get('min_price') || 0),max_price:Number(url.searchParams.get('max_price') || 0),
            attrib_values:url.searchParams.getAll('attrib').filter(x=>/^\d+-\d+$/.test(x)).map(x=>x.split('-').map(Number))};
        try {
            const response=await fetch('/website/snippet/autocomplete',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},signal:this.controller.signal,
                body:JSON.stringify({jsonrpc:'2.0',method:'call',params:{search_type:'products_only',term:query,order:'name asc',limit:8,max_nb_chars:120,options}})});
            if(!response.ok) throw new Error('request');const json=await response.json();if(json.error) throw new Error('rpc');
            if(seq!==this.sequence || query!==this.input.value.trim()) return;
            this.rows=(json.result?.results || []).map(r=>{
                const img=new DOMParser().parseFromString(String(r.image_url || ''),'text/html').querySelector('img');
                return {name:this.text(r.name),sku:this.text(r.default_code),url:this.localUrl(this.text(r.website_url)),image:this.localUrl(img?.getAttribute('src') || ''),price:this.text(r.detail)};
            }).filter(r=>r.name && r.url);
            this.active=-1;this.render();
        } catch(error) {
            if(seq===this.sequence && error.name!=='AbortError') {this.rows=[];this.popup.textContent='No se pudo cargar la búsqueda. Pulsa Enter para ver la tienda.';}
        }
    },
    render() {
        this.popup.replaceChildren();this.popup.hidden=false;this.input.setAttribute('aria-expanded','true');
        if(!this.rows.length) {this.popup.textContent='No encontramos resultados. Prueba otro término.';return;}
        this.rows.forEach((row,index)=>{
            const a=document.createElement('a');a.href=row.url;a.className='bpi-hs-row'+(index===this.active?' is-active':'');a.id='bpi-hs-option-'+index;a.setAttribute('role','option');a.setAttribute('aria-selected',String(index===this.active));
            if(row.image){const img=document.createElement('img');img.src=row.image;img.alt='';a.append(img);}
            const copy=document.createElement('span'),name=document.createElement('strong'),meta=document.createElement('small');name.textContent=row.name;meta.textContent=[row.sku,row.price].filter(Boolean).join(' · ');copy.append(name,meta);a.append(copy);this.popup.append(a);
        });
        if(this.active>=0)this.input.setAttribute('aria-activedescendant','bpi-hs-option-'+this.active);
        this.root.querySelector('[aria-live]').textContent=this.rows.length+' sugerencias';
    },
    destroy() {clearTimeout(this.timer);this.controller?.abort();document.removeEventListener('click',this.outside);this.root?.remove();this._super(...arguments);},
});
