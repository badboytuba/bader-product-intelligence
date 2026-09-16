# -*- coding: utf-8 -*-
import re
from odoo import api, fields, models, _
from odoo.osv import expression
from odoo.exceptions import ValidationError
from odoo.tools import html2plaintext
from .taxonomy import normalize, AXES


class SearchWebsite(models.Model):
    _inherit = 'website'
    bpi_taxonomy_search_enabled = fields.Boolean(string='BPI: búsqueda y clasificación integradas', default=False)


class SearchVariant(models.Model):
    _inherit = 'product.product'
    bpi_search_sku = fields.Char(compute='_compute_bpi_search_sku', store=True, index=True)

    @api.depends('default_code')
    def _compute_bpi_search_sku(self):
        for product in self:
            product.bpi_search_sku = normalize(product.default_code)


class SearchProduct(models.Model):
    _inherit = 'product.template'
    bpi_search_name = fields.Char(compute='_compute_bpi_search_identity', store=True, index=True)
    bpi_search_identity = fields.Text(compute='_compute_bpi_search_identity', store=True)
    bpi_search_description = fields.Text(compute='_compute_bpi_search_description', store=True)

    @api.depends('name', 'bpi_brand_name', 'public_categ_ids.name', 'product_variant_ids.default_code')
    def _compute_bpi_search_identity(self):
        for product in self:
            # Explicit Spanish context, independent of which user's write triggers recompute.
            localized = product.with_context(lang='es_ES')
            product.bpi_search_name = normalize(localized.name)
            product.bpi_search_identity = normalize(' '.join([localized.name or '', product.bpi_brand_name or ''] + product.public_categ_ids.with_context(lang='es_ES').mapped('name') + [v.default_code or '' for v in product.product_variant_ids]))

    @api.depends('description', 'description_sale', 'website_description')
    def _compute_bpi_search_description(self):
        for product in self:
            p = product.with_context(lang='es_ES')
            product.bpi_search_description = normalize(html2plaintext(' '.join([p.description or '', p.description_sale or '', p.website_description or ''])))

    @api.model
    def _bpi_filter_ids(self, value):
        if value in (None, False, ''):
            return []
        if isinstance(value, str):
            if len(value) > 1000 or not re.fullmatch(r'\d+(,\d+)*', value):
                raise ValidationError(_('Filtros de clasificación inválidos.'))
            value = [int(x) for x in value.split(',')]
        if not isinstance(value, list) or len(value) > 100 or any(type(i) is not int or i <= 0 for i in value):
            raise ValidationError(_('Filtros de clasificación inválidos.'))
        approved = {t['id'] for t in self.env['bpi.taxonomy.term']._catalog()}
        if set(value) - approved:
            raise ValidationError(_('El filtro contiene términos no disponibles.'))
        return sorted(set(value))

    @api.model
    def _bpi_filter_domain(self, ids):
        terms = [t for t in self.env['bpi.taxonomy.term']._catalog() if t['id'] in ids]
        domains = []
        for axis, unused in AXES:
            group = [t for t in terms if t['axis'] == axis]
            if group and not any(t['universal'] for t in group):
                domains.append([('bpi_taxonomy_term_ids', 'in', [t['id'] for t in group])])
        return expression.AND(domains)

    @api.model
    def _bpi_query_units(self, query):
        normalized = normalize(query)
        if len(normalized) > 200:
            raise ValidationError(_('La búsqueda admite hasta 200 caracteres.'))
        vocabulary = {}
        for term in self.env['bpi.taxonomy.term']._catalog():
            if not term['universal']:
                for word in [term['key']] + term['aliases']:
                    vocabulary.setdefault(word, []).append(term['id'])
        # Longest approved phrase wins; unmatched tokens still use literal identity matching.
        words = normalized.split(); units = []; index = 0
        while index < len(words):
            matched = False
            for end in range(len(words), index, -1):
                phrase = ' '.join(words[index:end])
                if phrase in vocabulary:
                    units.append((phrase, vocabulary[phrase])); index = end; matched = True; break
            if not matched:
                units.append((words[index], [])); index += 1
        # Connector words in natural multiword queries are not independent
        # product requirements. Match canonical phrases first so their own
        # connectors remain intact; never strip negation, SKU fragments, or
        # turn an all-connector query into an unrestricted catalog listing.
        connectors = {'de', 'del', 'la', 'el', 'los', 'las', 'para', 'en', 'con', 'y', 'un', 'una'}
        meaningful = [(word, ids) for word, ids in units if ids or word not in connectors]
        return meaningful if len(units) > 1 and meaningful else units

    @api.model
    def _bpi_query_domain(self, query, descriptions=False, identity_only=False):
        if not isinstance(query, str):
            raise ValidationError(_('La búsqueda debe ser texto.'))
        domains = []
        for word, ids in self._bpi_query_units(query):
            choices = [expression.AND([[('bpi_search_identity', 'ilike', part)] for part in word.split()])]
            if descriptions and not identity_only:
                choices.append([('bpi_search_description', 'ilike', word)])
            if ids and not identity_only:
                choices.append([('bpi_taxonomy_term_ids', 'in', ids)])
            domains.append(expression.OR(choices))
        return expression.AND(domains)

    @api.model
    def _bpi_ranked_search(self, domain, query, offset=0, limit=None, order='name, id'):
        if not normalize(query):
            return self.search(domain, offset=offset, limit=limit, order=order)
        term = normalize(query)
        tiers = [[('product_variant_ids.bpi_search_sku', '=', term)], [('bpi_search_name', '=', term)],
                 self._bpi_query_domain(query, identity_only=True), []]
        result = self.browse(); previous = []
        for tier in tiers:
            current = expression.AND([domain, tier] + ([['!'] + expression.OR(previous)] if previous else []))
            if offset:
                count = self.search_count(current)
                if offset >= count:
                    offset -= count; previous.append(tier); continue
            remaining = limit - len(result) if limit else None
            result |= self.search(current, offset=offset, limit=remaining, order=order)
            offset = 0
            if limit and len(result) >= limit:
                break
            previous.append(tier)
        return result

    @api.model
    def _bpi_facets(self, domain, selected=None):
        # One aggregate over eligible IDs, including product ACL/company/website constraints.
        self.check_access_rights('read')
        self.flush_model()
        query = self._where_calc(domain)
        self._apply_ir_rules(query, 'read')
        from_clause, where, params = query.get_sql()
        self.env.cr.execute('SELECT rel.term_id, count(DISTINCT rel.product_id) FROM bpi_product_taxonomy_rel rel '
                            'WHERE rel.product_id IN (SELECT product_template.id FROM ' + from_clause +
                            (' WHERE ' + where if where else '') + ') GROUP BY rel.term_id', params)
        counts = dict(self.env.cr.fetchall())
        total = self.search_count(domain)
        selected = selected or []
        return [{**{k:t[k] for k in ('id','axis','name','universal')},
                 'count':total if t['universal'] else counts.get(t['id'],0), 'selected':t['id'] in selected}
                for t in self.env['bpi.taxonomy.term']._catalog()]

    @api.model
    def _search_get_detail(self, website, order, options):
        detail = super()._search_get_detail(website, order, options)
        if website.bpi_taxonomy_search_enabled:
            ids = self._bpi_filter_ids(options.get('bpiTermIds'))
            detail['base_domain'].extend([self._bpi_filter_domain(ids), [('is_published','=',True),('active','=',True),('sale_ok','=',True)],
                ['|', ('company_id', '=', False), ('company_id', '=', website.company_id.id)]])
            detail['bpiTaxonomy'] = True
        return detail

    @api.model
    def _search_fetch(self, search_detail, search, limit, order):
        if not search_detail.get('bpiTaxonomy'):
            return super()._search_fetch(search_detail, search, limit, order)
        domain = expression.AND(search_detail['base_domain'] + [self._bpi_query_domain(search or '', descriptions=True)])
        results = self._bpi_ranked_search(domain, search or '', limit=limit, order=search_detail.get('order', order))
        return results, self.search_count(domain)


class SearchService(models.AbstractModel):
    _inherit = 'bpi.service'

    @api.model
    def _dashboard_search_domain(self, search):
        return self.env['product.template']._bpi_query_domain(search or '', descriptions=True)
