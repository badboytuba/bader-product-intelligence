# -*- coding: utf-8 -*-

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class BPIAIJob(models.Model):
    _name = "bpi.ai.job"
    _description = "Producto Intelligence AI Job"
    _order = "id desc"

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
        active_job = self.search(
            [
                ("product_tmpl_id", "=", product.id),
                ("job_type", "=", "seo"),
                ("target_audience", "=", target_audience),
                ("state", "in", ["pending", "running"]),
            ],
            order="id desc",
            limit=1,
        )
        if active_job:
            return active_job
        return self.create(
            {
                "name": _("SEO/GEO Nancy AI - %s") % (product.display_name or product.name),
                "job_type": "seo",
                "product_tmpl_id": product.id,
                "requested_by_id": user.id if user else self.env.user.id,
                "target_audience": target_audience,
                "state": "pending",
                "progress": 0,
                "message": _("En cola para Nancy AI"),
            }
        )

    @api.model
    def _cron_process_pending_jobs(self, limit=1):
        jobs = self.search([("state", "=", "pending")], order="id asc", limit=max(1, int(limit or 1)))
        for job in jobs:
            try:
                job._process_job()
            except Exception:
                _logger.exception("BPI AI job %s failed", job.id)
        return True

    def _process_job(self):
        self.ensure_one()
        if self.state not in ("pending", "running"):
            return self.bpi_to_payload()

        self.write(
            {
                "state": "running",
                "progress": 10,
                "message": _("Nancy AI está generando contenido..."),
                "started_at": self.started_at or fields.Datetime.now(),
                "error_message": False,
            }
        )
        self._commit_for_visibility()

        try:
            if self.job_type == "seo":
                result_payload = self._process_seo_job()
            else:
                raise ValueError("Unsupported BPI AI job type: %s" % self.job_type)
        except Exception as error:
            self.write(
                {
                    "state": "failed",
                    "progress": 100,
                    "message": _("No se pudo completar el trabajo IA"),
                    "error_message": str(error),
                    "finished_at": fields.Datetime.now(),
                }
            )
            self._commit_for_visibility()
            raise

        self.write(
            {
                "state": "done",
                "progress": 100,
                "message": _("Contenido listo"),
                "result_payload": result_payload,
                "finished_at": fields.Datetime.now(),
                "error_message": False,
            }
        )
        self._commit_for_visibility()
        return self.bpi_to_payload()

    def _process_seo_job(self):
        self.ensure_one()
        product = self.product_tmpl_id.sudo().exists()
        if not product:
            raise ValueError("Producto no encontrado")
        seo_data = self.env["bpi.service"].sudo().analyze_seo(product, self.target_audience or "clinicas")
        return {
            "seoData": seo_data,
            "detailPayload": product.bpi_build_payload(),
        }
