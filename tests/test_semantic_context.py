# -*- coding: utf-8 -*-
"""Saved semantics are vocabulary, not technical evidence or automatic publication.

All provider responses are controlled fixtures. The transport is blocked even
when a test forgets its response mock. Transaction fixtures never reach a paid
provider or require committed catalog changes.
"""

import json
from unittest.mock import patch

from odoo.exceptions import AccessError, MissingError, UserError
from odoo.tests.common import TransactionCase, tagged

from ..models.content_generation import CONTENT_TEMPLATE_UNSET
from ..models.taxonomy import digest


@tagged("-at_install", "post_install")
class TestBPISemanticContext(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["bpi.service"]
        cls.Term = cls.env["bpi.taxonomy.term"]
        cls.Product = cls.env["product.template"]
        cls.clinic = cls.env.ref("bader_product_intelligence.taxonomy_seed_0")
        cls.students = cls.env.ref("bader_product_intelligence.taxonomy_seed_2")
        cls.universal = cls.env.ref("bader_product_intelligence.taxonomy_seed_3")
        cls.commercial = cls.Term.create({
            "name": "Instrumental semántico fixture", "axis": "commercial", "state": "approved",
        })
        cls.technical = cls.Term.create({
            "name": "Restauración semántica fixture", "axis": "technical", "state": "approved",
        })
        cls.use = cls.Term.create({
            "name": "Modelar composite semántico", "axis": "use", "state": "approved",
            "aliases_text": "modelado resina semántica\nMODELADO RESINA SEMÁNTICA",
            "definition": "Uso editorial revisado, no prueba de medidas o esterilización.",
        })
        cls.draft = cls.Term.create({
            "name": "SEM_PENDING_NOT_APPROVED", "axis": "use",
            "aliases_text": "sem pending alias",
        })
        cls.excluded = cls.Term.create({
            "name": "SEM_EXCLUDED_NOT_SELECTED", "axis": "technical", "state": "approved",
            "aliases_text": "sem excluded alias",
        })
        cls.recipe = cls.env["bpi.content.template"].create({
            "name": "SEM_SAVED_RECIPE", "format": "free",
            "short_instructions": "SEM_SHORT_MODEL conservar instrucciones propias.",
            "long_instructions": "SEM_LONG_MODEL usar solo datos confirmados.",
            "short_min_words": 0, "short_max_words": 0,
        })
        cls.internal_category = cls.env["product.category"].create({"name": "SEM_SIMPLE_IMPORTED_CATEGORY"})
        cls.store_category = cls.env["product.public.category"].create({"name": "SEM_EXISTING_STORE_CATEGORY"})
        cls.product = cls.Product.create({
            "name": "Espátula para composite SEM_PRODUCT", "default_code": "SEM/17-4065",
            "categ_id": cls.internal_category.id,
            "public_categ_ids": [(6, 0, cls.store_category.ids)],
            "bpi_content_template_id": cls.recipe.id,
            "description_sale": "SEM_SAVED_COMMERCIAL_COPY",
            "bpi_ai_generated_description": "<p>SEM_OLD_AI_NOT_EVIDENCE</p>",
            "bpi_technical_description": "<p>SEM_OLD_TECH_NOT_EVIDENCE</p>",
            "website_meta_title": "SEM_SAVED_SEO", "bpi_geo_title": "SEM_SAVED_GEO",
            "bpi_faq_ids": [(0, 0, {"question": "¿SEM saved FAQ?", "answer": "Conservar."})],
        })
        cls.reader = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "BPI semantic internal reader", "login": "bpi_semantic_internal_reader",
            "groups_id": [(6, 0, cls.env.ref("base.group_user").ids)],
        })

    def setUp(self):
        super().setUp()
        transport = patch.object(type(self.service), "_openai_request", side_effect=AssertionError(
            "Semantic tests cannot call external providers"
        ))
        self.transport = transport.start()
        self.addCleanup(transport.stop)

        # Production uses a separate READ ONLY cursor to observe concurrent
        # commits. These uncommitted fixtures need same-transaction visibility;
        # retain the actual pre/post comparison, not a blanket guard bypass.
        def fixture_content_context(service, product_id, template_id=CONTENT_TEMPLATE_UNSET):
            return service.content_template_context(service._meli_product(product_id), template_id)

        freshness = patch.object(type(self.service), "_content_template_fresh_context", fixture_content_context)
        freshness.start()
        self.addCleanup(freshness.stop)

        def fixture_semantic_context(service, product_id):
            return service._meli_product(product_id)._bpi_semantic_context()

        semantic_freshness = patch.object(type(self.service), "_semantic_context_fresh", fixture_semantic_context)
        semantic_freshness.start()
        self.addCleanup(semantic_freshness.stop)

    def _save(self, terms, excluded=None, product=None):
        product = product or self.product
        data = {
            "termIds": terms.ids, "revision": product.bpi_classification_revision,
            "vocabularyRevision": self.Term._revision(),
        }
        if excluded is not None:
            data["excludedTermIds"] = excluded.ids
        return self.service.save_category(product, {"classification": data})

    def _jobs(self):
        # TransactionCase's superuser/OdooBot is not an active human requester.
        return self.env["bpi.ai.job"].with_user(self.env.ref("base.user_admin")).with_context(
            bpi_no_job_commit=True,
        )

    def _assert_semantic_job_failure(self, job):
        self.assertEqual(job.state, "failed", job.error_message)
        # A failure must actually be stale semantics, not missing requester,
        # permissions, company access or an uncommitted-fixture visibility bug.
        self.assertIn("clasificación guardada", (job.error_message or "").lower())
        self.assertIn("cambiaron", (job.error_message or "").lower())
        self.assertFalse(job.result_payload)

    def _snapshot(self):
        return self.product.read([
            "name", "categ_id", "public_categ_ids", "bpi_content_template_id", "description_sale",
            "bpi_ai_generated_description", "bpi_technical_description", "website_meta_title",
            "bpi_geo_title", "bpi_faq_ids", "bpi_taxonomy_term_ids", "bpi_classification_revision",
            "bpi_classification_excluded_ids", "website_published", "write_date",
        ])[0]

    def _context_ids(self, context):
        return {row["id"] for rows in context["axes"].values() for row in rows}

    def _proposal_response(self, **values):
        response = {"termIds": [], "reasons": "Sin evidencia suficiente.", "warnings": [], "newTerms": []}
        response.update(values)
        return response

    def _niche_evaluations(self, selected, overrides=None):
        overrides = overrides or {}
        return [dict({
            "termId": row["id"],
            "decision": "suggested" if row["id"] in selected else "insufficient_evidence",
            "reason": "Uso o compra justificados." if row["id"] in selected else "Sin evidencia suficiente para este público.",
        }, **overrides.get(row["id"], {})) for row in self.Term._catalog()
            if row["axis"] == "niche" and not row["universal"]]

    def _proposal(self, response, product=None):
        product = product or self.product
        with patch.object(type(self.service), "_openai_json", return_value=response) as provider:
            result = self.service._classification_proposal(
                product, product._bpi_classification_source(), self.Term._catalog(),
            )
        provider.assert_called_once()
        return result, provider.call_args.args[0]

    def _content_response(self):
        return {"description": "<p>Propuesta comercial para revisar.</p>",
                "technicalDescription": "<p>Ficha pendiente de datos técnicos confirmados.</p>"}

    def test_empty_context_has_four_axes_without_inferred_audiences(self):
        context = self.product._bpi_semantic_context()
        self.assertEqual(set(context["axes"]), {"niche", "commercial", "technical", "use"})
        self.assertFalse(self._context_ids(context))
        self.assertEqual(context["source"], "saved_approved_classification")
        self.assertEqual(context["classificationRevision"], 0)
        self.assertFalse(context["reviewedAt"])
        self.assertRegex(context["revision"], r"^[a-f0-9]{64}$")
        self.assertTrue(context["caveat"])

    def test_multiple_niches_and_canonical_aliases_share_saved_context(self):
        selected = self.clinic | self.students | self.commercial | self.technical | self.use
        self._save(selected, self.excluded)
        context = self.product._bpi_semantic_context()
        self.assertEqual(self._context_ids(context), set(selected.ids))
        self.assertEqual({row["id"] for row in context["axes"]["niche"]}, {self.clinic.id, self.students.id})
        row = context["axes"]["use"][0]
        self.assertEqual(row["name"], self.use.name)
        self.assertEqual(row["aliases"], ["modelado resina semantica"])
        self.assertEqual(row["definition"], self.use.definition)
        self.assertEqual(row["revision"], self.use.revision)
        self.assertEqual(context["classificationRevision"], self.product.bpi_classification_revision)
        self.assertTrue(context["reviewedAt"])
        self.assertNotIn(self.universal.id, self._context_ids(context))

    def test_queued_proposals_legacy_and_exclusions_never_become_saved_context(self):
        self._save(self.clinic, self.excluded)
        self.product.write({"bpi_intelligent_niches": ["estudiantes"]})
        jobs = self._jobs()
        job = jobs._create_classification_job(self.product)
        job.write({"state": "done", "result_payload": {"classificationProposal": {
            "termIds": [self.students.id, self.use.id],
            "newTerms": [{"id": self.draft.id, "name": self.draft.name}],
            "intentPhrases": [{"axis": "use", "text": "SEM_DRAFT_INTENT", "termIds": [self.use.id]}],
        }}})
        context = self.product._bpi_semantic_context()
        self.assertEqual(self._context_ids(context), {self.clinic.id})
        serialized = json.dumps(context, ensure_ascii=False)
        for forbidden in (self.draft.name, self.excluded.name, "SEM_DRAFT_INTENT", self.students.name, self.use.name):
            self.assertNotIn(forbidden, serialized)

    def test_reading_context_calls_no_provider_and_performs_no_model_writes(self):
        self._save(self.clinic | self.use)
        before = self._snapshot()
        with patch.object(type(self.Product), "write", side_effect=AssertionError("Read must not write product")), \
                patch.object(type(self.Term), "write", side_effect=AssertionError("Read must not write dictionary")), \
                patch.object(type(self.service), "_openai_json", side_effect=AssertionError("Read must not generate")):
            first = self.product._bpi_semantic_context()
            second = self.product._bpi_semantic_context()
        self.assertEqual(first, second)
        self.assertEqual(before, self._snapshot())
        self.transport.assert_not_called()

    def test_detail_and_content_template_metadata_share_semantic_revision(self):
        self._save(self.clinic | self.students | self.use)
        context = self.product._bpi_semantic_context()
        before = self._snapshot()
        payload = self.product.bpi_build_payload()
        self.assertEqual(payload["semanticContext"], context)
        self.assertEqual(payload["contentTemplates"]["semanticRevision"], context["revision"])
        self.assertEqual(payload["contentTemplates"]["effective"]["id"], self.recipe.id)
        self.assertEqual(before, self._snapshot())

    def test_context_revision_changes_when_assignment_or_linked_alias_changes(self):
        empty_revision = self.product._bpi_semantic_context()["revision"]
        self._save(self.clinic | self.use)
        saved_revision = self.product._bpi_semantic_context()["revision"]
        self.assertNotEqual(empty_revision, saved_revision)
        self.use.write({"aliases_text": self.use.aliases_text + "\nsem approved fresh alias"})
        changed_revision = self.product._bpi_semantic_context()["revision"]
        self.assertNotEqual(saved_revision, changed_revision)
        self.assertIn("sem approved fresh alias", self.product._bpi_semantic_context()["axes"]["use"][0]["aliases"])
        self._save(self.clinic, self.use)
        self.assertNotEqual(changed_revision, self.product._bpi_semantic_context()["revision"])
        self.assertNotIn(self.use.id, self._context_ids(self.product._bpi_semantic_context()))

    def test_approved_dictionary_edits_do_not_assign_product(self):
        original = self.product._bpi_semantic_context()
        self.draft.action_approve()
        self.assertFalse(self._context_ids(self.product._bpi_semantic_context()))
        self.assertEqual(self.product._bpi_semantic_context()["classificationRevision"], original["classificationRevision"])

    def test_unrelated_vocabulary_edits_do_not_invalidate_saved_semantics(self):
        self._save(self.clinic | self.use)
        before = self.product._bpi_semantic_context()
        self.excluded.write({"definition": "Edited unrelated approved term."})
        self.draft.action_approve()
        self.assertEqual(self.product._bpi_semantic_context(), before)

    def test_context_admin_and_company_boundaries(self):
        with self.assertRaises(AccessError):
            self.product.with_user(self.reader)._bpi_semantic_context()
        company = self.env["res.company"].create({"name": "BPI Semantics Other Company"})
        product = self.Product.create({"name": "SEM_PRIVATE_OTHER_COMPANY", "company_id": company.id})
        scoped = self.env(context=dict(self.env.context, allowed_company_ids=self.env.company.ids))
        with self.assertRaises(MissingError):
            product.with_env(scoped)._bpi_semantic_context()

    def test_semantic_labels_never_enter_technical_fact_ids(self):
        before = self.product._bpi_content_facts()
        self._save(self.clinic | self.students | self.commercial | self.technical | self.use)
        self.assertEqual(self.product._bpi_content_facts(), before)
        self.assertNotIn(self.use.name, json.dumps(before, ensure_ascii=False))

    def test_source_retains_original_categories_as_clues_and_marks_historical_prose(self):
        source = self.product._bpi_classification_source()
        self.assertEqual(source["internalCategory"], self.internal_category.complete_name)
        self.assertEqual(source["storeCategories"], [self.store_category.name])
        self.assertIn("SEM_OLD_TECH_NOT_EVIDENCE", " ".join(source["savedDescriptionsNotTechnicalEvidence"]))
        self.assertNotIn("SEM_OLD_TECH_NOT_EVIDENCE", json.dumps(source["facts"]))
        before = digest(source)
        self.product.name = "Espátula para composite SEM_SOURCE_REVISED"
        self.assertNotEqual(digest(self.product._bpi_classification_source()), before)

    def test_content_prompt_uses_saved_multi_niche_semantics_and_keeps_recipe(self):
        self._save(self.clinic | self.students | self.use, self.excluded)
        before = self._snapshot()
        with patch.object(type(self.service), "_openai_json", return_value=self._content_response()) as provider:
            result = self.service.generate_content(self.product, audience="clinicas")
        provider.assert_called_once()
        prompt = provider.call_args.args[0]
        for expected in (self.clinic.name, self.students.name, self.use.name, "modelado resina semantica",
                         "SEM_SHORT_MODEL", "SEM_LONG_MODEL", "DATOS CONFIRMADOS"):
            self.assertIn(expected, prompt)
        for forbidden in (self.draft.name, self.excluded.name, "SEM_OLD_AI_NOT_EVIDENCE", "SEM_OLD_TECH_NOT_EVIDENCE"):
            self.assertNotIn(forbidden, prompt)
        self.assertEqual(result["contentTemplates"]["effective"]["id"], self.recipe.id)
        self.assertEqual(before, self._snapshot())

    def test_content_rejects_semantic_assignment_changed_during_provider(self):
        self._save(self.clinic)
        before = self.product.bpi_ai_generated_description

        def changed(*args, **kwargs):
            self._save(self.clinic | self.students)
            return self._content_response()

        with patch.object(type(self.service), "_openai_json", side_effect=changed) as provider:
            with self.assertRaises(UserError):
                self.service.generate_content(self.product)
        provider.assert_called_once()
        self.assertEqual(self.product.bpi_ai_generated_description, before)

    def test_content_rejects_linked_alias_changed_during_provider(self):
        self._save(self.use)

        def changed(*args, **kwargs):
            self.use.write({"aliases_text": "sem revised approved alias"})
            return self._content_response()

        with patch.object(type(self.service), "_openai_json", side_effect=changed) as provider:
            with self.assertRaises(UserError):
                self.service.generate_content(self.product)
        provider.assert_called_once()
        self.assertIn("SEM_OLD_AI_NOT_EVIDENCE", self.product.bpi_ai_generated_description)

    def test_content_fresh_transaction_semantic_change_discards_preview(self):
        self._save(self.clinic | self.use)
        fresh = self.service.content_template_context(self.product)
        fresh["semanticRevision"] = "different-concurrently-committed-classification"
        with patch.object(type(self.service), "_content_template_fresh_context", return_value=fresh), \
                patch.object(type(self.service), "_openai_json", return_value=self._content_response()) as provider:
            with self.assertRaises(UserError):
                self.service.generate_content(self.product)
        provider.assert_called_once()

    def test_old_classification_responses_remain_valid_without_optional_explanation(self):
        before = self._snapshot()
        result, prompt = self._proposal(self._proposal_response(termIds=[self.use.id, self.clinic.id, self.use.id]))
        self.assertEqual(result["termIds"], sorted([self.use.id, self.clinic.id]))
        self.assertFalse(result.get("nicheEvaluations"))
        self.assertFalse(result.get("intentPhrases"))
        self.assertEqual(before, self._snapshot())
        self.assertIn("VOCABULARIO APROBADO", prompt)

    def test_classification_can_suggest_clinic_and_students_without_saving(self):
        before = self._snapshot()
        result, prompt = self._proposal(self._proposal_response(
            termIds=[self.clinic.id, self.students.id, self.use.id],
            nicheEvaluations=self._niche_evaluations({self.clinic.id, self.students.id}, {
                self.clinic.id: {"reason": "Instrumento de restauración clínica."},
                self.students.id: {"reason": "Uso formativo justificado por la identidad del instrumento."},
            }),
            intentPhrases=[{"axis": "use", "text": "instrumento para modelar composite", "termIds": [self.use.id]}],
        ))
        self.assertEqual(set(result["termIds"]), {self.clinic.id, self.students.id, self.use.id})
        self.assertEqual({row["termId"] for row in result["nicheEvaluations"]}, {
            row["id"] for row in self.Term._catalog() if row["axis"] == "niche" and not row["universal"]
        })
        self.assertEqual(result["intentPhrases"][0]["termIds"], [self.use.id])
        self.assertEqual(before, self._snapshot())
        self.assertIn("nicheEvaluations", prompt)
        self.assertIn("intentPhrases", prompt)

    def test_specialist_equipment_does_not_automatically_suggest_students(self):
        equipment = self.Product.create({"name": "SEM Tomógrafo profesional de instalación clínica"})
        result, unused_prompt = self._proposal(self._proposal_response(
            termIds=[self.clinic.id],
            nicheEvaluations=self._niche_evaluations({self.clinic.id}, {
                self.clinic.id: {"reason": "Equipo de instalación clínica."},
                self.students.id: {"decision": "not_suggested", "reason": "No hay uso ni compra estudiantil justificados."},
            }),
        ), product=equipment)
        self.assertNotIn(self.students.id, result["termIds"])
        self.assertEqual(next(row for row in result["nicheEvaluations"] if row["termId"] == self.students.id)["decision"], "not_suggested")
        self.assertFalse(equipment.bpi_taxonomy_term_ids)

    def test_proposal_new_words_and_intent_phrases_stay_out_of_saved_context(self):
        before_ids = self.product.bpi_taxonomy_term_ids.ids
        response = self._proposal_response(
            termIds=[self.use.id],
            newTerms=[{"axis": "use", "name": "SEM_NEW_AI_WORD", "aliases": ["sem new alias"], "definition": "Pendiente de revisión."}],
            intentPhrases=[{"axis": "use", "text": "SEM_NEW_AI_INTENT", "termIds": [self.use.id]}],
        )
        result, unused_prompt = self._proposal(response)
        term = self.Term.browse(result["newTerms"][0]["id"])
        self.assertEqual(term.state, "draft")
        self.assertEqual(self.product.bpi_taxonomy_term_ids.ids, before_ids)
        context = json.dumps(self.product._bpi_semantic_context())
        self.assertNotIn("SEM_NEW_AI_WORD", context)
        self.assertNotIn("SEM_NEW_AI_INTENT", context)

    def test_niche_evaluation_rejects_unknown_non_niche_and_inconsistent_ids(self):
        good = {"termId": self.clinic.id, "decision": "suggested", "reason": "Público confirmado."}
        invalid_rows = [
            None, [], {},
            dict(good, termId=True), dict(good, termId=999999999),
            dict(good, termId=self.universal.id), dict(good, termId=self.use.id),
            dict(good, termId=self.draft.id), dict(good, decision="not_suggested"),
            dict(good, decision="insufficient_evidence"), dict(good, decision="unknown"),
            dict(good, termId=self.students.id),
            dict(good, reason=" "), dict(good, reason="x" * 501), dict(good, reason=[]),
        ]
        before = self._snapshot()
        other_rows = [row for row in self._niche_evaluations({self.clinic.id}) if row["termId"] != self.clinic.id]
        for row in invalid_rows:
            with self.subTest(row=row), self.assertRaises(UserError):
                self._proposal(self._proposal_response(termIds=[self.clinic.id], nicheEvaluations=[row] + other_rows))
        for rows in (None, {}, "invalid", [good, good], [good] * 101):
            with self.subTest(rows=rows), self.assertRaises(UserError):
                self._proposal(self._proposal_response(termIds=[self.clinic.id], nicheEvaluations=rows))
        self.assertEqual(before, self._snapshot())

    def test_intent_phrases_reject_invalid_axes_text_and_unapproved_associations(self):
        good = {"axis": "use", "text": "modelar composite", "termIds": [self.use.id]}
        invalid_rows = [
            None, [], {}, dict(good, axis="unknown"), dict(good, axis=[]),
            dict(good, text=" "), dict(good, text="x" * 161), dict(good, text=[]),
            dict(good, termIds=[]), dict(good, termIds=True), dict(good, termIds=[True]),
            dict(good, termIds=[999999999]), dict(good, termIds=[self.draft.id]),
            dict(good, termIds=[self.excluded.id]), dict(good, termIds=[self.clinic.id]),
            dict(good, termIds=[self.use.id, self.use.id]), dict(good, termIds=[self.use.id] * 11),
        ]
        before = self._snapshot()
        for row in invalid_rows:
            with self.subTest(row=row), self.assertRaises(UserError):
                self._proposal(self._proposal_response(termIds=[self.use.id, self.clinic.id], intentPhrases=[row]))
        for rows in (None, {}, "invalid", [good] * 21):
            with self.subTest(rows=rows), self.assertRaises(UserError):
                self._proposal(self._proposal_response(termIds=[self.use.id], intentPhrases=rows))
        self.assertEqual(before, self._snapshot())

    def test_optional_semantic_text_is_trimmed_and_duplicate_intent_is_collapsed(self):
        result, unused_prompt = self._proposal(self._proposal_response(
            termIds=[self.clinic.id, self.use.id],
            nicheEvaluations=self._niche_evaluations({self.clinic.id}, {self.clinic.id: {"reason": "  Uso profesional.  "}}),
            intentPhrases=[
                {"axis": "use", "text": "  modelar   composite  ", "termIds": [self.use.id]},
                {"axis": "use", "text": "MODELAR COMPOSITE", "termIds": [self.use.id]},
            ],
        ))
        self.assertEqual(next(row for row in result["nicheEvaluations"] if row["termId"] == self.clinic.id)["reason"], "Uso profesional.")
        self.assertEqual(result["intentPhrases"], [{"axis": "use", "text": "modelar composite", "termIds": [self.use.id]}])

    def test_invalid_semantic_detail_is_rejected_before_new_dictionary_record(self):
        with self.assertRaises(UserError):
            self._proposal(self._proposal_response(
                termIds=[self.clinic.id],
                nicheEvaluations=[{"termId": self.clinic.id, "decision": "not_suggested", "reason": "Contradictorio."}],
                newTerms=[{"name": "SEM_INVALID_RESPONSE_NEW_WORD", "axis": "use"}],
            ))
        self.assertFalse(self.Term.search([("name", "=", "SEM_INVALID_RESPONSE_NEW_WORD")]))

    def test_present_niche_evaluations_require_every_nonuniversal_niche(self):
        for rows in ([], [{"termId": self.clinic.id, "decision": "suggested", "reason": "Only first niche evaluated."}]):
            with self.subTest(rows=rows), self.assertRaises(UserError):
                self._proposal(self._proposal_response(termIds=[self.clinic.id], nicheEvaluations=rows))
        empty_catalog_result = self.service._classification_semantic_details(
            {"nicheEvaluations": [], "intentPhrases": []}, [], set(),
        )
        self.assertEqual(empty_catalog_result, ([], []))

    def test_classification_prompt_evaluates_niches_without_global_student_assignment(self):
        unused_result, prompt = self._proposal(self._proposal_response())
        for expected in ("CADA nicho", "INDEPENDIENTES", "pista, NO una limitación",
                         "No deduzcas que todo producto es para estudiantes", "prácticas formativas supervisadas",
                         "Sinónimos significan lo mismo", "NO sinónimos", "NO prueban características técnicas"):
            self.assertIn(expected, prompt)
        self.assertIn(self.internal_category.name, prompt)
        self.assertIn(self.store_category.name, prompt)

    def test_classification_proposal_checks_admin_and_company_before_provider(self):
        with patch.object(type(self.service), "_openai_json") as provider:
            with self.assertRaises(AccessError):
                self.service.with_user(self.reader)._classification_proposal(self.product, {}, [])
            company = self.env["res.company"].create({"name": "SEM Proposal Other Company"})
            product = self.Product.create({"name": "SEM other product", "company_id": company.id})
            scoped = self.service.with_context(allowed_company_ids=self.env.company.ids)
            with self.assertRaises(MissingError):
                scoped._classification_proposal(product, {}, [])
        provider.assert_not_called()

    def test_seo_prompt_uses_saved_semantics_as_vocabulary_without_editorial_write(self):
        self._save(self.clinic | self.students | self.use, self.excluded)
        before = self._snapshot()
        with patch.object(type(self.service), "_openai_json", return_value={
            "seoTitle": "Propuesta SEM", "geoKeywords": ["modelar composite"],
            "aiGeneratedDescription": "NO_OVERWRITE", "aiTechnicalDescription": "NO_OVERWRITE",
            "geoFaq": [{"question": "No", "answer": "No"}],
        }) as provider:
            result = self.service.analyze_seo(self.product, "clinicas")
        provider.assert_called_once()
        prompt = provider.call_args.args[0]
        for expected in (self.clinic.name, self.students.name, self.use.name, "modelado resina semantica",
                         "CLASIFICACIÓN APROBADA GUARDADA", "NO evidencia técnica", "DATOS CONFIRMADOS"):
            self.assertIn(expected, prompt)
        for forbidden in (self.excluded.name, self.draft.name, "generá contenido basado en la categoría",
                          "Mencionar envío, garantía o soporte técnico"):
            self.assertNotIn(forbidden, prompt)
        facts_block = prompt.split("DATOS CONFIRMADOS (", 1)[1].split("REGLAS INVARIABLES:", 1)[0]
        for forbidden in (self.use.name, "SEM_OLD_AI_NOT_EVIDENCE", "SEM_OLD_TECH_NOT_EVIDENCE"):
            self.assertNotIn(forbidden, facts_block)
        self.assertEqual(result["seoTitle"], "Propuesta SEM")
        self.assertNotIn("aiGeneratedDescription", result)
        self.assertNotIn("aiTechnicalDescription", result)
        self.assertNotIn("geoFaq", result)
        self.assertEqual(before, self._snapshot())

    def test_seo_rejects_same_transaction_semantic_change_without_retry(self):
        self._save(self.clinic)

        def changed(*args, **kwargs):
            self._save(self.clinic | self.students)
            return {"seoTitle": "STALE_SEMANTIC_SEO"}

        with patch.object(type(self.service), "_openai_json", side_effect=changed) as provider:
            with self.assertRaises(UserError):
                self.service.analyze_seo(self.product, "clinicas")
        provider.assert_called_once()
        self.assertEqual(self.product.website_meta_title, "SEM_SAVED_SEO")

    def test_seo_analysis_admin_and_company_guards_precede_provider(self):
        with patch.object(type(self.service), "_openai_json") as provider:
            with self.assertRaises(AccessError):
                self.service.with_user(self.reader).analyze_seo(self.product, "general")
            company = self.env["res.company"].create({"name": "SEM SEO Other Company"})
            product = self.Product.create({"name": "SEM other SEO product", "company_id": company.id})
            scoped = self.service.with_context(allowed_company_ids=self.env.company.ids)
            with self.assertRaises(MissingError):
                scoped.analyze_seo(product, "general")
        provider.assert_not_called()

    def test_seo_job_creation_snapshots_semantics_and_never_calls_provider(self):
        self._save(self.clinic | self.students | self.use)
        jobs = self._jobs()
        before = self._snapshot()
        with patch.object(type(self.service), "_openai_json", side_effect=AssertionError("Queue does not generate")):
            job = jobs.create_seo_job(self.product)
            self.assertEqual(job, jobs.create_seo_job(self.product))
        self.assertEqual(job.semantic_request["revision"], self.product._bpi_semantic_context()["revision"])
        self.assertEqual(set(job.semantic_request["companies"]), set(self.env.companies.ids))
        self.assertEqual(before, self._snapshot())

    def test_stale_saved_semantics_fail_queued_seo_before_paid_request(self):
        self._save(self.clinic)
        job = self._jobs().create_seo_job(self.product)
        self._save(self.clinic | self.students)
        with patch.object(type(self.service), "analyze_seo", side_effect=AssertionError("Stale job cannot generate")) as provider:
            result = job._process_job()
        self._assert_semantic_job_failure(job)
        provider.assert_not_called()

    def test_concurrent_semantics_fail_queued_seo_before_paid_request(self):
        job = self._jobs().create_seo_job(self.product)
        fresh = dict(self.product._bpi_semantic_context(), revision="concurrent-change")
        with patch.object(type(self.service), "_semantic_context_fresh", return_value=fresh), \
                patch.object(type(self.service), "analyze_seo") as provider:
            job._process_job()
        self._assert_semantic_job_failure(job)
        provider.assert_not_called()

    def test_concurrent_semantics_after_seo_call_discard_result_without_replay(self):
        job = self._jobs().create_seo_job(self.product)
        original = self.product._bpi_semantic_context()
        fresh = dict(original, revision="concurrent-post-provider-change")
        with patch.object(type(self.service), "_semantic_context_fresh", side_effect=[original, fresh]), \
                patch.object(type(self.service), "analyze_seo", return_value={"seoTitle": "Discard"}) as provider:
            job._process_job()
            job._process_job()
        self._assert_semantic_job_failure(job)
        provider.assert_called_once()
        self.assertEqual(self.product.website_meta_title, "SEM_SAVED_SEO")

    def test_legacy_seo_job_without_semantic_snapshot_keeps_preview_contract(self):
        job = self._jobs().create({
            "name": "Legacy semantic fixture", "product_tmpl_id": self.product.id,
            "requested_by_id": self.env.uid, "job_type": "seo", "target_audience": "clinicas",
        })
        self.assertFalse(job.semantic_request)
        with patch.object(type(self.service), "analyze_seo", return_value={"seoTitle": "Legacy preview"}) as provider:
            result = job._process_job()
        self.assertEqual(result["state"], "done", job.error_message)
        self.assertEqual(result["resultPayload"], {"seoData": {"seoTitle": "Legacy preview"}})
        provider.assert_called_once()
        self.assertEqual(self.product.website_meta_title, "SEM_SAVED_SEO")

    def test_proposed_alias_for_saved_term_does_not_change_semantic_context(self):
        self._save(self.use)
        before = self.product._bpi_semantic_context()
        result, unused_prompt = self._proposal(self._proposal_response(
            termIds=[self.use.id],
            newTerms=[{"axis": "use", "name": self.use.name, "aliases": ["SEM_UNREVIEWED_NEW_ALIAS"]}],
        ))
        self.assertEqual(result["newTerms"][0]["id"], self.use.id)
        self.assertEqual(self.product._bpi_semantic_context(), before)
        self.assertNotIn("SEM_UNREVIEWED_NEW_ALIAS", self.use.aliases_text)

    def test_new_term_validation_precedes_all_creates_and_checks_existing_aliases(self):
        valid = {"axis": "use", "name": "SEM_VALID_BUT_ATOMIC_NEW_WORD"}
        for invalid in (dict(valid, name=" "), dict(valid, name="x" * 101),
                        dict(valid, definition="x" * 1501), dict(valid, aliases=["x"] * 21),
                        dict(valid, aliases=["x" * 101]), dict(valid, axis=[]),
                        {"axis": "use", "name": self.use.name, "aliases": ["x" * 101]}):
            with self.subTest(invalid=invalid), self.assertRaises(UserError):
                self._proposal(self._proposal_response(newTerms=[valid, invalid]))
        self.assertFalse(self.Term.search([("name", "=", valid["name"])]))

    def test_faq_prompt_uses_saved_multi_niche_vocabulary_without_writes(self):
        self._save(self.clinic | self.students | self.use, self.excluded)
        before = self._snapshot()
        faqs = [{"question": "¿Para qué sirve la espátula?", "answer": "Consulta su finalidad y los datos confirmados."}]
        with patch.object(type(self.service), "_openai_json", return_value={"faqs": faqs}) as provider:
            result = self.service.generate_faq(self.product, audience="clinicas")
        provider.assert_called_once()
        self.assertEqual(result["faqs"], faqs)
        self.assertEqual(result["semanticRevision"], self.product._bpi_semantic_context()["revision"])
        prompt = provider.call_args.args[0]
        for expected in (self.clinic.name, self.students.name, self.use.name, "CLASIFICACIÓN APROBADA GUARDADA",
                         "NO evidencia técnica", "DATOS CONFIRMADOS", "No inventes procedimientos paso a paso"):
            self.assertIn(expected, prompt)
        self.assertNotIn(self.excluded.name, prompt)
        self.assertNotIn(self.draft.name, prompt)
        self.assertEqual(before, self._snapshot())

    def test_faq_discards_semantic_change_during_provider_without_retry(self):
        self._save(self.clinic)

        def changed(*args, **kwargs):
            self._save(self.clinic | self.students)
            return {"faqs": [{"question": "Discard", "answer": "Discard"}]}

        with patch.object(type(self.service), "_openai_json", side_effect=changed) as provider:
            with self.assertRaises(UserError):
                self.service.generate_faq(self.product)
        provider.assert_called_once()
        self.assertEqual(self.product.bpi_faq_ids.mapped("question"), ["¿SEM saved FAQ?"])

    def test_faq_fresh_transaction_change_discards_result_without_write(self):
        self._save(self.clinic | self.use)
        fresh = dict(self.product._bpi_semantic_context(), revision="concurrent-faq-classification-change")
        before = self._snapshot()
        with patch.object(type(self.service), "_semantic_context_fresh", return_value=fresh), \
                patch.object(type(self.service), "_openai_json", return_value={
                    "faqs": [{"question": "Discard", "answer": "Discard"}],
                }) as provider:
            with self.assertRaises(UserError):
                self.service.generate_faq(self.product)
        provider.assert_called_once()
        self.assertEqual(before, self._snapshot())

    def test_seo_job_requester_losing_admin_access_cannot_generate(self):
        requester = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "SEM revoked administrator", "login": "sem_revoked_admin",
            "groups_id": [(6, 0, self.env.ref("base.group_system").ids)],
        })
        job = self.env["bpi.ai.job"].with_user(requester).with_context(bpi_no_job_commit=True).create_seo_job(
            self.product.with_user(requester),
        )
        requester.write({"groups_id": [(6, 0, self.env.ref("base.group_user").ids)]})
        job = job.with_env(self.env).with_context(bpi_no_job_commit=True)
        with patch.object(type(self.service), "analyze_seo") as provider:
            job._process_job()
        self.assertEqual(job.state, "failed")
        provider.assert_not_called()
