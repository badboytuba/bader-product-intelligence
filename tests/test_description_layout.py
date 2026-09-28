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
                       {'effect': 'script'}, {'type': 'iframe'}, {'align': 'arbitrary'}):
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

    def test_video_size_and_aspect_are_bounded_and_legacy_defaults_safe(self):
        node = {'id': 'v', 'type': 'video', 'url': 'https://youtu.be/abcdefghijk'}
        result = validate_layout(self.layout([node]))['blocks'][1]
        self.assertEqual((result['videoWidth'], result['videoRatio']), (100, 'auto'))
        for width in (0, 24, 101, '50', True, 50.5):
            with self.assertRaises(ValidationError):
                validate_layout(self.layout([dict(node, videoWidth=width)]))
        for ratio in ('2; color:red', '16/9', {}, None):
            with self.assertRaises(ValidationError):
                validate_layout(self.layout([dict(node, videoRatio=ratio)]))
        for ratio in ('auto', '16:9', '9:16', '1:1', '4:3'):
            self.assertEqual(validate_layout(self.layout([dict(node, videoWidth=55, videoRatio=ratio)]))['blocks'][1]['videoWidth'], 55)

    def test_video_poster_is_owned_image_and_prevents_unlink(self):
        poster = self.image()
        node = {'id': 'v', 'type': 'video', 'url': 'https://youtu.be/abcdefghijk', 'posterMediaId': poster.id}
        layout = self.layout([node])
        self.assertEqual(layout_media_ids(layout), {poster.id})
        with self.assertRaises(MissingError):
            self.service.save_content(self.other, {'descriptionLayout': layout})
        self.service.save_content(self.product, {'descriptionLayout': layout})
        with self.assertRaises(UserError):
            poster.unlink()
        self.service.save_content(self.product, {'descriptionLayout': self.layout()})
        poster.unlink()

    def test_poster_download_is_explicit_and_leaves_product_unchanged(self):
        raw = io.BytesIO(); Image.new('RGB', (480, 360), 'blue').save(raw, 'JPEG')
        before = self.product.bpi_editorial_revision
        with patch('odoo.addons.bader_product_intelligence.models.studio_fetch.fetch_public_image', return_value=raw.getvalue()) as fetch:
            payload = self.media._youtube_poster(self.product, 'https://youtu.be/abcdefghijk?si=discard')
        fetch.assert_called_once_with('https://i.ytimg.com/vi/abcdefghijk/hqdefault.jpg')
        self.assertEqual(payload['kind'], 'image')
        self.assertEqual(payload['state'], 'ready')
        self.assertEqual(self.product.bpi_editorial_revision, before)
        self.assertFalse(self.product.bpi_description_layout)
        with self.assertRaises(UserError):
            self.media._youtube_poster(self.product, 'https://www.instagram.com/reel/abcdef/')

    def test_video_projection_is_local_and_safe_for_public_render(self):
        poster = self.image()
        self.product.write({'is_published': True, 'website_id': self.website.id})
        self.service.save_content(self.product, {'descriptionLayout': self.layout([
            {'id':'v', 'type':'video', 'url':'https://youtu.be/abcdefghijk', 'posterMediaId':poster.id, 'videoWidth':55, 'videoRatio':'9:16'}])})
        with patch('odoo.addons.bader_product_intelligence.models.studio_fetch.fetch_public_image', side_effect=AssertionError('No page fetch')):
            node = self.product._bpi_public_description_layout(self.website)['blocks'][1]
        self.assertEqual(node['videoStyle'], '--bpi-video-width:55%;--bpi-video-ratio:9/16')
        self.assertIn('/%s/file?r=' % poster.id, node['posterSrc'])
        self.assertNotIn('ytimg', node['posterSrc'])
        html = self.env['ir.ui.view']._render_template('bader_product_intelligence.description_layout', {'product':self.product, 'bpi_layout':self.product._bpi_public_description_layout(self.website)})
        html = str(html)
        self.assertIn('bpi-layout__play-icon', html)
        self.assertNotIn('<iframe', html)
        self.assertNotIn('El vídeo se carga', html)

    def test_video_typography_legacy_and_independent_styles(self):
        node = {'id':'v', 'type':'video', 'url':'https://youtu.be/abcdefghijk', 'caption':'Leyenda existente'}
        before = copy.deepcopy(node)
        normalized = validate_layout(self.layout([node]))['blocks'][1]
        self.assertEqual(node, before)
        self.assertEqual(normalized['caption'], before['caption'])
        self.assertNotIn('title', normalized)
        self.assertNotIn('captionStyle', normalized)
        self.product.website_published = True
        self.service.save_content(self.product, {'descriptionLayout': self.layout([node])})
        projected = self.product._bpi_public_description_layout(self.website)['blocks'][1]
        self.assertIn('font-size:14px', projected['captionCss'])
        self.assertIn('var(--bader-font-body)', projected['captionCss'])
        new = dict(node, title='Título del vídeo', titleStyle={'font':'display','size':32,'bold':True,'align':'center'},
                   captionStyle={'font':'body','size':18,'italic':True,'color':'green'})
        result = validate_layout(self.layout([new]))['blocks'][1]
        self.assertEqual(result['titleStyle']['size'], 32)
        self.assertEqual(result['captionStyle']['size'], 18)
        self.assertFalse(result['captionStyle']['bold'])
        self.assertFalse(result['titleStyle']['italic'])

    def test_video_typography_rejects_css_injection_and_bad_types(self):
        base = {'id':'v', 'type':'video', 'url':'https://youtu.be/abcdefghijk'}
        for style in (None, [], 'font-size:30px', {'css':'display:none'}, {'font':'url(https://evil.invalid)'},
                      {'font':[]}, {'size':11}, {'size':65}, {'size':'28'}, {'size':True}, {'size':20.5},
                      {'bold':'false'}, {'italic':1}, {'align':'center;color:red'}, {'color':'url(x)'}):
            for field in ('titleStyle', 'captionStyle'):
                with self.assertRaises(ValidationError):
                    validate_layout(self.layout([dict(base, **{field:style})]))
        for title in (False, {}, ['x'], 'x'*201):
            with self.assertRaises(ValidationError):
                validate_layout(self.layout([dict(base, title=title)]))

    def test_video_title_caption_render_escaped_no_open_video_footer(self):
        node = {'id':'v', 'type':'video', 'url':'https://youtu.be/abcdefghijk',
                'title':'<img src=x onerror=alert(1)>', 'caption':'<script>unsafe</script>',
                'titleStyle':{'font':'display','size':31,'bold':True,'align':'center'},
                'captionStyle':{'font':'body','size':18,'italic':True,'color':'green'}}
        self.product.website_published = True
        self.service.save_content(self.product, {'descriptionLayout': self.layout([node])})
        layout = self.product._bpi_public_description_layout(self.website)
        html = str(self.env['ir.qweb']._render('bader_product_intelligence.description_layout', {'product':self.product,'bpi_layout':layout}))
        self.assertIn('&lt;img', html); self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<img src=x', html); self.assertNotIn('<script>', html)
        self.assertIn('font-size:31px', html); self.assertIn('font-size:18px', html)
        self.assertIn('font-style:italic', html); self.assertIn('text-align:center', html)
        self.assertNotIn('Abrir vídeo', html); self.assertNotIn('bpi-layout__video-footer', html)
        self.assertIn('aria-label="Reproducir vídeo"', html)
        self.assertNotIn('<iframe', html)
        self.assertEqual(self.product.bpi_technical_description, '<p>Texto principal aprobado.</p>')

    def test_empty_video_text_stays_hidden_and_styles_roundtrip_atomically(self):
        node = {'id':'v', 'type':'video', 'url':'https://www.instagram.com/reel/abcdef/',
                'title':'   ', 'caption':' ', 'titleStyle':{'size':64}}
        self.product.website_published = True
        saved = self.service.save_content(self.product, {'descriptionLayout':self.layout([node]), 'editorialRevision':self.product.bpi_editorial_revision})
        self.assertEqual(saved['descriptionLayout']['blocks'][1]['titleStyle']['size'],64)
        html = str(self.env['ir.qweb']._render('bader_product_intelligence.description_layout', {'product':self.product,'bpi_layout':self.product._bpi_public_description_layout(self.website)}))
        self.assertNotIn('bpi-layout__video-title',html); self.assertNotIn('bpi-layout__video-caption',html)
        self.assertIn('Ver en la red social',html); self.assertIn('target="_blank"',html)
        before = copy.deepcopy(self.product.bpi_description_layout)
        revision = self.product.bpi_editorial_revision
        with self.assertRaises(ValidationError):
            self.service.save_content(self.product, {'descriptionLayout':self.layout([dict(node,titleStyle={'size':1000})]), 'editorialRevision':revision})
        self.assertEqual(self.product.bpi_description_layout,before)
        self.assertEqual(self.product.bpi_editorial_revision,revision)

    def test_mixed_videos_preserve_short_orientation_and_independent_providers(self):
        value = self.layout([{'id': 'pair', 'type': 'columns', 'columnLayout': 'media', 'columnGap': 'compact', 'columnAlign': 'start', 'children': [
            {'id': 'wide', 'type': 'video', 'url': 'https://youtu.be/abcdefghijk', 'videoRatio': '16:9'},
            {'id': 'tall', 'type': 'video', 'url': 'https://www.youtube.com/shorts/12345678901'}]}])
        saved = validate_layout(value)
        children = saved['blocks'][1]['children']
        self.assertEqual(children[1]['videoRatio'], '9:16')
        self.assertEqual(children[1]['url'], 'https://www.youtube.com/watch?v=12345678901')
        self.assertEqual(validate_layout(saved), saved)
        children[1].update(url='https://www.tiktok.com/@bader/video/1234567890123456789', videoRatio='auto')
        self.product.write({'bpi_description_layout': saved, 'is_published': True})
        projected = self.product._bpi_public_description_layout(self.website)['blocks'][1]
        self.assertIn('1.7777777777777777fr', projected['columnsStyle'])
        self.assertIn('0.5625fr', projected['columnsStyle'])
        self.assertIn('gap:12px', projected['columnsStyle'])
        self.assertIn('9/16', projected['children'][1]['videoStyle'])
        self.assertIn('tiktok.com/player/v1/', projected['children'][1]['embed'])

    def test_image_controls_roundtrip_without_modifying_original_media_or_text(self):
        media = self.image()
        saved_text = self.product.bpi_technical_description
        layout = self.layout([{'id': 'image', 'type': 'image', 'mediaId': media.id, 'imageWidth': 65,
            'imageMaxWidth': 440, 'imageAlign': 'right', 'imageRatio': '1:1', 'imageFit': 'cover',
            'title': 'Detalle', 'titleStyle': {'font': 'display', 'size': 32}, 'caption': 'Vista lateral'}])
        self.service.save_content(self.product, {'descriptionLayout': layout})
        self.product.write({'is_published': True})
        node = self.product._bpi_public_description_layout(self.website)['blocks'][1]
        for fragment in ('width:65%', 'max:440px', 'ratio:1/1', 'fit:cover', 'left:auto', 'right:0'):
            self.assertIn(fragment, node['imageStyle'])
        self.assertIn('32px', node['titleCss'])
        self.assertEqual(self.product.bpi_technical_description, saved_text)
        self.assertEqual((media.width, media.height), (12, 12))
        self.assertEqual(media.state, 'ready')

    def test_image_controls_reject_free_css_and_invalid_numbers(self):
        for property, value in [('imageWidth', 0), ('imageWidth', True), ('imageWidth', 100.5),
                ('imageMaxWidth', 2401), ('imageMaxWidth', -1), ('imageAlign', 'float'),
                ('imageRatio', 'url(https://evil.test)'), ('imageFit', 'fill'),
                ('titleStyle', {'size': 999}), ('captionStyle', {'font': 'external'})]:
            with self.subTest(property=property, value=value), self.assertRaises(ValidationError):
                validate_layout(self.layout([dict({'id': 'photo', 'type': 'image', 'mediaId': 1}, **{property: value})]))

    def test_column_options_allow_only_safe_presets(self):
        for key, value in [('columnLayout', 'url(evil)'), ('columnGap', 24), ('columnAlign', 'stretch')]:
            with self.subTest(key=key), self.assertRaises(ValidationError):
                validate_layout(self.layout([dict({'id': 'cols', 'type': 'columns', 'children': [
                    {'id': 'text', 'type': 'text', 'html': '<p>Text</p>'}]}, **{key: value})]))
        value = validate_layout(self.layout([{'id': 'cols', 'type': 'columns', 'columnLayout': 'wide-right',
            'align': 'right', 'children': [{'id': 'text', 'type': 'text'}]}]))
        self.assertEqual(value['blocks'][1]['columnLayout'], 'wide-right')

    def test_legacy_image_columns_keep_omitted_settings(self):
        value = validate_layout(self.layout([{'id': 'cols', 'type': 'columns', 'children': [
            {'id': 'image', 'type': 'image', 'mediaId': 1, 'caption': 'Legacy'}, {'id': 'text', 'type': 'text'}]}]))
        self.assertNotIn('columnLayout', value['blocks'][1])
        image = value['blocks'][1]['children'][0]
        for key in ('imageWidth', 'imageRatio', 'imageFit', 'imageMaxWidth', 'title', 'titleStyle'):
            self.assertNotIn(key, image)
        self.assertEqual(image['caption'], 'Legacy')
        self.assertEqual(validate_layout(value), value)

    def test_mixed_media_ownership_validation_remains_atomic(self):
        media = self.image(self.other)
        layout = self.layout([{'id': 'cols', 'type': 'columns', 'columnLayout': 'wide-left', 'children': [
            {'id': 'image', 'type': 'image', 'mediaId': media.id, 'imageWidth': 50}, {'id': 'text', 'type': 'text'}]}])
        before = self.product.bpi_technical_description
        with self.assertRaises(MissingError):
            self.service.save_content(self.product, {'technicalDescription': '<p>Wrong</p>', 'descriptionLayout': layout})
        self.assertEqual(self.product.bpi_technical_description, before)

    def test_two_public_video_players_render_no_external_iframes(self):
        self.product.write({'is_published': True, 'bpi_description_layout': self.layout([
            {'id': 'cols', 'type': 'columns', 'columnLayout': 'media', 'children': [
                {'id': 'a', 'type': 'video', 'url': 'https://youtu.be/abcdefghijk', 'title': '<script>unsafe</script>'},
                {'id': 'b', 'type': 'video', 'url': 'https://www.instagram.com/reel/abcdef/', 'videoRatio': '9:16'}]}])})
        projected = self.product._bpi_public_description_layout(self.website)
        html = str(self.env['ir.qweb']._render('bader_product_intelligence.description_layout', {'product': self.product, 'bpi_layout': projected}))
        self.assertNotIn('<iframe', html)
        self.assertNotIn('<script>unsafe', html)
        self.assertIn('bpi-layout__columns--media', html)
        self.assertIn('target="_blank"', html)
        self.assertIn('data-bpi-video-embed="https://www.youtube-nocookie.com/embed/abcdefghijk"', html)
        self.assertIn('Texto principal aprobado.', html)

    def test_media_composition_enforces_total_blocks_limit(self):
        blocks = [{'id': 'd%s' % i, 'type': 'divider'} for i in range(49)]
        validate_layout(self.layout(blocks))
        with self.assertRaises(ValidationError):
            validate_layout(self.layout(blocks + [{'id': 'excess', 'type': 'divider'}]))

    def test_auxiliary_rich_styles_and_links_survive_save_and_public_projection(self):
        html = '<h2 style="font-family: Bader Sans; font-size: 32px; text-align: center">Detalle</h2><p style="color: #003841; background-color: #fff2a8; margin-left: 40px"><u>Texto</u> <a href="https://example.com/manual" target="evil" rel="opener">Manual</a></p>'
        clean = auxiliary_html(html)
        for expected in ("Bader Sans", "32px", "text-align: center", "background-color", "margin-left", 'rel="noopener noreferrer"', 'target="_blank"', '<u>Texto</u>'):
            self.assertIn(expected, clean)
        self.assertNotIn('opener"', clean)
        layout = self.layout([{'id': 'rich', 'type': 'text', 'html': html}])
        self.service.save_content(self.product, {'descriptionLayout': layout, 'editorialRevision': self.product.bpi_editorial_revision})
        self.product.write({'website_published': True})
        saved = self.product.bpi_description_layout
        public = self.product._bpi_public_description_layout(self.website)
        self.assertIn('32px', str(public))
        self.assertIn('noopener noreferrer', str(public))
        self.assertEqual(self.product.bpi_description_layout, saved)

    def test_auxiliary_styles_reject_css_and_active_link_attacks(self):
        payload = '<p id="evil" style="position:fixed; background:url(https://evil.test); color:expression(x); font-family:evil; font-size:9999px; text-align:center; --x:url(evil)">Safe</p><svg><script>bad()</script></svg>'
        clean = auxiliary_html(payload)
        self.assertIn('text-align: center', clean)
        for bad in ('position', 'url(', 'expression', '9999', 'evil', 'bad()', '<svg'):
            self.assertNotIn(bad, clean)
        for url in ('javascript:alert(1)', 'data:text/html,foo', '//evil.test', 'https://user:secret@host.test', 'https://x.test/\\evil', 'https://[invalid'):
            self.assertNotIn('href=', auxiliary_html('<a href="%s" onclick="bad()" target="x">Click</a>' % url))

    def test_auxiliary_formatting_is_idempotent_bounded_and_legacy_text_literal(self):
        html = '<p><span style="font-family:Helvetica Neue LT Pro;font-size:31px;font-weight:700;font-style:italic;text-decoration:underline">A &amp; B</span></p><ol><li>Uno</li><li>Dos</li></ol>'
        clean = auxiliary_html(html)
        self.assertEqual(auxiliary_html(clean), clean)
        self.assertIn('31px', clean)
        with self.assertRaises(ValidationError):
            auxiliary_html('á' * 10001)
        media = self.image()
        layout = validate_layout(self.layout([{'id':'img', 'type':'image', 'mediaId':media.id, 'caption':'<b>Literal</b>'}]))
        self.assertEqual(layout['blocks'][1]['caption'], '<b>Literal</b>')
