/** @odoo-module **/
import publicWidget from "web.public.widget";

publicWidget.registry.BpiDescriptionVideo = publicWidget.Widget.extend({
    selector: ".bpi-description-layout",
    events: {"click .bpi-layout__play": "_playVideo"},
    _playVideo(event) {
        event.preventDefault();
        const button = event.currentTarget;
        const container = button.closest(".bpi-layout__social");
        const url = container && container.dataset.bpiVideoEmbed;
        // Defense in depth: markup editors cannot inject arbitrary iframe URLs.
        if (!url || !/^https:\/\/(www\.youtube-nocookie\.com\/embed\/[\w-]{11}|www\.tiktok\.com\/player\/v1\/\d{10,25})$/.test(url)) {
            return;
        }
        const frame = document.createElement("iframe");
        frame.src = url;
        frame.title = "Vídeo del producto";
        frame.setAttribute("allow", "encrypted-media; fullscreen; picture-in-picture");
        frame.setAttribute("allowfullscreen", "");
        frame.setAttribute("sandbox", "allow-scripts allow-same-origin allow-presentation");
        frame.setAttribute("referrerpolicy", "no-referrer");
        button.replaceWith(frame);
        frame.focus();
    },
});
