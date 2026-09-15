# -*- coding: utf-8 -*-
"""Private dated import receipt. Approved prose is not technical evidence."""
import hashlib
import json

from odoo import fields, models


class EditorialImportProduct(models.Model):
    _inherit = "product.template"

    bpi_editorial_import = fields.Json(
        string="Origen de la importación editorial", groups="base.group_system",
        readonly=True, copy=False,
        help="Registro de origen y divergencias al importar; no modifica las medidas guardadas.",
    )

    def _bpi_editorial_content_hash(self):
        self.ensure_one()
        return hashlib.sha256(json.dumps([
            self.bpi_ai_generated_description or "", self.bpi_technical_description or "",
        ], ensure_ascii=False).encode()).hexdigest()

    def bpi_build_payload(self):
        result = super().bpi_build_payload()
        self.env["bpi.service"]._meli_product(self.id)
        receipt = self.bpi_editorial_import or {}
        result["product"]["editorialImport"] = {
            "date": receipt.get("date", ""), "sku": receipt.get("sku", ""),
            "differences": receipt.get("differences", []),
            "changedSinceImport": bool(receipt) and receipt.get("contentHash") != self._bpi_editorial_content_hash(),
        } if receipt else False
        return result
