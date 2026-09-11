# -*- coding: utf-8 -*-

import base64
from types import SimpleNamespace
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

from ..controllers.main import BaderProductIntelligenceController


PNG = base64.b64encode(base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
))


@tagged("-at_install", "post_install")
class TestBPIDashboardOverview(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["bpi.service"]
        cls.root_category = cls.env["product.public.category"].create({"name": "BPI Dashboard Scope"})
        cls.child_category = cls.env["product.public.category"].create({
            "name": "BPI Dashboard Child", "parent_id": cls.root_category.id,
        })
        cls.empty_category = cls.env["product.public.category"].create({"name": "BPI Dashboard Empty"})
        defaults = {
            "sale_ok": True, "website_published": False,
            "public_categ_ids": [(6, 0, cls.root_category.ids)],
        }
        cls.complete = cls.env["product.template"].create({
            **defaults, "name": "BPI Dashboard Complete", "default_code": "BPI-DASH-COMPLETE",
            "website_published": True, "bpi_featured": True,
            "description_sale": "Descripción comercial nativa",
            "bpi_technical_description": "<p>Ficha técnica confirmada</p>",
            "website_meta_title": "Título SEO", "website_meta_description": "Descripción SEO",
            "bpi_geo_title": "Título GEO", "bpi_geo_description": "Descripción GEO",
            "image_1920": PNG,
            "public_categ_ids": [(6, 0, (cls.root_category + cls.child_category).ids)],
            "bpi_faq_ids": [(0, 0, {"question": "¿Uso?", "answer": "Profesional"})],
            "bpi_competitor_ids": [(0, 0, {
                "competitor_name": "Registrado", "competitor_url": "https://example.com/producto",
                "scrape_status": "pending",
            })],
        })
        cls.empty = cls.env["product.template"].create({
            **defaults, "name": "BPI Dashboard Empty Published", "default_code": "BPI-DASH-EMPTY",
            "website_published": True, "bpi_ai_generated_description": "<p><br/></p>",
            "bpi_technical_description": "<p>&nbsp;</p>",
            "website_meta_title": " ", "website_meta_description": "<p><br/></p>",
            "bpi_geo_title": " ", "bpi_geo_description": " ",
            "public_categ_ids": [(6, 0, cls.child_category.ids)],
            "bpi_faq_ids": [(0, 0, {"question": " ", "answer": "<p><br/></p>"})],
            "bpi_competitor_ids": [(0, 0, {"competitor_name": "Vacío", "competitor_url": " "})],
        })
        cls.draft = cls.env["product.template"].create({
            **defaults, "name": "BPI Dashboard Draft", "default_code": "BPI-DASH-DRAFT",
        })
        cls.archived = cls.env["product.template"].create({
            **defaults, "name": "BPI Dashboard Archived", "website_meta_title": "SEO archivado",
            "website_meta_description": "Descripción archivada",
        })
        cls.archived.active = False
        cls.not_saleable = cls.env["product.template"].create({
            **defaults, "name": "BPI Dashboard Not Saleable", "sale_ok": False,
        })
        cls.manager = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "BPI Dashboard Manager", "login": "bpi_dashboard_test_manager",
            "groups_id": [(6, 0, [cls.env.ref("base.group_system").id])],
            "company_id": cls.env.company.id, "company_ids": [(6, 0, cls.env.company.ids)],
        })
        cls.non_manager = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "BPI Dashboard Internal", "login": "bpi_dashboard_test_internal",
            "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
        })

    def _overview(self, service=None, category=None):
        # Abstract service recordsets are empty/falsy even with a distinct user
        # or company context; never discard that explicitly supplied environment.
        service = self.service if service is None else service
        return service.dashboard_overview(
            category_id=(category or self.root_category).id,
        )

    def _catalog(self, service=None, **kwargs):
        # Overview/filter tests isolate the predicate contract from existing
        # operational row enrichment (stock/MRP/Pack), covered by legacy tests.
        with patch.object(type(self.env["product.template"]), "bpi_dashboard_payload", autospec=True,
                          side_effect=lambda product, **unused: {"id": product.id}):
            service = self.service if service is None else service
            return service.dashboard_payload(category_id=self.root_category.id, **kwargs)

    def _counts(self, overview):
        return {item["key"]: item["count"] for item in overview["kpis"]}

    def test_overview_exact_eight_kpis_and_active_saleable_universe(self):
        overview = self._overview()
        self.assertEqual(self._counts(overview), {
            "all": 3, "published": 2, "content": 1, "image": 1,
            "seo": 1, "geo": 1, "faq": 1, "competitor": 1,
        })
        self.assertEqual(overview["total"], 3)
        self.assertEqual(overview["publication"], {
            "published": 2, "unpublished": 1, "total": 3, "publishedPercent": 66.7,
        })
        self.assertTrue(overview["generatedAt"].endswith("Z"))
        self.assertEqual(overview["categoryId"], self.root_category.id)
        self.assertEqual(self._catalog()["stats"], {"total": 3, "published": 2, "featured": 1, "pending": 1})

    def test_every_metric_and_priority_drills_down_to_its_exact_count(self):
        overview = self._overview()
        for item in overview["kpis"] + overview["coverage"] + overview["priorities"]:
            with self.subTest(filter=item["filter"]):
                payload = self._catalog(quality_filter=item["filter"], limit=120)
                self.assertEqual(payload["pager"]["total"], item["count"])
                self.assertEqual(len(payload["products"]), item["count"])
                self.assertEqual(payload["tabCounts"]["all"], item["count"])
                self.assertEqual(item["percent"], round(item["count"] * 100.0 / 3, 1))

    def test_category_child_of_and_multiple_membership_do_not_duplicate(self):
        root = self._overview()
        child = self._overview(category=self.child_category)
        self.assertEqual(root["total"], 3)
        self.assertEqual(child["total"], 2)
        self.assertEqual(self._counts(child)["content"], 1)
        self.assertIn(self.child_category.id, [row["id"] for row in root["categories"]])

    def test_empty_catalog_has_zero_percentages_and_empty_jobs(self):
        overview = self._overview(category=self.empty_category)
        self.assertEqual(overview["total"], 0)
        self.assertTrue(all(item["count"] == item["percent"] == 0 for item in overview["kpis"]))
        self.assertEqual(overview["jobs"], {"pending": 0, "running": 0, "done": 0, "failed": 0, "recent": []})

    def test_empty_html_and_commercial_fallback_match_product_detail(self):
        self.assertFalse(self.empty._bpi_description_payload()["contentDescription"])
        self.empty.write({"description": "Ficha nativa usada como último fallback", "bpi_technical_description": "<p>Datos</p>"})
        overview = self._overview()
        self.assertEqual(self._counts(overview)["content"], 2)
        self.assertEqual(overview["priorities"][1]["count"], 0)
        self.assertEqual(self._counts(overview)["seo"], 1)
        self.assertEqual(self._counts(overview)["faq"], 1)

    def test_native_extra_variant_and_approved_bpi_image_fallbacks(self):
        self.env["product.image"].create({
            "name": "Galería nativa", "product_tmpl_id": self.empty.id, "image_1920": PNG,
        })
        self.env["bpi.product.image"].create({
            "name": "Preview no cuenta", "product_tmpl_id": self.draft.id, "image_1920": PNG, "state": "preview",
        })
        self.assertEqual(self._counts(self._overview())["image"], 2)
        approved = self.env["bpi.product.image"].create({
            "name": "Aprobada", "product_tmpl_id": self.draft.id, "image_1920": PNG, "state": "approved",
        })
        self.assertEqual(self._counts(self._overview())["image"], 3)
        approved.unlink()
        self.draft.product_variant_id.image_variant_1920 = PNG
        self.assertEqual(self._counts(self._overview())["image"], 3)
        for product in self.complete + self.empty + self.draft:
            self.assertTrue(product.with_context(bin_size=True)._bpi_primary_image_url())

    def test_archived_variant_image_and_pack_count_once_per_template(self):
        attribute = self.env["product.attribute"].create({"name": "BPI Dashboard Size", "create_variant": "always"})
        values = self.env["product.attribute.value"].create([
            {"name": name, "attribute_id": attribute.id} for name in ("A", "B")
        ])
        self.draft.write({
            "pack_ok": True,
            "attribute_line_ids": [(0, 0, {"attribute_id": attribute.id, "value_ids": [(6, 0, values.ids)]})],
        })
        variants = self.draft.product_variant_ids.sorted("id")
        self.assertEqual(len(variants), 2)
        variants[1].write({"image_variant_1920": PNG, "active": False})
        overview = self._overview()
        self.assertEqual(overview["total"], 3)
        self.assertEqual(self._counts(overview)["image"], 2)
        self.assertTrue(self.draft.with_context(bin_size=True)._bpi_primary_image_url())

    def test_archived_tab_intersects_quality_and_tab_counts_include_search(self):
        payload = self._catalog(tab="discontinued", quality_filter="seo")
        self.assertEqual([row["id"] for row in payload["products"]], self.archived.ids)
        self.assertEqual(payload["tabCounts"], {"all": 1, "new": 0, "discontinued": 1})
        filtered = self._catalog(search="BPI-DASH-EMPTY", quality_filter="missing_seo")
        self.assertEqual(filtered["pager"]["total"], 1)
        self.assertEqual(filtered["tabCounts"], {"all": 1, "new": 0, "discontinued": 0})
        self.assertEqual(filtered["stats"]["total"], 3, "Headline ignores catalog text/quality, not category")

    def test_pagination_clamps_after_filter_change_and_handles_empty_results(self):
        payload = self._catalog(page=99, limit=1)
        self.assertEqual(payload["pager"]["page"], 3)
        self.assertFalse(payload["pager"]["hasNext"])
        payload = self._catalog(search="NOT-A-MATCH", page=99)
        self.assertEqual(payload["pager"]["page"], 1)
        self.assertEqual(payload["pager"]["pageCount"], 1)
        self.assertFalse(payload["pager"]["hasPrevious"])

    def test_missing_category_priority_uses_ecommerce_categories(self):
        self.draft.public_categ_ids = [(5, 0, 0)]
        with patch.object(type(self.service), "_dashboard_base_domain", return_value=[("id", "in", (self.complete + self.draft).ids)]):
            overview = self.service.dashboard_overview()
            self.assertEqual(overview["priorities"][-1]["filter"], "missing_category")
            self.assertEqual(overview["priorities"][-1]["count"], 1)
            self.assertEqual(overview["coverage"][-1]["count"], 1)

    def test_job_counts_and_latest_five_are_scoped_and_do_not_leak_payloads(self):
        jobs = self.env["bpi.ai.job"]
        for index, state in enumerate(("done", "done", "failed", "done", "pending", "running")):
            jobs.create({
                "product_tmpl_id": self.complete.id, "state": state, "target_audience": "audience-%s" % index,
                "result_payload": {"private": "not-for-dashboard"}, "error_message": "private-error",
            })
        jobs.create({"product_tmpl_id": self.archived.id, "state": "pending"})
        overview = self._overview()
        self.assertEqual({key: overview["jobs"][key] for key in ("pending", "running", "done", "failed")}, {
            "pending": 1, "running": 1, "done": 3, "failed": 1,
        })
        self.assertEqual(len(overview["jobs"]["recent"]), 5)
        self.assertEqual(overview["jobs"]["recent"][0]["state"], "running")
        self.assertNotIn("private", str(overview))
        self.assertTrue(all(row["productId"] == self.complete.id for row in overview["jobs"]["recent"]))

    def test_invalid_inputs_are_rejected_instead_of_silently_broadening(self):
        for category_id in (True, 0, -1, 1.5, "bad", [], {}, 999999999):
            with self.subTest(category_id=category_id), self.assertRaises(UserError):
                self.service.dashboard_overview(category_id=category_id)
        for quality_filter in ("unknown", True, [], {}):
            with self.subTest(quality_filter=quality_filter), self.assertRaises(UserError):
                self.service.dashboard_payload(quality_filter=quality_filter)
        with self.assertRaises(UserError):
            self.service.dashboard_payload(tab="invalid")
        with self.assertRaises(UserError):
            self.service.dashboard_payload(search={})

    def test_admin_guards_apply_at_model_and_route(self):
        service = self.service.with_user(self.non_manager)
        for method in (service.dashboard_overview, service.dashboard_payload, service.sync_catalog):
            with self.assertRaises(AccessError):
                method()
        controller = BaderProductIntelligenceController()
        with patch("odoo.addons.bader_product_intelligence.controllers.main.request", SimpleNamespace(env=service.env)):
            for method in (controller.dashboard_overview, controller.dashboard, controller.sync_catalog):
                with self.assertRaises(AccessError):
                    method()

    def test_controller_forwards_category_and_quality_filter_without_mutating(self):
        controller = BaderProductIntelligenceController()
        with patch("odoo.addons.bader_product_intelligence.controllers.main.request", SimpleNamespace(env=self.env)):
            self.assertEqual(controller.dashboard_overview(category_id=self.root_category.id)["total"], 3)
            with patch.object(type(self.service), "dashboard_payload", return_value={"products": []}) as call:
                controller.dashboard(category_id=self.root_category.id, quality_filter="image", page=2)
                self.assertEqual(call.call_args.kwargs["category_id"], self.root_category.id)
                self.assertEqual(call.call_args.kwargs["quality_filter"], "image")
                self.assertEqual(call.call_args.kwargs["page"], 2)
                controller.sync_catalog(category_id=self.root_category.id, quality_filter="seo")
                self.assertEqual(call.call_args.kwargs["quality_filter"], "seo")

    def test_product_record_rules_are_respected_in_metrics_catalog_and_jobs(self):
        self.env["bpi.ai.job"].create({"product_tmpl_id": self.complete.id, "state": "done"})
        self.env["ir.rule"].create({
            "name": "BPI Dashboard hide complete product", "model_id": self.env["ir.model"]._get_id("product.template"),
            "domain_force": "[('id', '!=', %s)]" % self.complete.id,
        })
        service = self.service.with_user(self.manager)
        overview = self._overview(service=service)
        self.assertEqual(overview["total"], 2)
        self.assertEqual(self._counts(overview)["content"], 0)
        self.assertEqual(overview["jobs"]["recent"], [])
        self.assertEqual(self._catalog(service=service)["pager"]["total"], 2)

    def test_selected_companies_filter_even_when_admin_has_both_companies(self):
        other = self.env["res.company"].create({"name": "BPI Dashboard Other Company"})
        self.manager.company_ids = [(4, other.id)]
        self.draft.company_id = other
        service = self.service.with_user(self.manager).with_context(allowed_company_ids=self.env.company.ids)
        self.assertEqual(self._overview(service=service)["total"], 2)
        service = service.with_context(allowed_company_ids=(self.env.company + other).ids)
        self.assertEqual(self._overview(service=service)["total"], 3)

    def test_related_record_rules_do_not_leak_faq_or_competitor_coverage(self):
        for model in ("bpi.product.faq", "bpi.product.competitor"):
            self.env["ir.rule"].create({
                "name": "BPI Dashboard hide related %s" % model,
                "model_id": self.env["ir.model"]._get_id(model),
                "domain_force": "[('product_tmpl_id', '!=', %s)]" % self.complete.id,
            })
        counts = self._counts(self._overview(service=self.service.with_user(self.manager)))
        self.assertEqual(counts["all"], 3)
        self.assertEqual(counts["faq"], 0)
        self.assertEqual(counts["competitor"], 0)

    def test_coverage_query_count_does_not_grow_per_product(self):
        extra = self.env["product.template"].create([
            {"name": "BPI Dashboard Batch %s" % index, "sale_ok": True}
            for index in range(24)
        ])
        self.env.flush_all()

        def query_count(products):
            self.env.invalidate_all()
            before = self.env.cr.sql_log_count
            self.service._dashboard_coverage_sets(products)
            return self.env.cr.sql_log_count - before

        single_count = query_count(self.complete)
        batch_count = query_count(self.complete + extra)
        self.assertLessEqual(batch_count, single_count + 6, "Coverage must batch reads, not add a query per product")

    def test_overview_uses_batched_metadata_reads_without_row_detail_or_external_calls(self):
        products = self.complete + self.empty + self.draft
        observations = []
        model_type = type(self.env["product.template"])
        original = model_type.read

        def observe(records, *args, **kwargs):
            field_names = args[0] if args else kwargs.get("fields")
            if field_names:
                self.assertFalse(any(records._fields[name].type == "binary" for name in field_names))
            if field_names and "bpi_technical_description" in field_names:
                observations.append(len(records))
            return original(records, *args, **kwargs)

        before = products.read(["write_date"])
        with patch.object(model_type, "read", observe), \
                patch.object(model_type, "bpi_dashboard_payload", side_effect=AssertionError("No row enrichment")), \
                patch.object(model_type, "bpi_build_payload", side_effect=AssertionError("No detail enrichment")), \
                patch.object(type(self.service), "_openai_request", side_effect=AssertionError("No AI calls")), \
                patch("requests.sessions.Session.request", side_effect=AssertionError("No external HTTP")):
            self._overview()
        self.assertEqual(observations, [3])
        self.assertEqual(products.read(["write_date"]), before)

    def test_cold_image_coverage_never_reads_attachment_bytes(self):
        self.env["product.image"].create({
            "name": "Cold gallery", "product_tmpl_id": self.empty.id, "image_1920": PNG,
        })
        self.draft.product_variant_id.image_variant_1920 = PNG
        self.env.flush_all()
        for service in (self.service, self.service.with_user(self.manager)):
            self.env.invalidate_all()
            with patch.object(type(self.env["ir.attachment"]), "_file_read",
                              side_effect=AssertionError("Dashboard must never load attachment bytes")):
                self.assertEqual(self._counts(self._overview(service=service))["image"], 3)
                self.assertEqual(self._catalog(service=service, quality_filter="image")["pager"]["total"], 3)
