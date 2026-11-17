# -*- coding: utf-8 -*-
"""The native per-user checkbox is an authorization boundary, not a menu hint.

These are real Odoo ACL/record-rule tests. All fixtures are transaction-local;
the suite must never call a provider, publish a product, or commit a job.
"""

import base64
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from odoo.exceptions import AccessError, MissingError
from odoo.tests.common import TransactionCase, tagged

from ..controllers.main import BaderProductIntelligenceController


@tagged("-at_install", "post_install")
class TestBPIModuleAccess(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group = cls.env.ref("bader_product_intelligence.group_bpi_user")
        cls.employee_group = cls.env.ref("base.group_user")
        # Odoo 16 has no product.group_product_manager. Use an existing native
        # catalog-editing role only on this synthetic test editor; the BPI role
        # itself must never imply this sales privilege.
        cls.catalog_editor_group = cls.env.ref("sales_team.group_sale_manager")
        cls.pack_line_model = cls.env["product.product"]._fields["pack_line_ids"].comodel_name
        cls.checkbox = "in_group_%s" % cls.group.id
        cls.company = cls.env.company

        def user(login, groups, **values):
            return cls.env["res.users"].with_context(
                no_reset_password=True, mail_create_nolog=True,
            ).create({
                "name": login, "login": login,
                "company_id": cls.company.id,
                "company_ids": [(6, 0, cls.company.ids)],
                "groups_id": [(6, 0, groups.ids)],
                **values,
            })

        cls.plain = user("bpi_access_plain", cls.employee_group)
        cls.module_only = user("bpi_access_module_only", cls.group)
        cls.editor = user("bpi_access_editor", cls.group | cls.catalog_editor_group)
        cls.admin = user("bpi_access_admin", cls.env.ref("base.group_system"))
        cls.portal = user("bpi_access_portal", cls.env.ref("base.group_portal"))
        cls.inactive = user("bpi_access_inactive", cls.group, active=False)
        cls.product = cls.env["product.template"].create({
            "name": "BPI access isolated product",
            "default_code": "BPI-ACCESS-TEST",
            "company_id": cls.company.id,
            "sale_ok": True,
            "website_published": False,
            "description_sale": "Original sales copy",
        })
        cls.service = cls.env["bpi.service"]

    def setUp(self):
        super().setUp()
        # Opening payloads and testing denied activation must be free of paid
        # or external work, including transports outside the OpenAI wrapper.
        transport = patch(
            "requests.sessions.Session.request",
            side_effect=AssertionError("Module-access tests must not use the network"),
        )
        self.network = transport.start()
        self.addCleanup(transport.stop)

    def _service(self, user):
        return self.service.with_user(user).sudo(False).with_context(allowed_company_ids=self.company.ids)

    def _assert_controller_access(self, user, allowed):
        with patch(
            "odoo.addons.bader_product_intelligence.controllers.main.request",
            SimpleNamespace(env=self._service(user).env),
        ):
            controller = BaderProductIntelligenceController()
            if allowed:
                controller._ensure_manager()
            else:
                with self.assertRaises(AccessError):
                    controller._ensure_manager()

    def _visible_menus(self, user):
        return self.env["ir.ui.menu"].with_user(user)._visible_menu_ids()

    def test_native_checkbox_is_boolean_without_a_second_user_permission_field(self):
        self.assertFalse(self.group.category_id)
        description = self.env["res.users"].fields_get([self.checkbox])
        self.assertEqual(description[self.checkbox]["type"], "boolean")
        self.assertEqual(self.group.implied_ids, self.employee_group)
        view = self.env.ref("bader_product_intelligence.view_users_form_bpi_access")
        self.assertIn(self.checkbox, view.arch_db, "XML loader must resolve the native group ID")
        self.assertNotIn("%(", view.arch_db, "No unresolved interpolation may reach the view")
        self.assertNotIn("base.group_no_one", view.arch_db, "The access control must not require debug mode")
        native = self.env["res.users"].with_user(self.admin).sudo(False).with_context(debug=False).get_view(
            view_id=self.env.ref("base.view_users_form").id, view_type="form",
        )
        form = ET.fromstring(native["arch"])
        control = form.find(".//group[@name='bpi_module_access']/field[@name='%s']" % self.checkbox)
        self.assertIsNotNone(control, "An ordinary active administrator must receive the visible native checkbox")

    def test_group_never_implies_system_access_rights_product_or_marketplace_roles(self):
        for xmlid in (
            "base.group_system", "base.group_erp_manager",
            "product.group_product_manager", "website.group_website_designer",
            "sales_team.group_sale_manager",
            "bader_mercadolibre.group_bader_meli_user",
            "bader_mercadolibre.group_bader_meli_manager",
        ):
            forbidden = self.env.ref(xmlid, raise_if_not_found=False)
            with self.subTest(group=xmlid):
                if forbidden:
                    self.assertNotIn(forbidden, self.group.trans_implied_ids)
                    self.assertNotIn(forbidden, self.module_only.groups_id)

    def test_native_checkbox_grants_and_revokes_model_controller_and_menus(self):
        root = self.env.ref("bader_product_intelligence.menu_bpi_root")
        products = self.env.ref("bader_product_intelligence.menu_bpi_products")
        for granted in (False, True, False):
            self.plain.write({self.checkbox: granted})
            with self.subTest(granted=granted):
                self.assertEqual(self.group in self.plain.groups_id, granted)
                self.assertEqual(self._service(self.plain)._has_module_access(), granted)
                self._assert_controller_access(self.plain, granted)
                if granted:
                    self._service(self.plain)._ensure_manager()
                else:
                    with self.assertRaises(AccessError):
                        self._service(self.plain)._ensure_manager()
                visible = self._visible_menus(self.plain)
                self.assertEqual(root.id in visible, granted)
                self.assertEqual(products.id in visible, granted)

    def test_plain_internal_user_cannot_self_grant_native_checkbox_or_group(self):
        restricted = self.plain.with_user(self.plain)
        for values in ({self.checkbox: True}, {"groups_id": [(4, self.group.id)]}):
            with self.subTest(values=values), self.assertRaises(AccessError), self.cr.savepoint():
                restricted.write(values)
        self.assertNotIn(self.group, self.plain.groups_id)
        self.assertFalse(self._service(self.plain)._has_module_access())

    def test_module_operator_cannot_grant_access_to_another_user(self):
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.plain.with_user(self.module_only).write({self.checkbox: True})
        self.assertNotIn(self.group, self.plain.groups_id)

    def test_inactive_and_portal_users_are_denied_even_if_menu_checks_are_bypassed(self):
        self.assertIn(self.group, self.inactive.groups_id)
        for user in (self.plain, self.portal, self.inactive):
            with self.subTest(user=user.login):
                self.assertFalse(self._service(user)._has_module_access())
                with self.assertRaises(AccessError):
                    self._service(user)._ensure_manager()
                self._assert_controller_access(user, False)

    def test_serializable_context_flags_cannot_forge_module_or_admin_authority(self):
        for user in (self.plain, self.portal, self.inactive):
            service = self._service(user).with_context(
                su=True, bpi_admin=True, bpi_access=True, uid=self.admin.id,
                groups=[self.group.id], _bpi_job_create=True,
            )
            with self.subTest(user=user.login):
                self.assertFalse(service.env.su)
                self.assertFalse(service._has_module_access())
                with self.assertRaises(AccessError):
                    service._ensure_manager()
                with self.assertRaises(AccessError):
                    service._ensure_admin()

    def test_active_system_admin_retains_access_without_module_checkbox(self):
        self.assertNotIn(self.group, self.admin.groups_id)
        self.assertTrue(self._service(self.admin)._has_module_access())
        self._service(self.admin)._ensure_manager()
        self._service(self.admin)._ensure_admin()
        self._assert_controller_access(self.admin, True)

    def test_module_acl_covers_persistent_operational_models_including_private_sources(self):
        # Jobs intentionally have an additional controlled-constructor boundary;
        # neither their ACL nor their writable fields authorizes raw job writes.
        for model in (
            "bpi.product.keyword", "bpi.product.faq", "bpi.product.image",
            "bpi.product.competitor", "bpi.product.chat.session", "bpi.product.chat.message",
            "bpi.content.template", "bpi.product.specification",
            "bpi.product.document.panel", "bpi.taxonomy.term",
            "bpi.content.studio.session", "bpi.content.studio.source",
            "bpi.content.studio.message", "bpi.content.studio.proposal",
            "bpi.description.media", "bpi.variant.content",
        ):
            for operation in ("read", "write", "create"):
                with self.subTest(model=model, operation=operation):
                    self.assertTrue(self.env[model].with_user(self.module_only).check_access_rights(
                        operation, raise_exception=False,
                    ))
        self.assertTrue(self.env["bpi.ai.job"].with_user(self.module_only).check_access_rights(
            "read", raise_exception=False,
        ))

    def test_module_data_remains_private_to_users_without_the_checkbox(self):
        for model in (
            "bpi.product.keyword", "bpi.product.faq", "bpi.content.studio.session",
            "bpi.content.studio.source", "bpi.content.studio.message", "bpi.ai.job",
        ):
            with self.subTest(model=model):
                self.assertFalse(self.env[model].with_user(self.plain).check_access_rights(
                    "read", raise_exception=False,
                ))

    def test_checkbox_does_not_change_native_catalog_or_business_acl(self):
        models = (
            "product.template", "product.product", "product.category",
            "product.public.category", "product.image", self.pack_line_model,
            "res.users", "ir.config_parameter", "ir.ui.view",
        )
        before = {
            (model, operation): self.env[model].with_user(self.plain).check_access_rights(
                operation, raise_exception=False,
            )
            for model in models for operation in ("read", "write", "create", "unlink")
        }
        self.plain.write({self.checkbox: True})
        after = {
            (model, operation): self.env[model].with_user(self.plain).check_access_rights(
                operation, raise_exception=False,
            )
            for model in models for operation in ("read", "write", "create", "unlink")
        }
        self.assertEqual(after, before)

    def test_module_only_reader_and_native_editor_can_open_real_payloads(self):
        for user in (self.module_only, self.editor):
            with self.subTest(user=user.login):
                payload = self.product.with_user(user).sudo(False).with_context(
                    allowed_company_ids=self.company.ids,
                ).bpi_build_payload()
                self.assertEqual(payload["product"]["id"], self.product.id)
                self.assertIn("contentTemplates", payload)
                self.assertIn("documents", payload)
                self.assertIn("seoData", payload)
                dashboard = self._service(user).dashboard_payload(search="BPI-ACCESS-TEST")
                self.assertIsInstance(dashboard, dict)
                if payload["product"]["stockReadAllowed"]:
                    self.assertIsInstance(payload["product"]["qtyAvailable"], float)
                else:
                    self.assertIsNone(payload["product"]["qtyAvailable"])
                    self.assertIsNone(payload["product"]["inStock"])
        # Force a native dependent-compute denial regardless of optional MRP
        # installation or quantities warmed by another fixture/environment.
        variant = self.product.product_variant_id.with_user(self.module_only).sudo(False)
        variant.invalidate_recordset(["qty_available", "free_qty", "virtual_available", "incoming_qty", "outgoing_qty"])
        def deny_quantities(records):
            # Native fields.determine inspects the callable's __name__.
            raise AccessError("Inventory denied")
        with patch.object(type(variant), "_compute_quantities", deny_quantities):
            stock = self.product.with_user(self.module_only)._bpi_stock_payload(variant)
        self.assertFalse(stock["stockReadAllowed"])
        self.assertTrue(all(stock[k] is None for k in ("qtyAvailable", "freeQty", "virtualAvailable", "incomingQty", "outgoingQty", "inStock")))
        with patch.object(type(variant), "check_access_rule", side_effect=AccessError("Product denied")):
            with self.assertRaises(AccessError):
                self.product.with_user(self.module_only)._bpi_stock_payload(variant)
        self.network.assert_not_called()

    def test_module_operator_image_presence_uses_only_authorized_metadata(self):
        png = base64.b64encode(base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        ))
        category = self.env["product.public.category"].create({"name": "BPI private image coverage"})
        self.product.write({"image_1920": png, "public_categ_ids": [(6, 0, category.ids)]})
        self.env.flush_all()
        attachment_model = self.env["ir.attachment"]
        attachment_type = type(attachment_model)
        image_ids = set(attachment_model.search([
            ("res_model", "=", "product.template"), ("res_field", "=", "image_1920"),
            ("res_id", "=", self.product.id), ("file_size", ">", 0),
        ]).ids)
        self.assertTrue(image_ids, "The fixture must use actual native attachment-backed image storage")
        service = self._service(self.module_only)
        product = service.env["product.template"].browse(self.product.id)
        original_read = attachment_type.read
        projected = []

        def metadata_read(records, fields=None, load="_classic_read"):
            if fields:
                self.assertFalse(any(records._fields[name].type == "binary" for name in fields),
                                 "Image coverage must never read binary values")
            if records.env.su:
                self.assertEqual(fields, ["res_id"], "Only parent IDs may be projected with elevated metadata access")
                self.assertTrue(set(records.ids) <= image_ids)
                projected.extend(records.ids)
            return original_read(records, fields, load=load)

        def no_file_read(records, *args, **kwargs):
            raise AssertionError("Image coverage must not read attachment bytes")

        def catalog_row(record, **unused):
            return {"id": record.id}

        self.env.invalidate_all()
        with patch.object(attachment_type, "_file_read", no_file_read), \
                patch.object(attachment_type, "read", metadata_read), \
                patch.object(type(product), "bpi_dashboard_payload", autospec=True, side_effect=catalog_row):
            self.assertEqual(service._dashboard_image_record_ids(product, "image_1920"), {self.product.id})
            overview = service.dashboard_overview(category_id=category.id)
            self.assertEqual(next(k["count"] for k in overview["kpis"] if k["key"] == "image"), 1)
            catalog = service.dashboard_payload(category_id=category.id, quality_filter="image")
            self.assertEqual(catalog["pager"]["total"], 1)
            self.assertTrue(catalog["products"][0]["catalogHealth"]["image"])
        self.assertTrue(projected, "The non-system user exercised the narrow parent-ID metadata path")
        for guard in ("check_access_rights", "check_access_rule", "check_field_access_rights"):
            with self.subTest(guard=guard), \
                    patch.object(type(product), guard, side_effect=AccessError("Parent image access denied")), \
                    patch.object(attachment_type, "read") as forbidden_metadata:
                with self.assertRaises(AccessError):
                    service._dashboard_image_record_ids(product, "image_1920")
                forbidden_metadata.assert_not_called()
        self.network.assert_not_called()

    def test_editor_saves_reviewed_content_without_global_administration(self):
        service = self._service(self.editor)
        product = service._meli_product(self.product.id)
        result = service.save_content(product, {
            "description": "<p>Explicitly reviewed commercial copy.</p>",
            "technicalDescription": "<p>Explicitly reviewed technical copy.</p>",
        })
        self.assertEqual(result["product"]["id"], self.product.id)
        self.assertIn("reviewed commercial", self.product.bpi_ai_generated_description)
        self.assertIn("reviewed technical", self.product.bpi_technical_description)
        self.assertFalse(self.editor.has_group("base.group_system"))
        self.assertFalse(self.product.website_published)
        self.network.assert_not_called()

    def test_borrowing_a_superuser_record_does_not_bypass_service_guard(self):
        with self.assertRaises(AccessError):
            self._service(self.plain).save_content(self.product, {"description": "Not authorized"})
        self.assertNotIn("Not authorized", self.product.bpi_ai_generated_description or "")

    def test_company_rules_hide_foreign_product_keyword_and_reject_direct_lookup(self):
        other = self.env["res.company"].create({"name": "BPI access other company"})
        foreign = self.env["product.template"].create({
            "name": "Foreign BPI private product", "company_id": other.id,
        })
        keyword = self.env["bpi.product.keyword"].create({
            "name": "foreign private keyword", "product_tmpl_id": foreign.id,
        })
        allowed_keyword = self.env["bpi.product.keyword"].create({
            "name": "permitted keyword", "product_tmpl_id": self.product.id,
        })
        restricted = self._service(self.editor).env["bpi.product.keyword"]
        self.assertFalse(restricted.search([("id", "=", keyword.id)]))
        self.assertEqual(restricted.search([("id", "=", allowed_keyword.id)]).ids, allowed_keyword.ids)
        with self.assertRaises(AccessError):
            restricted.browse(keyword.id).read(["name"])
        with self.assertRaises(MissingError):
            self._service(self.editor)._meli_product(foreign.id)

    def test_global_exchange_rate_and_nancy_activation_remain_system_only(self):
        params = self.env["ir.config_parameter"].sudo()
        before = params.get_param("bader_product_intelligence.exchange_rate")
        for user in (self.module_only, self.editor):
            with self.subTest(user=user.login):
                service = self._service(user)
                with self.assertRaises(AccessError):
                    service.update_exchange_rate(9876)
                with self.assertRaises(AccessError):
                    service._studio_activate(self.product.id)
                with self.assertRaises(AccessError):
                    service._ensure_admin()
        self.assertEqual(params.get_param("bader_product_intelligence.exchange_rate"), before)
        self.network.assert_not_called()

    def test_website_configuration_and_global_bridge_sync_remain_admin_only(self):
        website = self.env["website"].create({"name": "BPI access isolated website"})
        for user in (self.module_only, self.editor):
            with self.subTest(user=user.login):
                with self.assertRaises(AccessError):
                    website.with_user(user).write({"bpi_premium_footer_legal_name": "Not authorized"})
                with self.assertRaises(AccessError):
                    self.env["ir.ui.view"].with_user(user).bpi_sync_product_description_bridges()

    def test_private_import_receipt_is_not_exposed_in_editor_payload(self):
        self.product.bpi_editorial_import = {"date": "private receipt", "sku": "private source"}
        product = self.product.with_user(self.editor)
        with self.assertRaises(AccessError):
            product.read(["bpi_editorial_import"])
        self.assertFalse(product.bpi_build_payload()["product"]["editorialImport"])

    def test_private_job_diagnostics_are_not_exposed_to_module_operator(self):
        job = self.env["bpi.ai.job"].create({
            "product_tmpl_id": self.product.id, "job_type": "content_studio",
            "requested_by_id": self.editor.id, "state": "failed",
            "studio_diagnostic": {"requestId": "private-admin-diagnostic"},
        })
        restricted = job.with_user(self.editor).sudo(False).with_context(
            allowed_company_ids=self.company.ids,
        )
        with self.assertRaises(AccessError):
            restricted.read(["studio_diagnostic"])
        self.assertEqual(restricted.bpi_to_payload().get("diagnostic"), {})

    def test_job_constructor_uses_calling_user_and_rejects_requester_impersonation(self):
        jobs = self.env["bpi.ai.job"].with_user(self.editor).with_context(
            allowed_company_ids=self.company.ids, bpi_no_job_commit=True,
        )
        with self.assertRaises(AccessError):
            jobs.create_seo_job(self.product, user=self.admin)
        job = jobs.create_seo_job(self.product)
        self.assertEqual(job.requested_by_id, self.editor)
        self.assertEqual(job.state, "pending")
        self.assertTrue(job.semantic_request)
        self.network.assert_not_called()

    def test_raw_job_create_cannot_forge_requester_or_paid_payload(self):
        jobs = self.env["bpi.ai.job"].with_user(self.editor)
        for values in (
            {"product_tmpl_id": self.product.id, "requested_by_id": self.admin.id},
            {"product_tmpl_id": self.product.id, "requested_by_id": self.editor.id,
             "semantic_request": {"companies": self.company.ids, "revision": "forged"}},
        ):
            for context in ({}, {"_bpi_job_create": True}, {"_bpi_job_create": "trusted"}):
                with self.subTest(values=values, context=context), self.assertRaises(AccessError), self.cr.savepoint():
                    jobs.with_context(**context).create(values)
        self.network.assert_not_called()

    def test_raw_job_writes_and_delete_are_denied_after_authorized_enqueue(self):
        jobs = self.env["bpi.ai.job"].with_user(self.editor).with_context(
            allowed_company_ids=self.company.ids, bpi_no_job_commit=True,
        )
        job = jobs.create_seo_job(self.product)
        for values in ({"requested_by_id": self.admin.id}, {"state": "done"},
                       {"semantic_request": {"companies": [], "revision": "forged"}}):
            with self.subTest(values=values), self.assertRaises(AccessError), self.cr.savepoint():
                job.write(values)
        with self.assertRaises(AccessError), self.cr.savepoint():
            job.unlink()
        self.assertEqual(job.requested_by_id, self.editor)
        self.assertEqual(job.state, "pending")

    def test_revoke_checkbox_blocks_enqueued_paid_work_before_provider_call(self):
        job = self.env["bpi.ai.job"].with_user(self.editor).with_context(
            allowed_company_ids=self.company.ids, bpi_no_job_commit=True,
        ).create_seo_job(self.product)
        self.editor.write({self.checkbox: False})
        with patch.object(type(self.service), "analyze_seo") as provider:
            with self.assertRaises(AccessError):
                job.sudo()._process_seo_job()
            provider.assert_not_called()
        self.network.assert_not_called()

    def test_classification_operator_enqueue_process_and_revoke_before_provider(self):
        jobs = self._service(self.editor).env["bpi.ai.job"].with_context(
            bpi_no_job_commit=True,
        )
        job = jobs._create_classification_job(self.product)
        self.assertEqual(job.requested_by_id, self.editor)
        self.assertEqual(job.job_type, "classification")
        self.assertEqual(job.state, "pending")
        self.assertEqual(job.classification_request["companies"], self.company.ids)
        self.assertIsNone(job.env.context.get("_bpi_job_create"))
        before = self.product.bpi_taxonomy_term_ids.ids
        proposal = {"termIds": [], "warnings": [], "newTerms": [], "reasons": "No new facts"}
        with patch.object(type(self.service), "_classification_proposal", return_value=proposal) as provider:
            result = job.sudo()._process_classification_job()
            provider.assert_called_once()
        self.assertEqual(result["classificationProposal"]["termIds"], [])
        self.assertEqual(self.product.bpi_taxonomy_term_ids.ids, before)
        self.editor.write({self.checkbox: False})
        with patch.object(type(self.service), "_classification_proposal") as provider:
            with self.assertRaises(AccessError):
                job.sudo()._process_classification_job()
            provider.assert_not_called()
        self.network.assert_not_called()

    def test_studio_operator_enqueue_process_and_revoke_before_provider(self):
        service = self._service(self.editor).with_context(bpi_no_job_commit=True)
        before = (self.product.bpi_ai_generated_description, self.product.bpi_technical_description,
                  self.product.website_published)
        # Availability is an admin-owned capability. The operator only consumes
        # an already enabled configuration; no activation or paid probe occurs.
        with patch.object(type(service), "_studio_availability", return_value={
            "enabled": True, "checkedAt": False, "reason": "",
        }):
            session_data = service._studio_open(self.product.id)["session"]
            envelope = service._studio_start(
                self.product.id, session_data["id"], session_data["revision"],
                "Aclara la estrategia sin crear una propuesta.", str(uuid4()),
            )
        job = service.env["bpi.ai.job"].browse(envelope["job"]["id"])
        self.assertEqual(job.requested_by_id, self.editor)
        self.assertEqual(job.job_type, "content_studio")
        self.assertEqual(job.state, "pending")
        self.assertEqual(job.studio_request["companies"], self.company.ids)
        self.assertIsNone(job.env.context.get("_bpi_job_create"))
        with patch.object(type(service), "_studio_post", return_value={
            "reply": "Orientación editorial para revisar.", "hasProposal": False,
        }) as provider:
            result = job.sudo()._process_content_studio_job()
            provider.assert_called_once()
        self.assertEqual(result["sessionId"], session_data["id"])
        self.assertFalse(result["proposalId"])
        self.assertEqual(before, (self.product.bpi_ai_generated_description,
                                self.product.bpi_technical_description, self.product.website_published))
        self.editor.write({self.checkbox: False})
        with patch.object(type(service), "_studio_post") as provider:
            with self.assertRaises(AccessError):
                job.sudo()._process_content_studio_job()
            provider.assert_not_called()
        self.network.assert_not_called()

