# -*- coding: utf-8 -*-
from lxml import etree
from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('-at_install', 'post_install')
class TestPremiumStorefront(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website = cls.env['website'].create({'name': 'Premium isolated website'})
        cls.other = cls.env['website'].create({'name': 'Legacy isolated website'})
        cls.editor = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Storefront non-administrator', 'login': 'bpi_storefront_non_admin',
            'groups_id': [(6, 0, [cls.env.ref('base.group_user').id,
                                 cls.env.ref('website.group_website_designer').id])],
        })

    def enable(self):
        self.website.write({'bpi_premium_footer_html': '<section><a href="/shop">Catálogo propio</a></section>',
                            'bpi_premium_footer_legal_name': 'Bader prueba',
                            'bpi_premium_storefront_enabled': True})

    def test_default_disabled_no_cross_website_activation(self):
        self.assertFalse(self.website.bpi_premium_storefront_enabled)
        self.assertFalse(self.website.bpi_premium_footer_html)
        self.enable()
        self.assertFalse(self.other.bpi_premium_storefront_enabled)
        self.assertFalse(self.other.bpi_premium_footer_html)
        self.assertFalse(self.website.copy({'name': 'No auto opt-in'}).bpi_premium_storefront_enabled)

    def test_enable_requires_prepared_website_specific_content(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.website.bpi_premium_storefront_enabled = True
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.website.write({'bpi_premium_footer_html': '<p>Contenido</p>',
                                'bpi_premium_storefront_enabled': True})
        self.assertFalse(self.website.bpi_premium_storefront_enabled)

    def test_configuration_and_native_html_write_require_admin(self):
        for values in ({'bpi_premium_storefront_enabled': True},
                       {'bpi_premium_footer_html': '<p>Changed</p>'},
                       {'bpi_premium_footer_legal_name': 'Changed'}):
            with self.subTest(values=values), self.assertRaises(AccessError):
                self.website.with_user(self.editor).write(values)
        with self.assertRaises(AccessError):
            self.env['website'].with_user(self.editor).create({
                'name': 'Unauthorized', 'bpi_premium_storefront_enabled': False})

    def test_native_html_is_sanitized_and_escaped_legal_name(self):
        self.enable()
        self.website.write({'bpi_premium_footer_html': '<p class="bpi-footer-copy">Seguro<script>alert(1)</script><img src="/web/static/img/placeholder.png" onerror="alert(2)"/></p>',
                            'bpi_premium_footer_legal_name': '<script>unsafe</script>'})
        output = str(self.env['ir.ui.view']._render_template(
            'bader_product_intelligence.bpi_premium_footer_content', {'website': self.website}))
        self.assertNotIn('<script>', output)
        self.assertNotIn('onerror=', output)
        self.assertIn('&lt;script&gt;', output)
        self.assertIn('bpi-footer-copy', output)
        self.assertIn(str(fields.Date.today().year), output)

    def test_disable_preserves_authored_footer_content(self):
        self.enable()
        original = self.website.bpi_premium_footer_html
        self.website.bpi_premium_storefront_enabled = False
        self.assertEqual(self.website.bpi_premium_footer_html, original)
        self.website.bpi_premium_storefront_enabled = True
        self.assertEqual(self.website.bpi_premium_footer_html, original)

    def test_footer_keeps_legacy_and_page_visibility(self):
        view = self.env.ref('bader_product_intelligence.bpi_premium_footer')
        self.assertEqual(view.inherit_id, self.env.ref('website.layout'))
        self.assertIn('$0', view.arch_db)
        self.assertIn('not website.bpi_premium_storefront_enabled', view.arch_db)
        # The replacement is inside #bottom, so footer_visible remains native.
        self.assertNotIn('footer_visible', view.arch_db)
        self.assertFalse(self.website.bpi_premium_storefront_enabled)

    def test_product_bridge_keeps_native_price_and_media_contracts(self):
        bridge = self.env.ref('bader_product_intelligence.bpi_product_detail_extensions')
        self.assertIn('pricelist,product,website', bridge.arch_db)
        self.assertIn('website.get_pricelist_available(show_visible=True)', bridge.arch_db)
        self.assertIn('website_sale.pricelist_list', bridge.arch_db)
        self.assertNotIn('shop_product_carousel', bridge.arch_db)
        self.assertNotIn('product.attribute', bridge.arch_db)

    def test_website_copy_synchronization_is_idempotent_and_non_destructive(self):
        View = self.env['ir.ui.view']
        source = self.env.ref('website_sale.product')
        copy = View.create({'name': 'Premium primary copy', 'key': 'website_sale.product',
            'type': 'qweb', 'mode': 'primary', 'website_id': self.website.id, 'arch_db': source.arch_db})
        before = copy.arch_db
        for unused in range(2):
            View.bpi_sync_product_description_bridges()
        self.assertEqual(copy.arch_db, before)
        bridges = View.search([('inherit_id', '=', copy.id),
            ('name', '=', 'bader.product.intelligence.website.formatted.description.%s' % copy.id)])
        self.assertEqual(len(bridges), 1)
        self.assertIn('bpi-product-premium', bridges.arch_db)
        combined = copy.with_context(website_id=self.website.id)._get_combined_arch()
        self.assertTrue(combined.xpath("//*[@id='product_detail']"))
        self.assertEqual(len(combined.xpath("//*[@id='product_details']//t[@t-call='website_sale.pricelist_list']")), 1)

    def test_native_combination_echo_does_not_modify_price_or_media(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from ..controllers.description_variant import DescriptionVariantController
        product = self.env['product.template'].create({'name': 'Native combination product'})
        native = {'product_template_id': product.id, 'product_id': product.product_variant_id.id,
                  'price': 123.4, 'carousel': '<div>native images</div>', 'is_combination_possible': True}
        self.enable()
        with patch('odoo.addons.bader_product_intelligence.controllers.description_variant.request',
                SimpleNamespace(env=self.env, website=self.website)), patch(
                'odoo.addons.website_sale.controllers.variant.WebsiteSaleVariantController.get_combination_info_website',
                return_value=dict(native)):
            result = DescriptionVariantController.get_combination_info_website.__wrapped__(
                DescriptionVariantController(), product.id, product.product_variant_id.id, [], 1,
                bpi_storefront_token='24')
        self.assertEqual(result.pop('bpi_storefront'), {'token': '24', 'productTemplateId': product.id})
        self.assertEqual(result, native)
        for enabled, token in ((False, '24'), (True, 'untrusted'), (True, '1' * 17)):
            self.website.bpi_premium_storefront_enabled = enabled
            with patch('odoo.addons.bader_product_intelligence.controllers.description_variant.request',
                    SimpleNamespace(env=self.env, website=self.website)), patch(
                    'odoo.addons.website_sale.controllers.variant.WebsiteSaleVariantController.get_combination_info_website',
                    return_value=dict(native)):
                result = DescriptionVariantController.get_combination_info_website.__wrapped__(
                    DescriptionVariantController(), product.id, product.product_variant_id.id, [], 1,
                    bpi_storefront_token=token)
            self.assertEqual(result, native)
