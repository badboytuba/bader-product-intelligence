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


def video_text_style(value, field):
    """Bounded typography, never user-supplied CSS. Also supplies legacy defaults."""
    default = {'font': 'display' if field == 'title' else 'body',
               'size': 28 if field == 'title' else 14, 'bold': False, 'italic': False,
               'align': 'inherit', 'color': 'auto'}
    if not isinstance(value, dict) or set(value) - set(default):
        raise ValidationError(_('Usa los controles de formato del título y la leyenda.'))
    result = dict(default, **value)
    if (result['font'] not in ('display', 'body') or type(result['size']) is not int
            or not 12 <= result['size'] <= 64 or type(result['bold']) is not bool
            or type(result['italic']) is not bool
            or result['align'] not in ('inherit', 'left', 'center', 'right')
            or result['color'] not in ('auto', 'petrol', 'green')):
        raise ValidationError(_('Elige una fuente Bader, tamaño de 12 a 64 px y estilos disponibles.'))
    return result


def video_text_css(value, field):
    style = video_text_style(value, field)
    font = 'var(--bader-font-display)' if style['font'] == 'display' else 'var(--bader-font-body)'
    color = {'auto': 'inherit', 'petrol': '#003841', 'green': '#2f7d32'}[style['color']]
    return ('font-family:%s;font-size:%spx;font-weight:%s;font-style:%s;text-align:%s;color:%s'
            % (font, style['size'], '700' if style['bold'] else '400',
               'italic' if style['italic'] else 'normal', style['align'], color))


def image_style(block):
    """Only validated design tokens become CSS; no authored CSS is accepted."""
    align = block.get('imageAlign', 'center')
    return ('--bpi-image-width:%s%%;--bpi-image-max:%s;--bpi-image-ratio:%s;'
            '--bpi-image-fit:%s;--bpi-image-left:%s;--bpi-image-right:%s' % (
                block.get('imageWidth', 100),
                '%spx' % block['imageMaxWidth'] if block.get('imageMaxWidth') else '100%',
                block.get('imageRatio', 'auto').replace(':', '/'), block.get('imageFit', 'contain'),
                '0' if align == 'left' else 'auto', '0' if align == 'right' else 'auto'))


def columns_style(block, ratios=None):
    layout = block.get('columnLayout', 'equal')
    left, right = {'equal': (1, 1), 'wide-left': (2, 1), 'wide-right': (1, 2)}.get(layout, (1, 1))
    if layout == 'media' and ratios and len(ratios) == 2:
        left, right = ratios
    gap = {'compact': 12, 'normal': 24, 'spacious': 40}[block.get('columnGap', 'normal')]
    return '--bpi-column-left:%sfr;--bpi-column-right:%sfr;--bpi-column-gap:%spx;--bpi-column-align:%s' % (
        left, right, gap, block.get('columnAlign', 'center'))


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


def auxiliary_style(value):
    """Allow presentation only; never CSS URLs, positioning or arbitrary rules."""
    fonts = {s.lower(): s for s in ('Bader Sans', 'Helvetica Neue LT Pro', 'Arial',
        'Verdana', 'Tahoma', 'Trebuchet MS', 'Georgia', 'Times New Roman', 'Courier New')}
    choices = {'font-size': {str(n) + 'px' for n in (10, *range(12, 65))},
        'text-align': {'left', 'center', 'right', 'justify'},
        'margin-left': {'40px', '80px', '120px', '160px', '200px'},
        'font-weight': {'bold', '700'}, 'font-style': {'italic'},
        'text-decoration': {'underline', 'line-through', 'underline line-through', 'line-through underline'}}
    result = {}
    for declaration in (value or '').split(';'):
        key, sep, val = declaration.partition(':')
        key, val = key.strip().lower(), val.strip()
        if not sep:
            continue
        if key == 'font-family':
            font = fonts.get(val.split(',')[0].strip().strip('\"\'').lower())
            if font:
                result[key] = "'%s'" % font
        elif key in choices and val.lower() in choices[key]:
            result[key] = val.lower()
        elif key in ('color', 'background-color') and re.fullmatch(
                r'#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?(?:[0-9a-fA-F]{2})?|rgba?\(\s*\d{1,3}(?:\.\d+)?\s*,\s*\d{1,3}(?:\.\d+)?\s*,\s*\d{1,3}(?:\.\d+)?(?:\s*,\s*(?:0|1|0?\.\d+))?\s*\)', val):
            result[key] = val
    return '; '.join('%s: %s' % pair for pair in result.items())


def auxiliary_html(value):
    """Text-only rich dialect, sanitized equally on save and public rendering."""
    if not isinstance(value, str) or len(value.encode('utf-8')) > 20000:
        raise ValidationError(_('El texto del bloque no es válido o supera 20 KB.'))
    try:
        root = lxml_html.fragment_fromstring(value or '<p/>', create_parent='div')
    except (ValueError, TypeError):
        raise ValidationError(_('El texto del bloque no es válido.'))
    allowed = {'p', 'br', 'strong', 'b', 'em', 'i', 'u', 's', 'strike', 'sub', 'sup',
        'span', 'div', 'ul', 'ol', 'li', 'h2', 'h3', 'h4', 'h5', 'blockquote', 'a'}
    for node in list(root.iterdescendants()):
        if not isinstance(node.tag, str):
            node.drop_tree()
        elif node.tag.lower() in ('script', 'style', 'iframe', 'object', 'embed', 'svg', 'math', 'form', 'input', 'video', 'audio'):
            node.drop_tree()
        elif node.tag.lower() not in allowed:
            node.drop_tag()
        else:
            style = auxiliary_style(node.get('style'))
            href = node.get('href', '')
            node.attrib.clear()
            if style:
                node.set('style', style)
            if node.tag.lower() == 'a':
                try:
                    parsed = urlsplit(href)
                    safe = (parsed.scheme in ('http', 'https') and parsed.hostname
                        and not parsed.username and not parsed.password
                        and not re.search(r'[\x00-\x20\\]', href))
                except ValueError:
                    safe = False
                if safe:
                    node.set('href', href)
                    node.set('target', '_blank')
                    node.set('rel', 'noopener noreferrer')
    return str(Markup.escape(root.text or '')) + ''.join(lxml_html.tostring(child, encoding='unicode') for child in root)


def validate_layout(value, media_lookup=None, variant_lookup=None):
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
    common = {'id', 'type', 'preset', 'align', 'effect', 'spacing', 'variantIds'}
    def visit(block, depth=0):
        if not isinstance(block, dict) or depth > 4:
            raise ValidationError(_('El diseño contiene demasiados niveles.'))
        count[0] += 1
        key, kind = block.get('id'), block.get('type')
        if count[0] > 50 or not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', key) or key in ids:
            raise ValidationError(_('Los bloques deben tener identificadores únicos; máximo 50 bloques.'))
        ids.add(key)
        accepted = {'main': set(), 'text': {'html'}, 'callout': {'html'},
                    'image': {'mediaId', 'alt', 'caption', 'title', 'titleStyle', 'captionStyle', 'imageWidth', 'imageMaxWidth', 'imageAlign', 'imageRatio', 'imageFit'},
                    'video': {'mediaId', 'url', 'caption', 'posterMediaId', 'videoWidth', 'videoRatio', 'title', 'titleStyle', 'captionStyle'},
                    'columns': {'children', 'columnLayout', 'columnGap', 'columnAlign'}, 'container': {'children'}, 'divider': set()}
        if not isinstance(kind, str) or kind not in accepted or set(block) - (common | accepted[kind]):
            raise ValidationError(_('Tipo o propiedades de bloque no permitidos.'))
        result = {'id': key, 'type': kind}
        if 'variantIds' in block:
            variants = block['variantIds']
            if (depth or kind == 'main' or not isinstance(variants, list)
                    or not 1 <= len(variants) <= 100
                    or any(type(v) is not int or v <= 0 for v in variants)
                    or len(set(variants)) != len(variants)):
                raise ValidationError(_('Selecciona variantes para la composición completa. El texto principal siempre es común.'))
            if variant_lookup:
                variant_lookup(variants)
            result['variantIds'] = sorted(variants)
        for field, allowed, default in (
            ('preset', ('white', 'mist', 'petrol', 'lime'), 'white'),
            ('align', ('left', 'center', 'right'), 'left'), ('effect', ('none', 'lift'), 'none'),
            ('spacing', ('compact', 'normal', 'spacious'), 'normal')):
            current = block.get(field, default)
            if current not in allowed:
                raise ValidationError(_('Usa los estilos Bader disponibles.'))
            result[field] = current
        if kind == 'image':
            for field, low, high, default in (('imageWidth', 10, 100, 100), ('imageMaxWidth', 0, 2400, 0)):
                val = block.get(field, default)
                if type(val) is not int or not low <= val <= high:
                    raise ValidationError(_('Usa un ancho de imagen de 10 a 100 % y un límite de 0 a 2400 px.'))
                if field in block:
                    result[field] = val
            for field, allowed in (('imageAlign', ('left', 'center', 'right')),
                    ('imageRatio', ('auto', '16:9', '9:16', '1:1', '4:3', '3:2')),
                    ('imageFit', ('contain', 'cover'))):
                if field in block:
                    if block[field] not in allowed:
                        raise ValidationError(_('Elige una proporción, posición y ajuste de imagen disponibles.'))
                    result[field] = block[field]
        if kind in ('image', 'video'):
            if 'title' in block:
                if not isinstance(block['title'], str) or len(block['title']) > 200:
                    raise ValidationError(_('El título admite hasta 200 caracteres.'))
                result['title'] = block['title'].strip()
            for field in ('title', 'caption'):
                if field + 'Style' in block:
                    result[field + 'Style'] = video_text_style(block[field + 'Style'], field)
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
            if 'variantIds' in result:
                def has_main(node):
                    return node['type'] == 'main' or any(has_main(c) for c in node.get('children', []))
                if has_main(result):
                    raise ValidationError(_('El texto principal siempre es común a todas las variantes.'))
            if kind == 'columns':
                for field, allowed in (('columnLayout', ('equal', 'wide-left', 'wide-right', 'media')),
                        ('columnGap', ('compact', 'normal', 'spacious')), ('columnAlign', ('start', 'center', 'end'))):
                    if field in block:
                        if block[field] not in allowed:
                            raise ValidationError(_('Usa una composición de columnas disponible.'))
                        result[field] = block[field]
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
                # Canonical YouTube URLs no longer retain /shorts/: persist the
                # explicit intent at save time, not a guessed remote dimension.
                if result.get('videoRatio') == 'auto' and urlsplit(url).path.startswith(('/shorts/', '/reel/')):
                    result['videoRatio'] = '9:16'
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
                if any('variantIds' in block for block in layout['blocks']):
                    raise ValidationError(_('Crea el producto y sus variantes antes de configurar el diseño específico.'))
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
                    lambda media_id, kind: self.env['bpi.description.media']._for_product(product, media_id, kind),
                    product._bpi_check_layout_variants)
            local['bpi_editorial_revision'] = revision + 1
            super(ProductTemplate, product).write(local)
        return True

    def bpi_build_payload(self):
        result = super().bpi_build_payload()
        result.update(descriptionLayout=self.bpi_description_layout or empty_layout(),
                      editorialRevision=self.bpi_editorial_revision or 1)
        return result

    def _bpi_check_layout_variants(self, variant_ids):
        self.ensure_one()
        variants = self.env['product.product'].with_context(active_test=False).search([
            ('id', 'in', variant_ids), ('product_tmpl_id', '=', self.id)])
        if set(variants.ids) != set(variant_ids):
            raise ValidationError(_('Las variantes del diseño deben pertenecer a este producto. Recarga la ficha.'))

    def _bpi_has_variant_layout(self):
        self.ensure_one()
        layout = self.bpi_description_layout or {}
        return bool(layout.get('enabled')) and any('variantIds' in b for b in layout.get('blocks', []))

    def _bpi_public_description_layout(self, website, variant_id=False):
        self.ensure_one()
        layout = self.bpi_description_layout
        if not layout or not layout.get('enabled') or not self._bpi_plain_text(self.bpi_technical_description).strip() or not self._bpi_visible_documents(website):
            return False
        # Do not interpret hash attribute-value IDs as product.product IDs. The
        # native combination response supplies the selected, existing variant.
        variant = self.env['product.product'].search([
            ('id', '=', variant_id), ('product_tmpl_id', '=', self.id), ('active', '=', True)
        ], limit=1) if type(variant_id) is int and variant_id > 0 else self.env['product.product']
        visible_blocks = [b for b in layout['blocks'] if 'variantIds' not in b or variant.id in b['variantIds']]
        media_ids = layout_media_ids(layout)
        dimensions = {}
        if media_ids:
            self.env.cr.execute('SELECT id,width,height FROM bpi_description_media WHERE id IN %s AND product_id=%s AND state=%s',
                                (tuple(media_ids), self.id, 'ready'))
            dimensions = {row[0]: row[1:] for row in self.env.cr.fetchall()}
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
            if block.get('type') in ('image', 'video'):
                for field in ('title', 'caption'):
                    block[field + 'Css'] = video_text_css(block.get(field + 'Style', {}), field)
            if block.get('type') == 'image':
                block['imageStyle'] = image_style(block)
            if block.get('type') == 'video':
                ratio = block.get('videoRatio', 'auto')
                if ratio == 'auto':
                    ratio = '9:16' if block.get('provider') == 'tiktok' or '/reel/' in block.get('url', '') else '16:9'
                    if block.get('mediaId'):
                        # Batched local metadata; never probe/fetch on a public page.
                        row = dimensions.get(block['mediaId'])
                        if row and row[0] > 0 and row[1] > 0:
                            ratio = '%s:%s' % row
                block['videoStyle'] = '--bpi-video-width:%s%%;--bpi-video-ratio:%s' % (block.get('videoWidth', 100), ratio.replace(':', '/'))
                width, height = ratio.split(':')
                block['videoAspect'] = float(width) / float(height)
            if 'children' in block:
                block['children'] = [project(child) for child in block['children']]
                if block['type'] == 'columns':
                    block['columnsStyle'] = columns_style(block, [child.get('videoAspect', 1) for child in block['children']])
                    children = block['children']
                    block['videoPair'] = len(children) == 2 and all(c['type'] == 'video' for c in children)
                    if len(children) == 2:
                        image = next((c for c in children if c['type'] == 'image'), None)
                        text = next((c for c in children if c['type'] in ('text', 'callout')), None)
                        if image and text and image.get('title'):
                            # Projection only: one title, unchanged saved content.
                            text.update(linkedTitle=image['title'], linkedTitleCss=image['titleCss'])
                            image['hideTitle'] = True
            return block
        return {'version': 1, 'enabled': True, 'blocks': [project(block) for block in visible_blocks]}


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
