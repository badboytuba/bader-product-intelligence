from odoo.api import call_kw
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged("-at_install", "post_install")
class TestBPIVideoSecurity(TransactionCase):
    def test_video_query_order_and_supported_providers(self):
        product = self.env["product.template"].create({"name": "BPI video regression"})
        for url in (
            "https://www.youtube.com/watch?feature=share&v=abc123_xyz01",
            "https://youtu.be/abc123_xyz01?si=tracking",
            "https://www.youtube.com/shorts/abc123_xyz01",
            "https://www.youtube.com/embed/abc123_xyz01",
        ):
            product.bpi_video_url = product._bpi_normalize_video_url(url)
            self.assertEqual(product.bpi_video_embed_url, "https://www.youtube.com/embed/abc123_xyz01")
        self.assertEqual(product._bpi_parse_video_url("https://www.instagram.com/reel/ABC123/?igsh=tracking")[1], "https://www.instagram.com/reel/ABC123/embed")
        self.assertEqual(product._bpi_parse_video_url("https://www.tiktok.com/@bader/video/123456789")[1], "https://www.tiktok.com/embed/v2/123456789")
        self.assertEqual(product._bpi_normalize_video_url(""), "")

    def test_invalid_legacy_video_does_not_break_payload(self):
        product = self.env["product.template"].create({"name": "BPI legacy video"})
        for url in (
            "https://www.youtube.com/watch",
            "https://www.youtube.com/watch?feature=share",
            "https://youtube.com.evil.invalid/watch?v=abc123_xyz01",
            "javascript:alert(1)",
            "https://user:secret@youtube.com/watch?v=abc123_xyz01",
            "https://www.youtube.com:bad/watch?v=abc123_xyz01",
        ):
            with self.assertRaises(UserError):
                product._bpi_normalize_video_url(url)
            product.bpi_video_url = url
            self.assertFalse(product.bpi_video_embed_url)
            self.assertEqual(product.bpi_build_payload()["product"]["id"], product.id)

    def test_generic_rpc_bridge_rejects_non_admin_before_sudo(self):
        user = new_test_user(self.env, login="bpi_bridge_no_admin", groups="base.group_user")
        model = self.env["ir.ui.view"].with_user(user)
        with self.assertRaises(AccessError):
            call_kw(model, "bpi_sync_product_description_bridges", [], {})
        # Existing website tests cover administrator synchronization and rendering contracts.
