# -*- coding: utf-8 -*-
import base64

from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request, content_disposition


class ProductDocuments(http.Controller):
    @http.route('/bader_product_intelligence/documents/<int:product_id>/<string:slot>',
                type='http', auth='public', website=True, methods=['GET'], sitemap=False)
    def document(self, product_id, slot, v=None, **kw):
        if slot not in ('cover','1','2','3'):
            return request.not_found()
        try:
            product = request.env['product.template'].browse(product_id).exists()
            if not product:
                return request.not_found()
            manager = request.env.user.has_group('base.group_system')
            if manager:
                product = request.env['bpi.service']._meli_product(product_id)
                panel = request.env['bpi.product.document.panel'].search([('product_id','=',product.id)],limit=1)
            else:
                if not product._bpi_visible_documents(request.website):
                    return request.not_found()
                panel = request.env['bpi.product.document.panel'].sudo().search([('product_id','=',product.id)],limit=1)
            if not panel or (v is not None and str(panel.revision) != v):
                return request.not_found()
            if slot == 'cover':
                if not any(b['label'] for b in panel.buttons) and not manager:
                    return request.not_found()
                data, filename, mimetype = panel.cover, 'portada.png', 'image/png'
            else:
                button = panel.buttons[int(slot)-1]
                if button['kind'] != 'file' or not button['label'] or not button['size']:
                    return request.not_found()
                data, filename, mimetype = panel['file_'+slot], button['filename'], 'application/pdf'
            if not data:
                return request.not_found()
            body = base64.b64decode(data)
            return request.make_response(body, headers=[
                ('Content-Type',mimetype), ('Content-Length',str(len(body))),
                ('Content-Disposition',content_disposition(filename,'inline')),
                ('X-Content-Type-Options','nosniff'), ('Cache-Control','private, no-store'),
                ('Content-Security-Policy',"sandbox; default-src 'none'; frame-ancestors 'self'"),
                ('Referrer-Policy','no-referrer'),
            ])
        except (AccessError,MissingError):
            return request.not_found()
