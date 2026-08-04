# -*- coding: utf-8 -*-

import base64
import inspect
import socket
from types import SimpleNamespace
from unittest.mock import patch

from odoo.exceptions import MissingError, UserError
from odoo.tests.common import TransactionCase, tagged

from ..controllers.main import BaderProductIntelligenceController


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class FakeStreamResponse:
    def __init__(self, status_code=200, headers=None, chunks=None):
        self.status_code = status_code
        self.headers = headers or {}
        self._chunks = chunks or []
        self.closed = False

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            response = SimpleNamespace(status_code=self.status_code)
            raise requests.HTTPError(response=response)

    def iter_content(self, chunk_size=65536):
        del chunk_size
        yield from self._chunks

    def close(self):
        self.closed = True


@tagged("-at_install", "post_install")
class TestProductoIntelligence(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["bpi.service"]
        cls.category = cls.env["product.public.category"].create({"name": "Fresas"})

        cls.product_published = cls.env["product.template"].create(
            {
                "name": "Producto Publicado",
                "default_code": "PUB-001",
                "list_price": 12.0,
                "standard_price": 5.0,
                "sale_ok": True,
                "website_published": True,
                "bpi_featured": True,
                "public_categ_ids": [(6, 0, [cls.category.id])],
            }
        )
        cls.product_new = cls.env["product.template"].create(
            {
                "name": "Producto Nuevo",
                "default_code": "NEW-001",
                "list_price": 20.0,
                "standard_price": 8.0,
                "sale_ok": True,
                "website_published": False,
                "public_categ_ids": [(6, 0, [cls.category.id])],
            }
        )
        cls.product_archived = cls.env["product.template"].create(
            {
                "name": "Producto Archivado",
                "default_code": "ARC-001",
                "list_price": 9.0,
                "sale_ok": True,
                "website_published": False,
            }
        )
        cls.product_archived.write({"active": False})

        cls.product_discontinued = cls.env["product.template"].create(
            {
                "name": "Producto Discontinuado",
                "default_code": "DIS-001",
                "list_price": 7.0,
                "sale_ok": False,
                "website_published": False,
            }
        )

    def test_dashboard_payload_is_paginated(self):
        payload = self.service.dashboard_payload(tab="all", search="", page=1, limit=1)

        self.assertEqual(payload["stats"]["total"], 3)
        self.assertEqual(payload["stats"]["published"], 1)
        self.assertEqual(payload["stats"]["featured"], 1)
        self.assertEqual(payload["tabCounts"]["all"], 2)
        self.assertEqual(payload["tabCounts"]["new"], 1)
        self.assertEqual(payload["tabCounts"]["discontinued"], 2)
        self.assertEqual(len(payload["products"]), 1)
        self.assertEqual(payload["pager"]["page"], 1)
        self.assertEqual(payload["pager"]["pageCount"], 2)
        self.assertTrue(payload["pager"]["hasNext"])
        self.assertFalse(payload["pager"]["hasPrevious"])

        search_payload = self.service.dashboard_payload(tab="all", search="NEW-001", page=1, limit=10)
        self.assertEqual(search_payload["pager"]["total"], 1)
        self.assertEqual(search_payload["products"][0]["sku"], "NEW-001")

    def test_update_product_generates_slug(self):
        payload = self.service.update_product(
            self.product_new,
            {
                "name": "Producto Inteligente Premium",
                "slug": "Producto Inteligente Premium!!",
                "featured": True,
            },
        )

        self.assertEqual(self.product_new.bpi_slug, "producto-inteligente-premium")
        self.assertTrue(self.product_new.bpi_featured)
        self.assertEqual(payload["product"]["slug"], "producto-inteligente-premium")

    def test_save_category_normalizes_free_text_ai_values(self):
        self.service.save_category(
            self.product_new,
            {
                "niches": ["Clínicas Dentales", "estudiante"],
                "type": "Clamps",
                "subcategory": "Clamp para dique de goma",
                "manualMode": False,
            },
        )

        self.assertEqual(self.product_new.bpi_intelligent_niches, ["clinica", "estudiantes"])
        self.assertEqual(self.product_new.bpi_intelligent_type, "instrumental")
        self.assertEqual(self.product_new.bpi_intelligent_subcategory, "aislamiento")

    def test_validate_external_url_blocks_private_networks(self):
        private_resolution = [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 443)),
        ]
        public_resolution = [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 443)),
        ]

        with patch(
            "odoo.addons.bader_product_intelligence.models.product_intelligence.socket.getaddrinfo",
            return_value=private_resolution,
        ):
            with self.assertRaises(UserError):
                self.service._validate_external_url("https://127.0.0.1/private.png")

        with patch(
            "odoo.addons.bader_product_intelligence.models.product_intelligence.socket.getaddrinfo",
            return_value=public_resolution,
        ):
            result = self.service._validate_external_url("https://example.com/image.png")

        self.assertEqual(result, "https://example.com/image.png")

    def test_category_views_keep_native_default_and_bind_bpi_views(self):
        native_form = self.env.ref("website_sale.product_public_category_form_view")
        native_tree = self.env.ref("website_sale.product_public_category_tree_view")
        bpi_form = self.env.ref("bader_product_intelligence.view_bpi_category_form")
        bpi_tree = self.env.ref("bader_product_intelligence.view_bpi_category_tree")
        bpi_action = self.env.ref("bader_product_intelligence.action_bpi_categories")

        self.assertEqual(bpi_form.mode, "primary")
        self.assertEqual(bpi_tree.mode, "primary")
        self.assertEqual(bpi_form.inherit_id, native_form)
        self.assertEqual(bpi_tree.inherit_id, native_tree)
        self.assertGreater(bpi_form.priority, native_form.priority)
        self.assertGreater(bpi_tree.priority, native_tree.priority)

        default_form = self.env["ir.ui.view"].search(
            [("model", "=", "product.public.category"), ("type", "=", "form"), ("mode", "=", "primary")],
            order="priority,name,id",
            limit=1,
        )
        default_tree = self.env["ir.ui.view"].search(
            [("model", "=", "product.public.category"), ("type", "=", "tree"), ("mode", "=", "primary")],
            order="priority,name,id",
            limit=1,
        )
        self.assertEqual(default_form, native_form)
        self.assertEqual(default_tree, native_tree)

        combined_form = bpi_form.get_combined_arch()
        combined_tree = bpi_tree.get_combined_arch()
        for field_name in ("parent_id", "image_1920", "website_id", "sequence"):
            self.assertIn('name="%s"' % field_name, combined_form)
        for field_name in ("parent_id", "website_id", "sequence"):
            self.assertIn('name="%s"' % field_name, combined_tree)

        bound_views = {(binding.view_mode, binding.view_id.id) for binding in bpi_action.view_ids}
        self.assertIn(("tree", bpi_tree.id), bound_views)
        self.assertIn(("form", bpi_form.id), bound_views)
        self.assertFalse(bpi_action.view_id)

    def test_gallery_payload_exposes_real_reference_tokens(self):
        image = self.env["bpi.product.image"].create(
            {
                "product_tmpl_id": self.product_new.id,
                "name": "Imagen segura",
                "image_1920": base64.b64encode(PNG_1X1),
                "mime_type": "image/png",
            }
        )
        payload = self.product_new._bpi_gallery_payload()
        item = next(entry for entry in payload if entry["id"] == "bpi:%s" % image.id)
        self.assertEqual(item["referenceToken"], "bpi:%s" % image.id)
        self.assertTrue(item["canReference"])
        self.assertTrue(item["canDelete"])

    def test_reference_tokens_reject_malformed_and_cross_product_values(self):
        image = self.env["bpi.product.image"].create(
            {
                "product_tmpl_id": self.product_new.id,
                "name": "Referencia",
                "image_1920": base64.b64encode(PNG_1X1),
                "mime_type": "image/png",
            }
        )
        references = self.service._reference_images(self.product_new, ["bpi:%s" % image.id])
        self.assertEqual(len(references), 1)
        self.assertEqual(references[0]["mime_type"], "image/png")

        for malformed in ("bpi:", "bpi:abc", "bpi:1:2", "odoo:-1", "https://example.com/x.png", 7):
            with self.assertRaises(UserError, msg=str(malformed)):
                self.service._reference_images(self.product_new, [malformed])

        with self.assertRaises(UserError):
            self.service._reference_images(self.product_published, ["bpi:%s" % image.id])

    def test_data_url_validation_checks_base64_size_mime_and_signature(self):
        encoded_png = base64.b64encode(PNG_1X1).decode()
        raw, mime_type, normalized = self.service._parse_image_data_url(
            "data:image/png;base64,%s" % encoded_png
        )
        self.assertEqual(raw, PNG_1X1)
        self.assertEqual(mime_type, "image/png")
        self.assertEqual(normalized, encoded_png)

        with self.assertRaises(UserError):
            self.service._parse_image_data_url("data:image/png;base64,not-base64!!")
        with self.assertRaises(UserError):
            self.service._parse_image_data_url("data:image/jpeg;base64,%s" % encoded_png)
        with self.assertRaises(UserError):
            self.service._parse_image_data_url(
                "data:image/gif;base64,%s" % base64.b64encode(b"GIF89a" + b"0" * 32).decode()
            )

        oversized = PNG_1X1 + (b"0" * (self.service._MAX_IMAGE_BYTES + 1))
        with self.assertRaises(UserError):
            self.service._parse_image_data_url(
                "data:image/png;base64,%s" % base64.b64encode(oversized).decode()
            )

    def test_external_image_download_validates_redirects_size_mime_and_stream(self):
        public_resolution = [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 443)),
        ]
        private_resolution = [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 80)),
        ]

        def resolve(hostname, *_args, **_kwargs):
            return private_resolution if hostname == "127.0.0.1" else public_resolution

        redirect = FakeStreamResponse(302, {"Location": "http://127.0.0.1/private.png"})
        with patch(
            "odoo.addons.bader_product_intelligence.models.product_intelligence.socket.getaddrinfo",
            side_effect=resolve,
        ), patch(
            "odoo.addons.bader_product_intelligence.models.product_intelligence.requests.get",
            return_value=redirect,
        ) as mocked_get:
            with self.assertRaises(UserError):
                self.service._download_external_image("https://example.com/image.png")
        self.assertEqual(mocked_get.call_count, 1)
        self.assertTrue(redirect.closed)

        valid = FakeStreamResponse(
            200,
            {"Content-Type": "image/png", "Content-Length": str(len(PNG_1X1))},
            [PNG_1X1[:12], PNG_1X1[12:]],
        )
        with patch(
            "odoo.addons.bader_product_intelligence.models.product_intelligence.socket.getaddrinfo",
            return_value=public_resolution,
        ), patch(
            "odoo.addons.bader_product_intelligence.models.product_intelligence.requests.get",
            return_value=valid,
        ) as mocked_get:
            raw, mime_type = self.service._download_external_image("https://example.com/image.png")
        self.assertEqual(raw, PNG_1X1)
        self.assertEqual(mime_type, "image/png")
        self.assertTrue(mocked_get.call_args.kwargs["stream"])
        self.assertFalse(mocked_get.call_args.kwargs["allow_redirects"])
        self.assertTrue(valid.closed)

        oversized = FakeStreamResponse(
            200,
            {"Content-Type": "image/png", "Content-Length": str(self.service._MAX_IMAGE_BYTES + 1)},
            [],
        )
        with patch(
            "odoo.addons.bader_product_intelligence.models.product_intelligence.socket.getaddrinfo",
            return_value=public_resolution,
        ), patch(
            "odoo.addons.bader_product_intelligence.models.product_intelligence.requests.get",
            return_value=oversized,
        ):
            with self.assertRaises(UserError):
                self.service._download_external_image("https://example.com/large.png")

        wrong_mime = FakeStreamResponse(200, {"Content-Type": "image/jpeg"}, [PNG_1X1])
        with patch(
            "odoo.addons.bader_product_intelligence.models.product_intelligence.socket.getaddrinfo",
            return_value=public_resolution,
        ), patch(
            "odoo.addons.bader_product_intelligence.models.product_intelligence.requests.get",
            return_value=wrong_mime,
        ):
            with self.assertRaises(UserError):
                self.service._download_external_image("https://example.com/wrong.jpg")

    def test_competitor_prices_preserve_currency_and_normalize_only_ars_usd(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "bader_product_intelligence.exchange_rate", "1650"
        )
        ars = self.env["bpi.product.competitor"].create(
            {
                "product_tmpl_id": self.product_new.id,
                "competitor_name": "ARS",
                "competitor_url": "https://example.com/ars",
                "competitor_price": 33000,
                "competitor_offer_price": 16500,
                "competitor_currency": "ARS",
            }
        )
        ars_payload = ars.bpi_to_payload()
        self.assertEqual(ars_payload["competitorCurrency"], "ARS")
        self.assertEqual(ars_payload["competitorPrice"], 33000)
        self.assertAlmostEqual(ars_payload["competitorPriceUsd"], 20.0)
        self.assertAlmostEqual(ars_payload["competitorOfferPriceUsd"], 10.0)
        self.assertTrue(ars_payload["priceComparisonAvailable"])

        usd = self.service._competitor_price_to_usd(25, "USD", 1650)
        unknown = self.service._competitor_price_to_usd(25, "EUR", 1650)
        invalid_rate = self.service._competitor_price_to_usd(1650, "ARS", 0)
        self.assertEqual(usd, 25)
        self.assertFalse(unknown)
        self.assertFalse(invalid_rate)

        unknown_competitor = self.env["bpi.product.competitor"].create(
            {
                "product_tmpl_id": self.product_new.id,
                "competitor_name": "EUR",
                "competitor_url": "https://example.com/eur",
                "competitor_price": 30,
                "competitor_currency": "EUR",
            }
        )
        unknown_payload = unknown_competitor.bpi_to_payload()
        self.assertEqual(unknown_payload["competitorCurrency"], "EUR")
        self.assertFalse(unknown_payload["competitorPriceUsd"])
        self.assertFalse(unknown_payload["priceComparisonAvailable"])

    def test_chat_does_not_reuse_session_across_products_and_limits_messages(self):
        with patch(
            "odoo.addons.bader_product_intelligence.models.product_intelligence.BPIService._openai_response",
            return_value="Respuesta segura",
        ):
            first = self.service.chat_with_product(self.product_new, "Primera pregunta")
            crossed = self.service.chat_with_product(
                self.product_published,
                "Pregunta de otro producto",
                session_key=first["sessionId"],
            )
            reused = self.service.chat_with_product(
                self.product_new,
                "Segunda pregunta",
                session_key=first["sessionId"],
            )

        self.assertNotEqual(first["sessionId"], crossed["sessionId"])
        self.assertEqual(first["sessionId"], reused["sessionId"])
        first_session = self.env["bpi.product.chat.session"].search(
            [("session_key", "=", first["sessionId"])], limit=1
        )
        crossed_session = self.env["bpi.product.chat.session"].search(
            [("session_key", "=", crossed["sessionId"])], limit=1
        )
        self.assertEqual(first_session.product_tmpl_id, self.product_new)
        self.assertEqual(crossed_session.product_tmpl_id, self.product_published)

        with self.assertRaises(UserError):
            self.service.chat_with_product(self.product_new, "x" * 4001)

    def test_controller_requires_owned_image_tokens_and_competitors(self):
        controller = BaderProductIntelligenceController()
        image = self.env["bpi.product.image"].create(
            {
                "product_tmpl_id": self.product_new.id,
                "name": "Propiedad",
                "image_1920": base64.b64encode(PNG_1X1),
            }
        )
        competitor = self.env["bpi.product.competitor"].create(
            {
                "product_tmpl_id": self.product_new.id,
                "competitor_name": "Propiedad",
                "competitor_url": "https://example.com/owned",
            }
        )
        fake_request = SimpleNamespace(env=self.env)
        with patch("odoo.addons.bader_product_intelligence.controllers.main.request", fake_request):
            self.assertEqual(controller._image(self.product_new, "bpi:%s" % image.id), image)
            self.assertEqual(controller._competitor(self.product_new, competitor.id), competitor)
            for token in ("main", "odoo:1", "bpi:abc", "bpi:-1", "bpi:1:2"):
                with self.assertRaises(MissingError):
                    controller._image(self.product_new, token)
            with self.assertRaises(MissingError):
                controller._image(self.product_published, "bpi:%s" % image.id)
            with self.assertRaises(MissingError):
                controller._competitor(self.product_published, competitor.id)

        delete_signature = inspect.signature(controller.delete_image)
        self.assertIn("product_tmpl_id", delete_signature.parameters)
        self.assertIn("image_token", delete_signature.parameters)
        for method_name in ("scrape_competitor", "analyze_competitor", "delete_competitor"):
            self.assertIn("product_tmpl_id", inspect.signature(getattr(controller, method_name)).parameters)
