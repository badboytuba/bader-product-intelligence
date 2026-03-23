# -*- coding: utf-8 -*-

from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request


class BaderProductIntelligenceController(http.Controller):
    def _ensure_manager(self):
        if not request.env.user.has_group("base.group_system"):
            raise AccessError("Producto Intelligence requiere permisos de administrador.")

    def _product(self, product_tmpl_id):
        self._ensure_manager()
        product = request.env["product.template"].browse(int(product_tmpl_id)).exists()
        if not product:
            raise MissingError("Producto no encontrado.")
        return product

    def _competitor(self, competitor_id):
        self._ensure_manager()
        competitor = request.env["bpi.product.competitor"].browse(int(competitor_id)).exists()
        if not competitor:
            raise MissingError("Competidor no encontrado.")
        return competitor

    def _image(self, image_id):
        self._ensure_manager()
        image = request.env["bpi.product.image"].browse(int(image_id)).exists()
        if not image:
            raise MissingError("Imagen no encontrada.")
        return image

    @http.route("/bader_product_intelligence/dashboard", type="json", auth="user")
    def dashboard(self, tab="all", search="", page=1, limit=40, **kwargs):
        self._ensure_manager()
        return request.env["bpi.service"].dashboard_payload(tab=tab, search=search, page=page, limit=limit)

    @http.route("/bader_product_intelligence/sync_catalog", type="json", auth="user")
    def sync_catalog(self, tab="all", search="", page=1, limit=40, **kwargs):
        self._ensure_manager()
        payload = request.env["bpi.service"].sync_catalog(tab=tab, search=search, page=page, limit=limit)
        return {"success": True, **payload}

    @http.route("/bader_product_intelligence/update_exchange_rate", type="json", auth="user")
    def update_exchange_rate(self, exchange_rate=1650, **kwargs):
        self._ensure_manager()
        return request.env["bpi.service"].update_exchange_rate(exchange_rate)

    @http.route("/bader_product_intelligence/data", type="json", auth="user")
    def data(self, product_tmpl_id, **kwargs):
        return self._product(product_tmpl_id).bpi_build_payload()

    @http.route("/bader_product_intelligence/update_product", type="json", auth="user")
    def update_product(self, product_tmpl_id, values=None, **kwargs):
        product = self._product(product_tmpl_id)
        payload = request.env["bpi.service"].update_product(product, values or {})
        return {"success": True, **payload}

    @http.route("/bader_product_intelligence/generate_content", type="json", auth="user")
    def generate_content(self, product_tmpl_id, tone="profesional", audience="clinicas", **kwargs):
        product = self._product(product_tmpl_id)
        return {"success": True, **request.env["bpi.service"].generate_content(product, tone=tone, audience=audience)}

    @http.route("/bader_product_intelligence/save_content", type="json", auth="user")
    def save_content(self, product_tmpl_id, values=None, **kwargs):
        product = self._product(product_tmpl_id)
        payload = request.env["bpi.service"].save_content(product, values or {})
        return {"success": True, **payload}

    @http.route("/bader_product_intelligence/generate_faq", type="json", auth="user")
    def generate_faq(self, product_tmpl_id, audience="clinicas", **kwargs):
        product = self._product(product_tmpl_id)
        return {"success": True, **request.env["bpi.service"].generate_faq(product, audience=audience)}

    @http.route("/bader_product_intelligence/save_category", type="json", auth="user")
    def save_category(self, product_tmpl_id, values=None, **kwargs):
        product = self._product(product_tmpl_id)
        payload = request.env["bpi.service"].save_category(product, values or {})
        return {"success": True, **payload}

    @http.route("/bader_product_intelligence/reclassify_category", type="json", auth="user")
    def reclassify_category(self, product_tmpl_id, **kwargs):
        product = self._product(product_tmpl_id)
        payload = request.env["bpi.service"].reclassify_category(product)
        return {"success": True, **payload}

    @http.route("/bader_product_intelligence/analyze_seo", type="json", auth="user")
    def analyze_seo(self, product_tmpl_id, target_audience="clinicas", **kwargs):
        product = self._product(product_tmpl_id)
        seo_data = request.env["bpi.service"].analyze_seo(product, target_audience)
        return {"success": True, "seoData": seo_data}

    @http.route("/bader_product_intelligence/save_seo", type="json", auth="user")
    def save_seo(self, product_tmpl_id, seo_data=None, **kwargs):
        product = self._product(product_tmpl_id)
        payload = request.env["bpi.service"].save_seo_payload(product, seo_data or {})
        return {"success": True, "seoData": payload}

    @http.route("/bader_product_intelligence/save_video", type="json", auth="user")
    def save_video(self, product_tmpl_id, video_url="", **kwargs):
        product = self._product(product_tmpl_id)
        product.write({"bpi_video_url": video_url or False})
        return {"success": True, "videoUrl": product.bpi_video_url or ""}

    @http.route("/bader_product_intelligence/generate_image", type="json", auth="user")
    def generate_image(self, product_tmpl_id, prompt="", reference_tokens=None, style="professional", use_pro=False, uploaded_ref="", **kwargs):
        product = self._product(product_tmpl_id)
        payload = request.env["bpi.service"].generate_image(
            product,
            prompt,
            reference_tokens=reference_tokens or [],
            style=style,
            use_pro=bool(use_pro),
            uploaded_ref=uploaded_ref or "",
        )
        return {"success": True, **payload}

    @http.route("/bader_product_intelligence/approve_image", type="json", auth="user")
    def approve_image(self, product_tmpl_id, image_data_url="", prompt="", **kwargs):
        product = self._product(product_tmpl_id)
        image = request.env["bpi.service"].save_generated_image(product, image_data_url, prompt)
        return {"success": True, "image": image}

    @http.route("/bader_product_intelligence/add_image_url", type="json", auth="user")
    def add_image_url(self, product_tmpl_id, image_url="", **kwargs):
        product = self._product(product_tmpl_id)
        image = request.env["bpi.service"].add_image_from_url(product, image_url)
        return {"success": True, "image": image}

    @http.route("/bader_product_intelligence/delete_image", type="json", auth="user")
    def delete_image(self, image_id, **kwargs):
        image = self._image(image_id)
        request.env["bpi.service"].delete_image(image)
        return {"success": True}

    @http.route("/bader_product_intelligence/discover_competitors", type="json", auth="user")
    def discover_competitors(self, product_tmpl_id, limit=10, **kwargs):
        product = self._product(product_tmpl_id)
        return request.env["bpi.service"].discover_competitors(product, int(limit or 10))

    @http.route("/bader_product_intelligence/add_competitor", type="json", auth="user")
    def add_competitor(self, product_tmpl_id, competitor_name="", competitor_url="", **kwargs):
        product = self._product(product_tmpl_id)
        competitor = request.env["bpi.service"].add_competitor(product, competitor_name, competitor_url)
        return {"success": True, "competitor": competitor}

    @http.route("/bader_product_intelligence/scrape_competitor", type="json", auth="user")
    def scrape_competitor(self, competitor_id, **kwargs):
        competitor = self._competitor(competitor_id)
        payload = request.env["bpi.service"].scrape_competitor(competitor)
        return {"success": True, "competitor": payload}

    @http.route("/bader_product_intelligence/analyze_competitor", type="json", auth="user")
    def analyze_competitor(self, competitor_id, **kwargs):
        competitor = self._competitor(competitor_id)
        payload = request.env["bpi.service"].analyze_competitor(competitor)
        return {"success": True, "competitor": payload}

    @http.route("/bader_product_intelligence/delete_competitor", type="json", auth="user")
    def delete_competitor(self, competitor_id, **kwargs):
        competitor = self._competitor(competitor_id)
        competitor.unlink()
        return {"success": True}

    @http.route("/bader_product_intelligence/generate_strategy", type="json", auth="user")
    def generate_strategy(self, product_tmpl_id, **kwargs):
        product = self._product(product_tmpl_id)
        strategy = request.env["bpi.service"].generate_competitive_strategy(product)
        return {"success": True, "strategy": strategy}

    @http.route("/bader_product_intelligence/chat", type="json", auth="user")
    def chat(self, product_tmpl_id, message="", session_id=False, **kwargs):
        product = self._product(product_tmpl_id)
        return request.env["bpi.service"].chat_with_product(product, message, session_key=session_id)
