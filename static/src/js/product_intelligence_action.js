/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useSetupAction } from "@web/webclient/actions/action_hook";
import { Component, onWillStart, onWillUnmount, onMounted, onPatched, useState, useRef } from "@odoo/owl";

const DASHBOARD_PAGE_SIZE = 40;
const MAX_IMAGE_UPLOAD_BYTES = 10 * 1024 * 1024;
const ALLOWED_IMAGE_UPLOAD_TYPES = new Set(["image/png", "image/jpeg", "image/webp"]);
const MAX_CHAT_MESSAGE_LENGTH = 4000;
const SAFE_ODOO_ERROR_NAMES = new Set([
    "odoo.exceptions.UserError", "odoo.exceptions.ValidationError", "odoo.exceptions.AccessError",
]);
const DESCRIPTION_FONT_FAMILIES = [
    { value: "Arial", label: "Arial" },
    { value: "Verdana", label: "Verdana" },
    { value: "Tahoma", label: "Tahoma" },
    { value: "Trebuchet MS", label: "Trebuchet" },
    { value: "Georgia", label: "Georgia" },
    { value: "Times New Roman", label: "Times New Roman" },
    { value: "Courier New", label: "Courier New" },
];
const DESCRIPTION_FONT_SIZES = [
    { value: "12px", label: "12" },
    { value: "14px", label: "14" },
    { value: "16px", label: "16" },
    { value: "18px", label: "18" },
    { value: "24px", label: "24" },
    { value: "32px", label: "32" },
];
const DESCRIPTION_BLOCK_FORMATS = [
    { value: "p", label: "Parrafo" },
    { value: "h2", label: "Titulo 2" },
    { value: "h3", label: "Titulo 3" },
    { value: "h4", label: "Titulo 4" },
    { value: "blockquote", label: "Cita" },
];
const DESCRIPTION_LEGACY_FONT_SIZES = {
    1: "10px",
    2: "12px",
    3: "14px",
    4: "18px",
    5: "24px",
    6: "32px",
    7: "48px",
};
const DESCRIPTION_COMMAND_FONT_SIZES = {
    "12px": "2",
    "14px": "3",
    "16px": "3",
    "18px": "4",
    "24px": "5",
    "32px": "6",
};
const DESCRIPTION_ALLOWED_FONT_SIZES = new Set([
    ...DESCRIPTION_FONT_SIZES.map((item) => item.value),
    "10px",
    "48px",
]);
const DESCRIPTION_ALLOWED_ALIGNMENTS = new Set(["left", "center", "right", "justify"]);
const DESCRIPTION_ALLOWED_INDENTS = new Set(["40px", "80px", "120px", "160px", "200px"]);

export function competitorComparablePriceUsd(competitor) {
    if (competitor?.priceStatus && competitor.priceStatus !== "known") return 0;
    const value = Number(competitor?.competitorOfferPriceUsd || competitor?.competitorPriceUsd || 0);
    return Number.isFinite(value) && value > 0 ? value : 0;
}

export function canDeleteGalleryImage(image) {
    return !!(image?.canDelete && /^bpi:[1-9][0-9]*$/.test(image?.referenceToken || ""));
}

export function productEffectivePriceRange(product) {
    const fallback = Number(product?.priceUsd || 0);
    const min = Number(product?.effectivePriceMinUsd ?? fallback);
    const max = Number(product?.effectivePriceMaxUsd ?? min);
    return {
        min: Number.isFinite(min) ? min : 0,
        max: Number.isFinite(max) ? max : 0,
    };
}

const DETAIL_TABS = [
    { id: "overview", label: "Resumen", icon: "fa-bar-chart" },
    { id: "datos", label: "Datos y precios", icon: "fa-cog" },
    { id: "variants_pack", label: "Variantes y Pack", icon: "fa-cubes" },
    { id: "categorization", label: "Clasificación", icon: "fa-sitemap" },
    { id: "content", label: "Descripciones y FAQs", icon: "fa-pencil" },
    { id: "images", label: "Imágenes y vídeo", icon: "fa-picture-o" },
    { id: "seo", label: "SEO y GEO", icon: "fa-search" },
    { id: "mercadolibre", label: "MercadoLibre", icon: "fa-shopping-bag" },
    { id: "competitors", label: "Competidores y precios", icon: "fa-bullseye" },
    { id: "chat", label: "Agente Nancy", icon: "fa-comments" },
];

const CHAT_QUICK_ACTIONS = [
    "Sugiere una descripcion atractiva",
    "Como mejorar el SEO de este producto?",
    "Ideas de promociones",
    "Analiza el precio vs competencia",
];

const NICHE_OPTIONS = [
    { id: "clinica", label: "Clinica Dental", icon: "fa-hospital-o" },
    { id: "laboratorio", label: "Laboratorio Dental", icon: "fa-flask" },
    { id: "estudiantes", label: "Estudiantes", icon: "fa-graduation-cap" },
];

const TYPE_OPTIONS = [
    { value: "consumible", label: "Consumible" },
    { value: "equipo", label: "Equipo" },
    { value: "instrumental", label: "Instrumental" },
    { value: "mobiliario", label: "Mobiliario" },
    { value: "protesis", label: "Protesis" },
    { value: "ortodoncia", label: "Ortodoncia" },
    { value: "endodoncia", label: "Endodoncia" },
    { value: "cirugia", label: "Cirugia" },
    { value: "higiene", label: "Higiene" },
    { value: "radiologia", label: "Radiologia" },
    { value: "otro", label: "Otro" },
];

const TYPE_ALIASES = {
    clamp: "instrumental",
    clamps: "instrumental",
    clamp_dental: "instrumental",
    instrumental_de_mano: "instrumental",
    instrumental_dental: "instrumental",
    instrumento: "instrumental",
    instrumentos: "instrumental",
    material: "consumible",
    materiales: "consumible",
    insumo: "consumible",
    insumos: "consumible",
    equipamiento: "equipo",
    equipos: "equipo",
};

const SUBCATEGORY_OPTIONS = [
    { value: "aislamiento", label: "Aislamiento / Clamps" },
    { value: "adhesivos", label: "Adhesivos" },
    { value: "anestesia", label: "Anestesia" },
    { value: "blanqueamiento", label: "Blanqueamiento" },
    { value: "cementos", label: "Cementos" },
    { value: "composites", label: "Composites" },
    { value: "desechables", label: "Desechables" },
    { value: "endodoncia", label: "Endodoncia" },
    { value: "esterilizacion", label: "Esterilizacion" },
    { value: "fresas", label: "Fresas" },
    { value: "higiene", label: "Higiene / Profilaxis" },
    { value: "implantes", label: "Implantes" },
    { value: "impresion", label: "Impresion" },
    { value: "instrumental_clinico", label: "Instrumental Clinico" },
    { value: "laboratorio", label: "Laboratorio" },
    { value: "matrices_bandas", label: "Matrices y Bandas" },
    { value: "ortodoncia", label: "Ortodoncia" },
    { value: "profilaxis", label: "Profilaxis" },
    { value: "protesis", label: "Protesis" },
    { value: "radiologia", label: "Radiologia" },
    { value: "restauracion", label: "Restauracion" },
    { value: "otro", label: "Otro" },
];

const SUBCATEGORY_ALIASES = {
    clamp: "aislamiento",
    clamps: "aislamiento",
    clamp_para_dique_de_goma: "aislamiento",
    dique: "aislamiento",
    dique_de_goma: "aislamiento",
    aislamiento_absoluto: "aislamiento",
    aislamiento_dental: "aislamiento",
    instrumental: "instrumental_clinico",
    instrumental_dental: "instrumental_clinico",
    instrumental_de_mano: "instrumental_clinico",
    higiene_dental: "higiene",
    profilaxis_dental: "profilaxis",
    fresas_dentales: "fresas",
    impresion_dental: "impresion",
    materiales_de_impresion: "impresion",
    descartables: "desechables",
    restauraciones: "restauracion",
};

export class ProductIntelligenceAction extends Component {
    setup() {
        this.rawRpc = useService("rpc");
        this.user = useService("user");
        this.rpc = (route, params, settings) => this.rpcWithContext(route, params, settings);
        this.notification = useService("notification");
        this.action = useService("action");

        this.detailTabs = DETAIL_TABS;
        this.nicheOptions = NICHE_OPTIONS;
        this.typeOptions = TYPE_OPTIONS;
        this.subcategoryOptions = SUBCATEGORY_OPTIONS;
        this.chatQuickActions = CHAT_QUICK_ACTIONS;
        this.descriptionFontFamilies = DESCRIPTION_FONT_FAMILIES;
        this.descriptionFontSizes = DESCRIPTION_FONT_SIZES;
        this.descriptionBlockFormats = DESCRIPTION_BLOCK_FORMATS;
        this.dashboardReloadTimer = null;
        this.seoJobPollTimer = null;
        this.detailLoadSequence = 0;
        this.chatRequestSequence = 0;
        this.requestSequences = {};
        this.viewGeneration = 0;
        this.destroyed = false;
        this.scrollSetupTimer = null;

        this.state = useState({
            loading: true,
            error: "",
            viewMode: "dashboard",
            origin: "menu",
            productId: null,
            dashboardBusy: false,
            dashboardSection: "overview",
            dashboardOverview: this.dashboardDefaultOverview(),
            overviewBusy: false,
            overviewError: "",
            dashboardCategoryId: "",
            dashboardQualityFilter: "",
            dashboardSortKey: "catalog",
            catalogReviewId: false,
            catalogBusyRows: {},
            dashboardCatalogUpdatedAt: "",
            showDashboardSettings: false,
            dashboardTab: "all",
            searchTerm: "",
            exchangeRateInput: "1650",
            exchangeRate: 1650,
            dashboardRows: [],
            dashboardStats: {
                total: 0,
                published: 0,
                featured: 0,
                pending: 0,
            },
            dashboardTabCounts: {
                all: 0,
                new: 0,
                discontinued: 0,
            },
            dashboardPager: {
                page: 1,
                pageCount: 1,
                total: 0,
                limit: DASHBOARD_PAGE_SIZE,
                hasNext: false,
                hasPrevious: false,
            },
            detail: null,
            activeTab: "overview",
            detailLeavePrompt: false,
            detailLeaveBusy: false,
            meliAccountId: "",
            meliFilter: "",
            meliCatalogContext: {},
            meliDetail: { available: false, groups: [], jobs: [], summary: {} },
            meliBusy: false,
            meliError: "",
            meliRefreshBusy: false,
            meliRefreshJob: false,
            meliRefreshMessage: "",
            saveBusy: false,
            exchangeRateBusy: false,
            seoBusy: false,
            seoJobId: false,
            seoJobMessage: "",
            seoPreviewPending: false,
            contentBusy: false,
            contentTemplateContext: null,
            contentTemplateBusy: false,
            contentTemplateAdminBusy: false,
            contentTemplateError: "",
            contentGenerationWarnings: [],
            faqBusy: false,
            imageBusy: false,
            competitorBusy: false,
            strategyBusy: false,
            categoryBusy: false,
            taxonomyPicker: "", taxonomyNotice: "", taxonomyAnalyzing: false, classificationJob: null, taxonomyQuery: "", taxonomyFilters: [], taxonomyFacets: [],
            taxonomyAiTermIds: [], taxonomyTermDetail: null, taxonomyDismissedPending: [],
            chatBusy: false,
            variantBusy: false,
            packBusy: false,
            componentSearchBusy: false,
            chatMessages: [],
            chatSessionKey: "",
            chatInput: "",
            expandedCompetitorId: null,
            showImageModal: false,
            showAddUrlInput: false,
            productForm: this.emptyProductForm(),
            contentForm: this.emptyContentForm(),
            seoForm: this.emptySeoForm(),
            categoryForm: this.emptyCategoryForm(),
            imageForm: this.emptyImageForm(),
            competitorForm: this.emptyCompetitorForm(),
            selectedVariantId: null,
            variantDrafts: [],
            packForm: this.emptyPackForm(),
            componentSearch: {
                query: "",
                results: [],
            },
            playground: {
                messages: [],
                canvasUrl: "",
                inputText: "",
            },
        });

        this.fileUploadInputRef = useRef("fileUploadInput");
        this.playgroundMessagesRef = useRef("playgroundMessages");
        this.contentDescriptionEditorRef = useRef("contentDescriptionEditor");
        this.technicalDescriptionEditorRef = useRef("technicalDescriptionEditor");
        this.detailLeaveDialogRef = useRef("detailLeaveDialog");
        this.taxonomyMapRef = useRef("taxonomyMap");
        this.lastContentDescriptionEditorHtml = "";
        this.lastTechnicalDescriptionEditorHtml = "";
        this.contentDescriptionSelection = null;
        this.technicalDescriptionSelection = null;

        useSetupAction({
            beforeLeave: () => this.confirmDetailLeave(),
            beforeUnload: (ev) => this.onDetailBeforeUnload(ev),
        });

        onWillStart(async () => {
            const productId = this.resolveProductId();
            this.state.origin = this.resolveOrigin();
            if (productId) {
                this.state.productId = productId;
                await this.loadDetail(productId);
            } else {
                await this.loadDashboardOverview();
            }
        });

        onMounted(() => {
            this._setupScrollListener();
            this._setupKeyboardShortcuts();
            this.syncContentDescriptionEditor(true);
            this.syncTechnicalDescriptionEditor(true);
        });

        onPatched(() => {
            this.syncContentDescriptionEditor();
            this.syncTechnicalDescriptionEditor();
            this.syncDetailLeaveFocus();
            this.syncTaxonomyFocus();
        });

        onWillUnmount(() => {
            this.destroyed = true;
            if (this.detailLeaveResolver) this.detailLeaveResolver(false);
            this.invalidateProductRequests();
            clearTimeout(this.scrollSetupTimer);
            this._cleanupScrollListener();
            this._cleanupKeyboardShortcuts();
        });
    }

    _setupScrollListener() {
        this._scrollHandler = () => {
            const header = this.el?.querySelector?.(".bpi-detail-header");
            const shell = this.el?.querySelector?.(".bpi-detail-shell");
            if (header && shell) {
                header.classList.toggle("is-scrolled", shell.scrollTop > 40);
            }
        };
        // Defer to let OWL render
        this.scrollSetupTimer = setTimeout(() => {
            if (this.destroyed) return;
            const shell = this.el?.querySelector?.(".bpi-detail-shell");
            if (shell) {
                shell.addEventListener("scroll", this._scrollHandler, { passive: true });
            }
            // Also listen on the parent .o_action since it may be the scrolling container
            const action = this.el?.closest?.(".o_action.bpi-app");
            if (action) {
                action.addEventListener("scroll", this._scrollHandler, { passive: true });
            }
        }, 100);
    }

    _cleanupScrollListener() {
        if (this._scrollHandler) {
            const shell = this.el?.querySelector?.(".bpi-detail-shell");
            if (shell) shell.removeEventListener("scroll", this._scrollHandler);
            const action = this.el?.closest?.(".o_action.bpi-app");
            if (action) action.removeEventListener("scroll", this._scrollHandler);
        }
    }

    _setupKeyboardShortcuts() {
        this._keyHandler = (ev) => {
            if ((ev.ctrlKey || ev.metaKey) && ev.key === "s") {
                ev.preventDefault();
                if (this.state.viewMode === "detail" && !this.state.saveBusy) {
                    this.saveCurrentDetailSection();
                }
            }
        };
        document.addEventListener("keydown", this._keyHandler);
    }

    _cleanupKeyboardShortcuts() {
        if (this._keyHandler) {
            document.removeEventListener("keydown", this._keyHandler);
        }
    }

    _scoreLevel(score) {
        if (score <= 30) return "critical";
        if (score <= 60) return "warning";
        return "good";
    }

    scoreCardClick(tab) {
        this.selectTab(tab);
    }

    emptyProductForm() {
        return {
            name: "",
            sku: "",
            slug: "",
            brand: "Bader",
            categoryId: "",
            priceUsd: "0",
            previousPriceUsd: "",
            costUsd: "",
            qtyAvailable: "",
            featured: false,
            isPublished: false,
        };
    }

    emptyContentForm() {
        return {
            templateId: false,
            tone: "profesional",
            audience: "clinicas",
            name: "",
            description: "",
            technicalDescription: "",
            faqs: [],
        };
    }

    emptySeoForm() {
        return {
            seoTitle: "",
            seoDescription: "",
            slug: "",
            seoKeywords: "",
            geoTitle: "",
            geoKeywords: "",
            geoDescription: "",
            geoFeatures: "",
        };
    }

    emptyCategoryForm() {
        return {
            manualMode: false,
            niches: [],
            type: "",
            subcategory: "",
        };
    }

    emptyImageForm() {
        return {
            prompt: "",
            style: "professional",
            selectedReferences: [],
            generatedPreviewUrl: "",
            selectedGalleryUrl: "",
            addImageUrl: "",
            videoUrl: "",
            uploadedRefUrl: "",
            uploadedRefName: "",
        };
    }

    emptyCompetitorForm() {
        return {
            competitorName: "",
            competitorUrl: "",
            discoveredCompetitors: [],
            discoveryQuery: "",
        };
    }

    emptyPackForm() {
        return {
            isPack: false,
            packType: "detailed",
            componentPriceMode: "ignored",
            modifiable: false,
            revision: false,
            warnings: [],
            compositions: [],
        };
    }

    resolveProductId() {
        const params = this.props.action.params || {};
        const context = this.props.action.context || {};
        return params.product_tmpl_id || context.active_id || null;
    }

    resolveOrigin() {
        const params = this.props.action.params || {};
        return params.origin || "menu";
    }

    meliContext() {
        if (this.state.viewMode === 'detail') return this.state.meliDetail || {};
        return this.state.dashboardSection === 'overview'
            ? (this.state.dashboardOverview?.meliOverview || {}) : (this.state.meliCatalogContext || {});
    }

    meliOverviewMetrics() { return this.state.dashboardOverview?.meliOverview?.kpis || []; }
    meliAccountOptions() { return this.meliContext().accounts || []; }
    meliGroups() { return this.state.meliDetail?.groups || []; }
    meliCanRefresh() { return !!this.state.meliDetail?.canRefresh && !this.state.meliRefreshBusy && !this.state.meliBusy && !['pending', 'running'].includes(this.state.meliRefreshJob?.state); }
    meliDateLabel(value) { return value ? this.dashboardDateLabel(value) : 'Sin observación verificada'; }

    meliValue(value, currency = false) {
        if (value === null || value === undefined || value === '' || value === false || !Number.isFinite(Number(value))) return 'Sin verificar';
        return currency ? this.formatCompetitorPrice(value, currency) : this.formatNumber(value);
    }

    meliStateLabel(value) {
        return {
            available: 'Datos locales disponibles', not_installed: 'Integración no instalada', no_access: 'Sin permiso de acceso',
            no_account: 'Sin cuenta disponible', read_disabled: 'Consulta remota desactivada', unavailable: 'Sin verificar',
            unlinked: 'Sin vincular', partial: 'Verificación parcial', verified: 'Verificado', review: 'Revisar',
            pending: 'Pendiente', running: 'En curso', done: 'Completado', failed: 'Error de consulta', disabled: 'Consulta desactivada',
            active: 'Activo', paused: 'Pausado', closed: 'Cerrado', under_review: 'En revisión', inactive: 'Inactivo',
            unknown: 'Sin verificar', missing: 'Falta información', mismatch: 'Diferencia detectada', manual: 'Gestión manual',
            complete: 'Completo', stale: 'Observación desactualizada', matched: 'Coincide', not_loaded: 'Pendiente de consulta local',
            present: 'Registrado', incomplete: 'Incompleto', conflict: 'Conflicto de identidad', blocked: 'Bloqueado',
            ambiguous: 'Vínculo ambiguo', not_applicable: 'No corresponde', unsupported: 'Condición no compatible',
            retry: 'Reintento pendiente', manual_excluded: 'Manual / excluido', error: 'Error', known: 'Dato disponible',
            stock: 'Stock / estado', price: 'Precios', single: 'Pago único', '3x': '3 cuotas', '6x': '6 cuotas',
            fulfillment: 'Full · depósito de Mercado Libre', self_service: 'Envíos Flex',
            drop_off: 'Entrega en punto de despacho', cross_docking: 'Distribución cruzada',
            xd_drop_off: 'Punto de despacho y distribución', not_specified: 'Logística no especificada', default: 'Logística estándar',
            local_cache: 'Datos locales', local_mirror: 'Espejo local', integrator_readback: 'Confirmación del integrador',
            manual_observation: 'Consulta manual', stored_target: 'Objetivo guardado',
        }[value] || (value ? String(value).replace(/_/g, ' ') : 'Sin verificar');
    }

    meliFilterOptions() {
        return [
            ['', 'Todos los estados ML'], ['linked', 'Con vínculo ML'], ['published', 'Con publicación activa'],
            ['stock', 'Stock verificado'], ['prices', 'Precios verificados'], ['conditions', 'Condiciones completas'],
            ['review', 'Revisar en ML'], ['unlinked', 'Sin vínculo ML'],
        ].map(([value, label]) => ({ value, label }));
    }

    async changeMeliAccount(ev) {
        const value = ev.target.value || '';
        if (value && (!/^[1-9][0-9]*$/.test(String(value)) || !this.meliAccountOptions().some((account) => String(account.id) === String(value)))) return;
        if (String(value) === String(this.state.meliAccountId || '')) return;
        this.state.meliAccountId = String(value);
        this.clearMeliPoll();
        this.beginRequest('meliRefresh');
        this.state.meliRefreshBusy = false;
        this.state.meliRefreshJob = false;
        this.state.meliRefreshMessage = '';
        if (this.state.viewMode === 'detail') {
            this.state.meliDetail = { available: false, state: 'not_loaded', accounts: this.meliAccountOptions(), groups: [], jobs: [], summary: {} };
            return this.loadMeliDetail();
        }
        if (this.state.dashboardSection === 'overview') return this.loadDashboardOverview();
        return this.loadDashboard({ page: 1 }, { showSpinner: false });
    }

    async changeMeliFilter(ev) {
        const key = ev.target.value || '';
        if (!this.meliFilterOptions().some((option) => option.value === key)) return;
        this.state.meliFilter = key;
        return this.loadDashboard({ page: 1 }, { showSpinner: false });
    }

    async openMeliFilter(key) {
        this.state.taxonomyFilters = [];
        if (!this.meliFilterOptions().some((option) => option.value === key)) return;
        this.state.meliFilter = key;
        this.state.dashboardQualityFilter = '';
        return this.loadDashboard({ tab: 'all', search: '', page: 1 }, { showSpinner: false });
    }

    async openMeliProduct(row) {
        if (!row?.id || this.catalogRowBusy(row)) return;
        if (this.detailHasUnsavedChanges() && !await this.confirmDetailLeave()) return;
        this.state.origin = 'dashboard';
        this.state.activeTab = 'mercadolibre';
        const loading = this.loadDetail(row.id);
        const entry = this.beginRequest('meliEntry');
        await loading;
        if (this.isRequestCurrent(entry) && this.state.viewMode === 'detail' && this.state.activeTab === 'mercadolibre') await this.loadMeliDetail();
    }

    meliRequestCurrent(request) {
        return this.isRequestCurrent(request) && String(request.meliAccountId || '') === String(this.state.meliAccountId || '');
    }

    async loadMeliDetail() {
        if (!this.state.productId || this.state.viewMode !== 'detail') return;
        const request = { ...this.beginRequest('meliDetail'), meliAccountId: this.state.meliAccountId || '' };
        this.state.meliBusy = true;
        this.state.meliError = '';
        try {
            const data = await this.rpc('/bader_product_intelligence/meli/product_status', {
                product_tmpl_id: request.productId, meli_account_id: request.meliAccountId ? Number(request.meliAccountId) : false,
            });
            if (!this.meliRequestCurrent(request)) return;
            if (data.productId && String(data.productId) !== String(request.productId)) throw new Error('La consulta no corresponde a este producto.');
            this.state.meliDetail = { ...data, groups: data.groups || [], jobs: data.jobs || [], summary: data.summary || {} };
            this.meliDetailAccountKey = String(request.meliAccountId || '');
        } catch (error) {
            if (this.meliRequestCurrent(request)) this.state.meliError = this.errorMessage(error, 'No se pudo consultar la información local de MercadoLibre.');
        } finally {
            if (this.meliRequestCurrent(request)) this.state.meliBusy = false;
        }
    }

    clearMeliPoll() {
        clearTimeout(this.meliPollTimer);
        this.meliPollTimer = null;
    }

    async requestMeliRefresh() {
        if (!this.meliCanRefresh() || !this.state.productId) return;
        const request = { ...this.beginRequest('meliRefresh'), meliAccountId: this.state.meliAccountId || '' };
        this.clearMeliPoll();
        this.state.meliRefreshBusy = true;
        this.state.meliError = '';
        this.state.meliRefreshMessage = 'Solicitando consulta de solo lectura…';
        try {
            const result = await this.rpc('/bader_product_intelligence/meli/refresh', {
                product_tmpl_id: request.productId, meli_account_id: request.meliAccountId ? Number(request.meliAccountId) : false,
            });
            if (!this.meliRequestCurrent(request)) return;
            this.applyMeliRefreshResult(result, request);
        } catch (error) {
            if (this.meliRequestCurrent(request)) {
                this.state.meliRefreshBusy = false;
                this.state.meliError = this.errorMessage(error, 'No se pudo iniciar la consulta de MercadoLibre.');
            }
        }
    }

    applyMeliRefreshResult(result, request, attempt = 0) {
        if (!this.meliRequestCurrent(request)) return;
        this.state.meliRefreshJob = result.job || false;
        this.state.meliRefreshMessage = result.message || result.job?.message || this.meliStateLabel(result.state);
        const state = result.job?.state || result.state;
        if (state === 'disabled') this.state.meliDetail = { ...this.state.meliDetail, canRefresh: false };
        const running = ['pending', 'running'].includes(state);
        this.state.meliRefreshBusy = running;
        if (running && result.job?.id && attempt < 120) {
            this.meliPollTimer = setTimeout(() => this.pollMeliRefresh(result.job.id, request, attempt + 1), 3000);
        } else {
            this.state.meliRefreshBusy = false;
            if (running) this.state.meliRefreshMessage = 'La consulta sigue en segundo plano. Vuelve a abrir esta sección para consultar los datos locales.';
            if (['done', 'partial'].includes(state)) this.loadMeliDetail();
        }
    }

    async pollMeliRefresh(jobId, request, attempt = 1) {
        if (!this.meliRequestCurrent(request)) return;
        try {
            const result = await this.rpc('/bader_product_intelligence/meli/refresh_status', { job_id: jobId });
            if (!this.meliRequestCurrent(request)) return;
            if (result.job?.id && String(result.job.id) !== String(jobId)) throw new Error('La consulta no corresponde al trabajo solicitado.');
            this.applyMeliRefreshResult(result, request, attempt);
        } catch (error) {
            if (this.meliRequestCurrent(request)) {
                this.state.meliRefreshBusy = false;
                this.state.meliError = this.errorMessage(error, 'No se pudo consultar el progreso. El trabajo no se reinicia automáticamente.');
            }
        }
    }

    rpcWithContext(route, params = {}, settings) {
        if (!route.startsWith('/bader_product_intelligence/')) return this.rawRpc(route, params, settings);
        const context = this.snapshotDraft({ ...(this.user?.context || {}), ...(params.context || {}),
            ...(this.state.meliAccountId ? { bpi_meli_account_id: Number(this.state.meliAccountId) } : {}),
        });
        return this.rawRpc(route, { ...params, context }, settings);
    }

    detailNavGroups() {
        const groups = [
            ['Inicio', ['overview']], ['Producto', ['datos', 'variants_pack', 'categorization']],
            ['Contenido', ['content', 'images', 'seo']], ['Canales', ['mercadolibre']],
            ['Inteligencia', ['competitors', 'chat']],
        ];
        const tabs = this.visibleDetailTabs();
        return groups.map(([label, ids]) => ({ label, tabs: tabs.filter((tab) => ids.includes(tab.id)) }));
    }

    detailSectionTitle() {
        return DETAIL_TABS.find((tab) => tab.id === this.state.activeTab)?.label || 'Resumen';
    }

    detailSectionDescription() {
        return {
            overview: 'Información guardada y prioridades de esta ficha. Sin puntuaciones artificiales.',
            datos: 'Datos nativos, categoría de la tienda y precio base. El stock es de solo lectura.',
            variants_pack: 'Datos de variantes y composición de Packs; cada operación tiene su propio guardado.',
            categorization: 'Nichos y clasificación comercial; independientes de la categoría de MercadoLibre.',
            content: 'Descripción comercial, ficha técnica y preguntas frecuentes. Revisa antes de guardar.',
            images: 'Galería, referencias y vídeo. Generar una propuesta no la guarda ni publica.',
            seo: 'Metadatos SEO y GEO. Su presencia no equivale a posicionamiento.',
            mercadolibre: 'Consulta local del canal. Actualizar consulta MercadoLibre, sin publicar ni modificar anuncios.',
            competitors: 'Precios registrados y observaciones de competidores, con su fuente y fecha.',
            chat: 'Conversación por producto. Las sugerencias no modifican la ficha automáticamente.',
        }[this.state.activeTab] || '';
    }

    async selectDetailSection(value) {
        const id = typeof value === 'string' ? value : value?.target?.value;
        const resolved = id === 'analytics' ? 'competitors' : id;
        if (!this.visibleDetailTabs().some((tab) => tab.id === resolved)) return;
        this.state.activeTab = resolved;
        if (resolved === 'mercadolibre') await this.loadMeliDetail();
    }

    detailChecklistItems() {
        return this.catalogHealthItems(this.currentProduct());
    }

    detailCurrentMarginKnown() {
        const product = this.currentProduct();
        const costMin = Number(product.effectiveCostMinUsd ?? product.costUsd);
        const costMax = Number(product.effectiveCostMaxUsd ?? costMin);
        const price = this.effectivePriceRange(product);
        return [costMin, costMax, price.min, price.max].every((value) => Number.isFinite(value) && value > 0);
    }

    detailDraftSnapshot() {
        const pick = (value, keys) => Object.fromEntries(keys.map((key) => [key, value?.[key] ?? '']));
        return this.snapshotDraft({
            datos: pick(this.state.productForm, ['name', 'sku', 'slug', 'brand', 'categoryId', 'priceUsd', 'previousPriceUsd', 'costUsd', 'featured', 'isPublished', 'technicalSpecifications']),
            categorization: pick(this.state.categoryForm, ['manualMode', 'niches', 'type', 'subcategory', 'classification']),
            content: pick(this.state.contentForm, ['name', 'description', 'technicalDescription', 'tone', 'audience', 'faqs', 'templateId', 'documents']),
            seo: pick(this.state.seoForm, ['seoTitle', 'seoDescription', 'seoKeywords', 'geoTitle', 'geoDescription', 'geoKeywords', 'geoFeatures', 'seoScore', 'geoScore', 'competitivenessScore']),
            variants_pack: {
                variants: (this.state.variantDrafts || []).map((v) => pick(v, ['id', 'sku', 'barcode', 'costUsdInput', 'active', 'imageReferenceToken', 'imageUploadDataUrl'])),
                pack: {
                    ...pick(this.state.packForm, ['isPack', 'packType', 'componentPriceMode', 'modifiable']),
                    compositions: (this.state.packForm?.compositions || []).map((c) => ({ variantId: c.variantId, components: (c.components || []).map((line) => pick(line, ['lineId', 'productVariantId', 'quantityInput', 'saleDiscountInput'])) })),
                },
            },
            images: { ...pick(this.state.imageForm, ['videoUrl', 'addImageUrl', 'uploadedRefUrl', 'generatedPreviewUrl']), input: this.state.playground?.inputText || '' },
            competitors: pick(this.state.competitorForm, ['competitorName', 'competitorUrl']),
            chat: { input: this.state.chatInput || '' },
        });
    }

    detailDirtySections() {
        if (!this.detailBaseline || this.state.viewMode !== 'detail' || !this.state.detail?.product ||
            String(this.state.detail.product.id) !== String(this.state.productId)) return [];
        const now = this.detailDraftSnapshot();
        return DETAIL_TABS.filter((tab) => Object.prototype.hasOwnProperty.call(now, tab.id) &&
            JSON.stringify(now[tab.id]) !== JSON.stringify(this.detailBaseline[tab.id]))
            .map((tab) => ({ id: tab.id, label: tab.label }));
    }

    detailHasUnsavedChanges() {
        return this.detailDirtySections().length > 0;
    }

    detailBaseSaveBusy() {
        return !!(this.state.saveBusy || this.state.contentBusy || this.state.faqBusy || this.state.seoBusy || this.state.categoryBusy);
    }

    detailSaveLabel() { return this.state.saveBusy ? 'Guardando ficha…' : 'Guardar ficha'; }

    detailSaveDisabled() { return !this.state.productId || this.detailBaseSaveBusy(); }

    detailCanSaveBeforeLeave() {
        return this.detailDirtySections().every((section) => ['datos', 'categorization', 'content', 'seo'].includes(section.id));
    }

    onDetailBeforeUnload(ev) {
        if (this.detailHasUnsavedChanges() || (this.state.viewMode === 'detail' && this.detailBaseSaveBusy())) {
            ev.preventDefault();
            ev.returnValue = '';
        }
    }

    confirmDetailLeave() {
        if (this.state.viewMode !== 'detail' || !this.detailHasUnsavedChanges()) return Promise.resolve(true);
        if (this.detailLeavePromise) return this.detailLeavePromise;
        this.detailLeaveFocusElement = document.activeElement;
        this.detailLeaveFocusReady = false;
        this.state.detailLeavePrompt = {
            title: 'Cambios sin guardar',
            message: 'Puedes seguir editando o descartar los cambios. Las operaciones ya enviadas no se cancelan al salir.',
            sections: this.detailDirtySections(), canSave: this.detailCanSaveBeforeLeave(),
        };
        this.detailLeavePromise = new Promise((resolve) => { this.detailLeaveResolver = resolve; });
        return this.detailLeavePromise;
    }

    async resolveDetailLeave(choice) {
        if (!this.detailLeaveResolver || this.state.detailLeaveBusy) return;
        if (choice === 'save') {
            if (!this.detailCanSaveBeforeLeave() || this.detailBaseSaveBusy()) return;
            this.state.detailLeaveBusy = true;
            await this.saveAll();
            this.state.detailLeaveBusy = false;
            if (this.detailHasUnsavedChanges()) {
                this.state.detailLeavePrompt = { ...this.state.detailLeavePrompt, sections: this.detailDirtySections(), canSave: this.detailCanSaveBeforeLeave(), message: 'Todavía hay cambios sin guardar. Revisa el resultado antes de salir.' };
                return;
            }
        } else if (choice !== 'discard' && choice !== 'stay') return;
        if (choice === 'discard') this.discardDetailChanges();
        const resolve = this.detailLeaveResolver;
        this.detailLeaveResolver = null;
        this.detailLeavePromise = null;
        this.state.detailLeavePrompt = false;
        resolve(choice !== 'stay');
        if (choice === 'stay' && this.detailLeaveFocusElement?.isConnected) this.detailLeaveFocusElement.focus({ preventScroll: true });
    }

    syncDetailLeaveFocus() {
        const dialog = this.detailLeaveDialogRef?.el;
        if (!this.state.detailLeavePrompt || !dialog || this.detailLeaveFocusReady) return;
        this.detailLeaveFocusReady = true;
        (dialog.querySelector('button:not(:disabled)') || dialog).focus();
    }

    onDetailLeaveKeydown(ev) {
        if (ev.key === 'Escape') {
            ev.preventDefault();
            ev.stopPropagation();
            if (!this.state.detailLeaveBusy) this.resolveDetailLeave('stay');
        } else if (ev.key === 'Tab') {
            const dialog = ev.currentTarget;
            const buttons = [...dialog.querySelectorAll('button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]')];
            const first = buttons[0];
            const last = buttons[buttons.length - 1];
            if (!first) { ev.preventDefault(); dialog.focus(); }
            else if (ev.shiftKey && document.activeElement === first) { ev.preventDefault(); last.focus(); }
            else if (!ev.shiftKey && document.activeElement === last) { ev.preventDefault(); first.focus(); }
        }
    }

    async requestDetailLeave(callback) {
        if (await this.confirmDetailLeave()) return callback();
        return false;
    }

    discardDetailChanges() {
        this.state.playground = { messages: [], canvasUrl: '', inputText: '' };
        if (this.state.detail) this.applyDetailPayload(this.state.detail);
        this.state.seoPreviewPending = false;
    }

    async saveCurrentDetailSection() {
        if (this.detailBaseSaveBusy()) return false;
        const method = { datos: 'saveProductOnly', categorization: 'saveCategoryOnly', content: 'saveContentOnly', seo: 'saveSeoOnly', images: 'saveVideo' }[this.state.activeTab];
        if (!method) {
            this.notify('Esta sección utiliza sus acciones de guardado específicas.', 'info');
            return false;
        }
        return this[method]();
    }

    async saveProductOnly() {
        if (this.detailBaseSaveBusy()) return false;
        const request = this.beginRequest('save', true);
        this.state.saveBusy = true;
        try {
            const result = await this.saveProductData();
            if (!this.isRequestCurrent(request)) return false;
            this.applyDetailUpdate(result, request, { productForm: true, contentForm: ['name'] });
            this.notify('Datos y precios guardados. No se modificaron MercadoLibre ni otras secciones.');
            return true;
        } catch (error) {
            if (this.isRequestCurrent(request)) this.notify(this.errorMessage(error, 'No se pudieron guardar los datos.'), 'danger');
            return false;
        } finally {
            if (this.isRequestCurrent(request)) this.state.saveBusy = false;
        }
    }

    snapshotDraft(value) {
        if (Array.isArray(value)) return value.map((item) => this.snapshotDraft(item));
        if (value && typeof value === "object") {
            return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, this.snapshotDraft(item)]));
        }
        return value;
    }

    captureDrafts() {
        const drafts = {};
        for (const key of ["productForm", "contentForm", "seoForm", "categoryForm", "imageForm", "competitorForm", "variantDrafts", "packForm"]) {
            if (this.state[key] !== undefined) {
                drafts[key] = this.snapshotDraft(this.state[key]);
            }
        }
        return drafts;
    }

    beginRequest(scope, withDrafts = false) {
        this.requestSequences = this.requestSequences || {};
        const sequence = (this.requestSequences[scope] || 0) + 1;
        this.requestSequences[scope] = sequence;
        return {
            scope,
            sequence,
            generation: this.viewGeneration || 0,
            productId: this.state.productId,
            companies: JSON.stringify(this.user?.context?.allowed_company_ids || []),
            seoPreviewVersion: this.seoPreviewVersion || 0,
            ...(withDrafts ? { drafts: this.captureDrafts() } : {}),
        };
    }

    isRequestCurrent(request) {
        return !!request && !this.destroyed &&
            (request.companies === undefined || request.companies === JSON.stringify(this.user?.context?.allowed_company_ids || [])) &&
            request.generation === (this.viewGeneration || 0) &&
            request.sequence === (this.requestSequences || {})[request.scope] &&
            String(request.productId || "") === String(this.state.productId || "");
    }

    invalidateProductRequests() {
        this.viewGeneration = (this.viewGeneration || 0) + 1;
        this.detailLoadSequence = (this.detailLoadSequence || 0) + 1;
        this.chatRequestSequence = (this.chatRequestSequence || 0) + 1;
        this.clearDashboardReloadTimer();
        this.clearSeoJobPollTimer();
        this.clearMeliPoll();
        this.state.meliBusy = false;
        this.state.meliRefreshBusy = false;
        this.state.meliRefreshJob = false;
        this.state.meliRefreshMessage = "";
        this.state.meliDetail = { available: false, state: "not_loaded", groups: [], jobs: [], summary: {} };
        for (const key of ["saveBusy", "seoBusy", "contentBusy", "faqBusy", "imageBusy", "competitorBusy", "strategyBusy", "categoryBusy", "chatBusy", "variantBusy", "packBusy", "componentSearchBusy", "dashboardBusy", "overviewBusy", "exchangeRateBusy"]) {
            this.state[key] = false;
        }
        this.state.seoJobId = false;
        this.state.seoJobMessage = "";
        this.state.seoPreviewPending = false;
        this.state.showImageModal = false;
        this.contentTemplateSelectionVersion = (this.contentTemplateSelectionVersion || 0) + 1;
        this.state.contentTemplateContext = null;
        this.state.contentTemplateBusy = false;
        this.state.contentTemplateAdminBusy = false;
        this.state.contentTemplateError = "";
        this.state.contentGenerationWarnings = [];
        this.state.catalogReviewId = false;
        this.state.catalogBusyRows = {};
        this.contentDescriptionSelection = null;
        this.technicalDescriptionSelection = null;
        this.state.playground = { messages: [], canvasUrl: "", inputText: "" };
    }

    mergeSavedDraft(current, submitted, saved) {
        if (Array.isArray(current) && Array.isArray(submitted) && Array.isArray(saved) &&
            saved.length && saved.every(row => row && Number.isInteger(row.variantId) && row.values && Number.isInteger(row.revision))) {
            return current.map(row => {
                const before = submitted.find(item => item.variantId === row.variantId);
                const after = saved.find(item => item.variantId === row.variantId);
                if (!before || !after) return row;
                return { ...row, revision: after.revision, values: this.mergeSavedDraft(row.values, before.values, after.values) };
            });
        }
        if (current && submitted && saved && Number.isInteger(saved.revision) && Array.isArray(saved.termIds)) {
            return { ...saved, termIds: this.mergeSavedDraft(current.termIds, submitted.termIds, saved.termIds), ...(saved.excludedTermIds ? { excludedTermIds: this.mergeSavedDraft(current.excludedTermIds || [], submitted.excludedTermIds || [], saved.excludedTermIds) } : {}) };
        }
        if (current && submitted && saved && Number.isInteger(saved.revision) &&
            Array.isArray(saved.buttons) && saved.buttons.length === 3 && Array.isArray(current.buttons)) {
            const panel = { ...saved };
            for (const key of ['title', 'intro']) panel[key] = this.mergeSavedDraft(current[key], submitted[key], saved[key]);
            if (current.cover !== submitted.cover) panel.cover = current.cover;
            panel.buttons = saved.buttons.map((row, index) => {
                const now = current.buttons[index], before = submitted.buttons[index];
                const result = this.mergeSavedDraft(now, before, row);
                if (now?.upload === before?.upload && result && 'upload' in result) delete result.upload;
                return result;
            });
            return panel;
        }
        if (JSON.stringify(current) === JSON.stringify(submitted)) {
            return saved;
        }
        if (current && submitted && saved && !Array.isArray(current) && typeof current === "object") {
            const merged = { ...current };
            for (const key of Object.keys(saved)) {
                merged[key] = this.mergeSavedDraft(current[key], submitted[key], saved[key]);
            }
            return merged;
        }
        // Never discard edits made after the request (including reordered FAQs/Pack lines).
        return current;
    }

    applyDetailUpdate(data, request, updates = {}) {
        if (!this.isRequestCurrent(request) || !data.product || String(data.product.id) !== String(request.productId)) {
            return;
        }
        const retained = {};
        const retainedTemplateContext = this.state.contentTemplateContext;
        const keys = ["productForm", "contentForm", "seoForm", "categoryForm", "imageForm", "competitorForm", "variantDrafts", "packForm", "componentSearch", "selectedVariantId", "chatMessages", "chatSessionKey", "chatInput", "chatBusy", "variantBusy", "packBusy", "componentSearchBusy", "taxonomyAiTermIds", "taxonomyTermDetail", "taxonomyDismissedPending"];
        for (const key of keys) retained[key] = this.state[key];
        this.applyDetailPayload(data);
        for (const key of keys) {
            const saved = this.state[key];
            this.state[key] = retained[key];
            if (!updates[key]) continue;
            const submitted = (request.drafts || {})[key];
            if (updates[key] === true) {
                this.state[key] = this.mergeSavedDraft(retained[key], submitted, saved);
            } else if (key === "variantDrafts") {
                this.state.variantDrafts = (retained.variantDrafts || []).map((variant) => {
                    const target = updates.variantDrafts.id || updates.variantDrafts;
                    if (String(variant.id) !== String(target)) return variant;
                    const original = (submitted || []).find((item) => item.id === variant.id);
                    const updated = (saved || []).find((item) => item.id === variant.id);
                    if (!updated) return variant;
                    if (updates.variantDrafts.fields) {
                        const fresh = { ...variant };
                        for (const field of updates.variantDrafts.fields) {
                            fresh[field] = this.mergeSavedDraft(variant[field], original?.[field], updated[field]);
                        }
                        return fresh;
                    }
                    return this.mergeSavedDraft(variant, original, updated);
                });
            } else {
                const updated = { ...retained[key] };
                for (const field of updates[key]) {
                    updated[field] = this.mergeSavedDraft(retained[key]?.[field], submitted?.[field], saved[field]);
                }
                this.state[key] = updated;
            }
        }
        // A save may finish after the operator has selected a different model.
        // Keep that selection's metadata together with its still-pending draft.
        if (data.contentTemplates && this.contentTemplateSelectionId() !== (data.contentTemplates.selectionId || false)) {
            this.state.contentTemplateContext = retainedTemplateContext;
            // The pending editorial model stays selected, but its saved product
            // context may have changed when another section was saved. Refresh
            // that model's metadata before allowing another paid generation.
            const semanticChanged = data.contentTemplates.semanticRevision !== undefined &&
                retainedTemplateContext?.semanticRevision !== data.contentTemplates.semanticRevision;
            if (!this.contentTemplateContextMatchesSelection() || semanticChanged) void this.refreshContentTemplateContext();
        }
    }

    async refreshDetail(request, updates = {}) {
        if (!this.isRequestCurrent(request)) return;
        const refresh = this.beginRequest("detailRefresh");
        const data = await this.rpc("/bader_product_intelligence/data", { product_tmpl_id: request.productId });
        if (this.isRequestCurrent(refresh)) this.applyDetailUpdate(data, request, updates);
    }

    clearDashboardReloadTimer() {
        if (this.dashboardReloadTimer) {
            clearTimeout(this.dashboardReloadTimer);
            this.dashboardReloadTimer = null;
        }
    }

    scheduleDashboardReload() {
        this.clearDashboardReloadTimer();
        const request = this.beginRequest("dashboard");
        this.dashboardReloadTimer = setTimeout(() => {
            if (this.isRequestCurrent(request) && this.state.dashboardSection !== "overview") {
                this.loadDashboard({ page: 1 }, { showSpinner: false });
            }
        }, 300);
    }

    clearSeoJobPollTimer() {
        if (this.seoJobPollTimer) {
            clearTimeout(this.seoJobPollTimer);
            this.seoJobPollTimer = null;
        }
    }

    scheduleSeoJobPoll(jobId, delay = 5000, request = this.beginRequest("seoJob")) {
        this.clearSeoJobPollTimer();
        this.seoJobPollTimer = setTimeout(() => {
            if (this.isRequestCurrent(request)) this.pollSeoJob(jobId, request);
        }, delay);
    }

    applySeoJobPayload(job, request = null) {
        if ((request && !this.isRequestCurrent(request)) || String(job?.productId) !== String(this.state.productId)) return;
        const seoData = job?.resultPayload?.seoData;
        if (!seoData) return;
        const proposal = { ...this.state.seoForm };
        for (const key of ["seoTitle", "seoDescription", "geoTitle", "geoDescription", "seoScore", "geoScore", "competitivenessScore"]) {
            if (seoData[key] !== undefined) proposal[key] = seoData[key];
        }
        for (const key of ["seoKeywords", "geoKeywords", "geoFeatures"]) {
            if (Array.isArray(seoData[key])) proposal[key] = seoData[key].join(", ");
        }
        this.state.seoForm = request?.drafts?.seoForm
            ? this.mergeSavedDraft(this.state.seoForm, request.drafts.seoForm, proposal)
            : proposal;
        this.state.seoPreviewPending = true;
        this.seoPreviewVersion = (this.seoPreviewVersion || 0) + 1;
        // SEO is a metadata preview: never replace product/content/FAQ/technical drafts.
    }

    async pollSeoJob(jobId, request = this.beginRequest("seoJob", true)) {
        if (!jobId || !request.productId || !this.isRequestCurrent(request)) return;
        try {
            const result = await this.rpc("/bader_product_intelligence/ai_job/status", { job_id: jobId });
            if (!this.isRequestCurrent(request)) return;
            const job = result.job || {};
            if (String(job.productId) !== String(request.productId) || String(job.id) !== String(jobId)) return;
            this.state.seoJobMessage = job.message || "Nancy AI esta trabajando...";
            if (job.state === "done" || job.state === "failed") {
                this.clearSeoJobPollTimer();
                this.state.seoBusy = false;
                this.state.seoJobId = false;
                this.state.seoJobMessage = "";
                if (job.state === "done") {
                    // New semantic jobs must still match the saved, approved map.
                    // Do not trust this tab's potentially stale detail payload.
                    if (job.resultPayload?.semanticRevision) {
                        const context = await this.rpc('/bader_product_intelligence/content_template_context', {
                            product_tmpl_id: request.productId, template_id: this.contentTemplateSelectionId(),
                        });
                        if (!this.isRequestCurrent(request)) return;
                        if (context?.semanticRevision !== job.resultPayload.semanticRevision) {
                            this.notify('La clasificación guardada cambió. No se aplicó la propuesta SEO; tus borradores se conservan.', 'warning');
                            return;
                        }
                    }
                    this.applySeoJobPayload(job, request);
                    this.notify("Propuesta SEO lista. Revisa los metadatos y pulsa Guardar para aplicarlos.", "info");
                } else {
                    this.notify(job.errorMessage || "No se pudo analizar el SEO.", "danger");
                }
                return;
            }
            this.scheduleSeoJobPoll(jobId, 5000, request);
        } catch (error) {
            if (!this.isRequestCurrent(request)) return;
            this.clearSeoJobPollTimer();
            this.state.seoBusy = false;
            this.state.seoJobId = false;
            this.state.seoJobMessage = "";
            this.notify(this.errorMessage(error, "No se pudo consultar el trabajo de SEO."), "danger");
        }
    }

    notify(message, type = "success") {
        this.notification.add(message, { type });
    }

    errorMessage(error, fallback) {
        const defaultMessage = typeof fallback === "string" && fallback.trim()
            ? fallback : "No se pudo completar la operación. Inténtalo de nuevo.";
        // Odoo's transport message is normally just "Odoo Server Error". Only
        // explicit user-facing exception classes may replace our safe fallback;
        // never surface arbitrary Python/network errors or their debug payload.
        const data = error?.data;
        if (!SAFE_ODOO_ERROR_NAMES.has(data?.name) || typeof data.message !== "string") return defaultMessage;
        const message = data.message.trim();
        if (!message || message.length > 1200 ||
            /[<>]|&(?:lt|gt|#0*60|#0*62|#x0*3c|#x0*3e);|\b(?:Traceback|psycopg2|SQLSTATE)\b|File\s+["'][^"']+["'],\s+line\s+\d/i.test(message) ||
            /\b(?:sk-(?:proj-)?|fc-)[a-z0-9_-]{8,}|\bBearer\s+\S+|\b(?:authorization|api[_ -]?key|token|password|secret)\s*[:=]\s*\S|https?:\/\/\S*[?@]/i.test(message)) return defaultMessage;
        return message.replace(/[\u0000-\u001f\u007f\u202a-\u202e\u2066-\u2069]/g, " ").replace(/\s+/g, " ").trim() || defaultMessage;
    }

    dashboardDefaultOverview() {
        return {
            generatedAt: "", categoryId: false, categories: [], total: 0,
            kpis: [], coverage: [], priorities: [],
            publication: { published: 0, unpublished: 0, total: 0, publishedPercent: 0 },
            jobs: { pending: 0, running: 0, done: 0, failed: 0, recent: [] },
        };
    }

    activateDashboardSection(section) {
        if (this.state.viewMode !== "dashboard" || this.state.dashboardSection !== section) {
            // Section switches are navigation too: A → B → A must invalidate old RPCs.
            this.invalidateProductRequests();
        }
        this.clearDashboardReloadTimer();
        this.state.viewMode = "dashboard";
        this.state.productId = null;
        this.state.dashboardSection = section;
        this.state.loading = false;
        this.state.error = "";
    }

    dashboardRequestContext() {
        // Plain JSON RPC does not inject the user/selected-company context.
        // Capture a snapshot so subsequent browser context changes cannot alter
        // an already submitted dashboard request or its category drill-down.
        return this.user ? { context: this.snapshotDraft(this.user.context || {}) } : {};
    }

    async loadDashboardOverview() {
        this.activateDashboardSection("overview");
        const request = this.beginRequest("dashboardOverview");
        const categoryId = this.state.dashboardCategoryId || "";
        this.state.overviewBusy = true;
        this.state.overviewError = "";
        try {
            const data = await this.rpc("/bader_product_intelligence/dashboard_overview", {
                category_id: categoryId ? Number(categoryId) : false,
                ...(this.state.meliAccountId ? { meli_account_id: Number(this.state.meliAccountId) } : {}),
                ...this.dashboardRequestContext(),
            });
            if (!this.isRequestCurrent(request)) return;
            const defaults = this.dashboardDefaultOverview();
            this.state.dashboardOverview = {
                ...defaults, ...data,
                publication: { ...defaults.publication, ...(data.publication || {}) },
                jobs: { ...defaults.jobs, ...(data.jobs || {}) },
            };
            this.state.exchangeRate = data.exchangeRate || this.state.exchangeRate || 1650;
            this.state.exchangeRateInput = String(this.state.exchangeRate);
        } catch (error) {
            if (this.isRequestCurrent(request)) {
                this.state.overviewError = this.errorMessage(error, "No se pudo cargar la visión general. Inténtalo de nuevo.");
            }
        } finally {
            if (this.isRequestCurrent(request)) this.state.overviewBusy = false;
        }
    }

    async selectDashboardSection(section) {
        if (section !== "overview" && section !== "catalog") return;
        if (section === "overview") return this.loadDashboardOverview();
        return this.loadDashboard({}, { showSpinner: false });
    }

    async refreshDashboardHome() {
        return this.selectDashboardSection(this.state.dashboardSection || "overview");
    }

    async changeDashboardCategory(ev) {
        const categoryId = ev.target.value || "";
        if (String(categoryId) === String(this.state.dashboardCategoryId || "")) return;
        this.invalidateProductRequests();
        this.state.dashboardCategoryId = String(categoryId);
        this.state.dashboardPager = { ...this.dashboardDefaultPager(), ...this.state.dashboardPager, page: 1 };
        // Keep category choices while hiding metrics from the previous category.
        this.state.dashboardOverview = {
            ...this.dashboardDefaultOverview(), categories: this.dashboardCategories(),
        };
        return this.refreshDashboardHome();
    }

    async openDashboardMetric(filter) {
        this.state.meliFilter = "";
        this.state.taxonomyFilters = [];
        this.state.dashboardQualityFilter = filter === "all" ? "" : filter || "";
        return this.loadDashboard({ tab: "all", search: "", page: 1 }, { showSpinner: false });
    }

    async clearDashboardQualityFilter() {
        this.state.dashboardQualityFilter = "";
        return this.loadDashboard({ page: 1 }, { showSpinner: false });
    }

    dashboardCategories() {
        return this.state.dashboardOverview?.categories || [];
    }

    dashboardQualityLabel() {
        const labels = {
            needs_attention: "Ficha incompleta", complete: "Ficha completa",
            published: "Publicados", unpublished: "Sin publicar", content: "Contenido completo",
            image: "Con imagen", seo: "Metadatos SEO completos", geo: "Metadatos GEO completos",
            faq: "Con FAQs", competitor: "Con competidores registrados", category: "Con categoría",
            published_missing_image: "Publicados sin imagen", published_missing_content: "Publicados sin descripción comercial",
            missing_seo: "SEO incompleto", missing_geo: "GEO incompleto", missing_category: "Sin categoría",
        };
        return labels[this.state.dashboardQualityFilter] || "";
    }

    dashboardMetricIcon(key) {
        const icon = {
            all: "fa-cubes", published: "fa-globe", content: "fa-file-text-o", image: "fa-picture-o",
            seo: "fa-search", geo: "fa-crosshairs", faq: "fa-comments-o", competitor: "fa-line-chart",
        }[key] || "fa-bar-chart";
        return `fa ${icon}`;
    }

    dashboardPercent(value) {
        return Math.max(0, Math.min(100, Number(value) || 0));
    }

    dashboardPublicationStyle() {
        const percent = this.dashboardPercent(this.state.dashboardOverview?.publication?.publishedPercent);
        return `--publication-percent: ${percent}%;`;
    }

    dashboardDateLabel(value) {
        if (!value) return "—";
        // Odoo datetime strings are UTC; format in the browser's local timezone.
        const normalized = String(value).replace(" ", "T");
        const date = new Date(/(?:Z|[+-]\d{2}:?\d{2})$/.test(normalized) ? normalized : `${normalized}Z`);
        if (Number.isNaN(date.getTime())) return "—";
        return date.toLocaleString("es-AR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
    }

    dashboardUpdatedLabel() {
        const value = this.state.dashboardSection === "catalog"
            ? this.state.dashboardCatalogUpdatedAt : this.state.dashboardOverview?.generatedAt;
        return this.dashboardDateLabel(value);
    }

    dashboardJobDate(job) {
        return this.dashboardDateLabel(job.finishedAt || job.createdAt);
    }

    dashboardJobLabel(state) {
        return { pending: "Pendiente", running: "En ejecución", done: "Propuesta lista", failed: "Fallido" }[state] || "Sin estado";
    }

    dashboardDefaultStats() {
        return {
            total: 0,
            published: 0,
            featured: 0,
            pending: 0,
        };
    }

    dashboardDefaultTabCounts() {
        return {
            all: 0,
            new: 0,
            discontinued: 0,
        };
    }

    dashboardDefaultPager(limit = DASHBOARD_PAGE_SIZE) {
        return {
            page: 1,
            pageCount: 1,
            total: 0,
            limit,
            hasNext: false,
            hasPrevious: false,
        };
    }

    resolveDashboardParams(overrides = {}) {
        const currentPager = this.state.dashboardPager || this.dashboardDefaultPager();
        const page = Math.max(1, Number(overrides.page !== undefined ? overrides.page : currentPager.page || 1) || 1);
        const limit = Math.max(
            1,
            Number(overrides.limit !== undefined ? overrides.limit : currentPager.limit || DASHBOARD_PAGE_SIZE) || DASHBOARD_PAGE_SIZE
        );
        return {
            tab: overrides.tab !== undefined ? overrides.tab : this.state.dashboardTab,
            search: overrides.search !== undefined ? overrides.search : this.state.searchTerm,
            page,
            limit,
            category_id: this.state.dashboardCategoryId ? Number(this.state.dashboardCategoryId) : false,
            quality_filter: this.state.dashboardQualityFilter || false,
            sort_key: this.state.dashboardSortKey || "catalog",
            ...(this.state.meliAccountId ? { meli_account_id: Number(this.state.meliAccountId) } : {}),
            ...(this.state.meliFilter ? { meli_filter: this.state.meliFilter } : {}),
            ...(this.state.taxonomyFilters?.length ? { taxonomy_term_ids: [...this.state.taxonomyFilters] } : {}),
            ...this.dashboardRequestContext(),
        };
    }

    applyDashboardPayload(data, params) {
        this.state.taxonomyFacets = data.taxonomyTerms || [];
        this.state.dashboardRows = data.products || [];
        this.state.meliCatalogContext = data.meli || {};
        this.state.dashboardStats = data.stats || this.dashboardDefaultStats();
        this.state.dashboardTabCounts = data.tabCounts || this.dashboardDefaultTabCounts();
        this.state.dashboardPager = {
            ...this.dashboardDefaultPager(params.limit),
            ...(data.pager || {}),
        };
        this.state.exchangeRate = data.exchangeRate || this.state.exchangeRate || 1650;
        this.state.exchangeRateInput = String(this.state.exchangeRate || 1650);
        this.state.dashboardTab = params.tab;
        this.state.searchTerm = params.search || "";
        this.state.dashboardCatalogUpdatedAt = data.generatedAt || new Date().toISOString();
    }

    async loadDashboard(overrides = {}, options = {}) {
        const params = this.resolveDashboardParams(overrides);
        this.closeCatalogReview();
        this.activateDashboardSection("catalog");
        const request = this.beginRequest("dashboard");
        this.state.dashboardTab = params.tab;
        this.state.searchTerm = params.search || "";
        const showSpinner = options.showSpinner !== false;
        this.state.loading = showSpinner;
        this.state.dashboardBusy = !showSpinner;
        this.state.error = "";
        try {
            const data = await this.rpc("/bader_product_intelligence/dashboard", params);
            if (this.isRequestCurrent(request)) this.applyDashboardPayload(data, params);
        } catch (error) {
            if (this.isRequestCurrent(request)) this.state.error = this.errorMessage(error, "No se pudo cargar Producto Intelligence.");
        } finally {
            if (this.isRequestCurrent(request)) {
                this.state.loading = false;
                this.state.dashboardBusy = false;
            }
        }
    }

    applyDetailPayload(data) {
        const product = data.product || {};
        const seoData = data.seoData || {};
        const variants = data.variants || [];
        const pack = data.pack || this.emptyPackForm();

        if (product.meliSummary && data.meli) {
            const accountMatches = !this.state.meliAccountId || String(data.meli.accountId) === String(this.state.meliAccountId);
            if (accountMatches) {
                const sameScope = String(this.state.meliDetail?.productId) === String(product.id) &&
                    String(this.meliDetailAccountKey || '') === String(this.state.meliAccountId || '');
                this.state.meliDetail = { ...data.meli, productId: product.id, summary: this.snapshotDraft(product.meliSummary),
                    groups: sameScope ? this.state.meliDetail.groups || [] : [],
                    jobs: sameScope ? this.state.meliDetail.jobs || [] : [],
                };
                this.meliDetailAccountKey = String(this.state.meliAccountId || '');
            }
        }

        this.state.detail = data;
        this.state.contentTemplateContext = data.contentTemplates || null;
        this.state.contentTemplateError = "";
        this.state.productForm = {
            name: product.name || "",
            sku: product.sku || "",
            slug: product.slug || "",
            brand: product.brand || "Bader",
            categoryId: product.categoryId ? String(product.categoryId) : "",
            priceUsd: this.toInput(product.priceUsd),
            previousPriceUsd: product.previousPriceUsd ? this.toInput(product.previousPriceUsd) : "",
            costUsd: product.costUsd ? this.toInput(product.costUsd) : "",
            technicalSpecifications: (data.technicalSpecifications || []).map(row => ({ variantId: row.variantId, revision: row.revision, values: { ...row.values } })),
            qtyAvailable: this.toInput(product.qtyAvailable),
            featured: !!product.featured,
            isPublished: !!product.isPublished,
        };
        this.state.contentForm = {
            documents: data.documents ? this.snapshotDraft(data.documents) : undefined,
            templateId: data.contentTemplates?.selectionId || false,
            tone: seoData.aiTone || "profesional",
            audience: seoData.aiTargetAudience || "clinicas",
            name: product.name || "",
            description: seoData.aiGeneratedDescriptionHtml || seoData.aiGeneratedDescription || product.description || "",
            technicalDescription: seoData.aiTechnicalDescriptionHtml || seoData.aiTechnicalDescription || product.bpiTechnicalDescriptionHtml || product.bpiTechnicalDescription || "",
            faqs: (seoData.geoFaq || []).map((faq) => ({
                question: faq.question || "",
                answer: faq.answer || "",
            })),
        };
        this.state.seoForm = {
            seoTitle: seoData.seoTitle || product.name || "",
            seoDescription: seoData.seoDescription || "",
            slug: product.slug || "",
            seoKeywords: (seoData.seoKeywords || []).join(", "),
            geoTitle: seoData.geoTitle || "",
            geoKeywords: (seoData.geoKeywords || []).join(", "),
            geoDescription: seoData.geoDescription || "",
            geoFeatures: (seoData.geoFeatures || []).join(", "),
            seoScore: seoData.seoScore || 0,
            geoScore: seoData.geoScore || 0,
            competitivenessScore: seoData.competitivenessScore || 0,
        };
        this.state.classificationJob = data.classification?.job || null;
        this.state.taxonomyPicker = ""; this.state.taxonomyNotice = ""; this.state.taxonomyAnalyzing = false;
        this.state.taxonomyAiTermIds = []; this.state.taxonomyTermDetail = null; this.state.taxonomyDismissedPending = [];
        this.taxonomyFocusSelector = null;
        this.state.categoryForm = {
            classification: data.classification ? { revision: data.classification.revision, vocabularyRevision: data.classification.vocabularyRevision, termIds: [...data.classification.termIds], excludedTermIds: [...(data.classification.excludedTermIds || [])] } : undefined,
            manualMode: !!product.intelligentCategoryManual,
            niches: product.intelligentNiches || [],
            type: this.normalizeChoiceValue(product.intelligentType, TYPE_OPTIONS, TYPE_ALIASES),
            subcategory: this.normalizeChoiceValue(product.intelligentSubcategory, SUBCATEGORY_OPTIONS, SUBCATEGORY_ALIASES),
        };
        const defaultImage = product.mainImageUrl || (data.images && data.images.length ? data.images[0].imageUrl : "");
        this.state.imageForm = {
            prompt: "",
            style: "professional",
            selectedReferences: (product.referenceImages || []).length ? [product.referenceImages[0].token] : [],
            generatedPreviewUrl: "",
            selectedGalleryUrl: defaultImage || "",
            addImageUrl: "",
            videoUrl: product.videoUrl || "",
        };
        this.state.competitorForm = {
            competitorName: "",
            competitorUrl: "",
            discoveredCompetitors: [],
            discoveryQuery: "",
        };
        this.state.variantDrafts = variants.map((variant) => ({
            ...variant,
            sku: variant.sku || "",
            barcode: variant.barcode || "",
            costUsdInput: this.toInput(variant.costUsd),
            imageReferenceToken: "",
            imageUploadDataUrl: "",
            imageUploadName: "",
        }));
        const selectedVariantExists = this.state.variantDrafts.some(
            (variant) => String(variant.id) === String(this.state.selectedVariantId || "")
        );
        if (!selectedVariantExists) {
            const preferredVariant = this.state.variantDrafts.find((variant) => variant.active) || this.state.variantDrafts[0];
            this.state.selectedVariantId = preferredVariant ? preferredVariant.id : null;
        }
        this.state.packForm = {
            ...this.emptyPackForm(),
            ...pack,
            compositions: (pack.compositions || []).map((composition) => ({
                ...composition,
                components: (composition.components || []).map((component) => ({
                    ...component,
                    quantityInput: this.toInput(component.quantity),
                    saleDiscountInput: this.toInput(component.saleDiscount),
                })),
            })),
        };
        this.state.componentSearch = { query: "", results: [] };
        this.state.variantBusy = false;
        this.state.packBusy = false;
        this.state.componentSearchBusy = false;
        this.state.chatMessages = (data.chatHistory || []).slice(-100).map((message) => ({
            role: message.role,
            content: message.content || "",
        }));
        this.state.chatSessionKey = data.chatSessionId || "";
        this.state.chatInput = "";
        this.state.chatBusy = false;
        this.state.exchangeRate = data.exchangeRate || this.state.exchangeRate || 1650;
        this.state.exchangeRateInput = String(this.state.exchangeRate || 1650);
        this.detailBaseline = this.detailDraftSnapshot();
        this.detailBaseline.images.input = '';
    }

    async loadDetail(productId = null) {
        const currentId = productId || this.state.productId;
        if (!currentId) {
            await this.refreshDashboardHome();
            return;
        }
        const differentProduct = String(currentId) !== String(this.state.productId || "");
        this.invalidateProductRequests();
        this.state.productId = currentId;
        this.state.viewMode = "detail";
        const request = this.beginRequest("detail");
        if (differentProduct) {
            this.state.detail = null;
            this.state.chatMessages = [];
            this.state.chatSessionKey = "";
            this.state.chatInput = "";
            this.state.selectedVariantId = null;
            this.state.variantDrafts = [];
            this.state.packForm = this.emptyPackForm();
            this.state.componentSearch = { query: "", results: [] };
        }
        this.state.loading = true;
        this.state.error = "";
        try {
            const data = await this.rpc("/bader_product_intelligence/data", { product_tmpl_id: currentId });
            if (!this.isRequestCurrent(request)) return;
            this.applyDetailPayload(data);
        } catch (error) {
            if (this.isRequestCurrent(request)) this.state.error = this.errorMessage(error, "No se pudo cargar el detalle del producto.");
        } finally {
            if (this.isRequestCurrent(request)) this.state.loading = false;
        }
    }

    currentProduct() {
        return (this.state.detail && this.state.detail.product) || {};
    }

    currentSeoData() {
        const data = (this.state.detail && this.state.detail.seoData) || {};
        if (!this.state.seoPreviewPending) return data;
        return { ...data, seoScore: this.state.seoForm.seoScore, geoScore: this.state.seoForm.geoScore, competitivenessScore: this.state.seoForm.competitivenessScore };
    }

    currentImages() {
        return (this.state.detail && this.state.detail.images) || [];
    }

    referenceableImages() {
        return this.currentImages().filter((image) => image.canReference && image.referenceToken);
    }

    currentCompetitors() {
        return (this.state.detail && this.state.detail.competitors) || [];
    }

    competitorEvidenceLabel(value) {
        return {
            firecrawl: "Firecrawl", direct_http: "Lectura directa", jsonld_offer: "JSON-LD / oferta",
            product_meta: "Metadatos de producto", visible_price: "Texto de precio",
            known: "Precio registrado", not_found: "No encontrado", ambiguous: "Precio ambiguo", unknown: "Sin verificar",
            pending: "Pendiente de consulta", done: "Consulta válida", success: "Consulta válida", failed: "Error de consulta",
        }[value] || "Sin fuente registrada";
    }

    competitorObservedPriceLabel(competitor) {
        const price = Number(competitor.competitorOfferPrice || competitor.competitorPrice);
        return (!competitor.priceStatus || competitor.priceStatus === "known") && Number.isFinite(price) && price > 0
            ? this.formatCompetitorPrice(price, competitor.competitorCurrency) : "No disponible";
    }

    competitorSeoEvidenceLabel(competitor) {
        const score = Number(competitor.seoScore);
        const observed = competitor.lastSuccessfulScrapedAt || (competitor.scrapeStatus === "done" && competitor.lastScrapedAt);
        return observed && Number.isFinite(score) ? `${Math.max(0, Math.min(100, score))}/100` : "Sin evaluar";
    }

    competitorKeywordsLabel(competitor) {
        return competitor.metaKeywordsSource === "page" || competitor.metaKeywordsSource === "not_found"
            ? "Meta keywords de la página" : "Keywords guardadas (origen no confirmado)";
    }

    competitorCollectionError(competitor) {
        return this.errorMessage({ data: { name: "odoo.exceptions.UserError", message: competitor?.scrapeError } },
            "No se pudo consultar el competidor. Se conservan los últimos datos válidos; revisa la URL y la configuración.");
    }

    notifyCompetitorCollection(competitor, successMessage) {
        if (competitor?.scrapeStatus === "failed") this.notify(this.competitorCollectionError(competitor), "warning");
        else this.notify(successMessage);
    }

    competitorExternalImageUrl(value) {
        try {
            const url = new URL(value);
            const host = url.hostname.toLowerCase();
            if (!["http:", "https:"].includes(url.protocol) || url.username || url.password ||
                !host.includes(".") || /(?:^|\.)(?:localhost|local|internal|test|invalid)$/.test(host) ||
                host.includes(":") || /^[\d.]+$/.test(host) || url.port) return false;
            return url.href;
        } catch { return false; }
    }

    currentCategories() {
        return (this.state.detail && this.state.detail.availableCategories) || [];
    }

    currentCategoryIntelligence() {
        return (this.state.detail && this.state.detail.categoryIntelligence) || null;
    }

    currentStrategy() {
        return (this.state.detail && this.state.detail.competitiveStrategy) || {};
    }

    currentVariants() {
        return this.state.variantDrafts || [];
    }

    currentPack() {
        return this.state.packForm || this.emptyPackForm();
    }

    hasVariantPackTab() {
        const product = this.currentProduct();
        return !!(product.isPack || Number(product.variantCount || 0) > 1);
    }

    visibleDetailTabs() {
        return this.detailTabs.filter((tab) => tab.id !== "variants_pack" || this.hasVariantPackTab());
    }

    selectedVariant() {
        return this.currentVariants().find(
            (variant) => String(variant.id) === String(this.state.selectedVariantId || "")
        ) || this.currentVariants()[0] || null;
    }

    selectVariant(variantId) {
        this.beginRequest("componentSearch");
        this.state.componentSearchBusy = false;
        this.state.selectedVariantId = variantId;
        this.state.componentSearch = { query: "", results: [] };
    }

    currentPackComposition() {
        const compositions = this.currentPack().compositions || [];
        return compositions.find(
            (composition) => String(composition.variantId) === String(this.state.selectedVariantId || "")
        ) || compositions[0] || null;
    }

    detailHeaderSubtitle() {
        const product = this.currentProduct();
        const sku = product.sku || "Sin SKU";
        const categoryPath = product.categoryPath || product.category || "Sin categoria";
        return `${sku} - ${categoryPath}`;
    }

    seoTitleCounterLabel() {
        return `${(this.state.seoForm.seoTitle || "").length}/60 caracteres`;
    }

    seoDescriptionCounterLabel() {
        return `${(this.state.seoForm.seoDescription || "").length}/160 caracteres`;
    }

    selectedGalleryImageUrl() {
        if (this.state.imageForm.selectedGalleryUrl) {
            return this.state.imageForm.selectedGalleryUrl;
        }
        const images = this.currentImages();
        return images.length ? images[0].imageUrl : "";
    }

    dismissGeneratedPreview() {
        this.state.imageForm.generatedPreviewUrl = "";
    }

    acknowledgeImagePreview(url) {
        if (url && this.state.imageForm.generatedPreviewUrl === url) this.state.imageForm.generatedPreviewUrl = '';
    }

    toInput(value) {
        if (value === undefined || value === null || value === false) {
            return "";
        }
        return String(value);
    }

    normalizeChoiceKey(value) {
        return this.toInput(value)
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "_")
            .replace(/^_+|_+$/g, "");
    }

    normalizeChoiceValue(value, options, aliases = {}) {
        const key = this.normalizeChoiceKey(value);
        if (!key) {
            return "";
        }
        const allowed = new Set(options.map((option) => option.value));
        if (allowed.has(key)) {
            return key;
        }
        return aliases[key] || "";
    }

    templateString(value) {
        return this.toInput(value);
    }

    escapeHtml(value) {
        const text = this.toInput(value);
        return text.replace(/[&<>"']/g, (char) => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;",
        }[char]));
    }

    looksLikeHtml(value) {
        return /<\/?[a-z][\s\S]*>/i.test(this.toInput(value));
    }

    plainTextToHtml(value) {
        const text = this.toInput(value).replace(/\r\n/g, "\n").replace(/\r/g, "\n").trim();
        if (!text) {
            return "";
        }
        return text
            .split(/\n{2,}/)
            .map((block) => {
                const lines = block.split("\n").map((line) => line.trim()).filter(Boolean);
                return lines.length ? `<p>${lines.map((line) => this.escapeHtml(line)).join("<br/>")}</p>` : "";
            })
            .filter(Boolean)
            .join("");
    }

    normalizeDescriptionFontFamily(value) {
        const firstFamily = this.toInput(value)
            .split(",")[0]
            .trim()
            .replace(/^['"]|['"]$/g, "");
        const allowedFamily = DESCRIPTION_FONT_FAMILIES.find(
            (item) => item.value.toLowerCase() === firstFamily.toLowerCase()
        );
        return allowedFamily ? allowedFamily.value : "";
    }

    normalizeDescriptionColor(value) {
        const color = this.toInput(value).trim().toLowerCase();
        if (/^#[0-9a-f]{3}([0-9a-f]{3})?([0-9a-f]{2})?$/.test(color)) {
            return color;
        }
        if (/^rgba?\(\s*\d{1,3}(?:\.\d+)?\s*,\s*\d{1,3}(?:\.\d+)?\s*,\s*\d{1,3}(?:\.\d+)?(?:\s*,\s*(?:0|1|0?\.\d+))?\s*\)$/.test(color)) {
            return color;
        }
        return "";
    }

    normalizeLegacyDescriptionFormatting(root) {
        if (!root || typeof document === "undefined") {
            return;
        }
        Array.from(root.querySelectorAll("font")).forEach((fontNode) => {
            const span = document.createElement("span");
            const legacyStyle = this.sanitizedDescriptionStyle(fontNode);
            const family = this.normalizeDescriptionFontFamily(fontNode.getAttribute("face"));
            const inlineSize = this.toInput(fontNode.style.fontSize).trim().toLowerCase();
            const size = DESCRIPTION_ALLOWED_FONT_SIZES.has(inlineSize)
                ? inlineSize
                : (DESCRIPTION_LEGACY_FONT_SIZES[fontNode.getAttribute("size")] || "");
            const color = this.normalizeDescriptionColor(fontNode.getAttribute("color"));
            if (legacyStyle) {
                span.setAttribute("style", legacyStyle);
            }
            if (family) {
                span.style.fontFamily = family;
            }
            if (size) {
                span.style.fontSize = size;
            }
            if (color) {
                span.style.color = color;
            }
            while (fontNode.firstChild) {
                span.appendChild(fontNode.firstChild);
            }
            fontNode.replaceWith(span);
        });
    }

    sanitizedDescriptionStyle(node) {
        const safeStyle = [];
        const color = this.normalizeDescriptionColor(node.style.color);
        const backgroundColor = this.normalizeDescriptionColor(node.style.backgroundColor);
        const fontFamily = this.normalizeDescriptionFontFamily(node.style.fontFamily);
        const fontSize = this.toInput(node.style.fontSize).trim().toLowerCase();
        const textAlign = this.toInput(node.style.textAlign || node.getAttribute("align")).trim().toLowerCase();
        const marginLeft = this.toInput(node.style.marginLeft).trim().toLowerCase();
        const fontWeight = this.toInput(node.style.fontWeight).trim().toLowerCase();
        const fontStyle = this.toInput(node.style.fontStyle).trim().toLowerCase();
        const textDecoration = this.toInput(node.style.textDecoration || node.style.textDecorationLine)
            .trim()
            .toLowerCase();

        if (color) {
            safeStyle.push(`color: ${color}`);
        }
        if (backgroundColor) {
            safeStyle.push(`background-color: ${backgroundColor}`);
        }
        if (fontFamily) {
            safeStyle.push(`font-family: '${fontFamily}'`);
        }
        if (DESCRIPTION_ALLOWED_FONT_SIZES.has(fontSize)) {
            safeStyle.push(`font-size: ${fontSize}`);
        }
        if (DESCRIPTION_ALLOWED_ALIGNMENTS.has(textAlign)) {
            safeStyle.push(`text-align: ${textAlign}`);
        }
        if (DESCRIPTION_ALLOWED_INDENTS.has(marginLeft)) {
            safeStyle.push(`margin-left: ${marginLeft}`);
        }
        if (["bold", "700"].includes(fontWeight)) {
            safeStyle.push("font-weight: 700");
        }
        if (fontStyle === "italic") {
            safeStyle.push("font-style: italic");
        }
        if (/^(underline|line-through)(\s+(underline|line-through))*$/.test(textDecoration)) {
            safeStyle.push(`text-decoration: ${textDecoration}`);
        }
        return safeStyle.join("; ");
    }

    sanitizeDescriptionHtml(value) {
        const html = this.toInput(value);
        if (!html || typeof document === "undefined") {
            return html;
        }
        const allowedTags = new Set([
            "p", "br", "ul", "ol", "li", "strong", "b", "em", "i", "u",
            "s", "strike", "sub", "sup", "span", "div", "h2", "h3", "h4", "h5",
            "blockquote", "a",
        ]);
        const template = document.createElement("template");
        template.innerHTML = html;
        this.normalizeLegacyDescriptionFormatting(template.content);

        const cleanNode = (node) => {
            if (node.nodeType === 3) {
                return;
            }
            if (node.nodeType !== 1) {
                node.remove();
                return;
            }
            Array.from(node.childNodes).forEach(cleanNode);
            const tagName = node.tagName.toLowerCase();
            if (!allowedTags.has(tagName)) {
                const fragment = document.createDocumentFragment();
                while (node.firstChild) {
                    fragment.appendChild(node.firstChild);
                }
                node.replaceWith(fragment);
                return;
            }
            const safeStyle = this.sanitizedDescriptionStyle(node);
            Array.from(node.attributes).forEach((attr) => {
                const attrName = attr.name.toLowerCase();
                if (tagName === "a" && attrName === "href" && /^https?:\/\//i.test(attr.value || "")) {
                    node.setAttribute("target", "_blank");
                    node.setAttribute("rel", "noopener noreferrer");
                    return;
                }
                if (tagName === "a" && ["target", "rel"].includes(attrName)) {
                    return;
                }
                node.removeAttribute(attr.name);
            });
            if (safeStyle) {
                node.setAttribute("style", safeStyle);
            }
        };

        Array.from(template.content.childNodes).forEach(cleanNode);
        return template.innerHTML.trim();
    }

    normalizedDescriptionHtml(value = this.state.contentForm.description) {
        const raw = this.toInput(value);
        if (!raw.trim()) {
            return "";
        }
        return this.sanitizeDescriptionHtml(this.looksLikeHtml(raw) ? raw : this.plainTextToHtml(raw));
    }

    descriptionPlainText(value = this.state.contentForm.description) {
        const raw = this.toInput(value);
        if (!raw) {
            return "";
        }
        if (typeof document !== "undefined" && this.looksLikeHtml(raw)) {
            const container = document.createElement("div");
            container.innerHTML = this.sanitizeDescriptionHtml(raw);
            return (container.textContent || container.innerText || "").trim();
        }
        return raw.trim();
    }

    syncContentDescriptionEditor(force = false) {
        const editor = this.contentDescriptionEditorRef && this.contentDescriptionEditorRef.el;
        if (!editor) {
            return;
        }
        const html = this.normalizedDescriptionHtml();
        if (!force && document.activeElement === editor) {
            return;
        }
        if (force || this.lastContentDescriptionEditorHtml !== html || editor.innerHTML !== html) {
            editor.innerHTML = html;
            this.lastContentDescriptionEditorHtml = html;
        }
    }

    onContentDescriptionInput(ev) {
        const html = this.sanitizeDescriptionHtml(ev.currentTarget.innerHTML || "");
        this.state.contentForm.description = html;
        this.lastContentDescriptionEditorHtml = ev.currentTarget.innerHTML || "";
        this.saveContentDescriptionSelection();
    }

    normalizeContentDescriptionEditor(ev) {
        const html = this.normalizedDescriptionHtml(ev.currentTarget.innerHTML || "");
        if (ev.currentTarget.innerHTML !== html) {
            ev.currentTarget.innerHTML = html;
        }
        this.state.contentForm.description = html;
        this.lastContentDescriptionEditorHtml = html;
    }

    onContentDescriptionSourceInput(ev) {
        this.state.contentForm.description = ev.target.value || "";
        this.syncContentDescriptionEditor(true);
    }

    saveContentDescriptionSelection() {
        const editor = this.contentDescriptionEditorRef && this.contentDescriptionEditorRef.el;
        const selection = typeof window !== "undefined" ? window.getSelection() : null;
        if (!editor || !selection || !selection.rangeCount) {
            return;
        }
        const range = selection.getRangeAt(0);
        if (editor.contains(range.commonAncestorContainer)) {
            this.contentDescriptionSelection = range.cloneRange();
        }
    }

    restoreContentDescriptionSelection() {
        const editor = this.contentDescriptionEditorRef && this.contentDescriptionEditorRef.el;
        const selection = typeof window !== "undefined" ? window.getSelection() : null;
        if (!editor || !selection) {
            return false;
        }
        editor.focus();
        selection.removeAllRanges();
        if (
            this.contentDescriptionSelection &&
            editor.contains(this.contentDescriptionSelection.commonAncestorContainer)
        ) {
            try {
                selection.addRange(this.contentDescriptionSelection);
                return true;
            } catch (_error) {
                this.contentDescriptionSelection = null;
            }
        }
        const range = document.createRange();
        range.selectNodeContents(editor);
        range.collapse(false);
        selection.addRange(range);
        return true;
    }

    onContentDescriptionToolbarMouseDown(ev) {
        this.saveContentDescriptionSelection();
        ev.preventDefault();
    }

    updateContentDescriptionFromEditor() {
        const editor = this.contentDescriptionEditorRef && this.contentDescriptionEditorRef.el;
        if (!editor) {
            return;
        }
        this.state.contentForm.description = this.sanitizeDescriptionHtml(editor.innerHTML || "");
        this.lastContentDescriptionEditorHtml = editor.innerHTML || "";
        this.saveContentDescriptionSelection();
    }

    applyContentDescriptionCommand(command, value = null) {
        if (typeof document === "undefined" || typeof document.execCommand !== "function") {
            return;
        }
        this.restoreContentDescriptionSelection();
        document.execCommand(command, false, value);
        this.updateContentDescriptionFromEditor();
    }

    onContentDescriptionBlockChange(ev) {
        const value = ev.target.value;
        ev.target.value = "";
        if (value) {
            this.applyContentDescriptionCommand("formatBlock", `<${value}>`);
        }
    }

    onContentDescriptionFontChange(ev) {
        const value = this.normalizeDescriptionFontFamily(ev.target.value);
        ev.target.value = "";
        if (value) {
            this.applyContentDescriptionCommand("fontName", value);
        }
    }

    onContentDescriptionFontSizeChange(ev) {
        const fontSize = ev.target.value;
        const value = DESCRIPTION_COMMAND_FONT_SIZES[fontSize];
        ev.target.value = "";
        if (!value || typeof document === "undefined" || typeof document.execCommand !== "function") {
            return;
        }
        this.restoreContentDescriptionSelection();
        document.execCommand("fontSize", false, value);
        const editor = this.contentDescriptionEditorRef && this.contentDescriptionEditorRef.el;
        if (editor) {
            Array.from(editor.querySelectorAll(`font[size="${value}"]`)).forEach((fontNode) => {
                fontNode.removeAttribute("size");
                fontNode.style.fontSize = fontSize;
            });
        }
        this.updateContentDescriptionFromEditor();
    }

    onContentDescriptionTextColor(ev) {
        const value = this.normalizeDescriptionColor(ev.target.value);
        if (value) {
            this.applyContentDescriptionCommand("foreColor", value);
        }
    }

    onContentDescriptionHighlightColor(ev) {
        const value = this.normalizeDescriptionColor(ev.target.value);
        if (!value) {
            return;
        }
        this.restoreContentDescriptionSelection();
        const applied = document.execCommand("hiliteColor", false, value);
        if (!applied) {
            document.execCommand("backColor", false, value);
        }
        this.updateContentDescriptionFromEditor();
    }

    createContentDescriptionLink() {
        this.saveContentDescriptionSelection();
        const rawUrl = typeof window !== "undefined"
            ? window.prompt("URL del enlace (https://...)", "https://")
            : "";
        if (!rawUrl) {
            return;
        }
        let parsedUrl;
        try {
            parsedUrl = new URL(rawUrl);
        } catch (_error) {
            this.notify("La URL del enlace no es valida.", "warning");
            return;
        }
        if (!["http:", "https:"].includes(parsedUrl.protocol)) {
            this.notify("Solo se permiten enlaces HTTP o HTTPS.", "warning");
            return;
        }
        this.applyContentDescriptionCommand("createLink", parsedUrl.href);
    }

    normalizedTechnicalDescriptionHtml(value = this.state.contentForm.technicalDescription) {
        return this.normalizedDescriptionHtml(value);
    }

    technicalDescriptionPlainText(value = this.state.contentForm.technicalDescription) {
        return this.descriptionPlainText(value);
    }

    syncTechnicalDescriptionEditor(force = false) {
        const editor = this.technicalDescriptionEditorRef && this.technicalDescriptionEditorRef.el;
        if (!editor) {
            return;
        }
        const html = this.normalizedTechnicalDescriptionHtml();
        if (!force && document.activeElement === editor) {
            return;
        }
        if (force || this.lastTechnicalDescriptionEditorHtml !== html || editor.innerHTML !== html) {
            editor.innerHTML = html;
            this.lastTechnicalDescriptionEditorHtml = html;
        }
    }

    onTechnicalDescriptionInput(ev) {
        const html = this.sanitizeDescriptionHtml(ev.currentTarget.innerHTML || "");
        this.state.contentForm.technicalDescription = html;
        this.lastTechnicalDescriptionEditorHtml = ev.currentTarget.innerHTML || "";
        this.saveTechnicalDescriptionSelection();
    }

    normalizeTechnicalDescriptionEditor(ev) {
        const html = this.normalizedTechnicalDescriptionHtml(ev.currentTarget.innerHTML || "");
        if (ev.currentTarget.innerHTML !== html) {
            ev.currentTarget.innerHTML = html;
        }
        this.state.contentForm.technicalDescription = html;
        this.lastTechnicalDescriptionEditorHtml = html;
    }

    onTechnicalDescriptionSourceInput(ev) {
        this.state.contentForm.technicalDescription = ev.target.value || "";
        this.syncTechnicalDescriptionEditor(true);
    }

    saveTechnicalDescriptionSelection() {
        const editor = this.technicalDescriptionEditorRef && this.technicalDescriptionEditorRef.el;
        const selection = typeof window !== "undefined" ? window.getSelection() : null;
        if (!editor || !selection || !selection.rangeCount) {
            return;
        }
        const range = selection.getRangeAt(0);
        if (editor.contains(range.commonAncestorContainer)) {
            this.technicalDescriptionSelection = range.cloneRange();
        }
    }

    restoreTechnicalDescriptionSelection() {
        const editor = this.technicalDescriptionEditorRef && this.technicalDescriptionEditorRef.el;
        const selection = typeof window !== "undefined" ? window.getSelection() : null;
        if (!editor || !selection) {
            return false;
        }
        editor.focus();
        selection.removeAllRanges();
        if (
            this.technicalDescriptionSelection &&
            editor.contains(this.technicalDescriptionSelection.commonAncestorContainer)
        ) {
            try {
                selection.addRange(this.technicalDescriptionSelection);
                return true;
            } catch (_error) {
                this.technicalDescriptionSelection = null;
            }
        }
        const range = document.createRange();
        range.selectNodeContents(editor);
        range.collapse(false);
        selection.addRange(range);
        return true;
    }

    onTechnicalDescriptionToolbarMouseDown(ev) {
        this.saveTechnicalDescriptionSelection();
        ev.preventDefault();
    }

    updateTechnicalDescriptionFromEditor() {
        const editor = this.technicalDescriptionEditorRef && this.technicalDescriptionEditorRef.el;
        if (!editor) {
            return;
        }
        this.state.contentForm.technicalDescription = this.sanitizeDescriptionHtml(editor.innerHTML || "");
        this.lastTechnicalDescriptionEditorHtml = editor.innerHTML || "";
        this.saveTechnicalDescriptionSelection();
    }

    applyTechnicalDescriptionCommand(command, value = null) {
        if (typeof document === "undefined" || typeof document.execCommand !== "function") {
            return;
        }
        this.restoreTechnicalDescriptionSelection();
        document.execCommand(command, false, value);
        this.updateTechnicalDescriptionFromEditor();
    }

    onTechnicalDescriptionBlockChange(ev) {
        const value = ev.target.value;
        ev.target.value = "";
        if (value) {
            this.applyTechnicalDescriptionCommand("formatBlock", `<${value}>`);
        }
    }

    onTechnicalDescriptionFontChange(ev) {
        const value = this.normalizeDescriptionFontFamily(ev.target.value);
        ev.target.value = "";
        if (value) {
            this.applyTechnicalDescriptionCommand("fontName", value);
        }
    }

    onTechnicalDescriptionFontSizeChange(ev) {
        const fontSize = ev.target.value;
        const value = DESCRIPTION_COMMAND_FONT_SIZES[fontSize];
        ev.target.value = "";
        if (!value || typeof document === "undefined" || typeof document.execCommand !== "function") {
            return;
        }
        this.restoreTechnicalDescriptionSelection();
        document.execCommand("fontSize", false, value);
        const editor = this.technicalDescriptionEditorRef && this.technicalDescriptionEditorRef.el;
        if (editor) {
            Array.from(editor.querySelectorAll(`font[size="${value}"]`)).forEach((fontNode) => {
                fontNode.removeAttribute("size");
                fontNode.style.fontSize = fontSize;
            });
        }
        this.updateTechnicalDescriptionFromEditor();
    }

    onTechnicalDescriptionTextColor(ev) {
        const value = this.normalizeDescriptionColor(ev.target.value);
        if (value) {
            this.applyTechnicalDescriptionCommand("foreColor", value);
        }
    }

    onTechnicalDescriptionHighlightColor(ev) {
        const value = this.normalizeDescriptionColor(ev.target.value);
        if (!value) {
            return;
        }
        this.restoreTechnicalDescriptionSelection();
        const applied = document.execCommand("hiliteColor", false, value);
        if (!applied) {
            document.execCommand("backColor", false, value);
        }
        this.updateTechnicalDescriptionFromEditor();
    }

    createTechnicalDescriptionLink() {
        this.saveTechnicalDescriptionSelection();
        const rawUrl = typeof window !== "undefined"
            ? window.prompt("URL del enlace (https://...)", "https://")
            : "";
        if (!rawUrl) {
            return;
        }
        let parsedUrl;
        try {
            parsedUrl = new URL(rawUrl);
        } catch (_error) {
            this.notify("La URL del enlace no es valida.", "warning");
            return;
        }
        if (!["http:", "https:"].includes(parsedUrl.protocol)) {
            this.notify("Solo se permiten enlaces HTTP o HTTPS.", "warning");
            return;
        }
        this.applyTechnicalDescriptionCommand("createLink", parsedUrl.href);
    }

    marginBenefitLabel() {
        const product = this.currentProduct();
        const price = this.productComparisonPrice(product);
        const cost = this.parseNumber(product.effectiveCostMaxUsd ?? product.costUsd);
        const benefit = price - cost;
        return `Beneficio: ${this.formatUSD(benefit)}`;
    }

    parseNumber(value) {
        if (value === "" || value === null || value === undefined) {
            return 0;
        }
        return Number(value) || 0;
    }

    formatARS(value) {
        return new Intl.NumberFormat("es-AR", {
            style: "currency",
            currency: "ARS",
            maximumFractionDigits: 0,
        }).format(Number(value || 0));
    }

    formatUSD(value) {
        return `USD $${Number(value || 0).toFixed(2)}`;
    }

    formatCompetitorPrice(value, currency) {
        const numericValue = Number(value || 0);
        const rawCurrency = String(currency || "").trim();
        const currencyCode = rawCurrency.toUpperCase();
        if (currencyCode === "ARS" || currencyCode === "AR$" || currencyCode === "$") {
            return this.formatARS(numericValue);
        }
        if (currencyCode === "USD" || currencyCode === "US$" || currencyCode === "U$S") {
            return this.formatUSD(numericValue);
        }
        if (/^[A-Z]{3}$/.test(currencyCode)) {
            try {
                return new Intl.NumberFormat("es-AR", {
                    style: "currency",
                    currency: currencyCode,
                    maximumFractionDigits: 2,
                }).format(numericValue);
            } catch (_error) {
                // Fall back to the raw code without pretending it is ARS or USD.
            }
        }
        return `${rawCurrency || "MONEDA"} ${numericValue.toFixed(2)}`;
    }

    formatNumber(value) {
        return new Intl.NumberFormat("es-AR").format(Number(value || 0));
    }

    formatPercent(value) {
        return `${Number(value || 0).toFixed(1)}%`;
    }

    contentWordCount() {
        const text = this.descriptionPlainText();
        if (!text) {
            return 0;
        }
        return text.split(/\s+/).filter(Boolean).length;
    }

    contentWordCountLabel() {
        return `${this.contentWordCount()} palabras · ${this.contentTemplateWordTarget('short')} (${this.currentContentTemplate()?.format === 'general_specs' ? 'Descripción General' : 'resumen comercial corto'})`;
    }

    technicalDescriptionWordCount() {
        const text = this.technicalDescriptionPlainText();
        if (!text) {
            return 0;
        }
        return text.split(/\s+/).filter(Boolean).length;
    }

    technicalDescriptionWordCountLabel() {
        return `${this.technicalDescriptionWordCount()} palabras · ${this.contentTemplateWordTarget('long')} (información técnica ampliada)`;
    }

    filteredDashboardProducts() {
        return this.state.dashboardRows || [];
    }

    onDashboardSearchInput(ev) {
        this.state.searchTerm = ev.target.value || "";
        this.scheduleDashboardReload();
    }

    catalogSortOptions() {
        return [
            { value: "catalog", label: "Orden del catálogo" },
            { value: "recent", label: "Última edición" },
            { value: "name_asc", label: "Nombre: A–Z" },
            { value: "name_desc", label: "Nombre: Z–A" },
            { value: "price_asc", label: "Precio base: menor a mayor" },
            { value: "price_desc", label: "Precio base: mayor a menor" },
        ];
    }

    catalogQualityOptions() {
        return [
            { value: "", label: "Todas las fichas" },
            { value: "needs_attention", label: "Ficha incompleta" },
            { value: "complete", label: "Ficha completa" },
            { value: "published_missing_image", label: "Publicados sin imagen" },
            { value: "published_missing_content", label: "Publicados sin descripción comercial" },
            { value: "missing_seo", label: "SEO incompleto" },
            { value: "missing_geo", label: "GEO incompleto" },
            { value: "missing_category", label: "Sin categoría" },
            { value: "published", label: "Publicados" },
            { value: "unpublished", label: "Sin publicar" },
            { value: "content", label: "Contenido completo" },
            { value: "image", label: "Con imagen" },
            { value: "seo", label: "Metadatos SEO completos" },
            { value: "geo", label: "Metadatos GEO completos" },
            { value: "faq", label: "Con FAQs" },
            { value: "category", label: "Con categoría" },
            { value: "competitor", label: "Con competidores registrados" },
        ];
    }

    async changeDashboardSort(ev) {
        const sortKey = ev.target.value;
        if (!this.catalogSortOptions().some((option) => option.value === sortKey)) return;
        if (sortKey === (this.state.dashboardSortKey || "catalog") && !this.state.error) return;
        this.state.dashboardSortKey = sortKey;
        return this.loadDashboard({ page: 1 }, { showSpinner: false });
    }

    async changeDashboardQualityFilter(ev) {
        const quality = ev.target.value || "";
        if (!this.catalogQualityOptions().some((option) => option.value === quality)) return;
        if (quality === (this.state.dashboardQualityFilter || "") && !this.state.error) return;
        this.state.dashboardQualityFilter = quality;
        return this.loadDashboard({ page: 1 }, { showSpinner: false });
    }

    async clearCatalogFilters() {
        this.state.taxonomyFilters = [];
        this.state.meliFilter = "";
        this.state.dashboardQualityFilter = "";
        this.state.dashboardSortKey = "catalog";
        return this.loadDashboard({ search: "", page: 1 }, { showSpinner: false });
    }

    catalogHasFilters() {
        return !!(this.state.taxonomyFilters?.length || this.state.searchTerm || this.state.dashboardQualityFilter || this.state.meliFilter ||
            (this.state.dashboardSortKey && this.state.dashboardSortKey !== "catalog"));
    }

    catalogResultLabel() {
        const pager = this.state.dashboardPager || this.dashboardDefaultPager();
        const total = Math.max(0, Number(pager.total) || 0);
        if (!total) return "Sin productos para esta selección";
        const first = ((pager.page || 1) - 1) * (pager.limit || DASHBOARD_PAGE_SIZE) + 1;
        const last = Math.min(first + (pager.limit || DASHBOARD_PAGE_SIZE) - 1, total);
        return `Mostrando ${this.formatNumber(first)}–${this.formatNumber(last)} de ${this.formatNumber(total)} productos`;
    }

    catalogHealthItems(row) {
        const health = row?.catalogHealth;
        if (!health) return [];
        return [
            { key: "commercial", label: "Descripción comercial", section: "content", icon: "fa fa-file-text-o" },
            { key: "technical", label: "Descripción técnica", section: "content", icon: "fa fa-list-alt" },
            { key: "image", label: "Imagen", section: "images", icon: "fa fa-picture-o" },
            { key: "seo", label: "Metadatos SEO", section: "seo", icon: "fa fa-search" },
            { key: "geo", label: "Metadatos GEO", section: "seo", icon: "fa fa-crosshairs" },
            { key: "faq", label: "FAQs", section: "content", icon: "fa fa-comments-o" },
            { key: "category", label: "Categoría", section: "datos", icon: "fa fa-folder-open-o" },
        ].map((item) => ({ ...item, complete: health[item.key] === true }));
    }

    catalogHealthLabel(row) {
        const items = this.catalogHealthItems(row);
        return items.length ? `${items.filter((item) => item.complete).length} de 7 secciones completas` : "Sin evaluar";
    }

    catalogHealthPercent(row) {
        const items = this.catalogHealthItems(row);
        return items.length ? Math.round(items.filter((item) => item.complete).length / items.length * 100) : 0;
    }

    catalogNextAction(row) {
        const items = this.catalogHealthItems(row);
        const copy = {
            image: ["Añadir imagen", "Falta una imagen disponible en el catálogo."],
            commercial: ["Completar descripción", "Falta la descripción comercial."],
            technical: ["Completar ficha técnica", "Falta la descripción técnica."],
            seo: ["Completar SEO", "Faltan metadatos SEO."],
            geo: ["Completar GEO", "Faltan metadatos GEO."],
            faq: ["Añadir FAQs", "Falta una pregunta y respuesta completas."],
            category: ["Asignar categoría", "Falta la categoría de comercio electrónico."],
        };
        for (const key of ["image", "commercial", "technical", "seo", "geo", "faq", "category"]) {
            const item = items.find((candidate) => candidate.key === key && !candidate.complete);
            if (item) return { section: item.section, label: copy[key][0], reason: copy[key][1] };
        }
        return { section: "datos", label: "Abrir ficha", reason: items.length
            ? "Las siete secciones están completas; revisa los datos del producto."
            : "Revisa los datos del producto." };
    }

    catalogStockLabel(row) {
        return Number(row?.qtyAvailable) > 0 ? "En stock" : "Sin stock";
    }

    catalogStockClass(row) {
        return Number(row?.qtyAvailable) > 0 ? "is-in-stock" : "is-out-of-stock";
    }

    catalogProductStatusLabel(row) {
        if (row?.isArchived || row?.isActive === false) return "Archivado";
        if (row?.isDiscontinued || row?.saleOk === false) return "Fuera de venta";
        return "Activo";
    }

    catalogStatusClass(row) {
        if (row?.isArchived || row?.isActive === false) return "is-archived";
        if (row?.isDiscontinued || row?.saleOk === false) return "is-unavailable";
        return "is-active";
    }

    catalogPublicationLabel(row) {
        return row?.isPublished ? "Publicado" : "Sin publicar";
    }

    catalogPublicationClass(row) {
        return row?.isPublished ? "is-published" : "is-unpublished";
    }

    catalogMarginKnown(row) {
        const cost = Number(row?.effectiveCostUsd ?? row?.costUsd ?? 0);
        const price = this.effectivePriceRange(row || {}).min;
        return Number.isFinite(cost) && cost > 0 && Number.isFinite(price) && price > 0;
    }

    catalogRowBusy(row) {
        const id = row && typeof row === "object" ? row.id : row;
        return !!(this.state.dashboardBusy || this.state.catalogBusyRows?.[id]);
    }

    toggleCatalogReview(row) {
        if (!row?.id || this.catalogRowBusy(row)) return;
        this.state.catalogReviewId = String(this.state.catalogReviewId) === String(row.id) ? false : row.id;
    }

    closeCatalogReview(ev = null) {
        const reviewId = this.state.catalogReviewId;
        const home = ev?.currentTarget?.closest?.(".bpi-home");
        this.state.catalogReviewId = false;
        // Only a deliberate close/Escape returns keyboard focus. Automatic
        // invalidation during navigation or refresh must never steal focus.
        if (home && reviewId) {
            const invoker = Array.from(home.querySelectorAll("[data-catalog-review]"))
                .find((button) => button.dataset.catalogReview === String(reviewId));
            if (invoker && !invoker.disabled) invoker.focus({ preventScroll: true });
        }
    }

    onCatalogReviewKeydown(ev) {
        if (ev.key !== "Escape" || !this.state.catalogReviewId) return;
        ev.preventDefault();
        ev.stopPropagation();
        this.closeCatalogReview(ev);
    }

    catalogReviewRow() {
        return (this.state.dashboardRows || []).find((row) => String(row.id) === String(this.state.catalogReviewId)) || null;
    }

    async openCatalogProduct(row, section = "datos") {
        if (!row?.id || this.catalogRowBusy(row)) return;
        if (this.detailHasUnsavedChanges() && !await this.confirmDetailLeave()) return;
        const allowed = new Set(["datos", "content", "seo", "images", "competitors"]);
        this.state.origin = "dashboard";
        // Set the tab before loading; never apply it after awaiting a request
        // that may now belong to a different product/navigation generation.
        this.state.activeTab = allowed.has(section) ? section : "datos";
        await this.loadDetail(row.id);
    }

    async changeDashboardTab(tab) {
        if (tab === this.state.dashboardTab && !this.state.dashboardQualityFilter && !this.state.error) {
            return;
        }
        this.state.dashboardQualityFilter = "";
        await this.loadDashboard({ tab, page: 1 }, { showSpinner: false });
    }

    async changeDashboardPage(page) {
        const targetPage = Math.max(1, Number(page || 1));
        const pager = this.state.dashboardPager || this.dashboardDefaultPager();
        if (targetPage === pager.page || targetPage > pager.pageCount) {
            return;
        }
        await this.loadDashboard({ page: targetPage }, { showSpinner: false });
    }

    dashboardPageLabel() {
        const pager = this.state.dashboardPager || this.dashboardDefaultPager();
        return `Pagina ${pager.page} de ${pager.pageCount}`;
    }


    async saveExchangeRate() {
        this.state.exchangeRateBusy = true;
        const request = this.beginRequest("saveExchangeRate");
        try {
            const value = this.parseNumber(this.state.exchangeRateInput) || 1650;
            const result = await this.rpc("/bader_product_intelligence/update_exchange_rate", {
                exchange_rate: value,
            });
            if (!this.isRequestCurrent(request)) return;
            this.state.exchangeRate = result.exchangeRate || value;
            this.state.exchangeRateInput = String(this.state.exchangeRate);
            await this.refreshDashboardHome();
            if (this.isRequestCurrent(request)) this.notify("Tipo de cambio actualizado.");
        } catch (error) {
            if (!this.isRequestCurrent(request)) return;
            this.notify(this.errorMessage(error, "No se pudo actualizar el tipo de cambio."), "danger");
        } finally {
            if (this.isRequestCurrent(request)) this.state.exchangeRateBusy = false;
        }
    }

    async openDetail(productId) {
        if (this.detailHasUnsavedChanges() && !await this.confirmDetailLeave()) return;
        this.state.origin = "dashboard";
        this.state.activeTab = "overview";
        await this.loadDetail(productId);
    }

    async goBack() {
        if (this.detailHasUnsavedChanges() && !await this.confirmDetailLeave()) return;
        if (this.state.origin === "product_form") {
            this.openProductForm();
            return;
        }
        await this.refreshDashboardHome();
    }

    async openProductForm() {
        if (this.detailHasUnsavedChanges() && !await this.confirmDetailLeave()) return;
        if (!this.state.productId) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "product.template",
            res_id: this.state.productId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async openVariantForm(variantId) {
        if (this.detailHasUnsavedChanges() && !await this.confirmDetailLeave()) return;
        if (!variantId) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "product.product",
            res_id: variantId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    effectivePriceRange(product = this.currentProduct()) {
        return productEffectivePriceRange(product);
    }

    productComparisonPrice(product = this.currentProduct()) {
        const range = this.effectivePriceRange(product);
        return range.max ? (range.min + range.max) / 2 : 0;
    }

    formatProductPrice(product = this.currentProduct()) {
        const range = this.effectivePriceRange(product);
        if (Math.abs(range.max - range.min) < 0.00001) {
            return this.formatUSD(range.min);
        }
        return `${this.formatUSD(range.min)} - ${this.formatUSD(range.max)}`;
    }

    formatProductPriceLocal(product = this.currentProduct()) {
        const range = this.effectivePriceRange(product);
        const exchangeRate = Number(product.localExchangeRate || this.state.exchangeRate || 0);
        const min = range.min * exchangeRate;
        const max = range.max * exchangeRate;
        if (Math.abs(max - min) < 0.00001) {
            return this.formatARS(min);
        }
        return `${this.formatARS(min)} - ${this.formatARS(max)}`;
    }

    formatProductCost(product = this.currentProduct()) {
        const min = Number(product.effectiveCostMinUsd ?? product.costUsd ?? 0);
        const max = Number(product.effectiveCostMaxUsd ?? min);
        if (Math.abs(max - min) < 0.00001) {
            return this.formatUSD(min);
        }
        return `${this.formatUSD(min)} - ${this.formatUSD(max)}`;
    }

    detailMargin() {
        const product = this.currentProduct();
        const price = this.productComparisonPrice(product);
        const minCost = Number(product.effectiveCostMinUsd ?? product.costUsd ?? 0);
        const maxCost = Number(product.effectiveCostMaxUsd ?? minCost);
        const cost = maxCost ? (minCost + maxCost) / 2 : 0;
        if (!price || !cost) {
            return 0;
        }
        return ((price - cost) / price) * 100;
    }

    averageCompetitorPrice() {
        const prices = this.currentCompetitors()
            .map((item) => competitorComparablePriceUsd(item))
            .filter((price) => price > 0);
        if (!prices.length) {
            return 0;
        }
        return prices.reduce((sum, price) => sum + price, 0) / prices.length;
    }

    priceVsCompetition() {
        const average = this.averageCompetitorPrice();
        const product = this.currentProduct();
        const price = this.productComparisonPrice(product);
        if (!average || !price) {
            return null;
        }
        return ((price - average) / average) * 100;
    }

    competitorPriceRange() {
        const prices = this.currentCompetitors()
            .map((item) => competitorComparablePriceUsd(item))
            .filter((price) => price > 0)
            .sort((left, right) => left - right);
        return {
            min: prices.length ? prices[0] : 0,
            max: prices.length ? prices[prices.length - 1] : 0,
        };
    }

    overviewInsights() {
        const product = this.currentProduct();
        const insights = [];
        const margin = this.detailMargin();
        const priceVs = this.priceVsCompetition();
        if (Number(product.qtyAvailable || 0) < 10) {
            insights.push({
                type: "warning",
                title: "Stock bajo",
                description: `Solo quedan ${this.formatNumber(product.qtyAvailable || 0)} unidades.`,
            });
        }
        if (margin > 40) {
            insights.push({
                type: "success",
                title: "Excelente margen",
                description: `El margen actual es ${this.formatPercent(margin)} y muestra buena rentabilidad.`,
            });
        }
        if (priceVs !== null && priceVs > 15) {
            insights.push({
                type: "warning",
                title: "Precio alto vs competencia",
                description: `El precio esta ${this.formatPercent(priceVs)} por encima del promedio de mercado.`,
            });
        }
        if (priceVs !== null && priceVs < 0) {
            insights.push({
                type: "success",
                title: "Precio competitivo",
                description: `El producto esta ${this.formatPercent(Math.abs(priceVs))} por debajo de la media.`,
            });
        }
        return insights;
    }

    analyticsInsights() {
        return this.overviewInsights();
    }

    selectTab(tabId) {
        return this.selectDetailSection(tabId);
    }

    updateProductField(field, value) {
        this.state.productForm[field] = value;
        if (field === "name") this.state.contentForm.name = value;
        if (field === "name" && !this.state.productForm.slug) {
            this.state.productForm.slug = this.generateSlug(value);
        }
    }

    updateVariantDraft(variantId, field, value) {
        const variant = this.currentVariants().find((item) => String(item.id) === String(variantId));
        if (variant) {
            variant[field] = value;
        }
    }

    async saveVariant(variant) {
        if (!variant || this.state.variantBusy) {
            return;
        }
        const request = this.beginRequest("variant", true);
        this.state.variantBusy = true;
        try {
            const payload = await this.rpc("/bader_product_intelligence/update_variant", {
                product_tmpl_id: request.productId,
                product_variant_id: variant.id,
                values: {
                    sku: variant.sku || "",
                    barcode: variant.barcode || "",
                    costUsd: this.parseNumber(variant.costUsdInput),
                    active: !!variant.active,
                },
            });
            if (!this.isRequestCurrent(request)) return;
            this.applyDetailUpdate(payload, request, { variantDrafts: { id: variant.id, fields: ['sku', 'barcode', 'costUsdInput', 'costUsd', 'active'] } });
            this.state.activeTab = "variants_pack";
            this.state.selectedVariantId = variant.id;
            this.notify("Variante actualizada.");
        } catch (error) {
            if (!this.isRequestCurrent(request)) return;
            this.notify(this.errorMessage(error, "No se pudo actualizar la variante."), "danger");
        } finally {
            if (this.isRequestCurrent(request)) this.state.variantBusy = false;
        }
    }

    async setVariantImage(variant, operation) {
        if (!variant || this.state.variantBusy) {
            return;
        }
        const payload = {
            product_tmpl_id: this.state.productId,
            product_variant_id: variant.id,
        };
        if (operation === "remove") {
            payload.remove = true;
        } else if (operation === "upload") {
            if (!variant.imageUploadDataUrl) {
                this.notify("Selecciona una imagen para la variante.", "warning");
                return;
            }
            payload.image_data_url = variant.imageUploadDataUrl;
        } else {
            if (!variant.imageReferenceToken) {
                this.notify("Selecciona una imagen de la galería.", "warning");
                return;
            }
            payload.image_token = variant.imageReferenceToken;
        }
        const request = this.beginRequest("variant", true);
        this.state.variantBusy = true;
        try {
            const result = await this.rpc("/bader_product_intelligence/set_variant_image", payload);
            if (!this.isRequestCurrent(request)) return;
            this.applyDetailUpdate(result, request, { variantDrafts: { id: variant.id, fields: ["imageUrl", "hasOwnImage", "imageUploadDataUrl", "imageUploadName", "imageReferenceToken"] } });
            this.state.activeTab = "variants_pack";
            this.state.selectedVariantId = variant.id;
            this.notify(operation === "remove" ? "Imagen propia eliminada." : "Imagen de variante actualizada.");
        } catch (error) {
            if (!this.isRequestCurrent(request)) return;
            this.notify(this.errorMessage(error, "No se pudo actualizar la imagen de la variante."), "danger");
        } finally {
            if (this.isRequestCurrent(request)) this.state.variantBusy = false;
        }
    }

    handleVariantImageUpload(variantId, ev) {
        const file = ev.target.files && ev.target.files[0];
        const variant = this.currentVariants().find((item) => String(item.id) === String(variantId));
        if (!file || !variant) {
            return;
        }
        if (!ALLOWED_IMAGE_UPLOAD_TYPES.has(file.type)) {
            this.notify("Solo se permiten imágenes PNG, JPEG o WebP.", "warning");
            ev.target.value = "";
            return;
        }
        if (file.size > MAX_IMAGE_UPLOAD_BYTES) {
            this.notify("La imagen supera el tamaño máximo permitido de 10 MiB.", "warning");
            ev.target.value = "";
            return;
        }
        const request = this.beginRequest("variantUpload");
        const reader = new FileReader();
        reader.onload = (event) => {
            if (!this.isRequestCurrent(request)) return;
            variant.imageUploadDataUrl = event.target.result;
            variant.imageUploadName = file.name;
        };
        reader.readAsDataURL(file);
    }

    updatePackField(field, value) {
        this.state.packForm[field] = value;
        if (
            (field === "packType" || field === "componentPriceMode") &&
            (this.state.packForm.packType !== "detailed" || this.state.packForm.componentPriceMode !== "detailed")
        ) {
            this.state.packForm.modifiable = false;
        }
    }

    updatePackComponent(component, field, value) {
        if (component) {
            component[field] = value;
        }
    }

    removePackComponent(composition, index) {
        if (!composition) {
            return;
        }
        composition.components.splice(index, 1);
    }

    onPackComponentSearchKeydown(ev) {
        if (ev.key !== "Enter" || ev.isComposing) {
            return;
        }
        ev.preventDefault();
        return this.searchPackComponents();
    }

    async searchPackComponents() {
        const query = (this.state.componentSearch.query || "").trim();
        const request = this.beginRequest("componentSearch", true);
        this.state.componentSearchBusy = true;
        try {
            const result = await this.rpc("/bader_product_intelligence/search_pack_components", {
                product_tmpl_id: request.productId,
                query,
                limit: 20,
            });
            if (!this.isRequestCurrent(request)) return;
            if (query === (this.state.componentSearch.query || "").trim()) this.state.componentSearch.results = result.components || [];
        } catch (error) {
            if (!this.isRequestCurrent(request)) return;
            this.notify(this.errorMessage(error, "No se pudieron buscar componentes."), "danger");
        } finally {
            if (this.isRequestCurrent(request)) this.state.componentSearchBusy = false;
        }
    }

    addPackComponent(candidate) {
        const composition = this.currentPackComposition();
        if (!composition || !candidate) {
            return;
        }
        if (composition.components.some((component) => component.productVariantId === candidate.productVariantId)) {
            this.notify("El componente ya está incluido en esta composición.", "warning");
            return;
        }
        composition.components.push({
            lineId: false,
            productVariantId: candidate.productVariantId,
            productTemplateId: candidate.productTemplateId,
            name: candidate.name,
            sku: candidate.sku || "",
            active: true,
            isPack: !!candidate.isPack,
            quantity: 1,
            quantityInput: "1",
            saleDiscount: 0,
            saleDiscountInput: "0",
            unitPriceUsd: candidate.effectivePriceUsd || 0,
            linePriceUsd: candidate.effectivePriceUsd || 0,
            unitCostUsd: candidate.costUsd || 0,
            lineCostUsd: candidate.costUsd || 0,
            qtyAvailable: candidate.qtyAvailable || 0,
            possiblePackQty: Number(candidate.qtyAvailable || 0),
        });
        this.state.componentSearch.results = [];
        this.state.componentSearch.query = "";
    }

    async savePack() {
        const pack = this.currentPack();
        if (!pack.isPack || this.state.packBusy) {
            return;
        }
        const request = this.beginRequest("pack", true);
        this.state.packBusy = true;
        try {
            const values = {
                packType: pack.packType,
                componentPriceMode: pack.componentPriceMode,
                modifiable: !!pack.modifiable,
                compositions: (pack.compositions || []).map((composition) => ({
                    variantId: composition.variantId,
                    components: (composition.components || []).map((component) => ({
                        lineId: component.lineId || false,
                        productVariantId: component.productVariantId,
                        quantity: this.parseNumber(component.quantityInput),
                        saleDiscount: this.parseNumber(component.saleDiscountInput),
                    })),
                })),
            };
            const result = await this.rpc("/bader_product_intelligence/update_pack", {
                product_tmpl_id: request.productId,
                packRevision: pack.revision,
                values,
            });
            if (!this.isRequestCurrent(request)) return;
            this.applyDetailUpdate(result, request, { packForm: true });
            this.state.activeTab = "variants_pack";
            this.notify("Pack actualizado.");
        } catch (error) {
            if (!this.isRequestCurrent(request)) return;
            this.notify(this.errorMessage(error, "No se pudo actualizar el Pack."), "danger");
        } finally {
            if (this.isRequestCurrent(request)) this.state.packBusy = false;
        }
    }

    generateSlug(text) {
        return (text || "")
            .toLowerCase()
            .normalize("NFKD")
            .replace(/[^\w\s-]/g, "")
            .replace(/[\u0300-\u036f]/g, "")
            .replace(/[-\s]+/g, "-")
            .replace(/^-+|-+$/g, "")
            .slice(0, 100);
    }

    regenerateSlug(source = "name") {
        const base = source === "seo" ? this.state.seoForm.seoTitle : this.state.productForm.name;
        const slug = this.generateSlug(base);
        this.state.productForm.slug = slug;
        this.state.seoForm.slug = slug;
    }

    updateContentField(field, value) {
        this.state.contentForm[field] = value;
        if (field === "name") this.state.productForm.name = value;
    }

    updateSeoField(field, value) {
        this.state.seoForm[field] = value;
        if (field === "slug") {
            this.state.productForm.slug = value;
        }
    }

    updateCategoryField(field, value) {
        if (field === "categoryId") this.state.productForm.categoryId = value;
        else this.state.categoryForm[field] = value;
    }

    toggleManualMode(ev) {
        this.state.categoryForm.manualMode = !!ev.target.checked;
    }

    toggleNiche(nicheId) {
        const current = this.state.categoryForm.niches || [];
        if (current.includes(nicheId)) {
            this.state.categoryForm.niches = current.filter((item) => item !== nicheId);
        } else {
            this.state.categoryForm.niches = [...current, nicheId];
        }
    }

    addFaq() {
        this.state.contentForm.faqs.push({ question: "", answer: "" });
    }

    updateFaq(index, field, value) {
        const current = this.state.contentForm.faqs[index] || { question: "", answer: "" };
        this.state.contentForm.faqs[index] = {
            ...current,
            [field]: value,
        };
    }

    removeFaq(index) {
        this.state.contentForm.faqs.splice(index, 1);
    }

    technicalSpecFields() {
        return [ ['height', 'Alto', 'cm'], ['widthMax', 'Ancho máximo', 'cm'],
            ['widthMin', 'Ancho mínimo', 'cm'], ['length', 'Largo', 'cm'],
            ['diameter', 'Diámetro', 'cm'], ['weight', 'Peso neto', 'g'] ];
    }

    technicalSpecMeta(variantId) {
        return (this.state.detail?.technicalSpecifications || []).find(row => row.variantId === variantId) || {};
    }

    technicalSpecSource(variantId, key) {
        const source = this.technicalSpecMeta(variantId).sources?.[key];
        return source ? `${source.label || 'Dato guardado'} · ${source.date || ''}${source.row ? ' · Fila ' + source.row : ''}` : 'Sin dato guardado';
    }

    updateTechnicalSpec(row, key, value) {
        row.values[key] = value;
    }

    productSaveValues(form = this.state.productForm) {
        return {
            technicalSpecifications: this.snapshotDraft(form.technicalSpecifications || []),
            name: form.name, sku: form.sku, slug: form.slug, brand: form.brand,
            categoryId: form.categoryId || false,
            priceUsd: this.parseNumber(form.priceUsd), previousPriceUsd: this.parseNumber(form.previousPriceUsd),
            costUsd: this.parseNumber(form.costUsd), isPublished: !!form.isPublished, featured: !!form.featured,
        };
    }

    categorySaveValues(form = this.state.categoryForm, product = this.state.productForm) {
        if (form.classification) return { classification: this.snapshotDraft(form.classification) };
        return {
            manualMode: !!form.manualMode, niches: [...(form.niches || [])],
            type: form.type || false, subcategory: form.subcategory || false,
            categoryId: product.categoryId || false,
        };
    }

    contentTemplateSelectionId() {
        return Number(this.state.contentForm?.templateId) || false;
    }

    contentTemplateContextMatchesSelection(context = this.state.contentTemplateContext) {
        return !!context?.effective?.id && (context.selectionId || false) === this.contentTemplateSelectionId();
    }

    currentContentTemplate() {
        return this.contentTemplateContextMatchesSelection() ? this.state.contentTemplateContext.effective : null;
    }

    contentTemplateWordTarget(kind) {
        const template = this.currentContentTemplate();
        if (!template) return kind === 'short' ? 'objetivo 45-70' : 'objetivo 350-650';
        const min = Number(template[`${kind}MinWords`]) || 0;
        const max = Number(template[`${kind}MaxWords`]) || 0;
        if (min && max) return `objetivo ${min}-${max}`;
        if (min) return `objetivo mínimo ${min}`;
        if (max) return `objetivo máximo ${max}`;
        return 'sin mínimo obligatorio';
    }

    contentTemplateSourceLabel() {
        const source = this.state.contentTemplateContext?.source || {};
        if (!this.contentTemplateContextMatchesSelection()) return 'Modelo pendiente de consultar';
        if (source.kind === 'manual') return 'Selección manual para este producto';
        if (source.kind === 'ancestor') return `Heredado de ${source.categoryPath || source.categoryName}`;
        if (source.kind === 'category') return `Configurado en ${source.categoryPath || source.categoryName}`;
        return 'Modelo general: la categoría interna no tiene otro modelo configurado';
    }

    contentTemplateFingerprint(context = this.state.contentTemplateContext) {
        return JSON.stringify([
            context?.selectionId || false, context?.effective?.id || false,
            context?.effective?.revision || false, context?.internalCategory?.id || false,
            context?.source?.kind || '', context?.source?.categoryId || false,
            context?.specificationRevision || '',
            context?.semanticRevision || '',
        ]);
    }

    async changeContentTemplate(ev) {
        this.state.contentForm.templateId = Number(ev?.target?.value ?? ev) || false;
        this.contentTemplateSelectionVersion = (this.contentTemplateSelectionVersion || 0) + 1;
        this.state.contentGenerationWarnings = [];
        await this.refreshContentTemplateContext();
    }

    async refreshContentTemplateContext() {
        if (!this.state.productId) return false;
        const request = this.beginRequest('contentTemplate');
        const selection = this.contentTemplateSelectionId();
        const version = this.contentTemplateSelectionVersion || 0;
        this.state.contentTemplateBusy = true;
        this.state.contentTemplateError = '';
        try {
            const context = await this.rpc('/bader_product_intelligence/content_template_context', {
                product_tmpl_id: request.productId, template_id: selection,
            });
            if (!this.isRequestCurrent(request) || version !== (this.contentTemplateSelectionVersion || 0) ||
                selection !== this.contentTemplateSelectionId()) return false;
            if (!this.contentTemplateContextMatchesSelection(context)) throw new Error('Invalid template context');
            this.state.contentTemplateContext = context;
            return context;
        } catch (error) {
            if (this.isRequestCurrent(request)) {
                this.state.contentTemplateError = this.errorMessage(error, 'No se pudo consultar el modelo. Tus borradores se conservan.');
            }
            return false;
        } finally {
            if (this.isRequestCurrent(request)) this.state.contentTemplateBusy = false;
        }
    }

    async manageContentTemplates() {
        if (this.state.contentTemplateAdminBusy) return;
        const request = this.beginRequest('contentTemplateAdmin');
        this.contentTemplateSelectionVersion = (this.contentTemplateSelectionVersion || 0) + 1;
        this.state.contentTemplateAdminBusy = true;
        try {
            await this.action.doAction({
                type: 'ir.actions.act_window', name: 'Modelos de descripción',
                res_model: 'bpi.content.template', views: [[false, 'list'], [false, 'form']],
                target: 'new', context: { ...(this.user?.context || {}) },
            }, {
                onClose: async () => {
                    if (!this.isRequestCurrent(request)) return;
                    this.state.contentTemplateAdminBusy = false;
                    await this.refreshContentTemplateContext();
                },
            });
        } catch (error) {
            if (!this.isRequestCurrent(request)) return;
            this.state.contentTemplateAdminBusy = false;
            this.notify(this.errorMessage(error, 'No se pudo abrir la biblioteca de modelos.'), 'danger');
        }
    }

    emptyDocumentPanel() {
        return { revision: 0, title: '', intro: '', coverUrl: '', buttons: Array.from({ length: 3 }, () => ({
            label: '', kind: 'url', url: '', filename: '', size: 0, hasFile: false, fileUrl: '',
        })) };
    }

    documentPanel() {
        return this.state.contentForm.documents || this.emptyDocumentPanel();
    }

    updateDocumentPanel(key, value) {
        if (!this.state.contentForm.documents) this.state.contentForm.documents = this.emptyDocumentPanel();
        this.state.contentForm.documents[key] = value;
    }

    updateDocumentButton(index, key, value) {
        if (!this.state.contentForm.documents) this.state.contentForm.documents = this.emptyDocumentPanel();
        const row = this.state.contentForm.documents.buttons[index];
        row[key] = value;
        if (key === 'kind') { row.upload = false; row.filename = ''; row.size = 0; row.hasFile = false; row.fileUrl = ''; row.url = ''; }
    }

    clearDocumentButton(index) {
        if (!this.state.contentForm.documents) this.state.contentForm.documents = this.emptyDocumentPanel();
        this.state.contentForm.documents.buttons[index] = { ...this.emptyDocumentPanel().buttons[index], upload: false };
    }

    documentCoverPreview() {
        const panel = this.documentPanel();
        return panel.cover ? 'data:image/' + (panel.cover.startsWith('/9j') ? 'jpeg' : (panel.cover.startsWith('UklGR') ? 'webp' : 'png')) + ';base64,' + panel.cover : (panel.cover === false ? '' : panel.coverUrl);
    }

    async selectDocumentFile(ev, slot) {
        const file = ev.target.files?.[0]; ev.target.value = '';
        if (!file) return;
        const cover = slot === 'cover';
        if (!file.size || file.size > (cover ? 2 : 10) * 1024 * 1024 ||
            (cover ? !['image/jpeg','image/png','image/webp'].includes(file.type) : !/\.pdf$/i.test(file.name))) {
            this.notify(cover ? 'Usa una portada JPG, PNG o WebP de hasta 2 MB.' : 'Usa un PDF de hasta 10 MB.', 'warning'); return;
        }
        if (!this.state.contentForm.documents) this.state.contentForm.documents = this.emptyDocumentPanel();
        const panel = this.state.contentForm.documents;
        const row = cover ? panel : panel.buttons[slot];
        const original = cover ? panel.cover : row.upload;
        const request = this.beginRequest('documentFile:' + slot);
        try {
            const encoded = await new Promise((resolve, reject) => {
                const reader = new FileReader(); reader.onload = () => resolve(String(reader.result).split(',')[1]);
                reader.onerror = () => reject(new Error('file read failed')); reader.readAsDataURL(file);
            });
            if (!this.isRequestCurrent(request)) return;
            if (this.state.contentForm.documents !== panel) {
                this.notify('La ficha cambió mientras se leía el archivo. Selecciónalo otra vez para conservarlo.', 'warning'); return;
            }
            if (cover ? panel.cover !== original : (panel.buttons[slot] !== row || row.kind !== 'file' || row.upload !== original)) return;
            if (cover) panel.cover = encoded;
            else Object.assign(row, { upload: encoded, filename: file.name, size: file.size, hasFile: true, fileUrl: '' });
        } catch (error) {
            if (this.isRequestCurrent(request)) this.notify('No se pudo leer el archivo. Tus borradores se conservan.', 'danger');
        }
    }

    contentSaveValues(form = this.state.contentForm) {
        return {
            ...(form.documents ? { documents: this.snapshotDraft(form.documents) } : {}),
            name: form.name, description: form.description, technicalDescription: form.technicalDescription,
            tone: form.tone, audience: form.audience,
            ...(form.templateId !== undefined ? { templateId: Number(form.templateId) || false } : {}),
            faqs: (form.faqs || []).map((faq) => ({ question: faq.question, answer: faq.answer })),
        };
    }

    seoSaveValues(form = this.state.seoForm) {
        return {
            seoTitle: form.seoTitle, seoDescription: form.seoDescription,
            seoKeywords: (form.seoKeywords || "").split(",").map((item) => item.trim()).filter(Boolean),
            geoTitle: form.geoTitle, geoDescription: form.geoDescription,
            geoKeywords: (form.geoKeywords || "").split(",").map((item) => item.trim()).filter(Boolean),
            geoFeatures: (form.geoFeatures || "").split(",").map((item) => item.trim()).filter(Boolean),
            seoScore: form.seoScore || 0, geoScore: form.geoScore || 0,
            competitivenessScore: form.competitivenessScore || 0,
        };
    }

    async saveProductData() {
        return this.rpc("/bader_product_intelligence/update_product", {
            product_tmpl_id: this.state.productId, values: this.productSaveValues(),
        });
    }

    async saveCategoryData() {
        return this.rpc("/bader_product_intelligence/save_category", {
            product_tmpl_id: this.state.productId, values: this.categorySaveValues(),
        });
    }

    async saveContentData() {
        return this.rpc("/bader_product_intelligence/save_content", {
            product_tmpl_id: this.state.productId, values: this.contentSaveValues(),
        });
    }

    async saveSeoData() {
        return this.rpc("/bader_product_intelligence/save_seo", {
            product_tmpl_id: this.state.productId, seo_data: this.seoSaveValues(),
        });
    }

    async saveAll() {
        if (!this.state.productId || this.detailBaseSaveBusy()) return;
        const request = this.beginRequest("save", true);
        const drafts = request.drafts;
        const payload = {
            product_tmpl_id: request.productId,
            product_values: this.productSaveValues(drafts.productForm),
            category_values: this.categorySaveValues(drafts.categoryForm, drafts.productForm),
            content_values: this.contentSaveValues(drafts.contentForm),
            seo_data: this.seoSaveValues(drafts.seoForm),
        };
        this.state.saveBusy = true;
        try {
            const result = await this.rpc("/bader_product_intelligence/save_all", payload);
            if (!this.isRequestCurrent(request)) return;
            this.applyDetailUpdate(result, request, { productForm: true, categoryForm: true, contentForm: true, seoForm: true });
            if (request.seoPreviewVersion === (this.seoPreviewVersion || 0)) this.state.seoPreviewPending = false;
            this.notify("Cambios guardados.");
        } catch (error) {
            if (this.isRequestCurrent(request)) this.notify(this.errorMessage(error, "No se pudieron guardar los cambios."), "danger");
        } finally {
            if (this.isRequestCurrent(request)) this.state.saveBusy = false;
        }
    }

    async analyzeSeo() {
        if (!this.state.productId || this.detailBaseSaveBusy()) return;
        const request = this.beginRequest("seoJob", true);
        this.state.seoBusy = true;
        this.state.seoJobMessage = "Iniciando trabajo de Nancy AI...";
        try {
            const result = await this.rpc("/bader_product_intelligence/ai_job/start_seo", {
                product_tmpl_id: request.productId,
                target_audience: this.state.contentForm.audience || "clinicas",
            });
            if (!this.isRequestCurrent(request)) return;
            const job = result.job || {};
            if (!job.id || String(job.productId) !== String(request.productId)) throw new Error("Trabajo SEO inválido.");
            this.state.seoJobId = job.id;
            this.state.seoJobMessage = job.message || "Nancy AI esta trabajando en segundo plano...";
            this.notify("Trabajo SEO iniciado. Nancy AI preparará una propuesta sin cambiar el contenido guardado.", "info");
            this.scheduleSeoJobPoll(job.id, 3000, request);
        } catch (error) {
            if (!this.isRequestCurrent(request)) return;
            this.state.seoBusy = false;
            this.state.seoJobId = false;
            this.state.seoJobMessage = "";
            this.notify(this.errorMessage(error, "No se pudo analizar el SEO."), "danger");
        }
    }

    async saveSeoOnly() {
        if (this.detailBaseSaveBusy()) return;
        const request = this.beginRequest("seoSave", true);
        this.state.seoBusy = true;
        try {
            await this.saveSeoData();
            if (!this.isRequestCurrent(request)) return;
            await this.refreshDetail(request, { seoForm: true });
            if (!this.isRequestCurrent(request)) return;
            if (request.seoPreviewVersion === (this.seoPreviewVersion || 0)) this.state.seoPreviewPending = false;
            this.notify("SEO guardado.");
        } catch (error) {
            if (!this.isRequestCurrent(request)) return;
            this.notify(this.errorMessage(error, "No se pudo guardar el SEO."), "danger");
        } finally {
            if (this.isRequestCurrent(request)) this.state.seoBusy = false;
        }
    }

    async generateContent() {
        if (this.state.saveBusy || this.state.categoryBusy || this.state.seoBusy ||
            this.state.contentTemplateBusy || this.state.contentTemplateAdminBusy || this.state.contentTemplateError) return;
        const request = this.beginRequest("content", true);
        const template = this.currentContentTemplate();
        const selectionVersion = this.contentTemplateSelectionVersion || 0;
        const fingerprint = this.contentTemplateFingerprint();
        this.state.contentBusy = true;
        this.state.contentGenerationWarnings = [];
        try {
            const result = await this.rpc("/bader_product_intelligence/generate_content", {
                product_tmpl_id: request.productId,
                tone: request.drafts.contentForm.tone,
                audience: request.drafts.contentForm.audience,
                ...(template ? {
                    template_id: Number(request.drafts.contentForm.templateId) || false,
                    template_revision: template.revision,
                } : {}),
            });
            if (!this.isRequestCurrent(request)) return;
            if (selectionVersion !== (this.contentTemplateSelectionVersion || 0) ||
                fingerprint !== this.contentTemplateFingerprint()) {
                this.notify('El modelo cambió durante la generación, o cambió el contexto guardado. Se conservaron tus borradores; vuelve a generar cuando estés listo.', 'warning');
                return;
            }
            if (template) {
                const short = result.descriptionHtml || result.description;
                const long = result.technicalDescriptionHtml || result.technicalDescription;
                if (typeof short !== 'string' || typeof long !== 'string' ||
                    !this.descriptionPlainText(short) || !this.technicalDescriptionPlainText(long)) {
                    throw new Error('Incomplete description proposal');
                }
                // A fresh, read-only request also catches edits in another browser tab.
                const fresh = await this.refreshContentTemplateContext();
                if (!this.isRequestCurrent(request)) return;
                if (!fresh || selectionVersion !== (this.contentTemplateSelectionVersion || 0) ||
                    fingerprint !== this.contentTemplateFingerprint(fresh) ||
                    fingerprint !== this.contentTemplateFingerprint(result.contentTemplates)) {
                    this.notify('No se aplicó la propuesta: el modelo o el contexto guardado cambió o no pudo verificarse. Tus borradores se conservan.', 'warning');
                    return;
                }
            }
            const proposal = {
                ...request.drafts.contentForm,
                // Generation never renames a product or rolls back an edited name.
                // The backend name is saved context, not an editable name proposal.
                description: result.descriptionHtml || result.description || request.drafts.contentForm.description,
                technicalDescription: result.technicalDescriptionHtml || result.technicalDescription || request.drafts.contentForm.technicalDescription,
            };
            this.state.contentForm = this.mergeSavedDraft(this.state.contentForm, request.drafts.contentForm, proposal);
            this.syncContentDescriptionEditor(true);
            this.syncTechnicalDescriptionEditor(true);
            this.state.contentGenerationWarnings = (result.warnings || []).filter((message) => typeof message === 'string');
            this.notify("Propuesta comercial y técnica generada. Revisa el contenido y guarda explícitamente.");
        } catch (error) {
            if (!this.isRequestCurrent(request)) return;
            this.notify(this.errorMessage(error, "No se pudo generar el contenido."), "danger");
        } finally {
            if (this.isRequestCurrent(request)) this.state.contentBusy = false;
        }
    }

    async generateFaq() {
        if (this.detailBaseSaveBusy()) return;
        const request = this.beginRequest("faq", true);
        this.state.faqBusy = true;
        try {
            const result = await this.rpc("/bader_product_intelligence/generate_faq", {
                product_tmpl_id: request.productId,
                audience: this.state.contentForm.audience,
            });
            if (!this.isRequestCurrent(request)) return;
            if (result.semanticRevision) {
                const context = await this.rpc('/bader_product_intelligence/content_template_context', {
                    product_tmpl_id: request.productId, template_id: this.contentTemplateSelectionId(),
                });
                if (!this.isRequestCurrent(request)) return;
                if (context?.semanticRevision !== result.semanticRevision) {
                    this.notify('La clasificación guardada cambió. No se aplicaron las FAQs; tus borradores se conservan.', 'warning');
                    return;
                }
            }
            const faqs = (result.faqs || []).map((faq) => ({
                question: faq.question || "",
                answer: faq.answer || "",
            }));
            this.state.contentForm.faqs = this.mergeSavedDraft(this.state.contentForm.faqs, request.drafts.contentForm.faqs, faqs);
            this.notify("FAQs generadas con Nancy AI.");
        } catch (error) {
            if (!this.isRequestCurrent(request)) return;
            this.notify(this.errorMessage(error, "No se pudieron generar las FAQs."), "danger");
        } finally {
            if (this.isRequestCurrent(request)) this.state.faqBusy = false;
        }
    }

    async saveContentOnly() {
        if (this.detailBaseSaveBusy()) return;
        const request = this.beginRequest("content", true);
        this.state.contentBusy = true;
        try {
            await this.saveContentData();
            if (!this.isRequestCurrent(request)) return;
            await this.refreshDetail(request, { contentForm: true, productForm: ["name"] });
            if (!this.isRequestCurrent(request)) return;
            this.notify("Contenido guardado.");
        } catch (error) {
            if (!this.isRequestCurrent(request)) return;
            this.notify(this.errorMessage(error, "No se pudo guardar el contenido."), "danger");
        } finally {
            if (this.isRequestCurrent(request)) this.state.contentBusy = false;
        }
    }

    get taxonomyAxes() {
        return [
            {id:'niche',label:'Nicho',question:'¿Quién lo busca?',hint:'Los públicos a los que se dirige.',icon:'fa-users',number:'01'},
            {id:'commercial',label:'Aplicación comercial',question:'¿Qué producto es?',hint:'Su naturaleza y familia comercial.',icon:'fa-cube',number:'02'},
            {id:'technical',label:'Aplicación técnica',question:'¿En qué área se utiliza?',hint:'La especialidad o el contexto de uso.',icon:'fa-crosshairs',number:'03'},
            {id:'use',label:'Uso / Procedimiento',question:'¿Para qué lo necesita?',hint:'La tarea que el cliente quiere realizar.',icon:'fa-hand-pointer-o',number:'04'},
        ];
    }

    get taxonomyProposal() { return this.state.classificationJob?.resultPayload?.classificationProposal || null; }
    get taxonomyMapStatus() {
        if (this.taxonomyDirty) return 'Cambios en borrador';
        return this.state.detail?.classification?.reviewedAt ? 'Clasificación guardada' : 'Pendiente de revisar';
    }
    get taxonomySavedCount() { return this.state.detail?.classification?.termIds?.length || 0; }
    get taxonomyAddedCount() {
        const saved = new Set(this.state.detail?.classification?.termIds || []);
        return (this.state.categoryForm.classification?.termIds || []).filter(id => !saved.has(id)).length;
    }
    get taxonomyRemovedCount() {
        const selected = new Set(this.state.categoryForm.classification?.termIds || []);
        return (this.state.detail?.classification?.termIds || []).filter(id => !selected.has(id)).length;
    }
    taxonomyTermOrigin(id) {
        if ((this.state.detail?.classification?.termIds || []).includes(id)) return 'saved';
        return (this.state.taxonomyAiTermIds || []).includes(id) ? 'ai' : 'draft';
    }
    taxonomyTermOriginLabel(id) {
        return { saved: 'Guardada', ai: 'IA · borrador', draft: 'Borrador' }[this.taxonomyTermOrigin(id)];
    }
    taxonomyInspectTerm(term) { this.state.taxonomyTermDetail = this.state.taxonomyTermDetail === term.id ? null : term.id; }
    taxonomyInspectedTerm(axis) { return this.taxonomySelected(axis).find(term => term.id === this.state.taxonomyTermDetail) || null; }
    taxonomySynonymTerms(axis) { return this.taxonomySelected(axis).filter(term => term.aliases?.length); }
    taxonomyBranchIntents(axis) {
        const selected = new Set(this.taxonomySelected(axis).map(term => term.id));
        return (this.taxonomyProposal?.intentPhrases || []).filter(row => row.axis === axis &&
            typeof row.text === 'string' && row.text.trim() && Array.isArray(row.termIds) &&
            row.termIds.length && row.termIds.every(id => selected.has(id)));
    }
    get taxonomyNicheEvaluations() {
        const terms = this.state.detail?.classification?.terms || [];
        const labels = { suggested: 'Sugerido', not_suggested: 'No sugerido', insufficient_evidence: 'Falta evidencia' };
        return (this.taxonomyProposal?.nicheEvaluations || []).flatMap(row => {
            const term = terms.find(item => item.id === row.termId && item.axis === 'niche' && !item.universal);
            return term && labels[row.decision] ? [{ ...row, name: term.name, label: labels[row.decision] }] : [];
        });
    }
    get taxonomySavedNiches() {
        return (this.state.detail?.semanticContext?.axes?.niche || []).map(term => term.name).join(' · ');
    }
    get taxonomySavedSemanticCount() {
        return this.taxonomyAxes.reduce((count, axis) => count + (this.state.detail?.semanticContext?.axes?.[axis.id]?.length || 0), 0);
    }
    syncTaxonomyFocus() {
        if (!this.taxonomyFocusSelector) return;
        const element = this.taxonomyMapRef?.el?.querySelector(this.taxonomyFocusSelector);
        this.taxonomyFocusSelector = null;
        if (element) element.focus();
    }

    taxonomyNormalize(value) { return String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase().replace(/\s+/g,' ').trim(); }
    taxonomyOptions(axis) {
        const query=this.taxonomyNormalize(this.state.taxonomyQuery);
        return (this.state.detail?.classification?.terms || []).filter(t=>t.axis===axis && (!query || this.taxonomyNormalize([t.name,...(t.aliases || [])].join(' ')).includes(query)));
    }
    taxonomySelected(axis) {
        const ids=this.state.categoryForm.classification?.termIds || [];
        return (this.state.detail?.classification?.terms || []).filter(t=>t.axis===axis && !t.universal && ids.includes(t.id));
    }
    taxonomyAvailable(axis) { const ids=this.state.categoryForm.classification?.termIds || [];return this.taxonomyOptions(axis).filter(t=>!t.universal && !ids.includes(t.id)); }
    get taxonomyUnavailableCount() {
        const approved=new Set((this.state.detail?.classification?.terms || []).map(t=>t.id));
        return (this.state.categoryForm.classification?.termIds || []).filter(id=>!approved.has(id)).length;
    }
    taxonomyClearUnavailable() {
        const approved=new Set((this.state.detail?.classification?.terms || []).map(t=>t.id)),form=this.state.categoryForm.classification;
        form.termIds=form.termIds.filter(id=>approved.has(id));form.excludedTermIds=(form.excludedTermIds || []).filter(id=>approved.has(id));
    }
    get taxonomySelectedCount() { return this.state.categoryForm.classification?.termIds?.length || 0; }
    get taxonomyDirty() {
        const form=this.state.categoryForm.classification, saved=this.state.detail?.classification;
        const key=ids=>[...(ids || [])].sort((a,b)=>a-b).join(',');
        return !!form && !!saved && (key(form.termIds)!==key(saved.termIds) || key(form.excludedTermIds)!==key(saved.excludedTermIds));
    }
    get taxonomyJobActive() { return !!this.state.taxonomyAnalyzing || ['pending','running'].includes(this.state.classificationJob?.state); }
    get taxonomyAnalysisLabel() { return this.state.taxonomyAnalyzing ? 'Analizando producto…' : this.taxonomyJobActive ? 'Consultar análisis' : 'Analizar producto'; }
    onTaxonomyPickerKeydown(ev) {
        if (ev.key !== 'Escape') return;
        ev.preventDefault(); ev.stopPropagation();
        this.taxonomyFocusSelector = `[data-taxonomy-add="${this.state.taxonomyPicker}"]`;
        this.state.taxonomyPicker = '';
    }
    taxonomyOpenPicker(axis) {
        this.state.taxonomyPicker=this.state.taxonomyPicker===axis ? '' : axis;this.state.taxonomyQuery='';
        this.taxonomyFocusSelector = this.state.taxonomyPicker ? `#bpi-tax-search-${axis}` : null;
    }
    toggleTaxonomyTerm(id) {
        const form=this.state.categoryForm.classification;if(!form)return;
        const removing=form.termIds.includes(id), excluded=new Set(form.excludedTermIds || []);
        if(removing){form.termIds=form.termIds.filter(x=>x!==id);excluded.add(id);}
        else {form.termIds=[...form.termIds,id];excluded.delete(id);}
        this.state.taxonomyAiTermIds = (this.state.taxonomyAiTermIds || []).filter(termId => termId !== id);
        if (removing && this.state.taxonomyTermDetail === id) this.state.taxonomyTermDetail = null;
        if(excluded.size || form.excludedTermIds)form.excludedTermIds=[...excluded];
    }
    taxonomyAddTerm(id) { if(!this.state.categoryForm.classification.termIds.includes(id))this.toggleTaxonomyTerm(id);this.state.taxonomyQuery=''; }
    async toggleTaxonomyFilter(id) {
        const ids=this.state.taxonomyFilters || [];this.state.taxonomyFilters=ids.includes(id)?ids.filter(x=>x!==id):[...ids,id];
        return this.loadDashboard({page:1},{showSpinner:false});
    }
    async refreshTaxonomyVocabulary() {
        const request=this.beginRequest('taxonomyVocabulary');
        try {
            const current=await this.rpc('/bader_product_intelligence/classification/context',{product_tmpl_id:request.productId});
            if(!this.isRequestCurrent(request))return;
            this.state.detail.classification=current;
            this.state.categoryForm.classification.vocabularyRevision=current.vocabularyRevision;
            const available=new Set(current.terms.map(t=>t.id));
            this.state.categoryForm.classification.excludedTermIds=(this.state.categoryForm.classification.excludedTermIds || []).filter(id=>available.has(id));
            this.state.classificationJob=current.job || null;
        }catch(error){if(this.isRequestCurrent(request))this.notify(this.errorMessage(error,'No se pudo actualizar el vocabulario.'),'danger');}
    }
    async openTaxonomyLibrary() {
        const request=this.beginRequest('taxonomyLibrary');
        await this.action.doAction({type:'ir.actions.act_window',name:'Vocabulario de clasificación',res_model:'bpi.taxonomy.term',views:[[false,'list'],[false,'form']],target:'new'},
            {onClose:()=>{if(this.isRequestCurrent(request))return this.refreshTaxonomyVocabulary();}});
    }
    taxonomyCanCreate(axis) {
        const query=this.taxonomyNormalize(this.state.taxonomyQuery);
        return !!query && !this.taxonomyOptions(axis).some(t=>[t.name,...t.aliases].some(x=>this.taxonomyNormalize(x)===query));
    }
    taxonomyPending(axis) {
        const approved=new Set((this.state.detail?.classification?.terms || []).map(t=>t.id));
        return (this.taxonomyProposal?.newTerms || []).filter(t=>t.axis===axis && !approved.has(t.id) && !(this.state.taxonomyDismissedPending || []).includes(this.taxonomyPendingKey(t)));
    }
    taxonomyPendingKey(term) { return `${this.state.classificationJob?.id || ''}:${term.id}`; }
    taxonomyDismissPending(term) {
        this.state.taxonomyDismissedPending = [...new Set([...(this.state.taxonomyDismissedPending || []), this.taxonomyPendingKey(term)])];
        this.state.taxonomyNotice = 'Sugerencia ocultada de este mapa. No se vinculó ni se eliminó del vocabulario; puedes revisarla en los detalles.';
    }
    async taxonomyReviewTerm(term, existing = false) {
        const request=this.beginRequest('taxonomyLibrary');
        await this.action.doAction({type:'ir.actions.act_window',name:existing ? 'Editar término y sinónimos compartidos' : 'Revisar nueva palabra',res_model:'bpi.taxonomy.term',res_id:term.id,views:[[false,'form']],target:'new'},
            {onClose:()=>{if(this.isRequestCurrent(request))return this.refreshTaxonomyVocabulary();}});
    }
    async taxonomyCreateTerm(axis) {
        const name=(this.state.taxonomyQuery || '').trim();if(!name || name.length>100)return;
        const request=this.beginRequest('taxonomyLibrary');
        await this.action.doAction({type:'ir.actions.act_window',name:'Proponer una nueva etiqueta',res_model:'bpi.taxonomy.term',views:[[false,'form']],target:'new',
            context:{...(this.user?.context || {}),default_axis:axis,default_name:name,default_state:'draft'}},
            {onClose:async()=>{if(!this.isRequestCurrent(request))return;await this.refreshTaxonomyVocabulary();if(this.isRequestCurrent(request))this.state.taxonomyNotice='La palabra se vincula solo después de aprobarla y seleccionarla. Tus etiquetas no cambiaron.';}});
    }
    taxonomyEvidenceDraft() {
        return JSON.stringify(this.snapshotDraft({product:this.state.productForm,content:this.state.contentForm}));
    }
    async analyzeClassification() {
        if(this.state.taxonomyAnalyzing)return;
        const request=this.beginRequest('classificationJob');
        request.evidenceDraft=this.taxonomyEvidenceDraft();
        this.state.taxonomyAnalyzing=true;this.state.taxonomyNotice='';
        try {
            const existing=this.state.classificationJob;
            const result=['pending','running'].includes(existing?.state)?{job:existing}:await this.rpc('/bader_product_intelligence/classification/analyze',{product_tmpl_id:request.productId});
            if(!this.isRequestCurrent(request))return;
            this.state.classificationJob=result.job;
            await this.pollClassification(result.job.id,request);
        }catch(error){if(this.isRequestCurrent(request)){this.state.taxonomyAnalyzing=false;this.notify(this.errorMessage(error,'No se pudo solicitar el análisis.'),'danger');}}
    }
    async pollClassification(jobId, request=this.beginRequest('classificationJob')) {
        try {
            const result=await this.rpc('/bader_product_intelligence/ai_job/status',{job_id:jobId});
            if(!this.isRequestCurrent(request))return;
            this.state.classificationJob=result.job;
            if(['pending','running'].includes(result.job.state)) {
                setTimeout(()=>{if(this.isRequestCurrent(request))this.pollClassification(jobId,request);},2500);
            }else {
                this.state.taxonomyAnalyzing=false;
                if(result.job.state==='done' && request.evidenceDraft!==undefined)await this.applyClassificationProposal(false,request);
            }
        }catch(error){if(this.isRequestCurrent(request)){this.state.taxonomyAnalyzing=false;this.notify(this.errorMessage(error,'No se pudo consultar el análisis. Pulsa Consultar análisis para continuar.'),'danger');}}
    }
    async applyClassificationProposal(legacy=false, analysisRequest=null) {
        const proposal=legacy?null:this.state.classificationJob?.resultPayload?.classificationProposal;
        if(!legacy && !proposal)return;
        if(analysisRequest && !this.isRequestCurrent(analysisRequest))return;
        if(analysisRequest && analysisRequest.evidenceDraft!==this.taxonomyEvidenceDraft()) {
            this.state.taxonomyNotice='Cambiaste datos o contenido durante el análisis. Conservamos tus cambios; revisa el resultado en los detalles.';return;
        }
        const request=this.beginRequest('classificationApply');
        try {
            const current=await this.rpc('/bader_product_intelligence/classification/context',{product_tmpl_id:request.productId});
            if(!this.isRequestCurrent(request) || (analysisRequest && (!this.isRequestCurrent(analysisRequest) || analysisRequest.evidenceDraft!==this.taxonomyEvidenceDraft())))return;
            const draft=this.state.categoryForm.classification;
            if(!legacy && (proposal.sourceRevision!==current.sourceRevision || proposal.vocabularyRevision!==current.vocabularyRevision || proposal.revision!==current.revision)) {
                this.state.taxonomyNotice='Los datos o el vocabulario cambiaron. El análisis anterior no se aplicó; tus etiquetas se conservan.';return;
            }
            if(draft.revision!==current.revision){this.notify('La clasificación guardada cambió. Recarga antes de aplicar.','warning');return;}
            const excluded=new Set(draft.excludedTermIds || []),allowed=new Set(current.terms.filter(t=>!t.universal).map(t=>t.id));
            const incoming=(legacy?current.legacyTermIds:proposal.termIds).filter(id=>allowed.has(id) && !excluded.has(id));
            if (!legacy) {
                // Only genuinely new AI additions get provenance. Manual choices
                // and historical proposals are never retroactively labelled AI.
                const additions = incoming.filter(id => !draft.termIds.includes(id));
                this.state.taxonomyAiTermIds = [...new Set([...(this.state.taxonomyAiTermIds || []), ...additions])];
            }
            this.state.detail.classification=current;
            this.state.categoryForm.classification={...draft,vocabularyRevision:current.vocabularyRevision,termIds:[...new Set([...draft.termIds,...incoming])]};
            this.state.taxonomyNotice='Etiquetas añadidas al borrador. Conservamos tus selecciones y exclusiones. Revisa y guarda cuando estés listo.';
        }catch(error){if(this.isRequestCurrent(request))this.notify(this.errorMessage(error,'No se pudo revisar el resultado.'),'danger');}
    }

    async reclassifyCategory() {
        if (this.detailBaseSaveBusy()) return;
        const request = this.beginRequest("category", true);
        this.state.categoryBusy = true;
        try {
            const result = await this.rpc("/bader_product_intelligence/reclassify_category", {
                product_tmpl_id: request.productId,
            });
            if (!this.isRequestCurrent(request)) return;
            this.applyDetailUpdate(result, request, { categoryForm: true, productForm: ["categoryId"] });
            this.notify("Categoria reclasificada con Nancy AI.");
        } catch (error) {
            if (!this.isRequestCurrent(request)) return;
            this.notify(this.errorMessage(error, "No se pudo reclasificar el producto."), "danger");
        } finally {
            if (this.isRequestCurrent(request)) this.state.categoryBusy = false;
        }
    }

    async saveCategoryOnly() {
        if (this.detailBaseSaveBusy()) return;
        const request = this.beginRequest("category", true);
        this.state.categoryBusy = true;
        try {
            await this.saveCategoryData();
            if (!this.isRequestCurrent(request)) return;
            await this.refreshDetail(request, { categoryForm: true, productForm: ["categoryId"] });
            if (!this.isRequestCurrent(request)) return;
            this.notify("Categorizacion guardada.");
        } catch (error) {
            if (!this.isRequestCurrent(request)) return;
            this.notify(this.errorMessage(error, "No se pudo guardar la categorizacion."), "danger");
        } finally {
            if (this.isRequestCurrent(request)) this.state.categoryBusy = false;
        }
    }

    toggleReference(token) {
        if (this.state.imageForm.selectedReferences.includes(token)) {
            this.state.imageForm.selectedReferences = this.state.imageForm.selectedReferences.filter((item) => item !== token);
        } else {
            this.state.imageForm.selectedReferences = [...this.state.imageForm.selectedReferences, token];
        }
    }

    selectGalleryImage(url) {
        this.state.imageForm.selectedGalleryUrl = url;
    }

    async generateImage(usePro = false) {
        if (!this.state.imageForm.prompt.trim()) {
            this.notify("Escribe un prompt para generar la imagen.", "warning");
            return;
        }
        const request = this.beginRequest("image", true);
        this.state.imageBusy = true;
        try {
            const payload = {
                product_tmpl_id: request.productId,
                prompt: this.state.imageForm.prompt,
                reference_tokens: [...this.state.imageForm.selectedReferences],
                style: this.state.imageForm.style,
                use_pro: true,
            };
            if (this.state.imageForm.uploadedRefUrl) {
                payload.uploaded_ref = this.state.imageForm.uploadedRefUrl;
            }
            const result = await this.rpc("/bader_product_intelligence/generate_image", payload);
            if (!this.isRequestCurrent(request)) return;
            this.state.imageForm.generatedPreviewUrl = result.previewUrl || "";
            this.notify("Preview generado con Nancy AI.");
        } catch (error) {
            if (!this.isRequestCurrent(request)) return;
            this.notify(this.errorMessage(error, "No se pudo generar la imagen."), "danger");
        } finally {
            if (this.isRequestCurrent(request)) this.state.imageBusy = false;
        }
    }

    async approveImage() {
        if (!this.state.imageForm.generatedPreviewUrl) {
            return;
        }
        const request = this.beginRequest("image", true);
        this.state.imageBusy = true;
        try {
            await this.rpc("/bader_product_intelligence/approve_image", {
                product_tmpl_id: request.productId,
                image_data_url: this.state.imageForm.generatedPreviewUrl,
                prompt: this.state.imageForm.prompt,
            });
            if (!this.isRequestCurrent(request)) return;
            this.acknowledgeImagePreview(request.drafts.imageForm.generatedPreviewUrl);
            await this.refreshDetail(request, {});
            if (!this.isRequestCurrent(request)) return;
            this.notify("Imagen aprobada y guardada.");
            return true;
        } catch (error) {
            if (!this.isRequestCurrent(request)) return;
            this.notify(this.errorMessage(error, "No se pudo guardar la imagen."), "danger");
        } finally {
            if (this.isRequestCurrent(request)) this.state.imageBusy = false;
        }
    }

    openImageModal() {
        this.beginRequest("image");
        this.beginRequest("imageModal");
        this.beginRequest("imageUpload");
        this.state.imageBusy = false;
        const product = this.currentProduct();
        this.state.playground.messages = [
            { role: "ai", text: `¡Hola! Soy Nancy AI. Estoy lista para editar las imágenes de "${product ? product.name : 'tu producto'}". Selecciona imágenes de referencia abajo, adjunta un logo si quieres, y describe lo que necesitas.` },
        ];
        this.state.playground.canvasUrl = (product && product.mainImageUrl) || "";
        this.state.playground.inputText = "";
        this.state.imageForm.selectedReferences = [];
        this.state.imageForm.uploadedRefUrl = "";
        this.state.imageForm.uploadedRefName = "";
        this.state.showImageModal = true;
    }

    closeImageModal() {
        this.beginRequest("image");
        this.beginRequest("imageModal");
        this.beginRequest("imageUpload");
        this.state.imageBusy = false;
        this.state.showImageModal = false;
    }

    triggerFileUpload() {
        const input = this.fileUploadInputRef.el;
        if (input) {
            input.click();
        }
    }

    handleFileUpload(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file) return;
        if (!ALLOWED_IMAGE_UPLOAD_TYPES.has(file.type)) {
            this.notify("Solo se permiten imágenes PNG, JPEG o WebP.", "warning");
            ev.target.value = "";
            return;
        }
        if (file.size > MAX_IMAGE_UPLOAD_BYTES) {
            this.notify("La imagen supera el tamaño máximo permitido de 10 MiB.", "warning");
            ev.target.value = "";
            return;
        }
        const request = this.beginRequest("imageUpload");
        const reader = new FileReader();
        reader.onload = (e) => {
            if (!this.isRequestCurrent(request)) return;
            this.state.imageForm.uploadedRefUrl = e.target.result;
            this.state.imageForm.uploadedRefName = file.name;
        };
        reader.readAsDataURL(file);
    }

    removeUploadedRef() {
        this.beginRequest("imageUpload");
        this.state.imageForm.uploadedRefUrl = "";
        this.state.imageForm.uploadedRefName = "";
    }

    async approveImageAndClose() {
        const request = this.beginRequest("imageModal");
        const approved = await this.approveImage();
        if (approved && this.isRequestCurrent(request)) this.state.showImageModal = false;
    }

    selectCanvasImage(url) {
        this.state.playground.canvasUrl = url;
    }

    togglePlaygroundRef(image) {
        const token = image.token || "";
        if (!token) return;
        if (this.state.imageForm.selectedReferences.includes(token)) {
            this.state.imageForm.selectedReferences = this.state.imageForm.selectedReferences.filter((t) => t !== token);
        } else {
            this.state.imageForm.selectedReferences = [...this.state.imageForm.selectedReferences, token];
        }
    }

    onPlaygroundKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.sendPlaygroundMessage();
        }
    }

    scrollPlayground() {
        const el = this.playgroundMessagesRef.el;
        if (el) {
            requestAnimationFrame(() => { if (!this.destroyed) el.scrollTop = el.scrollHeight; });
        }
    }

    async sendPlaygroundMessage() {
        const text = (this.state.playground.inputText || "").trim();
        if (!text) return;

        const attachments = [];
        if (this.state.imageForm.uploadedRefUrl) {
            attachments.push({ url: this.state.imageForm.uploadedRefUrl, name: this.state.imageForm.uploadedRefName });
        }

        this.state.playground.messages = [
            ...this.state.playground.messages,
            { role: "user", text, attachments },
        ];
        this.state.playground.inputText = "";
        this.scrollPlayground();

        const loadingIdx = this.state.playground.messages.length;
        this.state.playground.messages = [
            ...this.state.playground.messages,
            { role: "ai", text: "", loading: true },
        ];
        this.scrollPlayground();

        const request = this.beginRequest("image", true);
        this.state.imageBusy = true;
        try {
            const payload = {
                product_tmpl_id: request.productId,
                prompt: text,
                reference_tokens: [...this.state.imageForm.selectedReferences],
                style: this.state.imageForm.style || "professional",
                use_pro: true,
            };
            if (this.state.imageForm.uploadedRefUrl) {
                payload.uploaded_ref = this.state.imageForm.uploadedRefUrl;
            }
            const result = await this.rpc("/bader_product_intelligence/generate_image", payload);
            if (!this.isRequestCurrent(request)) return;
            const previewUrl = result.previewUrl || "";

            this.state.playground.messages = this.state.playground.messages.map((m, i) =>
                i === loadingIdx ? { role: "ai", text: "Imagen generada. Haz clic en la imagen para verla en el canvas.", imageUrl: previewUrl } : m
            );
            this.state.playground.canvasUrl = previewUrl;
            this.state.imageForm.generatedPreviewUrl = previewUrl;
            this.state.imageForm.uploadedRefUrl = "";
            this.state.imageForm.uploadedRefName = "";
        } catch (error) {
            if (!this.isRequestCurrent(request)) return;
            this.state.playground.messages = this.state.playground.messages.map((m, i) =>
                i === loadingIdx ? { role: "ai", text: this.errorMessage(error, "No se pudo generar la imagen. Intenta de nuevo.") } : m
            );
        } finally {
            if (this.isRequestCurrent(request)) this.state.imageBusy = false;
            if (this.isRequestCurrent(request)) this.scrollPlayground();
        }
    }

    async saveCanvasToGallery() {
        if (!this.state.playground.canvasUrl) return;
        const previewUrl = this.state.playground.canvasUrl;
        const request = this.beginRequest("image", true);
        this.state.imageBusy = true;
        try {
            await this.rpc("/bader_product_intelligence/approve_image", {
                product_tmpl_id: request.productId,
                image_data_url: this.state.playground.canvasUrl,
                prompt: "Nancy AI Studio",
            });
            if (!this.isRequestCurrent(request)) return;
            this.acknowledgeImagePreview(previewUrl);
            await this.refreshDetail(request, {});
            if (!this.isRequestCurrent(request)) return;
            this.notify("Imagen guardada en la galería.");
        } catch (error) {
            if (!this.isRequestCurrent(request)) return;
            this.notify(this.errorMessage(error, "No se pudo guardar la imagen."), "danger");
        } finally {
            if (this.isRequestCurrent(request)) this.state.imageBusy = false;
        }
    }

    async generateFromForm() {
        const prompt = (this.state.imageForm.prompt || "").trim();
        if (!prompt) {
            this.notify("Escribe un prompt para generar la imagen.", "warning");
            return;
        }

        const attachments = [];
        if (this.state.imageForm.uploadedRefUrl) {
            attachments.push({ url: this.state.imageForm.uploadedRefUrl, name: this.state.imageForm.uploadedRefName });
        }

        this.state.playground.messages = [
            ...this.state.playground.messages,
            { role: "user", text: prompt, attachments },
        ];
        this.scrollPlayground();

        const loadingIdx = this.state.playground.messages.length;
        this.state.playground.messages = [
            ...this.state.playground.messages,
            { role: "ai", text: "", loading: true },
        ];
        this.scrollPlayground();

        const request = this.beginRequest("image", true);
        this.state.imageBusy = true;
        try {
            const payload = {
                product_tmpl_id: request.productId,
                prompt,
                reference_tokens: [...this.state.imageForm.selectedReferences],
                style: this.state.imageForm.style || "professional",
                use_pro: true,
            };
            if (this.state.imageForm.uploadedRefUrl) {
                payload.uploaded_ref = this.state.imageForm.uploadedRefUrl;
            }
            const result = await this.rpc("/bader_product_intelligence/generate_image", payload);
            if (!this.isRequestCurrent(request)) return;
            const previewUrl = result.previewUrl || "";

            this.state.playground.messages = this.state.playground.messages.map((m, i) =>
                i === loadingIdx ? { role: "ai", text: "✅ Imagen generada con éxito.", imageUrl: previewUrl } : m
            );
            this.state.imageForm.generatedPreviewUrl = previewUrl;
        } catch (error) {
            if (!this.isRequestCurrent(request)) return;
            this.state.playground.messages = this.state.playground.messages.map((m, i) =>
                i === loadingIdx ? { role: "ai", text: this.errorMessage(error, "❌ No se pudo generar la imagen. Intenta de nuevo.") } : m
            );
        } finally {
            if (this.isRequestCurrent(request)) this.state.imageBusy = false;
            if (this.isRequestCurrent(request)) this.scrollPlayground();
        }
    }

    async saveGeneratedImage(imageUrl) {
        if (!imageUrl) return;
        const request = this.beginRequest("image", true);
        this.state.imageBusy = true;
        try {
            await this.rpc("/bader_product_intelligence/approve_image", {
                product_tmpl_id: request.productId,
                image_data_url: imageUrl,
                prompt: this.state.imageForm.prompt || "Nancy AI Studio",
            });
            if (!this.isRequestCurrent(request)) return;
            this.acknowledgeImagePreview(imageUrl);
            await this.refreshDetail(request, {});
            if (!this.isRequestCurrent(request)) return;
            this.notify("Imagen guardada en la galería del producto.");
        } catch (error) {
            if (!this.isRequestCurrent(request)) return;
            this.notify(this.errorMessage(error, "No se pudo guardar la imagen."), "danger");
        } finally {
            if (this.isRequestCurrent(request)) this.state.imageBusy = false;
        }
    }

    async addImageUrl() {
        if (!this.state.imageForm.addImageUrl.trim()) {
            return;
        }
        const request = this.beginRequest("image", true);
        this.state.imageBusy = true;
        try {
            await this.rpc("/bader_product_intelligence/add_image_url", {
                product_tmpl_id: request.productId,
                image_url: this.state.imageForm.addImageUrl,
            });
            if (!this.isRequestCurrent(request)) return;
            await this.refreshDetail(request, {});
            if (!this.isRequestCurrent(request)) return;
            this.notify("Imagen agregada.");
        } catch (error) {
            if (!this.isRequestCurrent(request)) return;
            this.notify(this.errorMessage(error, "No se pudo agregar la imagen."), "danger");
        } finally {
            if (this.isRequestCurrent(request)) this.state.imageBusy = false;
        }
    }

    async deleteImage(image) {
        if (!canDeleteGalleryImage(image)) {
            return;
        }
        const request = this.beginRequest("image", true);
        this.state.imageBusy = true;
        try {
            await this.rpc("/bader_product_intelligence/delete_image", {
                product_tmpl_id: request.productId,
                image_token: image.referenceToken,
            });
            if (!this.isRequestCurrent(request)) return;
            await this.refreshDetail(request, {});
            if (!this.isRequestCurrent(request)) return;
            this.notify("Imagen eliminada.");
        } catch (error) {
            if (!this.isRequestCurrent(request)) return;
            this.notify(this.errorMessage(error, "No se pudo eliminar la imagen."), "danger");
        } finally {
            if (this.isRequestCurrent(request)) this.state.imageBusy = false;
        }
    }

    async saveVideo() {
        const request = this.beginRequest("image", true);
        this.state.imageBusy = true;
        try {
            await this.rpc("/bader_product_intelligence/save_video", {
                product_tmpl_id: request.productId,
                video_url: this.state.imageForm.videoUrl,
            });
            if (!this.isRequestCurrent(request)) return;
            await this.refreshDetail(request, {});
            if (!this.isRequestCurrent(request)) return;
            this.notify("Video guardado.");
        } catch (error) {
            if (!this.isRequestCurrent(request)) return;
            this.notify(this.errorMessage(error, "No se pudo guardar el video."), "danger");
        } finally {
            if (this.isRequestCurrent(request)) this.state.imageBusy = false;
        }
    }

    async discoverCompetitors() {
        if (this.state.competitorBusy) return;
        const request = this.beginRequest("competitor", true);
        this.state.competitorBusy = true;
        try {
            const result = await this.rpc("/bader_product_intelligence/discover_competitors", {
                product_tmpl_id: request.productId,
                limit: 10,
            });
            if (!this.isRequestCurrent(request)) return;
            this.state.competitorForm.discoveredCompetitors = result.competitors || [];
            this.state.competitorForm.discoveryQuery = result.query || "";
            this.notify(`Se encontraron ${result.totalFound || 0} competidores.`);
        } catch (error) {
            if (!this.isRequestCurrent(request)) return;
            this.notify(this.errorMessage(error, "No se pudieron descubrir competidores."), "danger");
        } finally {
            if (this.isRequestCurrent(request)) this.state.competitorBusy = false;
        }
    }

    async addCompetitor(name = "", url = "", description = "") {
        if (this.state.competitorBusy) return;
        const competitorName = name || this.state.competitorForm.competitorName;
        const competitorUrl = url || this.state.competitorForm.competitorUrl;
        if (!competitorUrl) {
            this.notify("Ingresa una URL de competidor.", "warning");
            return;
        }
        const request = this.beginRequest("competitor", true);
        this.state.competitorBusy = true;
        try {
            const result = await this.rpc("/bader_product_intelligence/add_competitor", {
                product_tmpl_id: request.productId,
                competitor_name: competitorName,
                competitor_url: competitorUrl,
                competitor_description: description || "",
            });
            if (!this.isRequestCurrent(request)) return;
            if (!url) {
                this.state.competitorForm.competitorName = this.mergeSavedDraft(this.state.competitorForm.competitorName, request.drafts.competitorForm.competitorName, "");
                this.state.competitorForm.competitorUrl = this.mergeSavedDraft(this.state.competitorForm.competitorUrl, request.drafts.competitorForm.competitorUrl, "");
            }
            await this.refreshDetail(request, {});
            if (!this.isRequestCurrent(request)) return;
            this.notifyCompetitorCollection(result?.competitor, "Competidor agregado.");
        } catch (error) {
            if (!this.isRequestCurrent(request)) return;
            this.notify(this.errorMessage(error, "No se pudo agregar el competidor."), "danger");
        } finally {
            if (this.isRequestCurrent(request)) this.state.competitorBusy = false;
        }
    }

    async scrapeCompetitor(competitorId) {
        if (this.state.competitorBusy) return;
        const request = this.beginRequest("competitor", true);
        this.state.competitorBusy = true;
        try {
            const result = await this.rpc("/bader_product_intelligence/scrape_competitor", {
                product_tmpl_id: request.productId,
                competitor_id: competitorId,
            });
            if (!this.isRequestCurrent(request)) return;
            await this.refreshDetail(request, {});
            if (!this.isRequestCurrent(request)) return;
            this.notifyCompetitorCollection(result?.competitor, "Consulta del competidor completada.");
        } catch (error) {
            if (!this.isRequestCurrent(request)) return;
            this.notify(this.errorMessage(error, "No se pudo scrapear el competidor."), "danger");
        } finally {
            if (this.isRequestCurrent(request)) this.state.competitorBusy = false;
        }
    }

    async analyzeCompetitor(competitorId) {
        if (this.state.competitorBusy) return;
        const request = this.beginRequest("competitor", true);
        this.state.competitorBusy = true;
        try {
            await this.rpc("/bader_product_intelligence/analyze_competitor", {
                product_tmpl_id: request.productId,
                competitor_id: competitorId,
            });
            if (!this.isRequestCurrent(request)) return;
            await this.refreshDetail(request, {});
            if (!this.isRequestCurrent(request)) return;
            this.notify("Analisis competitivo actualizado.");
        } catch (error) {
            if (!this.isRequestCurrent(request)) return;
            this.notify(this.errorMessage(error, "No se pudo analizar el competidor."), "danger");
        } finally {
            if (this.isRequestCurrent(request)) this.state.competitorBusy = false;
        }
    }

    async deleteCompetitor(competitorId) {
        if (this.state.competitorBusy) return;
        const request = this.beginRequest("competitor", true);
        this.state.competitorBusy = true;
        try {
            await this.rpc("/bader_product_intelligence/delete_competitor", {
                product_tmpl_id: request.productId,
                competitor_id: competitorId,
            });
            if (!this.isRequestCurrent(request)) return;
            await this.refreshDetail(request, {});
            if (!this.isRequestCurrent(request)) return;
            this.notify("Competidor eliminado.");
        } catch (error) {
            if (!this.isRequestCurrent(request)) return;
            this.notify(this.errorMessage(error, "No se pudo eliminar el competidor."), "danger");
        } finally {
            if (this.isRequestCurrent(request)) this.state.competitorBusy = false;
        }
    }

    async generateStrategy() {
        const request = this.beginRequest("strategy", true);
        this.state.strategyBusy = true;
        try {
            await this.rpc("/bader_product_intelligence/generate_strategy", {
                product_tmpl_id: request.productId,
            });
            if (!this.isRequestCurrent(request)) return;
            await this.refreshDetail(request, {});
            if (!this.isRequestCurrent(request)) return;
            this.notify("Estrategia competitiva generada.");
        } catch (error) {
            if (!this.isRequestCurrent(request)) return;
            this.notify(this.errorMessage(error, "No se pudo generar la estrategia."), "danger");
        } finally {
            if (this.isRequestCurrent(request)) this.state.strategyBusy = false;
        }
    }

    async mutateCatalogFlag(productId, field, checked, event = null) {
        const currentRow = (this.state.dashboardRows || []).find((row) => String(row.id) === String(productId));
        const previous = currentRow ? !!currentRow[field] : !checked;
        if (this.catalogRowBusy(productId)) {
            if (event?.target) event.target.checked = previous;
            return;
        }
        this.state.catalogBusyRows = this.state.catalogBusyRows || {};
        this.state.catalogBusyRows[productId] = true;
        const request = this.beginRequest(`catalogFlag:${productId}:${field}`);
        try {
            await this.rpc("/bader_product_intelligence/update_product", {
                product_tmpl_id: productId, values: { [field]: !!checked },
            });
            if (!this.isRequestCurrent(request)) return;
            const updatedRow = (this.state.dashboardRows || []).find((row) => String(row.id) === String(productId));
            if (updatedRow) updatedRow[field] = !!checked;
            await this.loadDashboard({}, { showSpinner: false });
        } catch (error) {
            if (!this.isRequestCurrent(request)) return;
            const row = (this.state.dashboardRows || []).find((item) => String(item.id) === String(productId));
            if (row) row[field] = previous;
            if (event?.target) event.target.checked = previous;
            this.notify(this.errorMessage(error, field === "isPublished"
                ? "No se pudo actualizar la publicación." : "No se pudo actualizar el destacado."), "danger");
        } finally {
            if (this.isRequestCurrent(request)) delete this.state.catalogBusyRows[productId];
        }
    }

    async toggleDashboardPublish(productId, checked, event = null) {
        return this.mutateCatalogFlag(productId, "isPublished", checked, event);
    }

    async toggleDashboardFeatured(productId, checked, event = null) {
        return this.mutateCatalogFlag(productId, "featured", checked, event);
    }

    quickAction(tabId) {
        return this.selectDetailSection(tabId);
    }

    priceMarkerStyle() {
        const range = this.competitorPriceRange();
        const price = this.productComparisonPrice();
        if (!range.max || range.max === range.min) {
            return "left: 50%;";
        }
        const ratio = ((price - range.min) / (range.max - range.min)) * 100;
        const clamped = Math.max(0, Math.min(100, ratio));
        return `left: ${clamped}%;`;
    }

    toggleCompetitorExpand(competitorId) {
        if (this.state.expandedCompetitorId === competitorId) {
            this.state.expandedCompetitorId = null;
        } else {
            this.state.expandedCompetitorId = competitorId;
        }
    }

    async sendChatMessage(text) {
        const msg = (text || this.state.chatInput || "").trim();
        if (!msg || this.state.chatBusy) {
            return;
        }
        if (msg.length > MAX_CHAT_MESSAGE_LENGTH) {
            this.notify("El mensaje supera el límite de 4000 caracteres.", "warning");
            return;
        }
        const requestProductId = this.state.productId;
        const requestSequence = this.chatRequestSequence = (this.chatRequestSequence || 0) + 1;
        this.state.chatMessages.push({ role: "user", content: msg });
        this.state.chatInput = "";
        this.state.chatBusy = true;
        try {
            const result = await this.rpc("/bader_product_intelligence/chat", {
                product_tmpl_id: this.state.productId,
                message: msg,
                session_id: this.state.chatSessionKey || false,
            });
            if (this.destroyed || requestSequence !== this.chatRequestSequence || String(requestProductId) !== String(this.state.productId)) {
                return;
            }
            this.state.chatMessages.push({ role: "assistant", content: result.response });
            this.state.chatSessionKey = result.sessionId || this.state.chatSessionKey;
        } catch (error) {
            if (this.destroyed || requestSequence !== this.chatRequestSequence || String(requestProductId) !== String(this.state.productId)) {
                return;
            }
            this.state.chatMessages.push({ role: "assistant", content: "Error: " + this.errorMessage(error, "No se pudo obtener respuesta.") });
        } finally {
            if (!this.destroyed && requestSequence === this.chatRequestSequence && String(requestProductId) === String(this.state.productId)) {
                this.state.chatBusy = false;
            }
        }
    }

    onChatKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.sendChatMessage();
        }
    }

    useChatQuickAction(action) {
        this.sendChatMessage(action);
    }

    detailScoreCards() {
        const seo = this.currentSeoData();
        const images = this.currentImages();
        const scores = [
            { label: "Score SEO", score: seo.seoScore || 0, tab: "seo" },
            { label: "Score GEO", score: seo.geoScore || 0, tab: "seo" },
            { label: "Competitividad", score: seo.competitivenessScore || 0, tab: "competitors" },
            { label: "Imagenes", score: Math.min(100, (images.length || 0) * 20), tab: "images" },
        ];
        return scores.map((s) => ({
            ...s,
            level: this._scoreLevel(s.score),
            color: this._scoreLevel(s.score),
        }));
    }
}

ProductIntelligenceAction.template = "bader_product_intelligence.ProductIntelligenceAction";

registry.category("actions").add("bader_product_intelligence.action", ProductIntelligenceAction);
