# -*- coding: utf-8 -*-
"""Private Studio routes. No route here changes product content/publication."""
import json

from odoo import http, _
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.http import request

from ..models.content_studio import MAX_FILE


class ContentStudioController(http.Controller):
    def _service(self, upload=False):
        env = request.env
        # JSON-RPC already propagates params.context through the Odoo dispatcher.
        # Multipart uploads need the captured user company context explicitly.
        if upload:
            raw = request.httprequest.form.get('context', '{}')
            try:
                context = json.loads(raw)
            except (ValueError, TypeError) as error:
                raise ValidationError(_('El contexto de empresa no es válido.')) from error
            if not isinstance(context, dict):
                raise ValidationError(_('El contexto de empresa no es válido.'))
            allowed = context.get('allowed_company_ids', env.companies.ids)
            if not isinstance(allowed, list) or any(isinstance(i, bool) or not isinstance(i, int) or i not in env.user.company_ids.ids for i in allowed):
                raise AccessError(_('Empresa no disponible.'))
            env = env(context=dict(env.context, allowed_company_ids=allowed))
        service = env['bpi.service']
        service._ensure_manager()
        return service

    @http.route('/bader_product_intelligence/content_studio/open', type='json', auth='user')
    def open_studio(self, product_tmpl_id, session_id=False, new_session=False, **kw):
        return self._service()._studio_open(product_tmpl_id, session_id, new_session)

    @http.route('/bader_product_intelligence/content_studio/strategies', type='json', auth='user')
    def strategies(self, product_tmpl_id, search='', **kw):
        return self._service()._studio_strategy_options(product_tmpl_id, search)

    @http.route('/bader_product_intelligence/content_studio/reuse_strategy', type='json', auth='user')
    def reuse_strategy(self, product_tmpl_id, source_session_id, source_revision, brief, reviewed=False, **kw):
        return self._service()._studio_reuse_strategy(product_tmpl_id, source_session_id, source_revision, brief, reviewed)

    @http.route('/bader_product_intelligence/content_studio/activate', type='json', auth='user')
    def activate(self, product_tmpl_id, **kw):
        return self._service()._studio_activate(product_tmpl_id)

    @http.route('/bader_product_intelligence/content_studio/save_brief', type='json', auth='user')
    def save_brief(self, product_tmpl_id, session_id, revision, brief, **kw):
        return self._service()._studio_save_brief(product_tmpl_id, session_id, revision, brief)

    @http.route('/bader_product_intelligence/content_studio/add_source', type='json', auth='user')
    def add_source(self, product_tmpl_id, session_id, revision, kind='text', name='', text='', url='', **kw):
        return self._service()._studio_add_source(product_tmpl_id, session_id, revision, kind, name=name, text=text, url=url)

    @http.route('/bader_product_intelligence/content_studio/upload_source', type='http', auth='user', methods=['POST'], csrf=True)
    def upload_source(self, **kw):
        try:
            service = self._service(upload=True)
            form = request.httprequest.form
            product_id, session_id, revision = (int(form.get(k, '0')) for k in ('product_tmpl_id', 'session_id', 'revision'))
            # Authorize before reading a potentially large body.
            service._studio_session(product_id, session_id)
            upload = request.httprequest.files.get('file')
            if not upload:
                raise ValidationError(_('Selecciona un archivo.'))
            body = upload.read(MAX_FILE + 1)
            result = service._studio_add_source(product_id, session_id, revision, 'file',
                name=form.get('name', '') or upload.filename, filename=upload.filename or '', raw=body)
            return request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json'), ('Cache-Control', 'no-store')])
        except (AccessError, MissingError, UserError, ValidationError, ValueError) as error:
            # HTTP dispatch does not roll back on a handled exception.
            request.env.cr.rollback()
            message = str(error) if isinstance(error, UserError) else _('No se pudo añadir el archivo. Comprueba producto, empresa y formato.')
            return request.make_response(json.dumps({'error': message}), headers=[('Content-Type', 'application/json'), ('Cache-Control', 'no-store')], status=400)

    @http.route('/bader_product_intelligence/content_studio/remove_source', type='json', auth='user')
    def remove_source(self, product_tmpl_id, session_id, revision, source_id, **kw):
        return self._service()._studio_remove_source(product_tmpl_id, session_id, revision, source_id)

    @http.route('/bader_product_intelligence/content_studio/review_source', type='json', auth='user')
    def review_source(self, product_tmpl_id, session_id, revision, source_id, action, fact_ids=None, **kw):
        return self._service()._studio_review_source(product_tmpl_id, session_id, revision, source_id, action, fact_ids)

    @http.route('/bader_product_intelligence/content_studio/convert_link', type='json', auth='user')
    def convert_link(self, product_tmpl_id, session_id, revision, source_id, **kw):
        return self._service()._studio_convert_link(product_tmpl_id, session_id, revision, source_id)

    @http.route('/bader_product_intelligence/content_studio/process_source', type='json', auth='user')
    def process_source(self, product_tmpl_id, session_id, revision, source_id, request_key, **kw):
        return self._service()._studio_start(product_tmpl_id, session_id, revision, '', request_key, source_id=source_id)

    @http.route('/bader_product_intelligence/content_studio/start', type='json', auth='user')
    def start(self, product_tmpl_id, session_id, revision, message='', request_key='', draft=None, review_proposal_id=False, **kw):
        return self._service()._studio_start(product_tmpl_id, session_id, revision, message, request_key, draft=draft, review_proposal_id=review_proposal_id)

    @http.route('/bader_product_intelligence/content_studio/status', type='json', auth='user')
    def status(self, product_tmpl_id, session_id, **kw):
        service = self._service()
        return service._studio_envelope(service._studio_session(product_tmpl_id, session_id))

    @http.route('/bader_product_intelligence/content_studio/proposal', type='json', auth='user')
    def proposal(self, product_tmpl_id, session_id, proposal_id, **kw):
        service = self._service()
        session = service._studio_session(product_tmpl_id, session_id)
        result = session.proposal_ids.filtered(lambda p: p.id == proposal_id)
        if not result:
            raise MissingError(_('Propuesta no encontrada.'))
        return result._payload()

    @http.route('/bader_product_intelligence/content_studio/prepare_apply', type='json', auth='user')
    def prepare_apply(self, product_tmpl_id, session_id, proposal_id, selected=None, edits=None, **kw):
        return self._service()._studio_prepare_apply(product_tmpl_id, session_id, proposal_id, selected, edits)
