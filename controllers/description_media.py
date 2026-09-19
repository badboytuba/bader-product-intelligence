# -*- coding: utf-8 -*-
"""Authenticated upload transport and publication-gated Nginx media delivery."""
import json
import os

from odoo import http
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.http import content_disposition, request

from ..models.description_layout import CHUNK_SIZE, layout_media_ids


class DescriptionMediaController(http.Controller):
    def _model(self, context=None):
        model = request.env['bpi.description.media']
        model._ensure_manager()
        if context:
            if isinstance(context, str):
                try:
                    context = json.loads(context)
                except (ValueError, TypeError):
                    raise AccessError('Contexto no válido.')
            if not isinstance(context, dict):
                raise AccessError('Contexto no válido.')
            companies = context.get('allowed_company_ids')
            if companies is not None:
                if not isinstance(companies, list) or not companies or any(isinstance(value, bool) or not isinstance(value, int) for value in companies) or not set(companies).issubset(set(request.env.user.company_ids.ids)):
                    raise AccessError('Empresas no permitidas.')
                model = model.with_context(allowed_company_ids=companies)
        return model

    def _record(self, media_id, context=None):
        model = self._model(context)
        record = model.browse(media_id).exists()
        if not record:
            raise MissingError('Archivo no encontrado.')
        record.check_access_rights('read'); record.check_access_rule('read')
        model.env['bpi.service']._meli_product(record.product_id.id)
        return record

    @http.route('/bader_product_intelligence/description_media/start', type='json', auth='user', methods=['POST'])
    def start(self, product_tmpl_id, filename, size, kind, **kwargs):
        model = self._model()
        product = model.env['bpi.service']._meli_product(product_tmpl_id)
        record = model._start(product, filename, size, kind)
        return dict(record._payload(), csrfToken=request.csrf_token(), chunkSize=CHUNK_SIZE)

    @http.route('/bader_product_intelligence/description_media/video_poster', type='json', auth='user', methods=['POST'])
    def video_poster(self, product_tmpl_id, url, **kwargs):
        model = self._model()
        product = model.env['bpi.service']._meli_product(product_tmpl_id)
        return {'media': model._youtube_poster(product, url)}

    @http.route('/bader_product_intelligence/description_media/list', type='json', auth='user', methods=['POST'])
    def list_media(self, product_tmpl_id, **kwargs):
        model = self._model()
        product = model.env['bpi.service']._meli_product(product_tmpl_id)
        records = model.search([('product_id', '=', product.id), ('state', '!=', 'rejected')], limit=200)
        return {'media': [record._payload() for record in records], 'csrfToken': request.csrf_token()}

    @http.route('/bader_product_intelligence/description_media/<int:media_id>/chunk', type='http', auth='user', methods=['POST'], csrf=True)
    def chunk(self, media_id, offset=None, context=None, **kwargs):
        try:
            record = self._record(media_id, context)
            upload = request.httprequest.files.get('file')
            if not upload or request.httprequest.content_length is None or request.httprequest.content_length > CHUNK_SIZE + 65536:
                raise ValidationError('Fragmento no válido o demasiado grande.')
            if not isinstance(offset, str) or not offset.isdigit():
                raise ValidationError('Posición del fragmento no válida.')
            data = record._chunk(int(offset), upload.stream)
            return request.make_json_response(data)
        except (AccessError, MissingError):
            request.env.cr.rollback()
            return request.make_json_response({'error': 'Archivo no disponible.'}, status=404)
        except (UserError, ValidationError) as error:
            request.env.cr.rollback()
            return request.make_json_response({'error': str(error)}, status=400)

    @http.route('/bader_product_intelligence/description_media/<int:media_id>/complete', type='json', auth='user', methods=['POST'])
    def complete(self, media_id, **kwargs):
        return self._record(media_id)._complete()

    @http.route('/bader_product_intelligence/description_media/<int:media_id>/remove', type='json', auth='user', methods=['POST'])
    def remove(self, media_id, **kwargs):
        self._record(media_id).unlink()
        return {'success': True}

    def _deliver(self, media):
        path = media._path()
        if media.state != 'ready' or not os.path.isfile(path):
            return request.not_found()
        # Nginx internal alias; the private path is never returned in the body.
        internal = '/_bpi_private_media/%s/%s' % (os.path.basename(os.path.dirname(path)), media.storage_key)
        return request.make_response(b'', headers=[
            ('X-Accel-Redirect', internal), ('Content-Type', media.mimetype),
            ('Content-Disposition', content_disposition(media.name, 'inline')),
            ('X-Content-Type-Options', 'nosniff'), ('Cache-Control', 'private, no-store'),
            ('Content-Security-Policy', "default-src 'none'; media-src 'self'; img-src 'self'; frame-ancestors 'self'"),
            ('Referrer-Policy', 'no-referrer'),
        ])

    @http.route('/bader_product_intelligence/description_media/<int:media_id>/preview', type='http', auth='user', methods=['GET', 'HEAD'], sitemap=False)
    def preview(self, media_id, **kwargs):
        try:
            return self._deliver(self._record(media_id))
        except (AccessError, MissingError):
            return request.not_found()

    @http.route('/bader_product_intelligence/description_media/<int:media_id>/file', type='http', auth='public', website=True, methods=['GET', 'HEAD'], sitemap=False)
    def public_file(self, media_id, r=None, **kwargs):
        try:
            # Read only the parent identity first, then apply the same public
            # template/website/company/publication access gate as the documents.
            request.env.cr.execute('SELECT product_id FROM bpi_description_media WHERE id=%s AND state=%s', (media_id, 'ready'))
            row = request.env.cr.fetchone()
            if not row:
                return request.not_found()
            product = request.env['product.template'].browse(row[0]).exists()
            if not product or not product._bpi_visible_documents(request.website) or not product._bpi_plain_text(product.bpi_technical_description).strip() or str(product.bpi_editorial_revision or 1) != r:
                return request.not_found()
            layout = product.bpi_description_layout or {}
            if not layout.get('enabled') or media_id not in layout_media_ids(layout):
                return request.not_found()
            # Scoped elevation of one approved reference AFTER all public gates.
            media = request.env['bpi.description.media'].sudo().browse(media_id)
            return self._deliver(media)
        except (AccessError, MissingError):
            return request.not_found()
