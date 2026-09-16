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
