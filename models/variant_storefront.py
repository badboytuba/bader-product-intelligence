# -*- coding: utf-8 -*-
"""Read-only public projection. No profile, source, draft or price writes here."""
from urllib.parse import urljoin

from markupsafe import Markup
from odoo import SUPERUSER_ID, models
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.http import request
from odoo.tools.json import scriptsafe

from .description_layout import auxiliary_html, description_heading_style
from .variant_content import fingerprint


class VariantStorefrontProduct(models.Model):
    _inherit = 'product.template'

    def _bpi_public_variant(self, website, variant_id):
        self.ensure_one()
        if not website or not website.bpi_variant_content_enabled or not self._bpi_visible_documents(website):
            return self.env['product.product']
        if type(variant_id) is not int or variant_id <= 0:
            return self.env['product.product']
        variant = self.env['product.product'].search([
            ('id', '=', variant_id), ('product_tmpl_id', '=', self.id), ('active', '=', True)], limit=1)
        if not variant:
            return self.env['product.product']
        combination = self._get_first_possible_combination(necessary_values=variant.product_template_attribute_value_ids)
        if not self._is_combination_possible(combination) or self._get_variant_for_combination(combination) != variant:
            return self.env['product.product']
        return variant

    def _bpi_public_variant_content(self, website, variant_id):
        """Authorize the public identity FIRST, then project an explicit allowlist."""
        variant = self._bpi_public_variant(website, variant_id)
        if not variant:
            return False
        # Private profile ACLs are intentionally unchanged. Never return this
        # privileged recordset or its raw JSON to the visitor.
        admin = self.with_user(SUPERUSER_ID).with_context(allowed_company_ids=[website.company_id.id])
        _edition, profile, _base, values = admin._bpi_effective_variant(variant.id)
        revision = '%s-%s' % (self.bpi_editorial_revision or 1, profile.revision if profile else 0)
        name = variant.with_context(display_default_code=False).display_name
        image_records = variant._bpi_saved_public_images(website, values['gallery'])
        images = [image._bpi_public_gallery_url(website, 1024) if image._name == 'bpi.product.image'
                  else website.image_url(image, 'image_1024') for image in image_records]
        layout = self._bpi_project_description_layout(website, values['descriptionLayout'],
            values['technicalDescription'], revision, variant.id, variant_content=True)
        video = False
        if values['videoUrl']:
            try:
                video = self._bpi_project_description_layout(website, {
                    'enabled': True, 'blocks': [{'id': 'edition_video', 'type': 'video',
                        'url': values['videoUrl'], 'videoMaxWidth': 960}]},
                    '', revision, variant.id, variant_content=True)
            except UserError:
                # Legacy invalid common URLs must not break an inherited page.
                pass
        documents = dict(values['documents'])
        documents['buttons'] = [row for row in documents['buttons'] if row['label'] and (row['url'] or row['fileUrl'])]
        result = {
            'productId': self.id, 'variantId': variant.id, 'name': name, 'sku': variant.default_code or '',
            'revision': revision, 'url': '%s?variant=%s' % (self.website_url, variant.id),
            'short': Markup(auxiliary_html(values['description']) if values['description'] else ''),
            'long': Markup(auxiliary_html(values['technicalDescription']) if values['technicalDescription'] else ''), 'layout': layout,
            'video': video,
            'headingStyle': description_heading_style(values['descriptionLayout']),
            'faqs': [{'question': row['question'], 'answer': row['answer']} for row in values['faqs']],
            'documents': documents if documents['buttons'] else False,
            'title': values['seoTitle'] or name, 'description': values['seoDescription'],
            'keywords': ', '.join(values['seoKeywords']), 'image': images[0] if images else '',
            'geoTitle': values['geoTitle'], 'geoDescription': values['geoDescription'],
            'geoFeatures': values['geoFeatures'], 'images': images,
        }
        result['cacheKey'] = fingerprint([result, values['gallery']])
        return result

    def _bpi_public_gallery_reference(self, website, variant_id, image_id, revision=None):
        variant = self._bpi_public_variant(website, variant_id)
        Image = self.env['bpi.product.image']
        if not variant or type(image_id) is not int or image_id <= 0:
            return Image
        profile = self.env['bpi.variant.content'].sudo().search([('product_id','=',variant.id)], limit=1)
        current = '%s-%s' % (self.bpi_editorial_revision or 1, profile.revision if profile else 0)
        if (not profile or 'bpi:%s'%image_id not in (profile.overrides or {}).get('gallery', [])
                or (revision is not None and revision != current)):
            return Image
        # Only one owned saved reference is elevated, never the image library.
        return Image.sudo().search([('id','=',image_id), ('product_tmpl_id','=',self.id), ('state','=','approved')],limit=1)

    def _get_first_possible_combination(self, parent_combination=None, necessary_values=None):
        variant_id = self.env.context.get('bpi_public_variant_id')
        if variant_id and self.id == self.env.context.get('bpi_public_template_id'):
            edition = self.env['product.product'].browse(variant_id).exists()
            if edition and edition.active and edition.product_tmpl_id == self:
                necessary_values = (necessary_values or self.env['product.template.attribute.value']) | edition.product_template_attribute_value_ids
        return super()._get_first_possible_combination(parent_combination=parent_combination, necessary_values=necessary_values)

    def _bpi_variant_jsonld(self, website, projection, pricelist):
        """Current variant offer uses the same Odoo combination price and currency."""
        variant = self._bpi_public_variant(website, projection['variantId'])
        if not variant:
            return ''
        combination = self._get_combination_info(combination=self._get_first_possible_combination(necessary_values=variant.product_template_attribute_value_ids),
            product_id=variant.id, add_qty=1, pricelist=pricelist)
        base_url = website.get_base_url()
        variant_url = urljoin(base_url, projection['url'])
        group_url = urljoin(base_url, self.website_url)
        item = {'@type':'Product', '@id':variant_url+'#product', 'url':variant_url,
            'name':projection['name'], 'sku':projection['sku'],
            'description':self._bpi_plain_text(str(projection['short'])),
            'image':[urljoin(base_url, image) for image in projection['images']],
            'isVariantOf':{'@id':group_url+'#group'},
            'offers':{'@type':'Offer', 'url':variant_url, 'price':combination['price'],
                'priceCurrency':pricelist.currency_id.name}}
        group = {'@context':'https://schema.org', '@type':'ProductGroup', '@id':group_url+'#group',
            'name':self.name, 'productGroupID':str(self.id), 'url':group_url,
            'variesBy':[line.attribute_id.name for line in self.attribute_line_ids if line.attribute_id.create_variant != 'no_variant'],
            'hasVariant':[item]}
        if projection['geoFeatures']:
            item['additionalProperty'] = [{'@type':'PropertyValue', 'name':'Característica', 'value':text} for text in projection['geoFeatures']]
        return Markup(scriptsafe.dumps(group, ensure_ascii=False))


class VariantStorefrontEdition(models.Model):
    _inherit = 'product.product'

    def _bpi_saved_public_images(self, website, tokens):
        self.ensure_one()
        product = self.product_tmpl_id
        if not product._bpi_public_variant(website, self.id):
            return []
        records = []
        for token in tokens:
            if token == 'main':
                record = product
            else:
                kind, sep, raw = token.partition(':')
                if not sep or not raw.isdigit():
                    continue
                if kind == 'variant':
                    record = self.env['product.product'].search([('id','=',int(raw)), ('product_tmpl_id','=',product.id)], limit=1)
                elif kind == 'odoo':
                    record = self.env['product.image'].search([('id','=',int(raw)), '|',
                        ('product_tmpl_id','=',product.id), ('product_variant_id.product_tmpl_id','=',product.id)], limit=1)
                elif kind == 'bpi':
                    record = product._bpi_public_gallery_reference(website, self.id, int(raw))
                    if record:
                        record = record.with_context(bpi_gallery_variant_id=self.id)
                else:
                    continue
            if record and record not in records:
                records.append(record)
        return records

    def _get_images(self):
        website = request.website if request and getattr(request, 'website', None) else self.env['website']
        if website and website.bpi_variant_content_enabled and self.product_tmpl_id._bpi_public_variant(website, self.id):
            profile = self.env['bpi.variant.content'].sudo().search([('product_id','=',self.id)],limit=1)
            if profile and 'gallery' in (profile.overrides or {}):
                return self._bpi_saved_public_images(website, profile.overrides['gallery'])
        return super()._get_images()


class VariantPublicImage(models.Model):
    _inherit = 'bpi.product.image'

    def _bpi_public_gallery_url(self, website, size=1024):
        self.ensure_one()
        variant_id = self.env.context.get('bpi_gallery_variant_id')
        product = self.product_tmpl_id
        if not product._bpi_public_gallery_reference(website, variant_id, self.id):
            return ''
        profile = self.env['bpi.variant.content'].sudo().search([('product_id','=',variant_id)],limit=1)
        return '/bader_product_intelligence/variant_gallery/%s/%s/%s?size=%s&r=%s-%s' % (
            product.id, variant_id, self.id, size if size in (128,1024,1920) else 1024,
            product.bpi_editorial_revision or 1, profile.revision)
