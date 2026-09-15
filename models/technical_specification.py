# -*- coding: utf-8 -*-
"""Saved editorial measurements, separate from native logistics and ML writes."""
import hashlib
import json
import math
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

SPEC_FIELDS = {
    'height': ('Alto', 'cm'), 'widthMax': ('Ancho máximo', 'cm'),
    'widthMin': ('Ancho mínimo', 'cm'), 'length': ('Largo', 'cm'),
    'diameter': ('Diámetro', 'cm'), 'weight': ('Peso neto', 'g'),
}


class TechnicalSpecification(models.Model):
    _name = 'bpi.product.specification'
    _description = 'Especificaciones técnicas verificadas del producto'

    product_id = fields.Many2one('product.product', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='product_id.company_id', store=True, index=True)
    measurements = fields.Json(default=dict)
    provenance = fields.Json(default=dict)
    revision = fields.Integer(default=1, readonly=True)
    _sql_constraints = [('variant_unique', 'unique(product_id)', 'La variante ya tiene especificaciones.')]

    @api.model
    def _normalize(self, values):
        if not isinstance(values, dict) or set(values) - set(SPEC_FIELDS):
            raise ValidationError(_('Las especificaciones contienen campos no permitidos.'))
        result = {}
        for key, value in values.items():
            if value is None or value == '':
                continue
            if isinstance(value, bool) or not isinstance(value, (str, int, float)):
                raise ValidationError(_('Las medidas deben ser números positivos o campos vacíos.'))
            if isinstance(value, str):
                value = value.strip()
                if not re.fullmatch(r'\d+(?:[.,]\d{1,6})?', value):
                    raise ValidationError(_('Usa números sin separador de miles, con hasta seis decimales.'))
                value = value.replace(',', '.')
            value = float(value)
            if not math.isfinite(value) or value <= 0 or value > 1000000 or round(value, 6) != value:
                raise ValidationError(_('Las medidas deben ser mayores que cero y no superar 1.000.000.'))
            result[key] = value
        if result.get('widthMin', 0) > result.get('widthMax', float('inf')):
            raise ValidationError(_('El ancho mínimo no puede superar el ancho máximo.'))
        return result

    def _check_variant(self, variant):
        self.env['bpi.service']._ensure_manager()
        variant.check_access_rights('read')
        variant.check_access_rule('read')
        variant.check_access_rights('write')
        variant.check_access_rule('write')
        if not variant.exists() or (variant.company_id and variant.company_id not in self.env.companies):
            raise UserError(_('La variante no está disponible en las empresas seleccionadas.'))

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for vals in vals_list:
            self._check_variant(self.env['product.product'].browse(vals.get('product_id')))
            prepared.append(dict(vals, measurements=self._normalize(vals.get('measurements', {})), revision=1))
        return super().create(prepared)

    def write(self, vals):
        if 'product_id' in vals or 'revision' in vals:
            raise ValidationError(_('No se puede cambiar la identidad o revisión de las especificaciones.'))
        for record in self:
            record._check_variant(record.product_id)
            updated = dict(vals)
            if 'measurements' in vals:
                updated['measurements'] = self._normalize(vals['measurements'])
            updated['revision'] = record.revision + 1
            super(TechnicalSpecification, record).write(updated)
        return True

    @api.model
    def _payload(self, product):
        self.env['bpi.service']._meli_product(product.id)
        variants = product._bpi_all_variants()
        variants = variants.filtered(lambda v: not v.company_id or v.company_id in self.env.companies)
        records = {r.product_id.id: r for r in self.search([('product_id', 'in', variants.ids)])}
        return [{'variantId': v.id, 'sku': v.default_code or '', 'name': v.display_name,
                 'active': v.active, 'revision': records[v.id].revision if v.id in records else 0,
                 'values': records[v.id].measurements or {} if v.id in records else {},
                 'sources': records[v.id].provenance or {} if v.id in records else {}}
                for v in variants]

    @api.model
    def _save_rows(self, product, rows, source=None):
        self.env['bpi.service']._meli_product(product.id)
        if not isinstance(rows, list) or len(rows) > 1000:
            raise ValidationError(_('Las especificaciones deben ser una lista válida de variantes.'))
        variants = {v.id: v for v in product._bpi_all_variants()}
        seen = set()
        with self.env.cr.savepoint():
            for row in rows:
                if not isinstance(row, dict) or set(row) - {'variantId', 'revision', 'values'}:
                    raise ValidationError(_('La fila de especificaciones no es válida.'))
                vid, revision = row.get('variantId'), row.get('revision')
                if type(vid) is not int or vid not in variants or vid in seen or type(revision) is not int or revision < 0:
                    raise ValidationError(_('Variante ajena, duplicada o revisión inválida.'))
                seen.add(vid)
                self._check_variant(variants[vid])
                values = self._normalize(row.get('values'))
                record = self.search([('product_id', '=', vid)])
                if (record.revision if record else 0) != revision:
                    raise UserError(_('Las especificaciones cambiaron. Conservamos tus borradores; recarga antes de guardar.'))
                old = record.measurements or {} if record else {}
                if values == old:
                    continue
                if record:
                    # Serialize competing edits under PostgreSQL REPEATABLE READ.
                    self.env.cr.execute('UPDATE bpi_product_specification SET revision=revision WHERE id=%s', [record.id])
                provenance = dict(record.provenance or {}) if record else {}
                for key in SPEC_FIELDS:
                    if key not in values:
                        provenance.pop(key, None)
                    elif values.get(key) != old.get(key):
                        provenance[key] = dict(source or {'kind': 'manual', 'label': 'Edición manual'},
                                               date=fields.Datetime.to_string(fields.Datetime.now()))
                if record:
                    record.write({'measurements': values, 'provenance': provenance})
                else:
                    self.create({'product_id': vid, 'measurements': values, 'provenance': provenance})
        return True


class TechnicalProduct(models.Model):
    _inherit = 'product.template'

    def bpi_build_payload(self):
        result = super().bpi_build_payload()
        result['technicalSpecifications'] = self.env['bpi.product.specification']._payload(self)
        return result

    def _bpi_content_facts(self):
        facts = super()._bpi_content_facts()
        rows = self.env['bpi.product.specification']._payload(self)
        active = [r for r in rows if r['active']]
        for row in active:
            # Dedicated net weight supersedes native logistics weight as evidence.
            if 'weight' in row['values']:
                old_id = 'weight' if len(active) <= 1 else 'variant:%s:weight' % row['variantId']
                facts = [f for f in facts if f['id'] != old_id]
            for key, (label, unit) in SPEC_FIELDS.items():
                value = row['values'].get(key)
                if value is not None:
                    prefix = (row['sku'] or row['name']) + ' — ' if len(active) > 1 else ''
                    facts.append({'id': 'spec:%s:%s' % (row['variantId'], key), 'label': prefix + label,
                                  'value': ('%.6f' % value).rstrip('0').rstrip('.').replace('.', ',') + ' ' + unit})
        return facts


class TechnicalService(models.AbstractModel):
    _inherit = 'bpi.service'

    @api.model
    def update_product(self, product, values):
        product = self._meli_product(product.id)
        if not isinstance(values, dict):
            raise ValidationError(_('Los cambios deben ser un objeto válido.'))
        values = dict(values)
        rows = values.pop('technicalSpecifications', None)
        with self.env.cr.savepoint():
            if rows is not None:
                self.env['bpi.product.specification']._save_rows(product, rows)
            return super().update_product(product, values)

    @api.model
    def content_template_context(self, product, *args, **kwargs):
        result = super().content_template_context(product, *args, **kwargs)
        rows = self.env['bpi.product.specification']._payload(product)
        result['specificationRevision'] = hashlib.sha256(json.dumps(
            [(r['variantId'], r['sku'], r['active'], r['revision']) for r in rows], sort_keys=True).encode()).hexdigest()
        return result
