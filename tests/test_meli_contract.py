# -*- coding: utf-8 -*-
from types import SimpleNamespace
from unittest.mock import patch

from odoo.exceptions import AccessError, MissingError, UserError
from odoo.tests.common import TransactionCase, tagged

from ..controllers.main import BaderProductIntelligenceController
from ..models.meli_provider import BPIMeliProvider


@tagged('-at_install', 'post_install')
class TestBPIMeliContract(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env['bpi.service']
        cls.category = cls.env['product.public.category'].create({'name': 'BPI ML Contract'})
        cls.products = cls.env['product.template'].create([
            {'name': 'BPI ML Contract %s' % i, 'sale_ok': True,
             'public_categ_ids': [(6, 0, cls.category.ids)]} for i in range(3)
        ])

    def _projection(self, products, account_id=False):
        result = BPIMeliProvider._meli_projection(self.service, products, account_id)
        result.update(available=True, state='available')
        for key in ('linked', 'published', 'review'):
            result['sets'][key] = set((products & self.products[:2]).ids)
        result['sets']['unlinked'] = set((products & self.products[2:]).ids)
        return result

    def test_base_provider_unavailable_never_fake_green(self):
        result = BPIMeliProvider._meli_projection(self.service, self.products)
        self.assertFalse(result['available'])
        self.assertEqual(result['state'], 'not_installed')
        self.assertEqual(self.service._meli_overview_payload(result, 3)['kpis'], [])
        self.assertTrue(all(not row['stockVerified'] for row in result['rows'].values()))

    def test_account_and_filter_validation(self):
        for value in (True, 0, -1, 'x', '1.2', [], {}, 1.5):
            with self.assertRaises(UserError):
                self.service._meli_account_key(value)
        for value in (True, 'not_a_filter', [], 1):
            with self.assertRaises(UserError):
                self.service._meli_filter_key(value)
        self.assertEqual(self.service._meli_account_key('2'), 2)
        self.assertFalse(self.service._meli_account_key(''))

    def test_kpi_to_catalog_matches_distinct_templates(self):
        with patch.object(type(self.service), '_meli_projection', self._projection):
            overview = self.service.dashboard_overview(category_id=self.category.id)
            self.assertEqual(len(overview['kpis']), 8)
            self.assertEqual(len(overview['meliOverview']['kpis']), 6)
            for metric in overview['meliOverview']['kpis']:
                catalog = self.service.dashboard_payload(category_id=self.category.id, meli_filter=metric['filter'])
                self.assertEqual(catalog['pager']['total'], metric['count'])
                self.assertEqual(metric['percent'], round(metric['count'] * 100 / 3, 1))
                self.assertEqual(catalog['meliFilter'], metric['filter'])
                self.assertNotIn('sets', catalog['meli'])
                self.assertNotIn('rows', catalog['meli'])

    def test_meli_filter_pagination_and_quality_composition(self):
        with patch.object(type(self.service), '_meli_projection', self._projection):
            payload = self.service.dashboard_payload(category_id=self.category.id, meli_filter='linked', limit=1, page=2)
            self.assertEqual(payload['pager']['total'], 2)
            self.assertEqual(len(payload['products']), 1)
            empty = self.service.dashboard_payload(category_id=self.category.id, meli_filter='linked', quality_filter='seo')
            self.assertEqual(empty['pager']['total'], 0)

    def test_filter_unavailable_raises_instead_of_empty(self):
        with patch.object(type(self.service), '_meli_projection', lambda model, products, account_id=False: BPIMeliProvider._meli_projection(self.service, products, account_id)):
            with self.assertRaises(UserError):
                self.service.dashboard_payload(category_id=self.category.id, meli_filter='linked')

    def test_empty_overview_percentages(self):
        category = self.env['product.public.category'].create({'name': 'Empty ML Scope'})
        with patch.object(type(self.service), '_meli_projection', self._projection):
            payload = self.service.dashboard_overview(category_id=category.id)
            self.assertEqual(payload['meliOverview']['total'], 0)
            self.assertTrue(all(k['count'] == 0 and k['percent'] == 0 for k in payload['meliOverview']['kpis']))

    def test_product_saved_health_and_meli_context(self):
        with patch.object(type(self.service), '_meli_projection', self._projection):
            payload = self.products[0].bpi_build_payload()
            self.assertEqual(payload['product']['catalogHealth']['total'], 7)
            self.assertIn('meliSummary', payload['product'])
            self.assertIn('meli', payload)
            self.assertNotIn('rows', payload['meli'])

    def test_controller_product_respects_selected_company(self):
        other = self.env['res.company'].create({'name': 'Other BPI Contract Company'})
        product = self.env['product.template'].create({'name': 'Other company product', 'company_id': other.id})
        env = self.env(context=dict(self.env.context, allowed_company_ids=self.env.company.ids))
        with patch('odoo.addons.bader_product_intelligence.controllers.main.request', SimpleNamespace(env=env)):
            with self.assertRaises(MissingError):
                BaderProductIntelligenceController()._product(product.id)

    def test_admin_required_for_all_monitoring_methods(self):
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'BPI ML Contract Reader', 'login': 'bpi_meli_contract_reader',
            'groups_id': [(6, 0, self.env.ref('base.group_user').ids)],
        })
        service = self.service.with_user(user)
        for call in (lambda: service.meli_detail(self.products[0].id),
                     lambda: service.meli_request_refresh(self.products[0].id),
                     lambda: service.meli_refresh_status(1)):
            with self.assertRaises(AccessError):
                call()

    def test_stale_optional_account_does_not_rollback_core_save(self):
        product = self.products[0]
        for error in (AccessError, UserError):
            with patch.object(type(self.service), '_meli_projection', side_effect=error('Unavailable account')):
                payload = self.service.update_product(product, {'sku': 'BPI-CORE-KEPT'})
                self.assertEqual(product.default_code, 'BPI-CORE-KEPT')
                self.assertFalse(payload['meli']['available'])
                self.assertEqual(payload['meli']['state'], 'no_access')
