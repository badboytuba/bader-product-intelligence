# -*- coding: utf-8 -*-
"""Versioned long-copy composition and private, bounded media.

The main block is a reference, never another copy of the product's long text.
Media are deliberately not attachments: arbitrary /web/content URLs must not
bypass the current-layout/publication checks in the delivery controller.
"""
import hashlib
import io
import json
import math
import os
import re
import selectors
import shutil
import subprocess
import time
import uuid
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

from lxml import html as lxml_html
from markupsafe import Markup
from PIL import Image, ImageOps

from odoo import _, api, fields, models, tools
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError

MIB = 1024 * 1024
CHUNK_SIZE = MIB
MAX_IMAGE = 10 * MIB
MAX_VIDEO = 200 * MIB
QUOTA = 1024 * MIB
MIN_FREE = 3 * 1024 * MIB
QUOTA_LOCK = 1870193301
_REVISION_GUARD = object()
EDITORIAL_FIELDS = frozenset({
    'name', 'description_sale', 'bpi_ai_generated_description', 'bpi_technical_description',
    'bpi_description_layout', 'bpi_content_template_id', 'bpi_ai_target_audience',
    'bpi_ai_tone', 'website_meta_title', 'website_meta_description', 'website_meta_keywords',
    'bpi_geo_title', 'bpi_geo_description', 'bpi_geo_features', 'bpi_keyword_ids', 'bpi_faq_ids',
})


def empty_layout():
    return {'version': 1, 'enabled': False, 'blocks': [{'id': 'principal', 'type': 'main'}]}


def social_video(value):
    """Canonical allowlisted links. No fetch, API, iframe code or tracking URL."""
    if not isinstance(value, str) or len(value) > 2048 or re.search(r'[\x00-\x20\\]', value):
        raise ValidationError(_('Usa un enlace público de YouTube, TikTok, Instagram o Facebook.'))
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or '').lower().removeprefix('www.')
        if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443):
            raise ValueError()
        if host in ('youtube.com', 'm.youtube.com', 'youtu.be'):
            video_id = parsed.path.strip('/') if host == 'youtu.be' else parse_qs(parsed.query).get('v', [''])[0]
            if not video_id and parsed.path.startswith(('/shorts/', '/embed/', '/live/')):
                video_id = parsed.path.split('/')[2]
            if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
                raise ValueError()
            return {'url': 'https://www.youtube.com/watch?v=' + video_id,
                    'provider': 'youtube', 'embed': 'https://www.youtube-nocookie.com/embed/' + video_id}
        if host in ('tiktok.com', 'm.tiktok.com'):
            match = re.fullmatch(r'/@[^/]+/video/([0-9]{10,25})/?', parsed.path)
            if not match:
                raise ValueError()
            return {'url': 'https://www.tiktok.com' + parsed.path.rstrip('/'), 'provider': 'tiktok',
                    'embed': 'https://www.tiktok.com/player/v1/' + match.group(1)}
        if host == 'instagram.com':
            if not re.fullmatch(r'/(?:p|reel|tv)/[A-Za-z0-9_-]{3,100}/?', parsed.path):
                raise ValueError()
            return {'url': 'https://www.instagram.com' + parsed.path.rstrip('/') + '/',
                    'provider': 'instagram', 'embed': ''}
        if host in ('facebook.com', 'm.facebook.com', 'fb.watch') and parsed.path.strip('/'):
            canonical = 'https://' + host + parsed.path
            if parsed.path.rstrip('/') == '/watch':
                video_id = parse_qs(parsed.query).get('v', [''])[0]
                if not re.fullmatch(r'[0-9]{3,30}', video_id):
                    raise ValueError()
                canonical += '?v=' + video_id
            return {'url': canonical, 'provider': 'facebook', 'embed': ''}
    except (ValueError, IndexError):
        pass
    raise ValidationError(_('Enlace de vídeo no admitido. Usa la dirección pública de la publicación.'))


def auxiliary_html(value):
    """Tiny text-only dialect. Discard active nodes instead of promoting children."""
    if not isinstance(value, str) or len(value.encode('utf-8')) > 20000:
        raise ValidationError(_('El texto del bloque no es válido o supera 20 KB.'))
    try:
        root = lxml_html.fragment_fromstring(value or '<p/>', create_parent='div')
    except (ValueError, TypeError):
        raise ValidationError(_('El texto del bloque no es válido.'))
    allowed = {'p', 'br', 'strong', 'b', 'em', 'i', 'u', 'ul', 'ol', 'li', 'h3', 'h4', 'blockquote'}
    for node in list(root.iterdescendants()):
        if not isinstance(node.tag, str):
            node.drop_tree()
        elif node.tag.lower() in ('script', 'style', 'iframe', 'object', 'embed', 'svg', 'math', 'form', 'input', 'video', 'audio'):
            node.drop_tree()
        elif node.tag.lower() not in allowed:
            node.drop_tag()
        else:
            node.attrib.clear()
    return str(Markup.escape(root.text or '')) + ''.join(lxml_html.tostring(child, encoding='unicode') for child in root)


def validate_layout(value, media_lookup=None):
    if value is None or value is False:
        return empty_layout()
    if not isinstance(value, dict) or set(value) - {'version', 'enabled', 'blocks'} or type(value.get('version')) is not int or value.get('version') != 1:
        raise ValidationError(_('El diseño no es compatible. Recarga la ficha.'))
    if not isinstance(value.get('enabled'), bool) or not isinstance(value.get('blocks'), list):
        raise ValidationError(_('El diseño debe contener bloques válidos.'))
    try:
        size = len(json.dumps(value, ensure_ascii=False).encode('utf-8'))
    except (ValueError, TypeError, RecursionError):
        raise ValidationError(_('El diseño no es válido.'))
    if size > 150000:
        raise ValidationError(_('El diseño supera 150 KB.'))
    ids, count, mains = set(), [0], [0]
    common = {'id', 'type', 'preset', 'align', 'effect', 'spacing'}
    def visit(block, depth=0):
        if not isinstance(block, dict) or depth > 4:
            raise ValidationError(_('El diseño contiene demasiados niveles.'))
        count[0] += 1
        key, kind = block.get('id'), block.get('type')
        if count[0] > 50 or not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', key) or key in ids:
            raise ValidationError(_('Los bloques deben tener identificadores únicos; máximo 50 bloques.'))
        ids.add(key)
        accepted = {'main': set(), 'text': {'html'}, 'callout': {'html'},
                    'image': {'mediaId', 'alt', 'caption'}, 'video': {'mediaId', 'url', 'caption', 'posterMediaId', 'videoWidth', 'videoRatio'},
                    'columns': {'children'}, 'container': {'children'}, 'divider': set()}
        if not isinstance(kind, str) or kind not in accepted or set(block) - (common | accepted[kind]):
            raise ValidationError(_('Tipo o propiedades de bloque no permitidos.'))
        result = {'id': key, 'type': kind}
        for field, allowed, default in (
            ('preset', ('white', 'mist', 'petrol', 'lime'), 'white'),
            ('align', ('left', 'center'), 'left'), ('effect', ('none', 'lift'), 'none'),
            ('spacing', ('compact', 'normal', 'spacious'), 'normal')):
            current = block.get(field, default)
            if current not in allowed:
                raise ValidationError(_('Usa los estilos Bader disponibles.'))
            result[field] = current
        if kind == 'video':
            width = block.get('videoWidth', 100)
            ratio = block.get('videoRatio', 'auto')
            if type(width) is not int or not 25 <= width <= 100 or ratio not in ('auto', '16:9', '9:16', '1:1', '4:3'):
                raise ValidationError(_('Usa un ancho de 25 a 100 % y una proporción disponible.'))
            result.update(videoWidth=width, videoRatio=ratio)
            poster = block.get('posterMediaId')
            if poster:
                if type(poster) is not int or poster <= 0:
                    raise ValidationError(_('Portada no válida.'))
                if media_lookup:
                    media_lookup(poster, 'image')
                result['posterMediaId'] = poster
        if kind == 'main':
            mains[0] += 1
        if kind in ('text', 'callout'):
            result['html'] = auxiliary_html(block.get('html', ''))
        if kind in ('columns', 'container'):
            children = block.get('children', [])
            if not isinstance(children, list) or not 1 <= len(children) <= (2 if kind == 'columns' else 20):
                raise ValidationError(_('La composición debe contener bloques; las columnas admiten dos.'))
            result['children'] = [visit(child, depth + 1) for child in children]
        if kind in ('image', 'video'):
            media_id, url = block.get('mediaId'), block.get('url')
            if bool(media_id) == bool(url) or (kind == 'image' and url):
                raise ValidationError(_('Selecciona un archivo o un enlace de vídeo, no ambos.'))
            if media_id:
                if isinstance(media_id, bool) or not isinstance(media_id, int) or media_id <= 0:
                    raise ValidationError(_('Archivo no válido.'))
                if media_lookup:
                    media_lookup(media_id, kind)
                result['mediaId'] = media_id
            else:
                result['url'] = social_video(url)['url']
            for field, limit in (('caption', 500), ('alt', 500)):
                if field == 'alt' and kind != 'image':
                    continue
                text = block.get(field, '')
                if not isinstance(text, str) or len(text) > limit:
                    raise ValidationError(_('El texto de la imagen o del vídeo es demasiado largo.'))
                result[field] = text.strip()
        return result
    result = {'version': 1, 'enabled': value['enabled'], 'blocks': [visit(block) for block in value['blocks']]}
    if mains[0] != 1:
        raise ValidationError(_('El diseño debe incluir exactamente un bloque de texto principal.'))
    return result


def layout_media_ids(layout):
    result = set()
    def visit(blocks):
        for block in blocks:
            if block.get('mediaId'):
                result.add(block['mediaId'])
            if block.get('posterMediaId'):
                result.add(block['posterMediaId'])
            visit(block.get('children', []))
    visit((layout or {}).get('blocks', []))
    return result


def probe_video(path):
    """Fail closed, bounded ffprobe output/runtime; never invoke a shell."""
    binary = shutil.which('ffprobe')
    if not binary:
        raise UserError(_('La validación de vídeo no está disponible. Usa un enlace mientras se configura.'))
    with open(path, 'rb') as source:
        header = source.read(16)
    if len(header) < 16 or header[4:8] != b'ftyp' or header[8:12] not in (b'isom', b'iso2', b'iso4', b'iso5', b'iso6', b'mp41', b'mp42', b'M4V ', b'avc1', b'dash'):
        raise ValidationError(_('Usa un vídeo MP4 H.264/AAC, no un archivo de otro formato renombrado.'))
    try:
        process = subprocess.Popen([binary, '-v', 'error', '-protocol_whitelist', 'file', '-f', 'mov',
            '-show_entries', 'format=format_name,duration:stream=codec_type,codec_name,width,height',
            '-of', 'json', path], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError:
        raise UserError(_('La validación de vídeo no está disponible. Usa un enlace mientras se configura.'))
    output, deadline = bytearray(), time.monotonic() + 20
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                timeout = deadline - time.monotonic()
                if timeout <= 0 or not selector.select(timeout):
                    raise ValueError('probe timeout')
                chunk = os.read(process.stdout.fileno(), 8192)
                if not chunk:
                    break
                output.extend(chunk)
                if len(output) > 65536:
                    raise ValueError('probe output limit')
        if process.wait(timeout=max(.1, deadline - time.monotonic())):
            raise ValueError('invalid media')
        data = json.loads(output)
        streams = data.get('streams', [])
        video = [item for item in streams if item.get('codec_type') == 'video']
        audio = [item for item in streams if item.get('codec_type') == 'audio']
        if len(video) != 1 or video[0].get('codec_name') != 'h264' or any(item.get('codec_name') != 'aac' for item in audio):
            raise ValueError('unsupported codec')
        if any(item.get('codec_type') not in ('audio', 'video') for item in streams) or 'mp4' not in data.get('format', {}).get('format_name', '').split(','):
            raise ValueError('unsupported stream')
        duration = float(data['format']['duration'])
        if not math.isfinite(duration) or duration <= 0 or not 0 < video[0].get('width', 0) <= 7680 or not 0 < video[0].get('height', 0) <= 4320:
            raise ValueError('invalid dimensions')
        return {'mimetype': 'video/mp4', 'duration': duration, 'width': video[0]['width'], 'height': video[0]['height']}
    except (subprocess.SubprocessError, ValueError, KeyError, TypeError, OSError):
        raise ValidationError(_('El vídeo debe ser MP4 H.264 con audio AAC, hasta 200 MiB. No se convirtió el archivo.'))
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    bpi_description_layout = fields.Json(string='Diseño de descripción', copy=False)
    bpi_editorial_revision = fields.Integer(default=1, readonly=True, copy=False)

    def _bpi_lock_editorial_revision(self, expected=None):
        self.ensure_one()
        self.check_access_rights('write'); self.check_access_rule('write')
        self.flush_recordset(['bpi_editorial_revision'])
        self.env.cr.execute('SELECT bpi_editorial_revision FROM product_template WHERE id=%s FOR UPDATE', (self.id,))
        row = self.env.cr.fetchone()
        if not row:
            raise MissingError(_('Producto no encontrado.'))
        current = row[0] or 1
        self.invalidate_recordset(['bpi_editorial_revision'])
        if expected is not None and (isinstance(expected, bool) or not isinstance(expected, int) or current != expected):
            raise UserError(_('La ficha cambió durante la edición. Recarga y revisa los cambios antes de guardar.'))
        return current

    def _bpi_touch_editorial_revision(self):
        for product in self.sorted('id'):
            revision = product._bpi_lock_editorial_revision()
            super(ProductTemplate, product).write({'bpi_editorial_revision': revision + 1})
        return True

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            if 'bpi_description_layout' not in values and 'default_bpi_description_layout' in self.env.context:
                values['bpi_description_layout'] = self.env.context['default_bpi_description_layout']
            # Delegated product.product creation legitimately supplies template
            # defaults. Initial revision 1 is not a forged persisted revision.
            revision = values.get('bpi_editorial_revision', self.env.context.get('default_bpi_editorial_revision', 1))
            if type(revision) is not int or revision != 1:
                raise AccessError(_('La revisión editorial se administra automáticamente.'))
            values['bpi_editorial_revision'] = 1
            if values.get('bpi_description_layout') is not None and values.get('bpi_description_layout') is not False:
                self.env['bpi.service']._ensure_manager()
                layout = validate_layout(values['bpi_description_layout'])
                if layout_media_ids(layout):
                    raise ValidationError(_('Crea el producto antes de adjuntar sus archivos.'))
                values['bpi_description_layout'] = layout
        return super().create(values_list)

    def write(self, values):
        if 'bpi_editorial_revision' in values:
            raise AccessError(_('La revisión editorial se administra automáticamente.'))
        if not EDITORIAL_FIELDS.intersection(values):
            return super().write(values)
        for product in self.sorted('id'):
            revision = product._bpi_lock_editorial_revision()
            local = dict(values)
            if 'bpi_description_layout' in local:
                self.env['bpi.service']._ensure_manager()
                local['bpi_description_layout'] = validate_layout(local['bpi_description_layout'],
                    lambda media_id, kind: self.env['bpi.description.media']._for_product(product, media_id, kind))
            local['bpi_editorial_revision'] = revision + 1
            super(ProductTemplate, product).write(local)
        return True

    def bpi_build_payload(self):
        result = super().bpi_build_payload()
        result.update(descriptionLayout=self.bpi_description_layout or empty_layout(),
                      editorialRevision=self.bpi_editorial_revision or 1)
        return result

    def _bpi_public_description_layout(self, website):
        self.ensure_one()
        layout = self.bpi_description_layout
        if not layout or not layout.get('enabled') or not self._bpi_plain_text(self.bpi_technical_description).strip() or not self._bpi_visible_documents(website):
            return False
        def project(block):
            block = dict(block)
            if 'html' in block:
                block['html'] = Markup(auxiliary_html(block['html']))
            if block.get('mediaId'):
                block['src'] = '/bader_product_intelligence/description_media/%s/file?r=%s' % (block['mediaId'], self.bpi_editorial_revision or 1)
            if block.get('url'):
                block.update(social_video(block['url']))
            if block.get('posterMediaId'):
                block['posterSrc'] = '/bader_product_intelligence/description_media/%s/file?r=%s' % (block['posterMediaId'], self.bpi_editorial_revision or 1)
            if block.get('type') == 'video':
                ratio = block.get('videoRatio', 'auto')
                if ratio == 'auto':
                    ratio = '9:16' if block.get('provider') == 'tiktok' else '16:9'
                    if block.get('mediaId'):
                        # Local metadata only; never probe or fetch on a public page.
                        self.env.cr.execute('SELECT width,height FROM bpi_description_media WHERE id=%s AND product_id=%s AND state=%s', (block['mediaId'], self.id, 'ready'))
                        row = self.env.cr.fetchone()
                        if row and row[0] > 0 and row[1] > 0:
                            ratio = '%s:%s' % row
                block['videoStyle'] = '--bpi-video-width:%s%%;--bpi-video-ratio:%s' % (block.get('videoWidth', 100), ratio.replace(':', '/'))
            if 'children' in block:
                block['children'] = [project(child) for child in block['children']]
            return block
        return {'version': 1, 'enabled': True, 'blocks': [project(block) for block in layout['blocks']]}


class ProductKeywordRevision(models.Model):
    _inherit = 'bpi.product.keyword'

    def _editorial_products(self, values=None):
        products = self.mapped('product_tmpl_id')
        if values and values.get('product_tmpl_id'):
            products |= self.env['product.template'].browse(values['product_tmpl_id'])
        for product in products.sorted('id'):
            product._bpi_lock_editorial_revision()
        return products

    @api.model_create_multi
    def create(self, values_list):
        self.check_access_rights('create')
        product_ids = {value.get('product_tmpl_id', self.env.context.get('default_product_tmpl_id')) for value in values_list}
        products = self.env['product.template'].browse(sorted(product_id for product_id in product_ids if product_id))
        for product in products:
            product._bpi_lock_editorial_revision()
        records = super().create(values_list)
        products._bpi_touch_editorial_revision()
        return records

    def write(self, values):
        self.check_access_rights('write'); self.check_access_rule('write')
        products = self._editorial_products(values)
        result = super().write(values)
        products._bpi_touch_editorial_revision()
        return result

    def unlink(self):
        self.check_access_rights('unlink'); self.check_access_rule('unlink')
        products = self._editorial_products()
        result = super().unlink()
        products._bpi_touch_editorial_revision()
        return result


class ProductFaqRevision(models.Model):
    _inherit = 'bpi.product.faq'

    def _editorial_products(self, values=None):
        products = self.mapped('product_tmpl_id')
        if values and values.get('product_tmpl_id'):
            products |= self.env['product.template'].browse(values['product_tmpl_id'])
        for product in products.sorted('id'):
            product._bpi_lock_editorial_revision()
        return products

    @api.model_create_multi
    def create(self, values_list):
        self.check_access_rights('create')
        product_ids = {value.get('product_tmpl_id', self.env.context.get('default_product_tmpl_id')) for value in values_list}
        products = self.env['product.template'].browse(sorted(product_id for product_id in product_ids if product_id))
        for product in products:
            product._bpi_lock_editorial_revision()
        records = super().create(values_list)
        products._bpi_touch_editorial_revision()
        return records

    def write(self, values):
        self.check_access_rights('write'); self.check_access_rule('write')
        products = self._editorial_products(values)
        result = super().write(values)
        products._bpi_touch_editorial_revision()
        return result

    def unlink(self):
        self.check_access_rights('unlink'); self.check_access_rule('unlink')
        products = self._editorial_products()
        result = super().unlink()
        products._bpi_touch_editorial_revision()
        return result


class DescriptionService(models.AbstractModel):
    _inherit = 'bpi.service'

    @api.model
    def save_all(self, product, product_values=None, category_values=None, content_values=None, seo_data=None):
        self._ensure_manager()
        product = self._meli_product(product.id)
        with self.env.cr.savepoint():
            revisions = [value['editorialRevision'] for value in (product_values, category_values, content_values, seo_data)
                         if isinstance(value, dict) and 'editorialRevision' in value]
            expected = revisions[0] if revisions else None
            if any(revision != expected for revision in revisions):
                raise UserError(_('Las secciones pertenecen a revisiones distintas. Recarga y revisa la ficha.'))
            product._bpi_lock_editorial_revision(expected)
            # Check BEFORE Datos changes name or any other editorial field.
            service = self.with_context(_bpi_editorial_guard=_REVISION_GUARD)
            return super(DescriptionService, service).save_all(product, product_values, category_values, content_values, seo_data)

    @api.model
    def _guard_editorial_partial(self, product, values):
        self._ensure_manager()
        product = self._meli_product(product.id)
        if values is not None and not isinstance(values, dict):
            raise ValidationError(_('Los cambios deben ser un objeto válido.'))
        if self.env.context.get('_bpi_editorial_guard') is not _REVISION_GUARD:
            product._bpi_lock_editorial_revision((values or {}).get('editorialRevision'))
        return product

    @api.model
    def update_product(self, product, values):
        with self.env.cr.savepoint():
            product = self._guard_editorial_partial(product, values)
            return super().update_product(product, values)

    @api.model
    def save_category(self, product, values):
        with self.env.cr.savepoint():
            product = self._guard_editorial_partial(product, values)
            return super().save_category(product, values)

    @api.model
    def save_seo_payload(self, product, data):
        with self.env.cr.savepoint():
            product = self._guard_editorial_partial(product, data)
            return super().save_seo_payload(product, data)

    @api.model
    def save_content(self, product, values):
        self._ensure_manager()
        product = self._meli_product(product.id)
        values = {} if values is None else values
        if not isinstance(values, dict):
            raise ValidationError(_('El contenido debe ser un objeto.'))
        with self.env.cr.savepoint():
            if self.env.context.get('_bpi_editorial_guard') is not _REVISION_GUARD:
                product._bpi_lock_editorial_revision(values.get('editorialRevision'))
            if 'descriptionLayout' in values:
                product.write({'bpi_description_layout': values['descriptionLayout']})
            return super().save_content(product, values)


class DescriptionMedia(models.Model):
    _name = 'bpi.description.media'
    _description = 'Medios privados del diseño editorial'
    _order = 'id desc'

    product_id = fields.Many2one('product.template', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='product_id.company_id', store=True, index=True)
    name = fields.Char(required=True)
    kind = fields.Selection([('image', 'Imagen'), ('video', 'Vídeo')], required=True)
    state = fields.Selection([('uploading', 'Subiendo'), ('ready', 'Listo'), ('rejected', 'Cancelado')], default='uploading', required=True, index=True)
    storage_key = fields.Char(required=True, copy=False, default=lambda self: uuid.uuid4().hex)
    reserved_size = fields.Integer(required=True)
    file_size = fields.Integer(default=0)
    mimetype = fields.Char()
    checksum = fields.Char()
    duration = fields.Float()
    width = fields.Integer()
    height = fields.Integer()
    _sql_constraints = [('storage_key_unique', 'unique(storage_key)', 'Identificador de archivo duplicado.')]

    def _ensure_manager(self):
        self.env['bpi.service']._ensure_manager()

    @api.model_create_multi
    def create(self, values_list):
        # Upload allocation owns creation; normal RPC must not forge ready files.
        raise AccessError(_('Usa la carga segura de archivos.'))

    def write(self, values):
        raise AccessError(_('Usa la carga segura de archivos.'))

    def _set_values(self, values):
        return super().write(values)

    @api.model
    def _root(self, create=False):
        base = self.env['ir.config_parameter'].sudo().get_param('bpi.description_media_root') or os.path.join(tools.config['data_dir'], 'bpi_private_media')
        base = os.path.realpath(base)
        dbkey = hashlib.sha256(self.env.cr.dbname.encode()).hexdigest()[:24]
        directory = os.path.join(base, dbkey)
        if create:
            os.makedirs(directory, mode=0o750, exist_ok=True)
        return directory

    def _path(self):
        self.ensure_one()
        if not re.fullmatch(r'[a-f0-9]{32}', self.storage_key or ''):
            raise ValidationError(_('Identificador de archivo no válido.'))
        return os.path.join(self._root(), self.storage_key)

    @api.model
    def _check_capacity(self, additional_bytes=0):
        self._ensure_manager()
        if not isinstance(additional_bytes, int) or additional_bytes < 0:
            raise ValidationError(_('Tamaño no válido.'))
        self.env.cr.execute('SELECT pg_advisory_xact_lock(%s)', (QUOTA_LOCK,))
        self.flush_model(['reserved_size', 'state', 'file_size'])
        self.env.cr.execute("SELECT COALESCE(SUM(reserved_size),0), COALESCE(SUM(GREATEST(reserved_size-file_size,0)),0) FROM bpi_description_media WHERE state != 'rejected'")
        used, pending = self.env.cr.fetchone()
        path = self._root(create=True)
        actual = 0
        for entry in os.scandir(path):
            try:
                if entry.is_file(follow_symlinks=False):
                    actual += entry.stat(follow_symlinks=False).st_size
            except FileNotFoundError:
                continue
        used = max(used, actual + pending)
        self.env.cr.execute("SELECT to_regclass('bpi_content_studio_source')")
        if self.env.cr.fetchone()[0]:
            self.env['bpi.content.studio.source'].flush_model(['file_size'])
            self.env.cr.execute('SELECT COALESCE(SUM(file_size),0) FROM bpi_content_studio_source')
            used += self.env.cr.fetchone()[0]
        path = self._root(create=True)
        if used + additional_bytes > QUOTA or shutil.disk_usage(path).free - pending - additional_bytes < MIN_FREE:
            raise UserError(_('No hay espacio seguro para esta carga. Usa un enlace o solicita liberar almacenamiento; los archivos actuales se conservan.'))

    @api.model
    def _start(self, product, filename, size, kind):
        self._ensure_manager()
        product = self.env['bpi.service']._meli_product(product.id)
        limit = MAX_IMAGE if kind == 'image' else MAX_VIDEO if kind == 'video' else 0
        if isinstance(size, bool) or not isinstance(size, int) or not 0 < size <= limit:
            raise ValidationError(_('Máximo 10 MiB por imagen o 200 MiB por vídeo MP4.'))
        if not isinstance(filename, str) or not filename.strip() or len(filename) > 200 or re.search(r'[\x00-\x1f\x7f]', filename) or not os.path.basename(filename.replace('\\', '/')):
            raise ValidationError(_('Nombre de archivo no válido.'))
        self._check_capacity(size)
        record = super(DescriptionMedia, self).create({'product_id': product.id, 'name': os.path.basename(filename.replace('\\', '/')),
                'reserved_size': size, 'kind': kind, 'state': 'uploading', 'file_size': 0,
                'storage_key': uuid.uuid4().hex, 'mimetype': False, 'checksum': False})
        fd = os.open(record._path(), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o640)
        os.close(fd)
        return record

    @api.model
    def _for_product(self, product, media_id, kind=None, ready=True):
        self._ensure_manager()
        self.env['bpi.service']._meli_product(product.id)
        if isinstance(media_id, bool) or not isinstance(media_id, int):
            raise MissingError(_('Archivo no encontrado.'))
        record = self.browse(media_id).exists()
        record.check_access_rights('read'); record.check_access_rule('read')
        if not record or record.product_id != product:
            raise MissingError(_('Archivo no disponible para este producto.'))
        record._lock()
        if (kind and record.kind != kind) or (ready and record.state != 'ready'):
            raise MissingError(_('Archivo no disponible para este producto.'))
        return record

    def _lock(self):
        self.ensure_one(); self._ensure_manager()
        self.check_access_rights('write'); self.check_access_rule('write')
        self.env['bpi.service']._meli_product(self.product_id.id)
        self.env.cr.execute('SELECT id FROM bpi_description_media WHERE id=%s FOR UPDATE', (self.id,))
        if not self.env.cr.fetchone():
            raise MissingError(_('Archivo no encontrado.'))
        self.invalidate_recordset()

    def _chunk(self, offset, stream):
        self._lock()
        if self.state != 'uploading' or isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValidationError(_('Carga no disponible.'))
        raw = stream.read(CHUNK_SIZE + 1)
        if not raw or len(raw) > CHUNK_SIZE or offset + len(raw) > self.reserved_size:
            raise ValidationError(_('Fragmento demasiado grande o vacío.'))
        path = self._path()
        actual = os.path.getsize(path)
        if offset < actual:
            with open(path, 'rb') as source:
                source.seek(offset)
                if source.read(len(raw)) != raw or offset + len(raw) > actual:
                    raise ValidationError(_('La carga cambió. Reanuda desde el último fragmento confirmado.'))
        elif offset == actual:
            if shutil.disk_usage(os.path.dirname(path)).free - len(raw) < MIN_FREE:
                raise UserError(_('Se detuvo la carga para preservar espacio seguro.'))
            with open(path, 'ab') as target:
                target.write(raw); target.flush(); os.fsync(target.fileno())
            actual += len(raw)
        else:
            raise ValidationError(_('Fragmento fuera de orden. Reanuda la carga.'))
        self._set_values({'file_size': actual})
        return {'id': self.id, 'offset': actual}

    def _complete(self):
        self._lock()
        if self.state == 'ready':
            return self._payload()
        path = self._path()
        if self.state != 'uploading' or os.path.getsize(path) != self.reserved_size:
            raise ValidationError(_('La carga todavía no está completa.'))
        values = {}
        if self.kind == 'image':
            try:
                with Image.open(path) as source:
                    if source.format not in ('JPEG', 'PNG', 'WEBP') or source.width * source.height > 16000000 or getattr(source, 'is_animated', False):
                        raise ValueError()
                    source.load()
                    image = ImageOps.exif_transpose(source).convert('RGB')
                    image.thumbnail((4096, 4096))
                    buffer = io.BytesIO(); image.save(buffer, 'JPEG', quality=88, optimize=True)
                    raw = buffer.getvalue()
                    if len(raw) > MAX_IMAGE:
                        raise ValueError()
                # Normalization temporarily stores BOTH files; reserve that peak.
                self._check_capacity(len(raw))
                # New key keeps the original upload intact if the SQL transaction
                # fails after normalization. Never overwrite a resumable source.
                original = path
                key = uuid.uuid4().hex
                path = os.path.join(self._root(), key)
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o640)
                with os.fdopen(fd, 'wb') as target:
                    target.write(raw); target.flush(); os.fsync(target.fileno())
                def remove_original():
                    try:
                        os.unlink(original)
                    except FileNotFoundError:
                        pass
                self.env.cr.postcommit.add(remove_original)
                values.update(mimetype='image/jpeg', width=image.width, height=image.height,
                              storage_key=key, reserved_size=len(raw), file_size=len(raw))
            except (ValueError, OSError, Image.DecompressionBombError):
                raise ValidationError(_('Usa una imagen JPG, PNG o WebP estática, válida y de hasta 16 megapíxeles.'))
        else:
            values.update(probe_video(path))
        digest = hashlib.sha256()
        with open(path, 'rb') as source:
            for piece in iter(lambda: source.read(MIB), b''):
                digest.update(piece)
        values.update(state='ready', checksum=digest.hexdigest())
        self._set_values(values)
        return self._payload()

    @api.model
    def _youtube_poster(self, product, url):
        self._ensure_manager()
        product = self.env['bpi.service']._meli_product(product.id)
        info = social_video(url)
        if info['provider'] != 'youtube':
            raise UserError(_('Para esta red, sube una portada o elige una imagen de la biblioteca.'))
        from .studio_fetch import fetch_public_image, PublicFetchError
        video_id = parse_qs(urlsplit(info['url']).query)['v'][0]
        try:
            # Constructed CDN URL, not arbitrary user-provided image URLs. No API key.
            raw = fetch_public_image('https://i.ytimg.com/vi/%s/hqdefault.jpg' % video_id)
        except PublicFetchError:
            raise UserError(_('No se pudo obtener la portada. Puedes subir una imagen o volver a intentarlo.'))
        with self.env.cr.savepoint():
            record = self._start(product, 'Portada YouTube %s.jpg' % video_id, len(raw), 'image')
            for offset in range(0, len(raw), CHUNK_SIZE):
                record._chunk(offset, io.BytesIO(raw[offset:offset + CHUNK_SIZE]))
            record._complete()
            return record._payload()

    def _payload(self):
        self.ensure_one()
        prefix = '/bader_product_intelligence/description_media/%s/' % self.id
        offset = os.path.getsize(self._path()) if self.state == 'uploading' and os.path.isfile(self._path()) else self.file_size
        return {'id': self.id, 'kind': self.kind, 'state': self.state, 'filename': self.name,
                'size': self.file_size, 'offset': offset, 'total': self.reserved_size, 'chunkSize': CHUNK_SIZE,
                'mimetype': self.mimetype or '', 'url': prefix + 'file', 'previewUrl': prefix + 'preview',
                'width': self.width, 'height': self.height, 'duration': self.duration}

    def unlink(self):
        self._ensure_manager()
        for product in self.mapped('product_id').sorted('id'):
            product._bpi_lock_editorial_revision()
        for record in self.sorted('id'):
            record._lock()
            self.env['bpi.service']._meli_product(record.product_id.id)
            if record.id in layout_media_ids(record.product_id.bpi_description_layout):
                raise UserError(_('Guarda el diseño sin este archivo antes de eliminarlo.'))
        paths = [record._path() for record in self]
        result = super().unlink()
        # Defer filesystem removal until DB commit; rollback never loses files.
        def remove():
            for path in paths:
                try:
                    os.unlink(path)
                except FileNotFoundError:
                    pass
        self.env.cr.postcommit.add(remove)
        return result

    @api.model
    def _gc_uploads(self):
        """Bounded maintenance, no remote calls and no deletion of saved media."""
        self._ensure_manager()
        cutoff = fields.Datetime.now() - timedelta(days=7)
        records = self.search([('write_date', '<', cutoff)], limit=100)
        for record in records:
            if record.id not in layout_media_ids(record.product_id.bpi_description_layout):
                record.unlink()
        # Rollbacks and deleted products may leave opaque files without rows.
        # Old orphans only; never touch a key owned by any current record.
        path = self._root()
        if os.path.isdir(path):
            threshold = time.time() - 7 * 86400
            scanned = 0
            for entry in os.scandir(path):
                if scanned >= 1000:
                    break
                scanned += 1
                if not entry.is_file(follow_symlinks=False) or not re.fullmatch(r'[a-f0-9]{32}', entry.name) or entry.stat(follow_symlinks=False).st_mtime >= threshold:
                    continue
                self.env.cr.execute('SELECT 1 FROM bpi_description_media WHERE storage_key=%s', (entry.name,))
                if not self.env.cr.fetchone():
                    os.unlink(entry.path)
        return True

