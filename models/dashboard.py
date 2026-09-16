# -*- coding: utf-8 -*-
"""Read-only, ACL-aware catalog coverage and its exact drill-down predicates."""

import math

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression


class BPIDashboardService(models.AbstractModel):
    _inherit = "bpi.service"

    _DASHBOARD_FILTERS = frozenset((
        "all", "published", "unpublished", "content", "image", "seo", "geo",
        "faq", "competitor", "category", "published_missing_image",
        "published_missing_content", "missing_seo", "missing_geo", "missing_category",
        "needs_attention", "complete",
    ))
    _CATALOG_CHECKLIST = ("commercial", "technical", "image", "seo", "geo", "faq", "category")
    _CATALOG_SORT_ORDERS = {
        "catalog": "website_sequence asc, name asc, id desc",
        "recent": "write_date desc, id desc",
        "name_asc": "name asc, id asc",
        "name_desc": "name desc, id desc",
        # This is the stored base USD price, not an effective Pack/variant range.
        "price_asc": "list_price asc, name asc, id asc",
        "price_desc": "list_price desc, name asc, id asc",
    }
    _DASHBOARD_CONTENT_FIELDS = (
        # Preload publication dependencies too: its computed getter must not
        # fetch is_published/website_id separately for every template.
        "is_published", "website_id", "website_published", "bpi_featured", "bpi_ai_generated_description",
        "description_sale", "website_description", "description", "bpi_technical_description",
        "website_meta_title", "website_meta_description", "bpi_geo_title",
        "bpi_geo_description", "public_categ_ids", "active", "sale_ok", "write_date",
    )

    @api.model
    def _dashboard_category(self, category_id):
        if category_id is False or category_id is None or category_id == "":
            return self.env["product.public.category"]
        if isinstance(category_id, bool) or not isinstance(category_id, (int, str)):
            raise UserError(_("Selecciona una categoría válida."))
        if isinstance(category_id, str) and not category_id.isdigit():
            raise UserError(_("Selecciona una categoría válida."))
        category_id = int(category_id)
        if category_id <= 0:
            raise UserError(_("Selecciona una categoría válida."))
        # search, not browse.exists: record rules must hide inaccessible categories.
        category = self.env["product.public.category"].search([("id", "=", category_id)], limit=1)
        if not category:
            raise UserError(_("La categoría no existe o no está disponible."))
        return category

    @api.model
    def _dashboard_category_domain(self, category):
        return [("public_categ_ids", "child_of", category.id)] if category else []

    @api.model
    def _dashboard_quality_filter(self, quality_filter):
        if quality_filter is False or quality_filter is None or quality_filter == "":
            return "all"
        if not isinstance(quality_filter, str) or quality_filter not in self._DASHBOARD_FILTERS:
            raise UserError(_("Selecciona un filtro de calidad válido."))
        return quality_filter

    @api.model
    def _dashboard_sort_key(self, sort_key):
        if sort_key is False or sort_key is None or sort_key == "":
            return "catalog"
        if not isinstance(sort_key, str) or sort_key not in self._CATALOG_SORT_ORDERS:
            raise UserError(_("Selecciona un orden válido para el catálogo."))
        return sort_key

    @api.model
    def _dashboard_image_record_ids(self, records, field_name):
        """Return image presence without ever reading a Binary field.

        In this Odoo 16 runtime, Binary.compute_value strips bin_size before
        computing attachment.datas. A seemingly size-only read therefore loads
        the entire filestore on a cold cache. Query stored attachment metadata
        instead; parent records AND attachment searches retain normal ACL/rules.
        """
        if not records:
            return set()
        records.check_field_access_rights("read", [field_name])
        field = records._fields[field_name]
        if field.attachment:
            attachments = records.env["ir.attachment"].with_context(prefetch_fields=False).search([
                ("res_model", "=", records._name), ("res_field", "=", field_name),
                ("res_id", "in", records.ids), ("file_size", ">", 0),
            ])
            return {row["res_id"] for row in attachments.read(["res_id"], load=False)}
        # Stored non-attachment binary fields can be filtered in SQL without
        # selecting the bytes. Also preserves the normal search of related fields.
        return set(records.search([("id", "in", records.ids), (field_name, "!=", False)]).ids)

    @api.model
    def _dashboard_coverage_sets(self, products):
        """One predicate implementation for totals and drill-down, never row payloads.

        Read only required scalar/text fields, never Binary values (even bin_size
        can materialize raw attachments on this Odoo 16 runtime).
        Related models are searched/read in batches and retain their own ACL/rules.
        """
        result = {key: set() for key in self._DASHBOARD_FILTERS}
        result["all"] = set(products.ids)
        result["commercial"] = set()
        result["technical"] = set()
        result["featured"] = set()
        result["row_metadata"] = {}
        if not products:
            return result
        product_model = products.with_context(prefetch_fields=False)
        plain = self.env["product.template"]._bpi_plain_text
        for row in product_model.read(list(self._DASHBOARD_CONTENT_FIELDS), load=False):
            product_id = row["id"]
            result["row_metadata"][product_id] = {
                "isActive": bool(row["active"]), "saleOk": bool(row["sale_ok"]),
                "updatedAt": self._dashboard_datetime(row["write_date"]),
            }
            if row["website_published"]:
                result["published"].add(product_id)
            if row["bpi_featured"]:
                result["featured"].add(product_id)
            # Same fallback order/normalizer as _bpi_description_payload.
            if any(plain(row[field]) for field in (
                "bpi_ai_generated_description", "description_sale", "website_description", "description",
            )):
                result["commercial"].add(product_id)
            if plain(row["bpi_technical_description"]):
                result["technical"].add(product_id)
            for key, title, description in (
                ("seo", "website_meta_title", "website_meta_description"),
                ("geo", "bpi_geo_title", "bpi_geo_description"),
            ):
                if plain(row[title]) and plain(row[description]):
                    result[key].add(product_id)
            if row["public_categ_ids"]:
                result["category"].add(product_id)
        result["image"].update(self._dashboard_image_record_ids(product_model, "image_1920"))

        relation_domain = [("product_tmpl_id", "in", products.ids)]
        # _bpi_native_gallery_payload includes template extra images and ALL
        # variants, including archived ones, but not variant-extra-image galleries.
        for model_name, image_field in (
            ("product.image", "image_1920"),
            ("product.product", "image_variant_1920"),
        ):
            related = self.env[model_name].with_context(
                prefetch_fields=False, active_test=False,
            ).search(relation_domain)
            image_ids = self._dashboard_image_record_ids(related, image_field)
            for row in related.read(["product_tmpl_id"], load=False):
                if row["id"] in image_ids:
                    result["image"].add(row["product_tmpl_id"])
        # Existing catalog's approved fallback returns a URL for an approved
        # record (image_1920 is required); no generated preview counts as coverage.
        approved = self.env["bpi.product.image"].with_context(prefetch_fields=False).search(
            relation_domain + [("state", "=", "approved")],
        )
        for row in approved.read(["product_tmpl_id"], load=False):
            result["image"].add(row["product_tmpl_id"])
        for row in self.env["bpi.product.faq"].with_context(prefetch_fields=False).search(
            relation_domain,
        ).read(["product_tmpl_id", "question", "answer"], load=False):
            if plain(row["question"]) and plain(row["answer"]):
                result["faq"].add(row["product_tmpl_id"])
        for row in self.env["bpi.product.competitor"].with_context(prefetch_fields=False).search(
            relation_domain,
        ).read(["product_tmpl_id", "competitor_url"], load=False):
            if (row["competitor_url"] or "").strip():
                result["competitor"].add(row["product_tmpl_id"])

        result["unpublished"] = result["all"] - result["published"]
        result["content"] = result["commercial"] & result["technical"]
        result["published_missing_image"] = result["published"] - result["image"]
        result["published_missing_content"] = result["published"] - result["commercial"]
        for key in ("seo", "geo", "category"):
            result["missing_" + key] = result["all"] - result[key]
        result["complete"] = set.intersection(*(result[key] for key in self._CATALOG_CHECKLIST))
        result["needs_attention"] = result["all"] - result["complete"]
        return result

    @api.model
    def _dashboard_catalog_health(self, coverage, product_id):
        flags = {key: product_id in coverage[key] for key in (*self._CATALOG_CHECKLIST, "competitor")}
        completed = sum(flags[key] for key in self._CATALOG_CHECKLIST)
        total = len(self._CATALOG_CHECKLIST)
        return {
            **flags, "completed": completed, "total": total,
            "percent": round(completed * 100.0 / total, 1),
        }

    @api.model
    def _dashboard_metric(self, coverage, key, label, description):
        count = len(coverage[key])
        total = len(coverage["all"])
        return {
            "key": key, "label": label, "count": count,
            "percent": round(100.0 * count / total, 1) if total else 0.0,
            "description": description, "filter": key,
        }

    @api.model
    def _dashboard_jobs(self, products):
        payload = {"pending": 0, "running": 0, "done": 0, "failed": 0, "recent": []}
        if not products:
            return payload
        jobs = self.env["bpi.ai.job"].with_context(prefetch_fields=False)
        domain = [("job_type", "=", "seo"), ("product_tmpl_id", "in", products.ids)]
        for group in jobs.read_group(domain, ["state"], ["state"]):
            payload[group["state"]] = group["state_count"]
        rows = jobs.search(domain, order="create_date desc, id desc", limit=5).read(
            ["product_tmpl_id", "state", "create_date", "finished_at"], load=False,
        )
        names = {row["id"]: row["name"] for row in products.browse(
            [row["product_tmpl_id"] for row in rows],
        ).with_context(prefetch_fields=False).read(["name"], load=False)}
        for row in rows:
            payload["recent"].append({
                "id": row["id"], "productId": row["product_tmpl_id"],
                "productName": names[row["product_tmpl_id"]], "state": row["state"],
                "createdAt": self._dashboard_datetime(row["create_date"]),
                "finishedAt": self._dashboard_datetime(row["finished_at"]),
            })
        return payload

    @api.model
    def _dashboard_datetime(self, value):
        return fields.Datetime.to_datetime(value).isoformat() + "Z" if value else False

    @api.model
    def dashboard_overview(self, category_id=False, meli_account_id=False):
        self._ensure_manager()
        category = self._dashboard_category(category_id)
        products = self.env["product.template"].search(expression.AND([
            self._dashboard_base_domain(), self._dashboard_tab_domain("all"),
            self._dashboard_category_domain(category),
        ]))
        coverage = self._dashboard_coverage_sets(products)
        meli = self._meli_projection(products, account_id=self._meli_account_key(meli_account_id))
        specifications = (
            ("all", _("Productos activos"), _("Productos activos y disponibles para la venta.")),
            ("published", _("Publicados"), _("Productos publicados del catálogo activo vendible.")),
            ("content", _("Contenido completo"), _("Descripción comercial visible y descripción técnica BPI con texto.")),
            ("image", _("Con imagen"), _("Imagen Odoo, galería nativa, variante o imagen BPI aprobada.")),
            ("seo", _("Metadatos SEO completos"), _("Título y descripción SEO guardados; no mide posicionamiento.")),
            ("geo", _("Metadatos GEO completos"), _("Título y descripción GEO guardados; no mide posicionamiento.")),
            ("faq", _("Con FAQs"), _("Al menos una pregunta y respuesta completas.")),
            ("competitor", _("Con competidores registrados"), _("Al menos una URL de competidor registrada, no necesariamente analizada.")),
        )
        kpis = [self._dashboard_metric(coverage, *specification) for specification in specifications]
        completeness = [metric for metric in kpis if metric["key"] in ("content", "image", "seo", "geo", "faq")]
        completeness.append(self._dashboard_metric(
            coverage, "category", _("Con categoría"), _("Al menos una categoría de comercio electrónico asignada."),
        ))
        priorities = [self._dashboard_metric(coverage, *specification) for specification in (
            ("published_missing_image", _("Publicados sin imagen"), _("Productos visibles que necesitan una imagen.")),
            ("published_missing_content", _("Publicados sin descripción comercial"), _("Productos visibles sin texto comercial disponible.")),
            ("missing_seo", _("SEO incompleto"), _("Falta el título o la descripción SEO.")),
            ("missing_geo", _("GEO incompleto"), _("Falta el título o la descripción GEO.")),
            ("missing_category", _("Sin categoría"), _("Productos sin categoría de comercio electrónico.")),
        )]
        categories = self.env["product.public.category"].search([], order="name asc, id asc")
        return {
            "generatedAt": self._dashboard_datetime(fields.Datetime.now()),
            "categoryId": category.id or False,
            "categories": [{"id": item.id, "name": item.name, "completeName": item.display_name} for item in categories],
            "total": len(products), "kpis": kpis, "coverage": completeness, "priorities": priorities,
            "publication": {
                "published": len(coverage["published"]), "unpublished": len(coverage["unpublished"]),
                "total": len(products), "publishedPercent": kpis[1]["percent"],
            },
            "jobs": self._dashboard_jobs(products),
            "meliOverview": self._meli_overview_payload(meli, len(products)),
            "exchangeRate": self.env["product.template"]._bpi_exchange_rate(),
        }

    @api.model
    def _dashboard_stats(self, category=False):
        products = self.env["product.template"]
        domain = expression.AND([
            self._dashboard_base_domain(), self._dashboard_tab_domain("all"),
            self._dashboard_category_domain(category),
        ])
        return {
            "total": products.search_count(domain),
            "published": products.search_count(domain + [("website_published", "=", True)]),
            "featured": products.search_count(domain + [("bpi_featured", "=", True)]),
            "pending": products.search_count(domain + [("website_published", "=", False)]),
        }

    @api.model
    def dashboard_payload(self, tab="all", search="", page=1, limit=40, category_id=False, quality_filter=False, sort_key="catalog", meli_account_id=False, meli_filter=False, taxonomy_term_ids=None):
        self._ensure_manager()
        if tab not in ("all", "new", "discontinued"):
            raise UserError(_("Selecciona una sección válida del catálogo."))
        if not isinstance(search, str):
            raise UserError(_("La búsqueda debe ser un texto."))
        category = self._dashboard_category(category_id)
        quality_filter = self._dashboard_quality_filter(quality_filter)
        sort_key = self._dashboard_sort_key(sort_key)
        meli_filter = self._meli_filter_key(meli_filter)
        meli_account_id = self._meli_account_key(meli_account_id)
        try:
            safe_page = max(int(page or 1), 1)
            safe_limit = min(max(int(limit or 40), 1), 120)
        except (ValueError, TypeError, OverflowError) as error:
            raise UserError(_("La página y el límite deben ser números válidos.")) from error
        product_model = self.env["product.template"].with_context(active_test=False, bin_size=True)
        domain = expression.AND([
            self._dashboard_base_domain(), self._dashboard_category_domain(category),
            self._dashboard_search_domain(search),
            product_model._bpi_filter_domain(product_model._bpi_filter_ids(taxonomy_term_ids)),
        ])
        coverage = None
        if quality_filter != "all":
            coverage = self._dashboard_coverage_sets(product_model.search(domain))
            domain = expression.AND([domain, [("id", "in", sorted(coverage[quality_filter]))]])
        meli = None
        if meli_filter:
            meli = self._meli_projection(product_model.search(domain), account_id=meli_account_id)
            if not meli.get("available"):
                raise UserError(meli.get("message") or _("Los filtros de Mercado Libre no están disponibles."))
            domain = expression.AND([domain, [("id", "in", sorted(meli["sets"][meli_filter]))]])
        tab_counts = {
            key: product_model.search_count(expression.AND([domain, self._dashboard_tab_domain(key)]))
            for key in ("all", "new", "discontinued")
        }
        total_rows = tab_counts[tab]
        page_count = max(1, int(math.ceil(total_rows / float(safe_limit))))
        safe_page = min(safe_page, page_count)
        products = product_model._bpi_ranked_search(
            expression.AND([domain, self._dashboard_tab_domain(tab)]), search if sort_key == "catalog" else "",
            order=self._CATALOG_SORT_ORDERS[sort_key], offset=(safe_page - 1) * safe_limit,
            limit=safe_limit,
        )
        # Reuse the quality-filter batch; otherwise enrich only this page, never
        # all catalog templates just to render a paginated checklist.
        if coverage is None:
            coverage = self._dashboard_coverage_sets(products)
        if meli is None:
            meli = self._meli_projection(products, account_id=meli_account_id)
        exchange_rate = product_model._bpi_exchange_rate()
        rows = []
        for product in products:
            row = product.bpi_dashboard_payload(exchange_rate=exchange_rate)
            row.update(coverage["row_metadata"][product.id])
            row["catalogHealth"] = self._dashboard_catalog_health(coverage, product.id)
            row["meliSummary"] = meli.get("rows", {}).get(product.id, self._meli_summary_default())
            rows.append(row)
        return {
            "products": rows,
            "exchangeRate": exchange_rate, "stats": self._dashboard_stats(category), "tabCounts": tab_counts,
            "categoryId": category.id or False, "qualityFilter": quality_filter, "sortKey": sort_key,
            "meli": self._meli_public_context(meli), "meliFilter": meli_filter,
            "taxonomyTerms": product_model._bpi_facets(expression.AND([domain, self._dashboard_tab_domain(tab)]), product_model._bpi_filter_ids(taxonomy_term_ids)),
            "pager": {
                "page": safe_page, "pageCount": page_count, "total": total_rows, "limit": safe_limit,
                "hasNext": safe_page < page_count, "hasPrevious": safe_page > 1,
            },
        }

    @api.model
    def sync_catalog(self, tab="all", search="", page=1, limit=40, category_id=False, quality_filter=False, sort_key="catalog", meli_account_id=False, meli_filter=False, taxonomy_term_ids=None):
        return self.dashboard_payload(
            tab=tab, search=search, page=page, limit=limit, category_id=category_id, quality_filter=quality_filter,
            sort_key=sort_key, meli_account_id=meli_account_id, meli_filter=meli_filter, taxonomy_term_ids=taxonomy_term_ids,
        )
