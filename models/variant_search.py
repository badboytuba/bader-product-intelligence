# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.http import request
from odoo.osv import expression
from odoo.tools import html2plaintext
from odoo.tools.sql import escape_psql
from .taxonomy import AXES
from .taxonomy import normalize


class VariantSearchIndex(models.Model):
    _inherit = 'product.product'

    bpi_variant_profile_ids = fields.One2many('bpi.variant.content', 'product_id', groups='base.group_system')
    bpi_effective_term_ids = fields.Many2many('bpi.taxonomy.term', 'bpi_variant_effective_term_rel',
        'variant_id', 'term_id', compute='_compute_bpi_variant_index', store=True, compute_sudo=True)
    bpi_effective_category_ids = fields.Many2many('product.public.category', 'bpi_variant_effective_category_rel',
        'variant_id', 'category_id', compute='_compute_bpi_variant_index', store=True, compute_sudo=True)
    bpi_effective_search_identity = fields.Text(compute='_compute_bpi_variant_index', store=True, compute_sudo=True, unaccent=False)
    bpi_effective_search_description = fields.Text(compute='_compute_bpi_variant_index', store=True, compute_sudo=True, unaccent=False)

    @api.depends('bpi_variant_profile_ids.overrides', 'default_code',
                 'product_template_attribute_value_ids.name', 'product_tmpl_id.name', 'product_tmpl_id.bpi_brand_name',
                 'product_tmpl_id.bpi_taxonomy_term_ids', 'product_tmpl_id.public_categ_ids',
                 'product_tmpl_id.public_categ_ids.name', 'product_tmpl_id.description_sale',
                 'product_tmpl_id.bpi_ai_generated_description', 'product_tmpl_id.bpi_technical_description')
    def _compute_bpi_variant_index(self):
        # Index saved editorial content only. No conversation, source, draft or
        # proposal is included. Profiles remain private; common writes recompute
        # only the inherited values through normal ORM dependencies.
        for variant in self:
            product = variant.product_tmpl_id.with_context(lang='es_ES')
            overrides = variant.bpi_variant_profile_ids[:1].overrides or {}
            classification = overrides.get('classification', {'termIds':product.bpi_taxonomy_term_ids.ids})
            variant.bpi_effective_term_ids = [(6, 0, classification.get('termIds', []))]
            categories = self.env['product.public.category'].browse(overrides.get('publicCategoryIds', product.public_categ_ids.ids)).exists()
            variant.bpi_effective_category_ids = [(6, 0, categories.ids)]
            variant.bpi_effective_search_identity = normalize(' '.join([
                product.name or '', product.bpi_brand_name or '', variant.default_code or '',
                *variant.product_template_attribute_value_ids.with_context(lang='es_ES').mapped('name'), *categories.with_context(lang='es_ES').mapped('name')]))
            short = overrides.get('description', product.bpi_ai_generated_description or product.description_sale or '')
            long = overrides.get('technicalDescription', product.bpi_technical_description or '')
            variant.bpi_effective_search_description = normalize(html2plaintext(short + ' ' + long))


class VariantSearchProduct(models.Model):
    _inherit = 'product.template'

    def _bpi_variant_search_active(self):
        return bool(request and getattr(request, 'website', None) and request.website.bpi_variant_content_enabled)

    @api.model
    def _bpi_effective_template_domain(self, variant_domain):
        variants = self.env['product.product'].search(expression.AND([[('active','=',True)], variant_domain]))
        return [('id', 'in', variants.product_tmpl_id.ids)]

    @api.model
    def _bpi_effective_category_domain(self, category_id):
        return self._bpi_effective_template_domain([('bpi_effective_category_ids', 'child_of', category_id)])

    @api.model
    def _bpi_query_domain(self, query, descriptions=False, identity_only=False):
        if not self._bpi_variant_search_active():
            return super()._bpi_query_domain(query, descriptions=descriptions, identity_only=identity_only)
        clauses = []
        for word, ids in self._bpi_query_units(query):
            choices = [expression.AND([[('bpi_effective_search_identity', '=like', '%' + escape_psql(part) + '%')]
                                       for part in word.split()])]
            if descriptions and not identity_only:
                choices.append([('bpi_effective_search_description', '=like', '%' + escape_psql(word) + '%')])
            if ids and not identity_only:
                choices.append([('bpi_effective_term_ids', 'in', ids)])
            clauses.append(expression.OR(choices))
        clauses.extend(self._bpi_variant_term_clauses(self.env.context.get('bpi_variant_term_ids', [])))
        if self.env.context.get('bpi_variant_category_id'):
            clauses.append([('bpi_effective_category_ids', 'child_of', self.env.context['bpi_variant_category_id'])])
        return self._bpi_effective_template_domain(expression.AND(clauses)) if clauses else []

    @api.model
    def _bpi_filter_domain(self, ids):
        if not self._bpi_variant_search_active():
            return super()._bpi_filter_domain(ids)
        clauses = self._bpi_variant_term_clauses(ids)
        return self._bpi_effective_template_domain(expression.AND(clauses)) if clauses else []

    @api.model
    def _bpi_variant_term_clauses(self, ids):
        terms = [t for t in self.env['bpi.taxonomy.term']._catalog() if t['id'] in ids]
        clauses = []
        for axis, _label in AXES:
            group = [t for t in terms if t['axis'] == axis]
            if group and not any(t['universal'] for t in group):
                clauses.append([('bpi_effective_term_ids', 'in', [t['id'] for t in group])])
        return clauses

    @api.model
    def _bpi_facets(self, domain, selected=None):
        if not self._bpi_variant_search_active():
            return super()._bpi_facets(domain, selected)
        # Aggregate only products the current reader can see. Count a product
        # once, even when multiple editions share the same term.
        products = self.search(domain)
        self.env['product.product'].flush_model(['bpi_effective_term_ids', 'active', 'product_tmpl_id'])
        self.env.cr.execute('SELECT r.term_id, count(DISTINCT p.product_tmpl_id) '
            'FROM bpi_variant_effective_term_rel r JOIN product_product p ON p.id=r.variant_id '
            'WHERE p.active AND p.product_tmpl_id=ANY(%s) GROUP BY r.term_id', [products.ids])
        counts = dict(self.env.cr.fetchall())
        return [{**{k:t[k] for k in ('id','axis','name','universal')},
                 'count':len(products) if t['universal'] else counts.get(t['id'],0),
                 'selected':t['id'] in (selected or [])} for t in self.env['bpi.taxonomy.term']._catalog()]

    @api.model
    def _search_get_detail(self, website, order, options):
        result = super()._search_get_detail(website, order, options)
        if website.bpi_variant_content_enabled:
            result['bpiTaxonomy'] = True
            result['fetch_fields'] = list(dict.fromkeys(result['fetch_fields'] + ['default_code']))
            result['bpiVariantTermIds'] = self._bpi_filter_ids(options.get('bpiTermIds'))
            result['bpiVariantCategoryId'] = False
            domains = []
            for domain in result['base_domain']:
                adapted = []
                for leaf in domain:
                    if isinstance(leaf, (tuple,list)) and len(leaf)==3 and leaf[0]=='public_categ_ids' and leaf[1]=='child_of':
                        result['bpiVariantCategoryId'] = leaf[2]
                        adapted.extend(self._bpi_effective_category_domain(leaf[2]))
                    else:
                        adapted.append(leaf)
                domains.append(adapted)
            result['base_domain'] = domains
        return result

    def _bpi_search_edition(self, query, website):
        self.ensure_one()
        if not website.bpi_variant_content_enabled or not query or not self._bpi_visible_documents(website):
            return self.env['product.product']
        text = normalize(query)
        words = [word for word, _ids in self._bpi_query_units(query)]
        common = set(normalize(self.name).split())
        ranked = []
        for variant in self.product_variant_ids:
            sku = normalize(variant.default_code or '')
            attributes = normalize(' '.join(variant.product_template_attribute_value_ids.mapped('name')))
            score = 3 if sku and text == sku else 2 if sku and words and all(w in sku for w in words) else 0
            if not score and words and any(w not in common and w in attributes for w in words) and all(w in attributes or w in common for w in words):
                score = 1
            if score:
                ranked.append((score, variant))
        if not ranked:
            return self.env['product.product']
        best = max(score for score, variant in ranked)
        matches = [variant for score, variant in ranked if score == best]
        return matches[0] if len(matches) == 1 and self._bpi_public_variant(website, matches[0].id) else self.env['product.product']

    @api.model
    def _search_fetch(self, search_detail, search, limit, order):
        scoped = self.with_context(bpi_variant_term_ids=search_detail.get('bpiVariantTermIds', []),
                                   bpi_variant_category_id=search_detail.get('bpiVariantCategoryId', False))
        products, count = super(VariantSearchProduct, scoped)._search_fetch(search_detail, search, limit, order)
        return products.with_context(bpi_variant_search_query=search or ''), count

    def _search_render_results(self, fetch_fields, mapping, icon, limit):
        result = super()._search_render_results(fetch_fields, mapping, icon, limit)
        website = self.env['website'].get_current_website()
        if not website.bpi_variant_content_enabled:
            return result
        query = self.env.context.get('bpi_variant_search_query', '')
        for product, data in zip(self, result):
            edition = product._bpi_search_edition(query, website)
            if not edition:
                continue
            projection = product._bpi_public_variant_content(website, edition.id)
            data.update(website_url=projection['url'], default_code=edition.default_code or '', name=projection['name'])
            if 'image_url' in mapping:
                data['image_url'] = projection['image']
            if 'detail' in mapping:
                combination = product._get_combination_info(combination=product._get_first_possible_combination(necessary_values=edition.product_template_attribute_value_ids),
                    product_id=edition.id, pricelist=website.get_current_pricelist())
                data['price'], base = product._search_render_results_prices(mapping, combination)
                if base:
                    data['list_price'] = base
                else:
                    data.pop('list_price', None)
        return result

    def _bpi_variant_shop_card(self, website, query, pricelist):
        edition = self._bpi_search_edition(query, website)
        if not edition:
            return False
        projection = self._bpi_public_variant_content(website, edition.id)
        combination = self._get_combination_info(combination=self._get_first_possible_combination(necessary_values=edition.product_template_attribute_value_ids),
            product_id=edition.id, pricelist=pricelist)
        prices = {'price_reduce':combination['price']}
        if combination['has_discounted_price']:
            prices['base_price'] = combination['list_price']
        return {'url':projection['url'], 'image':projection['image'], 'name':projection['name'], 'prices':prices}


class VariantSitemap(models.Model):
    _inherit = 'website'

    def _enumerate_pages(self, query_string=None, force=False):
        yield from super()._enumerate_pages(query_string=query_string, force=force)
        if not self.bpi_variant_content_enabled:
            return
        domain = expression.AND([self.sale_product_domain(), [('is_published','=',True), ('active','=',True)],
            ['|',('company_id','=',False),('company_id','=',self.company_id.id)]])
        products = self.env['product.template'].search(domain)
        for product in products:
            if 'website_indexed' in product._fields and not product.website_indexed:
                continue
            for edition in product.product_variant_ids:
                if not product._bpi_public_variant(self, edition.id):
                    continue
                url = '%s?variant=%s' % (product.website_url, edition.id)
                if not query_string or query_string.lower() in url.lower():
                    yield {'loc':url}


class VariantSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    bpi_variant_content_enabled = fields.Boolean(related='website_id.bpi_variant_content_enabled', readonly=False)
