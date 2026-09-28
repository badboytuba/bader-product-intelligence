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
        self.assertNotIn('ilike', str(domain))

    def test_native_autocomplete_fetches_sku_without_changing_image_price_mapping(self):
        website = self.env['website'].search([], limit=1)
        website.bpi_taxonomy_search_enabled = True
        options = {'displayImage': True, 'displayDescription': False, 'displayDetail': True, 'displayExtraLink': False,
                   'display_currency': website.company_id.currency_id}
        detail = self.Product._search_get_detail(website, 'name asc', options)
        self.assertIn('default_code', detail['fetch_fields'])
        self.assertEqual(detail['mapping']['image_url']['name'], 'image_url')
        self.assertIn('detail', detail['mapping'])
