# -*- coding: utf-8 -*-
"""Extend the native variant response; never replace Odoo pricing or selection."""
import re
from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError, MissingError
from odoo.addons.website_sale.controllers.variant import WebsiteSaleVariantController


class DescriptionVariantController(WebsiteSaleVariantController):
    @http.route()
    def get_combination_info_website(self, product_template_id, product_id, combination, add_qty, **kw):
        variant_token = kw.pop('bpi_variant_token', '')
        variant_token = variant_token if isinstance(variant_token, str) and re.fullmatch(r'[0-9]{1,16}', variant_token) else ''
        token = kw.pop('bpi_description_token', '')
        token = token if isinstance(token, str) and re.fullmatch(r'[0-9]{1,16}', token) else ''
        storefront_token = kw.pop('bpi_storefront_token', '')
        storefront_token = storefront_token if isinstance(storefront_token, str) and re.fullmatch(r'[0-9]{1,16}', storefront_token) else ''
        result = super().get_combination_info_website(
            product_template_id, product_id, combination, add_qty, **kw)
        if request.website.bpi_premium_storefront_enabled and storefront_token:
            # Echo only request metadata. Prices, permissions, variants and
            # image HTML are still calculated solely by the native controller.
            result['bpi_storefront'] = {'token': storefront_token,
                'productTemplateId': result['product_template_id']}
        product = request.env['product.template'].browse(result['product_template_id']).exists()
        try:
            if product and product._bpi_has_variant_layout():
                variant_id = result.get('product_id') if result.get('is_combination_possible', True) else False
                layout = product._bpi_public_description_layout(request.website, variant_id=variant_id)
                html = request.env['ir.ui.view']._render_template(
                    'bader_product_intelligence.description_layout', {
                        'product': product, 'website': request.website, 'bpi_layout': layout,
                    }) if layout else ''
                result['bpi_description'] = {'html': str(html), 'variantId': variant_id or 0,
                    'productTemplateId': product.id, 'revision': product.bpi_editorial_revision, 'token': token}
        except (AccessError, MissingError):
            # No public fallback to privileged records or the previous variant.
            result['bpi_description'] = {'html': '', 'variantId': 0,
                'productTemplateId': result['product_template_id'], 'revision': 0, 'token': token}
        if request.website.bpi_variant_content_enabled and variant_token:
            projection = product._bpi_public_variant_content(request.website, result.get('product_id')) if product and result.get('is_combination_possible', True) else False
            public = {'token':variant_token, 'productId':result['product_template_id'], 'variantId':0,
                'short':'', 'html':'', 'url':'', 'name':'', 'title':'', 'description':'', 'keywords':'', 'image':'', 'jsonld':''}
            if projection:
                public.update({key:projection[key] for key in ('variantId','url','name','title','description','keywords','image')})
                public.update(short=str(projection['short']), html=str(request.env['ir.ui.view']._render_template(
                    'bader_product_intelligence.variant_editorial', {'product':product, 'website':request.website, 'bpi_variant_public':projection})),
                    jsonld=str(product._bpi_variant_jsonld(request.website, projection, request.website.get_current_pricelist())))
            result['bpi_variant_content'] = public
        return result
