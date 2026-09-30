/** @odoo-module **/
import publicWidget from "web.public.widget";
import "website_sale.website_sale";

// Reuse Odoo's combination request. Its DropMisordered wraps a promise AFTER
// the native DOM callbacks, so a per-request echo also guards those callbacks.
// Hash attributes, pricing and availability continue to be owned by Odoo.
publicWidget.registry.WebsiteSale.include({
    _getOptionalCombinationInfoParam($parent) {
        const params = this._super.apply(this, arguments);
        const host = this.el.querySelector('[data-bpi-variant-layout]');
        if (!host || !$parent.hasClass('js_main_product') || Number($parent.find('.product_template_id').val()) !== Number(host.dataset.bpiVariantLayout)) return params;
        this._bpiDescriptionSequence = (this._bpiDescriptionSequence || 0) + 1;
        const token = String(this._bpiDescriptionSequence);
        host.dataset.bpiRequestToken = token;
        return {...params, bpi_description_token: token};
    },
    onChangeVariant(ev) {
        const host = this.el.querySelector('[data-bpi-variant-layout]');
        const parent = ev.target.closest('.js_main_product');
        if (host && parent && Number(parent.querySelector('.product_template_id')?.value) === Number(host.dataset.bpiVariantLayout)) {
            host.querySelectorAll('[data-bpi-variant-specific]').forEach(node => {
                node.hidden = true;
                node.querySelectorAll('video').forEach(video => video.pause());
                // Stop external playback before hiding an obsolete edition.
                node.querySelectorAll('iframe').forEach(frame => frame.remove());
            });
            host.dataset.bpiPending = '1';
            host.dataset.bpiRequestToken = ''; // Invalidate during native throttle, too.
        }
        return this._super.apply(this, arguments);
    },
    _onChangeCombination(ev, $parent, combination) {
        const host = this.el.querySelector('[data-bpi-variant-layout]');
        const data = combination.bpi_description;
        if (host && $parent.hasClass('js_main_product') && data && Number(host.dataset.bpiVariantLayout) === data.productTemplateId &&
            (!data.token || data.token !== host.dataset.bpiRequestToken)) return;
        this._super.apply(this, arguments);
        if (!host || !$parent.hasClass('js_main_product') || !data ||
            Number(host.dataset.bpiVariantLayout) !== data.productTemplateId || typeof data.html !== 'string') return;
        const key = `${data.variantId}:${data.revision}`;
        if (host.dataset.bpiSelection !== key || host.dataset.bpiPending) {
            // Only trusted server QWeb HTML; no authored embed or client URL.
            host.innerHTML = data.html;
            host.dataset.bpiSelection = key;
        }
        delete host.dataset.bpiPending;
    },
});

publicWidget.registry.BpiDescriptionVideo = publicWidget.Widget.extend({
    selector: ".bpi-description-host",
    events: {"click .bpi-layout__play": "_playVideo"},
    _playVideo(event) {
        const button = event.currentTarget;
        const container = button.closest(".bpi-layout__social");
        const url = container && container.dataset.bpiVideoEmbed;
        // Defense in depth: markup editors cannot inject arbitrary iframe URLs.
        if (!url || !/^https:\/\/(www\.youtube-nocookie\.com\/embed\/[\w-]{11}|www\.tiktok\.com\/player\/v1\/\d{10,25})$/.test(url)) {
            return;
        }
        // Non-embeddable networks keep their ordinary external-link behavior.
        event.preventDefault();
        const frame = document.createElement("iframe");
        // Playback requested by the visitor, never on initial page load.
        frame.src = url + "?autoplay=1&playsinline=1";
        frame.title = "Vídeo del producto";
        frame.setAttribute("allow", "autoplay; encrypted-media; fullscreen; picture-in-picture");
        frame.setAttribute("allowfullscreen", "");
        frame.setAttribute("sandbox", "allow-scripts allow-same-origin allow-presentation");
        frame.setAttribute("referrerpolicy", "strict-origin-when-cross-origin");
        button.replaceWith(frame);
        frame.setAttribute("tabindex", "0");
        frame.focus();
    },
});
