/** @odoo-module **/
const SECTIONS = {
    content: ['description', 'technicalDescription', 'templateId', 'descriptionLayout', 'faqs', 'tone', 'audience', 'documents'],
    seo: ['seoTitle', 'seoDescription', 'seoKeywords', 'geoTitle', 'geoDescription', 'geoKeywords', 'geoFeatures'],
    categorization: ['classification', 'publicCategoryIds'], images: ['videoUrl', 'gallery'],
};
const LABELS = ['Descripción corta', 'Descripción larga', 'Modelo editorial', 'Diseño Bader', 'Preguntas frecuentes', 'Tono', 'Público editorial', 'Documentos',
    'Título SEO', 'Descripción SEO', 'Palabras SEO', 'Título GEO', 'Descripción GEO', 'Palabras GEO', 'Características GEO',
    'Clasificación comercial', 'Categorías de tienda', 'Vídeo', 'Galería'];
const KEYS = Object.values(SECTIONS).flat();
const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b);

export const variantWorkspaceMethods = {
    variantPendingSummary() {
        const labels = this.detailDirtySections().map(section => section.label);
        if (this.variantScopeModesDirty()) labels.push('Herencia de esta edición');
        if (this.state.variantPriceRule) labels.push('Regla de tarifa');
        for (const [key, cached] of Object.entries(this.variantWorkspaceDrafts || {})) {
            if (!key.startsWith(`${this.state.productId}:`) || key === this.variantWorkspaceKey() || !cached.dirty) continue;
            const scope = cached.detail?.variantContent;
            labels.push(scope ? `Otra edición: ${scope.sku || scope.name || scope.variantId}` : 'Contenido común');
        }
        return labels.join(', ');
    },
    variantScopeBusy() {
        return this.detailBaseSaveBusy() || this.state.imageBusy || this.state.variantBusy ||
            this.state.packBusy || this.state.descriptionMediaBusy || this.state.variantPriceBusy;
    },
    variantWorkspaceKey(id = this.state.workspaceVariantId) { return `${this.state.productId}:${id || 'common'}`; },
    variantWorkspaceFields() {
        return (SECTIONS[this.state.activeTab] || []).map(key => ({key, label: LABELS[KEYS.indexOf(key)], custom: this.variantFieldCustomized(key)}));
    },
    variantValues() {
        const content = this.state.contentForm || {}, seo = this.seoSaveValues(), classification = this.state.categoryForm?.classification || {};
        return {
            ...Object.fromEntries(SECTIONS.content.map(key => [key, content[key]])),
            ...Object.fromEntries(SECTIONS.seo.map(key => [key, seo[key]])),
            classification: {termIds: [...(classification.termIds || [])], excludedTermIds: [...(classification.excludedTermIds || [])]},
            publicCategoryIds: [...(this.state.variantPublicCategoryIds || [])], gallery: [...(this.state.variantGalleryTokens || [])],
            videoUrl: this.state.imageForm?.videoUrl || '',
        };
    },
    setVariantValue(key, value) {
        value = this.snapshotDraft(value);
        if (SECTIONS.content.includes(key)) this.state.contentForm[key] = value;
        else if (SECTIONS.seo.includes(key)) this.state.seoForm[key] = Array.isArray(value) ? value.join(', ') : value;
        else if (key === 'classification') this.state.categoryForm.classification = {...(this.state.categoryForm.classification || {}), ...value};
        else if (key === 'publicCategoryIds') this.state.variantPublicCategoryIds = value;
        else if (key === 'gallery') this.state.variantGalleryTokens = value;
        else if (key === 'videoUrl') this.state.imageForm.videoUrl = value;
    },
    applyVariantScope(scope) {
        this.state.workspaceVariantId = scope.variantId;
        this.state.selectedVariantId = scope.variantId;
        this.state.variantModes = Object.fromEntries(KEYS.map(key => [key, scope.overridden.includes(key)]));
        for (const [key, value] of Object.entries(scope.values)) this.setVariantValue(key, value);
    },
    variantFieldCustomized(key) {
        const scope = this.state.detail?.variantContent;
        if (!scope) return false;
        const baseline = this.state.variantModes[key] ? scope.values[key] : scope.baseValues[key];
        return !!this.state.variantModes[key] || !equal(this.variantValues()[key], baseline);
    },
    toggleVariantInheritance(key) {
        const scope = this.state.detail?.variantContent;
        if (!scope || this.detailBaseSaveBusy()) return;
        if (this.variantFieldCustomized(key)) {
            this.setVariantValue(key, scope.baseValues[key]);
            this.state.variantModes[key] = false;
        } else this.state.variantModes[key] = true;
    },
    variantScopeModesDirty() {
        const scope = this.state.detail?.variantContent;
        return !!scope && KEYS.some(k => this.variantFieldCustomized(k) !== scope.overridden.includes(k));
    },
    async switchWorkspaceVariant(ev) {
        const id = Number(ev.target.value) || false;
        if (id === this.state.workspaceVariantId || this.state.variantScopeLoading || this.variantScopeBusy()) return;
        this.variantWorkspaceDrafts ||= {};
        const oldId = this.state.workspaceVariantId;
        const previous = {detail: this.snapshotDraft(this.state.detail), drafts: this.captureDrafts(),
            baseline: this.snapshotDraft(this.detailBaseline), modes: {...this.state.variantModes}, values: this.variantValues(),
            playground: this.snapshotDraft(this.state.playground), chatInput: this.state.chatInput,
            studio: this.snapshotDraft(this.state.contentStudio), priceRule: this.snapshotDraft(this.state.variantPriceRule), pricing: this.snapshotDraft(this.state.variantPricing), dirty: !!this.state.variantPriceRule || this.detailDirtySections().length > 0 || this.variantScopeModesDirty()};
        this.variantWorkspaceDrafts[this.variantWorkspaceKey()] = previous;
        this.invalidateProductRequests();
        this.state.workspaceVariantId = id;
        this.state.variantScopeLoading = true;
        const request = this.beginRequest('variantScope');
        const restore = cached => {
            this.applyDetailPayload(cached.detail);
            Object.assign(this.state, cached.drafts);
            this.detailBaseline = cached.baseline; this.state.variantModes = cached.modes;
            this.state.variantPublicCategoryIds = cached.values.publicCategoryIds;
            this.state.variantGalleryTokens = cached.values.gallery;
            this.state.variantPriceRule = cached.priceRule; this.state.variantPricing = cached.pricing;
            if (cached.playground) this.state.playground = cached.playground;
            if (cached.chatInput !== undefined) this.state.chatInput = cached.chatInput;
            this.state.contentStudio = cached.studio || this.state.contentStudio;
            this.state.contentStudio.open = false;
            this.state.contentStudio.busy = false;
            this.state.contentStudio.loading = false;
        };
        try {
            const data = await this.rpc('/bader_product_intelligence/data', {product_tmpl_id: request.productId, product_variant_id: id});
            if (!this.isRequestCurrent(request)) return;
            const cached = this.variantWorkspaceDrafts[this.variantWorkspaceKey()];
            if (cached?.dirty) {
                restore(cached);
                // Jobs are server history, not an editable draft. Restore the
                // newest scoped job without applying its proposal automatically.
                this.state.classificationJob = data.classification?.job || null;
                if (cached.detail.variantContent?.revision !== data.variantContent?.revision || cached.detail.editorialRevision !== data.editorialRevision) {
                    this.notify('Hay cambios guardados por otro operador. Conservamos tus borradores; revisa antes de guardar.', 'warning');
                }
            } else {
                this.applyDetailPayload(data);
                delete this.variantWorkspaceDrafts[this.variantWorkspaceKey()];
            }
        } catch (error) {
            if (!this.isRequestCurrent(request)) return;
            this.state.workspaceVariantId = oldId;
            restore(previous);
            this.notify(this.errorMessage(error, 'No se pudo abrir esta variante.'), 'danger');
        } finally {
            if (request.generation === (this.viewGeneration || 0) && request.productId === this.state.productId) {
                this.state.variantScopeLoading = false;
                if (this.state.activeTab === 'mercadolibre') await this.loadMeliDetail();
            }
        }
    },
    async saveVariantSpecifications() {
        if (this.detailBaseSaveBusy()) return false;
        const scope = this.state.detail?.variantContent;
        if (!scope) return false;
        const request = this.beginRequest('variantSpecifications', true);
        this.state.saveBusy = true;
        try {
            const data = await this.rpc('/bader_product_intelligence/variant_specs/save', {
                product_tmpl_id: request.productId, product_variant_id: scope.variantId,
                base_revision: scope.baseRevision, revision: scope.revision, context_revision: scope.contextRevision,
                specifications: request.drafts.productForm.technicalSpecifications,
            });
            if (!this.isRequestCurrent(request)) return false;
            const values = this.variantValues(), modes = {...this.state.variantModes};
            this.applyDetailUpdate(data, request, {productForm:['technicalSpecifications']});
            for (const [key, value] of Object.entries(values)) this.setVariantValue(key, value);
            this.state.variantModes = modes;
            this.notify('Especificaciones guardadas para este SKU. No se modificaron tarifas.');
            return true;
        } catch(error) {
            if (this.isRequestCurrent(request)) this.notify(this.errorMessage(error, 'No se pudieron guardar las especificaciones.'), 'danger');
            return false;
        } finally { if (this.isRequestCurrent(request)) this.state.saveBusy = false; }
    },
    async loadVariantPricing() {
        if (!this.state.workspaceVariantId || this.state.variantPriceBusy) return;
        const request = this.beginRequest('variantPricing');
        const query = this.state.variantPriceQuery;
        this.state.variantPriceBusy = true;
        try {
            const data = await this.rpc('/bader_product_intelligence/variant_pricing/data', {
                product_tmpl_id: request.productId, product_variant_id: request.variantId,
                pricelist_id: Number(query.pricelistId), quantity: Number(query.quantity), date: query.date || false,
            });
            if (this.isRequestCurrent(request)) { this.state.variantPricing = data; this.state.variantPriceRule = null; }
        } catch(error) {
            if (this.isRequestCurrent(request)) this.notify(this.errorMessage(error, 'No se pudo consultar la tarifa.'), 'danger');
        } finally { if (this.isRequestCurrent(request)) this.state.variantPriceBusy = false; }
    },
    editVariantPriceRule(rule = null) {
        this.state.variantPriceRule = rule ? {...rule} : {id:false, compute_price:'fixed', fixed_price:0, percent_price:0, min_quantity:1, date_start:'', date_end:''};
    },
    async saveVariantPriceRule() {
        if (this.state.variantPriceBusy || !this.state.variantPricing || !this.state.variantPriceRule) return;
        const request = this.beginRequest('variantPricing');
        const data = this.state.variantPricing, draft = this.snapshotDraft(this.state.variantPriceRule);
        const values = Object.fromEntries(['compute_price','date_start','date_end'].map(k=>[k,draft[k] || false]));
        for (const k of ['fixed_price','percent_price','min_quantity']) values[k]=Number(draft[k]);
        this.state.variantPriceBusy = true;
        try {
            const result = await this.rpc('/bader_product_intelligence/variant_pricing/save', {
                product_tmpl_id: request.productId, product_variant_id: request.variantId,
                pricelist_id: data.pricelistId, revision:data.revision, rule_id:draft.id || false, values,
                quantity:data.quantity, date:data.date,
            });
            if (!this.isRequestCurrent(request)) return;
            this.state.variantPricing = result;
            if (equal(this.state.variantPriceRule, draft)) this.state.variantPriceRule = null;
            this.notify('Regla nativa guardada para este SKU. El contenido editorial no cambió.');
        } catch(error) {
            if (this.isRequestCurrent(request)) this.notify(this.errorMessage(error, 'No se pudo guardar la regla de tarifa.'), 'danger');
        } finally { if (this.isRequestCurrent(request)) this.state.variantPriceBusy = false; }
    },
    variantGalleryLibrary() { return this.state.detail?.galleryLibrary || this.currentImages(); },
    variantGallerySelected(token) { return (this.state.variantGalleryTokens || []).includes(token); },
    toggleVariantGallery(token) {
        const rows = this.state.variantGalleryTokens || [];
        this.state.variantGalleryTokens = rows.includes(token) ? rows.filter(t=>t!==token) : [...rows, token];
        this.state.variantModes.gallery = true;
    },
    moveVariantGallery(token, offset) {
        const rows = [...this.state.variantGalleryTokens], index = rows.indexOf(token), target = index + offset;
        if (index < 0 || target < 0 || target >= rows.length) return;
        [rows[index],rows[target]] = [rows[target],rows[index]];
        this.state.variantGalleryTokens = rows; this.state.variantModes.gallery = true;
    },
    toggleVariantCategory(id) {
        const rows = this.state.variantPublicCategoryIds || [];
        this.state.variantPublicCategoryIds = rows.includes(id) ? rows.filter(v=>v!==id) : [...rows,id];
        this.state.variantModes.publicCategoryIds = true;
    },
    async saveVariantScope(section = 'all') {
        if (this.detailBaseSaveBusy()) return false;
        const scope = this.state.detail?.variantContent;
        if (!scope) return false;
        const request = this.beginRequest('variantSave', true), values = this.variantValues();
        const submittedModes = {...this.state.variantModes};
        const saveSpecs = section === 'all' && this.detailDirtySections().some(row => row.id === 'datos');
        const keys = section === 'all' ? KEYS : (SECTIONS[section] || []);
        if (!keys.length) {
            this.notify('Usa las acciones nativas para datos operativos. El contenido común se edita seleccionando Contenido común.', 'info');
            return false;
        }
        const changes = {}, inherit = [];
        for (const key of keys) {
            if (this.variantFieldCustomized(key)) changes[key] = values[key];
            else if (scope.overridden.includes(key)) inherit.push(key);
        }
        this.state.saveBusy = true;
        try {
            const result = await this.rpc('/bader_product_intelligence/variant_content/save', {
                product_tmpl_id: request.productId, product_variant_id: scope.variantId,
                base_revision: scope.baseRevision, revision: scope.revision, context_revision: scope.contextRevision, changes, inherit,
                ...(saveSpecs ? {specifications: request.drafts.productForm.technicalSpecifications} : {}),
                ...(this.state.contentForm.studioProposalId && this.state.contentForm.studioProposalId !== scope.proposalId ? {proposal_id: this.state.contentForm.studioProposalId} : {}),
            });
            if (!this.isRequestCurrent(request)) return false;
            const retainedModes = {...this.state.variantModes};
            const retainedValues = this.variantValues();
            const updates = section === 'all' ? {contentForm:true,seoForm:true,categoryForm:true,imageForm:true,...(saveSpecs ? {productForm:['technicalSpecifications']} : {})} :
                ({content:{contentForm:true},seo:{seoForm:true},categorization:{categoryForm:true},images:{imageForm:true}}[section]);
            this.applyDetailUpdate(result, request, updates);
            for (const key of KEYS) {
                if (!keys.includes(key) || !equal(retainedValues[key], values[key]) || retainedModes[key] !== submittedModes[key]) {
                    this.setVariantValue(key, retainedValues[key]);
                    this.state.variantModes[key] = retainedModes[key];
                }
            }
            if (this.variantWorkspaceDrafts) delete this.variantWorkspaceDrafts[this.variantWorkspaceKey()];
            this.notify('Variante guardada. No se modificaron otras variantes ni tarifas.');
            return true;
        } catch (error) {
            if (this.isRequestCurrent(request)) this.notify(this.errorMessage(error, 'No se pudo guardar la variante.'), 'danger');
            return false;
        } finally { if (this.isRequestCurrent(request)) this.state.saveBusy = false; }
    },
};
