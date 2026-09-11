# -*- coding: utf-8 -*-
"""Optional marketplace contracts. The base addon never imports an integrator."""

from odoo import _, api, fields, models
from odoo.exceptions import MissingError, UserError


class BPIMeliProvider(models.AbstractModel):
    _inherit = "bpi.service"

    _MELI_FILTERS = ("linked", "published", "stock", "prices", "conditions", "review", "unlinked")

    @api.model
    def _meli_filter_key(self, value):
        if value is False or value is None or value == "" or value == "all":
            return ""
        if not isinstance(value, str) or value not in self._MELI_FILTERS:
            raise UserError(_("Selecciona un filtro de Mercado Libre válido."))
        return value

    @api.model
    def _meli_account_key(self, value):
        if value is False or value is None or value == "":
            return False
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise UserError(_("Selecciona una cuenta de Mercado Libre válida."))
        if isinstance(value, str) and not value.isdigit():
            raise UserError(_("Selecciona una cuenta de Mercado Libre válida."))
        if int(value) <= 0:
            raise UserError(_("Selecciona una cuenta de Mercado Libre válida."))
        return int(value)

    @api.model
    def _meli_summary_default(self, state="unavailable", reason=None):
        return {
            "state": state, "label": _("ML no disponible"),
            "reason": reason or _("La extensión de Mercado Libre no está instalada."),
            "linked": False, "published": False, "stockVerified": False,
            "pricesVerified": False, "conditionsComplete": False, "needsReview": False,
            "itemCount": 0, "variantCount": 0, "activeItemCount": 0,
            "stockState": "unknown", "priceState": "unknown", "conditionState": "unknown",
            "source": "unavailable", "observedAt": False,
        }

    @api.model
    def _meli_unavailable(self, state="not_installed", message=None):
        return {
            "available": False, "state": state,
            "message": message or _("La extensión de Mercado Libre no está instalada."),
            "canRefresh": False, "accounts": [], "accountId": False,
            "generatedAt": self._dashboard_datetime(fields.Datetime.now()), "observedAt": False,
        }

    @api.model
    def _meli_projection(self, products, account_id=False):
        self._ensure_manager()
        self._meli_account_key(account_id)
        products.check_access_rights("read")
        products.check_access_rule("read")
        return {
            **self._meli_unavailable(),
            "sets": {key: set() for key in self._MELI_FILTERS},
            "rows": {product_id: self._meli_summary_default() for product_id in products.ids},
        }

    @api.model
    def _meli_public_context(self, projection):
        return {key: projection.get(key) for key in (
            "available", "state", "message", "canRefresh", "accounts", "accountId",
            "generatedAt", "observedAt",
        )}

    @api.model
    def _meli_overview_payload(self, projection, total):
        payload = {**self._meli_public_context(projection), "total": total, "kpis": []}
        if not projection.get("available"):
            return payload
        specs = (
            ("linked", _("Vinculados"), _("Con al menos un vínculo local válido; no garantiza sincronización.")),
            ("published", _("Publicados en ML"), _("Al menos una publicación conocida como activa; consulta su origen y fecha.")),
            ("stock", _("Stock verificado"), _("Todos los destinos gestionados con evidencia individual vigente de hasta 60 minutos.")),
            ("prices", _("Precios verificados"), _("Precios gestionados confirmados para la generación actual y tarifa correspondiente.")),
            ("conditions", _("Tres condiciones completas"), _("Pago único, 3 y 6 cuotas sin ambigüedad en cada grupo gestionado.")),
            ("review", _("Requieren revisión"), _("Divergencias, bloqueos, información incompleta o confirmación insuficiente.")),
        )
        for key, label, description in specs:
            count = len(projection.get("sets", {}).get(key, set()))
            payload["kpis"].append({
                "key": key, "filter": key, "label": label, "description": description,
                "count": count, "percent": round(count * 100.0 / total, 1) if total else 0.0,
            })
        return payload

    @api.model
    def _meli_product(self, product_tmpl_id):
        self._ensure_manager()
        product_id = self._meli_account_key(product_tmpl_id)
        if not product_id:
            raise MissingError(_("Producto no encontrado."))
        products = self.env["product.template"].with_context(active_test=False).search([
            ("id", "=", product_id), "|", ("company_id", "=", False),
            ("company_id", "in", self.env.companies.ids),
        ], limit=1)
        if not products:
            raise MissingError(_("Producto no encontrado o no disponible en las empresas seleccionadas."))
        return products

    @api.model
    def meli_detail(self, product_tmpl_id, account_id=False):
        product = self._meli_product(product_tmpl_id)
        self._meli_account_key(account_id)
        return {
            **self._meli_unavailable(), "productId": product.id,
            "summary": self._meli_summary_default(), "groups": [], "jobs": [],
        }

    @api.model
    def meli_request_refresh(self, product_tmpl_id, account_id=False):
        self._meli_product(product_tmpl_id)
        self._meli_account_key(account_id)
        return {"success": False, "state": "disabled", "job": False,
                "message": self._meli_unavailable()["message"]}

    @api.model
    def meli_refresh_status(self, job_id):
        self._ensure_manager()
        self._meli_account_key(job_id)
        return {"success": False, "state": "disabled", "job": False,
                "message": self._meli_unavailable()["message"]}
