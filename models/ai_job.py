# -*- coding: utf-8 -*-

import logging
from datetime import timedelta

from psycopg2 import IntegrityError
from psycopg2.errors import InFailedSqlTransaction

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class BPIAIJob(models.Model):
    _name = "bpi.ai.job"
    _description = "Producto Intelligence AI Job"
    _order = "id desc"
    _PROCESS_LOCK_NAMESPACE = 4345929
    _STALE_AFTER_MINUTES = 30

    def init(self):
        # A search alone cannot deduplicate concurrent HTTP transactions.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS bpi_ai_job_unique_active
            ON bpi_ai_job (product_tmpl_id, job_type, target_audience)
            WHERE state IN ('pending', 'running')
        """)

    name = fields.Char(required=True, default=lambda self: _("Trabajo IA"))
    job_type = fields.Selection(
        [
            ("seo", "SEO/GEO"),
        ],
        required=True,
        default="seo",
        index=True,
    )
    product_tmpl_id = fields.Many2one("product.template", required=True, ondelete="cascade", index=True)
    requested_by_id = fields.Many2one("res.users", string="Solicitado por", ondelete="set null")
    target_audience = fields.Char(default="clinicas")
    state = fields.Selection(
        [
            ("pending", "Pendiente"),
            ("running", "Procesando"),
            ("done", "Completado"),
            ("failed", "Fallido"),
        ],
        default="pending",
        required=True,
        index=True,
    )
    progress = fields.Integer(default=0)
    message = fields.Char(default="En cola")
    result_payload = fields.Json(default=dict)
    error_message = fields.Text()
    started_at = fields.Datetime()
    finished_at = fields.Datetime()

    def _commit_for_visibility(self):
        if not self.env.context.get("bpi_no_job_commit"):
            self.env.cr.commit()

    def bpi_to_payload(self):
        self.ensure_one()
        return {
            "id": self.id,
            "name": self.name,
            "jobType": self.job_type,
            "productId": self.product_tmpl_id.id,
            "state": self.state,
            "progress": self.progress or 0,
            "message": self.message or "",
            "errorMessage": self.error_message or "",
            "resultPayload": self.result_payload or {},
            "startedAt": self.started_at.isoformat() if self.started_at else False,
            "finishedAt": self.finished_at.isoformat() if self.finished_at else False,
        }

    @api.model
    def create_seo_job(self, product, target_audience="clinicas", user=False):
        product.ensure_one()
        target_audience = target_audience or "clinicas"
        if target_audience not in ("clinicas", "laboratorios", "estudiantes", "general"):
            raise UserError(_("Selecciona una audiencia válida."))
        domain = [
                ("product_tmpl_id", "=", product.id),
                ("job_type", "=", "seo"),
                ("target_audience", "=", target_audience),
                ("state", "in", ["pending", "running"]),
            ]
        active_job = self.search(
            domain,
            order="id desc",
            limit=1,
        )
        if active_job:
            return active_job
        values = {
                "name": _("SEO/GEO Nancy AI - %s") % (product.display_name or product.name),
                "job_type": "seo",
                "product_tmpl_id": product.id,
                "requested_by_id": user.id if user else self.env.user.id,
                "target_audience": target_audience,
                "state": "pending",
                "progress": 0,
                "message": _("En cola para Nancy AI"),
            }
        try:
            with self.env.cr.savepoint():
                return self.create(values)
        except IntegrityError as error:
            if getattr(error.diag, "constraint_name", None) != "bpi_ai_job_unique_active":
                raise
            active_job = self.search(domain, order="id desc", limit=1)
            if active_job:
                return active_job
            # REPEATABLE READ may not see the concurrent winner yet. Ask Odoo's
            # RPC transaction retry to get a fresh snapshot; no API was called.
            # A Python-constructed SerializationFailure has no pgcode. Odoo's
            # retry dispatcher requires a real SQLSTATE 40001 from PostgreSQL.
            self.env.cr.execute("""
                DO $$ BEGIN
                    RAISE EXCEPTION 'Concurrent BPI job creation; retry transaction'
                    USING ERRCODE = '40001';
                END $$
            """)

    def _try_processing_lock(self):
        self.ensure_one()
        # Session advisory lock survives visibility commits, but is released
        # automatically when the worker's database connection dies.
        self.env.cr.execute("SELECT pg_try_advisory_lock(%s, %s)", (self._PROCESS_LOCK_NAMESPACE, self.id))
        return self.env.cr.fetchone()[0]

    def _release_processing_lock(self):
        try:
            self.env.cr.execute("SELECT pg_advisory_unlock(%s, %s)", (self._PROCESS_LOCK_NAMESPACE, self.id))
        except InFailedSqlTransaction:
            if self.env.context.get("bpi_no_job_commit"):
                raise
            # Never return a still-locked connection to Odoo's pool after an
            # unexpected SQL failure outside the normal processing boundary.
            self.env.cr.rollback()
            self.env.invalidate_all(flush=False)
            self.env.cr.execute("SELECT pg_advisory_unlock(%s, %s)", (self._PROCESS_LOCK_NAMESPACE, self.id))

    def _finish_job(self, result_payload):
        self.write({
            "state": "done", "progress": 100,
            "message": _("Propuesta SEO lista. Revisa y guarda los cambios."),
            "result_payload": result_payload,
            "finished_at": fields.Datetime.now(), "error_message": False,
        })

    def _record_failure(self, message):
        """Persist terminal failure without replaying a possibly paid request."""
        no_commit = self.env.context.get("bpi_no_job_commit")
        for attempt in range(1 if no_commit else 3):
            if not no_commit:
                self.env.cr.rollback()
                self.env.invalidate_all(flush=False)
            try:
                if not self.exists() or self.state == "done":
                    return
                self.write({
                    "state": "failed", "progress": 100,
                    "message": _("No se pudo completar el trabajo IA"),
                    "error_message": message, "result_payload": {},
                    "finished_at": fields.Datetime.now(),
                })
                self._commit_for_visibility()
                return
            except Exception:
                if no_commit:
                    raise
                _logger.warning("BPI job failure persistence job_id=%s attempt=%s code=finalization_error", self.id, attempt + 1)
        # If DB finalization is temporarily unavailable, the next cron recovers
        # the expired running job. Ensure this cursor is usable for lock release.
        self.env.cr.rollback()
        self.env.invalidate_all(flush=False)

    @api.model
    def _recover_stale_jobs(self):
        cutoff = fields.Datetime.now() - timedelta(minutes=self._STALE_AFTER_MINUTES)
        jobs = self.search([
            ("state", "=", "running"), "|",
            ("started_at", "<", cutoff),
            "&", ("started_at", "=", False), ("write_date", "<", cutoff),
        ], order="id", limit=100)
        for job in jobs:
            if not job._try_processing_lock():
                continue  # A slow but live worker must not be failed/replayed.
            try:
                with self.env.cr.savepoint():
                    job.invalidate_recordset()
                    interrupted = job.state == "running"
                if interrupted:
                    job._record_failure(_("El trabajo fue interrumpido. No se ha repetido la solicitud de IA; revisa antes de iniciar otro análisis."))
            finally:
                job._release_processing_lock()
        return True

    @api.model
    def _cron_process_pending_jobs(self, limit=1):
        self._recover_stale_jobs()
        jobs = self.search([("state", "=", "pending")], order="id asc", limit=max(1, int(limit or 1)))
        for job in jobs:
            try:
                job._process_job()
            except Exception:
                if not self.env.context.get("bpi_no_job_commit"):
                    self.env.cr.rollback()
                    self.env.invalidate_all(flush=False)
                _logger.error(
                    "BPI AI job failed operation=process job_id=%s job_type=%s code=processing_error",
                    job.id,
                    job.job_type,
                )
        return True

    def _process_job(self):
        self.ensure_one()
        if not self._try_processing_lock():
            return self.bpi_to_payload()
        try:
            with self.env.cr.savepoint():
                self.invalidate_recordset()
                pending = self.state == "pending"
            if not pending:
                return self.bpi_to_payload()  # Never automatically replay running.
            try:
                self.write({
                    "state": "running", "progress": 10,
                    "message": _("Nancy AI está preparando una propuesta SEO..."),
                    "started_at": fields.Datetime.now(), "error_message": False,
                })
                self._commit_for_visibility()
                # Include finalization in the failure boundary. A savepoint also
                # keeps TransactionCase/no-commit callers usable after SQL errors.
                with self.env.cr.savepoint():
                    if self.job_type != "seo":
                        raise ValueError("Unsupported BPI AI job type")
                    result_payload = self._process_seo_job()
                    self._finish_job(result_payload)
                self._commit_for_visibility()
            except Exception as error:
                safe_error = str(error) if isinstance(error, UserError) else _("Error interno al procesar el trabajo IA. No se ha repetido la solicitud; revisa antes de reintentar.")
                self._record_failure(safe_error)
                _logger.warning("BPI AI job failed job_id=%s code=processing_or_finalization_error", self.id)
        finally:
            self._release_processing_lock()
        return self.bpi_to_payload()

    def _process_seo_job(self):
        self.ensure_one()
        product = self.product_tmpl_id.sudo().exists()
        if not product:
            raise ValueError("Producto no encontrado")
        seo_data = self.env["bpi.service"].sudo().analyze_seo(product, self.target_audience or "clinicas")
        return {
            "seoData": seo_data,
        }
