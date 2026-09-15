from unittest.mock import patch

from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('-at_install', 'post_install')
class TestTechnicalSpecification(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env['product.template'].create({'name': 'Medidas BPI', 'default_code': 'BPI-SPEC-001', 'description_sale': 'Preservar'})
        cls.variant = cls.product.product_variant_id
        cls.specs = cls.env['bpi.product.specification']
        cls.service = cls.env['bpi.service']
        cls.user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Specifications reader', 'login': 'bpi_spec_reader',
            'groups_id': [(6, 0, cls.env.ref('base.group_user').ids)]})

    def row(self, values, revision=0, variant=None):
        return {'variantId': (variant or self.variant).id, 'revision': revision, 'values': values}

    def test_empty_payload(self):
        row = self.product.bpi_build_payload()['technicalSpecifications'][0]
        self.assertEqual(row['values'], {})
        self.assertEqual(row['revision'], 0)
        self.assertFalse(self.specs.search([('product_id', '=', self.variant.id)]))

    def test_save_decimal_and_clear(self):
        self.specs._save_rows(self.product, [self.row({'height': '1,5', 'weight': '17'})])
        row = self.specs._payload(self.product)[0]
        self.assertEqual(row['values'], {'height': 1.5, 'weight': 17.0})
        self.assertEqual(row['sources']['height']['kind'], 'manual')
        self.specs._save_rows(self.product, [self.row({'height': ''}, 1)])
        self.assertEqual(self.specs._payload(self.product)[0]['values'], {})
        self.assertEqual(self.specs._payload(self.product)[0]['sources'], {})

    def test_invalid_values(self):
        for value in (True, False, 0, -1, float('nan'), float('inf'), 'NO', '1.000,5', '2 cm', [], 1000001):
            with self.subTest(value=repr(value)):
                with self.assertRaises(ValidationError):
                    self.specs._normalize({'height': value})

    def test_unknown_fields(self):
        with self.assertRaises(ValidationError):
            self.specs._normalize({'sterilization': 135})

    def test_width_order(self):
        with self.assertRaises(ValidationError):
            self.specs._save_rows(self.product, [self.row({'widthMax': 20, 'widthMin': 30})])

    def test_stale_save(self):
        self.specs._save_rows(self.product, [self.row({'length': 17})])
        with self.assertRaises(UserError):
            self.specs._save_rows(self.product, [self.row({'length': 18})])
        self.assertEqual(self.specs._payload(self.product)[0]['values']['length'], 17)

    def test_noop_preserves_revision_and_date(self):
        self.specs._save_rows(self.product, [self.row({'length': 17})])
        before = self.specs._payload(self.product)
        self.specs._save_rows(self.product, [self.row({'length': '17'}, 1)])
        self.assertEqual(before, self.specs._payload(self.product))

    def test_foreign_variant(self):
        other = self.env['product.template'].create({'name': 'Other spec'})
        with self.assertRaises(ValidationError):
            self.specs._save_rows(self.product, [self.row({'length': 17}, variant=other.product_variant_id)])

    def test_duplicate_variant_atomic(self):
        with self.assertRaises(ValidationError):
            self.specs._save_rows(self.product, [self.row({'length': 17}), self.row({'length': 18})])
        self.assertFalse(self.specs.search([('product_id', '=', self.variant.id)]))

    def test_save_all_atomic(self):
        with self.assertRaises(ValidationError):
            self.service.save_all(self.product, product_values={'name': 'Must rollback', 'technicalSpecifications': [self.row({'height': -1})]})
        self.assertEqual(self.product.name, 'Medidas BPI')
        self.assertFalse(self.specs.search([('product_id', '=', self.variant.id)]))

    def test_legacy_omitted_preserves_specs(self):
        self.specs._save_rows(self.product, [self.row({'length': 17})])
        self.service.update_product(self.product, {'brand': 'Bader'})
        self.assertEqual(self.specs._payload(self.product)[0]['values'], {'length': 17.0})

    def test_no_native_product_writes_or_external_call(self):
        with patch.object(type(self.variant), 'write', side_effect=AssertionError('No logistic/integrator writes')), \
             patch.object(type(self.product), 'write', side_effect=AssertionError('No template writes')), \
             patch.object(type(self.service), '_openai_request', side_effect=AssertionError('No external call')):
            self.specs._save_rows(self.product, [self.row({'length': 17, 'weight': 17})])
            self.product.bpi_build_payload()
        self.assertEqual(self.product.description_sale, 'Preservar')

    def test_facts_and_native_weight_precedence(self):
        self.variant.weight = 2
        self.specs._save_rows(self.product, [self.row({'height': '1,5', 'weight': 17})])
        facts = self.product._bpi_content_facts()
        self.assertIn('1,5 cm', [f['value'] for f in facts])
        self.assertIn('17 g', [f['value'] for f in facts])
        self.assertNotIn('weight', [f['id'] for f in facts])
        self.assertEqual(self.variant.weight, 2)

    def test_revision_changes_generation_fingerprint(self):
        before = self.service.content_template_context(self.product)
        self.specs._save_rows(self.product, [self.row({'length': 17})])
        after = self.service.content_template_context(self.product)
        self.assertNotEqual(before['specificationRevision'], after['specificationRevision'])
        with self.assertRaises(UserError):
            self.service._content_template_assert_current(self.product, before)

    def test_non_admin(self):
        with self.assertRaises(AccessError):
            self.specs.with_user(self.user)._save_rows(self.product.with_user(self.user), [self.row({'length': 17})])
        with self.assertRaises(AccessError):
            self.specs.with_user(self.user).search([])

    def test_other_company(self):
        company = self.env['res.company'].create({'name': 'Spec isolated company'})
        product = self.env['product.template'].create({'name': 'Other company spec', 'company_id': company.id})
        with self.assertRaises(MissingError):
            self.specs.with_context(allowed_company_ids=[self.env.company.id])._save_rows(product, [self.row({'length': 17}, variant=product.product_variant_id)])

    def test_variant_specific_and_pack(self):
        attribute = self.env['product.attribute'].create({'name': 'Spec size'})
        values = self.env['product.attribute.value'].create([{'name': n, 'attribute_id': attribute.id} for n in ['Small', 'Large']])
        product = self.env['product.template'].create({'name': 'Two sizes', 'attribute_line_ids': [(0, 0, {'attribute_id': attribute.id, 'value_ids': [(6, 0, values.ids)]})]})
        a,b = product.product_variant_ids
        self.specs._save_rows(product, [self.row({'length': 10}, variant=a), self.row({'length': 20}, variant=b)])
        facts = [f for f in product._bpi_content_facts() if f['id'].startswith('spec:')]
        self.assertEqual(len(facts), 2)
        self.assertNotEqual(facts[0]['id'], facts[1]['id'])
        product.write({'pack_ok': True})
        self.assertEqual(len([f for f in product._bpi_content_facts() if f['id'].startswith('spec:')]), 2)

    def test_raw_write_rejects_invalid_measurement(self):
        record = self.specs.create({'product_id': self.variant.id, 'measurements': {'weight': 17}})
        with self.assertRaises(ValidationError):
            record.write({'measurements': {'weight': -1}})
        with self.assertRaises(ValidationError):
            record.write({'revision': 0})

    def test_import_valid_fields_only(self):
        rows = [{'row': 3, 'sku': 'BPI-SPEC-001', 'values': {'height': 'NO', 'length': '17', 'weight': '0', 'widthMin': 30, 'widthMax': 20}}]
        plan = self.service._prepare_specification_import(rows)
        self.assertEqual(plan['updates'][0]['values'], {'length': 17.0})
        self.assertEqual(len(plan['issues']), 3)
        self.assertFalse(self.specs.search([('product_id', '=', self.variant.id)]), 'Preview does not write')
        self.service._apply_specification_import(plan, {'kind': 'spreadsheet', 'label': 'Test spreadsheet'})
        self.assertEqual(self.specs._payload(self.product)[0]['sources']['length']['row'], 3)

    def test_import_duplicates_missing_and_unknown(self):
        rows = [{'row': i, 'sku': sku, 'values': {'weight': w}} for i,sku,w in [(3,'BPI-SPEC-001',35),(4,'BPI-SPEC-001',45),(5,'',5),(6,'NONEXISTENT',5)]]
        plan = self.service._prepare_specification_import(rows)
        self.assertFalse(plan['updates'])
        self.assertEqual(len(plan['issues']), 4)

    def test_import_preserves_existing_and_is_idempotent(self):
        self.specs._save_rows(self.product, [self.row({'weight': 18})])
        rows = [{'row': 3, 'sku': 'BPI-SPEC-001', 'values': {'length': 17, 'weight': 17}}]
        plan = self.service._prepare_specification_import(rows)
        self.assertEqual(plan['updates'][0]['values']['weight'], 18)
        self.service._apply_specification_import(plan, {'kind': 'spreadsheet', 'label': 'Test spreadsheet'})
        second = self.service._prepare_specification_import(rows)
        self.assertFalse(second['updates'])
        self.assertEqual(self.variant.weight, 0)

    def test_import_ambiguous_odoo_sku(self):
        self.env['product.template'].create({'name': 'Duplicate SKU', 'default_code': 'BPI-SPEC-001'})
        plan = self.service._prepare_specification_import([{'row': 3, 'sku': 'BPI-SPEC-001', 'values': {'length': 17}}])
        self.assertFalse(plan['updates'])
        self.assertEqual(plan['issues'][0]['reason'], 'ambiguous_odoo_sku')

    def test_archiving_variant_changes_evidence_fingerprint(self):
        before = self.service.content_template_context(self.product)['specificationRevision']
        self.variant.active = False
        after = self.service.content_template_context(self.product)['specificationRevision']
        self.assertNotEqual(before, after)

    def test_structured_generation_renders_saved_measurement_units(self):
        self.specs._save_rows(self.product, [self.row({'height': '1,5', 'weight': 17})])
        facts = self.product._bpi_content_facts()
        html = self.service._content_structured_html({
            'generalParagraphs': ['Primer párrafo comprobado.', 'Segundo párrafo comprobado.'],
            'specificationIds': [f['id'] for f in facts if f['id'].startswith('spec:')],
        }, facts)
        # Renderer returns (HTML, warnings).
        rendered = html[0] if isinstance(html, tuple) else html
        self.assertIn('1,5 cm', rendered)
        self.assertIn('17 g', rendered)
