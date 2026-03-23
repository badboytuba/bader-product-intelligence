/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, onWillUnmount, onMounted, useState, useRef } from "@odoo/owl";

const DASHBOARD_PAGE_SIZE = 40;

const DETAIL_TABS = [
    { id: "overview", label: "Overview", icon: "fa-bar-chart" },
    { id: "datos", label: "Datos", icon: "fa-cog" },
    { id: "categorization", label: "Categorization", icon: "fa-sitemap" },
    { id: "content", label: "Content", icon: "fa-pencil" },
    { id: "images", label: "Images", icon: "fa-picture-o" },
    { id: "seo", label: "SEO", icon: "fa-search" },
    { id: "competitors", label: "Competidores", icon: "fa-bullseye" },
    { id: "analytics", label: "Analytics", icon: "fa-line-chart" },
    { id: "chat", label: "Agente IA", icon: "fa-comments" },
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
];

const SUBCATEGORY_OPTIONS = [
    { value: "adhesivos", label: "Adhesivos" },
    { value: "anestesia", label: "Anestesia" },
    { value: "blanqueamiento", label: "Blanqueamiento" },
    { value: "cementos", label: "Cementos" },
    { value: "composites", label: "Composites" },
    { value: "desechables", label: "Desechables" },
    { value: "esterilizacion", label: "Esterilizacion" },
    { value: "fresas", label: "Fresas" },
    { value: "impresion", label: "Impresion" },
    { value: "profilaxis", label: "Profilaxis" },
    { value: "restauracion", label: "Restauracion" },
    { value: "otro", label: "Otro" },
];

class ProductIntelligenceAction extends Component {
    setup() {
        this.rpc = useService("rpc");
        this.notification = useService("notification");
        this.action = useService("action");

        this.detailTabs = DETAIL_TABS;
        this.nicheOptions = NICHE_OPTIONS;
        this.typeOptions = TYPE_OPTIONS;
        this.subcategoryOptions = SUBCATEGORY_OPTIONS;
        this.chatQuickActions = CHAT_QUICK_ACTIONS;
        this.dashboardReloadTimer = null;

        this.state = useState({
            loading: true,
            error: "",
            viewMode: "dashboard",
            origin: "menu",
            productId: null,
            dashboardBusy: false,
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
            saveBusy: false,
            exchangeRateBusy: false,
            seoBusy: false,
            contentBusy: false,
            faqBusy: false,
            imageBusy: false,
            competitorBusy: false,
            strategyBusy: false,
            categoryBusy: false,
            chatBusy: false,
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
            playground: {
                messages: [],
                canvasUrl: "",
                inputText: "",
            },
        });

        this.fileUploadInputRef = useRef("fileUploadInput");
        this.playgroundMessagesRef = useRef("playgroundMessages");

        onWillStart(async () => {
            const productId = this.resolveProductId();
            this.state.origin = this.resolveOrigin();
            if (productId) {
                this.state.productId = productId;
                await this.loadDetail(productId);
            } else {
                await this.loadDashboard();
            }
        });

        onMounted(() => {
            this._setupScrollListener();
            this._setupKeyboardShortcuts();
        });

        onWillUnmount(() => {
            this.clearDashboardReloadTimer();
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
        setTimeout(() => {
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
                    this.saveAll();
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
            tone: "profesional",
            audience: "clinicas",
            name: "",
            description: "",
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
            categoryId: "",
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

    resolveProductId() {
        const params = this.props.action.params || {};
        const context = this.props.action.context || {};
        return params.product_tmpl_id || context.active_id || null;
    }

    resolveOrigin() {
        const params = this.props.action.params || {};
        return params.origin || "menu";
    }

    clearDashboardReloadTimer() {
        if (this.dashboardReloadTimer) {
            clearTimeout(this.dashboardReloadTimer);
            this.dashboardReloadTimer = null;
        }
    }

    scheduleDashboardReload() {
        this.clearDashboardReloadTimer();
        this.dashboardReloadTimer = setTimeout(() => {
            this.loadDashboard({ page: 1 }, { showSpinner: false });
        }, 300);
    }

    notify(message, type = "success") {
        this.notification.add(message, { type });
    }

    errorMessage(error, fallback) {
        return (error && (error.message || error.data && error.data.message)) || fallback;
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
        };
    }

    applyDashboardPayload(data, params) {
        this.state.dashboardRows = data.products || [];
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
        this.state.viewMode = "dashboard";
    }

    async loadDashboard(overrides = {}, options = {}) {
        const params = this.resolveDashboardParams(overrides);
        const showSpinner = options.showSpinner !== false;
        if (showSpinner) {
            this.state.loading = true;
        } else {
            this.state.dashboardBusy = true;
        }
        this.state.error = "";
        try {
            const data = await this.rpc("/bader_product_intelligence/dashboard", params);
            this.applyDashboardPayload(data, params);
        } catch (error) {
            this.state.error = this.errorMessage(error, "No se pudo cargar Producto Intelligence.");
        } finally {
            this.state.loading = false;
            this.state.dashboardBusy = false;
        }
    }

    applyDetailPayload(data) {
        const product = data.product || {};
        const seoData = data.seoData || {};

        this.state.detail = data;
        this.state.productForm = {
            name: product.name || "",
            sku: product.sku || "",
            slug: product.slug || "",
            brand: product.brand || "Bader",
            categoryId: product.categoryId ? String(product.categoryId) : "",
            priceUsd: this.toInput(product.priceUsd),
            previousPriceUsd: product.previousPriceUsd ? this.toInput(product.previousPriceUsd) : "",
            costUsd: product.costUsd ? this.toInput(product.costUsd) : "",
            qtyAvailable: this.toInput(product.qtyAvailable),
            featured: !!product.featured,
            isPublished: !!product.isPublished,
        };
        this.state.contentForm = {
            tone: seoData.aiTone || "profesional",
            audience: seoData.aiTargetAudience || "clinicas",
            name: product.name || "",
            description: seoData.aiGeneratedDescription || product.description || "",
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
            geoDescription: seoData.geoDescription || "",
            geoFeatures: (seoData.geoFeatures || []).join(", "),
        };
        this.state.categoryForm = {
            manualMode: !!product.intelligentCategoryManual,
            niches: product.intelligentNiches || [],
            type: product.intelligentType || "",
            subcategory: product.intelligentSubcategory || "",
            categoryId: product.categoryId ? String(product.categoryId) : "",
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
        this.state.exchangeRate = data.exchangeRate || this.state.exchangeRate || 1650;
        this.state.exchangeRateInput = String(this.state.exchangeRate || 1650);
    }

    async loadDetail(productId = null) {
        const currentId = productId || this.state.productId;
        if (!currentId) {
            await this.loadDashboard();
            return;
        }
        this.state.loading = true;
        this.state.error = "";
        try {
            const data = await this.rpc("/bader_product_intelligence/data", {
                product_tmpl_id: currentId,
            });
            this.state.productId = currentId;
            this.state.viewMode = "detail";
            this.applyDetailPayload(data);
        } catch (error) {
            this.state.error = this.errorMessage(error, "No se pudo cargar el detalle del producto.");
        } finally {
            this.state.loading = false;
        }
    }

    currentProduct() {
        return (this.state.detail && this.state.detail.product) || {};
    }

    currentSeoData() {
        return (this.state.detail && this.state.detail.seoData) || {};
    }

    currentImages() {
        return (this.state.detail && this.state.detail.images) || [];
    }

    currentCompetitors() {
        return (this.state.detail && this.state.detail.competitors) || [];
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

    toInput(value) {
        if (value === undefined || value === null || value === false) {
            return "";
        }
        return String(value);
    }

    templateString(value) {
        return this.toInput(value);
    }

    marginBenefitLabel() {
        const product = this.currentProduct();
        const benefit = (this.parseNumber(product.priceUsd) - this.parseNumber(product.costUsd));
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

    formatNumber(value) {
        return new Intl.NumberFormat("es-AR").format(Number(value || 0));
    }

    formatPercent(value) {
        return `${Number(value || 0).toFixed(1)}%`;
    }

    contentWordCount() {
        const text = (this.state.contentForm.description || "").trim();
        if (!text) {
            return 0;
        }
        return text.split(/\s+/).filter(Boolean).length;
    }

    contentWordCountLabel() {
        return `${this.contentWordCount()} palabras - Optimizado para SEO y motores de IA (GEO)`;
    }

    filteredDashboardProducts() {
        return this.state.dashboardRows || [];
    }

    onDashboardSearchInput(ev) {
        this.state.searchTerm = ev.target.value || "";
        this.scheduleDashboardReload();
    }

    async changeDashboardTab(tab) {
        if (tab === this.state.dashboardTab && !this.state.error) {
            return;
        }
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
        try {
            const value = this.parseNumber(this.state.exchangeRateInput) || 1650;
            const result = await this.rpc("/bader_product_intelligence/update_exchange_rate", {
                exchange_rate: value,
            });
            this.state.exchangeRate = result.exchangeRate || value;
            await this.loadDashboard({}, { showSpinner: false });
            this.notify("Tipo de cambio actualizado.");
        } catch (error) {
            this.notify(this.errorMessage(error, "No se pudo actualizar el tipo de cambio."), "danger");
        } finally {
            this.state.exchangeRateBusy = false;
        }
    }

    async openDetail(productId) {
        this.state.origin = "dashboard";
        this.state.activeTab = "overview";
        await this.loadDetail(productId);
    }

    async goBack() {
        if (this.state.origin === "product_form") {
            this.openProductForm();
            return;
        }
        await this.loadDashboard({}, { showSpinner: true });
    }

    openProductForm() {
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

    detailMargin() {
        const product = this.currentProduct();
        const price = Number(product.priceUsd || 0);
        const cost = Number(product.costUsd || 0);
        if (!price || !cost) {
            return 0;
        }
        return ((price - cost) / price) * 100;
    }

    averageCompetitorPrice() {
        const competitors = this.currentCompetitors().filter((item) => item.competitorPrice);
        if (!competitors.length) {
            return 0;
        }
        const total = competitors.reduce((sum, item) => sum + Number(item.competitorPrice || 0), 0);
        return total / competitors.length;
    }

    priceVsCompetition() {
        const average = this.averageCompetitorPrice();
        const product = this.currentProduct();
        if (!average || !product.priceUsd) {
            return null;
        }
        return ((Number(product.priceUsd) - average) / average) * 100;
    }

    competitorPriceRange() {
        const prices = this.currentCompetitors()
            .filter((item) => item.competitorPrice)
            .map((item) => Number(item.competitorPrice || 0))
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
        this.state.activeTab = tabId;
        if (tabId === "chat") {
            this.loadChatHistory();
        }
    }

    updateProductField(field, value) {
        this.state.productForm[field] = value;
        if (field === "name" && !this.state.productForm.slug) {
            this.state.productForm.slug = this.generateSlug(value);
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
    }

    updateSeoField(field, value) {
        this.state.seoForm[field] = value;
        if (field === "slug") {
            this.state.productForm.slug = value;
        }
    }

    updateCategoryField(field, value) {
        this.state.categoryForm[field] = value;
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

    async saveProductData() {
        return this.rpc("/bader_product_intelligence/update_product", {
            product_tmpl_id: this.state.productId,
            values: {
                name: this.state.productForm.name,
                sku: this.state.productForm.sku,
                slug: this.state.productForm.slug,
                brand: this.state.productForm.brand,
                categoryId: this.state.productForm.categoryId || false,
                priceUsd: this.parseNumber(this.state.productForm.priceUsd),
                previousPriceUsd: this.parseNumber(this.state.productForm.previousPriceUsd),
                costUsd: this.parseNumber(this.state.productForm.costUsd),
                isPublished: !!this.state.productForm.isPublished,
                featured: !!this.state.productForm.featured,
            },
        });
    }

    async saveCategoryData() {
        return this.rpc("/bader_product_intelligence/save_category", {
            product_tmpl_id: this.state.productId,
            values: {
                manualMode: !!this.state.categoryForm.manualMode,
                niches: this.state.categoryForm.niches || [],
                type: this.state.categoryForm.type || false,
                subcategory: this.state.categoryForm.subcategory || false,
                categoryId: this.state.categoryForm.categoryId || false,
            },
        });
    }

    async saveContentData() {
        return this.rpc("/bader_product_intelligence/save_content", {
            product_tmpl_id: this.state.productId,
            values: {
                name: this.state.contentForm.name,
                description: this.state.contentForm.description,
                tone: this.state.contentForm.tone,
                audience: this.state.contentForm.audience,
                faqs: this.state.contentForm.faqs || [],
            },
        });
    }

    async saveSeoData() {
        return this.rpc("/bader_product_intelligence/save_seo", {
            product_tmpl_id: this.state.productId,
            seo_data: {
                seoTitle: this.state.seoForm.seoTitle,
                seoDescription: this.state.seoForm.seoDescription,
                seoKeywords: this.state.seoForm.seoKeywords
                    .split(",")
                    .map((item) => item.trim())
                    .filter(Boolean),
                geoTitle: this.state.seoForm.geoTitle,
                geoDescription: this.state.seoForm.geoDescription,
                geoFeatures: this.state.seoForm.geoFeatures
                    .split(",")
                    .map((item) => item.trim())
                    .filter(Boolean),
                geoFaq: this.state.contentForm.faqs || [],
                aiGeneratedDescription: this.state.contentForm.description,
                aiTargetAudience: this.state.contentForm.audience,
                seoScore: this.currentSeoData().seoScore || 0,
                geoScore: this.currentSeoData().geoScore || 0,
                competitivenessScore: this.currentSeoData().competitivenessScore || 0,
            },
        });
    }

    async saveAll() {
        if (!this.state.productId) {
            return;
        }
        this.state.saveBusy = true;
        try {
            await this.saveProductData();
            await this.saveCategoryData();
            await this.saveContentData();
            await this.saveSeoData();
            await this.loadDetail(this.state.productId);
            this.notify("Cambios guardados.");
        } catch (error) {
            this.notify(this.errorMessage(error, "No se pudieron guardar los cambios."), "danger");
        } finally {
            this.state.saveBusy = false;
        }
    }

    async analyzeSeo() {
        this.state.seoBusy = true;
        try {
            const result = await this.rpc("/bader_product_intelligence/analyze_seo", {
                product_tmpl_id: this.state.productId,
                target_audience: this.state.contentForm.audience || "clinicas",
            });
            this.applyDetailPayload({
                ...this.state.detail,
                seoData: result.seoData,
            });
            if (result.seoData && result.seoData.aiGeneratedDescription) {
                this.state.contentForm.description = result.seoData.aiGeneratedDescription;
            }
            this.notify("SEO optimizado con Nancy AI.");
        } catch (error) {
            this.notify(this.errorMessage(error, "No se pudo analizar el SEO."), "danger");
        } finally {
            this.state.seoBusy = false;
        }
    }

    async saveSeoOnly() {
        this.state.seoBusy = true;
        try {
            await this.saveSeoData();
            await this.loadDetail(this.state.productId);
            this.notify("SEO guardado.");
        } catch (error) {
            this.notify(this.errorMessage(error, "No se pudo guardar el SEO."), "danger");
        } finally {
            this.state.seoBusy = false;
        }
    }

    async generateContent() {
        this.state.contentBusy = true;
        try {
            const result = await this.rpc("/bader_product_intelligence/generate_content", {
                product_tmpl_id: this.state.productId,
                tone: this.state.contentForm.tone,
                audience: this.state.contentForm.audience,
            });
            this.state.contentForm.name = result.name || this.state.contentForm.name;
            this.state.contentForm.description = result.description || this.state.contentForm.description;
            this.notify("Descripcion generada con Nancy AI.");
        } catch (error) {
            this.notify(this.errorMessage(error, "No se pudo generar el contenido."), "danger");
        } finally {
            this.state.contentBusy = false;
        }
    }

    async generateFaq() {
        this.state.faqBusy = true;
        try {
            const result = await this.rpc("/bader_product_intelligence/generate_faq", {
                product_tmpl_id: this.state.productId,
                audience: this.state.contentForm.audience,
            });
            this.state.contentForm.faqs = (result.faqs || []).map((faq) => ({
                question: faq.question || "",
                answer: faq.answer || "",
            }));
            this.notify("FAQs generadas con Nancy AI.");
        } catch (error) {
            this.notify(this.errorMessage(error, "No se pudieron generar las FAQs."), "danger");
        } finally {
            this.state.faqBusy = false;
        }
    }

    async saveContentOnly() {
        this.state.contentBusy = true;
        try {
            await this.saveContentData();
            await this.loadDetail(this.state.productId);
            this.notify("Contenido guardado.");
        } catch (error) {
            this.notify(this.errorMessage(error, "No se pudo guardar el contenido."), "danger");
        } finally {
            this.state.contentBusy = false;
        }
    }

    async reclassifyCategory() {
        this.state.categoryBusy = true;
        try {
            const result = await this.rpc("/bader_product_intelligence/reclassify_category", {
                product_tmpl_id: this.state.productId,
            });
            this.applyDetailPayload(result);
            this.notify("Categoria reclasificada con Nancy AI.");
        } catch (error) {
            this.notify(this.errorMessage(error, "No se pudo reclasificar el producto."), "danger");
        } finally {
            this.state.categoryBusy = false;
        }
    }

    async saveCategoryOnly() {
        this.state.categoryBusy = true;
        try {
            await this.saveCategoryData();
            await this.loadDetail(this.state.productId);
            this.notify("Categorizacion guardada.");
        } catch (error) {
            this.notify(this.errorMessage(error, "No se pudo guardar la categorizacion."), "danger");
        } finally {
            this.state.categoryBusy = false;
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
        this.state.imageBusy = true;
        try {
            const payload = {
                product_tmpl_id: this.state.productId,
                prompt: this.state.imageForm.prompt,
                reference_tokens: this.state.imageForm.selectedReferences,
                style: this.state.imageForm.style,
                use_pro: true,
            };
            if (this.state.imageForm.uploadedRefUrl) {
                payload.uploaded_ref = this.state.imageForm.uploadedRefUrl;
            }
            const result = await this.rpc("/bader_product_intelligence/generate_image", payload);
            this.state.imageForm.generatedPreviewUrl = result.previewUrl || "";
            this.notify("Preview generado con Nancy AI.");
        } catch (error) {
            this.notify(this.errorMessage(error, "No se pudo generar la imagen."), "danger");
        } finally {
            this.state.imageBusy = false;
        }
    }

    async approveImage() {
        if (!this.state.imageForm.generatedPreviewUrl) {
            return;
        }
        this.state.imageBusy = true;
        try {
            await this.rpc("/bader_product_intelligence/approve_image", {
                product_tmpl_id: this.state.productId,
                image_data_url: this.state.imageForm.generatedPreviewUrl,
                prompt: this.state.imageForm.prompt,
            });
            await this.loadDetail(this.state.productId);
            this.notify("Imagen aprobada y guardada.");
        } catch (error) {
            this.notify(this.errorMessage(error, "No se pudo guardar la imagen."), "danger");
        } finally {
            this.state.imageBusy = false;
        }
    }

    openImageModal() {
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
        const reader = new FileReader();
        reader.onload = (e) => {
            this.state.imageForm.uploadedRefUrl = e.target.result;
            this.state.imageForm.uploadedRefName = file.name;
        };
        reader.readAsDataURL(file);
    }

    removeUploadedRef() {
        this.state.imageForm.uploadedRefUrl = "";
        this.state.imageForm.uploadedRefName = "";
    }

    async approveImageAndClose() {
        await this.approveImage();
        this.state.showImageModal = false;
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
            requestAnimationFrame(() => { el.scrollTop = el.scrollHeight; });
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

        this.state.imageBusy = true;
        try {
            const payload = {
                product_tmpl_id: this.state.productId,
                prompt: text,
                reference_tokens: this.state.imageForm.selectedReferences,
                style: this.state.imageForm.style || "professional",
                use_pro: true,
            };
            if (this.state.imageForm.uploadedRefUrl) {
                payload.uploaded_ref = this.state.imageForm.uploadedRefUrl;
            }
            const result = await this.rpc("/bader_product_intelligence/generate_image", payload);
            const previewUrl = result.previewUrl || "";

            this.state.playground.messages = this.state.playground.messages.map((m, i) =>
                i === loadingIdx ? { role: "ai", text: "Imagen generada. Haz clic en la imagen para verla en el canvas.", imageUrl: previewUrl } : m
            );
            this.state.playground.canvasUrl = previewUrl;
            this.state.imageForm.generatedPreviewUrl = previewUrl;
            this.state.imageForm.uploadedRefUrl = "";
            this.state.imageForm.uploadedRefName = "";
        } catch (error) {
            this.state.playground.messages = this.state.playground.messages.map((m, i) =>
                i === loadingIdx ? { role: "ai", text: this.errorMessage(error, "No se pudo generar la imagen. Intenta de nuevo.") } : m
            );
        } finally {
            this.state.imageBusy = false;
            this.scrollPlayground();
        }
    }

    async saveCanvasToGallery() {
        if (!this.state.playground.canvasUrl) return;
        this.state.imageBusy = true;
        try {
            await this.rpc("/bader_product_intelligence/approve_image", {
                product_tmpl_id: this.state.productId,
                image_data_url: this.state.playground.canvasUrl,
                prompt: "Nancy AI Studio",
            });
            await this.loadDetail(this.state.productId);
            this.notify("Imagen guardada en la galería.");
        } catch (error) {
            this.notify(this.errorMessage(error, "No se pudo guardar la imagen."), "danger");
        } finally {
            this.state.imageBusy = false;
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

        this.state.imageBusy = true;
        try {
            const payload = {
                product_tmpl_id: this.state.productId,
                prompt,
                reference_tokens: this.state.imageForm.selectedReferences,
                style: this.state.imageForm.style || "professional",
                use_pro: true,
            };
            if (this.state.imageForm.uploadedRefUrl) {
                payload.uploaded_ref = this.state.imageForm.uploadedRefUrl;
            }
            if (this.state.imageForm.selectedGalleryUrl) {
                payload.selected_image_url = this.state.imageForm.selectedGalleryUrl;
            }
            const result = await this.rpc("/bader_product_intelligence/generate_image", payload);
            const previewUrl = result.previewUrl || "";

            this.state.playground.messages = this.state.playground.messages.map((m, i) =>
                i === loadingIdx ? { role: "ai", text: "✅ Imagen generada con éxito.", imageUrl: previewUrl } : m
            );
            this.state.imageForm.generatedPreviewUrl = previewUrl;
        } catch (error) {
            this.state.playground.messages = this.state.playground.messages.map((m, i) =>
                i === loadingIdx ? { role: "ai", text: this.errorMessage(error, "❌ No se pudo generar la imagen. Intenta de nuevo.") } : m
            );
        } finally {
            this.state.imageBusy = false;
            this.scrollPlayground();
        }
    }

    async saveGeneratedImage(imageUrl) {
        if (!imageUrl) return;
        this.state.imageBusy = true;
        try {
            await this.rpc("/bader_product_intelligence/approve_image", {
                product_tmpl_id: this.state.productId,
                image_data_url: imageUrl,
                prompt: this.state.imageForm.prompt || "Nancy AI Studio",
            });
            await this.loadDetail(this.state.productId);
            this.notify("Imagen guardada en la galería del producto.");
        } catch (error) {
            this.notify(this.errorMessage(error, "No se pudo guardar la imagen."), "danger");
        } finally {
            this.state.imageBusy = false;
        }
    }

    async addImageUrl() {
        if (!this.state.imageForm.addImageUrl.trim()) {
            return;
        }
        this.state.imageBusy = true;
        try {
            await this.rpc("/bader_product_intelligence/add_image_url", {
                product_tmpl_id: this.state.productId,
                image_url: this.state.imageForm.addImageUrl,
            });
            await this.loadDetail(this.state.productId);
            this.notify("Imagen agregada.");
        } catch (error) {
            this.notify(this.errorMessage(error, "No se pudo agregar la imagen."), "danger");
        } finally {
            this.state.imageBusy = false;
        }
    }

    async deleteImage(imageId) {
        if (imageId === "main") {
            return;
        }
        this.state.imageBusy = true;
        try {
            await this.rpc("/bader_product_intelligence/delete_image", {
                image_id: imageId,
            });
            await this.loadDetail(this.state.productId);
            this.notify("Imagen eliminada.");
        } catch (error) {
            this.notify(this.errorMessage(error, "No se pudo eliminar la imagen."), "danger");
        } finally {
            this.state.imageBusy = false;
        }
    }

    async saveVideo() {
        this.state.imageBusy = true;
        try {
            await this.rpc("/bader_product_intelligence/save_video", {
                product_tmpl_id: this.state.productId,
                video_url: this.state.imageForm.videoUrl,
            });
            await this.loadDetail(this.state.productId);
            this.notify("Video guardado.");
        } catch (error) {
            this.notify(this.errorMessage(error, "No se pudo guardar el video."), "danger");
        } finally {
            this.state.imageBusy = false;
        }
    }

    async discoverCompetitors() {
        this.state.competitorBusy = true;
        try {
            const result = await this.rpc("/bader_product_intelligence/discover_competitors", {
                product_tmpl_id: this.state.productId,
                limit: 10,
            });
            this.state.competitorForm.discoveredCompetitors = result.competitors || [];
            this.state.competitorForm.discoveryQuery = result.query || "";
            this.notify(`Se encontraron ${result.totalFound || 0} competidores.`);
        } catch (error) {
            this.notify(this.errorMessage(error, "No se pudieron descubrir competidores."), "danger");
        } finally {
            this.state.competitorBusy = false;
        }
    }

    async addCompetitor(name = "", url = "") {
        const competitorName = name || this.state.competitorForm.competitorName;
        const competitorUrl = url || this.state.competitorForm.competitorUrl;
        if (!competitorUrl) {
            this.notify("Ingresa una URL de competidor.", "warning");
            return;
        }
        this.state.competitorBusy = true;
        try {
            await this.rpc("/bader_product_intelligence/add_competitor", {
                product_tmpl_id: this.state.productId,
                competitor_name: competitorName,
                competitor_url: competitorUrl,
            });
            this.state.competitorForm.competitorName = "";
            this.state.competitorForm.competitorUrl = "";
            await this.loadDetail(this.state.productId);
            this.notify("Competidor agregado.");
        } catch (error) {
            this.notify(this.errorMessage(error, "No se pudo agregar el competidor."), "danger");
        } finally {
            this.state.competitorBusy = false;
        }
    }

    async scrapeCompetitor(competitorId) {
        this.state.competitorBusy = true;
        try {
            await this.rpc("/bader_product_intelligence/scrape_competitor", {
                competitor_id: competitorId,
            });
            await this.loadDetail(this.state.productId);
            this.notify("Scraping completado.");
        } catch (error) {
            this.notify(this.errorMessage(error, "No se pudo scrapear el competidor."), "danger");
        } finally {
            this.state.competitorBusy = false;
        }
    }

    async analyzeCompetitor(competitorId) {
        this.state.competitorBusy = true;
        try {
            await this.rpc("/bader_product_intelligence/analyze_competitor", {
                competitor_id: competitorId,
            });
            await this.loadDetail(this.state.productId);
            this.notify("Analisis competitivo actualizado.");
        } catch (error) {
            this.notify(this.errorMessage(error, "No se pudo analizar el competidor."), "danger");
        } finally {
            this.state.competitorBusy = false;
        }
    }

    async deleteCompetitor(competitorId) {
        this.state.competitorBusy = true;
        try {
            await this.rpc("/bader_product_intelligence/delete_competitor", {
                competitor_id: competitorId,
            });
            await this.loadDetail(this.state.productId);
            this.notify("Competidor eliminado.");
        } catch (error) {
            this.notify(this.errorMessage(error, "No se pudo eliminar el competidor."), "danger");
        } finally {
            this.state.competitorBusy = false;
        }
    }

    async generateStrategy() {
        this.state.strategyBusy = true;
        try {
            await this.rpc("/bader_product_intelligence/generate_strategy", {
                product_tmpl_id: this.state.productId,
            });
            await this.loadDetail(this.state.productId);
            this.notify("Estrategia competitiva generada.");
        } catch (error) {
            this.notify(this.errorMessage(error, "No se pudo generar la estrategia."), "danger");
        } finally {
            this.state.strategyBusy = false;
        }
    }

    async toggleDashboardPublish(productId, checked) {
        try {
            await this.rpc("/bader_product_intelligence/update_product", {
                product_tmpl_id: productId,
                values: { isPublished: checked },
            });
            await this.loadDashboard({}, { showSpinner: false });
        } catch (error) {
            this.notify(this.errorMessage(error, "No se pudo actualizar la publicacion."), "danger");
        }
    }

    async toggleDashboardFeatured(productId, checked) {
        try {
            await this.rpc("/bader_product_intelligence/update_product", {
                product_tmpl_id: productId,
                values: { featured: checked },
            });
            await this.loadDashboard({}, { showSpinner: false });
        } catch (error) {
            this.notify(this.errorMessage(error, "No se pudo actualizar el destacado."), "danger");
        }
    }

    quickAction(tabId) {
        this.state.activeTab = tabId;
    }

    priceMarkerStyle() {
        const range = this.competitorPriceRange();
        const price = Number(this.currentProduct().priceUsd || 0);
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
        this.state.chatMessages.push({ role: "user", content: msg });
        this.state.chatInput = "";
        this.state.chatBusy = true;
        try {
            const result = await this.rpc("/bader_product_intelligence/chat", {
                product_tmpl_id: this.state.productId,
                message: msg,
                session_id: this.state.chatSessionKey || false,
            });
            this.state.chatMessages.push({ role: "assistant", content: result.response });
            this.state.chatSessionKey = result.sessionId || this.state.chatSessionKey;
        } catch (error) {
            this.state.chatMessages.push({ role: "assistant", content: "Error: " + this.errorMessage(error, "No se pudo obtener respuesta.") });
        } finally {
            this.state.chatBusy = false;
        }
    }

    onChatKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.sendChatMessage();
        }
    }

    useChatQuickAction(action) {
        this.state.chatMessages.push({ role: "user", content: action });
        this.sendChatMessage(action);
    }

    async loadChatHistory() {
        if (this.state.chatMessages.length || !this.state.productId) {
            return;
        }
        try {
            const data = await this.rpc("/bader_product_intelligence/data", {
                product_tmpl_id: this.state.productId,
            });
            const messages = (data && data.chatHistory) || [];
            if (messages.length) {
                this.state.chatSessionKey = data.chatSessionId || "";
                this.state.chatMessages = messages.map((m) => ({
                    role: m.role,
                    content: m.content,
                }));
            }
        } catch (_e) {
            // Silent fail
        }
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
