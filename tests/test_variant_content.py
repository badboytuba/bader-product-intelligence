from unittest.mock import patch

from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('-at_install', 'post_install')
class TestVariantContent(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env['bpi.service']
        cls.profiles = cls.env['bpi.variant.content']
        attribute = cls.env['product.attribute'].create({'name': 'Edición BPI test'})
        values = cls.env['product.attribute.value'].create([
            {'name': name, 'attribute_id': attribute.id} for name in ('High', 'Starter')])
        cls.product = cls.env['product.template'].create({'name': 'Unidad BPI', 'list_price': 200,
            'bpi_ai_generated_description': '<p>Contenido común</p>',
            'bpi_technical_description': '<p>Detalle común</p>',
            'attribute_line_ids': [(0, 0, {'attribute_id': attribute.id, 'value_ids': [(6, 0, values.ids)]})]})
        cls.high, cls.starter = cls.product.product_variant_ids.sorted('id')
        cls.high.default_code = 'BPI-HIGH'
        cls.starter.default_code = 'BPI-STARTER'
        cls.other = cls.env['product.template'].create({'name': 'Otro producto BPI'})
        cls.user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Variant reader', 'login': 'bpi_variant_reader',
            'groups_id': [(6, 0, cls.env.ref('base.group_user').ids)]})
        cls.pricelist = cls.env['product.pricelist'].create({'name': 'Tarifa BPI variantes',
            'currency_id': cls.env.company.currency_id.id})

    def scope(self, variant=None):
        return self.product._bpi_resolve_variant((variant or self.high).id)

    def save(self, changes=None, inherit=None, variant=None, scope=None):
        variant = variant or self.high
        current = scope or self.scope(variant)
        return self.profiles._save(self.product, variant.id, changes or {}, inherit or [],
                                   current['baseRevision'], current['revision'], context_revision=current['contextRevision'])

    def test_read_inherits_without_creating_profile(self):
        data = self.scope()
        self.assertEqual(data['revision'], 0)
        self.assertEqual(data['overridden'], [])
        self.assertEqual(data['values']['description'], '<p>Contenido común</p>')
        self.assertFalse(self.profiles.search([('product_id', '=', self.high.id)]))

    def test_override_does_not_touch_template_or_sibling(self):
        before = (self.product.write_date, self.product.bpi_editorial_revision, self.product.list_price)
        self.save({'description': '<p>Solo High</p>', 'seoTitle': 'High Edition'})
        self.assertEqual(self.scope()['values']['description'], '<p>Solo High</p>')
        self.assertEqual(self.scope(self.starter)['values']['description'], '<p>Contenido común</p>')
        self.assertEqual(before, (self.product.write_date, self.product.bpi_editorial_revision, self.product.list_price))

    def test_empty_is_not_inherit(self):
        self.save({'description': '', 'faqs': [], 'seoTitle': ''})
        self.assertEqual(self.scope()['values']['description'], '')
        self.assertIn('description', self.scope()['overridden'])
        self.save(inherit=['description'])
        self.assertEqual(self.scope()['values']['description'], '<p>Contenido común</p>')
        self.assertIn('seoTitle', self.scope()['overridden'])

    def test_variant_checklist_uses_effective_saved_content_not_common_scores(self):
        self.product.write({'website_meta_title': 'Título común',
                            'website_meta_description': 'Descripción común', 'bpi_seo_score': 99})
        self.save({'description': '', 'technicalDescription': '', 'gallery': [],
                   'seoTitle': '', 'faqs': [], 'publicCategoryIds': []})
        data = self.product.bpi_build_variant_payload(self.high.id)
        for key in ('commercial', 'technical', 'image', 'seo', 'faq', 'category'):
            self.assertFalse(data['product']['catalogHealth'][key], key)
        self.assertIsNone(data['seoData']['seoScore'])
        sibling = self.product.bpi_build_variant_payload(self.starter.id)
        self.assertTrue(sibling['product']['catalogHealth']['commercial'])
        self.assertTrue(sibling['product']['catalogHealth']['technical'])
        self.assertTrue(sibling['product']['catalogHealth']['seo'])

    def test_base_updates_propagate_only_to_inherited_fields(self):
        self.save({'description': '<p>High propia</p>'})
        self.product.write({'bpi_ai_generated_description': '<p>Nueva base</p>', 'bpi_technical_description': '<p>Nuevo detalle</p>'})
        self.assertEqual(self.scope()['values']['description'], '<p>High propia</p>')
        self.assertEqual(self.scope()['values']['technicalDescription'], '<p>Nuevo detalle</p>')
        self.assertEqual(self.scope(self.starter)['values']['description'], '<p>Nueva base</p>')

    def test_stale_variant_and_base_rejected(self):
        stale = self.scope()
        self.save({'seoTitle': 'Uno'})
        with self.assertRaises(UserError):
            self.save({'seoTitle': 'Dos'}, scope=stale)
        stale = self.scope()
        self.product.write({'bpi_technical_description': '<p>Actualizado</p>'})
        with self.assertRaises(UserError):
            self.save({'seoTitle': 'Tres'}, scope=stale)
        self.assertEqual(self.scope()['values']['seoTitle'], 'Uno')

    def test_noop_preserves_profile_revision(self):
        self.save({'seoTitle': 'High'})
        before = self.scope()
        self.save({'seoTitle': 'High'})
        self.assertEqual(before, self.scope())

    def test_strict_identity_and_revision_types(self):
        for value in (True, '1', 0, -1):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.product._bpi_resolve_variant(value)
        with self.assertRaises(MissingError):
            self.product._bpi_resolve_variant(self.other.product_variant_id.id)
        with self.assertRaises(ValidationError):
            self.profiles._save(self.product, self.high.id, {}, [], True, 0)

    def test_unknown_fields_atomic_and_ownership(self):
        for values in ({'list_price': 1}, {'name': 'Otro SKU'}, {'categ_id': 1},
                       {'gallery': ['variant:%s' % self.other.product_variant_id.id]},
                       {'classification': {'termIds': [True]}}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                self.save(dict(values, seoTitle='No guardar'))
        self.assertEqual(self.scope()['revision'], 0)

    def test_ambiguous_inheritance_rejected(self):
        with self.assertRaises(ValidationError):
            self.save({'seoTitle': 'High'}, ['seoTitle'])

    def test_html_and_links_sanitized(self):
        self.save({'description': '<p onclick="alert(1)">Texto</p><script>alert(1)</script><iframe src="https://evil.invalid"/>'})
        value = self.scope()['values']['description']
        self.assertNotIn('<script', value)
        self.assertNotIn('<iframe', value)
        self.assertNotIn('onclick', value)

    def test_regeneration_preserves_layout(self):
        layout = {'version': 1, 'enabled': True, 'blocks': [{'id': 'principal', 'type': 'main'},
            {'id': 'extra', 'type': 'text', 'html': '<p>Complemento</p>'}]}
        self.save({'descriptionLayout': layout})
        before = self.scope()['values']['descriptionLayout']
        self.save({'technicalDescription': '<p>Nuevo principal</p>'})
        self.assertEqual(before, self.scope()['values']['descriptionLayout'])

    def test_direct_orm_and_non_manager_are_blocked(self):
        with self.assertRaises(AccessError):
            self.profiles.create({'product_id': self.high.id})
        with self.assertRaises(AccessError):
            self.product.with_user(self.user)._bpi_resolve_variant(self.high.id)
        record = self.save({'seoTitle': 'High'})
        with self.assertRaises(AccessError):
            record.write({'overrides': {}})

    def test_payload_and_legacy_isolation(self):
        self.save({'description': '<p>High</p>', 'seoTitle': 'SEO High', 'faqs': [{'question': '¿Modelo?', 'answer': 'High'}]})
        data = self.product.bpi_build_variant_payload(self.high.id)
        self.assertEqual(data['variantContent']['variantId'], self.high.id)
        self.assertEqual(data['product']['sku'], 'BPI-HIGH')
        self.assertEqual(data['seoData']['seoTitle'], 'SEO High')
        self.assertEqual(data['seoData']['geoFaq'][0]['answer'], 'High')
        self.assertNotIn('variantContent', self.product.bpi_build_payload())
        self.assertEqual(self.product.bpi_build_payload()['seoData']['aiGeneratedDescriptionHtml'], '<p>Contenido común</p>')

    def test_no_provider_call_on_read_save(self):
        with patch.object(type(self.service), '_openai_request', side_effect=AssertionError('No paid calls')):
            self.save({'seoTitle': 'High'})
            self.product.bpi_build_variant_payload(self.high.id)

    def pricing(self, variant=None):
        return self.service.variant_pricing(self.product, (variant or self.high).id, self.pricelist.id)

    def test_native_fixed_price_only_target_variant(self):
        before = self.pricing()
        result = self.service.save_variant_pricing(self.product, self.high.id, self.pricelist.id,
            before['revision'], {'compute_price': 'fixed', 'fixed_price': 125})
        self.assertEqual(result['price'], 125)
        self.assertTrue(result['ruleIsVariantSpecific'])
        self.assertEqual(self.pricing(self.starter)['price'], 200)
        self.assertEqual(self.product.list_price, 200)

    def test_customer_currency_and_advanced_native_rule_remain_native(self):
        currency = self.env.ref('base.EUR')
        currency.active = True
        customer_list = self.env['product.pricelist'].create({
            'name': 'Cliente EUR variantes', 'currency_id': currency.id})
        customer = self.env['res.partner'].create({
            'name': 'Cliente de prueba variantes', 'property_product_pricelist': customer_list.id})
        rule = self.env['product.pricelist.item'].create({
            'pricelist_id': customer_list.id, 'applied_on': '0_product_variant',
            'product_id': self.high.id, 'compute_price': 'fixed', 'fixed_price': 81.25})
        data = self.service.variant_pricing(self.product, self.high.id, customer.property_product_pricelist.id)
        self.assertEqual(data['currency'], 'EUR')
        self.assertEqual(data['price'], 81.25)
        self.assertEqual(data['ruleId'], rule.id)
        self.assertEqual(self.pricing()['price'], 200)
        rule.write({'compute_price': 'formula', 'base': 'pricelist',
                    'base_pricelist_id': self.pricelist.id, 'price_discount': 0.1})
        data = self.service.variant_pricing(self.product, self.high.id, customer_list.id, quantity=3)
        self.assertAlmostEqual(data['price'], customer_list._get_product_price(self.high, 3))
        self.assertFalse(data['rules'][0]['editable'])
        with self.assertRaises(ValidationError):
            self.service.save_variant_pricing(self.product, self.high.id, customer_list.id,
                data['revision'], {'fixed_price': 1}, rule_id=rule.id)
        self.save({'description': '<p>Ficha sin cambios comerciales</p>'})
        self.assertEqual(rule.compute_price, 'formula')
        self.assertEqual(customer.property_product_pricelist, customer_list)

    def test_multi_attribute_variant_url_resolves_complete_native_combination(self):
        color = self.env['product.attribute'].create({'name': 'Color de prueba'})
        colors = self.env['product.attribute.value'].create([
            {'name': name, 'attribute_id': color.id} for name in ('Azul', 'Blanco')])
        self.product.write({'attribute_line_ids': [(0, 0, {
            'attribute_id': color.id, 'value_ids': [(6, 0, colors.ids)]})]})
        website = self.env['website'].search([], limit=1)
        website.bpi_variant_content_enabled = True
        self.product.write({'website_id': website.id, 'is_published': True})
        self.assertEqual(len(self.product.product_variant_ids), 4)
        for variant in self.product.product_variant_ids:
            self.assertEqual(len(variant.product_template_attribute_value_ids), 2)
            self.assertEqual(self.product._bpi_public_variant(website, variant.id), variant)
            scoped = self.product.with_context(bpi_public_variant_id=variant.id, bpi_public_template_id=self.product.id)
            self.assertEqual(scoped._get_variant_for_combination(scoped._get_first_possible_combination()), variant)

    def test_price_stale_save_and_delete(self):
        before = self.pricing()
        result = self.service.save_variant_pricing(self.product, self.high.id, self.pricelist.id,
            before['revision'], {'fixed_price': 125})
        with self.assertRaises(UserError):
            self.service.save_variant_pricing(self.product, self.high.id, self.pricelist.id,
                before['revision'], {'fixed_price': 999})
        result = self.service.save_variant_pricing(self.product, self.high.id, self.pricelist.id,
            result['revision'], rule_id=result['rules'][0]['id'], delete=True)
        self.assertEqual(result['price'], 200)

    def test_general_rules_are_not_editable_by_variant(self):
        rule = self.env['product.pricelist.item'].create({'pricelist_id': self.pricelist.id,
            'applied_on': '3_global', 'compute_price': 'fixed', 'fixed_price': 150})
        data = self.pricing()
        self.assertFalse(data['ruleIsVariantSpecific'])
        with self.assertRaises(ValidationError):
            self.service.save_variant_pricing(self.product, self.high.id, self.pricelist.id,
                data['revision'], {'fixed_price': 1}, rule_id=rule.id)
        self.assertEqual(rule.fixed_price, 150)

    def test_price_validation_no_partial_rule(self):
        for values in ({'fixed_price': -1}, {'fixed_price': float('nan')}, {'fixed_price': True},
                       {'percent_price': 110}, {'date_start': '2030-01-02', 'date_end': '2029-01-01'},
                       {'product_id': self.starter.id}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                self.service.save_variant_pricing(self.product, self.high.id, self.pricelist.id,
                    self.pricing()['revision'], values)
        self.assertEqual(self.pricing()['rules'], [])

    def test_quantity_and_date_use_native_precedence(self):
        result = self.service.save_variant_pricing(self.product, self.high.id, self.pricelist.id,
            self.pricing()['revision'], {'fixed_price': 80, 'min_quantity': 10,
                'date_start': '2030-01-01', 'date_end': '2030-12-31'})
        self.assertEqual(result['price'], 200)
        self.assertEqual(self.service.variant_pricing(self.product, self.high.id, self.pricelist.id, 10, '2030-06-01')['price'], 80)
        self.assertEqual(self.service.variant_pricing(self.product, self.high.id, self.pricelist.id, 1, '2030-06-01')['price'], 200)

    def test_content_save_does_not_write_prices(self):
        before = self.pricing()
        self.save({'description': '<p>Descripción</p>'})
        after = self.pricing()
        self.assertEqual(before['revision'], after['revision'])
        self.assertEqual(before['price'], after['price'])

    def test_studio_sessions_are_scoped_and_resumable(self):
        common = self.service._studio_open(self.product.id)
        high_service = self.service.with_context(bpi_product_variant_id=self.high.id)
        high = high_service._studio_open(self.product.id)
        starter = self.service.with_context(bpi_product_variant_id=self.starter.id)._studio_open(self.product.id)
        self.assertEqual(len({common['session']['id'], high['session']['id'], starter['session']['id']}), 3)
        self.assertEqual(high_service._studio_open(self.product.id)['session']['id'], high['session']['id'])
        self.assertEqual([s['id'] for s in high['sessions']], [high['session']['id']])
        with self.assertRaises(MissingError):
            high_service._studio_session(self.product.id, starter['session']['id'])
        with self.assertRaises(MissingError):
            self.service._studio_session(self.product.id, high['session']['id'])

    def test_studio_variant_identity_is_immutable(self):
        session_id = self.service.with_context(bpi_product_variant_id=self.high.id)._studio_open(self.product.id)['session']['id']
        session = self.env['bpi.content.studio.session'].browse(session_id)
        with self.assertRaises(ValidationError):
            session.write({'product_variant_id': self.starter.id})
        with self.assertRaises(MissingError):
            self.env['bpi.content.studio.session'].create({'product_tmpl_id': self.product.id,
                'product_variant_id': self.other.product_variant_id.id})

    def test_studio_snapshot_contains_only_selected_facts_and_copy(self):
        self.save({'description': '<p>High específica</p>'})
        self.env['bpi.product.specification']._save_rows(self.product, [
            {'variantId': self.high.id, 'revision': 0, 'values': {'length': 10, 'weight': 100}},
            {'variantId': self.starter.id, 'revision': 0, 'values': {'length': 20}},
        ])
        self.high.weight = 9
        service = self.service.with_context(bpi_product_variant_id=self.high.id)
        session = self.env['bpi.content.studio.session'].browse(service._studio_open(self.product.id)['session']['id'])
        data = session._snapshot()['data']
        self.assertEqual(data['sku'], self.high.default_code)
        self.assertEqual(data['savedCopyNotEvidence']['short'], '<p>High específica</p>')
        self.assertNotIn(self.starter.default_code, data['variantsAndPacks'])
        self.assertNotIn('20 cm', [f['value'] for f in data['facts']])
        self.assertNotIn('9 kg', [f['value'] for f in data['facts']])
        self.assertIn('10 cm', [f['value'] for f in data['facts']])
        self.assertIn('100 g', [f['value'] for f in data['facts']])
        self.assertNotIn('Starter', [f['value'] for f in data['facts']])

    def test_variant_edit_invalidates_its_studio_snapshot(self):
        service = self.service.with_context(bpi_product_variant_id=self.high.id)
        session = self.env['bpi.content.studio.session'].browse(service._studio_open(self.product.id)['session']['id'])
        before = session._snapshot()
        self.save({'seoTitle': 'Nuevo título'})
        with self.assertRaises(UserError):
            session._assert_snapshot(before, session.revision)

    def test_saved_specs_invalidate_editor_context(self):
        before = self.scope()
        self.env['bpi.product.specification']._save_rows(self.product, [
            {'variantId': self.high.id, 'revision': 0, 'values': {'length': 11}}])
        with self.assertRaises(UserError):
            self.save({'technicalDescription': '<p>Texto anterior</p>'}, scope=before)
        self.assertEqual(self.scope()['revision'], 0)

    def test_variant_context_cannot_write_shared_fields(self):
        with self.assertRaises(ValidationError):
            self.product.with_context(bpi_product_variant_id=self.high.id).write({'list_price': 1})
        self.assertEqual(self.product.list_price, 200)

    def test_variant_documents_inherit_without_copy_until_explicit_save(self):
        from ..models.product_documents import empty_panel
        documents = self.env['bpi.product.document.panel']
        panel = empty_panel()
        panel.update(title='Catálogo común')
        panel['buttons'][0].update(label='Manual', url='https://example.com/manual.pdf')
        documents._save_panel(self.product, panel)
        self.assertEqual(documents.search_count([('product_id','=',self.product.id)]), 1)
        inherited = self.scope()['values']['documents']
        self.assertEqual(inherited['title'], 'Catálogo común')
        inherited['title'] = 'Catálogo High'
        self.save({'documents': inherited})
        self.assertEqual(self.scope()['values']['documents']['title'], 'Catálogo High')
        common = documents.search([('product_id','=',self.product.id), ('product_variant_id','=',False)])
        self.assertEqual(common.title, 'Catálogo común')
        self.assertEqual(self.product._bpi_resolve_variant(self.starter.id)['values']['documents']['title'], 'Catálogo común')
        self.save({}, inherit=['documents'])
        self.assertEqual(self.scope()['values']['documents']['title'], 'Catálogo común')
        self.assertEqual(documents.search_count([('product_id','=',self.product.id)]), 2, 'history panel retained privately')

    def test_variant_documents_empty_is_explicit_and_concurrent_edits_rejected(self):
        from ..models.product_documents import empty_panel
        self.save({'documents': empty_panel()})
        first = self.scope()
        docs = first['values']['documents']
        self.assertIn('documents', first['overridden'])
        docs['title'] = 'Solo High'
        self.save({'documents': docs})
        self.assertGreater(self.scope()['revision'], first['revision'])
        with self.assertRaises(UserError):
            self.save({'documents': docs}, scope=first)
        for malformed in (True, None, [], 'bad'):
            with self.subTest(malformed=malformed), self.assertRaises(ValidationError):
                self.save({'documents': malformed})

    def public_fixture(self):
        website = self.env['website'].create({'name':'Variant public test', 'bpi_variant_content_enabled':True})
        self.product.write({'is_published':True, 'website_id':website.id})
        return website

    def test_public_variant_projection_uses_effective_copy_and_not_private_data(self):
        website = self.public_fixture()
        self.save({'description':'<p>Solo High</p>', 'seoTitle':'High SEO', 'faqs':[{'question':'¿Edición?', 'answer':'High'}]})
        public = self.product.with_user(website.user_id).with_context(website_id=website.id)
        result = public._bpi_public_variant_content(website, self.high.id)
        self.assertEqual(str(result['short']), '<p>Solo High</p>')
        self.assertEqual(result['title'], 'High SEO')
        self.assertNotIn('overrides', result)
        self.assertNotIn('baseValues', result)
        self.assertNotIn('contextRevision', result)
        self.assertNotIn('sources', result)
        with self.assertRaises(AccessError):
            self.profiles.with_user(website.user_id).search([])
        self.assertEqual(str(public._bpi_public_variant_content(website, self.starter.id)['short']), '<p>Contenido común</p>')

    def test_public_variant_rejects_wrong_product_archived_and_other_website(self):
        website = self.public_fixture()
        self.assertFalse(self.product._bpi_public_variant_content(website, self.other.product_variant_id.id))
        self.assertFalse(self.product._bpi_public_variant_content(website, True))
        self.high.active = False
        self.assertFalse(self.product._bpi_public_variant_content(website, self.high.id))
        second = self.env['website'].create({'name':'Another variant site','bpi_variant_content_enabled':True})
        self.assertFalse(self.product._bpi_public_variant_content(second, self.starter.id))
        website.bpi_variant_content_enabled = False
        self.assertFalse(self.product._bpi_public_variant_content(website, self.starter.id))

    def test_public_layout_references_single_effective_long_text(self):
        from ..models.description_layout import empty_layout
        website = self.public_fixture()
        layout = empty_layout(); layout['enabled'] = True
        self.save({'technicalDescription':'<p>Detalle High</p>', 'descriptionLayout':layout})
        result = self.product._bpi_public_variant_content(website, self.high.id)
        self.assertEqual(str(result['layout']['blocks'][0]['mainHtml']), '<p>Detalle High</p>')
        rendered = str(self.env['ir.ui.view']._render_template('bader_product_intelligence.variant_editorial',
            {'product':self.product,'website':website,'bpi_variant_public':result}))
        self.assertIn('Detalle High', rendered)
        self.assertNotIn('Detalle común', rendered)

    def test_query_variant_initial_combination_uses_native_identity(self):
        product = self.product.with_context(bpi_public_variant_id=self.starter.id, bpi_public_template_id=self.product.id)
        self.assertEqual(product._get_variant_for_combination(product._get_first_possible_combination()), self.starter)
        self.assertEqual(self.product._get_variant_for_combination(self.product._get_first_possible_combination()), self.high)

    def test_variant_search_unique_sku_or_edition_never_guesses_ambiguous(self):
        website = self.public_fixture()
        self.assertEqual(self.product._bpi_search_edition('BPI-STARTER', website), self.starter)
        self.assertEqual(self.product._bpi_search_edition('Unidad High', website), self.high)
        self.assertFalse(self.product._bpi_search_edition('Unidad', website))
        self.assertFalse(self.product._bpi_search_edition('BPI', website))
        website.bpi_variant_content_enabled = False
        self.assertFalse(self.product._bpi_search_edition('BPI-STARTER', website))

    def test_feature_defaults_off_and_copy_does_not_opt_in(self):
        website = self.env['website'].create({'name':'Off by default'})
        self.assertFalse(website.bpi_variant_content_enabled)
        website.bpi_variant_content_enabled = True
        self.assertFalse(website.copy({'name':'Copy without activation'}).bpi_variant_content_enabled)

    def test_template_only_generation_cannot_charge_or_write_for_variant(self):
        service = self.service.with_context(bpi_product_variant_id=self.high.id)
        with patch.object(type(service), '_openai_response', side_effect=AssertionError('No paid request')):
            for method, args in [('generate_content', []), ('generate_faq', []),
                                 ('analyze_seo', ['clinicas']), ('chat_with_product', ['Hola'])]:
                with self.subTest(method=method), self.assertRaises(ValidationError):
                    getattr(service, method)(self.product, *args)
        self.assertFalse(self.profiles.search([('product_id','=',self.high.id)]))

    def test_variant_pack_save_updates_only_selected_native_composition(self):
        self.product.write({'pack_ok':True, 'pack_type':'detailed', 'pack_component_price':'ignored', 'pack_modifiable':False})
        for variant in (self.high, self.starter):
            variant.write({'pack_line_ids':[(0,0,{'product_id':self.other.product_variant_id.id,'quantity':1})]})
        service = self.service.with_context(bpi_product_variant_id=self.high.id)
        pack = self.product.bpi_build_variant_payload(self.high.id)['pack']
        self.assertEqual([row['variantId'] for row in pack['compositions']], [self.high.id])
        values = {'packType':pack['packType'], 'componentPriceMode':pack['componentPriceMode'], 'modifiable':pack['modifiable'],
            'compositions':[{'variantId':self.high.id,'components':[{'lineId':self.high.pack_line_ids.id,
                'productVariantId':self.other.product_variant_id.id, 'quantity':3,'saleDiscount':0}]}]}
        data = service.update_pack(self.product.with_env(service.env), pack['revision'], values)
        self.assertEqual(self.high.pack_line_ids.quantity, 3)
        self.assertEqual(self.starter.pack_line_ids.quantity, 1)
        self.assertEqual(data['variantContent']['variantId'], self.high.id)
        values['packType'] = 'non_detailed'
        with self.assertRaises(UserError):
            service.update_pack(self.product.with_env(service.env), self.product._bpi_pack_revision(), values)

    def test_effective_search_index_recomputes_overrides_empty_and_inheritance(self):
        category = self.env['product.public.category'].create({'name':'Cirugía edición High'})
        self.save({'description':'<p>Contenido magnético específico</p>', 'publicCategoryIds':[category.id]})
        self.assertIn('magnetico', self.high.bpi_effective_search_description)
        self.assertNotIn('magnetico', self.starter.bpi_effective_search_description)
        self.assertEqual(self.high.bpi_effective_category_ids, category)
        self.save({'description':'', 'publicCategoryIds':[]})
        self.assertNotIn('contenido comun', self.high.bpi_effective_search_description)
        self.assertFalse(self.high.bpi_effective_category_ids)
        self.save(inherit=['description'])
        self.product.bpi_ai_generated_description = '<p>Base actualizada</p>'
        self.assertIn('base actualizada', self.high.bpi_effective_search_description)
        self.assertIn('base actualizada', self.starter.bpi_effective_search_description)

    def test_effective_taxonomy_search_and_distinct_facets(self):
        catalog = self.env['bpi.taxonomy.term']._catalog()
        term = next(t for t in catalog if not t['universal'])
        self.save({'classification':{'termIds':[term['id']], 'excludedTermIds':[]}})
        self.save({'classification':{'termIds':[term['id']], 'excludedTermIds':[]}}, variant=self.starter)
        model = self.env['product.template']
        with patch.object(type(model), '_bpi_variant_search_active', return_value=True):
            domain = model._bpi_filter_domain([term['id']])
            self.assertIn(self.product, model.search(domain))
            facet = next(t for t in model._bpi_facets([('id','=',self.product.id)]) if t['id']==term['id'])
            self.assertEqual(facet['count'], 1)
            self.save({'classification':{'termIds':[], 'excludedTermIds':[]}}, variant=self.high)
            self.starter.active = False
            self.assertNotIn(self.product, model.search(model._bpi_filter_domain([term['id']])))

    def test_effective_query_cannot_mix_two_variant_identities(self):
        model = self.env['product.template']
        with patch.object(type(model), '_bpi_variant_search_active', return_value=True):
            self.assertIn(self.product, model.search(model._bpi_query_domain('Unidad Starter')))
            self.assertNotIn(self.product, model.search(model._bpi_query_domain('High Starter')))
            self.save({'description':'<p>Palabraúnica</p>'})
            self.assertIn(self.product, model.search(model._bpi_query_domain('palabraunica', descriptions=True)))
            self.assertNotIn(self.product, model.search(model._bpi_query_domain('palabraunica', identity_only=True)))

    def test_native_variant_extra_gallery_order_and_private_references(self):
        png = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
        self.product.image_1920 = png
        own = self.env['product.image'].create({'name':'High detalle','product_variant_id':self.high.id,'image_1920':png})
        common = self.env['product.image'].create({'name':'Común detalle','product_tmpl_id':self.product.id,'image_1920':png})
        self.assertEqual(self.scope()['values']['gallery'], ['main', 'odoo:%s'%own.id, 'odoo:%s'%common.id])
        self.assertEqual(self.scope(self.starter)['values']['gallery'], ['main', 'odoo:%s'%common.id])
        self.save({'gallery':['odoo:%s'%own.id]})
        payload = self.product.bpi_build_variant_payload(self.high.id)
        self.assertEqual(len(payload['images']), 1)
        self.assertEqual([r['token'] for r in payload['product']['referenceImages']], ['odoo:%s'%own.id])
        self.assertEqual(payload['product']['alternativeImages'], [])
        private = self.env['bpi.product.image'].create({'name':'Privada', 'product_tmpl_id':self.product.id,'image_1920':png,'state':'approved'})
        website = self.public_fixture()
        self.assertFalse(self.product._bpi_public_gallery_reference(website, self.high.id, private.id))
        self.save({'gallery':['bpi:%s'%private.id]})
        self.assertEqual(self.product._bpi_public_gallery_reference(website, self.high.id, private.id), private)
        self.assertFalse(self.product._bpi_public_gallery_reference(website, self.starter.id, private.id))
        self.assertFalse(private.product_image_id)
        self.assertIn('/variant_gallery/', self.product._bpi_public_variant_content(website, self.high.id)['image'])
        self.save(inherit=['gallery'])
        self.assertFalse(self.product._bpi_public_gallery_reference(website, self.high.id, private.id))

    def test_workspace_specification_and_copy_are_atomic(self):
        scope = self.scope()
        args = (self.product, self.high.id, {'description':'<p>Texto nuevo</p>'}, [], scope['baseRevision'], scope['revision'])
        with self.assertRaises(ValidationError):
            self.profiles._save_workspace(*args, context_revision=scope['contextRevision'],
                specifications=[{'variantId':self.high.id,'revision':0,'values':{'length':-1}}])
        self.assertEqual(self.scope()['values']['description'], '<p>Contenido común</p>')
        self.assertEqual(self.scope()['revision'], scope['revision'])
        self.profiles._save_workspace(*args, context_revision=scope['contextRevision'],
            specifications=[{'variantId':self.high.id,'revision':0,'values':{'length':15}}])
        self.assertEqual(self.scope()['values']['description'], '<p>Texto nuevo</p>')
        row = self.env['bpi.product.specification'].search([('product_id','=',self.high.id)])
        self.assertEqual(row.measurements, {'length':15})
        self.assertNotEqual(self.scope()['contextRevision'], scope['contextRevision'])
        self.assertFalse(self.env['bpi.product.specification'].search([('product_id','=',self.starter.id)]))

    def test_workspace_rejects_proposal_with_changed_supporting_measurements(self):
        scope = self.scope()
        with self.assertRaises(ValidationError):
            self.profiles._save_workspace(self.product, self.high.id, {'description':'Nueva'}, [],
                scope['baseRevision'], scope['revision'], context_revision=scope['contextRevision'], proposal_id=1,
                specifications=[{'variantId':self.high.id,'revision':0,'values':{'length':15}}])
        self.assertEqual(self.scope()['revision'], 0)

    def test_non_variant_option_keeps_existing_edition_and_complete_combination(self):
        website = self.public_fixture()
        attribute = self.env['product.attribute'].create({'name':'Opción sin SKU','create_variant':'no_variant'})
        values = self.env['product.attribute.value'].create([{'name':name,'attribute_id':attribute.id} for name in ('A','B')])
        self.product.write({'attribute_line_ids':[(0,0,{'attribute_id':attribute.id,'value_ids':[(6,0,values.ids)]})]})
        self.assertEqual(self.product._bpi_public_variant(website, self.starter.id), self.starter)
        combo = self.product._get_first_possible_combination(necessary_values=self.starter.product_template_attribute_value_ids)
        self.assertEqual(len(combo), 2)
        self.assertEqual(self.product._get_variant_for_combination(combo), self.starter)
        self.assertTrue(self.product._bpi_public_variant_content(website, self.starter.id))

    def test_query_and_facets_require_the_same_edition(self):
        term = next(t for t in self.env['bpi.taxonomy.term']._catalog() if not t['universal'])
        self.save({'classification':{'termIds':[], 'excludedTermIds':[]}})
        self.save({'classification':{'termIds':[term['id']], 'excludedTermIds':[]}}, variant=self.starter)
        model = self.env['product.template'].with_context(bpi_variant_term_ids=[term['id']])
        with patch.object(type(model), '_bpi_variant_search_active', return_value=True):
            self.assertIn(self.product, model.search(model._bpi_query_domain('Starter')))
            self.assertNotIn(self.product, model.search(model._bpi_query_domain('High')))

    def test_classification_jobs_deduplicate_per_edition_and_common(self):
        jobs = self.env['bpi.ai.job']
        high = jobs.with_context(bpi_product_variant_id=self.high.id)._create_classification_job(self.product)
        starter = jobs.with_context(bpi_product_variant_id=self.starter.id)._create_classification_job(self.product)
        common = jobs._create_classification_job(self.product)
        self.assertEqual(len(high | starter | common), 3)
        self.assertEqual(jobs.with_context(bpi_product_variant_id=self.high.id)._create_classification_job(self.product), high)
        self.assertEqual(high.classification_request['source']['sku'], self.high.default_code)
        self.assertEqual(starter.classification_request['source']['sku'], self.starter.default_code)
        self.assertNotIn(self.starter.default_code, high.classification_request['source']['variantsAndPack'])
        self.assertEqual(self.product._bpi_classification_payload()['job']['id'], common.id)
        self.assertEqual(self.product.bpi_build_variant_payload(self.high.id)['classification']['job']['id'], high.id)
        self.assertEqual(self.product.bpi_build_variant_payload(self.starter.id)['classification']['job']['id'], starter.id)

    def test_classification_variant_process_uses_saved_scope_and_no_automatic_assignment(self):
        manager = self.env['res.users'].with_context(no_reset_password=True).create({'name':'Classification manager test', 'login':'bpi_classification_manager_variant_test', 'groups_id':[(6,0,self.env.ref('base.group_system').ids)]})
        job = self.env['bpi.ai.job'].with_context(bpi_product_variant_id=self.high.id)._create_classification_job(self.product)
        job.requested_by_id = manager
        term = next(t for t in self.env['bpi.taxonomy.term']._catalog() if not t['universal'])
        proposal = {'termIds':[term['id']], 'newTerms':[], 'warnings':[], 'reasons':'Revisar', 'nicheEvaluations':[], 'intentPhrases':[]}
        with patch.object(type(self.service), '_classification_proposal', return_value=proposal) as api:
            result = job._process_classification_job()
            self.assertEqual(api.call_args.args[1]['sku'], self.high.default_code)
        self.assertEqual(result['classificationProposal']['revision'], 0)
        self.assertEqual(self.scope()['revision'], 0)
        self.assertFalse(self.product.bpi_taxonomy_term_ids)
        self.high.default_code = 'CHANGED-HIGH'
        with patch.object(type(self.service), '_classification_proposal', side_effect=AssertionError('No paid retry')):
            with self.assertRaises(UserError):
                job._process_classification_job()

    def test_variant_meli_projection_filters_without_remote_calls(self):
        service = self.service
        if not hasattr(service, '_meli_project'):
            self.assertFalse(service._variant_meli_detail(self.product, self.high.id)['available'])
            return
        grouped = {self.product.id:{
            'high':{'productVariantId':self.high.id,'items':[{'_identity':True,'_listingId':7}]},
            'starter':{'productVariantId':self.starter.id,'items':[{'_identity':True,'_listingId':8}]}}}
        with patch.object(type(service), 'meli_detail', return_value={'available':True,'groups':[],'jobs':[]}), \
             patch.object(type(service), '_meli_project', return_value=({}, grouped)), \
             patch.object(type(service), '_meli_product_summary', return_value={'variantCount':1}) as summarize:
            result = service._variant_meli_detail(self.product, self.high.id)
        self.assertEqual([g['productVariantId'] for g in result['groups']], [self.high.id])
        self.assertEqual(result['variantId'], self.high.id)
        self.assertEqual(result['summary']['variantCount'], 1)
        self.assertNotIn('_identity', result['groups'][0]['items'][0])
        self.assertEqual(len(summarize.call_args.args[0]), 1)
        with self.assertRaises(MissingError):
            service._variant_meli_detail(self.product, self.other.product_variant_id.id)

    def test_variant_job_identity_is_owned_and_immutable(self):
        jobs = self.env['bpi.ai.job']
        with self.assertRaises(MissingError):
            jobs.create({'product_tmpl_id':self.product.id,'product_variant_id':self.other.product_variant_id.id})
        job = jobs.with_context(bpi_product_variant_id=self.high.id)._create_classification_job(self.product)
        with self.assertRaises(ValidationError):
            job.write({'product_variant_id':self.starter.id})
        with self.assertRaises(ValidationError):
            job.write({'product_tmpl_id':self.other.id})

    def test_explicit_empty_main_does_not_drop_complementary_variant_design(self):
        from ..models.description_layout import empty_layout
        website = self.public_fixture()
        layout = empty_layout(); layout['enabled'] = True
        layout['blocks'].append({'id':'variant_note','type':'text','html':'<p>Detalle complementario</p>'})
        self.save({'technicalDescription':'','descriptionLayout':layout})
        public = self.product._bpi_public_variant_content(website, self.high.id)
        self.assertEqual(str(public['long']), '')
        self.assertTrue(public['layout'])
        self.assertEqual(str(public['layout']['blocks'][0]['mainHtml']), '')
        rendered = str(self.env['ir.ui.view']._render_template('bader_product_intelligence.variant_editorial',
            {'product':self.product,'website':website,'bpi_variant_public':public}))
        self.assertIn('Detalle complementario', rendered)
        self.assertNotIn('Detalle común', rendered)

    def test_variant_video_is_effective_click_to_load_and_can_be_empty(self):
        website = self.public_fixture()
        self.product.bpi_video_url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        inherited = self.product._bpi_public_variant_content(website, self.high.id)
        self.assertIn('youtube-nocookie.com', inherited['video']['blocks'][0]['embed'])
        self.save({'videoUrl':'https://www.tiktok.com/@bader/video/1234567890123456789'})
        public = self.product._bpi_public_variant_content(website, self.high.id)
        self.assertEqual(public['video']['blocks'][0]['provider'], 'tiktok')
        rendered = str(self.env['ir.ui.view']._render_template('bader_product_intelligence.variant_editorial',
            {'product':self.product,'website':website,'bpi_variant_public':public}))
        self.assertIn('data-bpi-edition-video', rendered)
        self.assertIn('data-bpi-video-embed', rendered)
        self.assertNotIn('<iframe', rendered)
        self.assertNotIn('dQw4w9WgXcQ', rendered)
        self.save({'videoUrl':''})
        self.assertFalse(self.product._bpi_public_variant_content(website, self.high.id)['video'])
        self.assertTrue(self.product._bpi_public_variant_content(website, self.starter.id)['video'])
        self.save(inherit=['videoUrl'])
        self.assertIn('youtube-nocookie.com', self.product._bpi_public_variant_content(website, self.high.id)['video']['blocks'][0]['embed'])
        self.product.bpi_video_url = 'https://private.invalid/not-a-video'
        self.assertFalse(self.product._bpi_public_variant_content(website, self.high.id)['video'])

    def test_native_price_save_retains_consulted_quantity_and_date(self):
        before = self.service.variant_pricing(self.product, self.high.id, self.pricelist.id, 5, '2026-10-10 12:00:00')
        after = self.service.save_variant_pricing(self.product, self.high.id, self.pricelist.id,
            before['revision'], {'compute_price':'fixed','fixed_price':17,'min_quantity':5,
                'date_start':'2026-10-01 00:00:00','date_end':'2026-10-31 23:59:59'},
            quantity=before['quantity'], date=before['date'])
        self.assertEqual(after['quantity'], 5)
        self.assertEqual(after['date'], '2026-10-10 12:00:00')
        self.assertEqual(after['price'], 17)
        self.assertTrue(after['ruleIsVariantSpecific'])
