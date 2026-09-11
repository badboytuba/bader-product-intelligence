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
        return request.env["bpi.service"]._meli_product(product_tmpl_id)

    def _competitor(self, product, competitor_id):
        self._ensure_manager()
        try:
            record_id = int(competitor_id)
        except (TypeError, ValueError) as error:
            raise MissingError("Competidor no encontrado.") from error
        competitor = request.env["bpi.product.competitor"].browse(record_id).exists()
        if not competitor or competitor.product_tmpl_id != product:
            raise MissingError("Competidor no encontrado.")
        return competitor

    def _variant(self, product, product_variant_id):
        self._ensure_manager()
        try:
            variant_id = int(product_variant_id)
        except (TypeError, ValueError) as error:
            raise MissingError("Variante no encontrada.") from error
        variant = request.env["product.product"].with_context(active_test=False).browse(variant_id).exists()
        if not variant or variant.product_tmpl_id != product:
            raise MissingError("Variante no encontrada.")
        return variant

    def _image(self, product, image_token):
        self._ensure_manager()
        token = image_token if isinstance(image_token, str) else ""
        token_parts = token.split(":")
        if len(token_parts) != 2 or token_parts[0] != "bpi" or not token_parts[1].isdigit() or int(token_parts[1]) <= 0:
            raise MissingError("Imagen no encontrada.")
        image = request.env["bpi.product.image"].browse(int(token_parts[1])).exists()
        if not image or image.product_tmpl_id != product:
            raise MissingError("Imagen no encontrada.")
        return image

    def _ai_job(self, job_id):
        self._ensure_manager()
        job = request.env["bpi.ai.job"].sudo().browse(int(job_id)).exists()
        if not job:
            raise MissingError("Trabajo IA no encontrado.")
        return job

    @http.route("/bader_product_intelligence/dashboard", type="json", auth="user")
    def dashboard(self, tab="all", search="", page=1, limit=40, category_id=False, quality_filter=False, sort_key="catalog", meli_account_id=False, meli_filter=False, **kwargs):
        self._ensure_manager()
        return request.env["bpi.service"].dashboard_payload(
            tab=tab, search=search, page=page, limit=limit, category_id=category_id, quality_filter=quality_filter,
            sort_key=sort_key, meli_account_id=meli_account_id, meli_filter=meli_filter,
        )

    @http.route("/bader_product_intelligence/dashboard_overview", type="json", auth="user")
    def dashboard_overview(self, category_id=False, meli_account_id=False, **kwargs):
        self._ensure_manager()
        return request.env["bpi.service"].dashboard_overview(category_id=category_id, meli_account_id=meli_account_id)

    @http.route("/bader_product_intelligence/sync_catalog", type="json", auth="user")
    def sync_catalog(self, tab="all", search="", page=1, limit=40, category_id=False, quality_filter=False, sort_key="catalog", meli_account_id=False, meli_filter=False, **kwargs):
        self._ensure_manager()
        payload = request.env["bpi.service"].sync_catalog(
            tab=tab, search=search, page=page, limit=limit, category_id=category_id, quality_filter=quality_filter,
            sort_key=sort_key, meli_account_id=meli_account_id, meli_filter=meli_filter,
        )
        return {"success": True, **payload}

    @http.route("/bader_product_intelligence/update_exchange_rate", type="json", auth="user")
    def update_exchange_rate(self, exchange_rate=1650, **kwargs):
        self._ensure_manager()
        return request.env["bpi.service"].update_exchange_rate(exchange_rate)

    @http.route("/bader_product_intelligence/data", type="json", auth="user")
    def data(self, product_tmpl_id, **kwargs):
        return self._product(product_tmpl_id).bpi_build_payload()

    @http.route("/bader_product_intelligence/meli/product_status", type="json", auth="user")
    def meli_product_status(self, product_tmpl_id, meli_account_id=False, **kwargs):
        self._ensure_manager()
        return request.env["bpi.service"].meli_detail(product_tmpl_id, account_id=meli_account_id)

    @http.route("/bader_product_intelligence/meli/refresh", type="json", auth="user")
    def meli_refresh(self, product_tmpl_id, meli_account_id=False, **kwargs):
        self._ensure_manager()
        return request.env["bpi.service"].meli_request_refresh(product_tmpl_id, account_id=meli_account_id)

    @http.route("/bader_product_intelligence/meli/refresh_status", type="json", auth="user")
    def meli_refresh_status(self, job_id, **kwargs):
        self._ensure_manager()
        return request.env["bpi.service"].meli_refresh_status(job_id)

    @http.route("/bader_product_intelligence/update_product", type="json", auth="user")
    def update_product(self, product_tmpl_id, values=None, **kwargs):
        product = self._product(product_tmpl_id)
        payload = request.env["bpi.service"].update_product(product, values or {})
        return {"success": True, **payload}

    @http.route("/bader_product_intelligence/save_all", type="json", auth="user")
    def save_all(self, product_tmpl_id, product_values=None, category_values=None, content_values=None, seo_data=None, **kwargs):
        product = self._product(product_tmpl_id)
        return request.env["bpi.service"].save_all(
            product,
            product_values=product_values,
            category_values=category_values,
            content_values=content_values,
            seo_data=seo_data,
        )

    @http.route("/bader_product_intelligence/update_variant", type="json", auth="user")
    def update_variant(self, product_tmpl_id, product_variant_id, values=None, **kwargs):
        product = self._product(product_tmpl_id)
        variant = self._variant(product, product_variant_id)
        payload = request.env["bpi.service"].update_variant(product, variant, values or {})
        return {"success": True, **payload}

    @http.route("/bader_product_intelligence/set_variant_image", type="json", auth="user")
    def set_variant_image(
        self,
        product_tmpl_id,
        product_variant_id,
        image_token=False,
        image_data_url=False,
        remove=False,
        **kwargs
    ):
        product = self._product(product_tmpl_id)
        variant = self._variant(product, product_variant_id)
        payload = request.env["bpi.service"].set_variant_image(
            product,
            variant,
            image_token=image_token,
            image_data_url=image_data_url,
            remove=remove,
        )
        return {"success": True, **payload}

    @http.route("/bader_product_intelligence/search_pack_components", type="json", auth="user")
    def search_pack_components(self, product_tmpl_id, query="", limit=20, **kwargs):
        product = self._product(product_tmpl_id)
        return request.env["bpi.service"].search_pack_components(product, query=query, limit=limit)

    @http.route("/bader_product_intelligence/update_pack", type="json", auth="user")
    def update_pack(self, product_tmpl_id, packRevision, values=None, **kwargs):
        product = self._product(product_tmpl_id)
        payload = request.env["bpi.service"].update_pack(
            product,
            pack_revision=packRevision,
            values=values or {},
        )
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

    @http.route("/bader_product_intelligence/ai_job/start_seo", type="json", auth="user")
    def start_seo_job(self, product_tmpl_id, target_audience="clinicas", **kwargs):
        product = self._product(product_tmpl_id)
        job = request.env["bpi.ai.job"].sudo().create_seo_job(
            product.sudo(),
            target_audience=target_audience or "clinicas",
            user=request.env.user,
        )
        return {"success": True, "job": job.bpi_to_payload()}

    @http.route("/bader_product_intelligence/ai_job/status", type="json", auth="user")
    def ai_job_status(self, job_id, **kwargs):
        job = self._ai_job(job_id)
        return {"success": True, "job": job.bpi_to_payload()}

    @http.route("/bader_product_intelligence/save_seo", type="json", auth="user")
    def save_seo(self, product_tmpl_id, seo_data=None, **kwargs):
        product = self._product(product_tmpl_id)
        payload = request.env["bpi.service"].save_seo_payload(product, seo_data or {})
        return {"success": True, "seoData": payload}

    @http.route("/bader_product_intelligence/save_video", type="json", auth="user")
    def save_video(self, product_tmpl_id, video_url="", **kwargs):
        product = self._product(product_tmpl_id)
        product.write({"bpi_video_url": product._bpi_normalize_video_url(video_url)})
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
    def delete_image(self, product_tmpl_id, image_token, **kwargs):
        product = self._product(product_tmpl_id)
        image = self._image(product, image_token)
        request.env["bpi.service"].delete_image(image)
        return {"success": True}

    @http.route("/bader_product_intelligence/discover_competitors", type="json", auth="user")
    def discover_competitors(self, product_tmpl_id, limit=10, **kwargs):
        product = self._product(product_tmpl_id)
        return request.env["bpi.service"].discover_competitors(product, int(limit or 10))

    @http.route("/bader_product_intelligence/add_competitor", type="json", auth="user")
    def add_competitor(self, product_tmpl_id, competitor_name="", competitor_url="", competitor_description="", **kwargs):
        product = self._product(product_tmpl_id)
        competitor = request.env["bpi.service"].add_competitor(product, competitor_name, competitor_url, competitor_description=competitor_description)
        return {"success": True, "competitor": competitor}

    @http.route("/bader_product_intelligence/scrape_competitor", type="json", auth="user")
    def scrape_competitor(self, product_tmpl_id, competitor_id, **kwargs):
        product = self._product(product_tmpl_id)
        competitor = self._competitor(product, competitor_id)
        payload = request.env["bpi.service"].scrape_competitor(competitor)
        return {"success": True, "competitor": payload}

    @http.route("/bader_product_intelligence/analyze_competitor", type="json", auth="user")
    def analyze_competitor(self, product_tmpl_id, competitor_id, **kwargs):
        product = self._product(product_tmpl_id)
        competitor = self._competitor(product, competitor_id)
        payload = request.env["bpi.service"].analyze_competitor(competitor)
        return {"success": True, "competitor": payload}

    @http.route("/bader_product_intelligence/delete_competitor", type="json", auth="user")
    def delete_competitor(self, product_tmpl_id, competitor_id, **kwargs):
        product = self._product(product_tmpl_id)
        competitor = self._competitor(product, competitor_id)
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
