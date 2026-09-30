# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale
from ..models.taxonomy import AXES
from odoo.exceptions import ValidationError
from werkzeug.exceptions import BadRequest


class TaxonomyShop(WebsiteSale):
    def _get_search_options(self, *args, **kwargs):
        options = super()._get_search_options(*args, **kwargs)
        if request.website.bpi_taxonomy_search_enabled:
            options['bpiTermIds'] = request.env['product.template']._bpi_filter_ids(request.params.get('bpi_terms'))
            options['allowFuzzy'] = False
        return options

    def _shop_get_query_url_kwargs(self, *args, **kwargs):
        result = super()._shop_get_query_url_kwargs(*args, **kwargs)
        if request.website.bpi_taxonomy_search_enabled:
            result['bpi_terms'] = request.params.get('bpi_terms', '')
        return result

    def _get_search_domain(self, search, category, attrib_values, search_in_description=True):
        from odoo.osv import expression
        model = request.env['product.template']
        if request.website.bpi_variant_content_enabled:
            model = model.with_context(bpi_variant_term_ids=model._bpi_filter_ids(request.params.get('bpi_terms')),
                                       bpi_variant_category_id=int(category) if category else False)
        if not request.website.bpi_taxonomy_search_enabled:
            result = super()._get_search_domain(search, category, attrib_values, search_in_description)
        else:
            result = expression.AND([super()._get_search_domain('',category,attrib_values,False),
                model._bpi_query_domain(search or '', descriptions=True), model._bpi_filter_domain(model._bpi_filter_ids(request.params.get('bpi_terms')))])
        if request.website.bpi_variant_content_enabled:
            adapted = []
            for leaf in result:
                if isinstance(leaf, (tuple,list)) and len(leaf)==3 and leaf[0]=='public_categ_ids' and leaf[1]=='child_of':
                    adapted.extend(model._bpi_effective_category_domain(leaf[2]))
                else:
                    adapted.append(leaf)
            return adapted
        return result

    @http.route()
    def shop(self, page=0, category=None, search='', min_price=0.0, max_price=0.0, ppg=False, **post):
        if request.website.bpi_taxonomy_search_enabled:
            try:
                request.env['product.template']._bpi_filter_ids(post.get('bpi_terms'))
                request.env['product.template']._bpi_query_domain(search or '')
            except ValidationError as error:
                raise BadRequest(str(error)) from error
        response = super().shop(page=page, category=category, search=search, min_price=min_price, max_price=max_price, ppg=ppg, **post)
        if request.website.bpi_taxonomy_search_enabled and getattr(response, 'qcontext', None):
            model = request.env['product.template']
            ids = model._bpi_filter_ids(post.get('bpi_terms'))
            products = response.qcontext.get('search_product', response.qcontext.get('products', model))
            facets = model._bpi_facets([('id','in',products.ids)],ids)
            response.qcontext.update(bpi_taxonomy_axes=AXES, bpi_taxonomy_facets=facets,
                bpi_taxonomy_selected=ids, bpi_taxonomy_search=search,
                bpi_taxonomy_preserved=[(k,v) for k,vs in request.httprequest.args.lists() if k not in ('bpi_terms','page') for v in vs])
        if request.website.bpi_variant_content_enabled and search and getattr(response, 'qcontext', None):
            products = response.qcontext.get('search_product', request.env['product.template'])
            variants = request.env['product.product'].search([('product_tmpl_id','in',products.ids), ('active','=',True)])
            Category = request.env['product.public.category']
            categories = Category.search([('id','in',variants.bpi_effective_category_ids.ids)] + request.website.website_domain()).parents_and_self
            response.qcontext.update(categories=categories.filtered(lambda category: not category.parent_id),
                                     search_categories_ids=categories.ids)
        return response
