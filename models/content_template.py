# -*- coding: utf-8 -*-
"""Admin-owned editorial recipes, independent of eCommerce categorization."""

import math

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class ContentTemplate(models.Model):
    _name = "bpi.content.template"
    _description = "Modelo de descripción Nancy"
    _order = "name, id"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    short_instructions = fields.Text(string="Instrucciones de descripción corta", required=True)
    long_instructions = fields.Text(string="Instrucciones de descripción larga", required=True)
    short_min_words = fields.Integer(string="Mínimo orientativo (corta)", default=45)
    short_max_words = fields.Integer(string="Máximo orientativo (corta)", default=70)
    long_min_words = fields.Integer(string="Mínimo orientativo (larga)")
    long_max_words = fields.Integer(string="Máximo orientativo (larga)")
    format = fields.Selection([
        ("free", "Libre"), ("two_sections", "Ficha de dos secciones"),
        ("general_specs", "General en corta · Especificaciones en larga"),
    ], required=True, default="free", string="Formato")
    revision = fields.Integer(default=1, readonly=True, copy=False)
    category_ids = fields.One2many(
        "product.category", "bpi_content_template_id", string="Categorías internas", copy=False,
    )
    category_selection_ids = fields.Many2many(
        "product.category", compute="_compute_category_selection", inverse="_inverse_category_selection",
        string="Aplicar a categorías internas", copy=False,
        help="Las subcategorías heredan este modelo. Seleccionar una categoría reemplaza su modelo anterior; no cambia la categoría de ningún producto.",
    )

    @api.depends("category_ids")
    def _compute_category_selection(self):
        for recipe in self:
            recipe.category_selection_ids = recipe.category_ids

    def _inverse_category_selection(self):
        self._ensure_manager()
        for recipe in self:
            desired = recipe.category_selection_ids
            (recipe.category_ids - desired).write({"bpi_content_template_id": False})
            (desired - recipe.category_ids).write({"bpi_content_template_id": recipe.id})

    @api.model
    def _ensure_manager(self):
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Los modelos de descripción requieren permisos de administrador."))

    @api.constrains("short_min_words", "short_max_words", "long_min_words", "long_max_words", "short_instructions", "long_instructions")
    def _check_recipe(self):
        for recipe in self:
            for prefix in ("short", "long"):
                low, high = recipe[prefix + "_min_words"], recipe[prefix + "_max_words"]
                if low < 0 or high < 0 or (low and high and low > high) or max(low, high) > 5000:
                    raise ValidationError(_("Las metas deben estar entre 0 y 5000 palabras, con mínimo no mayor al máximo. Cero significa sin límite."))
            if not (recipe.short_instructions or "").strip() or not (recipe.long_instructions or "").strip():
                raise ValidationError(_("Completa las instrucciones de las dos descripciones."))
            if max(len(recipe.short_instructions), len(recipe.long_instructions)) > 20000:
                raise ValidationError(_("Cada instrucción admite hasta 20.000 caracteres."))

    @api.model_create_multi
    def create(self, vals_list):
        self._ensure_manager()
        return super().create([{**vals, "revision": 1} for vals in vals_list])

    def _check_retirement(self):
        general = self.env.ref("bader_product_intelligence.content_template_general", raise_if_not_found=False)
        if general and general in self:
            raise UserError(_("General Bader es el modelo de respaldo y no puede archivarse ni eliminarse."))
        self._serialize_reference_change()
        # The database-wide reference check also sees archived/other-company
        # templates. It reveals no product data and never bypasses ORM writes.
        self.env["product.template"].flush_model(["bpi_content_template_id"])
        self.env["product.category"].flush_model(["bpi_content_template_id"])
        self.env.cr.execute("""
            SELECT 1 FROM product_template WHERE bpi_content_template_id IN %s
            UNION ALL
            SELECT 1 FROM product_category WHERE bpi_content_template_id IN %s LIMIT 1
        """, (tuple(self.ids), tuple(self.ids)))
        if self.env.cr.fetchone():
            raise UserError(_("El modelo está asociado a categorías o productos. Sustituye esas asociaciones antes de archivarlo o eliminarlo."))

    def write(self, vals):
        self._ensure_manager()
        if vals.get("active") is False and self:
            self._check_retirement()
        vals = {key: value for key, value in vals.items() if key != "revision"}
        if not vals:
            return True
        for recipe in self:
            super(ContentTemplate, recipe).write({**vals, "revision": recipe.revision + 1})
        return True

    def unlink(self):
        self._ensure_manager()
        if self:
            self._check_retirement()
        return super().unlink()

    def _bpi_payload(self):
        self.ensure_one()
        self._ensure_manager()
        self.check_access_rights("read")
        self.check_access_rule("read")
        return {
            "id": self.id, "name": self.name, "revision": self.revision, "format": self.format,
            "shortInstructions": self.short_instructions, "longInstructions": self.long_instructions,
            "shortMinWords": self.short_min_words, "shortMaxWords": self.short_max_words,
            "longMinWords": self.long_min_words, "longMaxWords": self.long_max_words,
        }

    @api.model
    def _check_assignment(self, value, for_write=False):
        self._ensure_manager()
        if value is False or value is None:
            return self.browse()
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValidationError(_("Selecciona un modelo de descripción válido."))
        recipe = self.browse(value).exists()
        recipe.check_access_rights("read")
        recipe.check_access_rule("read")
        if not recipe or not recipe.active:
            raise ValidationError(_("El modelo seleccionado no existe o está archivado."))
        if for_write:
            recipe._serialize_reference_change()
        return recipe

    def _serialize_reference_change(self):
        """Serialize assignments with retirement without changing a recipe.

        SELECT FOR UPDATE alone is insufficient under REPEATABLE READ: an
        assignment does not otherwise update this row, so retirement could
        later inspect an older reference snapshot. A no-op row UPDATE makes
        competing snapshots raise the normal serialization failure (safe to
        retry a save, never used during a paid generation request).
        """
        self._ensure_manager()
        self.check_access_rights("write")
        self.check_access_rule("write")
        if not self:
            return
        self.flush_recordset(["revision"])
        self.env.cr.execute(
            "UPDATE bpi_content_template SET revision = revision WHERE id IN %s",
            (tuple(sorted(self.ids)),),
        )


class ProductCategory(models.Model):
    _inherit = "product.category"

    bpi_content_template_id = fields.Many2one(
        "bpi.content.template", string="Modelo de descripción Nancy", ondelete="restrict",
        groups="base.group_system", copy=False,
        help="Se hereda por las subcategorías sin modelo propio. Las categorías duplicadas vuelven a la selección heredada.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "bpi_content_template_id" in vals:
                self.env["bpi.content.template"]._check_assignment(vals["bpi_content_template_id"], for_write=True)
        return super().create(vals_list)

    def write(self, vals):
        if "bpi_content_template_id" in vals:
            self.env["bpi.content.template"]._check_assignment(vals["bpi_content_template_id"], for_write=True)
        return super().write(vals)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    bpi_content_template_id = fields.Many2one(
        "bpi.content.template", string="Excepción de modelo Nancy", ondelete="restrict",
        groups="base.group_system", copy=False,
        help="Vacío: selección automática por la categoría interna y sus antecesoras.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "bpi_content_template_id" in vals:
                self.env["bpi.content.template"]._check_assignment(vals["bpi_content_template_id"], for_write=True)
        return super().create(vals_list)

    def write(self, vals):
        if "bpi_content_template_id" in vals:
            self.env["bpi.content.template"]._check_assignment(vals["bpi_content_template_id"], for_write=True)
        return super().write(vals)

    def _bpi_content_facts(self):
        """Explicit saved fields only: never treat generated prose as evidence."""
        self.ensure_one()
        self.env["bpi.service"]._meli_product(self.id)
        facts = []

        def add(key, label, value):
            if value:
                facts.append({"id": key, "label": label, "value": str(value)[:500]})

        def measurement(record, name, prefix="", label_prefix=""):
            number = record[name]
            if not number or not math.isfinite(number) or number <= 0:
                return
            # Native Odoo settings select kg/lb and m³/ft³. Resolve the native
            # uom record and convert to SI; never infer units from a number.
            getter = getattr(self, "_get_%s_uom_id_from_ir_config_parameter" % name, None)
            if not getter:
                return
            unit = getter()
            if isinstance(unit, int):
                unit = self.env["uom.uom"].browse(unit)
            si = self.env.ref("uom.product_uom_kgm" if name == "weight" else "uom.product_uom_cubic_meter", raise_if_not_found=False)
            if not unit or not si or unit.category_id != si.category_id:
                return
            number = unit._compute_quantity(number, si, round=False)
            value = ("%.6f" % number).rstrip("0").rstrip(".").replace(".", ",")
            add(prefix + name, label_prefix + (_("Peso") if name == "weight" else _("Volumen")), value + (" kg" if name == "weight" else " m³"))

        variants = self._bpi_all_variants().filtered("active")
        if len(variants) <= 1:
            record = variants[:1] or self
            for field in ("weight", "volume"):
                measurement(record, field)
            for line in self.attribute_line_ids:
                for value in line.value_ids:
                    add("attribute:%s:%s" % (line.id, value.id), line.attribute_id.name, value.name)
        else:
            for variant in variants[:30]:
                label = "%s — " % (variant.default_code or variant.display_name)
                for field in ("weight", "volume"):
                    measurement(variant, field, "variant:%s:" % variant.id, label)
                for value in variant.product_template_attribute_value_ids:
                    add("variant:%s:attribute:%s" % (variant.id, value.id), label + value.attribute_id.name, value.name)
        if self.pack_ok:
            for variant in variants[:20]:
                for line in variant.pack_line_ids[:60]:
                    component = line.product_id
                    component.check_access_rights("read")
                    component.check_access_rule("read")
                    if component.company_id and component.company_id not in self.env.companies:
                        continue
                    label = _("Componente de Pack") if len(variants) <= 1 else _("Componente de Pack %s") % (variant.default_code or variant.display_name)
                    quantity = ("%g" % line.quantity).replace(".", ",")
                    add("pack:%s:%s" % (variant.id, line.id), label, "%s × %s (%s)" % (quantity, component.display_name, component.uom_id.name))
        return facts[:200]
