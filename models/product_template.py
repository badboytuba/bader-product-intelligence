# -*- coding: utf-8 -*-

import re
import unicodedata

from markupsafe import escape

from odoo import _, fields, models
from odoo.tools import html2plaintext


class ProductTemplate(models.Model):
    _inherit = "product.template"

    bpi_brand_name = fields.Char(string="Marca Producto Intelligence", default="Bader")
    bpi_slug = fields.Char(string="Slug Producto Intelligence")
    bpi_previous_price = fields.Float(string="Precio Anterior")
    bpi_featured = fields.Boolean(string="Destacado", default=False)

    bpi_geo_title = fields.Char(string="GEO Title")
    bpi_geo_description = fields.Text(string="GEO Description")
    bpi_ai_generated_description = fields.Html(string="Descripcion IA")
    bpi_ai_target_audience = fields.Selection(
        [
            ("clinicas", "Clinicas"),
            ("laboratorios", "Laboratorios"),
            ("estudiantes", "Estudiantes"),
            ("general", "General"),
        ],
        string="Audiencia IA",
        default="clinicas",
    )
    bpi_ai_tone = fields.Selection(
        [
            ("profesional", "Profesional"),
            ("tecnico", "Tecnico"),
            ("comercial", "Comercial"),
        ],
        string="Tono IA",
        default="profesional",
    )
    bpi_geo_features = fields.Json(string="Features GEO", default=list)
    bpi_seo_score = fields.Integer(string="SEO Score", default=0)
    bpi_geo_score = fields.Integer(string="GEO Score", default=0)
    bpi_competitiveness_score = fields.Integer(string="Competitiveness Score", default=0)
    bpi_last_analyzed_at = fields.Datetime(string="Ultimo Analisis")
    bpi_video_url = fields.Char(string="Video URL")
    bpi_video_embed_url = fields.Char(string="Video Embed URL", compute="_compute_bpi_video_embed_url")
    bpi_competitive_strategy = fields.Json(string="Estrategia Competitiva", default=dict)
    bpi_competitive_strategy_updated_at = fields.Datetime(string="Estrategia Actualizada")

    bpi_intelligent_niches = fields.Json(string="Nichos Inteligentes", default=list)
    bpi_intelligent_type = fields.Char(string="Tipo Inteligente")
    bpi_intelligent_subcategory = fields.Char(string="Subcategoria Inteligente")
    bpi_intelligent_category_manual = fields.Boolean(string="Categoria Manual", default=False)
    bpi_intelligent_path = fields.Char(string="Ruta Inteligente", compute="_compute_bpi_intelligent_path")

    bpi_keyword_ids = fields.One2many(
        "bpi.product.keyword",
        "product_tmpl_id",
        string="Keywords",
    )
    bpi_faq_ids = fields.One2many(
        "bpi.product.faq",
        "product_tmpl_id",
        string="FAQs",
    )
    bpi_image_ids = fields.One2many(
        "bpi.product.image",
        "product_tmpl_id",
        string="Imagenes IA",
    )
    bpi_competitor_ids = fields.One2many(
        "bpi.product.competitor",
        "product_tmpl_id",
        string="Competidores",
    )
    bpi_chat_session_ids = fields.One2many(
        "bpi.product.chat.session",
        "product_tmpl_id",
        string="Sesiones Chat IA",
    )

    def _bpi_exchange_rate(self):
        value = self.env["ir.config_parameter"].sudo().get_param("bader_product_intelligence.exchange_rate", "1650")
        try:
            return int(float(value or 1650))
        except Exception:
            return 1650

    def _bpi_generate_slug_value(self, value=False):
        text = value or self.name or ""
        normalized = unicodedata.normalize("NFKD", text)
        ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
        slug_value = re.sub(r"[^a-zA-Z0-9\s-]", "", ascii_text).strip().lower()
        slug_value = re.sub(r"[-\s]+", "-", slug_value).strip("-")
        return slug_value[:100]

    def _bpi_main_category(self):
        self.ensure_one()
        if not self.public_categ_ids:
            return self.env["product.public.category"]
        return self.public_categ_ids.sorted(key=lambda rec: ((rec.display_name or rec.name or ""), rec.id))[:1]

    def _bpi_category_display_name(self, category):
        if not category:
            return ""
        return category.display_name or category.name or ""

    def _bpi_plain_text(self, raw_value):
        if not raw_value:
            return ""
        try:
            text = html2plaintext(raw_value)
        except Exception:
            text = str(raw_value)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[^\S\n]+", " ", text)
        text = "\n".join(line.strip() for line in text.split("\n"))
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()[:18000]

    def _bpi_html_from_plaintext(self, raw_value):
        text = (raw_value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        if not text:
            return False
        paragraphs = []
        for block in re.split(r"\n{2,}", text):
            lines = [line.strip() for line in block.split("\n") if line.strip()]
            if not lines:
                continue
            paragraphs.append("<p>%s</p>" % "<br/>".join(str(escape(line)) for line in lines))
        return "".join(paragraphs) or False

    def _bpi_description_payload(self):
        self.ensure_one()
        ai_description = self._bpi_plain_text(self.bpi_ai_generated_description)
        sale_description = self._bpi_plain_text(self.description_sale)
        website_description_text = self._bpi_plain_text(self.website_description)
        technical_description = self._bpi_plain_text(self.description)

        description_candidates = [
            ("ai", ai_description),
            ("sale", sale_description),
            ("website", website_description_text),
            ("technical", technical_description),
        ]
        source = ""
        content_description = ""
        for candidate_source, candidate_value in description_candidates:
            if candidate_value:
                source = candidate_source
                content_description = candidate_value
                break

        source_labels = {
            "ai": _("Descripcion optimizada por Nancy AI"),
            "sale": _("Descripcion comercial de Odoo"),
            "website": _("Descripcion web de Odoo"),
            "technical": _("Descripcion interna de Odoo"),
            "": _("Sin descripcion cargada"),
        }
        return {
            "aiDescription": ai_description,
            "descriptionSale": sale_description,
            "websiteDescriptionText": website_description_text,
            "technicalDescription": technical_description,
            "contentDescription": content_description,
            "source": source,
            "sourceLabel": source_labels.get(source, source_labels[""]),
        }

    def _bpi_prompt_category_name(self):
        self.ensure_one()
        return self._bpi_category_display_name(self._bpi_main_category()) or _("Sin categoria")

    def _bpi_prompt_description(self):
        self.ensure_one()
        descriptions = self._bpi_description_payload()
        return (
            descriptions["descriptionSale"]
            or descriptions["websiteDescriptionText"]
            or descriptions["technicalDescription"]
            or descriptions["aiDescription"]
        )

    def _bpi_image_url(self, model_name, record_id, field_name="image_1920"):
        return "/web/image/%s/%s/%s" % (model_name, record_id, field_name)

    def _bpi_append_image_entry(self, payload, seen_urls, image_url, **values):
        if not image_url or image_url in seen_urls:
            return
        seen_urls.add(image_url)
        payload.append({"imageUrl": image_url, **values})

    def _bpi_native_gallery_payload(self):
        self.ensure_one()
        payload = []
        seen_urls = set()

        if self.image_1920:
            self._bpi_append_image_entry(
                payload,
                seen_urls,
                self._bpi_image_url("product.template", self.id, "image_1920"),
                id="main",
                name=_("Imagen principal"),
                imageType="odoo_main",
                source="odoo",
                sourceLabel=_("Imagen principal de Odoo"),
                prompt="",
                state="approved",
                sequence=0,
                canDelete=False,
            )

        if "product_template_image_ids" in self._fields:
            extra_images = self.product_template_image_ids.sorted(
                key=lambda rec: (getattr(rec, "sequence", 0), rec.id)
            )
            for index, image in enumerate(extra_images, start=1):
                if not image.image_1920:
                    continue
                self._bpi_append_image_entry(
                    payload,
                    seen_urls,
                    self._bpi_image_url(image._name, image.id, "image_1920"),
                    id="odoo:%s" % image.id,
                    name=image.name or (_("Imagen Odoo %s") % index),
                    imageType="odoo_gallery",
                    source="odoo",
                    sourceLabel=_("Imagen extra de Odoo"),
                    prompt="",
                    state="approved",
                    sequence=getattr(image, "sequence", index * 10),
                    canDelete=False,
                )

        variant_records = self.product_variant_ids.sorted("id")
        for index, variant in enumerate(variant_records, start=1):
            field_name = ""
            if variant.image_1920:
                field_name = "image_1920"
            elif getattr(variant, "image_variant_1920", False):
                field_name = "image_variant_1920"
            if not field_name:
                continue
            self._bpi_append_image_entry(
                payload,
                seen_urls,
                self._bpi_image_url(variant._name, variant.id, field_name),
                id="variant:%s" % variant.id,
                name=variant.display_name or (_("Imagen variante %s") % index),
                imageType="odoo_variant",
                source="odoo",
                sourceLabel=_("Imagen de variante de Odoo"),
                prompt="",
                state="approved",
                sequence=1000 + index,
                canDelete=False,
            )
        return payload

    def _bpi_primary_image_url(self):
        self.ensure_one()
        native_gallery = self._bpi_native_gallery_payload()
        if native_gallery:
            return native_gallery[0]["imageUrl"]
        approved_image = self.bpi_image_ids.filtered(lambda rec: rec.state == "approved").sorted("sequence")[:1]
        if not approved_image:
            return False
        linked_native = approved_image.product_image_id
        if linked_native and linked_native.image_1920:
            return self._bpi_image_url(linked_native._name, linked_native.id, "image_1920")
        return self._bpi_image_url("bpi.product.image", approved_image.id, "image_1920")

    def _compute_bpi_intelligent_path(self):
        for product in self:
            segments = []
            category = product._bpi_main_category()
            if category:
                segments.append(product._bpi_category_display_name(category))
            if product.bpi_intelligent_type:
                segments.append(product.bpi_intelligent_type)
            if product.bpi_intelligent_subcategory:
                segments.append(product.bpi_intelligent_subcategory)
            product.bpi_intelligent_path = " / ".join([segment for segment in segments if segment])

    def _compute_bpi_video_embed_url(self):
        for product in self:
            url = product.bpi_video_url or ""
            embed_url = ""
            if "youtube.com/watch" in url:
                video_id = url.split("watch?v=")[1].split("&")[0]
                embed_url = "https://www.youtube.com/embed/%s" % video_id
            elif "youtu.be/" in url:
                video_id = url.split("youtu.be/")[1].split("?")[0]
                embed_url = "https://www.youtube.com/embed/%s" % video_id
            elif "youtube.com/shorts/" in url:
                video_id = url.split("youtube.com/shorts/")[1].split("?")[0]
                embed_url = "https://www.youtube.com/embed/%s" % video_id
            else:
                instagram_match = re.search(r"/(p|reel|reels)/([A-Za-z0-9_-]+)", url)
                tiktok_match = re.search(r"video/(\d+)", url)
                if instagram_match:
                    embed_url = "https://www.instagram.com/%s/%s/embed" % (
                        instagram_match.group(1),
                        instagram_match.group(2),
                    )
                elif tiktok_match:
                    embed_url = "https://www.tiktok.com/embed/v2/%s" % tiktok_match.group(1)
            product.bpi_video_embed_url = embed_url

    def action_open_product_intelligence(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "bader_product_intelligence.action",
            "name": _("Producto Intelligence"),
            "target": "current",
            "params": {"product_tmpl_id": self.id, "origin": "product_form"},
        }

    def _bpi_keyword_values(self, keyword_type):
        self.ensure_one()
        return self.bpi_keyword_ids.filtered(lambda rec: rec.keyword_type == keyword_type).mapped("name")

    def _bpi_reference_images_payload(self):
        self.ensure_one()
        payload = []
        for image in self._bpi_native_gallery_payload():
            payload.append(
                {
                    "token": "main" if image["id"] == "main" else image["id"],
                    "label": image["name"],
                    "url": image["imageUrl"],
                }
            )

        approved_images = self.bpi_image_ids.filtered(lambda rec: rec.state == "approved").sorted("sequence")
        for image in approved_images:
            if image.product_image_id:
                continue
            payload.append(
                {
                    "token": "bpi:%s" % image.id,
                    "label": image.name or _("Variacion IA"),
                    "url": self._bpi_image_url("bpi.product.image", image.id, "image_1920"),
                }
            )
        return payload

    def _bpi_gallery_payload(self):
        self.ensure_one()
        payload = list(self._bpi_native_gallery_payload())
        for image in self.bpi_image_ids.filtered(lambda rec: rec.state == "approved").sorted("sequence"):
            if image.product_image_id:
                continue
            payload.append(
                {
                    "id": "bpi:%s" % image.id,
                    "name": image.name,
                    "imageUrl": self._bpi_image_url("bpi.product.image", image.id, "image_1920"),
                    "imageType": image.image_type,
                    "source": "bpi",
                    "sourceLabel": _("Imagen IA de Producto Intelligence"),
                    "prompt": image.prompt or "",
                    "state": image.state,
                    "sequence": image.sequence,
                    "canDelete": True,
                }
            )
        return payload

    def _bpi_categories_payload(self):
        category_model = self.env["product.public.category"]
        return [
            {
                "id": category.id,
                "name": category.name,
                "completeName": category.display_name or category.name,
            }
            for category in category_model.search([], order="name asc, id asc")
        ]

    def bpi_dashboard_payload(self, exchange_rate=False):
        self.ensure_one()
        exchange_rate = exchange_rate or self._bpi_exchange_rate()
        category = self._bpi_main_category()
        price = float(self.list_price or 0.0)
        local_price = price * exchange_rate
        return {
            "id": self.id,
            "name": self.name or "",
            "sku": self.default_code or "",
            "brand": self.bpi_brand_name or "Bader",
            "category": category.name if category else "",
            "categoryPath": self._bpi_category_display_name(category),
            "priceUsd": price,
            "previousPriceUsd": float(self.bpi_previous_price or 0.0),
            "costUsd": float(self.standard_price or 0.0),
            "localExchangeRate": exchange_rate,
            "priceLocal": local_price,
            "mainImageUrl": self._bpi_primary_image_url(),
            "qtyAvailable": float(self.qty_available or 0.0),
            "inStock": bool((self.qty_available or 0.0) > 0),
            "isPublished": bool(self.website_published),
            "featured": bool(self.bpi_featured),
            "isArchived": not bool(self.active),
            "isDiscontinued": not bool(self.sale_ok),
            "seoScore": int(self.bpi_seo_score or 0),
            "margin": (
                ((float(self.list_price or 0.0) - float(self.standard_price or 0.0)) / float(self.list_price or 1.0) * 100.0)
                if self.list_price and self.standard_price
                else 0.0
            ),
        }

    def bpi_build_payload(self):
        self.ensure_one()
        category = self._bpi_main_category()
        exchange_rate = self._bpi_exchange_rate()
        description_payload = self._bpi_description_payload()
        native_gallery_payload = self._bpi_native_gallery_payload()
        gallery_payload = self._bpi_gallery_payload()
        primary_image_url = gallery_payload[0]["imageUrl"] if gallery_payload else False
        native_primary_image_url = native_gallery_payload[0]["imageUrl"] if native_gallery_payload else primary_image_url
        latest_session = self.bpi_chat_session_ids.sorted(lambda rec: rec.write_date or rec.create_date, reverse=True)[:1]
        chat_messages = []
        if latest_session:
            chat_messages = [
                {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "createdAt": msg.create_date.isoformat() if msg.create_date else False,
                }
                for msg in latest_session.message_ids.sorted("id")
            ]

        current_slug = self.bpi_slug or self._bpi_generate_slug_value()
        seo_data = {
            "seoTitle": self.website_meta_title or self.name or "",
            "seoDescription": self.website_meta_description or "",
            "seoKeywords": self._bpi_keyword_values("seo"),
            "geoTitle": self.bpi_geo_title or "",
            "geoDescription": self.bpi_geo_description or "",
            "geoFeatures": self.bpi_geo_features or [],
            "geoFaq": [
                {
                    "id": faq.id,
                    "question": faq.question,
                    "answer": faq.answer,
                }
                for faq in self.bpi_faq_ids.sorted("sequence")
            ],
            "aiGeneratedDescription": description_payload["aiDescription"],
            "aiGeneratedDescriptionHtml": self.bpi_ai_generated_description or "",
            "aiTargetAudience": self.bpi_ai_target_audience or "clinicas",
            "aiTone": self.bpi_ai_tone or "profesional",
            "seoScore": self.bpi_seo_score,
            "geoScore": self.bpi_geo_score,
            "competitivenessScore": self.bpi_competitiveness_score,
            "lastAnalyzedAt": self.bpi_last_analyzed_at.isoformat() if self.bpi_last_analyzed_at else False,
        }

        return {
            "product": {
                "id": self.id,
                "name": self.name or "",
                "description": description_payload["contentDescription"],
                "contentDescription": description_payload["contentDescription"],
                "descriptionSource": description_payload["source"],
                "descriptionSourceLabel": description_payload["sourceLabel"],
                "descriptionSale": description_payload["descriptionSale"],
                "websiteDescription": self.website_description or "",
                "websiteDescriptionText": description_payload["websiteDescriptionText"],
                "technicalDescription": description_payload["technicalDescription"],
                "sku": self.default_code or "",
                "slug": current_slug,
                "brand": self.bpi_brand_name or "Bader",
                "category": category.name if category else "",
                "categoryPath": self._bpi_category_display_name(category),
                "categoryId": category.id if category else False,
                "priceUsd": float(self.list_price or 0.0),
                "previousPriceUsd": float(self.bpi_previous_price or 0.0),
                "costUsd": float(self.standard_price or 0.0),
                "localExchangeRate": exchange_rate,
                "priceLocal": float(self.list_price or 0.0) * exchange_rate,
                "qtyAvailable": float(self.qty_available or 0.0),
                "inStock": bool((self.qty_available or 0.0) > 0),
                "isPublished": bool(self.website_published),
                "featured": bool(self.bpi_featured),
                "dataLabel": _("Producto Bader: SKU origen %s") % (self.default_code or "-"),
                "mainImageUrl": primary_image_url,
                "imageUrl": native_primary_image_url,
                "imageLarge": primary_image_url,
                "alternativeImages": [image["imageUrl"] for image in native_gallery_payload[1:]],
                "videoUrl": self.bpi_video_url or "",
                "videoEmbedUrl": self.bpi_video_embed_url or "",
                "referenceImages": self._bpi_reference_images_payload(),
                "galleryCount": len(gallery_payload),
                "nativeImageCount": len(native_gallery_payload),
                "intelligentNiches": self.bpi_intelligent_niches or [],
                "intelligentType": self.bpi_intelligent_type or "",
                "intelligentSubcategory": self.bpi_intelligent_subcategory or "",
                "intelligentCategoryManual": bool(self.bpi_intelligent_category_manual),
                "intelligentPath": self.bpi_intelligent_path or "",
                "websiteUrl": self.website_url or "",
            },
            "seoData": seo_data,
            "images": gallery_payload,
            "competitors": [competitor.bpi_to_payload() for competitor in self.bpi_competitor_ids.sorted(lambda rec: rec.id, reverse=True)],
            "categoryIntelligence": category.bpi_to_payload() if category else False,
            "availableCategories": self._bpi_categories_payload(),
            "chatHistory": chat_messages,
            "chatSessionId": latest_session.session_key if latest_session else False,
            "competitiveStrategy": self.bpi_competitive_strategy or {},
            "exchangeRate": exchange_rate,
        }
