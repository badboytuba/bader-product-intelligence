# -*- coding: utf-8 -*-
"""Explicit editorial overrides. An absent key inherits; an empty value does not.

Never write template fields to simulate a variant. Operational product.product
and price-list data remain native and have separate save boundaries.
"""
import copy
import hashlib
import json

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError

from .description_layout import auxiliary_html, empty_layout, layout_media_ids, validate_layout


TEXT_KEYS = {'seoTitle', 'seoDescription', 'geoTitle', 'geoDescription', 'tone', 'audience'}
LIST_KEYS = {'seoKeywords', 'geoKeywords', 'geoFeatures'}
CONTENT_KEYS = TEXT_KEYS | LIST_KEYS | {
    'description', 'technicalDescription', 'templateId', 'descriptionLayout',
    'faqs', 'videoUrl', 'gallery', 'classification', 'publicCategoryIds', 'documents',
}
_PROFILE_WRITE = object()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     default=str).encode()).hexdigest()


class VariantContent(models.Model):
    _name = 'bpi.variant.content'
    _description = 'Contenido específico de una variante Bader'

    product_id = fields.Many2one('product.product', required=True, ondelete='cascade', index=True)
    product_tmpl_id = fields.Many2one(related='product_id.product_tmpl_id', store=True, index=True)
    company_id = fields.Many2one(related='product_id.company_id', store=True, index=True)
    overrides = fields.Json(default=dict, copy=False)
    revision = fields.Integer(default=1, required=True, copy=False, readonly=True)
    proposal_id = fields.Many2one('bpi.content.studio.proposal', ondelete='set null', copy=False)
    _sql_constraints = [('variant_unique', 'unique(product_id)', 'La variante ya tiene un perfil editorial.')]

    @api.model
    def _variant(self, product, variant_id, active=False):
        self.env['bpi.service']._meli_product(product.id)
        if type(variant_id) is not int or variant_id <= 0:
            raise ValidationError(_('Selecciona una variante válida.'))
        variant = self.env['product.product'].with_context(active_test=False).browse(variant_id).exists()
        if not variant or variant.product_tmpl_id != product or (active and not variant.active):
            raise MissingError(_('La variante no pertenece a este producto o no está disponible.'))
        variant.check_access_rights('read')
        variant.check_access_rule('read')
        return variant

    @api.model
    def _normalize(self, product, value):
        if not isinstance(value, dict) or set(value) - CONTENT_KEYS:
            raise ValidationError(_('Campos de contenido de variante no permitidos.'))
        try:
            if len(json.dumps(value, allow_nan=False)) > 750000:
                raise ValueError()
        except (TypeError, ValueError):
            raise ValidationError(_('Contenido de variante demasiado extenso o inválido.'))
        result = copy.deepcopy(value)
        for key, item in value.items():
            if key in TEXT_KEYS | {'description', 'technicalDescription', 'videoUrl'}:
                if not isinstance(item, str) or len(item) > (100000 if 'Description' in key or key == 'description' else 4000):
                    raise ValidationError(_('El texto de %s no es válido.') % key)
                if key in ('description', 'technicalDescription'):
                    result[key] = str(auxiliary_html(item)) if item.strip() else ''
                elif key == 'videoUrl':
                    # Existing URL validation/canonicalization, never a fetch.
                    if item:
                        from .description_layout import social_video
                        result[key] = social_video(item)['url']
            elif key in LIST_KEYS:
                if not isinstance(item, list) or len(item) > 30 or any(not isinstance(x, str) or len(x) > 500 for x in item):
                    raise ValidationError(_('La lista de metadatos no es válida.'))
                result[key] = list(dict.fromkeys(x.strip() for x in item if x.strip()))
            elif key == 'faqs':
                if not isinstance(item, list) or len(item) > 50:
                    raise ValidationError(_('La lista de preguntas no es válida.'))
                rows = []
                for row in item:
                    if not isinstance(row, dict) or set(row) - {'id', 'question', 'answer'}:
                        raise ValidationError(_('Pregunta inválida.'))
                    if any(not isinstance(row.get(k), str) or len(row[k]) > 12000 for k in ('question', 'answer')):
                        raise ValidationError(_('Completa la pregunta y la respuesta con texto.'))
                    if not row['question'].strip() or not row['answer'].strip():
                        raise ValidationError(_('Completa la pregunta y la respuesta o elimina la fila.'))
                    rows.append({k: row[k].strip() for k in ('question', 'answer')})
                result[key] = rows
            elif key == 'documents':
                if item is not True:
                    raise ValidationError(_('Los documentos de variante requieren su guardado revisado.'))
            elif key == 'templateId':
                if item is not False and (type(item) is not int or item <= 0):
                    raise ValidationError(_('Modelo editorial inválido.'))
                result[key] = self.env['bpi.content.template']._check_assignment(item).id or False
            elif key == 'descriptionLayout':
                result[key] = validate_layout(item,
                    lambda media_id, kind: self.env['bpi.description.media']._for_product(product, media_id, kind),
                    product._bpi_check_layout_variants)
            elif key in ('publicCategoryIds', 'gallery', 'classification'):
                if key == 'classification':
                    if not isinstance(item, dict) or set(item) - {'termIds', 'excludedTermIds'}:
                        raise ValidationError(_('Clasificación de variante inválida.'))
                    allowed = {t['id'] for t in self.env['bpi.taxonomy.term']._catalog()}
                    for name in ('termIds', 'excludedTermIds'):
                        ids = item.get(name, [])
                        self._check_ids(ids, allowed)
                    if set(item.get('termIds', [])) & set(item.get('excludedTermIds', [])):
                        raise ValidationError(_('Un término no puede estar seleccionado y excluido.'))
                    result[key] = {k: sorted(set(item.get(k, []))) for k in ('termIds', 'excludedTermIds')}
                elif key == 'publicCategoryIds':
                    self._check_ids(item)
                    categories = self.env['product.public.category'].search([('id', 'in', item)])
                    if set(item) != set(categories.ids):
                        raise ValidationError(_('Categoría de tienda no disponible.'))
                    result[key] = list(dict.fromkeys(item))
                else:
                    if not isinstance(item, list) or len(item) > 100 or any(not isinstance(x, str) for x in item) or len(set(item)) != len(item):
                        raise ValidationError(_('Referencias de galería inválidas.'))
                    owned = {str(row.get('referenceToken') or row['id']) for row in product._bpi_variant_gallery_library() if row.get('canPublish', True)}
                    if set(item) - owned:
                        raise ValidationError(_('Una imagen no pertenece a este producto.'))
        return result

    @api.model
    def _check_ids(self, ids, allowed=None):
        if not isinstance(ids, list) or len(ids) > 100 or any(type(i) is not int or i <= 0 for i in ids):
            raise ValidationError(_('Selección inválida.'))
        if allowed is not None and set(ids) - allowed:
            raise ValidationError(_('Selecciona únicamente términos aprobados.'))

    @api.model_create_multi
    def create(self, vals_list):
        self.env['bpi.service']._ensure_manager()
        if self.env.context.get('_bpi_profile_write') is not _PROFILE_WRITE:
            raise AccessError(_('Guarda el contenido desde la ficha de la variante.'))
        for vals in vals_list:
            variant = self.env['product.product'].browse(vals.get('product_id')).exists()
            if not variant:
                raise MissingError(_('Variante no encontrada.'))
            self._variant(variant.product_tmpl_id, variant.id)
            vals['overrides'] = self._normalize(variant.product_tmpl_id, vals.get('overrides', {}))
            vals['revision'] = 1
        return super().create(vals_list)

    def write(self, vals):
        self.env['bpi.service']._ensure_manager()
        if self.env.context.get('_bpi_profile_write') is not _PROFILE_WRITE or set(vals) - {'overrides', 'proposal_id'}:
            raise AccessError(_('El perfil se guarda con control de revisiones.'))
        for record in self:
            self._variant(record.product_tmpl_id, record.product_id.id)
            prepared = dict(vals, revision=record.revision + 1)
            if 'overrides' in vals:
                prepared['overrides'] = self._normalize(record.product_tmpl_id, vals['overrides'])
            super(VariantContent, record).write(prepared)
        return True

    def unlink(self):
        self.env['bpi.service']._ensure_manager()
        raise AccessError(_('Utiliza «Volver a heredar» para conservar la trazabilidad.'))

    @api.model
    def _save_workspace(self, product, variant_id, changes, inherit, base_revision, revision,
                        proposal_id=None, context_revision=None, specifications=None):
        if specifications is not None:
            if (not isinstance(specifications, list) or len(specifications) != 1
                    or not isinstance(specifications[0], dict)
                    or specifications[0].get('variantId') != variant_id):
                raise ValidationError(_('Guarda únicamente las especificaciones de la variante seleccionada.'))
            if proposal_id:
                raise ValidationError(_('La propuesta se generó con otras especificaciones. Guarda primero las medidas y solicita su revisión en Nancy AI Studio.'))
        with self.env.cr.savepoint():
            record = self._save(product, variant_id, changes, inherit, base_revision, revision,
                                proposal_id=proposal_id, context_revision=context_revision)
            if specifications is not None:
                self.env['bpi.product.specification']._save_rows(product, specifications)
            return record

    @api.model
    def _save(self, product, variant_id, changes, inherit, base_revision, revision, proposal_id=None, context_revision=None):
        variant = self._variant(product, variant_id)
        if type(base_revision) is not int or type(revision) is not int or revision < 0:
            raise ValidationError(_('La ficha necesita sus revisiones para guardar.'))
        if not isinstance(context_revision, str) or len(context_revision) != 64:
            raise ValidationError(_('Recarga el contexto de la variante antes de guardar.'))
        if not isinstance(inherit, list) or any(not isinstance(k, str) or k not in CONTENT_KEYS for k in inherit):
            raise ValidationError(_('Campos de herencia inválidos.'))
        changes = dict(changes) if isinstance(changes, dict) else changes
        has_documents = isinstance(changes, dict) and 'documents' in changes
        document_data = changes.pop('documents', None) if has_documents else None
        if has_documents:
            if not isinstance(document_data, dict):
                raise ValidationError(_('Bloque de documentos inválido.'))
            changes['documents'] = True
        changes = self._normalize(product, changes)
        if set(inherit) & set(changes):
            raise ValidationError(_('No se puede personalizar y heredar el mismo campo a la vez.'))
        with self.env.cr.savepoint():
            # The template row serializes first profile creation and base edits.
            # Unlike a fake product.write(), it changes no business value.
            product._bpi_lock_editorial_revision(base_revision)
            self.env.cr.execute('UPDATE product_template SET bpi_editorial_revision=bpi_editorial_revision WHERE id=%s', [product.id])
            self.env.cr.execute('SELECT id FROM product_product WHERE id=%s FOR UPDATE', [variant.id])
            if product._bpi_resolve_variant(variant.id)['contextRevision'] != context_revision:
                raise UserError(_('La base, las especificaciones o el modelo editorial cambiaron. Conservamos tus borradores; revisa el contexto.'))
            record = self.search([('product_id', '=', variant.id)], limit=1)
            if record:
                self.env.cr.execute('SELECT revision FROM bpi_variant_content WHERE id=%s FOR UPDATE', [record.id])
                current = self.env.cr.fetchone()[0]
                record.invalidate_recordset()
            else:
                current = 0
            if revision != current:
                raise UserError(_('Esta variante cambió en otra ventana. Conservamos tus borradores; revisa antes de guardar.'))
            document_revision = product._bpi_resolve_variant(variant.id)['values']['documents']['revision']
            if document_data is not None:
                self.env['bpi.product.document.panel']._save_panel(product, document_data, variant_id=variant.id)
            overrides = dict(record.overrides or {}) if record else {}
            overrides.update(changes)
            for key in inherit:
                overrides.pop(key, None)
            prepared = {'overrides': overrides}
            if proposal_id is not None:
                proposal = self.env['bpi.service'].with_context(bpi_product_variant_id=variant.id)._studio_reference(product, proposal_id)
                if proposal and (not hasattr(proposal.session_id, 'product_variant_id') or proposal.session_id.product_variant_id != variant):
                    raise ValidationError(_('La propuesta pertenece a otro contexto de edición.'))
                prepared['proposal_id'] = proposal.id or False
            if record:
                if overrides != record.overrides or (document_data is not None and product._bpi_resolve_variant(variant.id)['values']['documents']['revision'] != document_revision) or ('proposal_id' in prepared and prepared['proposal_id'] != record.proposal_id.id):
                    record.with_context(_bpi_profile_write=_PROFILE_WRITE).write(prepared)
            elif overrides or prepared.get('proposal_id'):
                record = self.with_context(_bpi_profile_write=_PROFILE_WRITE).create(dict(prepared, product_id=variant.id))
            return record.with_context(_bpi_profile_write=None)


class VariantProduct(models.Model):
    _inherit = 'product.template'

    def write(self, values):
        if self.env.context.get('bpi_product_variant_id'):
            raise ValidationError(_('Estás editando una variante. Para cambiar datos comunes, selecciona Contenido común.'))
        return super().write(values)

    def bpi_build_payload(self):
        variant_id = self.env.context.get('bpi_product_variant_id')
        if variant_id and not self.env.context.get('_bpi_building_variant'):
            return self.with_context(_bpi_building_variant=True).bpi_build_variant_payload(variant_id)
        result = super().bpi_build_payload()
        result['variantWorkspaceEnabled'] = bool(self.env['website'].search_count([
            ('bpi_variant_content_enabled', '=', True), ('company_id', 'in', self.env.companies.ids)] +
            ([('id', '=', self.website_id.id)] if self.website_id else [])))
        return result

    def _bpi_variant_facts(self, variant_id):
        variant = self.env['bpi.variant.content']._variant(self, variant_id)
        facts = self.with_context(_bpi_selected_facts=variant.id)._bpi_content_facts()
        scoped = []
        for fact in facts:
            parts = fact['id'].split(':')
            if parts[0] in ('variant', 'spec', 'pack') and len(parts) > 1 and parts[1] != str(variant.id):
                continue
            scoped.append(fact)
        return scoped

    def _bpi_saved_layout_media_ids(self):
        self.ensure_one()
        self.env['bpi.service']._ensure_manager()
        result = layout_media_ids(self.bpi_description_layout)
        for profile in self.env['bpi.variant.content'].search([('product_tmpl_id', '=', self.id)]):
            result |= layout_media_ids((profile.overrides or {}).get('descriptionLayout'))
        return result

    def _bpi_ai_catalog_context(self):
        variant_id = self.env.context.get('bpi_product_variant_id')
        if variant_id:
            return self._bpi_variant_catalog_context(variant_id)
        return super()._bpi_ai_catalog_context()

    def _bpi_variant_catalog_context(self, variant_id):
        variant = self.env['bpi.variant.content']._variant(self, variant_id)
        result = ['%s | SKU %s' % (variant.with_context(display_default_code=False).display_name, variant.default_code or '-')]
        if self.pack_ok:
            for line in variant.pack_line_ids[:60]:
                line.product_id.check_access_rights('read'); line.product_id.check_access_rule('read')
                if line.product_id.company_id and line.product_id.company_id not in self.env.companies:
                    continue
                result.append('%s × %s' % (line.quantity, line.product_id.display_name))
        return '\n'.join(result)[:6000]

    def _bpi_variant_semantic_context(self, scope):
        context = self._bpi_semantic_context()
        catalog = self.env['bpi.taxonomy.term']._catalog()
        ids = set(scope['values']['classification']['termIds'])
        context['axes'] = {axis: [t for t in catalog if t['axis'] == axis and t['id'] in ids]
                           for axis in context['axes']}
        context['revision'] = fingerprint([context['revision'], scope['variantId'], scope['values']['classification']])
        return context

    def _bpi_classification_source(self):
        variant_id = self.env.context.get('bpi_product_variant_id')
        if not variant_id:
            return super()._bpi_classification_source()
        variant, _profile, _base, values = self._bpi_effective_variant(variant_id)
        return {'name':variant.with_context(display_default_code=False).display_name,
                'sku':variant.default_code or '', 'internalCategory':self.categ_id.complete_name,
                'storeCategories':self.env['product.public.category'].browse(values['publicCategoryIds']).mapped('name'),
                'facts':self._bpi_variant_facts(variant_id), 'variantsAndPack':self._bpi_ai_catalog_context(),
                'savedDescriptionsNotTechnicalEvidence':[values['description'], values['technicalDescription']]}

    def _bpi_classification_payload(self):
        result = super()._bpi_classification_payload()
        variant_id = self.env.context.get('bpi_product_variant_id')
        if not variant_id:
            return result
        from .taxonomy import digest
        variant, profile, _base, values = self._bpi_effective_variant(variant_id)
        job = self.env['bpi.ai.job'].search([('product_tmpl_id','=',self.id), ('product_variant_id','=',variant.id),
                                           ('job_type','=','classification')], order='id desc', limit=1)
        result.update(values['classification'])
        result.update(revision=profile.revision if profile else 0, sourceRevision=digest(self._bpi_classification_source()),
                      legacyTermIds=[], reviewedAt=False, job=job.bpi_to_payload() if job else False)
        return result

    def _bpi_variant_gallery_library(self):
        self.ensure_one()
        rows = copy.deepcopy(self._bpi_gallery_payload())
        seen = {str(row.get('referenceToken') or row['id']) for row in rows}
        for row in rows:
            # Selection remains private until this exact reference is saved.
            row['canPublish'] = True
        for variant in self._bpi_all_variants():
            for image in variant.product_variant_image_ids:
                token = 'odoo:%s' % image.id
                if token in seen:
                    continue
                seen.add(token)
                rows.append({'id':token, 'referenceToken':token, 'name':image.name,
                    'imageUrl':self._bpi_image_url('product.image', image.id, 'image_1920'),
                    'imageType':'odoo_variant_extra', 'source':'odoo', 'state':'approved',
                    'sourceLabel':variant.display_name, 'variantId':variant.id,
                    'canPublish':True, 'canReference':True, 'canDelete':False, 'sequence':image.sequence})
        return rows

    def _bpi_variant_base(self):
        self.ensure_one()
        from .product_documents import empty_panel
        panel = self.env['bpi.product.document.panel'].search([('product_id','=',self.id), ('product_variant_id','=',False)], limit=1)
        documents = panel._payload() if panel else empty_panel()
        documents['revision'] = 0
        return {
            'documents': documents,
            'description': self.bpi_ai_generated_description or self.description_sale or '',
            'technicalDescription': self.bpi_technical_description or '',
            'templateId': self.bpi_content_template_id.id or False,
            'descriptionLayout': self.bpi_description_layout or empty_layout(),
            'faqs': [{'question': f.question, 'answer': f.answer} for f in self.bpi_faq_ids.sorted('sequence')],
            'videoUrl': self.bpi_video_url or '',
            'seoTitle': self.website_meta_title or self.name or '',
            'seoDescription': self.website_meta_description or '',
            'seoKeywords': self._bpi_keyword_values('seo'),
            'geoTitle': self.bpi_geo_title or '', 'geoDescription': self.bpi_geo_description or '',
            'geoKeywords': self._bpi_keyword_values('geo'), 'geoFeatures': self.bpi_geo_features or [],
            'tone': self.bpi_ai_tone or 'profesional', 'audience': self.bpi_ai_target_audience or 'clinicas',
            'classification': {'termIds': self.bpi_taxonomy_term_ids.ids, 'excludedTermIds': self.bpi_classification_excluded_ids or []},
            'publicCategoryIds': self.public_categ_ids.ids,
            'gallery': [str(row.get('referenceToken') or row['id']) for row in self._bpi_gallery_payload()],
        }

    def _bpi_effective_variant(self, variant_id):
        """Private base + overrides shared by editor, Studio and public projection."""
        self.ensure_one()
        profiles = self.env['bpi.variant.content']
        variant = profiles._variant(self, variant_id)
        record = profiles.search([('product_id', '=', variant.id)], limit=1)
        overrides = record.overrides or {} if record else {}
        base = self._bpi_variant_base()
        # Native inheritance: own main image replaces common main, never adds
        # all sibling main images to the selected edition.
        library = self._bpi_variant_gallery_library()
        common_gallery = [str(row.get('referenceToken') or row['id']) for row in library
                          if row.get('imageType') == 'odoo_gallery']
        own_gallery = ['odoo:%s' % image.id for image in variant.product_variant_image_ids]
        main = ['variant:%s' % variant.id] if variant.image_variant_1920 else (['main'] if self.image_1920 else [])
        base['gallery'] = main + own_gallery + common_gallery
        values = copy.deepcopy(dict(base, **overrides))
        documents = self.env['bpi.product.document.panel'].search([('product_id','=',self.id), ('product_variant_id','=',variant.id)], limit=1)
        # A retained private panel is not effective until explicitly customized.
        if overrides.get('documents') and documents:
            values['documents'] = documents._payload()
        else:
            values['documents'] = copy.deepcopy(base['documents'])
            values['documents']['revision'] = documents.revision if documents else 0
            base['documents']['revision'] = values['documents']['revision']
        return variant, record, base, values

    def _bpi_resolve_variant(self, variant_id):
        variant, record, base, values = self._bpi_effective_variant(variant_id)
        overrides = record.overrides or {} if record else {}
        recipe = self.env['bpi.service'].content_template_context(self, values['templateId'])
        context_revision = fingerprint([base, variant.default_code, variant.active,
            variant.product_template_attribute_value_ids.ids, self._bpi_variant_facts(variant.id),
            recipe.get('effective'), recipe.get('semanticRevision'), recipe.get('internalCategory'),
            [t for t in self.env['bpi.taxonomy.term']._catalog() if t['id'] in values['classification']['termIds']]])
        return {
            'productId': self.id, 'variantId': variant.id, 'sku': variant.default_code or '',
            'name': variant.with_context(display_default_code=False).display_name,
            'revision': record.revision if record else 0,
            'baseRevision': self.bpi_editorial_revision or 1,
            'contextRevision': context_revision,
            'overridden': sorted(overrides), 'values': values,
            'baseValues': copy.deepcopy(base), 'proposalId': record.proposal_id.id if record else False,
            'websiteUrl': '%s?variant=%s' % (self.website_url, variant.id),
            'fingerprint': fingerprint([values, variant.default_code, variant.product_template_attribute_value_ids.ids, variant.active]),
        }

    def bpi_build_variant_payload(self, variant_id):
        scope = self._bpi_resolve_variant(variant_id)
        result = self.with_context(_bpi_building_variant=True, bpi_product_variant_id=variant_id).bpi_build_payload()
        values = scope['values']
        selected = next(row for row in result['variants'] if row['id'] == variant_id)
        result['variantPricelists'] = self.env['product.pricelist'].search([
            '|', ('company_id', '=', False), ('company_id', 'in', self.env.companies.ids)]).read(['name', 'currency_id'])
        result['semanticContext'] = self._bpi_variant_semantic_context(scope)
        result['galleryLibrary'] = self._bpi_variant_gallery_library()
        result['variantContent'] = scope
        result['descriptionLayout'] = values['descriptionLayout']
        result['documents'] = values['documents']
        result['studioProposalId'] = scope['proposalId']
        result['product'].update(sku=scope['sku'], name=scope['name'], websiteUrl=scope['websiteUrl'],
            qtyAvailable=selected['qtyAvailable'], inStock=selected['inStock'],
            effectivePriceMinUsd=selected['effectivePriceUsd'], effectivePriceMaxUsd=selected['effectivePriceUsd'],
            costUsd=selected['costUsd'], effectiveCostMinUsd=selected['costUsd'], effectiveCostMaxUsd=selected['costUsd'],
            contentDescription=self._bpi_plain_text(values['description']),
            bpiTechnicalDescriptionHtml=values['technicalDescription'],
            bpiTechnicalDescription=self._bpi_plain_text(values['technicalDescription']),
            videoUrl=values['videoUrl'])
        result['seoData'].update({k: values[k] for k in TEXT_KEYS | LIST_KEYS if k not in ('tone', 'audience')})
        result['seoData'].update(aiGeneratedDescriptionHtml=values['description'],
            aiGeneratedDescription=self._bpi_plain_text(values['description']),
            aiTechnicalDescriptionHtml=values['technicalDescription'],
            aiTechnicalDescription=self._bpi_plain_text(values['technicalDescription']),
            aiTone=values['tone'], aiTargetAudience=values['audience'], geoFaq=values['faqs'])
        result['contentTemplates'] = self.env['bpi.service'].content_template_context(self, values['templateId'])
        result['classification'].update(values['classification'])
        result['technicalSpecifications'] = [r for r in result.get('technicalSpecifications', []) if r['variantId'] == variant_id]
        if result.get('pack', {}).get('isPack'):
            pack = result['pack']
            pack['compositions'] = [row for row in pack['compositions'] if row['variantId'] == variant_id]
            pack['componentCount'] = sum(len(row['components']) for row in pack['compositions'])
            if pack['compositions']:
                composition = pack['compositions'][0]
                for stem, source in [('effectivePrice', 'effectivePriceUsd'), ('componentCost', 'componentCostUsd')]:
                    for bound in ('Min', 'Max'):
                        pack[stem + bound + 'Usd'] = composition[source]
                result['product'].update(effectiveCostMinUsd=composition['componentCostUsd'], effectiveCostMaxUsd=composition['componentCostUsd'])

        images = {str(r.get('referenceToken') or r['id']): r for r in result['galleryLibrary']}
        result['images'] = [images[k] for k in values['gallery'] if k in images]
        image = result['images'][0]['imageUrl'] if result['images'] else False
        result['product'].update(mainImageUrl=image, imageUrl=image, imageLarge=image, galleryCount=len(result['images']),
            alternativeImages=[row['imageUrl'] for row in result['images'][1:]],
            referenceImages=[{'token':str(row.get('referenceToken') or row['id']),
                              'label':row['name'], 'url':row['imageUrl']} for row in result['images'] if row.get('canReference')])
        result['chatHistory'] = []
        result['chatSessionId'] = False
        # Legacy competitive observations/strategies are template-owned. Never
        # present those numbers as a comparison for the selected SKU.
        result['competitors'] = []
        result['competitiveStrategy'] = {}
        # Completeness is a saved-content checklist, not the common product's
        # analysis score. Intentional empty overrides must appear as missing.
        plain = self._bpi_plain_text
        flags = {
            'commercial': bool(plain(values['description'])),
            'technical': bool(plain(values['technicalDescription'])),
            'image': bool(result['images']),
            'seo': bool(plain(values['seoTitle']) and plain(values['seoDescription'])),
            'geo': bool(plain(values['geoTitle']) and plain(values['geoDescription'])),
            'faq': any(plain(row.get('question')) and plain(row.get('answer')) for row in values['faqs']),
            'category': bool(values['publicCategoryIds']),
            'competitor': False,
        }
        result['product']['catalogHealth'] = self.env['bpi.service']._dashboard_catalog_health(
            {key: {self.id} if present else set() for key, present in flags.items()}, self.id)
        # No edition-specific legacy scoring analysis has been performed.
        result['seoData'].update(seoScore=None, geoScore=None, competitivenessScore=None, lastAnalyzedAt=False)
        return result


class VariantWebsite(models.Model):
    _inherit = 'website'
    bpi_variant_content_enabled = fields.Boolean(string='BPI: fichas por variante', default=False, copy=False)

    @api.model_create_multi
    def create(self, values_list):
        if any('bpi_variant_content_enabled' in values for values in values_list):
            self.env['bpi.service']._ensure_manager()
        return super().create(values_list)

    def write(self, values):
        if 'bpi_variant_content_enabled' in values:
            self.env['bpi.service']._ensure_manager()
        return super().write(values)


class VariantGalleryReference(models.Model):
    _inherit = 'bpi.product.image'

    def unlink(self):
        profiles = self.env['bpi.variant.content'].sudo().search([('product_tmpl_id', 'in', self.product_tmpl_id.ids)])
        used = {token for profile in profiles for token in (profile.overrides or {}).get('gallery', [])}
        if any('bpi:%s' % image.id in used for image in self):
            raise UserError(_('Esta imagen se usa en la galería de una variante. Quita primero esa referencia y guarda.'))
        return super().unlink()
