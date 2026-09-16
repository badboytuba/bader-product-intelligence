# -*- coding: utf-8 -*-
"""Private per-product assets with an explicitly curated website projection."""
import base64
import io
import ipaddress
import re
from urllib.parse import urlsplit, urlunsplit

from PIL import Image
from PyPDF2 import PdfFileReader
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError, UserError

MAX_PDF = 10 * 1024 * 1024
MAX_COVER = 2 * 1024 * 1024


def document_url(value):
    if not isinstance(value, str) or len(value) > 2048 or re.search(r'[\x00-\x20\\]', value):
        raise ValidationError(_('Usa un enlace HTTPS público válido.'))
    try:
        url = urlsplit(value)
        host = (url.hostname or '').encode('idna').decode('ascii').lower()
        if url.scheme != 'https' or not host or url.username or url.password or url.port not in (None, 443):
            raise ValueError()
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            if '.' not in host or re.fullmatch(r'[0-9.]+', host) or host.startswith('0x') or host.endswith(('.local', '.localhost', '.internal', '.test', '.invalid')):
                raise ValueError()
        else:
            if not address.is_global:
                raise ValueError()
        return urlunsplit(('https', url.netloc, url.path, url.query, url.fragment))
    except (ValueError, UnicodeError):
        raise ValidationError(_('Usa un enlace HTTPS público, sin credenciales ni direcciones internas.'))


def decode_upload(value, limit):
    if not isinstance(value, (str, bytes)) or len(value) > ((limit + 2) // 3) * 4:
        raise ValidationError(_('El archivo supera el límite permitido.'))
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, TypeError):
        raise ValidationError(_('El archivo no es válido.'))
    if not raw or len(raw) > limit:
        raise ValidationError(_('El archivo está vacío o supera el límite permitido.'))
    return raw


def pdf_upload(value):
    raw = decode_upload(value, MAX_PDF)
    if not raw.startswith(b'%PDF-'):
        raise ValidationError(_('Solo se permiten documentos PDF.'))
    try:
        reader = PdfFileReader(io.BytesIO(raw), strict=True)
        if reader.isEncrypted or not 0 < reader.getNumPages() <= 500:
            raise ValueError()
        # Inspect the object graph without decompressing arbitrary content streams.
        seen, count = set(), [0]
        forbidden = {'/JavaScript', '/JS', '/Launch', '/OpenAction', '/AA', '/EmbeddedFiles',
                     '/EF', '/XFA', '/RichMedia', '/SubmitForm', '/ImportData', '/GoToR',
                     '/Rendition', '/Sound', '/Movie', '/FileAttachment'}
        def visit(obj):
            obj = obj.getObject() if hasattr(obj, 'getObject') else obj
            key = id(obj)
            if key in seen:
                return
            seen.add(key); count[0] += 1
            if count[0] > 30000:
                raise ValueError()
            if isinstance(obj, dict):
                if any(str(k) in forbidden or (isinstance(v, str) and str(v) in forbidden) for k, v in obj.items()):
                    raise ValueError()
                if '/URI' in obj:
                    document_url(str(obj['/URI']))
                for child in obj.values():
                    visit(child)
            elif isinstance(obj, (list, tuple)):
                for child in obj:
                    visit(child)
        visit(reader.trailer)
    except Exception:
        raise ValidationError(_('El PDF está dañado, protegido o contiene funciones activas no admitidas. Exporta una versión PDF estática.'))
    return base64.b64encode(raw), len(raw)


def cover_upload(value):
    raw = decode_upload(value, MAX_COVER)
    try:
        with Image.open(io.BytesIO(raw)) as source:
            if source.format not in ('PNG', 'JPEG', 'WEBP') or source.width * source.height > 16000000 or getattr(source, 'is_animated', False):
                raise ValueError()
            source.load()
            source.thumbnail((1000, 1000))
            image = source.convert('RGBA')
            buffer = io.BytesIO(); image.save(buffer, 'PNG')
        return base64.b64encode(buffer.getvalue())
    except Exception:
        raise ValidationError(_('La portada debe ser una imagen JPG, PNG o WebP estática de hasta 2 MB.'))


def empty_panel():
    return {'revision': 0, 'title': '', 'intro': '', 'coverUrl': '', 'buttons': [
        {'label': '', 'kind': 'url', 'url': '', 'filename': '', 'size': 0, 'hasFile': False, 'fileUrl': ''}
        for unused in range(3)]}


class ProductDocumentPanel(models.Model):
    _name = 'bpi.product.document.panel'
    _description = 'Catálogos y documentos del producto'

    product_id = fields.Many2one('product.template', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='product_id.company_id', store=True, index=True)
    title = fields.Char()
    intro = fields.Text()
    buttons = fields.Json(default=list)
    cover = fields.Binary(attachment=True)
    file_1 = fields.Binary(attachment=True)
    file_2 = fields.Binary(attachment=True)
    file_3 = fields.Binary(attachment=True)
    revision = fields.Integer(default=1, readonly=True)
    _sql_constraints = [('product_unique', 'unique(product_id)', 'El producto ya tiene un bloque de documentos.')]

    def _guard(self, product):
        product = self.env['bpi.service']._meli_product(product.id)
        product.check_access_rights('write'); product.check_access_rule('write')
        return product

    def _prepare(self, values, record=None):
        values = dict(values)
        if set(values) - {'product_id', 'title', 'intro', 'buttons', 'cover', 'file_1', 'file_2', 'file_3'}:
            raise ValidationError(_('Campos de documentos no permitidos.'))
        for name, maximum in (('title', 120), ('intro', 600)):
            if name in values:
                if not isinstance(values[name], str) or len(values[name]) > maximum:
                    raise ValidationError(_('El título o la presentación supera el límite permitido.'))
                values[name] = values[name].strip()
        if values.get('cover'):
            values['cover'] = cover_upload(values['cover'])
        buttons = values.get('buttons', record.buttons if record else []) or []
        if not isinstance(buttons, list) or len(buttons) != 3:
            raise ValidationError(_('Se requieren tres posiciones de documento.'))
        prepared, total = [], 0
        for index, row in enumerate(buttons, 1):
            if not isinstance(row, dict) or set(row) - {'label', 'kind', 'url', 'filename', 'size'}:
                raise ValidationError(_('El documento no es válido.'))
            label, kind, url = row.get('label', ''), row.get('kind', 'url'), row.get('url', '')
            if not isinstance(label, str) or len(label) > 70 or kind not in ('url', 'file') or not isinstance(url, str):
                raise ValidationError(_('Completa una etiqueta válida y el tipo de documento.'))
            label = label.strip(); field = 'file_%s' % index
            old = (record.buttons or [])[index - 1] if record and len(record.buttons or []) == 3 else {}
            filename, size = '', 0
            if kind == 'file':
                if values.get(field):
                    values[field], size = pdf_upload(values[field])
                    filename = row.get('filename', '')
                    if not isinstance(filename, str) or not filename.lower().endswith('.pdf'):
                        raise ValidationError(_('El nombre del documento debe terminar en .pdf.'))
                    filename = re.sub(r'[^\w .()-]', '_', filename)[:140]
                elif field not in values and record and record.with_context(bin_size=True)[field]:
                    filename, size = old.get('filename', 'documento.pdf'), old.get('size', 0)
                if not size or not label:
                    raise ValidationError(_('Para cada PDF, indica el texto del botón y sube el archivo.'))
                url = ''
            else:
                values[field] = False
                if bool(label) != bool(url):
                    raise ValidationError(_('Completa el texto y el enlace del botón, o deja ambos vacíos.'))
                url = document_url(url) if url else ''
            total += size
            prepared.append({'label': label, 'kind': kind, 'url': url, 'filename': filename, 'size': size})
        if total > 20 * 1024 * 1024:
            raise ValidationError(_('El total de documentos no puede superar 20 MB.'))
        values['buttons'] = prepared
        return values

    @api.model_create_multi
    def create(self, values_list):
        prepared = []
        for values in values_list:
            self._guard(self.env['product.template'].browse(values.get('product_id')))
            prepared.append(dict(self._prepare(values), revision=1))
        return super().create(prepared)

    def write(self, values):
        if 'product_id' in values:
            raise ValidationError(_('No se puede reasignar el bloque a otro producto.'))
        for record in self:
            record._guard(record.product_id)
            super(ProductDocumentPanel, record).write(dict(record._prepare(values, record), revision=record.revision + 1))
        return True

    def unlink(self):
        for record in self:
            record._guard(record.product_id)
        self.env['ir.attachment'].search([
            ('res_model','=',self._name),('res_id','in',self.ids),
            ('res_field','in',['cover','file_1','file_2','file_3']),
        ]).unlink()
        return super().unlink()

    def _payload(self):
        self.ensure_one()
        data = empty_panel()
        data.update(revision=self.revision, title=self.title or '', intro=self.intro or '')
        base = '/bader_product_intelligence/documents/%s/' % self.product_id.id
        data['coverUrl'] = base + 'cover?v=%s' % self.revision if self.with_context(bin_size=True).cover else ''
        for index, button in enumerate(self.buttons, 1):
            data['buttons'][index - 1].update(button, hasFile=bool(button.get('size')),
                fileUrl=base + '%s?v=%s' % (index, self.revision) if button.get('size') else '')
        return data

    @api.model
    def _save_panel(self, product, data):
        self._guard(product)
        if not isinstance(data, dict) or set(data) - {'revision','title','intro','buttons','cover','coverUrl'}:
            raise ValidationError(_('Bloque de documentos inválido.'))
        revision = data.get('revision')
        if type(revision) is not int or revision < 0:
            raise ValidationError(_('Revisión de documentos inválida.'))
        # Serialize creation and edits on the parent, including concurrent first saves.
        self.env.cr.execute('UPDATE product_template SET write_date=write_date WHERE id=%s', [product.id])
        panel = self.search([('product_id','=',product.id)])
        if revision != (panel.revision if panel else 0):
            raise UserError(_('Los documentos cambiaron. Conservamos tus borradores; recarga antes de guardar.'))
        values = {key:data.get(key,'') for key in ('title','intro')}
        buttons = data.get('buttons')
        if not isinstance(buttons, list) or len(buttons) != 3:
            raise ValidationError(_('Se requieren tres posiciones de documento.'))
        values['buttons'] = []
        for index, row in enumerate(buttons,1):
            if not isinstance(row,dict) or set(row)-{'label','kind','url','filename','size','hasFile','fileUrl','upload'}:
                raise ValidationError(_('El documento no es válido.'))
            values['buttons'].append({k:row[k] for k in ('label','kind','url','filename') if k in row})
            if 'upload' in row:
                values['file_%s'%index] = row['upload']
        if 'cover' in data:
            values['cover'] = data['cover']
        prepared = self._prepare(values, panel)
        if panel:
            # Unchanged content saves must not invalidate open document drafts.
            if all((panel[k] or '') == (v or '') for k,v in prepared.items() if k not in ('file_1','file_2','file_3','cover')) and not any(k in values for k in ('file_1','file_2','file_3','cover')):
                return
            panel.write(values)
        elif any(row['label'] for row in prepared['buttons']) or values['title'] or values['intro'] or values.get('cover'):
            self.create(dict(values,product_id=product.id))


class DocumentProduct(models.Model):
    _inherit = 'product.template'

    def bpi_build_payload(self):
        result = super().bpi_build_payload()
        panel = self.env['bpi.product.document.panel'].search([('product_id','=',self.id)])
        result['documents'] = panel._payload() if panel else empty_panel()
        return result

    def _bpi_visible_documents(self, website):
        self.ensure_one()
        self.check_access_rights('read'); self.check_access_rule('read')
        return bool(website and website._name == 'website' and self.active and self.sale_ok and self.website_published
            and (not self.website_id or self.website_id == website)
            and (not self.company_id or self.company_id == website.company_id))

    def _bpi_public_document_panel(self, website):
        if not self._bpi_visible_documents(website):
            return False
        # Narrow elevation after product/website/company/publication checks.
        panel = self.env['bpi.product.document.panel'].sudo().search([('product_id','=',self.id)],limit=1)
        if not panel:
            return False
        data = panel._payload()
        data['buttons'] = [row for row in data['buttons'] if row['label'] and (row['url'] or row['fileUrl'])]
        return data if data['buttons'] else False


class DocumentService(models.AbstractModel):
    _inherit = 'bpi.service'

    @api.model
    def save_content(self, product, values):
        product = self._meli_product(product.id)
        with self.env.cr.savepoint():
            if isinstance(values,dict) and 'documents' in values:
                self.env['bpi.product.document.panel']._save_panel(product, values['documents'])
            return super().save_content(product,values)
