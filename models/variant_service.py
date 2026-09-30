# -*- coding: utf-8 -*-
"""Fail closed for template-only actions until a variant contract is supplied."""
from odoo import _, api, models
from odoo.exceptions import ValidationError


class VariantService(models.AbstractModel):
    _inherit = 'bpi.service'

    @api.model
    def _variant_meli_detail(self, product, variant_id, account_id=False):
        variant = self.env['bpi.variant.content']._variant(product, variant_id)
        result = self.meli_detail(product.id, account_id=account_id)
        result.update(variantId=variant.id, scopeNotice=_(
            'Se muestran los vínculos de este SKU. Las consultas del observador son compartidas por producto; no publican ni sincronizan anuncios.'))
        if not result.get('available') or not hasattr(self, '_meli_project'):
            result['groups'] = []
            return result
        # Reuse the optional bridge's native identity and evidence aggregation,
        # BEFORE private internal identity flags are stripped. No remote calls.
        _projection, grouped = self._meli_project(product, account_id=account_id, detail=True)
        groups = [group for group in grouped.get(product.id, {}).values() if group['productVariantId']==variant.id]
        result['summary'] = self._meli_product_summary(groups)
        for group in groups:
            for item in group['items']:
                item.pop('_identity', None)
                item.pop('_listingId', None)
        result['groups'] = groups
        return result

    def _require_common_generation(self):
        if self.env.context.get('bpi_product_variant_id'):
            raise ValidationError(_('Para esta edición utiliza Nancy AI Studio. La acción común no se ejecutó ni consumió una generación.'))

    @api.model
    def generate_content(self, product, *args, **kwargs):
        self._require_common_generation()
        return super().generate_content(product, *args, **kwargs)

    @api.model
    def generate_faq(self, product, *args, **kwargs):
        self._require_common_generation()
        return super().generate_faq(product, *args, **kwargs)

    @api.model
    def analyze_seo(self, product, *args, **kwargs):
        self._require_common_generation()
        return super().analyze_seo(product, *args, **kwargs)

    @api.model
    def chat_with_product(self, product, *args, **kwargs):
        self._require_common_generation()
        return super().chat_with_product(product, *args, **kwargs)

    @api.model
    def update_variant(self, product, variant, values):
        selected = self.env.context.get('bpi_product_variant_id')
        if selected and selected != variant.id:
            raise ValidationError(_('Selecciona la variante que deseas editar.'))
        return super().update_variant(product, variant, values)

    @api.model
    def set_variant_image(self, product, variant, *args, **kwargs):
        selected = self.env.context.get('bpi_product_variant_id')
        if selected and selected != variant.id:
            raise ValidationError(_('Selecciona la variante de la imagen.'))
        return super().set_variant_image(product, variant, *args, **kwargs)


    @api.model
    def add_competitor(self, product, *args, **kwargs):
        self._require_common_generation()
        return super().add_competitor(product, *args, **kwargs)

    @api.model
    def discover_competitors(self, product, *args, **kwargs):
        self._require_common_generation()
        return super().discover_competitors(product, *args, **kwargs)

    @api.model
    def scrape_competitor(self, competitor):
        self._require_common_generation()
        return super().scrape_competitor(competitor)

    @api.model
    def analyze_competitor(self, competitor):
        self._require_common_generation()
        return super().analyze_competitor(competitor)

    @api.model
    def generate_competitive_strategy(self, product):
        self._require_common_generation()
        return super().generate_competitive_strategy(product)


class VariantGenerationJob(models.Model):
    _inherit = 'bpi.ai.job'

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            if values.get('product_variant_id'):
                product = self.env['bpi.service']._meli_product(values.get('product_tmpl_id'))
                self.env['bpi.variant.content']._variant(product, values['product_variant_id'])
        return super().create(values_list)

    def write(self, values):
        if 'product_variant_id' in values and any((values['product_variant_id'] or False) != record.product_variant_id.id for record in self):
            raise ValidationError(_('No se puede cambiar la edición de un trabajo existente.'))
        if 'product_tmpl_id' in values and any(record.product_variant_id and values['product_tmpl_id'] != record.product_tmpl_id.id for record in self):
            raise ValidationError(_('El trabajo pertenece a otro producto.'))
        return super().write(values)

    @api.model
    def create_seo_job(self, product, target_audience='clinicas', user=False):
        self.env['bpi.service']._require_common_generation()
        return super().create_seo_job(product, target_audience=target_audience, user=user)
