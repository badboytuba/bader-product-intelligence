/** @odoo-module **/
import publicWidget from "web.public.widget";
import "website_sale.website_sale";

// Native DropMisordered resolves AFTER its DOM callback. Guard that callback
// for opt-in main products, including those without a variant-specific layout.
publicWidget.registry.WebsiteSale.include({
    _bpiPremiumProduct($parent) {
        const product = $parent.closest('.bpi-product-premium')[0];
        return product && $parent.hasClass('js_main_product') &&
            Number($parent.find('.product_template_id').val()) === Number(product.dataset.bpiStorefrontProduct) ? product : null;
    },
    _getOptionalCombinationInfoParam($parent) {
        const params = this._super(...arguments), product = this._bpiPremiumProduct($parent);
        if (!product) return params;
        this._bpiStorefrontSequence = (this._bpiStorefrontSequence || 0) + 1;
        product.dataset.bpiStorefrontToken = String(this._bpiStorefrontSequence);
        return {...params, bpi_storefront_token: product.dataset.bpiStorefrontToken};
    },
    onChangeVariant(event) {
        const product = this._bpiPremiumProduct($(event.target).closest('.js_main_product'));
        if (product) product.dataset.bpiStorefrontToken = '';
        return this._super(...arguments);
    },
    _onChangeCombination(event, $parent, combination) {
        const product = this._bpiPremiumProduct($parent), echo = combination.bpi_storefront;
        if (product && echo && Number(product.dataset.bpiStorefrontProduct) === echo.productTemplateId &&
                echo.token !== product.dataset.bpiStorefrontToken) return;
        return this._super(...arguments);
    },
});

// Enhance the native widget itself: Odoo restarts it after variant replacement.
// No new fetch, image payload or parallel carousel state.
const NativeCarousel = publicWidget.registry.websiteSaleCarouselProduct;
NativeCarousel.include({
    events: Object.assign({}, NativeCarousel.prototype.events, {
        "keydown .carousel-indicators [data-bs-slide-to]": "_bpiIndicatorKeydown",
    }),
    _bpiIsPremium() {
        return !!this.el.closest(".bpi-product-premium");
    },
    async start() {
        await this._super(...arguments);
        if (this._bpiIsPremium()) {
            this.el.setAttribute("aria-label", "Galería del producto");
            this.el.querySelectorAll(".carousel-control-prev, .carousel-control-next").forEach(control => {
                control.setAttribute("aria-label", control.classList.contains("carousel-control-prev") ? "Imagen anterior" : "Imagen siguiente");
            });
            this._bpiSyncIndicators();
            this._bpiGalleryColumn = this.el.closest('.o_wsale_product_images');
            this._bpiHeader = document.querySelector('#top');
            this._bpiGalleryResize = new ResizeObserver(() => this._bpiUpdateGalleryFollow());
            this._bpiGalleryResize.observe(this.el);
            if (this._bpiHeader) this._bpiGalleryResize.observe(this._bpiHeader);
            this._bpiWindowResize = () => this._bpiUpdateGalleryFollow();
            window.addEventListener('resize', this._bpiWindowResize);
            this._bpiUpdateGalleryFollow();
        }
    },
    _bpiUpdateGalleryFollow() {
        const column = this._bpiGalleryColumn;
        if (!column || !this.el.isConnected) return;
        // CSS sticky is bounded by the native purchasing row. Never pin a
        // card taller than the available viewport or animate page scrolling.
        const header = this._bpiHeader;
        const offset = Math.max(0, header ? header.getBoundingClientRect().bottom : 0) + 16;
        const enabled = window.innerWidth >= 992 && this.el.offsetHeight + offset + 16 <= window.innerHeight;
        column.style.setProperty('--bpi-gallery-top', offset + 'px');
        column.classList.toggle('bpi-gallery-follow', enabled);
    },
    destroy() {
        this._bpiGalleryResize?.disconnect();
        if (this._bpiWindowResize) window.removeEventListener('resize', this._bpiWindowResize);
        this._bpiGalleryColumn?.classList.remove('bpi-gallery-follow');
        this._bpiGalleryColumn?.style.removeProperty('--bpi-gallery-top');
        return this._super(...arguments);
    },
    _updateCarouselPosition() {
        if (!this._bpiIsPremium()) return this._super(...arguments);
        this.el.style.removeProperty("top");
        this._bpiUpdateGalleryFollow();
    },
    _updateJustifyContent() {
        if (!this._bpiIsPremium()) return this._super(...arguments);
    },
    _onMouseWheel() {
        if (!this._bpiIsPremium()) return this._super(...arguments);
        // Native scrolling of the rail/page, not accidental slide changes.
    },
    _onSlideCarouselProduct(event) {
        if (!this._bpiIsPremium()) return this._super(...arguments);
        this._bpiSyncIndicators(event);
    },
    _bpiSyncIndicators(event) {
        const rail = this.el.querySelector(".carousel-indicators");
        if (!rail) return;
        const items = [...rail.querySelectorAll("[data-bs-slide-to]")];
        const slides = [...this.el.querySelectorAll(".carousel-inner > .carousel-item")];
        const index = event && event.relatedTarget ? slides.indexOf(event.relatedTarget) : items.findIndex(item => item.classList.contains("active"));
        const current = Math.max(0, index);
        rail.setAttribute("aria-label", "Seleccionar imagen o vídeo");
        items.forEach((item, i) => {
            item.setAttribute("role", "button");
            item.setAttribute("tabindex", i === current ? "0" : "-1");
            item.setAttribute("aria-current", i === current ? "true" : "false");
            const image = item.querySelector("img");
            const kind = item.querySelector(".o_product_video_thumb") ? "Vídeo" : "Imagen";
            item.setAttribute("aria-label", `${kind} ${i + 1} de ${items.length}${image && image.alt ? ': ' + image.alt : ''}`);
        });
        if (items[current]) {
            const item = items[current].getBoundingClientRect(), box = rail.getBoundingClientRect();
            // Scroll only the thumbnails, never the product page or #wrapwrap.
            if (getComputedStyle(rail).flexDirection === "column") rail.scrollTop += item.top - box.top - (box.height - item.height) / 2;
            else rail.scrollLeft += item.left - box.left - (box.width - item.width) / 2;
        }
    },
    _bpiIndicatorKeydown(event) {
        if (!this._bpiIsPremium()) return;
        const keys = ["Enter", " ", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"];
        if (!keys.includes(event.key)) return;
        event.preventDefault();
        const items = [...this.el.querySelectorAll(".carousel-indicators [data-bs-slide-to]")];
        const current = items.indexOf(event.currentTarget);
        let next = current;
        if (event.key === "Home") next = 0;
        else if (event.key === "End") next = items.length - 1;
        else if (["ArrowRight", "ArrowDown"].includes(event.key)) next = (current + 1) % items.length;
        else if (["ArrowLeft", "ArrowUp"].includes(event.key)) next = (current + items.length - 1) % items.length;
        if (items[next]) {
            items[next].focus({preventScroll: true});
            items[next].click();
        }
    },
});
