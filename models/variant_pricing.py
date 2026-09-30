# -*- coding: utf-8 -*-
"""Guarded editing of native, SKU-specific price-list rules, not another engine."""
import math

from odoo import _, api, fields, models
from odoo.exceptions import MissingError, UserError, ValidationError

from .variant_content import fingerprint


class VariantPricingService(models.AbstractModel):
    _inherit = 'bpi.service'

    @api.model
    def _variant_pricelist(self, product, variant_id, pricelist_id):
        self._ensure_manager()
        variant = self.env['bpi.variant.content']._variant(product, variant_id)
        if type(pricelist_id) is not int or pricelist_id <= 0:
            raise ValidationError(_('Selecciona una tarifa.'))
        pricelist = self.env['product.pricelist'].browse(pricelist_id).exists()
        if not pricelist or not pricelist.active:
            raise MissingError(_('Tarifa no disponible.'))
        pricelist.check_access_rights('read'); pricelist.check_access_rule('read')
        if pricelist.company_id and pricelist.company_id not in self.env.companies:
            raise ValidationError(_('La tarifa pertenece a otra empresa.'))
        if product.company_id and pricelist.company_id and product.company_id != pricelist.company_id:
            raise ValidationError(_('La tarifa y el producto pertenecen a empresas diferentes.'))
        return variant, pricelist

    @api.model
    def _variant_rule_values(self, rule):
        return {name: rule[name] for name in ('compute_price', 'fixed_price', 'percent_price',
            'min_quantity', 'date_start', 'date_end')}

    @api.model
    def _variant_pricing_revision(self, variant, pricelist):
        rules = pricelist.item_ids.filtered(lambda r: r.product_id == variant)
        return fingerprint([(r.id, r.write_date, self._variant_rule_values(r)) for r in rules.sorted('id')])

    @api.model
    def variant_pricing(self, product, variant_id, pricelist_id, quantity=1, date=False):
        variant, pricelist = self._variant_pricelist(product, variant_id, pricelist_id)
        quantity = self._variant_number(quantity, positive=True)
        try:
            when = fields.Datetime.to_datetime(date) if date else fields.Datetime.now()
        except (TypeError, ValueError):
            raise ValidationError(_('Fecha no válida.'))
        # Odoo chooses rule precedence, currency conversion, quantity and date.
        price, rule_id = pricelist._get_product_price_rule(variant, quantity, date=when)
        rule = self.env['product.pricelist.item'].browse(rule_id)
        rows = []
        for item in pricelist.item_ids.filtered(lambda r: r.product_id == variant).sorted('id'):
            values = self._variant_rule_values(item)
            rows.append(dict(values, id=item.id, editable=item.compute_price in ('fixed', 'percentage'),
                date_start=fields.Datetime.to_string(item.date_start) or False,
                date_end=fields.Datetime.to_string(item.date_end) or False))
        return {'variantId': variant.id, 'pricelistId': pricelist.id, 'pricelistName': pricelist.name,
            'currency': pricelist.currency_id.name, 'quantity': quantity, 'date': fields.Datetime.to_string(when),
            'price': price, 'ruleId': rule.id or False, 'ruleName': rule.name if rule else '',
            'ruleIsVariantSpecific': bool(rule and rule.product_id == variant), 'rules': rows,
            'revision': self._variant_pricing_revision(variant, pricelist),
            'notice': _('Precio de tarifa. Los impuestos y posiciones fiscales se calculan en la venta por Odoo.')}

    @api.model
    def _variant_number(self, value, positive=False):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 or (positive and value == 0):
            raise ValidationError(_('Introduce un importe o cantidad numérica válida.'))
        return float(value)

    @api.model
    def save_variant_pricing(self, product, variant_id, pricelist_id, revision, values=None, rule_id=False, delete=False, quantity=1, date=False):
        variant, pricelist = self._variant_pricelist(product, variant_id, pricelist_id)
        if not isinstance(revision, str) or type(delete) is not bool:
            raise ValidationError(_('Revisión de tarifa inválida.'))
        with self.env.cr.savepoint():
            # Serialize additions/deletions too; force snapshot retries instead
            # of overwriting a rule committed while this request was waiting.
            pricelist.check_access_rights('write'); pricelist.check_access_rule('write')
            self.env.cr.execute('UPDATE product_pricelist SET write_date=write_date WHERE id=%s', [pricelist.id])
            pricelist.invalidate_recordset(['item_ids'])
            if self._variant_pricing_revision(variant, pricelist) != revision:
                raise UserError(_('La tarifa cambió. Recarga sus reglas antes de guardar.'))
            rule = self.env['product.pricelist.item']
            if rule_id is not False and rule_id is not None:
                if type(rule_id) is not int or rule_id <= 0:
                    raise ValidationError(_('Regla de tarifa inválida.'))
                rule = rule.browse(rule_id).exists()
                if not rule or rule.pricelist_id != pricelist or rule.product_id != variant or rule.applied_on != '0_product_variant':
                    raise ValidationError(_('Solo se pueden editar reglas específicas de esta variante y tarifa.'))
                if rule.compute_price not in ('fixed', 'percentage'):
                    raise ValidationError(_('Edita esta fórmula avanzada desde el formulario nativo de Odoo.'))
            if delete:
                if not rule or values:
                    raise ValidationError(_('Selecciona solamente la regla que quieres eliminar.'))
                rule.unlink()
            else:
                allowed = {'compute_price', 'fixed_price', 'percent_price', 'min_quantity', 'date_start', 'date_end'}
                if not isinstance(values, dict) or set(values) - allowed:
                    raise ValidationError(_('Campos de tarifa no permitidos.'))
                current = self._variant_rule_values(rule) if rule else {'compute_price': 'fixed', 'fixed_price': 0, 'percent_price': 0, 'min_quantity': 1, 'date_start': False, 'date_end': False}
                current.update(values)
                if current['compute_price'] not in ('fixed', 'percentage'):
                    raise ValidationError(_('Selecciona precio fijo o descuento porcentual.'))
                for key in ('fixed_price', 'percent_price', 'min_quantity'):
                    current[key] = self._variant_number(current[key])
                if current['percent_price'] > 100:
                    raise ValidationError(_('El descuento no puede superar 100 %.'))
                try:
                    for key in ('date_start', 'date_end'):
                        current[key] = fields.Datetime.to_datetime(current[key]) if current[key] else False
                except (TypeError, ValueError):
                    raise ValidationError(_('Vigencia de tarifa inválida.'))
                if current['date_start'] and current['date_end'] and current['date_end'] < current['date_start']:
                    raise ValidationError(_('La fecha final debe ser posterior a la inicial.'))
                if rule:
                    rule.write(current)
                else:
                    self.env['product.pricelist.item'].create(dict(current, pricelist_id=pricelist.id,
                        applied_on='0_product_variant', product_id=variant.id, product_tmpl_id=product.id))
            return self.variant_pricing(product, variant.id, pricelist.id, quantity=quantity, date=date)
