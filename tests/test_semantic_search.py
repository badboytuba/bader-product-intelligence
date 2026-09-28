from unittest.mock import patch
from odoo.tests.common import TransactionCase, tagged


@tagged('-at_install', 'post_install')
class TestSemanticSearch(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Product = cls.env['product.template']
        cls.Term = cls.env['bpi.taxonomy.term']
        cls.audience = cls.Term.create({'name': 'Aprendices mapa', 'axis': 'niche', 'state': 'approved'})
        cls.commercial = cls.Term.create({'name': 'Utillaje mapa', 'axis': 'commercial', 'state': 'approved'})
        cls.product = cls.Product.create({'name': 'Producto semántico de prueba', 'default_code': 'MAP-DE-1'})
        cls.other = cls.Product.create({'name': 'Producto sin clasificar de prueba', 'default_code': 'MAP-DE-2'})
        cls.product.write({'bpi_taxonomy_term_ids': [(6, 0, [cls.audience.id, cls.commercial.id])]})

    def test_connectors_combine_approved_niche_and_application(self):
        query = '  Utillaje mapa PARA los aprendices mapa  '
        matches = self.Product.search(self.Product._bpi_query_domain(query))
        self.assertIn(self.product, matches)
        self.assertNotIn(self.other, matches)
        self.assertEqual(self.env['bpi.service']._dashboard_search_domain(query), self.Product._bpi_query_domain(query, descriptions=True))
        self.assertEqual(query, '  Utillaje mapa PARA los aprendices mapa  ')

    def test_all_connectors_do_not_become_unrestricted_query(self):
        self.assertEqual(self.Product._bpi_query_units('para de'), [('para', []), ('de', [])])
        self.assertTrue(self.Product._bpi_query_domain('para de'))
        self.assertEqual(self.Product._bpi_query_units('DE'), [('de', [])])

    def test_canonical_phrase_owns_its_connectors(self):
        term = self.Term.create({'name': 'Trabajo con guía mapa', 'axis': 'use', 'state': 'approved'})
        self.assertEqual(self.Product._bpi_query_units('trabajo con guía mapa'), [('trabajo con guia mapa', [term.id])])

    def test_negation_and_sku_are_not_removed(self):
        self.assertIn(('sin', []), self.Product._bpi_query_units('utillaje mapa sin látex'))
        self.assertEqual(self.Product._bpi_query_units('MAP-DE-1'), [('map-de-1', [])])
        domain = self.Product._bpi_query_domain('MAP-DE-1')
        self.assertEqual(self.Product._bpi_ranked_search(domain, 'MAP-DE-1', limit=1), self.product)

    def test_direct_name_precedes_category_only_match_before_pagination(self):
        category = self.env['product.public.category'].create({'name': 'Fres needle'})
        indirect = self.Product.create({'name': 'AAA contraángulo needle', 'public_categ_ids': [(6, 0, [category.id])]})
        direct = self.Product.create({'name': 'ZZZ Fresero needle'})
        domain = self.Product._bpi_query_domain('frés needle', descriptions=True)
        limited = [('id', 'in', (direct | indirect).ids)] + domain
        self.assertEqual(self.Product._bpi_ranked_search(limited, 'frés needle', limit=1), direct)
        self.assertEqual(self.Product._bpi_ranked_search(limited, 'frés needle', offset=1, limit=1), indirect)

    def test_normalized_contains_preserves_description_only_and_accents(self):
        self.other.description_sale = 'Aplicación única: caracterización protésica extraordinaria.'
        domain = self.Product._bpi_query_domain('  CARACTERIZACIÓN protésica ', descriptions=True)
        self.assertIn(self.other, self.Product.search(domain))
        self.assertNotIn(self.product, self.Product.search(domain))
        self.assertIn('=like', str(domain))
        self.assertFalse(self.Product._fields['bpi_search_description'].unaccent)

    def test_native_autocomplete_fetches_sku_without_changing_image_price_mapping(self):
        website = self.env['website'].search([], limit=1)
        website.bpi_taxonomy_search_enabled = True
        options = {'displayImage': True, 'displayDescription': False, 'displayDetail': True, 'displayExtraLink': False,
                   'display_currency': website.company_id.currency_id}
        detail = self.Product._search_get_detail(website, 'name asc', options)
        self.assertIn('default_code', detail['fetch_fields'])
        self.assertEqual(detail['mapping']['image_url']['name'], 'image_url')
        self.assertIn('detail', detail['mapping'])

    def test_displayed_name_translation_precedes_es_fallback_identity(self):
        self.env['res.lang']._activate_lang('es_AR')
        self.env['res.lang']._activate_lang('es_ES')
        wrong_title = self.Product.create({'name': 'AAA fresas mango needle'})
        wrong_title.with_context(lang='es_ES').name = 'AAA fresas mango needle'
        wrong_title.with_context(lang='es_AR').name = 'AAA Contraángulo needle'
        right_title = self.Product.create({'name': 'ZZZ Other needle'})
        right_title.with_context(lang='es_ES').name = 'ZZZ Other needle'
        right_title.with_context(lang='es_AR').name = 'ZZZ Fresero needle'
        model = self.Product.with_context(lang='es_AR')
        domain = [('id', 'in', (wrong_title | right_title).ids)] + model._bpi_query_domain('fres', descriptions=True)
        self.assertEqual(model._bpi_ranked_search(domain, 'fres', limit=1), right_title)
        self.assertEqual(model._bpi_ranked_search(domain, 'fres', offset=1, limit=1), wrong_title)
        self.assertIn(right_title, model.search(domain))
        compiled = model._where_calc([('bpi_search_description', '=like', '%fres%')]).get_sql()[1]
        self.assertNotIn('unaccent', compiled)

    def test_no_match_skips_all_ranking_scans(self):
        website = self.env['website'].search([], limit=1)
        website.bpi_taxonomy_search_enabled = True
        options = {'displayImage': False, 'displayDescription': False, 'displayDetail': False, 'displayExtraLink': False}
        detail = self.Product._search_get_detail(website, 'name', options)
        with patch.object(type(self.Product), '_bpi_ranked_search', side_effect=AssertionError('Empty search must not rank')):
            rows, count = self.Product._search_fetch(detail, 'unfindable-zz93827-needle', 8, 'name')
        self.assertFalse(rows)
        self.assertEqual(count, 0)
