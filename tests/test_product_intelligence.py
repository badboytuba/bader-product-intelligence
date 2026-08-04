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
        baseline_payload = cls.service.dashboard_payload(tab="all", search="", page=1, limit=1)
        cls.dashboard_baseline_stats = baseline_payload["stats"]
        cls.dashboard_baseline_tab_counts = baseline_payload["tabCounts"]
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

        cls.variant_attribute = cls.env["product.attribute"].create(
            {"name": "Color BPI", "create_variant": "always"}
        )
        cls.variant_value_red = cls.env["product.attribute.value"].create(
            {"name": "Rojo", "attribute_id": cls.variant_attribute.id}
        )
        cls.variant_value_blue = cls.env["product.attribute.value"].create(
            {"name": "Azul", "attribute_id": cls.variant_attribute.id}
        )
        cls.product_with_variants = cls.env["product.template"].create(
            {
                "name": "Producto con Variantes BPI",
                "list_price": 30.0,
                "sale_ok": True,
                "attribute_line_ids": [
                    (
                        0,
                        0,
                        {
                            "attribute_id": cls.variant_attribute.id,
                            "value_ids": [
                                (6, 0, [cls.variant_value_red.id, cls.variant_value_blue.id])
                            ],
                        },
                    )
                ],
            }
        )
        cls.multi_variants = cls.product_with_variants.product_variant_ids.sorted("id")
        cls.multi_variants[0].write(
            {"default_code": "VAR-RED", "barcode": "BPI-VAR-RED", "standard_price": 11.0}
        )
        cls.multi_variants[1].write(
            {"default_code": "VAR-BLUE", "barcode": "BPI-VAR-BLUE", "standard_price": 13.0}
        )
        blue_template_value = cls.product_with_variants.valid_product_template_attribute_line_ids.product_template_value_ids.filtered(
            lambda value: value.product_attribute_value_id == cls.variant_value_blue
        )
        blue_template_value.write({"price_extra": 5.0})

        cls.pack_component_a = cls.env["product.template"].create(
            {"name": "Componente A BPI", "default_code": "COMP-A", "list_price": 10.0, "standard_price": 4.0}
        )
        cls.pack_component_b = cls.env["product.template"].create(
            {"name": "Componente B BPI", "default_code": "COMP-B", "list_price": 20.0, "standard_price": 7.0}
        )
        cls.pack_product = cls.env["product.template"].create(
            {
                "name": "Pack BPI",
                "default_code": "PACK-BPI",
                "list_price": 50.0,
                "standard_price": 1.0,
                "pack_ok": True,
                "pack_type": "detailed",
                "pack_component_price": "ignored",
            }
        )
        cls.pack_variant = cls.pack_product.product_variant_id
        cls.pack_variant.write(
            {
                "pack_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": cls.pack_component_a.product_variant_id.id,
                            "quantity": 2.0,
                            "sale_discount": 10.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": cls.pack_component_b.product_variant_id.id,
                            "quantity": 1.0,
                            "sale_discount": 0.0,
                        },
                    ),
                ]
            }
        )

    def test_dashboard_payload_is_paginated(self):
        payload = self.service.dashboard_payload(tab="all", search="", page=1, limit=1)

        self.assertEqual(payload["stats"]["total"], self.dashboard_baseline_stats["total"] + 7)
        self.assertEqual(payload["stats"]["published"], self.dashboard_baseline_stats["published"] + 1)
        self.assertEqual(payload["stats"]["featured"], self.dashboard_baseline_stats["featured"] + 1)
        self.assertEqual(payload["tabCounts"]["all"], self.dashboard_baseline_tab_counts["all"] + 6)
        self.assertEqual(payload["tabCounts"]["new"], self.dashboard_baseline_tab_counts["new"] + 5)
        self.assertEqual(
            payload["tabCounts"]["discontinued"],
            self.dashboard_baseline_tab_counts["discontinued"] + 2,
        )
        self.assertEqual(len(payload["products"]), 1)
        self.assertEqual(payload["pager"]["page"], 1)
        self.assertEqual(payload["pager"]["pageCount"], payload["tabCounts"]["all"])
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

    def test_variant_payload_exposes_native_operational_data_and_price_range(self):
        payload = self.product_with_variants.bpi_build_payload()

        self.assertEqual(payload["product"]["productKind"], "variants")
        self.assertEqual(payload["variantSummary"]["count"], 2)
        self.assertTrue(payload["variantSummary"]["hasVariants"])
        self.assertEqual(payload["variantSummary"]["effectivePriceMinUsd"], 30.0)
        self.assertEqual(payload["variantSummary"]["effectivePriceMaxUsd"], 35.0)
        self.assertEqual({item["sku"] for item in payload["variants"]}, {"VAR-RED", "VAR-BLUE"})
        blue = next(item for item in payload["variants"] if item["sku"] == "VAR-BLUE")
        self.assertEqual(blue["barcode"], "BPI-VAR-BLUE")
        self.assertEqual(blue["costUsd"], 13.0)
        self.assertEqual(blue["attributeValues"][0]["valueName"], "Azul")

        dashboard = self.product_with_variants.bpi_dashboard_payload(exchange_rate=1000)
        self.assertEqual(dashboard["productKind"], "variants")
        self.assertEqual(dashboard["variantCount"], 2)
        self.assertEqual(dashboard["effectivePriceMaxUsd"], 35.0)

    def test_update_variant_is_owned_and_does_not_accept_price_or_stock(self):
        variant = self.multi_variants[0]
        payload = self.service.update_variant(
            self.product_with_variants,
            variant,
            {"sku": "VAR-UPDATED", "barcode": "BPI-VAR-UPDATED", "costUsd": 12.5, "active": True},
        )
        self.assertEqual(variant.default_code, "VAR-UPDATED")
        self.assertEqual(variant.barcode, "BPI-VAR-UPDATED")
        self.assertEqual(variant.standard_price, 12.5)
        self.assertEqual(payload["variantSummary"]["count"], 2)

        with self.assertRaises(UserError):
            self.service.update_variant(self.product_new, variant, {"sku": "CROSS"})
        with self.assertRaises(UserError):
            self.service.update_variant(self.product_with_variants, variant, {"priceUsd": 99})
        with self.assertRaises(UserError):
            self.service.update_variant(self.product_with_variants, variant, {"qtyAvailable": 99})

    def test_variant_image_accepts_valid_product_owned_sources_only(self):
        variant = self.multi_variants[0]
        encoded_png = base64.b64encode(PNG_1X1).decode()
        payload = self.service.set_variant_image(
            self.product_with_variants,
            variant,
            image_data_url="data:image/png;base64,%s" % encoded_png,
        )
        item = next(value for value in payload["variants"] if value["id"] == variant.id)
        self.assertTrue(item["hasOwnImage"])
        self.assertEqual(item["imageToken"], "variant:%s" % variant.id)

        with self.assertRaises(UserError):
            self.service.set_variant_image(
                self.product_with_variants,
                variant,
                image_token="main",
                remove=True,
            )
        with self.assertRaises(UserError):
            self.service.set_variant_image(self.product_new, variant, remove=True)

        removed = self.service.set_variant_image(self.product_with_variants, variant, remove=True)
        removed_item = next(value for value in removed["variants"] if value["id"] == variant.id)
        self.assertFalse(removed_item["hasOwnImage"])

    def test_pack_payload_calculates_modes_component_cost_and_warnings(self):
        payload = self.pack_product.bpi_build_payload()
        pack = payload["pack"]
        self.assertTrue(pack["isPack"])
        self.assertEqual(payload["product"]["productKind"], "pack")
        self.assertEqual(pack["componentCount"], 2)
        self.assertEqual(pack["componentCostMinUsd"], 15.0)
        self.assertEqual(pack["effectivePriceMinUsd"], 50.0)
        self.assertAlmostEqual(pack["marginMinPercent"], 70.0)
        self.assertTrue(pack["revision"])

        self.pack_product.write(
            {"pack_type": "detailed", "pack_component_price": "detailed"}
        )
        detailed_price = self.pack_product._bpi_effective_variant_price(self.pack_variant)
        self.assertAlmostEqual(detailed_price, 88.0)

        self.pack_component_b.product_variant_id.write({"active": False})
        warning_payload = self.pack_product.bpi_build_payload()["pack"]
        self.assertTrue(any("archivado" in warning for warning in warning_payload["warnings"]))
        self.pack_component_b.product_variant_id.write({"active": True})

    def test_update_pack_is_atomic_validated_and_revision_guarded(self):
        pack = self.pack_product.bpi_build_payload()["pack"]
        composition = pack["compositions"][0]
        values = {
            "packType": "detailed",
            "componentPriceMode": "ignored",
            "modifiable": True,
            "compositions": [
                {
                    "variantId": composition["variantId"],
                    "components": [
                        {
                            "lineId": component["lineId"],
                            "productVariantId": component["productVariantId"],
                            "quantity": 3 if component["sku"] == "COMP-A" else component["quantity"],
                            "saleDiscount": component["saleDiscount"],
                        }
                        for component in composition["components"]
                    ],
                }
            ],
        }
        updated = self.service.update_pack(self.pack_product, pack["revision"], values)
        component_a = self.pack_variant.pack_line_ids.filtered(
            lambda line: line.product_id == self.pack_component_a.product_variant_id
        )
        self.assertEqual(component_a.quantity, 3)
        self.assertFalse(self.pack_product.pack_modifiable)
        self.assertNotEqual(updated["pack"]["revision"], pack["revision"])

        with self.assertRaises(UserError):
            self.service.update_pack(self.pack_product, pack["revision"], values)

        current = self.pack_product.bpi_build_payload()["pack"]
        invalid_values = {
            "packType": "detailed",
            "componentPriceMode": "ignored",
            "modifiable": False,
            "compositions": [
                {
                    "variantId": self.pack_variant.id,
                    "components": [
                        {
                            "lineId": False,
                            "productVariantId": self.pack_variant.id,
                            "quantity": 1,
                            "saleDiscount": 0,
                        }
                    ],
                }
            ],
        }
        with self.assertRaises(UserError):
            self.service.update_pack(self.pack_product, current["revision"], invalid_values)

    def test_pack_component_search_excludes_current_product_and_archived_candidates(self):
        result = self.service.search_pack_components(self.pack_product, query="COMP-", limit=20)
        result_ids = {item["productVariantId"] for item in result["components"]}
        self.assertIn(self.pack_component_a.product_variant_id.id, result_ids)
        self.assertNotIn(self.pack_variant.id, result_ids)

        self.pack_component_a.product_variant_id.write({"active": False})
        archived = self.service.search_pack_components(self.pack_product, query="COMP-A", limit=20)
        self.assertFalse(archived["components"])
        self.pack_component_a.product_variant_id.write({"active": True})

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
            self.assertEqual(
                controller._variant(self.product_with_variants, self.multi_variants[0].id),
                self.multi_variants[0],
            )
            with self.assertRaises(MissingError):
                controller._variant(self.product_new, self.multi_variants[0].id)

        delete_signature = inspect.signature(controller.delete_image)
        self.assertIn("product_tmpl_id", delete_signature.parameters)
        self.assertIn("image_token", delete_signature.parameters)
        for method_name in ("scrape_competitor", "analyze_competitor", "delete_competitor"):
            self.assertIn("product_tmpl_id", inspect.signature(getattr(controller, method_name)).parameters)
        for method_name in ("update_variant", "set_variant_image"):
            signature = inspect.signature(getattr(controller, method_name))
            self.assertIn("product_tmpl_id", signature.parameters)
            self.assertIn("product_variant_id", signature.parameters)
        self.assertIn("packRevision", inspect.signature(controller.update_pack).parameters)
