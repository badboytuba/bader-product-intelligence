"""Private audited import helper: no downloads, cron, fuzzy SKU or native writes."""
from collections import Counter
from odoo import api, models
from odoo.exceptions import ValidationError
from .technical_specification import SPEC_FIELDS


class SpecificationImport(models.AbstractModel):
    _inherit = 'bpi.service'

    @api.model
    def _prepare_specification_import(self, rows):
        self._ensure_manager()
        if not isinstance(rows, list) or len(rows) > 10000:
            raise ValidationError('La importación debe contener hasta 10.000 filas.')
        counts = Counter(str(row.get('sku', '')).strip() for row in rows)
        variants = self.env['product.product'].with_context(active_test=False).search([
            ('default_code', 'in', [sku for sku in counts if sku]),
            '|', ('company_id', '=', False), ('company_id', 'in', self.env.companies.ids)])
        by_sku = {}
        for variant in variants:
            by_sku.setdefault(variant.default_code, []).append(variant)
        specs = self.env['bpi.product.specification']
        existing = {r.product_id.id: r for r in specs.search([('product_id', 'in', variants.ids)])}
        updates, issues, unchanged = [], [], 0
        for row in rows:
            sku = str(row.get('sku', '')).strip()
            def issue(reason, **extra):
                issues.append(dict(row=row.get('row'), sku=sku, reason=reason, **extra))
            if not sku:
                issue('missing_sku'); continue
            if counts[sku] != 1:
                issue('duplicate_sheet_sku'); continue
            matches = by_sku.get(sku, [])
            if len(matches) != 1:
                issue('sku_not_found' if not matches else 'ambiguous_odoo_sku'); continue
            variant = matches[0]
            if not variant.active or not variant.product_tmpl_id.active:
                issue('archived_product'); continue
            record = existing.get(variant.id)
            old = dict(record.measurements or {}) if record else {}
            desired = dict(old)
            for key, raw in row.get('values', {}).items():
                if key not in SPEC_FIELDS:
                    issue('unknown_field', field=key); continue
                if raw is None or (isinstance(raw, str) and not raw.strip()):
                    continue
                try:
                    clean = specs._normalize({key: raw})[key]
                except (ValidationError, KeyError):
                    issue('invalid_measurement', field=key, value=str(raw)); continue
                if key in old and old[key] != clean:
                    issue('existing_value_preserved', field=key, existing=old[key], incoming=clean); continue
                desired[key] = clean
            if desired.get('widthMin', 0) > desired.get('widthMax', float('inf')):
                issue('minimum_exceeds_maximum')
                for key in ('widthMin', 'widthMax'):
                    if key in old: desired[key] = old[key]
                    else: desired.pop(key, None)
            if desired == old:
                unchanged += 1; continue
            updates.append({'productId': variant.product_tmpl_id.id, 'sku': sku, 'sourceRow': row.get('row'),
                            'variantId': variant.id, 'revision': record.revision if record else 0,
                            'values': desired})
        return {'updates': updates, 'issues': issues, 'unchanged': unchanged, 'inputRows': len(rows)}

    @api.model
    def _apply_specification_import(self, plan, source):
        self._ensure_manager()
        with self.env.cr.savepoint():
            for item in plan['updates']:
                product = self._meli_product(item['productId'])
                variant = self.env['product.product'].with_context(active_test=False).browse(item['variantId'])
                if variant.default_code != item['sku'] or not variant.active:
                    raise ValidationError('El SKU o estado cambió después de preparar la importación.')
                self.env['bpi.product.specification']._save_rows(product, [
                    {key: item[key] for key in ('variantId', 'revision', 'values')}],
                    dict(source, row=item['sourceRow']))
        return len(plan['updates'])
