/** @odoo-module **/
import publicWidget from "web.public.widget";

publicWidget.registry.BpiDescriptionVideo = publicWidget.Widget.extend({
    selector: ".bpi-description-layout",
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
