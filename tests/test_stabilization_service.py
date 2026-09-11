# -*- coding: utf-8 -*-

from types import SimpleNamespace
from unittest.mock import patch

from odoo.api import call_kw
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

from ..controllers.main import BaderProductIntelligenceController


@tagged("-at_install", "post_install")
class TestBPIStabilizationService(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["bpi.service"]
        cls.category_old = cls.env["product.public.category"].create({"name": "BPI Original"})
        cls.category_new = cls.env["product.public.category"].create({"name": "BPI Elegida"})
        cls.product = cls.env["product.template"].create({
            "name": "Clamp BPI 13A",
            "default_code": "BPI-STABILIZATION-13A",
            "description_sale": "Resumen comercial manual.",
            "bpi_ai_generated_description": "<p><strong>Resumen comercial manual.</strong></p>",
            "bpi_technical_description": "<h3>Ficha técnica manual</h3><p>Datos confirmados.</p>",
            "website_meta_title": "Título original",
            "bpi_geo_title": "GEO original",
            "bpi_seo_score": 25,
            "bpi_intelligent_type": "instrumental",
            "public_categ_ids": [(6, 0, [cls.category_old.id])],
            "bpi_keyword_ids": [
                (0, 0, {"name": "clamp SEO original", "keyword_type": "seo"}),
                (0, 0, {"name": "aislamiento GEO original", "keyword_type": "geo"}),
            ],
            "bpi_faq_ids": [(0, 0, {"question": "¿Uso confirmado?", "answer": "Respuesta manual publicada."})],
        })
        cls.non_manager = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "BPI Stabilization Internal User",
            "login": "bpi_stabilization_internal_user",
            "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
        })

    def _snapshot(self):
        return self.product.read([
            "name", "description_sale", "bpi_ai_generated_description", "bpi_technical_description",
            "website_meta_title", "website_meta_description", "bpi_geo_title", "bpi_geo_description",
            "bpi_geo_features", "bpi_ai_target_audience", "bpi_seo_score", "bpi_geo_score",
            "bpi_competitiveness_score", "bpi_last_analyzed_at", "public_categ_ids",
            "bpi_intelligent_type", "bpi_keyword_ids", "bpi_faq_ids", "write_date",
        ])[0]

    def test_seo_analysis_is_metadata_only_preview_without_any_product_write(self):
        before = self._snapshot()
        response = {
            "seoTitle": "Título propuesto",
            "seoDescription": "Descripción SEO propuesta",
            "seoKeywords": [" clamp ", ""],
            "geoKeywords": ["aislamiento absoluto"],
            "geoFeatures": ["Uso dental"],
            "geoScore": 120,
            "aiGeneratedDescription": "NO PUBLICAR",
            "aiTechnicalDescription": "NO PUBLICAR TÉCNICA",
            "geoFaq": [{"question": "No publicar", "answer": "No publicar"}],
        }
        with patch.object(type(self.service), "_openai_json", return_value=response) as openai, \
                patch.object(type(self.product), "write", side_effect=AssertionError("SEO must not write")), \
                patch.object(type(self.env["bpi.product.faq"]), "unlink", side_effect=AssertionError("SEO must not unlink FAQs")), \
                patch.object(type(self.env["bpi.product.keyword"]), "unlink", side_effect=AssertionError("SEO must not unlink keywords")):
            proposal = self.service.analyze_seo(self.product, "laboratorios")
        self.assertEqual(proposal["seoTitle"], "Título propuesto")
        self.assertEqual(proposal["seoKeywords"], ["clamp"])
        self.assertEqual(proposal["aiTargetAudience"], "laboratorios")
        self.assertEqual(proposal["geoScore"], 100)
        self.assertFalse({"aiGeneratedDescription", "aiTechnicalDescription", "geoFaq"} & set(proposal))
        self.assertNotIn("200-300", openai.call_args.args[0])
        self.assertEqual(self._snapshot(), before)

    def test_save_seo_metadata_patch_preserves_omitted_editorial_and_keywords(self):
        before = self._snapshot()
        self.service.save_seo_payload(self.product, {"seoTitle": "Solo cambia el título"})
        after = self._snapshot()
        self.assertEqual(after["website_meta_title"], "Solo cambia el título")
        for field in before:
            if field not in {"website_meta_title", "bpi_last_analyzed_at", "write_date"}:
                self.assertEqual(after[field], before[field], field)

    def test_save_seo_keyword_patch_changes_only_explicit_type(self):
        seo_ids = self.product.bpi_keyword_ids.filtered(lambda kw: kw.keyword_type == "seo").ids
        geo_ids = self.product.bpi_keyword_ids.filtered(lambda kw: kw.keyword_type == "geo").ids
        self.service.save_seo_payload(self.product, {"geoFeatures": ["Característica citable"]})
        self.assertEqual(self.product.bpi_keyword_ids.filtered(lambda kw: kw.keyword_type == "seo").ids, seo_ids)
        self.assertEqual(self.product.bpi_keyword_ids.filtered(lambda kw: kw.keyword_type == "geo").ids, geo_ids)
        self.service.save_seo_payload(self.product, {"seoKeywords": ["SEO nuevo"]})
        self.assertEqual(self.product._bpi_keyword_values("seo"), ["SEO nuevo"])
        self.assertEqual(self.product.bpi_keyword_ids.filtered(lambda kw: kw.keyword_type == "geo").ids, geo_ids)
        self.service.save_seo_payload(self.product, {"geoKeywords": []})
        self.assertFalse(self.product._bpi_keyword_values("geo"))
        self.assertEqual(self.product._bpi_keyword_values("seo"), ["SEO nuevo"])

    def test_save_seo_legacy_editorial_requires_explicit_keys(self):
        technical_before = self.product.bpi_technical_description
        self.service.save_seo_payload(self.product, {
            "aiGeneratedDescription": "<p><strong>Edición explícita.</strong></p>",
            "geoFaq": [],
        })
        self.assertIn("<strong>Edición explícita.</strong>", self.product.bpi_ai_generated_description)
        self.assertIn("Edición explícita.", self.product.description_sale)
        self.assertNotIn("<", self.product.description_sale)
        self.assertEqual(self.product.bpi_technical_description, technical_before)
        self.assertFalse(self.product.bpi_faq_ids)

    def test_save_all_category_is_written_once_and_content_wins_over_stale_seo(self):
        original_write = type(self.product).write
        category_writes = []

        def record_write(records, values):
            if self.product in records and "public_categ_ids" in values:
                category_writes.append(values["public_categ_ids"])
            return original_write(records, values)

        with patch.object(type(self.product), "write", autospec=True, side_effect=record_write):
            payload = self.service.save_all(
                self.product,
                product_values={"categoryId": self.category_new.id},
                category_values={"categoryId": self.category_old.id, "type": "equipo"},
                content_values={
                    "description": "<p><strong>Resumen revisado.</strong></p>",
                    "technicalDescription": "<h3>Ficha revisada</h3><p>Contenido técnico.</p>",
                    "faqs": [{"question": "¿Guardada?", "answer": "Sí, revisada."}],
                },
                seo_data={
                    "seoTitle": "SEO revisado",
                    "aiGeneratedDescription": "Texto antiguo",
                    "aiTechnicalDescription": "Técnica antigua",
                    "geoFaq": [],
                },
            )
        self.assertEqual(len(category_writes), 1)
        self.assertEqual(self.product.public_categ_ids, self.category_new)
        self.assertEqual(payload["product"]["categoryId"], self.category_new.id)
        self.assertIn("<strong>Resumen revisado.</strong>", self.product.bpi_ai_generated_description)
        self.assertIn("Ficha revisada", self.product.bpi_technical_description)
        self.assertEqual(self.product.bpi_faq_ids.question, "¿Guardada?")
        self.assertEqual(self.product.website_meta_title, "SEO revisado")

    def test_save_all_explicit_empty_category_does_not_restore_previous_category(self):
        self.service.save_all(
            self.product,
            product_values={"categoryId": False},
            category_values={"categoryId": self.category_old.id},
        )
        self.assertFalse(self.product.public_categ_ids)

    def test_save_all_rolls_back_every_stage_when_final_seo_save_fails(self):
        before = self._snapshot()
        with patch.object(type(self.service), "save_seo_payload", side_effect=UserError("Fallo final simulado")):
            with self.assertRaisesRegex(UserError, "Fallo final"):
                self.service.save_all(
                    self.product,
                    product_values={"name": "No conservar", "categoryId": self.category_new.id},
                    category_values={"type": "equipo"},
                    content_values={"description": "No conservar", "technicalDescription": "No conservar", "faqs": []},
                    seo_data={"seoTitle": "No conservar"},
                )
        self.assertEqual(self._snapshot(), before)

    def test_discovery_builds_catalog_context_and_only_returns_real_candidates(self):
        candidate = {
            "url": "https://competidor.example/producto/clamp-13a",
            "domain": "competidor.example",
            "name": "Clamp 13A dental",
            "description": "Clamp para aislamiento absoluto",
        }
        with patch.object(type(self.service), "_build_competitor_queries", return_value=["clamp 13a"]), \
                patch.object(type(self.service), "_duckduckgo_search", return_value=[candidate]), \
                patch.object(type(self.service), "_candidate_compatibility_score", return_value=90), \
                patch.object(type(self.service), "_openai_json", return_value={"competitors": [
                    {"url": "https://inventado.example/producto", "relevanceScore": 100},
                    {"url": candidate["url"], "relevanceScore": 95},
                ]}) as openai:
            result = self.service.discover_competitors(self.product, limit=3)
        self.assertEqual(result["candidateCount"], 1)
        self.assertEqual([row["url"] for row in result["competitors"]], [candidate["url"]])
        self.assertIn("Contexto de variantes/Pack", openai.call_args.args[0])
        self.assertNotIn("%(catalog_context)s", openai.call_args.args[0])

    def test_discovery_falls_back_when_ai_is_unavailable(self):
        candidate = {
            "url": "https://competidor.example/producto/clamp-13a",
            "domain": "competidor.example",
            "name": "Clamp 13A dental",
            "deterministicScore": 90,
        }
        with patch.object(type(self.service), "_openai_json", side_effect=UserError("IA no disponible")):
            ranked = self.service._ai_rank_real_competitor_candidates(self.product, [candidate], 3)
        self.assertEqual([row["url"] for row in ranked], [candidate["url"]])
        self.assertEqual(ranked[0]["relevanceScore"], 90)

    def test_exchange_rate_generic_model_call_requires_administrator(self):
        key = "bader_product_intelligence.exchange_rate"
        params = self.env["ir.config_parameter"].sudo()
        before = params.get_param(key)
        self.assertFalse(self.non_manager.has_group("base.group_system"))
        with self.assertRaises(AccessError):
            call_kw(self.service.with_user(self.non_manager), "update_exchange_rate", [2000], {})
        self.assertEqual(params.get_param(key), before)

    def test_exchange_rate_requires_finite_positive_integer(self):
        for invalid in (None, False, True, "", "invalid", 0, "0", -100, 0.5, "1.5", float("nan"), float("inf")):
            with self.subTest(rate=invalid):
                with self.assertRaises(UserError):
                    self.service.update_exchange_rate(invalid)
        self.assertEqual(self.service.update_exchange_rate("1650.0")["exchangeRate"], 1650)

    def test_controller_save_all_returns_detail_payload_and_video_rejects_before_write(self):
        controller = BaderProductIntelligenceController()
        with patch("odoo.addons.bader_product_intelligence.controllers.main.request", SimpleNamespace(env=self.env)):
            result = controller.save_all(self.product.id, product_values={"categoryId": self.category_new.id})
            self.assertEqual(result["product"]["categoryId"], self.category_new.id)
            self.product.bpi_video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            with self.assertRaises(UserError):
                controller.save_video(self.product.id, video_url="https://evil.example/watch?v=dQw4w9WgXcQ")
            self.assertEqual(self.product.bpi_video_url, "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            result = controller.save_video(self.product.id, video_url="")
            self.assertFalse(self.product.bpi_video_url)
            self.assertEqual(result["videoUrl"], "")
