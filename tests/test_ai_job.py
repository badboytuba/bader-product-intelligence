from datetime import timedelta
from unittest.mock import patch

from psycopg2 import IntegrityError
from psycopg2.errors import SerializationFailure

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("-at_install", "post_install")
class TestBPIAIJob(TransactionCase):
    def setUp(self):
        super().setUp()
        self.jobs = self.env["bpi.ai.job"].with_context(bpi_no_job_commit=True)
        self.product = self.env["product.template"].create({"name": "BPI job regression", "bpi_ai_generated_description": "<p>Manual commercial text</p>"})

    def test_active_jobs_are_deduplicated_and_constraint_guarded(self):
        job = self.jobs.create_seo_job(self.product)
        self.assertEqual(self.jobs.create_seo_job(self.product), job)
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError), self.env.cr.savepoint():
            self.jobs.create({"product_tmpl_id": self.product.id, "target_audience": "clinicas"})
        self.assertNotEqual(self.jobs.create_seo_job(self.product, "general"), job)
        job.write({"state": "done"})
        self.assertNotEqual(self.jobs.create_seo_job(self.product), job)

    def test_job_completes_as_preview_without_editorial_write(self):
        job = self.jobs.create_seo_job(self.product)
        preview = {"seoTitle": "Suggested title", "seoKeywords": ["dental"]}
        with patch.object(type(self.env["bpi.service"]), "analyze_seo", return_value=preview) as provider:
            result = job._process_job()
            self.assertEqual(result["state"], "done")
            self.assertEqual(result["resultPayload"], {"seoData": preview})
            job._process_job()
            provider.assert_called_once()
        self.assertIn("Manual commercial text", self.product.bpi_ai_generated_description)

    def test_invisible_duplicate_winner_requests_real_sqlstate_retry(self):
        self.jobs.create_seo_job(self.product)
        # Simulate the older transaction not seeing the winner, while the real
        # unique index still observes it. The dispatcher requires SQLSTATE, not
        # merely a Python-constructed exception of the matching class.
        with mute_logger("odoo.sql_db"), patch.object(type(self.jobs), "search", return_value=self.jobs.browse()):
            with self.assertRaises(SerializationFailure) as caught, self.env.cr.savepoint():
                self.jobs.create_seo_job(self.product)
        self.assertEqual(caught.exception.pgcode, "40001")

    def test_provider_failure_becomes_terminal_without_replay(self):
        job = self.jobs.create_seo_job(self.product)
        with patch.object(type(job), "_process_seo_job", side_effect=UserError("Test provider unavailable")) as provider:
            self.assertEqual(job._process_job()["state"], "failed")
            job._process_job()
            provider.assert_called_once()
        self.assertEqual(job.error_message, "Test provider unavailable")

    def test_finalization_failure_is_caught_and_secret_not_exposed(self):
        job = self.jobs.create_seo_job(self.product)
        with patch.object(type(job), "_process_seo_job", return_value={"seoData": {}}) as provider, patch.object(type(job), "_finish_job", side_effect=RuntimeError("private-provider-data")):
            result = job._process_job()
        self.assertEqual(result["state"], "failed")
        self.assertNotIn("private-provider-data", result["errorMessage"])
        provider.assert_called_once()

    def test_sql_failure_during_finalization_recovers_transaction(self):
        job = self.jobs.create_seo_job(self.product)

        def broken_finish(record, result):
            record.env.cr.execute("SELECT 1 / 0")

        with mute_logger("odoo.sql_db"), patch.object(type(job), "_process_seo_job", return_value={"seoData": {}}), patch.object(type(job), "_finish_job", broken_finish):
            self.assertEqual(job._process_job()["state"], "failed")
        self.env.cr.execute("SELECT 1")
        self.assertEqual(self.env.cr.fetchone()[0], 1)

    def test_stale_job_fails_without_repeating_provider(self):
        job = self.jobs.create_seo_job(self.product)
        job.write({"state": "running", "started_at": fields.Datetime.now() - timedelta(hours=2)})
        with patch.object(type(job), "_process_seo_job") as provider:
            job._process_job()  # Running jobs are never replayed even if called directly.
            self.jobs._recover_stale_jobs()
            provider.assert_not_called()
        self.assertEqual(job.state, "failed")
        self.assertIn("interrumpido", job.error_message)

    def test_processing_lock_excludes_other_database_connection(self):
        job = self.jobs.create_seo_job(self.product)
        with self.env.registry.cursor() as other_cr:
            other_cr.execute("SELECT pg_advisory_lock(%s, %s)", (job._PROCESS_LOCK_NAMESPACE, job.id))
            try:
                with patch.object(type(job), "_process_seo_job") as provider:
                    self.assertEqual(job._process_job()["state"], "pending")
                    provider.assert_not_called()
                job.write({"state": "running", "started_at": fields.Datetime.now() - timedelta(hours=2)})
                self.jobs._recover_stale_jobs()
                self.assertEqual(job.state, "running")
            finally:
                other_cr.execute("SELECT pg_advisory_unlock(%s, %s)", (job._PROCESS_LOCK_NAMESPACE, job.id))
        self.jobs._recover_stale_jobs()
        self.assertEqual(job.state, "failed")
