# -*- coding: utf-8 -*-
from odoo import http
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale


class VariantStorefront(WebsiteSale):
    @http.route()
    def product(self, product, category='', search='', **kwargs):
        website = request.website
        raw = kwargs.get('variant')
        if not website.bpi_variant_content_enabled:
            return super().product(product, category=category, search=search, **kwargs)
        try:
            if raw is not None:
                if not isinstance(raw, str) or not raw.isdigit() or int(raw) <= 0:
                    return request.not_found()
                variant = product._bpi_public_variant(website, int(raw))
                if not variant:
                    return request.not_found()
            else:
                combination = product._get_first_possible_combination()
                variant = product._get_variant_for_combination(combination)
            projection = product._bpi_public_variant_content(website, variant.id) if variant else False
            if not projection:
                return super().product(product, category=category, search=search, **kwargs)
            product = product.with_context(bpi_public_variant_id=variant.id, bpi_public_template_id=product.id)
            response = super().product(product, category=category, search=search, **kwargs)
            if getattr(response, 'qcontext', None):
                response.qcontext.update(bpi_variant_public=projection,
                    bpi_variant_jsonld=product._bpi_variant_jsonld(website, projection, response.qcontext['pricelist']))
                if raw is not None:
                    response.qcontext['canonical_params'] = {'variant':variant.id}
                response.headers['Cache-Control'] = 'private, no-cache'
            return response
        except (AccessError, MissingError):
            return request.not_found()


class VariantGallery(http.Controller):
    @http.route('/bader_product_intelligence/variant_gallery/<int:product_id>/<int:variant_id>/<int:image_id>',
                type='http', auth='public', website=True, methods=['GET','HEAD'], sitemap=False)
    def image(self, product_id, variant_id, image_id, size='1024', r=None, **kwargs):
        if size not in ('128','1024','1920') or not isinstance(r, str) or len(r)>40:
            return request.not_found()
        try:
            product = request.env['product.template'].browse(product_id).exists()
            image = product._bpi_public_gallery_reference(request.website, variant_id, image_id, r) if product else False
            if not image:
                return request.not_found()
            stream = request.env['ir.binary']._get_image_stream_from(image, field_name='image_1920',
                        width=int(size), height=int(size), crop=False)
            if stream.type == 'url' or stream.mimetype not in ('image/png','image/jpeg','image/webp'):
                return request.not_found()
            response = stream.get_response(as_attachment=False)
            response.headers.update({'Cache-Control':'private, no-store', 'X-Content-Type-Options':'nosniff',
                'Content-Security-Policy':"sandbox; default-src 'none'; frame-ancestors 'self'", 'Referrer-Policy':'no-referrer'})
            return response
        except (AccessError, MissingError, UserError, ValueError):
            return request.not_found()
