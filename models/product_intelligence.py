# -*- coding: utf-8 -*-

import base64
from collections import Counter
import ipaddress
import json
import logging
import math
import os
import re
import socket
import unicodedata
import uuid
from html import unescape
from urllib.parse import parse_qs, urljoin, urlparse

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)


class BPIProductKeyword(models.Model):
    _name = "bpi.product.keyword"
    _description = "Producto Intelligence Keyword"
    _order = "sequence, id"

    product_tmpl_id = fields.Many2one("product.template", required=True, ondelete="cascade")
    name = fields.Char(required=True)
    keyword_type = fields.Selection(
        [("seo", "SEO"), ("geo", "GEO")],
        required=True,
        default="seo",
    )
    sequence = fields.Integer(default=10)


class BPIProductFaq(models.Model):
    _name = "bpi.product.faq"
    _description = "Producto Intelligence FAQ"
    _order = "sequence, id"

    product_tmpl_id = fields.Many2one("product.template", required=True, ondelete="cascade")
    question = fields.Char(required=True)
    answer = fields.Text(required=True)
    sequence = fields.Integer(default=10)


class BPIProductImage(models.Model):
    _name = "bpi.product.image"
    _description = "Producto Intelligence Image"
    _order = "sequence, id desc"

    product_tmpl_id = fields.Many2one("product.template", required=True, ondelete="cascade")
    product_image_id = fields.Many2one("product.image", string="Imagen Odoo", ondelete="set null")
    name = fields.Char(required=True)
    image_1920 = fields.Image(required=True, attachment=True)
    mime_type = fields.Char()
    prompt = fields.Text()
    image_type = fields.Selection(
        [
            ("ai_generated", "IA"),
            ("reference", "Referencia"),
        ],
        default="ai_generated",
        required=True,
    )
    state = fields.Selection(
        [
            ("approved", "Approved"),
            ("preview", "Preview"),
            ("rejected", "Rejected"),
        ],
        default="approved",
        required=True,
    )
    sequence = fields.Integer(default=10)


class BPIProductCompetitor(models.Model):
    _name = "bpi.product.competitor"
    _description = "Producto Intelligence Competitor"
    _order = "id desc"

    product_tmpl_id = fields.Many2one("product.template", required=True, ondelete="cascade")
    competitor_name = fields.Char(required=True)
    competitor_url = fields.Char(required=True)
    competitor_price = fields.Float()
    competitor_offer_price = fields.Float()
    competitor_currency = fields.Char(default="ARS")
    competitor_title = fields.Char()
    competitor_description = fields.Text()
    competitor_features = fields.Json(default=list)
    meta_title = fields.Char()
    meta_description = fields.Text()
    meta_keywords = fields.Json(default=list)
    h1_tags = fields.Json(default=list)
    h2_tags = fields.Json(default=list)
    og_title = fields.Char()
    og_description = fields.Text()
    og_image = fields.Char()
    canonical_url = fields.Char()
    structured_data = fields.Json(default=list)
    page_content = fields.Text()
    word_count = fields.Integer()
    image_count = fields.Integer()
    internal_links = fields.Integer()
    external_links = fields.Integer()
    seo_score = fields.Integer()
    price_comparison = fields.Selection(
        [
            ("cheaper", "Más barato"),
            ("similar", "Similar"),
            ("expensive", "Más caro"),
        ],
        default="similar",
    )
    strengths_vs_us = fields.Json(default=list)
    weaknesses_vs_us = fields.Json(default=list)
    firecrawl_data = fields.Json(default=dict)
    scrape_status = fields.Selection(
        [
            ("pending", "Pending"),
            ("success", "Success"),
            ("failed", "Failed"),
        ],
        default="pending",
    )
    scrape_error = fields.Text()
    last_scraped_at = fields.Datetime()

    def bpi_to_payload(self):
        self.ensure_one()
        return {
            "id": self.id,
            "competitorName": self.competitor_name,
            "competitorUrl": self.competitor_url,
            "competitorPrice": self.competitor_price,
            "competitorOfferPrice": self.competitor_offer_price,
            "competitorCurrency": self.competitor_currency,
            "competitorTitle": self.competitor_title or "",
            "competitorDescription": self.competitor_description or "",
            "competitorFeatures": self.competitor_features or [],
            "priceComparison": self.price_comparison or "similar",
            "strengthsVsUs": self.strengths_vs_us or [],
            "weaknessesVsUs": self.weaknesses_vs_us or [],
            "lastScrapedAt": self.last_scraped_at.isoformat() if self.last_scraped_at else False,
            "metaTitle": self.meta_title or "",
            "metaDescription": self.meta_description or "",
            "metaKeywords": self.meta_keywords or [],
            "h1Tags": self.h1_tags or [],
            "h2Tags": self.h2_tags or [],
            "ogTitle": self.og_title or "",
            "ogDescription": self.og_description or "",
            "ogImage": self.og_image or "",
            "canonicalUrl": self.canonical_url or "",
            "structuredData": self.structured_data or [],
            "pageContent": self.page_content or "",
            "wordCount": self.word_count or 0,
            "imageCount": self.image_count or 0,
            "internalLinks": self.internal_links or 0,
            "externalLinks": self.external_links or 0,
            "seoScore": self.seo_score or 0,
            "firecrawlData": self.firecrawl_data or {},
            "scrapeStatus": self.scrape_status or "pending",
            "scrapeError": self.scrape_error or "",
        }


class BPIProductChatSession(models.Model):
    _name = "bpi.product.chat.session"
    _description = "Producto Intelligence Chat Session"
    _order = "write_date desc, id desc"

    product_tmpl_id = fields.Many2one("product.template", required=True, ondelete="cascade")
    name = fields.Char(required=True)
    session_key = fields.Char(required=True, index=True, default=lambda self: str(uuid.uuid4()))
    message_ids = fields.One2many("bpi.product.chat.message", "session_id", string="Mensajes")


class BPIProductChatMessage(models.Model):
    _name = "bpi.product.chat.message"
    _description = "Producto Intelligence Chat Message"
    _order = "id"

    session_id = fields.Many2one("bpi.product.chat.session", required=True, ondelete="cascade")
    role = fields.Selection(
        [
            ("user", "User"),
            ("assistant", "Assistant"),
            ("system", "System"),
        ],
        required=True,
        default="user",
    )
    content = fields.Text(required=True)


class BPIService(models.AbstractModel):
    _name = "bpi.service"
    _description = "Producto Intelligence Service"

    _CATEGORY_NICHE_ALIASES = {
        "clinica": "clinica",
        "clinicas": "clinica",
        "clinica_dental": "clinica",
        "clinicas_dentales": "clinica",
        "laboratorio": "laboratorio",
        "laboratorios": "laboratorio",
        "laboratorio_dental": "laboratorio",
        "laboratorios_dentales": "laboratorio",
        "estudiante": "estudiantes",
        "estudiantes": "estudiantes",
    }
    _CATEGORY_TYPE_ALLOWED = {
        "consumible",
        "equipo",
        "instrumental",
        "mobiliario",
        "protesis",
        "ortodoncia",
        "endodoncia",
        "cirugia",
        "higiene",
        "radiologia",
        "otro",
    }
    _CATEGORY_TYPE_ALIASES = {
        "clamp": "instrumental",
        "clamps": "instrumental",
        "clamp_dental": "instrumental",
        "instrumental_de_mano": "instrumental",
        "instrumental_dental": "instrumental",
        "instrumento": "instrumental",
        "instrumentos": "instrumental",
        "material": "consumible",
        "materiales": "consumible",
        "insumo": "consumible",
        "insumos": "consumible",
        "equipamiento": "equipo",
        "equipos": "equipo",
    }
    _CATEGORY_SUBCATEGORY_ALLOWED = {
        "aislamiento",
        "adhesivos",
        "anestesia",
        "blanqueamiento",
        "cementos",
        "composites",
        "desechables",
        "endodoncia",
        "esterilizacion",
        "fresas",
        "higiene",
        "implantes",
        "impresion",
        "instrumental_clinico",
        "laboratorio",
        "matrices_bandas",
        "ortodoncia",
        "profilaxis",
        "protesis",
        "radiologia",
        "restauracion",
        "otro",
    }
    _CATEGORY_SUBCATEGORY_ALIASES = {
        "clamp": "aislamiento",
        "clamps": "aislamiento",
        "clamp_para_dique_de_goma": "aislamiento",
        "dique": "aislamiento",
        "dique_de_goma": "aislamiento",
        "aislamiento_absoluto": "aislamiento",
        "aislamiento_dental": "aislamiento",
        "instrumental": "instrumental_clinico",
        "instrumental_dental": "instrumental_clinico",
        "instrumental_de_mano": "instrumental_clinico",
        "higiene_dental": "higiene",
        "profilaxis_dental": "profilaxis",
        "fresas_dentales": "fresas",
        "impresion_dental": "impresion",
        "materiales_de_impresion": "impresion",
        "descartables": "desechables",
        "restauraciones": "restauracion",
    }

    _ENV_FALLBACKS = {
        "bader_product_intelligence.openai_api_key": [
            "BPI_OPENAI_API_KEY",
            "OPENAI_API_KEY",
        ],
        "bader_product_intelligence.openai_text_model": [
            "BPI_OPENAI_TEXT_MODEL",
        ],
        "bader_product_intelligence.openai_image_model": [
            "BPI_OPENAI_IMAGE_MODEL",
        ],
        "bader_product_intelligence.openai_image_edit_model": [
            "BPI_OPENAI_IMAGE_EDIT_MODEL",
        ],
        "bader_product_intelligence.openai_reasoning_effort": [
            "BPI_OPENAI_REASONING_EFFORT",
        ],
        "bader_product_intelligence.openai_text_verbosity": [
            "BPI_OPENAI_TEXT_VERBOSITY",
        ],
        "bader_product_intelligence.firecrawl_api_key": [
            "BPI_FIRECRAWL_API_KEY",
            "FIRECRAWL_API_KEY",
        ],
        "bader_product_intelligence.firecrawl_base_url": [
            "BPI_FIRECRAWL_BASE_URL",
        ],
    }

    @api.model
    def _get_config(self, key, default=False):
        value = self.env["ir.config_parameter"].sudo().get_param(key)
        if value:
            return value
        for env_key in self._ENV_FALLBACKS.get(key, []):
            env_value = os.getenv(env_key)
            if env_value:
                return env_value
        return default

    @api.model
    def _description_plain_text(self, raw_value):
        if not raw_value:
            return False
        try:
            text = html2plaintext(raw_value)
        except Exception:
            text = str(raw_value)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[^\S\n]+", " ", text)
        text = "\n".join(line.strip() for line in text.split("\n"))
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip() or False

    @api.model
    def _taxonomy_key(self, value):
        if not value:
            return ""
        text = unicodedata.normalize("NFKD", str(value))
        text = text.encode("ascii", "ignore").decode("ascii").lower()
        return re.sub(r"[^a-z0-9]+", "_", text).strip("_")

    @api.model
    def _normalize_taxonomy_choice(self, value, allowed_values, aliases, default=False):
        key = self._taxonomy_key(value)
        if not key:
            return default
        if key in allowed_values:
            return key
        return aliases.get(key, default)

    @api.model
    def _normalize_category_niches(self, raw_values):
        normalized = []
        for raw_value in raw_values or []:
            value = self._CATEGORY_NICHE_ALIASES.get(self._taxonomy_key(raw_value))
            if value and value not in normalized:
                normalized.append(value)
        return normalized

    @api.model
    def _require_config(self, key, label):
        value = self._get_config(key)
        if not value:
            raise UserError(_("Configura %s en Ajustes antes de usar Producto Intelligence.") % label)
        return value

    @api.model
    def _public_category_label(self, product, default="Sin categoría"):
        category = product.public_categ_ids[:1]
        if not category:
            return default
        return category.display_name or category.name or default

    @api.model
    def _openai_headers(self):
        api_key = self._require_config("bader_product_intelligence.openai_api_key", "OpenAI API Key")
        return {
            "Authorization": "Bearer %s" % api_key,
            "Content-Type": "application/json",
        }

    @api.model
    def _clean_json_text(self, raw_text):
        raw_text = (raw_text or "").strip()
        if raw_text.startswith("```"):
            raw_text = re.sub(r"^```(?:json)?", "", raw_text).strip()
            raw_text = re.sub(r"```$", "", raw_text).strip()
        return raw_text

    @api.model
    def _parse_openai_text(self, payload):
        if payload.get("output_text"):
            return (payload.get("output_text") or "").strip()
        texts = []
        for item in payload.get("output") or []:
            if item.get("type") != "message":
                continue
            for part in item.get("content") or []:
                if part.get("type") == "output_text" and part.get("text"):
                    texts.append(part["text"])
        return "\n".join(texts).strip()

    @api.model
    def _openai_request(self, path, json_payload=None, files=None, data=None, timeout=120):
        import time as _time

        url = "https://api.openai.com/v1/%s" % path.lstrip("/")
        headers = self._openai_headers()
        if files:
            headers.pop("Content-Type", None)
        max_retries = 5
        for attempt in range(max_retries):
            try:
                response = requests.post(url, json=json_payload, files=files, data=data, headers=headers, timeout=timeout)
                response.raise_for_status()
                return response.json()
            except requests.RequestException as error:
                response = getattr(error, "response", None)
                status = getattr(response, "status_code", 0)
                openai_error = {}
                if response is not None:
                    try:
                        openai_error = (response.json() or {}).get("error") or {}
                    except ValueError:
                        openai_error = {}
                error_type = openai_error.get("type") or ""
                error_code = openai_error.get("code") or ""
                error_label = error_code or error_type or "unknown"

                if status in (401, 403):
                    _logger.warning("OpenAI authentication/permission error for %s: %s", path, error_label)
                    raise UserError(
                        _("La API Key de OpenAI no es valida o no tiene permisos para este proyecto. Configura una API Key activa en Ajustes.")
                    ) from error

                if status == 400 and error_label in ("model_not_found", "invalid_request_error"):
                    _logger.warning("OpenAI request/configuration error for %s: %s", path, error_label)
                    raise UserError(
                        _("El modelo/configuracion de OpenAI no esta disponible para esta API Key. Revisa el modelo configurado en Ajustes.")
                    ) from error

                if status == 429 and error_label in ("billing_not_active", "insufficient_quota", "quota_exceeded"):
                    _logger.error("OpenAI billing/quota error for %s: %s", path, error_label)
                    raise UserError(
                        _("La cuenta/proyecto de OpenAI no tiene billing o creditos activos. Activa billing/creditos en OpenAI o configura una API Key de un proyecto activo.")
                    ) from error

                if status == 429 and attempt < max_retries - 1:
                    wait = 3 * (2 ** attempt)  # 3, 6, 12, 24, 48
                    _logger.warning("OpenAI 429 rate-limited (%s), retrying in %ss (attempt %s/%s)", error_label, wait, attempt + 1, max_retries)
                    _time.sleep(wait)
                    continue
                if status == 429:
                    _logger.error("OpenAI rate limit exhausted after %s retries (%s)", max_retries, error_label)
                    raise UserError(
                        _("Límite de uso de OpenAI alcanzado. Espera 1-2 minutos e intenta de nuevo.")
                    ) from error
                _logger.exception("OpenAI request failed for %s (%s)", path, error_label)
                raise UserError(
                    _("No se pudo completar la solicitud a OpenAI. Revisa la configuracion e intenta de nuevo.")
                ) from error
            except ValueError as error:
                _logger.exception("OpenAI returned a non-JSON response for %s", path)
                raise UserError(_("OpenAI devolvio una respuesta invalida.")) from error

    @api.model
    def _openai_response(self, prompt, model_name=False, text_format=None):
        model_name = model_name or self._get_config("bader_product_intelligence.openai_text_model", "gpt-5.5")
        text_payload = {"format": text_format or {"type": "text"}}
        verbosity = (self._get_config("bader_product_intelligence.openai_text_verbosity", "medium") or "medium").strip().lower()
        if verbosity in ("low", "medium", "high"):
            text_payload["verbosity"] = verbosity
        json_payload = {
            "model": model_name,
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}],
                }
            ],
            "text": text_payload,
            "store": False,
        }
        reasoning_effort = (self._get_config("bader_product_intelligence.openai_reasoning_effort", "low") or "low").strip().lower()
        if model_name.startswith("gpt-5") and reasoning_effort in ("none", "minimal", "low", "medium", "high", "xhigh"):
            json_payload["reasoning"] = {"effort": reasoning_effort}
        payload = self._openai_request(
            "responses",
            json_payload=json_payload,
        )
        return self._parse_openai_text(payload)

    @api.model
    def _openai_json(self, prompt, model_name=False):
        text = self._clean_json_text(self._openai_response(prompt, model_name=model_name, text_format={"type": "json_object"}))
        if not text:
            raise UserError(_("OpenAI no devolvió contenido JSON."))
        try:
            return json.loads(text)
        except ValueError as error:
            _logger.exception("OpenAI returned invalid JSON: %s", text[:500])
            raise UserError(_("OpenAI devolvio JSON invalido para esta accion.")) from error

    @api.model
    def _image_mime_from_base64(self, encoded):
        try:
            raw = base64.b64decode(encoded)
        except Exception:
            return "image/png"
        signatures = (
            (b"\x89PNG\r\n\x1a\n", "image/png"),
            (b"\xff\xd8\xff", "image/jpeg"),
            (b"GIF87a", "image/gif"),
            (b"GIF89a", "image/gif"),
            (b"RIFF", "image/webp"),
        )
        for signature, mime_type in signatures:
            if raw.startswith(signature):
                if mime_type == "image/webp" and raw[8:12] != b"WEBP":
                    continue
                return mime_type
        return "image/png"

    @api.model
    def _binary_to_openai_image(self, binary_value, filename="reference.png"):
        if not binary_value:
            return False
        encoded = binary_value.decode() if isinstance(binary_value, bytes) else binary_value
        try:
            raw = base64.b64decode(encoded)
        except Exception:
            return False
        mime_type = self._image_mime_from_base64(encoded)
        return {
            "filename": filename,
            "mime_type": mime_type,
            "raw": raw,
        }

    @api.model
    def _data_url_to_openai_image(self, data_url, filename="uploaded-reference.png"):
        if not data_url or "," not in data_url:
            return False
        meta, encoded = data_url.split(",", 1)
        mime_type = "image/png"
        if ":" in meta and ";" in meta:
            mime_type = meta.split(":", 1)[1].split(";", 1)[0] or "image/png"
        try:
            raw = base64.b64decode(encoded)
        except Exception:
            return False
        return {
            "filename": filename,
            "mime_type": mime_type,
            "raw": raw,
        }

    @api.model
    def _reference_images(self, product, reference_tokens):
        images = []
        for token in reference_tokens or []:
            if token == "main" and product.image_1920:
                image = self._binary_to_openai_image(product.image_1920, "product-main.png")
                if image:
                    images.append(image)
                continue

            if token.startswith("bpi:"):
                image_id = int(token.split(":")[1])
                image = self.env["bpi.product.image"].browse(image_id).exists()
                if image and image.product_tmpl_id == product:
                    image_payload = self._binary_to_openai_image(image.image_1920, "bpi-%s.png" % image.id)
                    if image_payload:
                        images.append(image_payload)
                continue

            if token.startswith("odoo:"):
                image_id = int(token.split(":")[1])
                image = self.env["product.image"].browse(image_id).exists()
                if image and image.product_tmpl_id == product:
                    image_payload = self._binary_to_openai_image(image.image_1920, "odoo-%s.png" % image.id)
                    if image_payload:
                        images.append(image_payload)
                continue

            if token.startswith("variant:"):
                variant_id = int(token.split(":")[1])
                variant = self.env["product.product"].browse(variant_id).exists()
                if variant and variant.product_tmpl_id == product:
                    image_payload = self._binary_to_openai_image(
                        variant.image_1920 or getattr(variant, "image_variant_1920", False),
                        "variant-%s.png" % variant.id,
                    )
                    if image_payload:
                        images.append(image_payload)
        return images

    @api.model
    def _extract_openai_image(self, payload):
        data = payload.get("data") or []
        if data and data[0].get("b64_json"):
            return {"mimeType": "image/png", "data": data[0]["b64_json"]}
        for item in payload.get("output") or []:
            if item.get("type") == "image_generation_call" and item.get("result"):
                return {"mimeType": "image/png", "data": item["result"]}
        raise UserError(_("OpenAI no devolvió una imagen válida."))

    @api.model
    def _detect_price_comparison(self, our_price, competitor_price):
        if not our_price or not competitor_price:
            return "similar"
        diff = (competitor_price - our_price) / max(our_price, 0.01)
        if diff > 0.10:
            return "expensive"
        if diff < -0.10:
            return "cheaper"
        return "similar"

    @api.model
    def _extract_meta_tag(self, html, tag_name):
        if not html:
            return ""
        regex = re.compile(r'<meta\s+name=["\']%s["\']\s+content=["\']([^"\']+)["\']' % re.escape(tag_name), re.I)
        alt_regex = re.compile(r'<meta\s+content=["\']([^"\']+)["\']\s+name=["\']%s["\']' % re.escape(tag_name), re.I)
        match = regex.search(html) or alt_regex.search(html)
        return match.group(1).strip() if match else ""

    @api.model
    def _extract_meta_property(self, html, prop_name):
        if not html:
            return ""
        regex = re.compile(r'<meta\s+property=["\']%s["\']\s+content=["\']([^"\']+)["\']' % re.escape(prop_name), re.I)
        alt_regex = re.compile(r'<meta\s+content=["\']([^"\']+)["\']\s+property=["\']%s["\']' % re.escape(prop_name), re.I)
        match = regex.search(html) or alt_regex.search(html)
        return match.group(1).strip() if match else ""

    @api.model
    def _extract_headings(self, html, tag):
        if not html:
            return []
        pattern = re.compile(r"<%s[^>]*>(.*?)</%s>" % (tag, tag), re.I | re.S)
        values = []
        for match in pattern.finditer(html):
            text = re.sub(r"<[^>]+>", "", match.group(1) or "").strip()
            if text:
                values.append(text[:200])
        return values[:10]

    @api.model
    def _extract_structured_data(self, html):
        if not html:
            return []
        pattern = re.compile(r'<script\s+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.I | re.S)
        items = []
        for match in pattern.finditer(html):
            try:
                items.append(json.loads(match.group(1)))
            except Exception:
                continue
        return items

    @api.model
    def _walk_structured_data(self, value, depth=0):
        """Yield every dict inside JSON-LD, including @graph/offers nests."""
        if depth > 8:
            return
        if isinstance(value, dict):
            yield value
            for child in value.values():
                for item in self._walk_structured_data(child, depth + 1):
                    yield item
            return
        if isinstance(value, list):
            for child in value:
                for item in self._walk_structured_data(child, depth + 1):
                    yield item

    @api.model
    def _parse_price_number(self, raw_value):
        if raw_value in (None, False, ""):
            return False
        if isinstance(raw_value, (int, float)) and not isinstance(raw_value, bool):
            value = float(raw_value)
            return value if value > 0 else False

        text = unescape(str(raw_value))
        text = re.sub(r"(?i)\b(ars|usd|u\$s|us\$|ar\$|precio|price|sale|oferta|regular|final|desde|hasta|iva|incluido|contado)\b", " ", text)
        text = re.sub(r"[^\d,.\s]", " ", text)
        text = re.sub(r"\s+", "", text)
        if not re.search(r"\d", text or ""):
            return False

        has_dot = "." in text
        has_comma = "," in text
        normalized = text
        if has_dot and has_comma:
            if text.rfind(",") > text.rfind("."):
                normalized = text.replace(".", "").replace(",", ".")
            else:
                normalized = text.replace(",", "")
        elif has_comma:
            parts = text.split(",")
            if len(parts[-1]) in (1, 2):
                normalized = "".join(parts[:-1]).replace(",", "") + "." + parts[-1]
            else:
                normalized = text.replace(",", "")
        elif has_dot:
            parts = text.split(".")
            if len(parts) > 2:
                normalized = "".join(parts[:-1]) + ("." + parts[-1] if len(parts[-1]) in (1, 2) else parts[-1])
            elif len(parts[-1]) == 3 and len(parts[0]) <= 3:
                normalized = text.replace(".", "")

        try:
            value = float(normalized)
        except Exception:
            return False
        if value <= 0 or value > 1000000000:
            return False
        return value

    @api.model
    def _extract_title_tag(self, html):
        if not html:
            return ""
        match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        if not match:
            return ""
        title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", match.group(1) or ""))
        return unescape(title).strip()

    @api.model
    def _extract_canonical_url(self, html, base_url):
        if not html:
            return ""
        patterns = [
            r'<link[^>]+rel=["\'][^"\']*canonical[^"\']*["\'][^>]+href=["\']([^"\']+)["\']',
            r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\'][^"\']*canonical[^"\']*["\']',
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.I)
            if match:
                return urljoin(base_url or "", match.group(1).strip())
        return ""

    @api.model
    def _html_to_markdown_text(self, html):
        if not html:
            return ""
        clean_html = re.sub(r"<(script|style|noscript)\b[^>]*>.*?</\1>", " ", html, flags=re.I | re.S)
        try:
            text = html2plaintext(clean_html)
        except Exception:
            text = re.sub(r"<[^>]+>", " ", clean_html)
        text = unescape(text or "")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[^\S\n]+", " ", text)
        text = "\n".join(line.strip() for line in text.split("\n"))
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @api.model
    def _derive_keywords(self, *parts):
        stopwords = {
            "para", "con", "sin", "por", "una", "uno", "del", "las", "los", "les", "sus", "este", "esta",
            "estos", "estas", "sobre", "entre", "desde", "hasta", "como", "más", "mas", "muy", "cada",
            "producto", "productos", "comprar", "venta", "online", "tienda", "argentina", "bader",
            "precio", "precios", "stock", "disponible", "disponibles", "oferta", "ofertas", "envio",
            "envíos", "envios", "carrito", "cantidad", "marca", "modelo", "inicio", "contacto", "buscar",
            "login", "cuenta", "condiciones", "privacidad", "copyright", "todos", "todas", "your", "the",
            "and", "for", "with", "sin", "nbsp", "none", "ver", "home", "menu", "catalogo", "categorias",
        }
        domain_terms = {
            "clamp", "clamps", "grapa", "grapas", "dique", "goma", "aislamiento", "absoluto", "molar",
            "molares", "premolar", "premolares", "dental", "odontologico", "odontológica", "odontologia",
            "odontología", "instrumental", "acero", "inoxidable", "endodoncia", "operatoria", "clinica",
            "clínica",
        }

        def clean_text(value):
            text = str(value or "")
            text = html2plaintext(text) if "<" in text else text
            text = unescape(text).lower()
            return re.sub(r"\s+", " ", text).strip()

        def tokenize(value):
            tokens = re.findall(r"[a-záéíóúüñ0-9][a-záéíóúüñ0-9\-]{2,}", clean_text(value), re.I)
            clean_tokens = []
            for token in tokens:
                token = token.strip("-")
                if not token or token in stopwords:
                    continue
                if token.isdigit() and len(token) < 4:
                    continue
                clean_tokens.append(token)
            return clean_tokens

        def has_domain_term(keyword):
            key = self._taxonomy_key(keyword)
            return any(self._taxonomy_key(term) in key for term in domain_terms)

        candidate_scores = Counter()
        priority_parts = [part for part in parts[:-1] if part]
        body_parts = [parts[-1]] if parts else []

        for part in priority_parts:
            tokens = tokenize(part)
            for token in tokens:
                candidate_scores[token] += 8 if has_domain_term(token) else 3
            for size in (2, 3):
                for index in range(0, max(len(tokens) - size + 1, 0)):
                    phrase = " ".join(tokens[index : index + size])
                    if len(phrase) <= 48:
                        candidate_scores[phrase] += 14 if has_domain_term(phrase) else 4

        body_tokens = []
        for part in body_parts:
            body_tokens.extend(tokenize(clean_text(part)[:8000]))
        body_counts = Counter(body_tokens)
        for token, count in body_counts.most_common(80):
            if has_domain_term(token):
                candidate_scores[token] += min(count, 8)
        for size in (2, 3):
            phrase_counts = Counter()
            for index in range(0, max(len(body_tokens) - size + 1, 0)):
                phrase = " ".join(body_tokens[index : index + size])
                if len(phrase) <= 48 and has_domain_term(phrase):
                    phrase_counts[phrase] += 1
            for phrase, count in phrase_counts.most_common(40):
                candidate_scores[phrase] += min(count, 5) * size

        if not candidate_scores:
            return []

        selected = []
        seen = set()
        for keyword, _score in candidate_scores.most_common(80):
            key = self._taxonomy_key(keyword)
            if not key or key in seen:
                continue
            if any(key in self._taxonomy_key(existing) and key != self._taxonomy_key(existing) for existing in selected):
                continue
            seen.add(key)
            selected.append(keyword[:60])
            if len(selected) >= 14:
                break
        return selected

    @api.model
    def _extract_prices(self, html, markdown, structured_data):
        price = False
        offer_price = False
        currency = "ARS"

        def set_candidate(raw_price, raw_currency=None, prefer_offer=False):
            parsed_price = self._parse_price_number(raw_price)
            if not parsed_price:
                return
            nonlocal price, offer_price, currency
            currency = raw_currency or currency or "ARS"
            if prefer_offer:
                if not offer_price or parsed_price < offer_price:
                    offer_price = parsed_price
                return
            if not price:
                price = parsed_price
            elif parsed_price < price and parsed_price > 10:
                if not offer_price or parsed_price < offer_price:
                    offer_price = parsed_price

        for data in structured_data or []:
            for item in self._walk_structured_data(data):
                raw_type = item.get("@type") or item.get("type") or ""
                if isinstance(raw_type, list):
                    raw_type = " ".join(str(value) for value in raw_type)
                raw_type = str(raw_type).lower()
                item_currency = item.get("priceCurrency") or item.get("currency") or item.get("price_currency")
                if any(key in item for key in ("price", "salePrice", "lowPrice", "highPrice")):
                    set_candidate(item.get("price") or item.get("salePrice") or item.get("highPrice"), item_currency)
                    set_candidate(item.get("lowPrice") or item.get("salePrice"), item_currency, prefer_offer=True)
                if "offer" in raw_type or "product" in raw_type:
                    spec = item.get("priceSpecification")
                    if isinstance(spec, dict):
                        set_candidate(spec.get("price"), spec.get("priceCurrency") or item_currency)
                    elif isinstance(spec, list):
                        for spec_item in spec:
                            if isinstance(spec_item, dict):
                                set_candidate(spec_item.get("price"), spec_item.get("priceCurrency") or item_currency)

        if not price:
            text = "%s\n%s" % (html or "", markdown or "")
            compact_text = re.sub(r"\s+", " ", unescape(text))[:250000]
            currency_patterns = [
                (r"(?i)(?:ARS|AR\$|\$)\s*([\d][\d\.\,\s]{2,})", "ARS"),
                (r"(?i)(?:USD|U\$S|US\$)\s*([\d][\d\.\,\s]{1,})", "USD"),
                (r"(?i)(?:precio|price|oferta|sale)[^0-9$]{0,60}(?:ARS|AR\$|\$)?\s*([\d][\d\.\,\s]{2,})", "ARS"),
                (r"(?i)([\d][\d\.\,\s]{2,})\s*(?:ARS|pesos)", "ARS"),
            ]
            fallback_prices = []
            for pattern, detected_currency in currency_patterns:
                for match in re.finditer(pattern, compact_text):
                    parsed_price = self._parse_price_number(match.group(1))
                    if parsed_price and parsed_price >= 10:
                        fallback_prices.append((match.start(), parsed_price, detected_currency))
                if fallback_prices:
                    break
            if fallback_prices:
                fallback_prices = sorted(fallback_prices, key=lambda item: item[0])
                price = fallback_prices[0][1]
                currency = fallback_prices[0][2]
                lower_prices = [candidate[1] for candidate in fallback_prices[1:8] if candidate[1] < price]
                if lower_prices:
                    offer_price = min(lower_prices)
        return price, offer_price, currency

    @api.model
    def _extract_features(self, markdown):
        features = []
        for line in (markdown or "").splitlines():
            clean = line.strip(" -*\t")
            if clean and len(clean) > 8 and len(clean) < 160:
                features.append(clean)
            if len(features) >= 10:
                break
        return features

    @api.model
    def _count_links(self, html, base_url):
        internal = 0
        external = 0
        if not html:
            return internal, external
        host = urlparse(base_url).netloc
        for match in re.finditer(r'href=["\']([^"\']+)["\']', html, re.I):
            href = match.group(1)
            if href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
                continue
            parsed = urlparse(href)
            if not parsed.netloc or parsed.netloc == host:
                internal += 1
            else:
                external += 1
        return internal, external

    @api.model
    def _calculate_seo_score(self, meta_title, meta_description, h1_tags, structured_data, og_title, og_description, canonical_url, word_count, image_count, h2_tags):
        score = 0
        if meta_title:
            score += 15
        if meta_description:
            score += 15
        if h1_tags:
            score += 10
        if structured_data:
            score += 15
        if og_title and og_description:
            score += 10
        if canonical_url:
            score += 10
        if 50 <= len(meta_title or "") <= 65:
            score += 10
        if 120 <= len(meta_description or "") <= 165:
            score += 10
        if (word_count or 0) >= 300:
            score += 10
        if (image_count or 0) >= 3:
            score += 5
        if (len(h2_tags or [])) >= 2:
            score += 5
        return min(score, 100)

    @api.model
    def save_seo_payload(self, product, data):
        product.ensure_one()
        seo_keywords = [kw.strip() for kw in (data.get("seoKeywords") or []) if kw and kw.strip()]
        geo_keywords = [kw.strip() for kw in (data.get("geoKeywords") or data.get("geoFeatures") or []) if kw and kw.strip()]
        faqs = data.get("geoFaq") or []
        # Sanitize aiTargetAudience: AI may return full text instead of selection key
        valid_audiences = {"clinicas", "laboratorios", "estudiantes", "general"}
        raw_audience = (data.get("aiTargetAudience") or "clinicas").strip().lower()
        if raw_audience not in valid_audiences:
            # Fuzzy match: "Clínicas Dentales" → "clinicas"
            audience_map = {"clin": "clinicas", "lab": "laboratorios", "estud": "estudiantes"}
            sanitized = "clinicas"
            for prefix, key in audience_map.items():
                if prefix in raw_audience:
                    sanitized = key
                    break
            raw_audience = sanitized

        product.write(
            {
                "website_meta_title": data.get("seoTitle") or "",
                "website_meta_description": data.get("seoDescription") or "",
                "bpi_geo_title": data.get("geoTitle") or "",
                "bpi_geo_description": data.get("geoDescription") or "",
                "bpi_geo_features": data.get("geoFeatures") or [],
                "bpi_ai_generated_description": data.get("aiGeneratedDescription") or "",
                "bpi_ai_target_audience": raw_audience,
                "bpi_seo_score": int(data.get("seoScore") or 0),
                "bpi_geo_score": int(data.get("geoScore") or 0),
                "bpi_competitiveness_score": int(data.get("competitivenessScore") or 0),
                "bpi_last_analyzed_at": fields.Datetime.now(),
            }
        )

        product.bpi_keyword_ids.unlink()
        keyword_commands = []
        for index, keyword in enumerate(seo_keywords):
            keyword_commands.append((0, 0, {"name": keyword, "keyword_type": "seo", "sequence": index * 10 + 10}))
        for index, keyword in enumerate(geo_keywords):
            keyword_commands.append((0, 0, {"name": keyword, "keyword_type": "geo", "sequence": index * 10 + 10}))
        if keyword_commands:
            product.write({"bpi_keyword_ids": keyword_commands})

        product.bpi_faq_ids.unlink()
        faq_commands = []
        for index, faq in enumerate(faqs):
            question = (faq or {}).get("question")
            answer = (faq or {}).get("answer")
            if question and answer:
                faq_commands.append((0, 0, {"question": question, "answer": answer, "sequence": index * 10 + 10}))
        if faq_commands:
            product.write({"bpi_faq_ids": faq_commands})
        return product.bpi_build_payload()["seoData"]

    @api.model
    def analyze_seo(self, product, target_audience):
        product.ensure_one()
        prompt = """Sos Nancy AI, la experta #1 en SEO dental y GEO (Generative Engine Optimization) de Bader Argentina — importador líder de equipamiento e insumos odontológicos.

Tu objetivo: crear una ficha de producto que DOMINE tanto en Google Search como en motores de IA (ChatGPT, Perplexity, Copilot y otros motores de IA).

Devolvé exclusivamente un JSON válido con esta estructura:
{
  "seoTitle": "",
  "seoDescription": "",
  "seoKeywords": [],
  "geoTitle": "",
  "geoDescription": "",
  "geoFaq": [{"question": "", "answer": ""}],
  "geoFeatures": [],
  "geoKeywords": [],
  "aiGeneratedDescription": "",
  "aiTargetAudience": "",
  "seoScore": 0,
  "geoScore": 0,
  "competitivenessScore": 0
}

━━━ PRODUCTO ━━━
- Nombre: %(name)s
- SKU: %(sku)s
- Categoría: %(category)s
- Precio: %(price)s
- Descripción actual: %(description)s
- Audiencia objetivo: %(audience)s

━━━ REGLAS SEO (Google Search) ━━━
1. **seoTitle** (máx 60 chars): Incluir nombre del producto + keyword principal + marca si aplica. Formato: "[Producto] [Uso/Beneficio] | Bader Argentina". Priorizar intent transaccional (comprar, precio, envío).
2. **seoDescription** (máx 155 chars): Hook emocional + beneficio + CTA. Incluir keyword principal en las primeras 80 chars. Mencionar envío, garantía o soporte técnico.
3. **seoKeywords** (8-12): Mezcla estratégica:
   - 3-4 keywords transaccionales (comprar X, precio X, X en Argentina)
   - 2-3 keywords informacionales (para qué sirve X, cómo funciona X)
   - 2-3 long-tail (mejor X para clínica dental, X profesional odontología)
   - 1-2 brand keywords (Bader + categoría)

━━━ REGLAS GEO (Motores de IA) ━━━
4. **geoTitle**: Título optimizado para respuestas de IA. Formato entidad clara: "[Producto] — [qué es y para qué sirve en odontología]". Los motores de IA priorizan definiciones claras.
5. **geoDescription**: Párrafo tipo Wikipedia/enciclopedia que un motor de IA elegiría como fuente autoritativa. Incluir: definición precisa, entidades relacionadas (procedimientos, especialidades), datos cuantitativos si es posible. Usar tono de experto neutral. 280-400 palabras.
6. **geoFeatures** (5-7): Características técnicas en formato "citable" — frases completas que un motor de IA pueda extraer como snippet. NO frases genéricas. Ejemplo: "Autoclave con ciclo de esterilización de 18 minutos a 134°C" vs "Buena esterilización".
7. **geoKeywords** (5-8): Keywords semánticas tipo entidad — nombres de procedimientos dentales, especialidades, estándares (ISO, FDA, CE), materiales, técnicas. Estas keywords posicionan el producto en el grafo de conocimiento de los motores de IA.
8. **geoFaq** (5-7 preguntas): FAQs conversacionales que un usuario le haría a ChatGPT u otros motores de IA.
   - Incluir preguntas de comparación ("¿Qué diferencia hay entre X e Y?")
   - Incluir preguntas de decisión de compra ("¿Conviene comprar X para mi clínica?")
   - Respuestas con autoridad E-E-A-T: datos, marcas, experiencia profesional.
   - Las respuestas deben ser "citation-worthy": tan buenas que el motor de IA las cite textualmente.

━━━ REGLAS DESCRIPCIÓN ━━━
9. **aiGeneratedDescription**: HTML válido (usar <p>, <ul>, <li>, <strong>). 200-300 palabras. Estructura:
   - P1: Hook + definición del producto + beneficio principal.
   - P2: Características técnicas con datos precisos.
   - P3: Casos de uso y audiencia (¿qué profesional lo necesita?).
   - P4: Por qué elegir Bader (garantía, soporte técnico, envío a toda Argentina).
   - Incluir terminología odontológica específica y precisa.

━━━ REGLAS DE SCORING ━━━
10. **seoScore** (0-100): Evaluar: keywords en title (25pts), meta description con CTA (20pts), keywords long-tail (20pts), coherencia semántica (20pts), datos técnicos (15pts).
11. **geoScore** (0-100): Evaluar: citabilidad de descripción (25pts), FAQ conversacionales (25pts), entidades nombradas (20pts), features cuantitativos (15pts), autoridad E-E-A-T (15pts).
12. **competitivenessScore** (0-100): Evaluar: diferenciación de mercado (30pts), propuesta de valor clara (25pts), keywords competitivas (25pts), cobertura de nichos (20pts).
13. **aiTargetAudience**: Devolver EXACTAMENTE uno de: "clinicas", "laboratorios", "estudiantes", "general".

━━━ IDIOMA ━━━
- Español argentino natural. Usar "vos" implícito pero tono profesional.
- NO inventar datos clínicos falsos. Si no tenés datos del producto, generá contenido basado en la categoría.
""" % {
            "name": product.name,
            "sku": product.default_code or "N/A",
            "category": (product.public_categ_ids[:1].name if product.public_categ_ids else "Sin categoría"),
            "price": product.list_price,
            "description": product.description_sale or product.description or "Sin descripción",
            "audience": target_audience or "clinicas",
        }
        analysis = self._openai_json(prompt)
        analysis.setdefault("aiTargetAudience", target_audience or "clinicas")
        self.save_seo_payload(product, analysis)
        return product.bpi_build_payload()["seoData"]

    @api.model
    def _validate_external_url(self, raw_url):
        clean_url = (raw_url or "").strip()
        parsed = urlparse(clean_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise UserError(_("Ingresa una URL externa válida."))

        hostname = (parsed.hostname or "").strip().lower()
        if not hostname:
            raise UserError(_("Ingresa una URL externa válida."))
        if hostname in ("localhost", "0.0.0.0") or hostname.endswith(".local") or hostname.endswith(".internal"):
            raise UserError(_("La URL apunta a una red privada o interna y no está permitida."))

        try:
            host_entries = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
        except socket.gaierror as error:
            raise UserError(_("No se pudo resolver el dominio indicado.")) from error

        for entry in host_entries:
            ip_address = ipaddress.ip_address(entry[4][0])
            if (
                ip_address.is_private
                or ip_address.is_loopback
                or ip_address.is_link_local
                or ip_address.is_multicast
                or ip_address.is_reserved
                or ip_address.is_unspecified
            ):
                raise UserError(_("La URL apunta a una red privada o interna y no está permitida."))

        return clean_url

    @api.model
    def _dashboard_base_domain(self):
        return []

    @api.model
    def _dashboard_search_domain(self, search):
        term = (search or "").strip()
        if not term:
            return []
        return expression.OR(
            [
                [("name", "ilike", term)],
                [("default_code", "ilike", term)],
                [("bpi_brand_name", "ilike", term)],
                [("public_categ_ids.name", "ilike", term)],
            ]
        )

    @api.model
    def _dashboard_tab_domain(self, tab):
        active_sale_domain = [("active", "=", True), ("sale_ok", "=", True)]
        if tab == "new":
            return expression.AND([active_sale_domain, [("website_published", "=", False)]])
        if tab == "discontinued":
            return expression.OR([[("active", "=", False)], [("sale_ok", "=", False)]])
        return active_sale_domain

    @api.model
    def _dashboard_stats(self):
        PT = self.env["product.template"]
        base_domain = self._dashboard_base_domain()
        active_domain = expression.AND([base_domain, [('active', '=', True)]])
        return {
            "total": PT.search_count(active_domain),
            "published": PT.search_count(expression.AND([active_domain, [("website_published", "=", True)]])),
            "featured": PT.search_count(expression.AND([active_domain, [("bpi_featured", "=", True)]])),
            "pending": PT.search_count(expression.AND([active_domain, [("website_published", "=", False)]])),
        }

    @api.model
    def dashboard_payload(self, tab="all", search="", page=1, limit=40):
        use_inactive = (tab == "discontinued")
        product_model = self.env["product.template"]
        if use_inactive:
            product_model = product_model.with_context(active_test=False)
        exchange_rate = product_model._bpi_exchange_rate()
        safe_page = max(int(page or 1), 1)
        safe_limit = min(max(int(limit or 40), 1), 120)
        base_domain = self._dashboard_base_domain()
        query_domain = expression.AND([base_domain, self._dashboard_tab_domain(tab), self._dashboard_search_domain(search)])
        total_rows = product_model.search_count(query_domain)
        if total_rows and (safe_page - 1) * safe_limit >= total_rows:
            safe_page = max(1, int(math.ceil(total_rows / float(safe_limit))))
        offset = (safe_page - 1) * safe_limit
        products = product_model.search(
            query_domain,
            order="website_sequence asc, name asc, id desc",
            offset=offset,
            limit=safe_limit,
        )
        rows = [product.bpi_dashboard_payload(exchange_rate=exchange_rate) for product in products]
        page_count = max(1, int(math.ceil(total_rows / float(safe_limit))) if total_rows else 1)

        PT = self.env["product.template"]
        PT_inactive = PT.with_context(active_test=False)
        return {
            "products": rows,
            "exchangeRate": exchange_rate,
            "stats": self._dashboard_stats(),
            "tabCounts": {
                "all": PT.search_count(expression.AND([base_domain, self._dashboard_tab_domain("all")])),
                "new": PT.search_count(expression.AND([base_domain, self._dashboard_tab_domain("new")])),
                "discontinued": PT_inactive.search_count(expression.AND([base_domain, self._dashboard_tab_domain("discontinued")])),
            },
            "pager": {
                "page": safe_page,
                "pageCount": page_count,
                "total": total_rows,
                "limit": safe_limit,
                "hasNext": safe_page < page_count,
                "hasPrevious": safe_page > 1,
            },
        }

    @api.model
    def sync_catalog(self, tab="all", search="", page=1, limit=40):
        return self.dashboard_payload(tab=tab, search=search, page=page, limit=limit)

    @api.model
    def update_exchange_rate(self, exchange_rate):
        value = int(float(exchange_rate or 1650))
        self.env["ir.config_parameter"].sudo().set_param("bader_product_intelligence.exchange_rate", value)
        return {"success": True, "exchangeRate": value}

    @api.model
    def update_product(self, product, values):
        product.ensure_one()
        values = values or {}
        write_values = {}
        if "name" in values:
            write_values["name"] = (values.get("name") or "").strip() or product.name
        if "sku" in values:
            write_values["default_code"] = (values.get("sku") or "").strip() or False
        if "slug" in values:
            write_values["bpi_slug"] = product._bpi_generate_slug_value(values.get("slug"))
        if "brand" in values:
            write_values["bpi_brand_name"] = (values.get("brand") or "Bader").strip() or "Bader"
        if "priceUsd" in values:
            write_values["list_price"] = float(values.get("priceUsd") or 0.0)
        if "previousPriceUsd" in values:
            write_values["bpi_previous_price"] = float(values.get("previousPriceUsd") or 0.0)
        if "isPublished" in values:
            write_values["website_published"] = bool(values.get("isPublished"))
        if "featured" in values:
            write_values["bpi_featured"] = bool(values.get("featured"))

        category_id = values.get("categoryId")
        if category_id:
            write_values["public_categ_ids"] = [(6, 0, [int(category_id)])]
        elif "categoryId" in values:
            write_values["public_categ_ids"] = [(5, 0, 0)]

        if write_values:
            product.write(write_values)

        if "costUsd" in values:
            cost_value = float(values.get("costUsd") or 0.0)
            if product.product_variant_id:
                product.product_variant_id.write({"standard_price": cost_value})
            else:
                product.write({"standard_price": cost_value})

        if "description" in values:
            description_value = values.get("description") or False
            product.write(
                {
                    "description_sale": self._description_plain_text(description_value),
                    "bpi_ai_generated_description": description_value,
                }
            )

        return product.bpi_build_payload()

    @api.model
    def generate_content(self, product, tone="profesional", audience="clinicas"):
        product.ensure_one()
        prompt = """Sos Nancy AI, copywriter experta en e-commerce dental para Bader Argentina — importador líder de equipamiento e insumos odontológicos en Argentina.

Tu misión: crear contenido de producto que CONVIERTE visitantes en compradores Y que los motores de IA (ChatGPT, Perplexity) citen como fuente autoritativa.

Devolvé solo JSON válido:
{
  "name": "",
  "description": ""
}

━━━ PRODUCTO ━━━
- Nombre actual: %(name)s
- SKU: %(sku)s
- Categoría: %(category)s
- Precio USD: %(price)s
- Descripción actual: %(description)s
- Tono: %(tone)s
- Audiencia: %(audience)s

━━━ REGLAS PARA "name" ━━━
- Mantener el nombre original si ya es claro y descriptivo.
- Solo ajustar si falta claridad: agregar uso principal o material si mejora la comprensión.
- NO cambiar marca ni modelo. NO agregar adjetivos de marketing vacíos.
- Máximo 80 caracteres.

━━━ REGLAS PARA "description" ━━━
Generar descripción en HTML válido. Extensión: 180-280 palabras. Estructura obligatoria:

**Párrafo 1 — Hook + Definición** (2-3 oraciones):
- Empezar con el beneficio principal del producto, NO con "Este producto es...".
- Definir qué es y para qué procedimiento dental se usa.
- Incluir al menos 1 entidad dental específica (procedimiento, técnica, especialidad).

**Párrafo 2 — Características Técnicas** (usar <ul><li>):
- 4-6 características con datos precisos (medidas, materiales, certificaciones).
- Si no tenés datos exactos, describir la categoría general con precisión técnica.
- Usar terminología odontológica correcta.

**Párrafo 3 — Casos de Uso y Audiencia** (2-3 oraciones):
- ¿Quién lo necesita? (odontólogo general, especialista, laboratorio, estudiante)
- ¿En qué procedimiento específico se usa?
- Tono de recomendación experta.

**Párrafo 4 — Por qué Bader** (1-2 oraciones):
- Mencionar: soporte técnico, envío a toda Argentina, garantía.
- Cerrar con CTA implícito.

━━━ PRINCIPIOS DE CALIDAD ━━━
- Tono: %(tone)s pero siempre profesional y creíble.
- Español argentino natural.
- NO inventar especificaciones clínicas que no surjan del contexto.
- Usar HTML semántico: <p>, <ul>, <li>, <strong>.
- El contenido debe ser "citation-worthy" — tan preciso que un motor de IA lo citaría.
- Evitar frases genéricas ("la mejor calidad", "excelente rendimiento"). Preferir datos concretos.
""" % {
            "name": product.name,
            "sku": product.default_code or "N/A",
            "category": self._public_category_label(product),
            "price": product.list_price,
            "description": product.description_sale or product.description or "Sin descripción",
            "tone": tone or "profesional",
            "audience": audience or "clinicas",
        }
        response = self._openai_json(prompt)
        description_html = response.get("description") or product.bpi_ai_generated_description or product.description_sale or product.description or ""
        return {
            "name": response.get("name") or product.name,
            "description": self._description_plain_text(description_html) or "",
            "descriptionHtml": description_html,
            "tone": tone or "profesional",
            "audience": audience or "clinicas",
        }

    @api.model
    def _save_faq_items(self, product, faqs):
        product.bpi_faq_ids.unlink()
        commands = []
        for index, faq in enumerate(faqs or []):
            question = (faq or {}).get("question", "").strip()
            answer = (faq or {}).get("answer", "").strip()
            if question and answer:
                commands.append(
                    (
                        0,
                        0,
                        {
                            "question": question,
                            "answer": answer,
                            "sequence": index * 10 + 10,
                        },
                    )
                )
        if commands:
            product.write({"bpi_faq_ids": commands})

    @api.model
    def save_content(self, product, values):
        product.ensure_one()
        values = values or {}
        write_values = {}
        if "name" in values:
            write_values["name"] = (values.get("name") or "").strip() or product.name
        if "description" in values:
            description_value = values.get("description") or False
            write_values["description_sale"] = self._description_plain_text(description_value)
            write_values["bpi_ai_generated_description"] = description_value
        if "audience" in values:
            write_values["bpi_ai_target_audience"] = values.get("audience") or "clinicas"
        if "tone" in values:
            write_values["bpi_ai_tone"] = values.get("tone") or "profesional"
        if write_values:
            product.write(write_values)
        if "faqs" in values:
            self._save_faq_items(product, values.get("faqs") or [])
        return product.bpi_build_payload()

    @api.model
    def generate_faq(self, product, audience="clinicas"):
        product.ensure_one()
        prompt = """Sos Nancy AI, experta en SEO y GEO dental para Bader Argentina.

Tu misión: crear FAQs que posicionen en Google (People Also Ask / FAQ Rich Snippets) Y que los motores de IA citen como respuesta autoritativa.

Devolvé solo JSON válido:
{
  "faqs": [
    {"question": "", "answer": ""}
  ]
}

━━━ PRODUCTO ━━━
- Nombre: %(name)s
- SKU: %(sku)s
- Categoría: %(category)s
- Descripción: %(description)s
- Audiencia: %(audience)s

━━━ REGLAS FAQ ━━━
Generar entre 5 y 7 FAQs. Cada FAQ debe cubrir una etapa diferente del buyer journey:

1. **Pregunta de definición**: "¿Qué es [producto] y para qué se usa?" — respuesta tipo enciclopedia, precisa y citable.
2. **Pregunta de decisión de compra**: "¿Conviene comprar [producto] para mi clínica/laboratorio?" — respuesta con criterios objetivos.
3. **Pregunta de comparación**: "¿Qué diferencia hay entre [producto] y [alternativa]?" — respuesta que posiciona el producto.
4. **Pregunta técnica/clínica**: "¿Cómo se usa [producto] en [procedimiento]?" — respuesta con autoridad profesional.
5. **Pregunta de especificaciones**: "¿Qué incluye el [producto]?" o "¿Cuáles son las medidas/materiales?" — respuesta con datos concretos.
6-7. **Preguntas de soporte/logística**: sobre envío, garantía, soporte técnico de Bader. Opcional.

━━━ REGLAS DE CALIDAD ━━━
- Las preguntas deben sonar naturales — como las haría un profesional dental real buscando en Google o preguntando a ChatGPT.
- Respuestas entre 40 y 80 palabras. Concisas pero completas.
- Incluir datos técnicos precisos cuando sea posible.
- NO inventar especificaciones que no surjan del contexto.
- Cada respuesta debe empezar con la información más importante (pirámide invertida).
- Usar español argentino profesional.
- Las respuestas deben ser "citation-worthy" — que un motor de IA las cite textualmente.
""" % {
            "name": product.name,
            "sku": product.default_code or "N/A",
            "category": self._public_category_label(product),
            "description": product.description_sale or product.description or "Sin descripción",
            "audience": audience or "clinicas",
        }
        response = self._openai_json(prompt)
        return {"faqs": response.get("faqs") or []}

    @api.model
    def save_category(self, product, values):
        product.ensure_one()
        values = values or {}
        product.write(
            {
                "bpi_intelligent_niches": self._normalize_category_niches(values.get("niches") or []),
                "bpi_intelligent_type": self._normalize_taxonomy_choice(
                    values.get("type"),
                    self._CATEGORY_TYPE_ALLOWED,
                    self._CATEGORY_TYPE_ALIASES,
                    default=False,
                ),
                "bpi_intelligent_subcategory": self._normalize_taxonomy_choice(
                    values.get("subcategory"),
                    self._CATEGORY_SUBCATEGORY_ALLOWED,
                    self._CATEGORY_SUBCATEGORY_ALIASES,
                    default=False,
                ),
                "bpi_intelligent_category_manual": bool(values.get("manualMode")),
            }
        )
        category_id = values.get("categoryId")
        if category_id:
            product.write({"public_categ_ids": [(6, 0, [int(category_id)])]})
        return product.bpi_build_payload()

    @api.model
    def reclassify_category(self, product):
        product.ensure_one()
        prompt = """Sos Nancy AI. Clasifica un producto dental para el catalogo de Bader Argentina.

Devolve solo JSON valido:
{
  "niches": [],
  "type": "",
  "subcategory": ""
}

Producto:
- Nombre: %(name)s
- Categoria actual: %(category)s
- Descripcion: %(description)s

Reglas:
- niches debe contener solo estos valores exactos: clinica, laboratorio, estudiantes.
- type debe ser EXACTAMENTE uno de estos valores: consumible, equipo, instrumental, mobiliario, protesis, ortodoncia, endodoncia, cirugia, higiene, radiologia, otro.
- subcategory debe ser EXACTAMENTE uno de estos valores: aislamiento, adhesivos, anestesia, blanqueamiento, cementos, composites, desechables, endodoncia, esterilizacion, fresas, higiene, implantes, impresion, instrumental_clinico, laboratorio, matrices_bandas, ortodoncia, profilaxis, protesis, radiologia, restauracion, otro.
- Para clamps, grapas, dique de goma o aislamiento absoluto usa type "instrumental" y subcategory "aislamiento".
- No devuelvas textos libres como "Clamps" o "Clamp para dique de goma"; usa siempre los codigos exactos anteriores.
""" % {
            "name": product.name,
            "category": self._public_category_label(product, "Sin categoria"),
            "description": product.description_sale or product.description or "Sin descripcion",
        }
        response = self._openai_json(prompt)
        values = {
            "niches": self._normalize_category_niches(response.get("niches") or []),
            "type": self._normalize_taxonomy_choice(
                response.get("type"),
                self._CATEGORY_TYPE_ALLOWED,
                self._CATEGORY_TYPE_ALIASES,
                default="otro",
            ),
            "subcategory": self._normalize_taxonomy_choice(
                response.get("subcategory"),
                self._CATEGORY_SUBCATEGORY_ALLOWED,
                self._CATEGORY_SUBCATEGORY_ALIASES,
                default="otro",
            ),
            "manualMode": False,
        }
        return self.save_category(product, values)

    @api.model
    def generate_image(self, product, prompt, reference_tokens=None, style="professional", use_pro=False, uploaded_ref=""):
        product.ensure_one()
        image_model = self._get_config("bader_product_intelligence.openai_image_model", "gpt-image-2")
        image_edit_model = self._get_config("bader_product_intelligence.openai_image_edit_model", "gpt-image-1.5")
        style_map = {
            "professional": "fotografía de producto profesional, fondo blanco limpio, iluminación de estudio",
            "lifestyle": "escena lifestyle en consultorio dental moderno",
            "artistic": "composición artística premium y llamativa",
            "minimalist": "composición minimalista blanca y elegante",
        }
        references = self._reference_images(product, reference_tokens)
        uploaded_image = self._data_url_to_openai_image(uploaded_ref, "uploaded-reference.png")
        if uploaded_image:
            references.append(uploaded_image)

        full_prompt = """Generá una imagen publicitaria para Bader Argentina.
Producto: %(name)s
Pedido: %(prompt)s
Estilo: %(style)s
Reglas:
- Mantener identidad del producto.
- Si hay imágenes de referencia, usarlas para preservar forma, marca, color y proporciones.
- Aspecto premium para e-commerce.
- Solo una imagen final.
- Fondo limpio y look comercial.
""" % {
            "name": product.name,
            "prompt": prompt,
            "style": style_map.get(style, style_map["professional"]),
        }
        quality = "high" if use_pro else "medium"
        if references:
            files = [
                ("image[]", (image["filename"], image["raw"], image["mime_type"]))
                for image in references[:8]
            ]
            payload = self._openai_request(
                "images/edits",
                files=files,
                data={
                    "model": image_edit_model,
                    "prompt": full_prompt,
                    "size": "1024x1024",
                    "quality": quality,
                    "output_format": "png",
                },
                timeout=180,
            )
        else:
            payload = self._openai_request(
                "images/generations",
                json_payload={
                    "model": image_model,
                    "prompt": full_prompt,
                    "size": "1024x1024",
                    "quality": quality,
                    "output_format": "png",
                },
                timeout=180,
            )
        inline = self._extract_openai_image(payload)
        return {
            "previewUrl": "data:%s;base64,%s" % (inline.get("mimeType") or "image/png", inline["data"]),
            "mimeType": inline.get("mimeType") or "image/png",
            "base64": inline["data"],
        }

    @api.model
    def save_generated_image(self, product, data_url, prompt):
        product.ensure_one()
        if not data_url or "," not in data_url:
            raise UserError(_("No llegó una imagen válida para guardar."))
        meta, encoded = data_url.split(",", 1)
        mime_type = "image/png"
        if ";" in meta and ":" in meta:
            mime_type = meta.split(":", 1)[1].split(";", 1)[0]
        image = self.env["bpi.product.image"].create(
            {
                "product_tmpl_id": product.id,
                "name": _("Variación IA %s") % fields.Datetime.now(),
                "image_1920": encoded,
                "mime_type": mime_type,
                "prompt": prompt,
                "image_type": "ai_generated",
                "state": "approved",
                "sequence": (max(product.bpi_image_ids.mapped("sequence")) + 10) if product.bpi_image_ids else 10,
            }
        )
        return {
            "id": image.id,
            "imageUrl": "/web/image/bpi.product.image/%s/image_1920" % image.id,
        }

    @api.model
    def add_image_from_url(self, product, image_url):
        product.ensure_one()
        clean_url = self._validate_external_url(image_url)
        try:
            response = requests.get(clean_url, timeout=90)
            response.raise_for_status()
        except requests.RequestException as error:
            _logger.exception("Unable to download image from %s", clean_url)
            raise UserError(_("No se pudo descargar la imagen externa.")) from error

        mime_type = (response.headers.get("Content-Type") or "image/png").split(";", 1)[0]
        if not mime_type.startswith("image/"):
            raise UserError(_("La URL indicada no devolvió una imagen válida."))
        content_length = int(response.headers.get("Content-Length") or 0)
        if content_length and content_length > 10 * 1024 * 1024:
            raise UserError(_("La imagen supera el tamaño máximo permitido de 10 MB."))
        if len(response.content or b"") > 10 * 1024 * 1024:
            raise UserError(_("La imagen supera el tamaño máximo permitido de 10 MB."))

        encoded = base64.b64encode(response.content).decode()
        image = self.env["bpi.product.image"].create(
            {
                "product_tmpl_id": product.id,
                "name": _("Imagen externa %s") % fields.Datetime.now(),
                "image_1920": encoded,
                "mime_type": mime_type,
                "prompt": _("Importada desde URL"),
                "image_type": "reference",
                "state": "approved",
                "sequence": (max(product.bpi_image_ids.mapped("sequence")) + 10) if product.bpi_image_ids else 10,
            }
        )
        return {
            "id": image.id,
            "imageUrl": "/web/image/bpi.product.image/%s/image_1920" % image.id,
        }

    @api.model
    def delete_image(self, image):
        image.unlink()
        return True

    @api.model
    def _strip_search_html(self, raw_value):
        text = re.sub(r"<[^>]+>", " ", raw_value or "")
        text = unescape(text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @api.model
    def _competitor_domain(self, raw_url):
        parsed = urlparse(raw_url or "")
        return (parsed.netloc or "").lower().replace("www.", "")

    @api.model
    def _decode_duckduckgo_url(self, raw_href):
        href = unescape(raw_href or "").strip()
        if href.startswith("//"):
            href = "https:" + href
        parsed = urlparse(href)
        if parsed.netloc.endswith("duckduckgo.com") or parsed.path.startswith("/l/"):
            uddg = parse_qs(parsed.query).get("uddg") or []
            if uddg:
                return unescape(uddg[0])
        return href

    @api.model
    def _normalize_search_url(self, raw_url):
        parsed = urlparse(raw_url or "")
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return ""
        fragmentless = parsed._replace(fragment="")
        return fragmentless.geturl().strip()

    @api.model
    def _search_candidate_allowed(self, raw_url):
        clean_url = self._normalize_search_url(raw_url)
        if not clean_url:
            return False
        parsed = urlparse(clean_url)
        domain = self._competitor_domain(clean_url)
        if not domain:
            return False
        blocked_domains = (
            "bader.com.ar",
            "qas.bader.com.ar",
            "google.",
            "bing.",
            "duckduckgo.",
            "facebook.com",
            "instagram.com",
            "youtube.com",
            "youtu.be",
            "tiktok.com",
            "pinterest.",
            "linkedin.com",
            "scribd.com",
        )
        if any(blocked in domain for blocked in blocked_domains):
            return False
        blocked_ext = (".pdf", ".jpg", ".jpeg", ".png", ".webp", ".gif", ".zip", ".doc", ".docx", ".xls", ".xlsx")
        return not parsed.path.lower().endswith(blocked_ext)

    @api.model
    def _discovery_tokens(self, *values):
        stopwords = {
            "para", "con", "sin", "por", "las", "los", "del", "una", "uno", "the", "and",
            "bader", "argentina", "odontologia", "odontologico", "odontologica", "dental",
            "producto", "comprar", "precio", "envio", "acero", "inoxidable",
        }
        tokens = []
        for value in values:
            text = self._taxonomy_key(value)
            for token in text.split("_"):
                if len(token) >= 3 and token not in stopwords and token not in tokens:
                    tokens.append(token)
        return tokens

    @api.model
    def _build_competitor_queries(self, product):
        name = re.sub(r"\bBader\b", "", product.name or "", flags=re.I).strip() or (product.name or "")
        category = self._public_category_label(product, "")
        description = self._description_plain_text(product.description_sale or product.description or "") or ""
        numbers = []
        for raw_number in re.findall(r"\b\d+[A-Za-z]?\b", name):
            if raw_number not in numbers:
                numbers.append(raw_number)

        text_key = self._taxonomy_key("%s %s %s %s" % (name, category, product.bpi_intelligent_subcategory or "", description[:300]))
        category_terms = []
        if any(term in text_key for term in ("clamp", "grapa", "dique", "aislamiento")):
            category_terms = ["clamp", "dique de goma", "aislamiento absoluto"]
        elif any(term in text_key for term in ("fresa", "fresas")):
            category_terms = ["fresa dental"]
        elif "adhesivo" in text_key:
            category_terms = ["adhesivo dental"]
        elif "composite" in text_key:
            category_terms = ["composite dental"]
        elif "cemento" in text_key:
            category_terms = ["cemento dental"]
        elif "anestesia" in text_key or "anestesico" in text_key:
            category_terms = ["anestesia dental"]
        else:
            category_terms = [category or "insumo odontologico"]

        queries = [
            '"%s" odontologia Argentina' % name,
            '"%s" dental comprar Argentina' % name,
            "%s %s Argentina odontologia" % (name, " ".join(category_terms[:2])),
        ]
        for number in numbers[:2]:
            if any(term in text_key for term in ("clamp", "grapa", "dique", "aislamiento")):
                queries.append('"clamp %s" "dique de goma" Argentina' % number)
                queries.append('"grapa %s" odontologia Argentina' % number)
            else:
                queries.append('"%s" "%s" Argentina' % (number, category_terms[0]))

        seen = set()
        normalized = []
        for query in queries:
            query = re.sub(r"\s+", " ", query).strip()
            key = query.lower()
            if query and key not in seen:
                normalized.append(query)
                seen.add(key)
        return normalized[:5]

    @api.model
    def _duckduckgo_search(self, query, limit=8):
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; BaderProductIntelligence/1.0; +https://bader.com.ar)",
            "Accept-Language": "es-AR,es;q=0.9,en;q=0.5",
        }
        try:
            response = requests.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query},
                headers=headers,
                timeout=15,
            )
            if response.status_code >= 400 or "result__a" not in response.text:
                response = requests.post(
                    "https://lite.duckduckgo.com/lite/",
                    data={"q": query},
                    headers=headers,
                    timeout=15,
                )
            response.raise_for_status()
        except requests.RequestException as error:
            _logger.warning("Competitor search failed for query %s: %s", query, error)
            return []

        html_text = response.text or ""
        results = []
        result_matches = list(re.finditer(r'<a[^>]+class=["\'][^"\']*(?:result__a|result-link)[^"\']*["\'][^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html_text, re.I | re.S))
        for index, match in enumerate(result_matches):
            raw_url = self._decode_duckduckgo_url(match.group(1))
            clean_url = self._normalize_search_url(raw_url)
            if not self._search_candidate_allowed(clean_url):
                continue
            title = self._strip_search_html(match.group(2))
            next_start = result_matches[index + 1].start() if index + 1 < len(result_matches) else match.end() + 2200
            block = html_text[match.end():next_start]
            snippet_match = re.search(
                r'<(?:a|div|td)[^>]+class=["\'][^"\']*(?:result__snippet|result-snippet)[^"\']*["\'][^>]*>(.*?)</(?:a|div|td)>',
                block,
                re.I | re.S,
            )
            snippet = self._strip_search_html(snippet_match.group(1)) if snippet_match else ""
            domain = self._competitor_domain(clean_url)
            if title or snippet:
                results.append({
                    "name": title[:160] or domain,
                    "url": clean_url,
                    "domain": domain,
                    "description": snippet[:360],
                    "sourceQuery": query,
                    "source": "duckduckgo",
                })
            if len(results) >= limit:
                break
        return results

    @api.model
    def _extract_estimated_price(self, text):
        match = re.search(r"(?:\$|ARS\s*)\s?([\d\.]{2,}(?:,\d{1,2})?)", text or "", re.I)
        return match.group(0).strip() if match else ""

    @api.model
    def _candidate_compatibility_score(self, product, candidate):
        product_text = "%s %s %s %s" % (
            product.name or "",
            self._public_category_label(product, ""),
            product.bpi_intelligent_type or "",
            product.bpi_intelligent_subcategory or "",
        )
        candidate_text = "%s %s %s %s" % (
            candidate.get("name") or "",
            candidate.get("description") or "",
            candidate.get("domain") or "",
            candidate.get("url") or "",
        )
        product_tokens = self._discovery_tokens(product_text)
        candidate_tokens = set(self._discovery_tokens(candidate_text))
        score = 0
        score += min(25, len([token for token in product_tokens if token in candidate_tokens]) * 7)

        product_key = self._taxonomy_key(product_text)
        candidate_key = self._taxonomy_key(candidate_text)
        for number in re.findall(r"\b\d+[A-Za-z]?\b", product.name or ""):
            number_key = self._taxonomy_key(number)
            if re.search(r"(?:^|_)n?%s(?:_|$)" % re.escape(number_key), candidate_key) or number_key in candidate_key.split("_"):
                score += 28
                break

        if any(term in product_key for term in ("clamp", "grapa", "dique", "aislamiento")):
            if any(term in candidate_key for term in ("clamp", "clamps", "grapa", "dique", "aislamiento")):
                score += 25
            if "molar" in candidate_key or "molares" in candidate_key:
                score += 5
        if "odont" in candidate_key or "dental" in candidate_key:
            score += 8
        domain = candidate.get("domain") or ""
        if domain.endswith(".com.ar") or "argentina" in candidate_key:
            score += 8
        if any(hint in (candidate.get("url") or "").lower() for hint in ("producto", "productos", "product", "articulo", "prod", "item")):
            score += 8
        if any(term in domain for term in ("dental", "odont", "insumos", "dentista")):
            score += 8
        if any(term in candidate_key for term in ("catalogo", "categoria", "blog", "nomenclatura", "pdf", "documento")):
            score -= 18
        if "bader" in domain or "bader" in candidate_key:
            score -= 100
        return max(0, min(100, int(score)))

    @api.model
    def _fallback_rank_competitors(self, candidates, limit):
        ranked = []
        per_domain = {}
        for candidate in sorted(candidates, key=lambda item: item.get("deterministicScore", 0), reverse=True):
            domain = candidate.get("domain") or ""
            if per_domain.get(domain, 0) >= 2:
                continue
            per_domain[domain] = per_domain.get(domain, 0) + 1
            score = int(candidate.get("deterministicScore") or 0)
            ranked.append({
                "name": candidate.get("name") or domain or "Competidor",
                "url": candidate.get("url"),
                "domain": domain,
                "description": candidate.get("description") or domain,
                "estimatedPrice": candidate.get("estimatedPrice") or "",
                "relevanceScore": score,
                "compatibilityLevel": "direct" if score >= 75 else ("compatible" if score >= 55 else "generic"),
                "matchReason": candidate.get("matchReason") or _("Resultado real encontrado en buscador y filtrado por similitud de nombre/categoría."),
                "sourceQuery": candidate.get("sourceQuery") or "",
                "source": candidate.get("source") or "duckduckgo",
            })
            if len(ranked) >= limit:
                break
        return ranked

    @api.model
    def _ai_rank_real_competitor_candidates(self, product, candidates, limit):
        if not candidates:
            return []
        candidate_payload = []
        by_url = {}
        for index, candidate in enumerate(candidates, start=1):
            url = candidate.get("url")
            if not url:
                continue
            by_url[url] = candidate
            candidate_payload.append({
                "id": index,
                "url": url,
                "domain": candidate.get("domain"),
                "title": candidate.get("name"),
                "snippet": candidate.get("description"),
                "deterministicScore": candidate.get("deterministicScore"),
                "sourceQuery": candidate.get("sourceQuery"),
            })
        prompt = """Sos Nancy AI, analista competitivo dental para Bader Argentina.

Tenés candidatos REALES obtenidos de un buscador. Tu tarea es seleccionar solo productos o páginas de producto que sean competidores directos o compatibles del producto Bader. NO inventes URLs: solo podés devolver URLs que estén exactamente en CANDIDATOS.

Devolvé JSON válido:
{
  "competitors": [
    {
      "url": "",
      "name": "",
      "description": "",
      "estimatedPrice": "",
      "relevanceScore": 0,
      "compatibilityLevel": "direct|compatible|generic",
      "matchReason": ""
    }
  ]
}

Criterios:
- Directo: mismo tipo de producto, mismo uso clínico y, si aplica, mismo número/modelo/medida.
- Compatible: producto equivalente para el mismo procedimiento aunque cambie marca/modelo.
- Generic: categoría o listado amplio; usar solo si no hay suficientes directos.
- Priorizá tiendas odontológicas y marketplaces argentinos con páginas de producto reales.
- Penalizá documentos, blogs, PDFs, páginas institucionales o categorías demasiado amplias.
- relevanceScore de 0 a 100.
- Máximo %(limit)s resultados.

Producto Bader:
- Nombre: %(name)s
- SKU: %(sku)s
- Categoría: %(category)s
- Tipo: %(type)s
- Subcategoría: %(subcategory)s
- Descripción: %(description)s

CANDIDATOS:
%(candidates)s
""" % {
            "limit": limit,
            "name": product.name or "",
            "sku": product.default_code or "",
            "category": self._public_category_label(product, "Sin categoría"),
            "type": product.bpi_intelligent_type or "",
            "subcategory": product.bpi_intelligent_subcategory or "",
            "description": (self._description_plain_text(product.description_sale or product.description or "") or "")[:1200],
            "candidates": json.dumps(candidate_payload[:30], ensure_ascii=False),
        }
        try:
            response = self._openai_json(prompt)
        except UserError:
            _logger.info("OpenAI competitor rerank unavailable; using deterministic ranking")
            return self._fallback_rank_competitors(candidates, limit)

        ranked = []
        used = set()
        for item in response.get("competitors") or []:
            url = item.get("url")
            candidate = by_url.get(url)
            if not candidate or url in used:
                continue
            used.add(url)
            score = item.get("relevanceScore") or candidate.get("deterministicScore") or 0
            try:
                score = int(float(score))
            except Exception:
                score = int(candidate.get("deterministicScore") or 0)
            ranked.append({
                "name": item.get("name") or candidate.get("name") or candidate.get("domain"),
                "url": url,
                "domain": candidate.get("domain") or self._competitor_domain(url),
                "description": item.get("description") or candidate.get("description") or "",
                "estimatedPrice": item.get("estimatedPrice") or candidate.get("estimatedPrice") or "",
                "relevanceScore": max(0, min(100, score)),
                "compatibilityLevel": item.get("compatibilityLevel") or ("direct" if score >= 75 else "compatible"),
                "matchReason": item.get("matchReason") or "Coincidencia validada sobre resultados reales de búsqueda.",
                "sourceQuery": candidate.get("sourceQuery") or "",
                "source": candidate.get("source") or "duckduckgo",
            })
            if len(ranked) >= limit:
                break
        if len(ranked) < min(limit, 3):
            seen_urls = {item["url"] for item in ranked}
            for item in self._fallback_rank_competitors(candidates, limit):
                if item["url"] not in seen_urls:
                    ranked.append(item)
                if len(ranked) >= limit:
                    break
        return ranked[:limit]

    @api.model
    def discover_competitors(self, product, limit=10):
        product.ensure_one()
        limit = max(1, min(int(limit or 10), 12))
        queries = self._build_competitor_queries(product)
        candidates_by_url = {}
        for query in queries:
            for candidate in self._duckduckgo_search(query, limit=8):
                url = candidate.get("url")
                if not url:
                    continue
                score = self._candidate_compatibility_score(product, candidate)
                if score < 28:
                    continue
                candidate["deterministicScore"] = score
                candidate["estimatedPrice"] = self._extract_estimated_price("%s %s" % (candidate.get("name") or "", candidate.get("description") or ""))
                existing = candidates_by_url.get(url)
                if not existing or score > existing.get("deterministicScore", 0):
                    candidates_by_url[url] = candidate

        candidates = list(candidates_by_url.values())
        competitors = self._ai_rank_real_competitor_candidates(product, candidates, limit)
        return {
            "success": True,
            "query": " | ".join(queries),
            "searchQueries": queries,
            "candidateCount": len(candidates),
            "totalFound": len(competitors),
            "competitors": competitors,
        }

    @api.model
    def _normalize_keyword_list(self, raw_value):
        if not raw_value:
            return []
        if isinstance(raw_value, str):
            values = re.split(r"[,;\n|]+", raw_value)
        elif isinstance(raw_value, list):
            values = raw_value
        else:
            values = [raw_value]

        keywords = []
        seen = set()
        for value in values:
            keyword = unescape(str(value or "")).strip()
            keyword = re.sub(r"\s+", " ", keyword)
            if not keyword:
                continue
            key = self._taxonomy_key(keyword)
            if key and key not in seen:
                seen.add(key)
                keywords.append(keyword[:60])
            if len(keywords) >= 14:
                break
        return keywords

    @api.model
    def _fetch_competitor_direct(self, safe_url):
        current_url = self._validate_external_url(safe_url)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-AR,es;q=0.9,pt;q=0.8,en;q=0.6",
            "Cache-Control": "no-cache",
        }
        response = None
        for _index in range(6):
            current_url = self._validate_external_url(current_url)
            try:
                response = requests.get(current_url, headers=headers, timeout=35, allow_redirects=False)
            except requests.RequestException as error:
                raise UserError(_("No se pudo conectar con el sitio del competidor.")) from error

            if response.status_code in (301, 302, 303, 307, 308) and response.headers.get("Location"):
                current_url = urljoin(current_url, response.headers["Location"])
                continue
            break

        if response is None:
            raise UserError(_("No se pudo obtener el sitio del competidor."))

        if response.status_code in (401, 403, 429):
            raise UserError(
                _("El sitio bloqueó el scraper directo (HTTP %s). Configura Firecrawl o probá con una URL pública del producto.")
                % response.status_code
            )
        if response.status_code >= 400:
            raise UserError(_("El sitio del competidor respondió HTTP %s.") % response.status_code)

        content_type = (response.headers.get("Content-Type") or "").lower()
        if content_type and all(allowed not in content_type for allowed in ("text/html", "application/xhtml", "text/plain")):
            raise UserError(_("La URL no devolvió una página HTML válida para scrapear."))

        html = (response.text or "")[:2500000]
        if not html.strip():
            raise UserError(_("La página del competidor está vacía o no pudo leerse."))

        final_url = response.url or current_url
        metadata = {
            "title": self._extract_title_tag(html),
            "description": self._extract_meta_tag(html, "description"),
            "keywords": self._extract_meta_tag(html, "keywords"),
            "ogTitle": self._extract_meta_property(html, "og:title"),
            "ogDescription": self._extract_meta_property(html, "og:description"),
            "ogImage": urljoin(final_url, self._extract_meta_property(html, "og:image") or ""),
            "canonicalUrl": self._extract_canonical_url(html, final_url),
            "sourceURL": final_url,
            "statusCode": response.status_code,
        }
        return {
            "html": html,
            "markdown": self._html_to_markdown_text(html),
            "metadata": metadata,
            "source": "direct_http",
            "statusCode": response.status_code,
            "sourceURL": final_url,
        }

    @api.model
    def _apply_competitor_scrape_data(self, competitor, data, source="firecrawl"):
        html = data.get("html") or data.get("rawHtml") or ""
        markdown = data.get("markdown") or data.get("content") or data.get("text") or ""
        if not markdown and html:
            markdown = self._html_to_markdown_text(html)
        metadata = data.get("metadata") or {}
        source_url = (
            metadata.get("sourceURL")
            or metadata.get("url")
            or data.get("sourceURL")
            or data.get("url")
            or competitor.competitor_url
        )

        title_tag = self._extract_title_tag(html)
        meta_title = metadata.get("title") or metadata.get("ogTitle") or title_tag or self._extract_meta_property(html, "og:title")
        meta_description = (
            metadata.get("description")
            or metadata.get("ogDescription")
            or self._extract_meta_tag(html, "description")
            or self._extract_meta_property(html, "og:description")
        )
        raw_keywords = metadata.get("keywords") or metadata.get("metaKeywords") or self._extract_meta_tag(html, "keywords")
        h1_tags = self._extract_headings(html, "h1")
        h2_tags = self._extract_headings(html, "h2")
        meta_keywords = self._normalize_keyword_list(raw_keywords)
        if not meta_keywords:
            meta_keywords = self._derive_keywords(
                competitor.competitor_name,
                competitor.competitor_description,
                meta_title,
                meta_description,
                " ".join(h1_tags),
                " ".join(h2_tags),
                markdown[:8000],
            )

        canonical_url = metadata.get("canonicalUrl") or metadata.get("canonical") or self._extract_canonical_url(html, source_url)
        og_title = metadata.get("ogTitle") or self._extract_meta_property(html, "og:title")
        og_description = metadata.get("ogDescription") or self._extract_meta_property(html, "og:description")
        og_image = metadata.get("ogImage") or self._extract_meta_property(html, "og:image")
        if og_image:
            og_image = urljoin(source_url or competitor.competitor_url, og_image)
        structured_data = self._extract_structured_data(html)
        price, offer_price, currency = self._extract_prices(html, markdown, structured_data)
        features = self._extract_features(markdown)
        word_count = len(re.findall(r"\w+", markdown or "", re.U))
        image_count = len(re.findall(r"<img\b", html or "", re.I))
        if not image_count and data.get("images"):
            image_count = len(data.get("images") or [])
        internal_links, external_links = self._count_links(html, source_url or competitor.competitor_url)
        seo_score = self._calculate_seo_score(
            meta_title,
            meta_description,
            h1_tags,
            structured_data,
            og_title,
            og_description,
            canonical_url,
            word_count,
            image_count,
            h2_tags,
        )
        compared_price = offer_price or price
        competitor.write(
            {
                "competitor_title": meta_title or competitor.competitor_title or competitor.competitor_name,
                "competitor_description": meta_description or competitor.competitor_description,
                "competitor_price": price or False,
                "competitor_offer_price": offer_price or False,
                "competitor_currency": currency or "ARS",
                "competitor_features": features,
                "price_comparison": self._detect_price_comparison(competitor.product_tmpl_id.list_price, compared_price),
                "meta_title": meta_title or "",
                "meta_description": meta_description or "",
                "meta_keywords": meta_keywords,
                "h1_tags": h1_tags,
                "h2_tags": h2_tags,
                "og_title": og_title or "",
                "og_description": og_description or "",
                "og_image": og_image or "",
                "canonical_url": canonical_url or "",
                "structured_data": structured_data,
                "page_content": (markdown or "")[:5000],
                "word_count": word_count,
                "image_count": image_count,
                "internal_links": internal_links,
                "external_links": external_links,
                "seo_score": seo_score,
                "firecrawl_data": {
                    "metadata": metadata,
                    "success": True,
                    "source": source,
                    "sourceURL": source_url,
                    "statusCode": data.get("statusCode") or metadata.get("statusCode"),
                },
                "scrape_status": "success",
                "scrape_error": False,
                "last_scraped_at": fields.Datetime.now(),
            }
        )
        return competitor.bpi_to_payload()

    @api.model
    def scrape_competitor(self, competitor):
        competitor.ensure_one()
        competitor.write({"scrape_status": "pending", "scrape_error": False})
        safe_url = self._validate_external_url(competitor.competitor_url)

        firecrawl_error = ""
        api_key = self._get_config("bader_product_intelligence.firecrawl_api_key")
        if api_key:
            base_url = self._get_config("bader_product_intelligence.firecrawl_base_url", "https://api.firecrawl.dev").rstrip("/")
            try:
                response = requests.post(
                    "%s/v1/scrape" % base_url,
                    json={
                        "url": safe_url,
                        "formats": ["markdown", "html"],
                        "includeTags": ["meta", "title", "h1", "h2", "script", "img", "a"],
                        "onlyMainContent": False,
                    },
                    headers={"Authorization": "Bearer %s" % api_key, "Content-Type": "application/json"},
                    timeout=120,
                )
                response.raise_for_status()
                payload = response.json()
                return self._apply_competitor_scrape_data(competitor, payload.get("data") or payload, source="firecrawl")
            except (requests.RequestException, ValueError, UserError) as error:
                firecrawl_error = str(error)
                _logger.warning("Firecrawl scrape failed for competitor %s; falling back to direct HTTP.", competitor.id, exc_info=True)

        try:
            direct_data = self._fetch_competitor_direct(safe_url)
            return self._apply_competitor_scrape_data(competitor, direct_data, source="direct_http")
        except UserError as error:
            message = str(error)
            if firecrawl_error:
                message = _("Firecrawl falló y el scraper directo tampoco pudo leer la página. Directo: %s") % message
            competitor.write(
                {
                    "scrape_status": "failed",
                    "scrape_error": message,
                    "last_scraped_at": fields.Datetime.now(),
                    "firecrawl_data": {
                        "success": False,
                        "source": "direct_http",
                        "firecrawlError": bool(firecrawl_error),
                    },
                }
            )
            raise UserError(message) from error

    @api.model
    def add_competitor(self, product, competitor_name, competitor_url, competitor_description=""):
        product.ensure_one()
        competitor_url = self._validate_external_url(competitor_url)
        name = competitor_name or ""
        if not name and competitor_url:
            parsed = urlparse(competitor_url)
            name = (parsed.netloc or "competidor").replace("www.", "").split(".")[0].title()
        competitor = self.env["bpi.product.competitor"].create(
            {
                "product_tmpl_id": product.id,
                "competitor_name": name or _("Competidor"),
                "competitor_url": competitor_url,
                "competitor_title": name or _("Competidor"),
                "competitor_description": competitor_description or False,
                "scrape_status": "pending",
            }
        )

        try:
            return self.scrape_competitor(competitor)
        except UserError as error:
            competitor.write(
                {
                    "scrape_status": "failed",
                    "scrape_error": str(error),
                    "last_scraped_at": fields.Datetime.now(),
                }
            )
            return competitor.bpi_to_payload()

    @api.model
    def analyze_competitor(self, competitor):
        competitor.ensure_one()
        product = competitor.product_tmpl_id
        prompt = """Sos Nancy AI, experta en análisis competitivo dental para Argentina.

Devolvé solo JSON:
{
  "competitorTitle": "",
  "competitorDescription": "",
  "competitorFeatures": [],
  "strengthsVsUs": [],
  "weaknessesVsUs": [],
  "priceComparison": "cheaper|similar|expensive",
  "recommendedKeywords": [],
  "contentStrategy": ""
}

Nuestro producto:
- Nombre: %(our_name)s
- Precio: %(our_price)s
- Descripción: %(our_description)s

Competidor:
- Nombre: %(name)s
- URL: %(url)s
- Título: %(title)s
- Descripción: %(description)s
- Precio: %(price)s
- Keywords: %(keywords)s
- H1: %(h1)s
- H2: %(h2)s
- Features: %(features)s
- Contenido: %(content)s
""" % {
            "our_name": product.name,
            "our_price": product.list_price,
            "our_description": product.description_sale or product.description or "Sin descripción",
            "name": competitor.competitor_name,
            "url": competitor.competitor_url,
            "title": competitor.competitor_title or "",
            "description": competitor.competitor_description or "",
            "price": competitor.competitor_offer_price or competitor.competitor_price or "",
            "keywords": ", ".join(competitor.meta_keywords or []),
            "h1": ", ".join(competitor.h1_tags or []),
            "h2": ", ".join(competitor.h2_tags or []),
            "features": ", ".join(competitor.competitor_features or []),
            "content": (competitor.page_content or "")[:1500],
        }
        analysis = self._openai_json(prompt)
        price_comparison = analysis.get("priceComparison") or self._detect_price_comparison(
            product.list_price,
            competitor.competitor_offer_price or competitor.competitor_price,
        )
        competitor.write(
            {
                "competitor_title": analysis.get("competitorTitle") or competitor.competitor_title,
                "competitor_description": analysis.get("competitorDescription") or competitor.competitor_description,
                "competitor_features": analysis.get("competitorFeatures") or competitor.competitor_features,
                "strengths_vs_us": analysis.get("strengthsVsUs") or [],
                "weaknesses_vs_us": analysis.get("weaknessesVsUs") or [],
                "price_comparison": price_comparison,
            }
        )
        return competitor.bpi_to_payload()

    @api.model
    def generate_competitive_strategy(self, product):
        product.ensure_one()
        competitors = product.bpi_competitor_ids
        if not competitors:
            raise UserError(_("Agregá al menos un competidor antes de generar la estrategia."))
        prompt = """Sos Nancy AI. Construí una estrategia competitiva superior para Bader Argentina.

Devolvé solo JSON:
{
  "overallStrategy": "",
  "competitivePosition": "",
  "seoStrategy": {
    "recommendedTitle": "",
    "recommendedDescription": "",
    "primaryKeywords": [],
    "secondaryKeywords": [],
    "longTailKeywords": []
  },
  "geoStrategy": {
    "recommendedTitle": "",
    "recommendedDescription": "",
    "naturalQuestions": [],
    "contextualPhrases": []
  },
  "contentRecommendations": [],
  "pricingStrategy": "",
  "competitorExploits": [],
  "immediateActions": [],
  "estimatedImpact": {
    "seoScoreTarget": 0,
    "expectedRankingImprovement": "",
    "timeToResults": ""
  }
}

Producto:
- Nombre: %(name)s
- Precio: %(price)s
- Descripción: %(description)s

SEO actual:
- SEO title: %(seo_title)s
- Meta description: %(seo_description)s
- Keywords: %(seo_keywords)s

Competidores:
%(competitors)s
""" % {
            "name": product.name,
            "price": product.list_price,
            "description": product.description_sale or product.description or "",
            "seo_title": product.website_meta_title or "",
            "seo_description": product.website_meta_description or "",
            "seo_keywords": ", ".join(product._bpi_keyword_values("seo")),
            "competitors": json.dumps([comp.bpi_to_payload() for comp in competitors], ensure_ascii=False),
        }
        strategy = self._openai_json(prompt)
        product.write(
            {
                "bpi_competitive_strategy": strategy,
                "bpi_competitive_strategy_updated_at": fields.Datetime.now(),
            }
        )
        return strategy

    @api.model
    def chat_with_product(self, product, message, session_key=False):
        product.ensure_one()
        session = self.env["bpi.product.chat.session"].search(
            [("product_tmpl_id", "=", product.id), ("session_key", "=", session_key)],
            limit=1,
        )
        if not session:
            session = self.env["bpi.product.chat.session"].create(
                {
                    "product_tmpl_id": product.id,
                    "name": _("Sesión %s") % product.name,
                    "session_key": session_key or str(uuid.uuid4()),
                }
            )
        self.env["bpi.product.chat.message"].create({"session_id": session.id, "role": "user", "content": message})
        history = session.message_ids.sorted("id")
        history_lines = []
        for item in history[-12:]:
            history_lines.append("%s: %s" % (item.role, item.content))
        prompt = """Sos Nancy AI, agente de producto para Bader Argentina.

Producto:
- Nombre: %(name)s
- SKU: %(sku)s
- Categoría: %(category)s
- Precio: %(price)s
- Descripción: %(description)s

Objetivo:
- Ayudar al administrador a mejorar contenido, SEO, GEO, pricing, marketing e imágenes.
- Responder en español argentino.
- Ser concreta, útil y accionable.

Historial:
%(history)s

Respondé al último mensaje del usuario:
%(message)s
""" % {
            "name": product.name,
            "sku": product.default_code or "",
            "category": product.public_categ_ids[:1].name if product.public_categ_ids else "",
            "price": product.list_price,
            "description": product.description_sale or product.description or "",
            "history": "\n".join(history_lines),
            "message": message,
        }
        model_name = self._get_config("bader_product_intelligence.openai_text_model", "gpt-5.5")
        reply = self._openai_response(prompt, model_name=model_name)
        self.env["bpi.product.chat.message"].create({"session_id": session.id, "role": "assistant", "content": reply})
        return {"response": reply, "sessionId": session.session_key}
