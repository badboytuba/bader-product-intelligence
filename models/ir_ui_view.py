# -*- coding: utf-8 -*-

from odoo import _, api, models
from odoo.exceptions import AccessError


class IrUiView(models.Model):
    _inherit = "ir.ui.view"

    _BPI_PRODUCT_TEMPLATE_KEY = "website_sale.product"
    _BPI_BRIDGE_XMLID_PREFIX = "bpi_website_product_description_bridge_view_"
    _BPI_BRIDGE_NAME_PREFIX = "bader.product.intelligence.website.formatted.description."

    @api.model
    def bpi_sync_product_description_bridges(self):
        """Attach the formatted-description, technical-content and FAQ bridge to template clones.

        Website customizations may create a website-specific *primary* copy of
        ``website_sale.product`` without an XML ID. In that case, extensions of
        the global template are not part of the selected template's combined
        architecture. Keep one module-owned extension for every active clone.
        """
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Solo los administradores pueden sincronizar las vistas de Producto Intelligence."))
        View = self.sudo().with_context(active_test=False)
        ModelData = self.env["ir.model.data"].sudo()
        source_bridge = self.env.ref(
            "bader_product_intelligence.bpi_product_detail_extensions",
            raise_if_not_found=False,
        )
        if not source_bridge:
            return True

        targets = View.search(
            [
                ("key", "=", self._BPI_PRODUCT_TEMPLATE_KEY),
                ("mode", "=", "primary"),
                ("website_id", "!=", False),
                ("active", "=", True),
            ],
            order="id",
        )
        active_xmlid_names = set()
        for target in targets:
            xmlid_name = "%s%s" % (self._BPI_BRIDGE_XMLID_PREFIX, target.id)
            active_xmlid_names.add(xmlid_name)
            model_data = ModelData.search(
                [
                    ("module", "=", "bader_product_intelligence"),
                    ("name", "=", xmlid_name),
                    ("model", "=", "ir.ui.view"),
                ],
                limit=1,
            )
            bridge = View.browse(model_data.res_id).exists() if model_data else View.browse()
            if not bridge:
                bridge = View.search(
                    [
                        ("inherit_id", "=", target.id),
                        ("name", "=", "%s%s" % (self._BPI_BRIDGE_NAME_PREFIX, target.id)),
                    ],
                    limit=1,
                )

            values = {
                "name": "%s%s" % (self._BPI_BRIDGE_NAME_PREFIX, target.id),
                "type": "qweb",
                "inherit_id": target.id,
                "mode": "extension",
                "priority": source_bridge.priority,
                "active": True,
                "website_id": target.website_id.id,
                "arch_db": source_bridge.arch_db,
            }
            if bridge:
                bridge.write(values)
            else:
                bridge = View.create(values)

            if model_data:
                if model_data.res_id != bridge.id:
                    model_data.write({"res_id": bridge.id})
            else:
                ModelData.create(
                    {
                        "module": "bader_product_intelligence",
                        "name": xmlid_name,
                        "model": "ir.ui.view",
                        "res_id": bridge.id,
                        "noupdate": True,
                    }
                )

        managed_records = ModelData.search(
            [
                ("module", "=", "bader_product_intelligence"),
                ("name", "like", "%s%%" % self._BPI_BRIDGE_XMLID_PREFIX),
                ("model", "=", "ir.ui.view"),
            ]
        )
        for model_data in managed_records.filtered(
            lambda record: record.name not in active_xmlid_names
        ):
            stale_bridge = View.browse(model_data.res_id).exists()
            model_data.unlink()
            stale_bridge.unlink()

        self.clear_caches()
        return True
