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
        token = kw.pop('bpi_description_token', '')
        token = token if isinstance(token, str) and re.fullmatch(r'[0-9]{1,16}', token) else ''
        result = super().get_combination_info_website(
            product_template_id, product_id, combination, add_qty, **kw)
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
        return result
