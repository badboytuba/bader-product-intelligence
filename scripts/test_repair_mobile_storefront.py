import unittest

from repair_mobile_storefront import BLOCK, MARKER, repair_mobile_storefront


class MobileStorefrontRepairTests(unittest.TestCase):
    def reviewed(self):
        return '/* BADER_PRODUCT_TYPOGRAPHY_V1 */\r\n/* END_BADER_PRODUCT_TYPOGRAPHY_V1 */\r\n/* café */'

    def test_preserves_every_existing_byte(self):
        before = self.reviewed()
        after, changed = repair_mobile_storefront(before)
        self.assertTrue(changed)
        self.assertEqual(after[:len(before)], before)
        self.assertEqual(after[len(before):], '\n\n' + BLOCK + '\n')

    def test_repeated_operation_is_idempotent(self):
        once, _ = repair_mobile_storefront(self.reviewed())
        self.assertEqual(repair_mobile_storefront(once), (once, False))

    def test_marker_drift_is_not_overwritten(self):
        for css in (self.reviewed() + MARKER, repair_mobile_storefront(self.reviewed())[0] + '/* later edit */', repair_mobile_storefront(self.reviewed())[0] + BLOCK):
            with self.assertRaisesRegex(ValueError, 'drift'):
                repair_mobile_storefront(css)

    def test_unreviewed_or_wrong_input_rejected(self):
        for css in (None, b'css', '', 'h1{}'):
            with self.assertRaises(ValueError):
                repair_mobile_storefront(css)

    def test_legacy_missing_fonts_require_separate_repair(self):
        with self.assertRaisesRegex(ValueError, 'font sources'):
            repair_mobile_storefront(self.reviewed() + '/website/static/src/fonts/old.otf')

    def test_scope_and_media_queries(self):
        self.assertEqual(BLOCK.count('#wrapwrap:has(> #top .bpi-header-search)'), 5)
        self.assertIn('@media (max-width: 767.98px)', BLOCK)
        self.assertIn('@media (max-width: 575.98px)', BLOCK)
        self.assertIn('#wrap:not(.js_sale) h1', BLOCK)
        self.assertIn('font-size: inherit !important', BLOCK)

    def test_fixes_intrinsic_width_not_by_clipping(self):
        self.assertIn('overflow-wrap: anywhere', BLOCK)
        self.assertIn('flex-wrap: wrap !important', BLOCK)
        self.assertIn('min-width: 0', BLOCK)
        self.assertNotIn('overflow-x:', BLOCK)
        self.assertNotIn('overflow: hidden', BLOCK)

    def test_native_controls_and_fonts_preserved(self):
        for unsupported in ('display: none', 'font-family:', 'font-weight:', 'position: fixed', 'img {', 'iframe {', '.navbar', '@font-face', 'https:'):
            self.assertNotIn(unsupported, BLOCK)


if __name__ == '__main__':
    unittest.main()
