# -*- coding: utf-8 -*-
import copy
import io
import os
import tempfile
from unittest.mock import patch

from PIL import Image
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

from ..models.description_layout import (
    CHUNK_SIZE, MAX_VIDEO, MIN_FREE, QUOTA, auxiliary_html, empty_layout,
    layout_media_ids, probe_video, social_video, validate_layout,
)


@tagged('-at_install', 'post_install')
class TestDescriptionLayout(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env['product.template'].create({'name': 'Layout fixture', 'sale_ok': True,
            'bpi_technical_description': '<p>Texto principal aprobado.</p>'})
        cls.other = cls.env['product.template'].create({'name': 'Other layout product'})
        cls.service = cls.env['bpi.service']
        cls.media = cls.env['bpi.description.media']
        cls.website = cls.env['website'].search([], limit=1)

    def setUp(self):
        super().setUp()
        self.directory = tempfile.TemporaryDirectory(prefix='bpi-layout-test-')
        self.addCleanup(self.directory.cleanup)
        self.env['ir.config_parameter'].sudo().set_param('bpi.description_media_root', self.directory.name)
        # Test reservations independent of the QAS server disk's free capacity.
        usage = type('Usage', (), {'free': 8 * 1024 * 1024 * 1024})()
        disk = patch('odoo.addons.bader_product_intelligence.models.description_layout.shutil.disk_usage', return_value=usage)
        disk.start(); self.addCleanup(disk.stop)

    def layout(self, extra=None):
        value = empty_layout(); value['enabled'] = True
        value['blocks'].extend(extra or [])
        return value

    def image(self, product=None):
        buffer = io.BytesIO(); Image.new('RGB', (12, 12), 'white').save(buffer, 'PNG')
        data = buffer.getvalue()
        record = self.media._start(product or self.product, 'photo.png', len(data), 'image')
        record._chunk(0, io.BytesIO(data)); record._complete()
        return record

    def test_layout_main_reference_and_no_external_calls(self):
        before = self.product.bpi_technical_description
        layout = self.layout([{'id': 'note', 'type': 'callout', 'html': '<p>Información útil</p>', 'preset': 'mist'}])
        with patch.object(type(self.service), '_openai_request', side_effect=AssertionError('No provider calls')):
            payload = self.service.save_content(self.product, {'descriptionLayout': layout,
                'editorialRevision': self.product.bpi_editorial_revision})
        self.assertTrue(payload['descriptionLayout']['enabled'])
        self.assertEqual(before, self.product.bpi_technical_description)
        self.assertNotIn('Texto principal', str(payload['descriptionLayout']))

    def test_requires_exactly_one_main_and_unique_ids(self):
        for blocks in ([], [{'id': 'a', 'type': 'main'}, {'id': 'b', 'type': 'main'}],
                       [{'id': 'same', 'type': 'main'}, {'id': 'same', 'type': 'divider'}]):
            with self.subTest(blocks=blocks), self.assertRaises(ValidationError):
                validate_layout({'version': 1, 'enabled': True, 'blocks': blocks})

    def test_layout_rejects_arbitrary_css_embed_and_excessive_depth(self):
        for change in ({'style': 'background:url(https://evil.test)'}, {'preset': 'custom'},
                       {'effect': 'script'}, {'type': 'iframe'}, {'align': 'right'}):
            value = self.layout(); value['blocks'][0].update(change)
            with self.assertRaises(ValidationError):
                validate_layout(value)
        nested = {'id': 'm', 'type': 'main'}
        for index in range(6):
            nested = {'id': str(index), 'type': 'container', 'children': [nested]}
        with self.assertRaises(ValidationError):
            validate_layout({'version': 1, 'enabled': True, 'blocks': [nested]})

    def test_auxiliary_html_has_no_active_or_external_content(self):
        text = auxiliary_html('Intro<p class="x" onclick="x()">Seguro<strong>texto</strong></p><script>alert(1)</script><iframe src="x"/><img src="https://evil.test/a"/>')
        self.assertIn('Intro', text); self.assertIn('<strong>texto</strong>', text)
        for forbidden in ('onclick', 'class=', 'script', 'iframe', '<img', 'alert(1)'):
            self.assertNotIn(forbidden, text)

    def test_social_links_are_normalized_without_requests(self):
        youtube = social_video('https://youtu.be/abcdefghijk?si=tracking')
        self.assertEqual(youtube['embed'], 'https://www.youtube-nocookie.com/embed/abcdefghijk')
        self.assertNotIn('tracking', youtube['url'])
        self.assertEqual(social_video('https://www.instagram.com/reel/abcdef/')['embed'], '')
        for url in ('javascript:alert(1)', 'https://youtube.com.evil.test/watch?v=abcdefghijk',
                    'http://youtu.be/abcdefghijk', 'https://u:p@youtube.com/watch?v=abcdefghijk',
                    'https://127.0.0.1/video', 'https://facebook.com:444/video', 'https://youtu.be/no'):
            with self.subTest(url=url), self.assertRaises(ValidationError):
                social_video(url)

    def test_save_all_checks_revision_before_datos_mutation(self):
        revision = self.product.bpi_editorial_revision
        self.product.write({'website_meta_title': 'Concurrent title'})
        with self.assertRaises(UserError):
            self.service.save_all(self.product, product_values={'name': 'Do not save'},
                content_values={'description': 'Do not save', 'editorialRevision': revision})
        self.assertEqual(self.product.name, 'Layout fixture')
        self.assertEqual(self.product.website_meta_title, 'Concurrent title')

    def test_partial_saves_guard_editorial_revision(self):
        revision = self.product.bpi_editorial_revision
        self.product.write({'website_meta_description': 'Concurrent edit'})
        for method, values in (
            (self.service.update_product, {'name': 'Do not save'}),
            (self.service.save_category, {}),
            (self.service.save_seo_payload, {'seoTitle': 'Do not save'}),
        ):
            with self.assertRaises(UserError):
                method(self.product, dict(values, editorialRevision=revision))
        self.assertEqual(self.product.name, 'Layout fixture')
        self.assertNotEqual(self.product.website_meta_title, 'Do not save')

    def test_save_all_own_product_changes_do_not_conflict(self):
        revision = self.product.bpi_editorial_revision
        result = self.service.save_all(self.product, product_values={'name': 'Updated fixture'},
            content_values={'description': '<p>New short</p>', 'descriptionLayout': self.layout(), 'editorialRevision': revision},
            seo_data={'seoTitle': 'Updated SEO'})
        self.assertEqual(result['seoData']['seoTitle'], 'Updated SEO')
        self.assertIn('New short', self.product.bpi_ai_generated_description)
        self.assertGreater(result['editorialRevision'], revision)

    def test_invalid_layout_rolls_back_content_and_datos(self):
        revision = self.product.bpi_editorial_revision
        with self.assertRaises(ValidationError):
            self.service.save_all(self.product, product_values={'name': 'Rollback'},
                content_values={'description': 'Rollback', 'descriptionLayout': {'version': 99}, 'editorialRevision': revision})
        self.assertEqual(self.product.name, 'Layout fixture')
        self.assertEqual(self.product.bpi_editorial_revision, revision)

    def test_legacy_omitted_layout_and_revisions_stay_compatible(self):
        self.service.save_content(self.product, {'descriptionLayout': self.layout()})
        saved = copy.deepcopy(self.product.bpi_description_layout)
        self.service.save_content(self.product, {'technicalDescription': '<p>New principal</p>'})
        self.assertEqual(self.product.bpi_description_layout, saved)
        self.service.save_content(self.product, {'descriptionLayout': False})
        self.assertFalse(self.product.bpi_description_layout['enabled'])
        self.assertIn('New principal', self.product.bpi_technical_description)

    def test_keyword_and_faq_direct_orm_changes_advance_revision(self):
        for model, values in (
            ('bpi.product.keyword', {'name': 'keyword', 'keyword_type': 'seo'}),
            ('bpi.product.faq', {'question': 'Question?', 'answer': 'Answer'}),
        ):
            revision = self.product.bpi_editorial_revision
            record = self.env[model].create(dict(values, product_tmpl_id=self.product.id))
            self.assertGreater(self.product.bpi_editorial_revision, revision)
            revision = self.product.bpi_editorial_revision
            record.write({'sequence': 20})
            self.assertGreater(self.product.bpi_editorial_revision, revision)
            revision = self.product.bpi_editorial_revision
            record.unlink()
            self.assertGreater(self.product.bpi_editorial_revision, revision)

    def test_native_variant_creation_preserves_delegated_defaults(self):
        variant = self.env['product.product'].create({'name': 'Native variant', 'default_code': 'BPI-LAYOUT-VARIANT'})
        self.assertEqual(variant.product_tmpl_id.bpi_editorial_revision, 1)
        self.assertFalse(variant.product_tmpl_id.bpi_description_layout)
        product = self.env['product.template'].create({'name': 'Explicit initial default', 'bpi_editorial_revision': 1})
        self.assertEqual(product.bpi_editorial_revision, 1)

    def test_revision_cannot_be_forged_or_layout_media_created_cross_product(self):
        with self.assertRaises(AccessError):
            self.product.write({'bpi_editorial_revision': 0})
        with self.assertRaises(AccessError):
            self.env['product.template'].create({'name': 'Forgery', 'bpi_editorial_revision': 9})
        image = self.image()
        with self.assertRaises(ValidationError):
            self.env['product.template'].create({'name': 'Foreign layout', 'bpi_description_layout': self.layout([
                {'id': 'photo', 'type': 'image', 'mediaId': image.id}])})

    def test_chunk_resume_duplicate_and_invalid_offset(self):
        record = self.media._start(self.product, 'video.mp4', 6, 'video')
        self.assertEqual(record._chunk(0, io.BytesIO(b'abc'))['offset'], 3)
        self.assertEqual(record._chunk(0, io.BytesIO(b'abc'))['offset'], 3)
        with self.assertRaises(ValidationError): record._chunk(0, io.BytesIO(b'xyz'))
        with self.assertRaises(ValidationError): record._chunk(5, io.BytesIO(b'x'))
        self.assertEqual(record._chunk(3, io.BytesIO(b'def'))['offset'], 6)
        self.assertEqual(open(record._path(), 'rb').read(), b'abcdef')
        with patch('odoo.addons.bader_product_intelligence.models.description_layout.shutil.which', return_value='/usr/bin/ffprobe'):
            with self.assertRaises(ValidationError): record._complete()

    def test_images_are_reencoded_and_draft_private(self):
        record = self.image()
        self.assertEqual(record.mimetype, 'image/jpeg')
        with open(record._path(), 'rb') as data:
            self.assertEqual(data.read(2), b'\xff\xd8')
        self.assertFalse(self.env['ir.attachment'].search([('res_model', '=', record._name), ('res_id', '=', record.id)]))
        self.assertNotIn(record.id, layout_media_ids(self.product.bpi_description_layout))
        with self.assertRaises(AccessError):
            record.write({'state': 'ready', 'storage_key': '../bad'})
        with self.assertRaises(AccessError):
            self.media.create({'product_id': self.product.id, 'name': 'Forged', 'kind': 'video', 'state': 'ready', 'reserved_size': 1})

    def test_media_ownership_and_ready_status(self):
        record = self.image()
        value = self.layout([{'id': 'photo', 'type': 'image', 'mediaId': record.id, 'alt': 'Photo'}])
        with self.assertRaises(MissingError):
            self.service.save_content(self.other, {'descriptionLayout': value})
        self.service.save_content(self.product, {'descriptionLayout': value})
        with self.assertRaises(UserError): record.unlink()
        self.service.save_content(self.product, {'descriptionLayout': empty_layout()})
        self.assertTrue(record.exists())  # Removing a block never removes its media.

    def test_quota_includes_pending_reservations_and_free_floor(self):
        self.media._start(self.product, 'v.mp4', MAX_VIDEO, 'video')
        with self.assertRaises(UserError): self.media._check_capacity(QUOTA - MAX_VIDEO + 1)
        usage = type('Usage', (), {'free': MIN_FREE + MAX_VIDEO - 1})()
        with patch('odoo.addons.bader_product_intelligence.models.description_layout.shutil.disk_usage', return_value=usage):
            with self.assertRaises(UserError): self.media._check_capacity(0)
        with self.assertRaises(ValidationError): self.media._start(self.product, 'v.mp4', MAX_VIDEO + 1, 'video')

    def test_missing_video_validator_fails_closed(self):
        with patch('odoo.addons.bader_product_intelligence.models.description_layout.shutil.which', return_value=None):
            with self.assertRaises(UserError): probe_video('/nonexistent-but-no-probe')

    def test_public_projection_current_saved_reference_only(self):
        image = self.image()
        self.service.save_content(self.product, {'descriptionLayout': self.layout([
            {'id': 'photo', 'type': 'image', 'mediaId': image.id, 'caption': '<unsafe>', 'alt': 'Image'},
            {'id': 'yt', 'type': 'video', 'url': 'https://youtu.be/abcdefghijk'}])})
        self.assertFalse(self.product._bpi_public_description_layout(self.website))
        self.product.website_published = True
        layout = self.product._bpi_public_description_layout(self.website)
        self.assertIn('/%s/file' % image.id, layout['blocks'][1]['src'])
        rendered = self.env['ir.qweb']._render('bader_product_intelligence.description_layout', {'product': self.product, 'bpi_layout': layout})
        rendered = str(rendered)
        self.assertIn('Texto principal aprobado.', rendered)
        self.assertIn('&lt;unsafe&gt;', rendered)
        self.assertIn('data-bpi-video-embed=', rendered)
        self.assertNotIn('<iframe', rendered)
        self.product.sale_ok = False
        self.assertFalse(self.product._bpi_public_description_layout(self.website))

    def test_company_and_administrator_guard(self):
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Layout reader', 'login': 'bpi_layout_reader',
            'groups_id': [(6, 0, self.env.ref('base.group_user').ids)]})
        with self.assertRaises(AccessError):
            self.media.with_user(user)._start(self.product.with_user(user), 'a.png', 10, 'image')
        company = self.env['res.company'].create({'name': 'Other layout company'})
        other = self.env['product.template'].create({'name': 'Other company', 'company_id': company.id})
        with self.assertRaises(MissingError):
            self.media.with_context(allowed_company_ids=[self.env.company.id])._start(other, 'a.png', 10, 'image')
