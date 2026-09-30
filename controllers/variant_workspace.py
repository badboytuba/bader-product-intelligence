# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

from .main import BaderProductIntelligenceController


class VariantWorkspaceController(BaderProductIntelligenceController):
    def _competitor(self, product, competitor_id):
        request.env['bpi.service']._require_common_generation()
        return super()._competitor(product, competitor_id)

    def _ai_job(self, job_id):
        from odoo import _
        from odoo.exceptions import MissingError
        job = super()._ai_job(job_id)
        selected = request.env.context.get('bpi_product_variant_id') or False
        if job.product_variant_id.id != selected:
            raise MissingError(_('El trabajo pertenece a otro contexto de edición.'))
        return job

    @http.route()
    def data(self, product_tmpl_id, product_variant_id=False, **kwargs):
        product = self._product(product_tmpl_id)
        if product_variant_id is not False and product_variant_id is not None:
            return product.bpi_build_variant_payload(product_variant_id)
        return super().data(product_tmpl_id, **kwargs)

    @http.route()
    def meli_product_status(self, product_tmpl_id, meli_account_id=False, product_variant_id=False, **kwargs):
        selected = product_variant_id or request.env.context.get('bpi_product_variant_id')
        if not selected:
            return super().meli_product_status(product_tmpl_id, meli_account_id=meli_account_id, **kwargs)
        return request.env['bpi.service']._variant_meli_detail(self._product(product_tmpl_id), selected, meli_account_id)

    @http.route('/bader_product_intelligence/variant_content/save', type='json', auth='user')
    def save_variant_content(self, product_tmpl_id, product_variant_id, base_revision,
                             revision, changes=None, inherit=None, proposal_id=None, context_revision=None, specifications=None, **kwargs):
        product = self._product(product_tmpl_id)
        request.env['bpi.variant.content']._save_workspace(product, product_variant_id,
            {} if changes is None else changes, [] if inherit is None else inherit,
            base_revision, revision, proposal_id=proposal_id, context_revision=context_revision, specifications=specifications)
        return {'success': True, **product.bpi_build_variant_payload(product_variant_id)}

    @http.route('/bader_product_intelligence/variant_pricing/data', type='json', auth='user')
    def variant_pricing(self, product_tmpl_id, product_variant_id, pricelist_id, quantity=1, date=False, **kwargs):
        return request.env['bpi.service'].variant_pricing(self._product(product_tmpl_id), product_variant_id, pricelist_id, quantity, date)

    @http.route('/bader_product_intelligence/variant_pricing/save', type='json', auth='user')
    def save_variant_pricing(self, product_tmpl_id, product_variant_id, pricelist_id, revision, values=None, rule_id=False, delete=False, quantity=1, date=False, **kwargs):
        return request.env['bpi.service'].save_variant_pricing(self._product(product_tmpl_id), product_variant_id, pricelist_id, revision, values, rule_id, delete, quantity=quantity, date=date)

    @http.route('/bader_product_intelligence/variant_specs/save', type='json', auth='user')
    def save_variant_specs(self, product_tmpl_id, product_variant_id, base_revision, revision,
                           context_revision, specifications, **kwargs):
        from odoo import _
        from odoo.exceptions import ValidationError
        product = self._product(product_tmpl_id)
        if not isinstance(specifications, list) or len(specifications) != 1 or not isinstance(specifications[0], dict) or specifications[0].get('variantId') != product_variant_id:
            raise ValidationError(_('Guarda únicamente las especificaciones de la variante seleccionada.'))
        with request.env.cr.savepoint():
            request.env['bpi.variant.content']._save(product, product_variant_id, {}, [],
                base_revision, revision, context_revision=context_revision)
            request.env['bpi.product.specification']._save_rows(product, specifications)
            return product.bpi_build_variant_payload(product_variant_id)
