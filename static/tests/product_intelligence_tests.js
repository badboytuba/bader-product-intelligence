/** @odoo-module **/

import { App } from "@odoo/owl";
import { templates } from "@web/core/assets";
import { CallbackRecorder } from "@web/webclient/actions/action_hook";

import {
    ProductIntelligenceAction,
    canDeleteGalleryImage,
    competitorComparablePriceUsd,
    productEffectivePriceRange,
} from "@bader_product_intelligence/js/product_intelligence_action";

QUnit.module("Bader Product Intelligence stabilization");

QUnit.test("Studio selects gallery images by real reference token", (assert) => {
    const action = Object.create(ProductIntelligenceAction.prototype);
    action.state = { imageForm: { selectedReferences: [] } };

    action.toggleReference("bpi:42");
    assert.deepEqual(action.state.imageForm.selectedReferences, ["bpi:42"]);
    action.toggleReference("bpi:42");
    assert.deepEqual(action.state.imageForm.selectedReferences, []);
});

QUnit.test("safe Odoo user errors replace generic transport messages without exposing internal details", (assert) => {
    const action = Object.create(ProductIntelligenceAction.prototype);
    const fallback = "No se pudo completar esta acción.";
    for (const name of ["odoo.exceptions.UserError", "odoo.exceptions.ValidationError", "odoo.exceptions.AccessError"]) {
        assert.strictEqual(action.errorMessage({ message: "Odoo Server Error", data: { name, message: "Configura OpenAI API Key en Ajustes." } }, fallback), "Configura OpenAI API Key en Ajustes.");
    }
    for (const message of ["<script>private()</script>", "&lt;img src=x&gt;", "Traceback (most recent call last): internal detail", 'File "/private/server.py", line 42', "API key: synthetic-private-token", "Bearer synthetic-private-token", "https://example.invalid/api?token=private", "sk-proj-synthetic-private-token", "fc-synthetic-private-token", "x".repeat(1201), ""]) {
        assert.strictEqual(action.errorMessage({ message: "Odoo Server Error", data: { name: "odoo.exceptions.UserError", message, debug: "must never be exposed" } }, fallback), fallback, "unsafe or empty details use the operation fallback");
    }
    assert.strictEqual(action.errorMessage({ data: { name: "builtins.TypeError", message: "private backend detail" } }, fallback), fallback);
    assert.strictEqual(action.errorMessage(new Error("Unexpected local detail"), fallback), fallback);
    assert.strictEqual(action.errorMessage({ data: { name: "odoo.exceptions.UserError", message: { private: true } } }, fallback), fallback);
    assert.strictEqual(action.errorMessage(null, fallback), fallback);
    assert.strictEqual(action.errorMessage({ data: { name: "odoo.exceptions.UserError", message: "  Falta configuración.\n Revisa Ajustes.\u202e  " } }, fallback), "Falta configuración. Revisa Ajustes.");
});

QUnit.test("gallery deletion is conditioned by canDelete and bpi token", async (assert) => {
    assert.notOk(canDeleteGalleryImage({ canDelete: false, referenceToken: "main" }));
    assert.notOk(canDeleteGalleryImage({ canDelete: true, referenceToken: "odoo:8" }));
    assert.ok(canDeleteGalleryImage({ canDelete: true, referenceToken: "bpi:8" }));

    const calls = [];
    const action = Object.create(ProductIntelligenceAction.prototype);
    action.state = { productId: 7, imageBusy: false };
    action.rpc = async (route, payload) => calls.push({ route, payload });
    action.refreshDetail = async () => {};
    action.notify = () => {};
    action.errorMessage = () => "error";

    await action.deleteImage({ canDelete: false, referenceToken: "main" });
    await action.deleteImage({ canDelete: true, referenceToken: "bpi:8" });
    assert.strictEqual(calls.length, 1);
    assert.deepEqual(calls[0].payload, { product_tmpl_id: 7, image_token: "bpi:8" });
});

QUnit.test("description editor preserves safe Word-like formatting only", (assert) => {
    const action = Object.create(ProductIntelligenceAction.prototype);
    const sanitized = action.sanitizeDescriptionHtml(`
        <h2 style="color: #cc0000; background-color: #fff2a8; font-family: Arial; font-size: 24px; text-align: center; position: fixed">
            Titulo <script>alert(1)</script>
        </h2>
        <font face="Georgia" size="5" color="#00525c" style="background-color: #fff2a8">Texto</font>
        <a href="javascript:alert(1)" onclick="alert(2)">Enlace inseguro</a>
    `);
    const container = document.createElement("div");
    container.innerHTML = sanitized;
    const heading = container.querySelector("h2");
    const legacySpan = container.querySelector("span");
    const link = container.querySelector("a");

    assert.ok(heading, "supported heading is retained");
    assert.ok(heading.style.color, "text color is retained");
    assert.ok(heading.style.backgroundColor, "highlight color is retained");
    assert.strictEqual(heading.style.fontFamily, "Arial", "allowlisted font is retained");
    assert.strictEqual(heading.style.fontSize, "24px", "allowlisted size is retained");
    assert.strictEqual(heading.style.textAlign, "center", "alignment is retained");
    assert.notOk(heading.style.position, "unsafe style properties are removed");
    assert.strictEqual(legacySpan.style.fontFamily, "Georgia", "legacy font markup is normalized");
    assert.strictEqual(legacySpan.style.fontSize, "24px", "legacy font size is normalized");
    assert.ok(legacySpan.style.backgroundColor, "legacy highlight is retained");
    assert.notOk(container.querySelector("script"), "script elements are removed");
    assert.notOk(link.hasAttribute("href"), "unsafe link protocols are removed");
    assert.notOk(link.hasAttribute("onclick"), "event attributes are removed");
});

QUnit.test("content save keeps optimized and technical descriptions independent", async (assert) => {
    const calls = [];
    const action = Object.create(ProductIntelligenceAction.prototype);
    action.state = {
        productId: 17,
        contentForm: {
            name: "Producto técnico",
            description: "<p>Resumen corto</p>",
            technicalDescription: "<h3>Especificaciones</h3><p>Contenido ampliado</p>",
            tone: "tecnico",
            audience: "clinicas",
            faqs: [],
        },
    };
    action.rpc = async (route, payload) => calls.push({ route, payload });

    await action.saveContentData();

    assert.strictEqual(calls.length, 1);
    assert.strictEqual(calls[0].route, "/bader_product_intelligence/save_content");
    assert.strictEqual(calls[0].payload.values.description, "<p>Resumen corto</p>");
    assert.strictEqual(
        calls[0].payload.values.technicalDescription,
        "<h3>Especificaciones</h3><p>Contenido ampliado</p>"
    );
});

QUnit.test("chat quick action does not duplicate the user message", (assert) => {
    const action = Object.create(ProductIntelligenceAction.prototype);
    const sent = [];
    action.state = { chatMessages: [] };
    action.sendChatMessage = (message) => sent.push(message);

    action.useChatQuickAction("Mejora el SEO");
    assert.deepEqual(sent, ["Mejora el SEO"]);
    assert.deepEqual(action.state.chatMessages, []);
});

QUnit.test("detail payload replaces chat state when product changes", (assert) => {
    const action = Object.create(ProductIntelligenceAction.prototype);
    action.state = {
        detail: null,
        productForm: {},
        contentForm: {},
        seoForm: {},
        categoryForm: {},
        imageForm: {},
        competitorForm: {},
        chatMessages: [{ role: "user", content: "Producto anterior" }],
        chatSessionKey: "old-session",
        chatInput: "pending",
        chatBusy: true,
        exchangeRate: 1650,
        exchangeRateInput: "1650",
    };

    action.applyDetailPayload({
        product: { id: 2, name: "Producto B", referenceImages: [] },
        seoData: {
            aiGeneratedDescriptionHtml: "<p>Resumen B</p>",
            aiTechnicalDescriptionHtml: "<h3>Ficha B</h3><p>Detalle B</p>",
        },
        images: [],
        chatHistory: [{ role: "assistant", content: "Historial B" }],
        chatSessionId: "session-b",
        exchangeRate: 1650,
    });

    assert.deepEqual(action.state.chatMessages, [{ role: "assistant", content: "Historial B" }]);
    assert.strictEqual(action.state.contentForm.description, "<p>Resumen B</p>");
    assert.strictEqual(
        action.state.contentForm.technicalDescription,
        "<h3>Ficha B</h3><p>Detalle B</p>"
    );
    assert.strictEqual(action.state.chatSessionKey, "session-b");
    assert.strictEqual(action.state.chatInput, "");
    assert.notOk(action.state.chatBusy);
});

QUnit.test("late chat response from another product is ignored", async (assert) => {
    let resolveRpc;
    const rpcResult = new Promise((resolve) => { resolveRpc = resolve; });
    const action = Object.create(ProductIntelligenceAction.prototype);
    action.chatRequestSequence = 0;
    action.state = {
        productId: 1,
        chatInput: "",
        chatBusy: false,
        chatMessages: [],
        chatSessionKey: "session-a",
    };
    action.rpc = () => rpcResult;
    action.notify = () => {};
    action.errorMessage = () => "error";

    const pending = action.sendChatMessage("Pregunta A");
    action.state.productId = 2;
    action.state.chatMessages = [];
    ++action.chatRequestSequence;
    resolveRpc({ response: "Respuesta A", sessionId: "session-a" });
    await pending;

    assert.deepEqual(action.state.chatMessages, []);
});

QUnit.test("analytics only uses normalized USD values", (assert) => {
    assert.strictEqual(competitorComparablePriceUsd({ competitorPriceUsd: 20 }), 20);
    assert.strictEqual(
        competitorComparablePriceUsd({ competitorPriceUsd: 20, competitorOfferPriceUsd: 15 }),
        15
    );
    assert.strictEqual(competitorComparablePriceUsd({ competitorPrice: 999, competitorCurrency: "EUR" }), 0);
    for (const priceStatus of ['unknown', 'not_found', 'ambiguous']) assert.strictEqual(competitorComparablePriceUsd({ priceStatus, competitorPriceUsd: 999 }), 0, 'explicitly unverified price is excluded from analytics');
    assert.strictEqual(competitorComparablePriceUsd({ priceStatus: 'known', competitorPriceUsd: 20 }), 20);

    const action = Object.create(ProductIntelligenceAction.prototype);
    action.currentCompetitors = () => [
        { competitorPriceUsd: 20 },
        { competitorPriceUsd: 30, competitorOfferPriceUsd: 10 },
        { competitorPrice: 999, competitorCurrency: "EUR", competitorPriceUsd: false },
    ];
    assert.strictEqual(action.averageCompetitorPrice(), 15);
    assert.deepEqual(action.competitorPriceRange(), { min: 10, max: 20 });
});

QUnit.test("product prices use native effective variant range", (assert) => {
    assert.deepEqual(productEffectivePriceRange({ priceUsd: 12 }), { min: 12, max: 12 });
    assert.deepEqual(
        productEffectivePriceRange({ priceUsd: 12, effectivePriceMinUsd: 14, effectivePriceMaxUsd: 19 }),
        { min: 14, max: 19 }
    );

    const action = Object.create(ProductIntelligenceAction.prototype);
    action.state = { exchangeRate: 1000 };
    assert.strictEqual(
        action.productComparisonPrice({ effectivePriceMinUsd: 10, effectivePriceMaxUsd: 20 }),
        15
    );
});

QUnit.test("variant save only sends operational native fields", async (assert) => {
    const calls = [];
    const action = Object.create(ProductIntelligenceAction.prototype);
    action.state = { productId: 7, variantBusy: false, activeTab: "variants_pack" };
    action.rpc = async (route, payload) => {
        calls.push({ route, payload });
        return {};
    };
    action.applyDetailPayload = () => {};
    action.notify = () => {};
    action.errorMessage = () => "error";

    await action.saveVariant({
        id: 21,
        sku: "VAR-21",
        barcode: "7790000000021",
        costUsdInput: "4.25",
        active: true,
        effectivePriceUsd: 99,
        qtyAvailable: 500,
    });
    assert.strictEqual(calls[0].route, "/bader_product_intelligence/update_variant");
    assert.deepEqual(calls[0].payload.values, {
        sku: "VAR-21",
        barcode: "7790000000021",
        costUsd: 4.25,
        active: true,
    });
});

QUnit.test("variant image requires exactly the selected operation", async (assert) => {
    const calls = [];
    const action = Object.create(ProductIntelligenceAction.prototype);
    action.state = { productId: 7, variantBusy: false, activeTab: "variants_pack" };
    action.rpc = async (route, payload) => {
        calls.push({ route, payload });
        return {};
    };
    action.applyDetailPayload = () => {};
    action.notify = () => {};
    action.errorMessage = () => "error";
    const variant = { id: 22, imageReferenceToken: "bpi:8" };

    await action.setVariantImage(variant, "reference");
    assert.deepEqual(calls[0], {
        route: "/bader_product_intelligence/set_variant_image",
        payload: { product_tmpl_id: 7, product_variant_id: 22, image_token: "bpi:8" },
    });
});

QUnit.test("pack save sends all variant compositions with revision", async (assert) => {
    const calls = [];
    const action = Object.create(ProductIntelligenceAction.prototype);
    action.state = {
        productId: 7,
        packBusy: false,
        activeTab: "variants_pack",
        packForm: {
            isPack: true,
            packType: "detailed",
            componentPriceMode: "ignored",
            modifiable: false,
            revision: "revision-1",
            compositions: [{
                variantId: 21,
                components: [{
                    lineId: 4,
                    productVariantId: 31,
                    quantityInput: "2",
                    saleDiscountInput: "10",
                }],
            }],
        },
    };
    action.rpc = async (route, payload) => {
        calls.push({ route, payload });
        return {};
    };
    action.applyDetailPayload = () => {};
    action.notify = () => {};
    action.errorMessage = () => "error";

    await action.savePack();
    assert.strictEqual(calls[0].route, "/bader_product_intelligence/update_pack");
    assert.strictEqual(calls[0].payload.packRevision, "revision-1");
    assert.deepEqual(calls[0].payload.values.compositions, [{
        variantId: 21,
        components: [{ lineId: 4, productVariantId: 31, quantity: 2, saleDiscount: 10 }],
    }]);
});

QUnit.test("pack component search handles Enter without unsupported OWL modifiers", async (assert) => {
    const action = Object.create(ProductIntelligenceAction.prototype);
    let searches = 0;
    let prevented = 0;
    action.searchPackComponents = async () => {
        searches += 1;
        return "searched";
    };

    action.onPackComponentSearchKeydown({
        key: "a",
        isComposing: false,
        preventDefault: () => { prevented += 1; },
    });
    assert.deepEqual([searches, prevented], [0, 0], "other keys are ignored");

    action.onPackComponentSearchKeydown({
        key: "Enter",
        isComposing: true,
        preventDefault: () => { prevented += 1; },
    });
    assert.deepEqual([searches, prevented], [0, 0], "IME composition Enter is ignored");

    const result = await action.onPackComponentSearchKeydown({
        key: "Enter",
        isComposing: false,
        preventDefault: () => { prevented += 1; },
    });
    assert.deepEqual([searches, prevented], [1, 1], "Enter prevents submit and starts one search");
    assert.strictEqual(result, "searched", "the search promise is returned");
});

function stabilizationDeferred() {
    let resolve;
    let reject;
    const promise = new Promise((done, fail) => { resolve = done; reject = fail; });
    return { promise, resolve, reject };
}

function stabilizationPayload(id = 1) {
    return {
        product: { id, name: `Producto ${id}`, categoryId: 11, slug: `producto-${id}`, description: `Resumen ${id}`, referenceImages: [], isPack: true },
        seoData: { seoTitle: `Meta ${id}`, seoKeywords: ["dental"], geoKeywords: ["clinicas"], seoScore: 40, geoFaq: [{ question: "Pregunta", answer: "Respuesta" }] },
        variants: [{ id: id * 10, sku: `VAR-${id}`, active: true, costUsd: 3 }],
        pack: { isPack: true, revision: `rev-${id}`, compositions: [] },
        images: [],
    };
}

function stabilizationAction(id = 1) {
    const action = Object.create(ProductIntelligenceAction.prototype);
    action.state = {
        productId: id, viewMode: "detail", activeTab: "overview", dashboardTab: "all", searchTerm: "",
        playground: { messages: [], canvasUrl: "", inputText: "" },
    };
    action.applyDetailPayload(stabilizationPayload(id));
    action.notifications = [];
    action.notify = (message) => action.notifications.push(message);
    action.syncContentDescriptionEditor = action.syncTechnicalDescriptionEditor = action.scrollPlayground = () => {};
    return action;
}

QUnit.test("saveAll uses one immutable transaction and one canonical category", async (assert) => {
    const action = stabilizationAction();
    action.state.productForm.categoryId = "22";
    action.state.categoryForm.categoryId = "11"; // Legacy stale state must not win.
    action.state.contentForm.faqs = [{ question: "Antes", answer: "Original" }];
    const pending = stabilizationDeferred();
    const calls = [];
    action.rpc = (route, payload) => { calls.push({ route, payload }); return pending.promise; };
    const saving = action.saveAll();
    action.state.contentForm.faqs[0].answer = "Edición posterior";
    action.invalidateProductRequests();
    action.state.productId = 2;
    action.applyDetailPayload(stabilizationPayload(2));
    pending.resolve(stabilizationPayload(1));
    await saving;
    assert.strictEqual(calls.length, 1, "no second request can target the newly selected product");
    assert.strictEqual(calls[0].route, "/bader_product_intelligence/save_all");
    assert.strictEqual(calls[0].payload.product_tmpl_id, 1);
    assert.strictEqual(calls[0].payload.product_values.categoryId, "22");
    assert.strictEqual(calls[0].payload.category_values.categoryId, "22");
    assert.strictEqual(calls[0].payload.content_values.faqs[0].answer, "Original", "RPC values are not live form references");
    assert.strictEqual(action.state.detail.product.id, 2);
    assert.deepEqual(action.notifications, [], "no stale success notification");
});

QUnit.test("saveAll retains edits made during the request and clears its busy flag", async (assert) => {
    const action = stabilizationAction();
    action.state.productForm.categoryId = "22";
    const pending = stabilizationDeferred();
    action.rpc = () => pending.promise;
    const saving = action.saveAll();
    action.state.contentForm.description = "Nuevo borrador sin guardar";
    action.state.productForm.sku = "SKU-NUEVO";
    const saved = stabilizationPayload();
    saved.product.categoryId = 22;
    pending.resolve(saved);
    await saving;
    assert.strictEqual(action.state.productForm.categoryId, "22", "canonical category survives normal reload");
    assert.strictEqual(action.state.productForm.sku, "SKU-NUEVO");
    assert.strictEqual(action.state.contentForm.description, "Nuevo borrador sin guardar");
    assert.notOk(action.state.saveBusy);
});

QUnit.test("saveAll failure retains every draft and makes no follow-up RPC", async (assert) => {
    const action = stabilizationAction();
    action.state.contentForm.description = "Borrador";
    action.state.productForm.categoryId = "22";
    const before = action.captureDrafts();
    let calls = 0;
    action.rpc = async () => { calls += 1; throw new Error("Rollback"); };
    await action.saveAll();
    assert.strictEqual(calls, 1);
    assert.deepEqual(action.captureDrafts(), before);
    assert.notOk(action.state.saveBusy);
});

QUnit.test("SEO preview changes metadata only and SEO save omits every editorial field", async (assert) => {
    const action = stabilizationAction();
    action.state.contentForm.description = "Comercial sin guardar";
    action.state.contentForm.technicalDescription = "Técnica sin guardar";
    action.state.contentForm.faqs = [{ question: "Manual", answer: "Conservar" }];
    action.state.productForm.categoryId = "22";
    const before = action.captureDrafts();
    const originalDetail = action.state.detail;
    action.applySeoJobPayload({ productId: 1, resultPayload: { seoData: {
        seoTitle: "Nueva meta", seoScore: 88, seoKeywords: ["a", "b"], geoKeywords: ["local"],
        aiGeneratedDescriptionHtml: "NO", aiTechnicalDescription: "NO", geoFaq: [],
    } } });
    assert.strictEqual(action.state.seoForm.seoTitle, "Nueva meta");
    assert.strictEqual(action.state.seoForm.seoScore, 88);
    assert.strictEqual(action.state.seoForm.geoKeywords, "local");
    assert.strictEqual(action.state.detail, originalDetail, "preview does not impersonate persisted product data");
    assert.deepEqual(action.state.contentForm, before.contentForm);
    assert.deepEqual(action.state.productForm, before.productForm);
    assert.deepEqual(action.state.packForm, before.packForm);
    assert.ok(action.state.seoPreviewPending);
    const calls = [];
    action.rpc = async (route, payload) => { calls.push({ route, payload }); return {}; };
    await action.saveSeoData();
    const values = calls[0].payload.seo_data;
    for (const field of ["geoFaq", "aiGeneratedDescription", "aiGeneratedDescriptionHtml", "aiTechnicalDescription", "aiTargetAudience"]) {
        assert.notOk(field in values, `${field} is outside SEO save`);
    }
    assert.deepEqual(values.geoKeywords, ["local"]);
});

QUnit.test("late SEO polling preserves new product and a fresh SEO job busy state", async (assert) => {
    const action = stabilizationAction();
    const pending = stabilizationDeferred();
    action.rpc = () => pending.promise;
    const polling = action.pollSeoJob(99);
    action.invalidateProductRequests();
    action.state.productId = 2;
    action.applyDetailPayload(stabilizationPayload(2));
    action.state.seoBusy = true;
    action.state.seoJobId = 100;
    pending.resolve({ job: { id: 99, productId: 1, state: "done", resultPayload: { seoData: { seoTitle: "Producto A" }, detailPayload: stabilizationPayload(1) } } });
    await polling;
    assert.strictEqual(action.state.detail.product.id, 2);
    assert.strictEqual(action.state.seoForm.seoTitle, "Meta 2");
    assert.strictEqual(action.state.seoJobId, 100);
    assert.ok(action.state.seoBusy, "old finalizer cannot release the new product's operation");
    assert.notOk(action.seoJobPollTimer);
});

QUnit.test("SEO preview preserves metadata typed while the job was pending", (assert) => {
    const action = stabilizationAction();
    const request = action.beginRequest("seoJob", true);
    action.state.seoForm.seoTitle = "Meta manual más reciente";
    action.applySeoJobPayload({ productId: 1, resultPayload: { seoData: { seoTitle: "Meta de IA", geoTitle: "Nueva GEO" } } }, request);
    assert.strictEqual(action.state.seoForm.seoTitle, "Meta manual más reciente");
    assert.strictEqual(action.state.seoForm.geoTitle, "Nueva GEO");
});

QUnit.test("late responses for every product operation are ignored after navigation", async (assert) => {
    const operations = [
        ["generateContent", [], "contentBusy"], ["generateFaq", [], "faqBusy"],
        ["analyzeSeo", [], "seoBusy"], ["saveSeoOnly", [], "seoBusy"],
        ["saveContentOnly", [], "contentBusy"], ["reclassifyCategory", [], "categoryBusy"],
        ["saveCategoryOnly", [], "categoryBusy"], ["generateImage", [], "imageBusy"],
        ["approveImage", [], "imageBusy"], ["saveCanvasToGallery", [], "imageBusy"],
        ["generateFromForm", [], "imageBusy"], ["sendPlaygroundMessage", [], "imageBusy"],
        ["saveGeneratedImage", ["data:image/png;base64,preview"], "imageBusy"],
        ["addImageUrl", [], "imageBusy"], ["deleteImage", [{ canDelete: true, referenceToken: "bpi:8" }], "imageBusy"],
        ["saveVideo", [], "imageBusy"], ["discoverCompetitors", [], "competitorBusy"],
        ["addCompetitor", ["Tienda", "https://example.com/item"], "competitorBusy"],
        ["scrapeCompetitor", [1], "competitorBusy"], ["analyzeCompetitor", [1], "competitorBusy"],
        ["deleteCompetitor", [1], "competitorBusy"], ["generateStrategy", [], "strategyBusy"],
        ["searchPackComponents", [], "componentSearchBusy"], ["savePack", [], "packBusy"],
        ["saveVariant", [{ id: 10, sku: "OLD", active: true }], "variantBusy"],
        ["setVariantImage", [{ id: 10, imageReferenceToken: "main" }, "reference"], "variantBusy"],
    ];
    for (const [method, args, busy] of operations) {
        const action = stabilizationAction();
        action.state.imageForm.prompt = "Prompt A";
        action.state.imageForm.generatedPreviewUrl = "data:image/png;base64,preview";
        action.state.imageForm.addImageUrl = "https://example.com/image.png";
        action.state.playground.canvasUrl = "data:image/png;base64,preview";
        action.state.playground.inputText = "Prompt A";
        const pending = stabilizationDeferred();
        let calls = 0;
        action.rpc = () => { calls += 1; return pending.promise; };
        const result = action[method](...args);
        action.invalidateProductRequests();
        action.state.productId = 2;
        action.applyDetailPayload(stabilizationPayload(2));
        action.state[busy] = true;
        const before = action.captureDrafts();
        pending.resolve({
            ...stabilizationPayload(1), previewUrl: "STALE", name: "STALE", description: "STALE", faqs: [],
            competitors: [{ id: 99 }], components: [{ id: 99 }],
            job: { id: 99, productId: 1, state: "pending" },
        });
        await result;
        assert.strictEqual(calls, 1, `${method}: no stale follow-up fetch/mutation`);
        assert.deepEqual(action.captureDrafts(), before, `${method}: all new product drafts preserved`);
        assert.ok(action.state[busy], `${method}: new product busy flag preserved`);
        assert.deepEqual(action.notifications, [], `${method}: no stale notification`);
        assert.notOk(action.seoJobPollTimer, `${method}: no stale polling timer`);
    }
});

QUnit.test("generation tokens reject A to B to A and destroyed-component responses", async (assert) => {
    for (const destroyed of [false, true]) {
        const action = stabilizationAction();
        const pending = stabilizationDeferred();
        action.rpc = () => pending.promise;
        const generating = action.generateContent();
        action.invalidateProductRequests();
        action.state.productId = 2;
        action.invalidateProductRequests();
        action.state.productId = 1;
        action.applyDetailPayload(stabilizationPayload());
        action.destroyed = destroyed;
        pending.resolve({ name: "Respuesta vieja", description: "Respuesta vieja" });
        await generating;
        assert.strictEqual(action.state.contentForm.name, "Producto 1");
        assert.strictEqual(action.state.contentForm.description, "Resumen 1");
        assert.deepEqual(action.notifications, []);
    }
});

QUnit.test("newest request wins and stale failure cannot reset busy or notify", async (assert) => {
    const action = stabilizationAction();
    const old = stabilizationDeferred();
    const recent = stabilizationDeferred();
    let count = 0;
    action.rpc = () => (++count === 1 ? old.promise : recent.promise);
    const a = action.generateContent();
    const b = action.generateContent();
    old.reject(new Error("Old failure"));
    await a;
    assert.ok(action.state.contentBusy);
    assert.deepEqual(action.notifications, []);
    recent.resolve({ name: "Más reciente", description: "Contenido reciente" });
    await b;
    assert.strictEqual(action.state.contentForm.name, "Producto 1", "generation does not rename products");
    assert.strictEqual(action.state.productForm.name, "Producto 1", "canonical product name stays unchanged");
    assert.strictEqual(action.state.contentForm.description, "Contenido reciente", "newest description proposal wins");
    assert.notOk(action.state.contentBusy);
});

QUnit.test("AI configuration failures keep drafts and release busy state without implicit retry or save", async (assert) => {
    for (const [method, args, busy] of [
        ["generateContent", [], "contentBusy"], ["generateFaq", [], "faqBusy"],
        ["analyzeSeo", [], "seoBusy"], ["reclassifyCategory", [], "categoryBusy"],
        ["generateImage", [], "imageBusy"], ["discoverCompetitors", [], "competitorBusy"],
        ["scrapeCompetitor", [7], "competitorBusy"], ["analyzeCompetitor", [7], "competitorBusy"],
        ["generateStrategy", [], "strategyBusy"],
    ]) {
        const action = stabilizationAction();
        action.state.contentForm.description = "Descripción todavía sin guardar";
        action.state.seoForm.seoTitle = "SEO todavía sin guardar";
        action.state.categoryForm.type = "instrumental";
        action.state.imageForm.prompt = "Generar imagen de prueba";
        action.state.imageForm.generatedPreviewUrl = "data:image/png;base64,retained";
        const before = action.captureDrafts();
        let calls = 0;
        action.rpc = async () => { calls++; throw { message: "Odoo Server Error", data: { name: "odoo.exceptions.UserError", message: "Configura OpenAI API Key en Ajustes." } }; };
        await action[method](...args);
        assert.strictEqual(calls, 1, `${method}: no retry or mutation after error`);
        assert.deepEqual(action.state.contentForm, before.contentForm, `${method}: content draft retained`);
        assert.deepEqual(action.state.seoForm, before.seoForm, `${method}: SEO draft retained`);
        assert.deepEqual(action.state.categoryForm, before.categoryForm, `${method}: category draft retained`);
        assert.strictEqual(action.state.imageForm.generatedPreviewUrl, before.imageForm.generatedPreviewUrl);
        assert.notOk(action.state[busy], `${method}: busy state released`);
        assert.deepEqual(action.notifications, ["Configura OpenAI API Key en Ajustes."]);
        assert.notOk(action.seoJobPollTimer, "failed initiation does not begin polling");
    }
});

QUnit.test("partial variant and gallery updates retain editorial, Pack and chat drafts", async (assert) => {
    const action = stabilizationAction();
    action.state.contentForm.description = "Comercial borrador";
    action.state.contentForm.technicalDescription = "Técnica borrador";
    action.state.productForm.categoryId = "22";
    action.state.seoForm.seoTitle = "SEO borrador";
    action.state.chatMessages = [{ role: "user", content: "Mensaje pendiente" }];
    action.state.packForm.modifiable = true;
    const before = action.captureDrafts();
    action.rpc = async () => stabilizationPayload();
    await action.saveVariant(action.currentVariants()[0]);
    assert.deepEqual(action.state.contentForm, before.contentForm);
    assert.deepEqual(action.state.productForm, before.productForm);
    assert.deepEqual(action.state.seoForm, before.seoForm);
    assert.deepEqual(action.state.packForm, before.packForm);
    assert.deepEqual(action.state.chatMessages, [{ role: "user", content: "Mensaje pendiente" }]);
    await action.deleteImage({ canDelete: true, referenceToken: "bpi:9" });
    assert.deepEqual(action.state.contentForm, before.contentForm, "gallery refresh does not reset editors");
    assert.deepEqual(action.state.packForm, before.packForm);
});

QUnit.test("dashboard out-of-order search and dashboard/detail navigation cannot restore stale views", async (assert) => {
    const action = stabilizationAction();
    const old = stabilizationDeferred();
    const recent = stabilizationDeferred();
    action.rpc = (_route, data) => data.search === "old" ? old.promise : recent.promise;
    const a = action.loadDashboard({ search: "old" });
    const b = action.loadDashboard({ search: "new" });
    recent.resolve({ products: [{ id: 2 }] });
    await b;
    old.resolve({ products: [{ id: 1 }] });
    await a;
    assert.strictEqual(action.state.searchTerm, "new");
    assert.strictEqual(action.state.dashboardRows[0].id, 2);

    for (const first of ["dashboard", "detail"]) {
        const pending = stabilizationDeferred();
        action.rpc = (route) => {
            if (route.endsWith(first === "dashboard" ? "/dashboard" : "/data")) return pending.promise;
            return Promise.resolve(first === "dashboard" ? stabilizationPayload(2) : { products: [{ id: 3 }] });
        };
        const waiting = first === "dashboard" ? action.loadDashboard() : action.loadDetail(1);
        if (first === "dashboard") await action.loadDetail(2);
        else await action.loadDashboard();
        pending.resolve(first === "dashboard" ? { products: [{ id: 1 }] } : stabilizationPayload(1));
        await waiting;
        assert.strictEqual(action.state.viewMode, first === "dashboard" ? "detail" : "dashboard");
        assert.strictEqual(action.state.productId, first === "dashboard" ? 2 : null);
    }
});

QUnit.test("navigation cancels dashboard debounce and SEO polling timers", (assert) => {
    const action = stabilizationAction();
    action.scheduleDashboardReload();
    action.scheduleSeoJobPoll(99, 60000);
    assert.ok(action.dashboardReloadTimer);
    assert.ok(action.seoJobPollTimer);
    action.state.seoBusy = true;
    action.state.imageBusy = true;
    action.state.showImageModal = true;
    action.invalidateProductRequests();
    assert.strictEqual(action.dashboardReloadTimer, null);
    assert.strictEqual(action.seoJobPollTimer, null);
    assert.notOk(action.state.seoBusy);
    assert.notOk(action.state.imageBusy);
    assert.notOk(action.state.showImageModal);
});

QUnit.test("variant selection invalidates component searches without losing drafts", async (assert) => {
    const action = stabilizationAction();
    action.state.componentSearch.query = "motor";
    const pending = stabilizationDeferred();
    action.rpc = () => pending.promise;
    const searching = action.searchPackComponents();
    action.selectVariant(20);
    pending.resolve({ components: [{ productVariantId: 99 }] });
    await searching;
    assert.deepEqual(action.state.componentSearch.results, []);
    assert.notOk(action.state.componentSearchBusy);
});

QUnit.test("late follow-up refresh after a successful mutation cannot replace a new product", async (assert) => {
    for (const method of ["saveSeoOnly", "saveContentOnly", "saveCategoryOnly", "saveVideo"]) {
        const action = stabilizationAction();
        const refresh = stabilizationDeferred();
        let calls = 0;
        action.rpc = async (route) => {
            calls += 1;
            return route.endsWith("/data") ? refresh.promise : {};
        };
        const saving = action[method]();
        // Let the mutation settle and the second RPC start.
        await Promise.resolve();
        await Promise.resolve();
        await Promise.resolve();
        action.invalidateProductRequests();
        action.state.productId = 2;
        action.applyDetailPayload(stabilizationPayload(2));
        refresh.resolve(stabilizationPayload(1));
        await saving;
        assert.strictEqual(calls, 2, `${method}: exercised the post-mutation read`);
        assert.strictEqual(action.state.detail.product.id, 2, `${method}: stale read ignored`);
        assert.deepEqual(action.notifications, []);
    }
});

QUnit.test("dashboard mutations do not navigate away from a newly opened product", async (assert) => {
    for (const method of ["toggleDashboardPublish", "toggleDashboardFeatured", "saveExchangeRate"]) {
        const action = stabilizationAction();
        action.state.viewMode = "dashboard";
        action.state.productId = null;
        const pending = stabilizationDeferred();
        let calls = 0;
        action.rpc = () => { calls += 1; return pending.promise; };
        const mutation = action[method](1, true);
        action.invalidateProductRequests();
        action.state.productId = 2;
        action.state.viewMode = "detail";
        action.applyDetailPayload(stabilizationPayload(2));
        pending.resolve({ exchangeRate: 1800 });
        await mutation;
        assert.strictEqual(calls, 1, `${method}: no unsolicited dashboard refresh`);
        assert.strictEqual(action.state.viewMode, "detail");
        assert.deepEqual(action.notifications, []);
    }
});

QUnit.test("file reader responses are invalidated on product change or reference removal", (assert) => {
    const OriginalReader = window.FileReader;
    const readers = [];
    window.FileReader = class {
        constructor() { readers.push(this); }
        readAsDataURL() {}
    };
    try {
        const action = stabilizationAction();
        const event = { target: { files: [{ type: "image/png", size: 4, name: "a.png" }] } };
        action.handleFileUpload(event);
        action.removeUploadedRef();
        readers[0].onload({ target: { result: "OLD" } });
        assert.strictEqual(action.state.imageForm.uploadedRefUrl, "", "removed reference cannot reappear");
        action.handleFileUpload(event);
        action.handleVariantImageUpload(10, event);
        const oldVariant = action.currentVariants()[0];
        action.invalidateProductRequests();
        action.state.productId = 2;
        action.applyDetailPayload(stabilizationPayload(2));
        readers[1].onload({ target: { result: "OLD" } });
        readers[2].onload({ target: { result: "OLD" } });
        assert.notOk(action.state.imageForm.uploadedRefUrl);
        assert.strictEqual(action.currentVariants()[0].imageUploadDataUrl, "");
        assert.strictEqual(oldVariant.imageUploadDataUrl, "", "detached old variant is untouched too");
    } finally {
        window.FileReader = OriginalReader;
    }
});

QUnit.test("saving a variant image retains its unsaved SKU and Pack composition", async (assert) => {
    const action = stabilizationAction();
    const variant = action.currentVariants()[0];
    variant.sku = "SKU SIN GUARDAR";
    variant.imageReferenceToken = "main";
    action.state.packForm.modifiable = true;
    action.rpc = async () => ({
        ...stabilizationPayload(),
        variants: [{ ...stabilizationPayload().variants[0], imageUrl: "/fresh-image", hasOwnImage: true }],
    });
    await action.setVariantImage(variant, "reference");
    assert.strictEqual(action.currentVariants()[0].sku, "SKU SIN GUARDAR");
    assert.strictEqual(action.currentVariants()[0].imageUrl, "/fresh-image");
    assert.ok(action.currentVariants()[0].hasOwnImage);
    assert.ok(action.state.packForm.modifiable);
});

function dashboardAction() {
    const action = stabilizationAction();
    Object.assign(action.state, {
        productId: null, viewMode: "dashboard", dashboardSection: "overview",
        dashboardOverview: action.dashboardDefaultOverview(), dashboardCategoryId: "",
        dashboardQualityFilter: "", dashboardSortKey: "catalog", catalogReviewId: false, catalogBusyRows: {},
        dashboardCatalogUpdatedAt: "", overviewError: "",
        overviewBusy: false, dashboardBusy: false, loading: false,
        dashboardPager: action.dashboardDefaultPager(), dashboardRows: [],
    });
    return action;
}

function dashboardOverviewPayload(total = 12) {
    return {
        generatedAt: "2026-09-11 12:00:00", total, exchangeRate: 1750,
        categories: [{ id: 7, name: "Instrumental", completeName: "Dental / Instrumental" }],
        publication: { published: 9, unpublished: 3, total, publishedPercent: 75 },
        kpis: [{ key: "all", label: "Productos activos", count: total, percent: 100, filter: "all" }],
    };
}

QUnit.test("overview-first home requests only read-only metrics and no catalog or IA", async (assert) => {
    const action = dashboardAction();
    const calls = [];
    action.rpc = async (route, params) => { calls.push({ route, params }); return dashboardOverviewPayload(); };
    await action.refreshDashboardHome();
    assert.deepEqual(calls, [{ route: "/bader_product_intelligence/dashboard_overview", params: { category_id: false } }]);
    assert.strictEqual(action.state.dashboardSection, "overview");
    assert.strictEqual(action.state.dashboardOverview.total, 12);
    assert.strictEqual(action.state.exchangeRateInput, "1750");
    assert.deepEqual(action.state.dashboardRows, [], "stock/detail payload stays lazy");
    assert.notOk(action.state.overviewBusy);
    assert.notOk(action.state.loading);
    assert.strictEqual(action.dashboardCategories()[0].id, 7);
});

QUnit.test("KPI drill-down clears search and page but preserves the shared category", async (assert) => {
    const action = dashboardAction();
    action.state.dashboardCategoryId = "7";
    action.state.searchTerm = "bisturi";
    action.state.dashboardTab = "new";
    action.state.dashboardPager.page = 4;
    const calls = [];
    action.rpc = async (route, params) => { calls.push({ route, params }); return { products: [{ id: 19 }] }; };
    await action.openDashboardMetric("published_missing_image");
    assert.strictEqual(action.state.dashboardSection, "catalog");
    assert.strictEqual(action.state.dashboardTab, "all");
    assert.strictEqual(action.state.dashboardQualityFilter, "published_missing_image");
    assert.strictEqual(action.state.searchTerm, "");
    assert.deepEqual(calls[0], {
        route: "/bader_product_intelligence/dashboard",
        params: { tab: "all", search: "", page: 1, limit: 40, category_id: 7, quality_filter: "published_missing_image", sort_key: "catalog" },
    });
    assert.strictEqual(action.dashboardQualityLabel(), "Publicados sin imagen");
    await action.openDashboardMetric("all");
    assert.strictEqual(calls[1].params.quality_filter, false, "all removes quality restriction");
});

QUnit.test("category changes refresh the active section and reset only its page", async (assert) => {
    const action = dashboardAction();
    action.state.dashboardOverview = dashboardOverviewPayload();
    const calls = [];
    action.rpc = async (route, params) => {
        calls.push({ route, params });
        return route.endsWith("/dashboard_overview") ? dashboardOverviewPayload() : { products: [] };
    };
    await action.changeDashboardCategory({ target: { value: "7" } });
    assert.deepEqual(calls[0].params, { category_id: 7 });
    assert.strictEqual(action.state.dashboardCategoryId, "7");
    await action.selectDashboardSection("catalog");
    action.state.searchTerm = "pinza";
    action.state.dashboardQualityFilter = "seo";
    action.state.dashboardPager.page = 3;
    await action.changeDashboardCategory({ target: { value: "8" } });
    assert.strictEqual(calls[2].params.category_id, 8);
    assert.strictEqual(calls[2].params.search, "pinza");
    assert.strictEqual(calls[2].params.quality_filter, "seo");
    assert.strictEqual(calls[2].params.page, 1);
    assert.strictEqual(action.dashboardCategories()[0].id, 7, "choices survive category reset");
    assert.strictEqual(action.state.dashboardOverview.total, 0, "old-category counters are hidden");
});

QUnit.test("overview category A-B-A and out-of-order refreshes discard every stale response", async (assert) => {
    const action = dashboardAction();
    const requests = [];
    action.rpc = () => { const pending = stabilizationDeferred(); requests.push(pending); return pending.promise; };
    const a = action.loadDashboardOverview();
    const b = action.changeDashboardCategory({ target: { value: "7" } });
    const c = action.changeDashboardCategory({ target: { value: "" } });
    requests[2].resolve(dashboardOverviewPayload(33));
    await c;
    requests[0].resolve(dashboardOverviewPayload(11));
    requests[1].resolve(dashboardOverviewPayload(22));
    await Promise.all([a, b]);
    assert.strictEqual(action.state.dashboardOverview.total, 33);
    assert.strictEqual(action.state.dashboardCategoryId, "");
    const old = action.loadDashboardOverview();
    const latest = action.loadDashboardOverview();
    requests[4].resolve(dashboardOverviewPayload(55));
    await latest;
    requests[3].reject(new Error("obsolete error"));
    await old;
    assert.strictEqual(action.state.dashboardOverview.total, 55);
    assert.strictEqual(action.state.overviewError, "");
    assert.notOk(action.state.overviewBusy);
});

QUnit.test("catalog and overview section switches cannot restore each other's pending responses", async (assert) => {
    for (const first of ["catalog", "overview"]) {
        const action = dashboardAction();
        const pending = stabilizationDeferred();
        const second = first === "catalog" ? "overview" : "catalog";
        action.rpc = (route) => route.endsWith(first === "catalog" ? "/dashboard" : "/dashboard_overview")
            ? pending.promise : Promise.resolve(second === "overview" ? dashboardOverviewPayload(22) : { products: [{ id: 22 }] });
        const waiting = action.selectDashboardSection(first);
        await action.selectDashboardSection(second);
        pending.resolve(first === "overview" ? dashboardOverviewPayload(11) : { products: [{ id: 11 }] });
        await waiting;
        assert.strictEqual(action.state.dashboardSection, second);
        assert.strictEqual(action.state.viewMode, "dashboard");
        assert.strictEqual(second === "catalog" ? action.state.dashboardRows[0].id : action.state.dashboardOverview.total, 22);
        assert.notOk(action.state.overviewBusy);
        assert.notOk(action.state.dashboardBusy);
    }
});

QUnit.test("overview responses and errors cannot replace product detail even after returning home", async (assert) => {
    const action = dashboardAction();
    const pending = stabilizationDeferred();
    action.rpc = (route) => route.endsWith("/dashboard_overview") ? pending.promise : Promise.resolve(stabilizationPayload(2));
    const loading = action.loadDashboardOverview();
    await action.openDetail(2);
    pending.resolve(dashboardOverviewPayload(88));
    await loading;
    assert.strictEqual(action.state.viewMode, "detail");
    assert.strictEqual(action.state.detail.product.id, 2);
    assert.strictEqual(action.state.dashboardOverview.total, 0);
    assert.notOk(action.state.overviewBusy);
    action.rpc = async () => dashboardOverviewPayload(99);
    await action.goBack();
    assert.strictEqual(action.state.dashboardSection, "overview", "Nancy job drill-down returns to overview");
    assert.strictEqual(action.state.dashboardOverview.total, 99);
});

QUnit.test("returning from product detail preserves catalog category quality search and pagination", async (assert) => {
    const action = dashboardAction();
    Object.assign(action.state, { dashboardSection: "catalog", dashboardCategoryId: "7", dashboardQualityFilter: "faq", searchTerm: "pinza" });
    action.state.dashboardPager = { ...action.dashboardDefaultPager(), page: 3, pageCount: 4 };
    const calls = [];
    action.rpc = async (route, params) => {
        calls.push({ route, params });
        return route.endsWith("/data") ? stabilizationPayload(2) : { products: [{ id: 2 }], pager: { page: 3, pageCount: 4 } };
    };
    await action.openDetail(2);
    await action.goBack();
    assert.strictEqual(action.state.dashboardSection, "catalog");
    assert.deepEqual(calls[1].params, { tab: "all", search: "pinza", page: 3, limit: 40, category_id: 7, quality_filter: "faq", sort_key: "catalog" });
    assert.strictEqual(action.state.dashboardPager.page, 3);
    assert.strictEqual(action.state.searchTerm, "pinza");
});

QUnit.test("overview failure preserves the home shell and supports an explicit retry", async (assert) => {
    const action = dashboardAction();
    action.rpc = async () => { throw new Error("Metrics unavailable"); };
    await action.refreshDashboardHome();
    assert.strictEqual(action.state.viewMode, "dashboard");
    assert.strictEqual(action.state.dashboardSection, "overview");
    assert.strictEqual(action.state.overviewError, "No se pudo cargar la visión general. Inténtalo de nuevo.", "unexpected internal errors use the safe operation fallback");
    assert.strictEqual(action.state.error, "", "top-level error never removes the home header");
    assert.notOk(action.state.overviewBusy);
    assert.notOk(action.state.loading);
    action.rpc = async () => dashboardOverviewPayload();
    await action.refreshDashboardHome();
    assert.strictEqual(action.state.overviewError, "");
    assert.strictEqual(action.state.dashboardOverview.total, 12);
});

QUnit.test("catalog base tabs and quality clear retain category and never restart IA jobs", async (assert) => {
    const action = dashboardAction();
    Object.assign(action.state, { dashboardSection: "catalog", dashboardCategoryId: "7", dashboardQualityFilter: "image", searchTerm: "pinza" });
    const calls = [];
    action.rpc = async (route, params) => { calls.push({ route, params }); return { products: [] }; };
    await action.changeDashboardTab("new");
    assert.strictEqual(calls[0].params.quality_filter, false);
    assert.strictEqual(calls[0].params.category_id, 7);
    assert.strictEqual(calls[0].params.tab, "new");
    assert.strictEqual(calls[0].params.search, "pinza");
    action.state.dashboardQualityFilter = "seo";
    await action.clearDashboardQualityFilter();
    assert.strictEqual(calls[1].params.quality_filter, false);
    assert.strictEqual(calls[1].params.page, 1);
    assert.ok(calls.every((call) => call.route.endsWith("/dashboard")));
    action.state.dashboardTab = "all";
    action.state.dashboardQualityFilter = "image";
    await action.changeDashboardTab("all");
    assert.strictEqual(calls[2].params.quality_filter, false, "clicking the selected base tab clears KPI filtering");
});

QUnit.test("pending catalog writes cannot pull the user back out of overview", async (assert) => {
    for (const method of ["toggleDashboardPublish", "toggleDashboardFeatured", "saveExchangeRate"]) {
        const action = dashboardAction();
        action.state.dashboardSection = "catalog";
        const pending = stabilizationDeferred();
        const routes = [];
        action.rpc = (route) => {
            routes.push(route);
            return route.endsWith("/dashboard_overview") ? Promise.resolve(dashboardOverviewPayload()) : pending.promise;
        };
        const saving = action[method](2, true);
        await action.selectDashboardSection("overview");
        pending.resolve({ exchangeRate: 1800 });
        await saving;
        assert.strictEqual(action.state.dashboardSection, "overview", method);
        assert.strictEqual(routes.length, 2, "no unsolicited catalog reload");
        assert.deepEqual(action.notifications, []);
    }
});

QUnit.test("exchange-rate save refreshes the current overview without loading catalog rows", async (assert) => {
    const action = dashboardAction();
    action.state.exchangeRateInput = "1800";
    const routes = [];
    action.rpc = async (route) => { routes.push(route); return { ...dashboardOverviewPayload(), exchangeRate: 1800 }; };
    await action.saveExchangeRate();
    assert.deepEqual(routes, ["/bader_product_intelligence/update_exchange_rate", "/bader_product_intelligence/dashboard_overview"]);
    assert.strictEqual(action.state.dashboardSection, "overview");
    assert.strictEqual(action.state.exchangeRate, 1800);
    assert.notOk(action.state.exchangeRateBusy);
    assert.strictEqual(action.notifications.length, 1);
});

QUnit.test("dashboard helpers expose bounded current-state values and honest Nancy status", (assert) => {
    const action = dashboardAction();
    assert.strictEqual(action.dashboardPercent(-5), 0);
    assert.strictEqual(action.dashboardPercent(150), 100);
    assert.strictEqual(action.dashboardPercent("invalid"), 0);
    assert.strictEqual(action.dashboardPublicationStyle(), "--publication-percent: 0%;");
    assert.strictEqual(action.dashboardUpdatedLabel(), "—");
    assert.strictEqual(action.dashboardDateLabel("malformed"), "—");
    assert.strictEqual(action.dashboardJobLabel("done"), "Propuesta lista");
    assert.strictEqual(action.dashboardJobLabel("running"), "En ejecución");
    assert.ok(action.dashboardMetricIcon("image").startsWith("fa "));
    assert.notOk(action.dashboardJobDate({ createdAt: "2026-09-11 12:00:00" }).includes("Invalid"));
});


QUnit.test("custom dashboard RPC forwards a captured selected-company user context", async (assert) => {
    const action = dashboardAction();
    action.user = { context: { allowed_company_ids: [7], lang: "es_AR", tz: "Europe/Madrid" } };
    const pending = stabilizationDeferred();
    const calls = [];
    action.rpc = (route, params) => {
        calls.push({ route, params });
        return route.endsWith("/dashboard_overview") ? pending.promise : Promise.resolve({ products: [] });
    };
    const loading = action.loadDashboardOverview();
    action.user.context.allowed_company_ids.push(8);
    assert.deepEqual(calls[0].params.context.allowed_company_ids, [7], "in-flight overview snapshot is immutable");
    assert.strictEqual(calls[0].params.context.lang, "es_AR");
    assert.strictEqual(calls[0].params.context.tz, "Europe/Madrid");
    pending.resolve(dashboardOverviewPayload());
    await loading;
    await action.openDashboardMetric("seo");
    assert.deepEqual(calls[1].params.context.allowed_company_ids, [7, 8], "catalog carries current selected companies");
    assert.strictEqual(calls[1].params.quality_filter, "seo");
    action.user.context.allowed_company_ids = [9];
    assert.deepEqual(calls[1].params.context.allowed_company_ids, [7, 8], "catalog request context is captured too");
});


QUnit.test("populated dashboard mounts its actual OWL template and supports category drill-down", async (assert) => {
    const target = document.createElement("div");
    document.body.appendChild(target);
    const metrics = ["all", "published", "content", "image", "seo", "geo", "faq", "competitor"].map((key) => ({
        key, filter: key, label: `Métrica ${key}`, count: 12, percent: 100, description: `Cobertura ${key}`,
    }));
    const overview = {
        ...dashboardOverviewPayload(), kpis: metrics, coverage: metrics.slice(2),
        priorities: [{ key: "missing_seo", filter: "missing_seo", label: "SEO incompleto", count: 2, description: "Falta metadatos" }],
        jobs: { pending: 1, running: 0, done: 1, failed: 0, recent: [
            { id: 5, productId: 2, productName: "Producto técnico", state: "done", createdAt: "2026-09-11T12:00:00Z", finishedAt: "2026-09-11T12:01:00Z" },
        ] },
    };
    const calls = [];
    const app = new App(ProductIntelligenceAction, {
        templates, test: true, props: { action: { params: {}, context: {} } },
        env: { services: {
            user: { context: { allowed_company_ids: [1], lang: "es_AR" } },
            notification: { add() {} }, action: { doAction() {} },
            rpc: async (route, params) => {
                calls.push({ route, params });
                if (route.endsWith("/dashboard_overview")) return overview;
                if (route.endsWith("/dashboard")) return { products: [], pager: { total: 12 } };
                throw new Error(`Unexpected RPC in read-only home test: ${route}`);
            },
        } },
    });
    const patched = async () => {
        await new Promise((resolve) => window.requestAnimationFrame(resolve));
        await new Promise((resolve) => setTimeout(resolve, 0));
    };
    try {
        const action = await app.mount(target);
        assert.strictEqual(target.querySelector(".bpi-home h1").textContent, "Inteligencia del catálogo");
        assert.strictEqual(target.querySelectorAll("[data-kpi-key]").length, 8, "all KPI expressions render");
        assert.strictEqual(target.querySelectorAll("#bpi-home-category option").length, 2, "populated category expressions render");
        assert.ok(target.querySelector(".bpi-home-job-list").textContent.includes("Propuesta lista"), "job dates/status render");
        assert.strictEqual(calls.length, 1, "overview opening never fetches catalog or paid services");
        await action.changeDashboardCategory({ target: { value: "7" } });
        await patched();
        assert.strictEqual(target.querySelector("#bpi-home-category").value, "7", "numeric backend category matches selected string state");
        target.querySelector('[data-kpi-key="seo"]').click();
        await patched();
        assert.ok(target.querySelector(".bpi-home-catalog"), "real event binding opens the catalog");
        assert.strictEqual(calls[calls.length - 1].params.quality_filter, "seo");
        assert.strictEqual(calls[calls.length - 1].params.category_id, 7);
    } finally {
        app.destroy();
        target.remove();
    }
});


function catalogRow(id = 2, overrides = {}) {
    return {
        id, name: `Producto ${id}`, sku: `SKU-${id}`, qtyAvailable: 3,
        isPublished: false, featured: false, isActive: true, saleOk: true,
        priceUsd: 20, effectivePriceMinUsd: 20, effectivePriceMaxUsd: 20, costUsd: 10, effectiveCostUsd: 10,
        catalogHealth: { commercial: true, technical: false, image: false, seo: false, geo: false, faq: false, category: true, competitor: false, completed: 2, total: 7, percent: 29 },
        ...overrides,
    };
}

QUnit.test("catalog sorting preserves scoped filters and selected companies through pagination and detail return", async (assert) => {
    const action = dashboardAction();
    Object.assign(action.state, { dashboardSection: "catalog", dashboardCategoryId: "7", dashboardQualityFilter: "needs_attention", searchTerm: "pinza" });
    action.state.dashboardPager = { ...action.dashboardDefaultPager(), page: 3, pageCount: 4 };
    action.user = { context: { allowed_company_ids: [3] } };
    const calls = [];
    action.rpc = async (route, params) => {
        calls.push({ route, params });
        return route.endsWith("/data") ? stabilizationPayload(2)
            : { products: [catalogRow()], pager: { page: params.page, pageCount: 4, total: 130 } };
    };
    await action.changeDashboardSort({ target: { value: "price_asc" } });
    assert.strictEqual(calls[0].params.sort_key, "price_asc");
    assert.strictEqual(calls[0].params.category_id, 7);
    assert.strictEqual(calls[0].params.quality_filter, "needs_attention");
    assert.strictEqual(calls[0].params.search, "pinza");
    assert.strictEqual(calls[0].params.page, 1);
    assert.deepEqual(calls[0].params.context.allowed_company_ids, [3]);
    await action.changeDashboardPage(2);
    await action.openCatalogProduct(catalogRow(), "images");
    assert.strictEqual(action.state.activeTab, "images");
    await action.goBack();
    assert.strictEqual(calls[calls.length - 1].params.sort_key, "price_asc");
    assert.strictEqual(calls[calls.length - 1].params.page, 2);
    assert.strictEqual(action.state.dashboardQualityFilter, "needs_attention");
    assert.ok(action.catalogSortOptions().find((option) => option.value === "price_asc").label.includes("Precio base"));
});

QUnit.test("late catalog sort responses and failures cannot replace the latest order", async (assert) => {
    const action = dashboardAction();
    action.state.dashboardSection = "catalog";
    const older = stabilizationDeferred();
    const newer = stabilizationDeferred();
    action.rpc = (_route, params) => params.sort_key === "recent" ? older.promise : newer.promise;
    const first = action.changeDashboardSort({ target: { value: "recent" } });
    const second = action.changeDashboardSort({ target: { value: "name_asc" } });
    newer.resolve({ products: [catalogRow(22)] });
    await second;
    older.reject(new Error("obsolete sort error"));
    await first;
    assert.strictEqual(action.state.dashboardRows[0].id, 22);
    assert.strictEqual(action.state.dashboardSortKey, "name_asc");
    assert.strictEqual(action.state.error, "");
    assert.notOk(action.state.dashboardBusy);
});

QUnit.test("catalog quality and reset controls preserve category and base tab without retaining stale review", async (assert) => {
    const action = dashboardAction();
    Object.assign(action.state, { dashboardSection: "catalog", dashboardTab: "new", dashboardCategoryId: "7", dashboardSortKey: "recent", searchTerm: "pinza" });
    const calls = [];
    action.rpc = async (route, params) => { calls.push({ route, params }); return { products: [catalogRow()] }; };
    await action.changeDashboardQualityFilter({ target: { value: "complete" } });
    assert.strictEqual(calls[0].params.quality_filter, "complete");
    assert.strictEqual(calls[0].params.page, 1);
    assert.strictEqual(calls[0].params.sort_key, "recent");
    assert.strictEqual(action.dashboardQualityLabel(), "Ficha completa");
    action.toggleCatalogReview(action.state.dashboardRows[0]);
    assert.strictEqual(action.state.catalogReviewId, 2);
    await action.clearCatalogFilters();
    assert.deepEqual(calls[1].params, { tab: "new", search: "", page: 1, limit: 40, category_id: 7, quality_filter: false, sort_key: "catalog" });
    assert.notOk(action.state.catalogReviewId);
    assert.notOk(action.catalogHasFilters(), "category/base tab are intentionally retained, not resettable filters");
    await action.changeDashboardSort({ target: { value: "unknown" } });
    await action.changeDashboardQualityFilter({ target: { value: "unknown" } });
    assert.strictEqual(calls.length, 2, "invalid controls cannot broaden scope or trigger RPC");
});

QUnit.test("catalog inline review uses current rows only and never fetches product details", async (assert) => {
    const action = dashboardAction();
    action.state.dashboardSection = "catalog";
    action.state.dashboardRows = [catalogRow()];
    let calls = 0;
    action.rpc = async () => { calls++; return { products: [catalogRow(3)] }; };
    action.toggleCatalogReview(action.state.dashboardRows[0]);
    assert.strictEqual(action.catalogReviewRow().id, 2);
    assert.strictEqual(calls, 0);
    action.toggleCatalogReview(action.state.dashboardRows[0]);
    assert.strictEqual(action.catalogReviewRow(), null);
    action.toggleCatalogReview(action.state.dashboardRows[0]);
    await action.loadDashboard();
    assert.strictEqual(action.catalogReviewRow(), null);
    assert.strictEqual(calls, 1, "only explicit catalog refresh fetched data");
    action.state.catalogReviewId = 3;
    action.invalidateProductRequests();
    assert.notOk(action.state.catalogReviewId);
});

QUnit.test("catalog checklist excludes competitors and next actions map only to existing editable sections", (assert) => {
    const action = dashboardAction();
    const row = catalogRow();
    assert.strictEqual(action.catalogHealthItems(row).length, 7);
    assert.strictEqual(action.catalogHealthLabel(row), "2 de 7 secciones completas");
    assert.strictEqual(action.catalogHealthPercent(row), 29);
    row.catalogHealth.competitor = true;
    assert.strictEqual(action.catalogHealthPercent(row), 29, "competitor info never increases completion");
    assert.strictEqual(action.catalogNextAction(row).section, "images");
    row.catalogHealth.image = true;
    assert.strictEqual(action.catalogNextAction(row).section, "content");
    row.catalogHealth.technical = true;
    assert.strictEqual(action.catalogNextAction(row).section, "seo");
    Object.keys(row.catalogHealth).forEach((key) => { row.catalogHealth[key] = true; });
    assert.strictEqual(action.catalogNextAction(row).section, "datos");
    assert.strictEqual(action.catalogHealthLabel(row), "7 de 7 secciones completas");
    assert.strictEqual(action.catalogHealthLabel({}), "Sin evaluar");
    assert.deepEqual(action.catalogHealthItems({}), []);
    assert.strictEqual(action.catalogNextAction({}).section, "datos");
});

QUnit.test("catalog labels separate real publication inventory availability and missing cost", (assert) => {
    const action = dashboardAction();
    const row = catalogRow(2, { isArchived: true, isActive: false, isPublished: true, qtyAvailable: 5 });
    assert.strictEqual(action.catalogProductStatusLabel(row), "Archivado");
    assert.strictEqual(action.catalogPublicationLabel(row), "Publicado", "archived does not mean publication flag false");
    assert.strictEqual(action.catalogStockLabel(row), "En stock", "archived inventory is still real inventory");
    assert.strictEqual(action.catalogProductStatusLabel(catalogRow(3, { saleOk: false })), "Fuera de venta");
    assert.strictEqual(action.catalogStockLabel(catalogRow(3, { qtyAvailable: -1 })), "Sin stock");
    assert.notOk(action.catalogMarginKnown(catalogRow(3, { effectiveCostUsd: 0, costUsd: 10 })), "effective Pack missing cost is not replaced by template cost");
    assert.notOk(action.catalogMarginKnown(catalogRow(3, { effectivePriceMinUsd: 0 })));
    assert.ok(action.catalogMarginKnown(catalogRow()));
    action.state.dashboardPager = { page: 2, limit: 40, total: 43 };
    assert.strictEqual(action.catalogResultLabel(), "Mostrando 41–43 de 43 productos");
});

QUnit.test("late quick-section product response cannot overwrite a newer product's selected tab", async (assert) => {
    const action = dashboardAction();
    action.state.dashboardSection = "catalog";
    const older = stabilizationDeferred();
    action.rpc = (_route, params) => params.product_tmpl_id === 1 ? older.promise : Promise.resolve(stabilizationPayload(2));
    const first = action.openCatalogProduct(catalogRow(1), "images");
    await action.openCatalogProduct(catalogRow(2), "seo");
    older.resolve(stabilizationPayload(1));
    await first;
    assert.strictEqual(action.state.detail.product.id, 2);
    assert.strictEqual(action.state.activeTab, "seo");
    await action.openCatalogProduct(catalogRow(2), "untrusted-section");
    assert.strictEqual(action.state.activeTab, "datos", "unknown actions fall back to existing Datos tab");
});

QUnit.test("catalog toggle blocks duplicate row writes and restores checkbox DOM after a failed mutation", async (assert) => {
    const action = dashboardAction();
    action.state.dashboardSection = "catalog";
    action.state.dashboardRows = [catalogRow()];
    const pending = stabilizationDeferred();
    let calls = 0;
    action.rpc = () => { calls++; return pending.promise; };
    const publishEvent = { target: { checked: true } };
    const duplicateEvent = { target: { checked: true } };
    const saving = action.toggleDashboardPublish(2, true, publishEvent);
    assert.ok(action.catalogRowBusy(action.state.dashboardRows[0]));
    await action.toggleDashboardFeatured(2, true, duplicateEvent);
    assert.strictEqual(calls, 1);
    assert.notOk(duplicateEvent.target.checked);
    pending.reject(new Error("Write rejected"));
    await saving;
    assert.notOk(publishEvent.target.checked);
    assert.notOk(action.state.dashboardRows[0].isPublished);
    assert.notOk(action.catalogRowBusy(2));
    assert.strictEqual(action.notifications.length, 1);
});

QUnit.test("catalog writes on separate rows preserve independent busy state and current sort", async (assert) => {
    const action = dashboardAction();
    Object.assign(action.state, { dashboardSection: "catalog", dashboardSortKey: "name_desc", dashboardQualityFilter: "needs_attention" });
    action.state.dashboardRows = [catalogRow(2), catalogRow(3)];
    const first = stabilizationDeferred();
    const second = stabilizationDeferred();
    const calls = [];
    action.rpc = (route, params) => {
        calls.push({ route, params });
        if (route.endsWith("/update_product")) return params.product_tmpl_id === 2 ? first.promise : second.promise;
        return Promise.resolve({ products: [catalogRow(2, { isPublished: true }), catalogRow(3, { featured: true })] });
    };
    const a = action.toggleDashboardPublish(2, true);
    const b = action.toggleDashboardFeatured(3, true);
    first.resolve({ success: true });
    await a;
    assert.notOk(action.catalogRowBusy(2));
    assert.ok(action.catalogRowBusy(3));
    second.resolve({ success: true });
    await b;
    assert.notOk(action.catalogRowBusy(3));
    assert.ok(calls.filter((call) => call.route.endsWith("/dashboard")).every((call) => call.params.sort_key === "name_desc" && call.params.quality_filter === "needs_attention"));
});

QUnit.test("successful catalog write stays visible if its refresh fails and stale failures never affect another view", async (assert) => {
    const action = dashboardAction();
    action.state.dashboardSection = "catalog";
    action.state.dashboardRows = [catalogRow()];
    const event = { target: { checked: true } };
    action.rpc = async (route) => {
        if (route.endsWith("/update_product")) return { success: true };
        throw new Error("Refresh unavailable");
    };
    await action.toggleDashboardPublish(2, true, event);
    assert.ok(action.state.dashboardRows[0].isPublished, "committed write not visually rolled back by refresh error");
    assert.ok(event.target.checked);
    assert.notOk(action.catalogRowBusy(2));
    const pending = stabilizationDeferred();
    action.rpc = (route) => route.endsWith("/dashboard_overview") ? Promise.resolve(dashboardOverviewPayload()) : pending.promise;
    const staleEvent = { target: { checked: true } };
    const stale = action.toggleDashboardFeatured(2, true, staleEvent);
    await action.selectDashboardSection("overview");
    pending.reject(new Error("Obsolete failed write"));
    await stale;
    assert.deepEqual(action.notifications, []);
    assert.strictEqual(action.state.dashboardSection, "overview");
    assert.ok(staleEvent.target.checked, "detached old DOM is not changed after navigation");
    assert.deepEqual(action.state.catalogBusyRows, {});
});

QUnit.test("actual catalog template binds sort quality inline review and direct section actions", async (assert) => {
    const target = document.createElement("div");
    document.body.appendChild(target);
    const calls = [];
    const app = new App(ProductIntelligenceAction, {
        templates, test: true, props: { action: { params: {}, context: {} } },
        env: { services: {
            user: { context: { allowed_company_ids: [1] } }, notification: { add() {} }, action: { doAction() {} },
            rpc: async (route, params) => {
                calls.push({ route, params });
                if (route.endsWith("/dashboard_overview")) return dashboardOverviewPayload();
                if (route.endsWith("/dashboard")) return { products: [catalogRow()], pager: { total: 1 }, tabCounts: { all: 1, new: 1, discontinued: 0 } };
                if (route.endsWith("/data")) return stabilizationPayload(params.product_tmpl_id);
                throw new Error(`Unexpected write or IA request: ${route}`);
            },
        } },
    });
    const patched = async () => {
        await new Promise((resolve) => window.requestAnimationFrame(resolve));
        await new Promise((resolve) => setTimeout(resolve, 0));
    };
    try {
        const action = await app.mount(target);
        target.querySelector('[data-bpi-section="catalog"]').click();
        await patched();
        assert.strictEqual(target.querySelectorAll("tr[data-product-id]").length, 1);
        const beforeReview = calls.length;
        target.querySelector('[data-catalog-review="2"]').click();
        await patched();
        assert.strictEqual(calls.length, beforeReview, "expanding review performs zero RPC");
        assert.strictEqual(target.querySelectorAll('[data-catalog-inspector="2"] [data-catalog-check]').length, 7);
        assert.strictEqual(target.querySelector('[data-catalog-check="image"]').getAttribute("data-catalog-present"), "false");
        const sort = target.querySelector("#bpi-catalog-sort");
        sort.value = "price_desc";
        sort.dispatchEvent(new Event("change", { bubbles: true }));
        await patched();
        assert.strictEqual(calls[calls.length - 1].params.sort_key, "price_desc");
        assert.notOk(target.querySelector("[data-catalog-inspector]"), "new catalog load closes prior review");
        const quality = target.querySelector("#bpi-catalog-quality");
        quality.value = "needs_attention";
        quality.dispatchEvent(new Event("change", { bubbles: true }));
        await patched();
        assert.strictEqual(calls[calls.length - 1].params.quality_filter, "needs_attention");
        target.querySelector("[data-catalog-clear]").click();
        await patched();
        assert.strictEqual(target.querySelector("#bpi-catalog-sort").value, "catalog");
        assert.strictEqual(target.querySelector("#bpi-catalog-quality").value, "");
        target.querySelector('[data-catalog-review="2"]').click();
        await patched();
        target.querySelector('[data-catalog-check="image"]').click();
        await patched();
        assert.strictEqual(action.state.activeTab, "images");
        assert.strictEqual(action.state.detail.product.id, 2);
        assert.ok(target.querySelector(".bpi-detail-shell"));
        assert.strictEqual(calls[calls.length - 1].route, "/bader_product_intelligence/data");
        await action.goBack();
        await patched();
        assert.ok(target.querySelector(".bpi-home-catalog"));
        assert.notOk(target.querySelector("[data-catalog-inspector]"));
    } finally {
        app.destroy();
        target.remove();
    }
});

QUnit.test("actual catalog name row open and next buttons retain real helper receivers without double navigation", async (assert) => {
    const target = document.createElement("div");
    document.body.appendChild(target);
    const details = [];
    const app = new App(ProductIntelligenceAction, {
        templates, test: true, props: { action: { params: {}, context: {} } },
        env: { services: {
            user: { context: {} }, notification: { add() {} }, action: { doAction() {} },
            rpc: async (route, params) => {
                if (route.endsWith("/dashboard_overview")) return dashboardOverviewPayload();
                if (route.endsWith("/dashboard")) return { products: [catalogRow(2), catalogRow(3)], pager: { total: 2 } };
                if (route.endsWith("/data")) {
                    details.push(params.product_tmpl_id);
                    return stabilizationPayload(params.product_tmpl_id);
                }
                throw new Error(`Unexpected RPC: ${route}`);
            },
        } },
    });
    const patched = async () => {
        await new Promise((resolve) => window.requestAnimationFrame(resolve));
        await new Promise((resolve) => setTimeout(resolve, 0));
    };
    try {
        const action = await app.mount(target);
        await action.selectDashboardSection("catalog");
        await patched();
        assert.strictEqual(action.catalogRowBusy, ProductIntelligenceAction.prototype.catalogRowBusy,
            "use the real method: a stub could conceal an unbound this in template lambdas");
        action.state.catalogBusyRows = { 2: true };
        await patched();
        const busyRow = target.querySelector('tr[data-product-id="2"]');
        const busyName = busyRow.querySelector(".bpi-home-product-link");
        const busyOpen = busyRow.querySelector(".bpi-catalog-open");
        assert.ok(busyName.disabled, "busy product name is disabled");
        assert.ok(busyOpen.disabled, "busy open action is disabled");
        busyName.click();
        busyOpen.click();
        busyRow.click();
        await patched();
        assert.strictEqual(details.length, 0, "busy row and disabled controls cannot open details");
        assert.strictEqual(action.state.viewMode, "dashboard");
        action.state.catalogBusyRows = {};
        await patched();
        for (const [id, selector] of [
            [2, 'tr[data-product-id="2"] .bpi-home-product-link'],
            [3, 'tr[data-product-id="3"]'],
            [2, 'tr[data-product-id="2"] .bpi-catalog-open'],
        ]) {
            const before = details.length;
            target.querySelector(selector).click();
            await patched();
            assert.strictEqual(action.state.viewMode, "detail", `${selector} opens the product workspace`);
            assert.strictEqual(action.state.detail.product.id, id, "the clicked row supplies the correct product ID");
            assert.strictEqual(details.length, before + 1, "one click creates exactly one detail request, without bubbling twice");
            assert.strictEqual(action.state.activeTab, "overview", "standard catalog entry preserves default detail overview");
            await action.goBack();
            await patched();
        }
        assert.strictEqual(action.catalogNextAction, ProductIntelligenceAction.prototype.catalogNextAction,
            "recommended action also uses the real prototype method inside its event lambda");
        target.querySelector('[data-catalog-review="2"]').click();
        await patched();
        target.querySelector('[data-catalog-next="2"]').click();
        await patched();
        assert.strictEqual(action.state.viewMode, "detail");
        assert.strictEqual(action.state.detail.product.id, 2);
        assert.strictEqual(action.state.activeTab, "images", "next action opens the actual first incomplete section");
        assert.deepEqual(details, [2, 3, 2, 2], "next action also opens only once");
        await action.goBack();
        await patched();
        assert.strictEqual(action.state.dashboardSection, "catalog");
    } finally {
        app.destroy();
        target.remove();
    }
});

QUnit.test("actual catalog review Escape and close return focus without requests or automatic focus stealing", async (assert) => {
    const target = document.createElement("div");
    document.body.appendChild(target);
    let calls = 0;
    const app = new App(ProductIntelligenceAction, {
        templates, test: true, props: { action: { params: {}, context: {} } },
        env: { services: {
            user: { context: {} }, notification: { add() {} }, action: { doAction() {} },
            rpc: async (route) => {
                calls++;
                if (route.endsWith("/dashboard_overview")) return dashboardOverviewPayload();
                if (route.endsWith("/dashboard")) return { products: [catalogRow()], pager: { total: 1 } };
                throw new Error(`Unexpected RPC: ${route}`);
            },
        } },
    });
    const patched = async () => {
        await new Promise((resolve) => window.requestAnimationFrame(resolve));
        await new Promise((resolve) => setTimeout(resolve, 0));
    };
    try {
        const action = await app.mount(target);
        await action.selectDashboardSection("catalog");
        await patched();
        const beforeReview = calls;
        const invoker = target.querySelector('[data-catalog-review="2"]');
        invoker.click();
        await patched();
        const check = target.querySelector('[data-catalog-check="image"]');
        check.focus();
        check.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }));
        assert.ok(action.state.catalogReviewId, "unrelated keys do not dismiss the review");
        const escape = new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true });
        check.dispatchEvent(escape);
        await patched();
        assert.ok(escape.defaultPrevented, "Escape is handled locally");
        assert.notOk(target.querySelector("[data-catalog-inspector]"));
        assert.strictEqual(document.activeElement, invoker, "Escape returns focus to the invoking review button");
        invoker.click();
        await patched();
        const close = target.querySelector(".bpi-catalog-close");
        close.focus();
        close.click();
        await patched();
        assert.notOk(target.querySelector("[data-catalog-inspector]"));
        assert.strictEqual(document.activeElement, invoker, "manual close also restores focus");
        invoker.click();
        await patched();
        const search = target.querySelector("#bpi-catalog-search");
        search.focus();
        action.closeCatalogReview();
        await patched();
        assert.strictEqual(document.activeElement, search, "automatic close does not move keyboard focus");
        assert.strictEqual(calls, beforeReview, "inspection, closing and Escape perform zero RPC");
    } finally {
        app.destroy();
        target.remove();
    }
});

QUnit.test("actual catalog checkbox binds busy state and restores visual value on rejected write", async (assert) => {
    const target = document.createElement("div");
    document.body.appendChild(target);
    const mutation = stabilizationDeferred();
    const notifications = [];
    let writes = 0;
    const app = new App(ProductIntelligenceAction, {
        templates, test: true, props: { action: { params: {}, context: {} } },
        env: { services: {
            user: { context: {} }, notification: { add: (message) => notifications.push(message) }, action: { doAction() {} },
            rpc: async (route) => {
                if (route.endsWith("/dashboard_overview")) return dashboardOverviewPayload();
                if (route.endsWith("/dashboard")) return { products: [catalogRow()], pager: { total: 1 } };
                if (route.endsWith("/update_product")) { writes++; return mutation.promise; }
                throw new Error(`Unexpected RPC: ${route}`);
            },
        } },
    });
    const patched = async () => {
        await new Promise((resolve) => window.requestAnimationFrame(resolve));
        await new Promise((resolve) => setTimeout(resolve, 0));
    };
    try {
        const action = await app.mount(target);
        await action.selectDashboardSection("catalog");
        await patched();
        const publish = target.querySelector('input[aria-label="Publicar Producto 2"]');
        const featured = target.querySelector('input[aria-label="Destacar Producto 2"]');
        assert.notOk(publish.checked);
        publish.click();
        await patched();
        assert.strictEqual(writes, 1);
        assert.ok(publish.disabled);
        assert.ok(featured.disabled, "another flag on the same row cannot race the first mutation");
        mutation.reject(new Error("Rejected fixture write"));
        await patched();
        assert.notOk(publish.checked, "failed browser checked state is restored");
        assert.notOk(publish.disabled);
        assert.notOk(featured.disabled);
        assert.strictEqual(notifications.length, 1);
        assert.strictEqual(action.state.viewMode, "dashboard", "toggle event does not open product detail");
    } finally {
        app.destroy();
        target.remove();
    }
});

QUnit.test('detail navigation groups preserve real keys and Analytics resolves to competitors without fetching providers', async (assert) => {
    const action = stabilizationAction();
    // Read labels from the real component through its group builder, not a mock callback.
    action.detailTabs = ['overview', 'datos', 'variants_pack', 'categorization', 'content', 'images', 'seo', 'mercadolibre', 'competitors', 'chat'].map((id) => ({ id, label: id }));
    let calls = 0;
    action.rpc = async () => { calls++; return { productId: 1, available: false, state: 'not_installed' }; };
    assert.strictEqual(action.detailNavGroups().length, 5);
    assert.strictEqual(action.detailNavGroups().flatMap((group) => group.tabs).length, 10);
    action.state.detail.product.isPack = false;
    action.state.detail.product.variantCount = 1;
    assert.strictEqual(action.detailNavGroups().flatMap((group) => group.tabs).length, 9);
    action.state.contentForm.description = 'Borrador retenido';
    await action.selectTab('analytics');
    assert.strictEqual(action.state.activeTab, 'competitors');
    await action.selectDetailSection({ target: { value: 'content' } });
    assert.strictEqual(action.state.contentForm.description, 'Borrador retenido');
    assert.strictEqual(calls, 0, 'normal internal section changes are local');
    await action.selectDetailSection('mercadolibre');
    assert.strictEqual(calls, 1, 'ML opens only its local read projection');
    await action.selectDetailSection('invalid');
    assert.strictEqual(action.state.activeTab, 'mercadolibre');
});

QUnit.test('detail completeness uses persisted server flags and unknown margin is not a zero score', (assert) => {
    const action = stabilizationAction();
    assert.deepEqual(action.detailChecklistItems(), [], 'metadata title fallback does not fabricate completeness');
    action.state.detail.product.catalogHealth = catalogRow().catalogHealth;
    assert.strictEqual(action.detailChecklistItems().length, 7);
    assert.strictEqual(action.detailChecklistItems().filter((item) => item.complete).length, 2);
    action.state.detail.product.costUsd = 0;
    assert.notOk(action.detailCurrentMarginKnown());
    Object.assign(action.state.detail.product, { effectiveCostMinUsd: 10, effectiveCostMaxUsd: 15, effectivePriceMinUsd: 20, effectivePriceMaxUsd: 30 });
    assert.ok(action.detailCurrentMarginKnown());
    action.state.detail.product.effectiveCostMinUsd = 0;
    assert.notOk(action.detailCurrentMarginKnown(), 'an unknown end of a variant/Pack range stays unknown');
});

QUnit.test('canonical draft baseline excludes display fields and retains edits made during a save', async (assert) => {
    const action = stabilizationAction();
    assert.notOk(action.detailHasUnsavedChanges());
    action.state.activeTab = 'images';
    action.state.selectedVariantId = 10;
    action.state.imageForm.selectedGalleryUrl = '/selected-image';
    assert.notOk(action.detailHasUnsavedChanges(), 'navigation and image selection are not persistent edits');
    action.state.contentForm.description = 'Submitted';
    assert.deepEqual(action.detailDirtySections().map((section) => section.id), ['content']);
    const pending = stabilizationDeferred();
    action.rpc = () => pending.promise;
    const saving = action.saveAll();
    action.state.contentForm.description = 'Typed while saving';
    pending.resolve(stabilizationPayload());
    await saving;
    assert.strictEqual(action.state.contentForm.description, 'Typed while saving');
    assert.ok(action.detailHasUnsavedChanges());
    action.rpc = async () => { throw new Error('Rejected'); };
    await action.saveAll();
    assert.strictEqual(action.state.contentForm.description, 'Typed while saving');
    assert.ok(action.detailHasUnsavedChanges(), 'failed saves do not reset baseline');
});

QUnit.test('detail leave stays or discards every independent draft without saving or automatically generating', async (assert) => {
    const action = stabilizationAction();
    action.state.contentForm.description = 'Pending description';
    action.state.variantDrafts[0].sku = 'Pending variant';
    action.state.packForm.modifiable = true;
    action.state.imageForm.generatedPreviewUrl = '/unsaved-preview';
    action.state.playground.inputText = 'Unsent image request';
    action.state.competitorForm.competitorUrl = 'https://example.com/pending';
    action.state.chatInput = 'Unsent chat';
    let calls = 0;
    action.rpc = async () => { calls++; return {}; };
    const staying = action.confirmDetailLeave();
    assert.notOk(action.state.detailLeavePrompt.canSave, 'atomic base save cannot commit independent operations');
    assert.ok(action.state.detailLeavePrompt.sections.some((section) => section.id === 'variants_pack'));
    await action.resolveDetailLeave('stay');
    assert.notOk(await staying);
    assert.ok(action.detailHasUnsavedChanges());
    const leaving = action.confirmDetailLeave();
    await action.resolveDetailLeave('discard');
    assert.ok(await leaving);
    assert.notOk(action.detailHasUnsavedChanges());
    assert.strictEqual(action.state.chatInput, '');
    assert.strictEqual(action.state.playground.inputText, '');
    assert.strictEqual(calls, 0);
});

QUnit.test('save and leave uses the atomic fiche and never leaves with newer or rejected drafts', async (assert) => {
    const action = stabilizationAction();
    action.state.productForm.brand = 'Pending';
    const pending = stabilizationDeferred();
    const calls = [];
    action.rpc = (route, params) => { calls.push({ route, params }); return pending.promise; };
    const leaving = action.confirmDetailLeave();
    assert.ok(action.state.detailLeavePrompt.canSave);
    const saving = action.resolveDetailLeave('save');
    action.state.productForm.brand = 'Newer';
    pending.resolve(stabilizationPayload());
    await saving;
    assert.ok(action.state.detailLeavePrompt, 'new edit blocks leaving');
    assert.strictEqual(calls[0].route, '/bader_product_intelligence/save_all');
    assert.strictEqual(calls[0].params.product_values.brand, 'Pending');
    await action.resolveDetailLeave('stay');
    assert.notOk(await leaving);
    action.rpc = async () => stabilizationPayload();
    const cleanLeave = action.confirmDetailLeave();
    await action.resolveDetailLeave('save');
    assert.ok(await cleanLeave);
    assert.notOk(action.detailHasUnsavedChanges());
});

QUnit.test('contextual save commits only the selected scope and blocks overlapping fiche writes', async (assert) => {
    const action = stabilizationAction();
    action.state.activeTab = 'datos';
    action.state.productForm.brand = 'Changed brand';
    action.state.contentForm.description = 'Unrelated draft';
    const calls = [];
    const pending = stabilizationDeferred();
    action.rpc = (route, params) => { calls.push({ route, params }); return pending.promise; };
    const saving = action.saveCurrentDetailSection();
    await action.saveAll();
    await action.saveSeoOnly();
    assert.strictEqual(calls.length, 1);
    assert.strictEqual(calls[0].route, '/bader_product_intelligence/update_product');
    assert.notOk(calls[0].params.content_values);
    pending.resolve(stabilizationPayload());
    await saving;
    assert.strictEqual(action.state.contentForm.description, 'Unrelated draft');
    assert.ok(action.detailDirtySections().some((section) => section.id === 'content'));
    action.state.activeTab = 'mercadolibre';
    await action.saveCurrentDetailSection();
    assert.strictEqual(calls.length, 1, 'Ctrl+S on read-only ML cannot submit product or channel data');
});

QUnit.test('all BPI calls capture selected company context and old-company requests cannot update state', async (assert) => {
    const action = stabilizationAction();
    action.user = { context: { allowed_company_ids: [2], lang: 'es_AR' } };
    const calls = [];
    action.rawRpc = async (route, params) => { calls.push({ route, params }); return {}; };
    const request = action.beginRequest('proof');
    for (const route of ['data', 'save_all', 'update_variant', 'meli/product_status', 'meli/refresh_status']) {
        await action.rpcWithContext(`/bader_product_intelligence/${route}`, { product_tmpl_id: 1 });
    }
    action.user.context.allowed_company_ids.push(3);
    assert.ok(calls.every((call) => JSON.stringify(call.params.context.allowed_company_ids) === '[2]'));
    assert.ok(calls.every((call) => call.params.context.lang === 'es_AR'));
    assert.notOk(action.isRequestCurrent(request));
    await action.rpcWithContext('/unrelated', { untouched: true });
    assert.deepEqual(calls[calls.length - 1].params, { untouched: true });
});

QUnit.test('ML filters account category quality search sort and pagination compose without changing existing KPI universe', async (assert) => {
    const action = dashboardAction();
    Object.assign(action.state, { meliAccountId: '8', meliFilter: 'review', dashboardCategoryId: '7', dashboardQualityFilter: 'needs_attention', searchTerm: 'SKU', dashboardSortKey: 'name_asc' });
    const calls = [];
    action.rpc = async (route, params) => { calls.push({ route, params }); return { products: [], meli: { available: true, accounts: [{ id: 8 }, { id: 9 }] } }; };
    await action.loadDashboard({ page: 2 });
    assert.deepEqual([calls[0].params.meli_account_id, calls[0].params.meli_filter, calls[0].params.category_id, calls[0].params.quality_filter, calls[0].params.search, calls[0].params.sort_key, calls[0].params.page], [8, 'review', 7, 'needs_attention', 'SKU', 'name_asc', 2]);
    await action.openDashboardMetric('seo');
    assert.notOk(calls[1].params.meli_filter, 'existing overview KPI drilldown clears independent ML filter');
    assert.strictEqual(calls[1].params.meli_account_id, 8);
    await action.openMeliFilter('prices');
    assert.strictEqual(calls[2].params.meli_filter, 'prices');
    assert.notOk(calls[2].params.quality_filter);
    assert.strictEqual(calls[2].params.search, '');
    await action.clearCatalogFilters();
    assert.notOk(action.state.meliFilter);
    assert.strictEqual(action.state.meliAccountId, '8', 'reset retains account and category');
    assert.strictEqual(action.state.dashboardCategoryId, '7');
});

QUnit.test('ML local read preserves drafts and unknown values never become zero or automatic refresh', async (assert) => {
    const action = stabilizationAction();
    action.state.contentForm.description = 'Draft';
    const calls = [];
    action.rpc = async (route, params) => { calls.push({ route, params }); return { productId: 1, available: true, canRefresh: false, state: 'read_disabled', groups: [], summary: { linked: true } }; };
    await action.loadMeliDetail();
    await action.requestMeliRefresh();
    assert.strictEqual(calls.length, 1);
    assert.strictEqual(calls[0].route, '/bader_product_intelligence/meli/product_status');
    assert.strictEqual(action.state.contentForm.description, 'Draft');
    assert.ok(action.detailHasUnsavedChanges());
    assert.strictEqual(action.meliValue(null), 'Sin verificar');
    assert.strictEqual(action.meliValue(undefined, 'ARS'), 'Sin verificar');
    assert.strictEqual(action.meliValue(0), '0', 'observed zero is a valid known stock value');
    assert.notOk(action.meliCanRefresh());
    assert.deepEqual(
        ['present', 'incomplete', 'conflict', 'blocked', 'ambiguous', 'not_applicable', 'retry', 'manual_excluded', 'stock', 'price', 'fulfillment', 'done', 'local_mirror'].map((value) => action.meliStateLabel(value)),
        ['Registrado', 'Incompleto', 'Conflicto de identidad', 'Bloqueado', 'Vínculo ambiguo', 'No corresponde', 'Reintento pendiente', 'Manual / excluido', 'Stock / estado', 'Precios', 'Full · depósito de Mercado Libre', 'Completado', 'Espejo local'],
        'bridge evidence, native task flow and logistics codes have explicit Spanish labels'
    );
});

QUnit.test('out-of-order ML account product and company responses cannot contaminate another scope', async (assert) => {
    const action = stabilizationAction();
    action.state.meliAccountId = '8';
    const first = stabilizationDeferred();
    action.rpc = (_route, params) => params.meli_account_id === 8 ? first.promise : Promise.resolve({ productId: 1, accountId: 9, groups: [] });
    const old = action.loadMeliDetail();
    action.state.meliAccountId = '9';
    await action.loadMeliDetail();
    first.resolve({ productId: 1, accountId: 8, groups: [{ key: 'OLD' }] });
    await old;
    assert.strictEqual(action.state.meliDetail.accountId, 9);
    assert.deepEqual(action.state.meliDetail.groups, []);
    const pending = stabilizationDeferred();
    action.rpc = () => pending.promise;
    const stale = action.loadMeliDetail();
    action.invalidateProductRequests();
    action.state.productId = 2;
    action.state.meliBusy = true;
    pending.reject(new Error('Old product failure'));
    await stale;
    assert.ok(action.state.meliBusy, 'old finally cannot clear a new request');
    assert.notOk(action.state.meliError);
});

QUnit.test('manual ML refresh polls only the requested local job and never restarts on failure or navigation', async (assert) => {
    const action = stabilizationAction();
    Object.assign(action.state, { meliAccountId: '8', meliDetail: { canRefresh: true }, meliRefreshBusy: false });
    const calls = [];
    action.rpc = async (route, params) => {
        calls.push({ route, params });
        if (route.endsWith('/refresh')) return { state: 'pending', job: { id: 12, state: 'pending' } };
        if (route.endsWith('/refresh_status')) return { state: 'failed', job: { id: 12, state: 'failed' }, message: 'Consulta fallida' };
        throw new Error('Unexpected route');
    };
    await action.requestMeliRefresh();
    assert.ok(action.state.meliRefreshBusy);
    assert.ok(action.meliPollTimer);
    action.clearMeliPoll();
    const request = { ...action.beginRequest('meliRefresh'), meliAccountId: '8' };
    await action.pollMeliRefresh(12, request);
    assert.notOk(action.state.meliRefreshBusy);
    assert.strictEqual(calls.length, 2);
    assert.strictEqual(calls[1].params.job_id, 12);
    action.invalidateProductRequests();
    await action.pollMeliRefresh(12, request);
    assert.strictEqual(calls.length, 2);
    assert.notOk(action.meliPollTimer);
});

async function workspacePatched() {
    await new Promise((resolve) => window.requestAnimationFrame(resolve));
    await new Promise((resolve) => setTimeout(resolve, 0));
}

function workspaceMeliPayload() {
    return {
        productId: 1, available: true, canRefresh: true, state: 'available', generatedAt: '2026-09-11T12:00:00Z', observedAt: false,
        accountId: 8, accounts: [{ id: 8, name: 'Cuenta QAS', companyId: 2, canRefresh: true }],
        summary: { label: 'Revisar', reason: 'Falta evidencia de precio', linked: true }, jobs: [],
        groups: [{ key: '8:10:UP1', accountId: 8, accountName: 'Cuenta QAS', productVariantId: 10, sku: 'VAR-1', userProductId: 'UP1', categoryId: 'MLA1', conditionState: 'partial',
            conditions: ['single', '3x', '6x'].map((key) => ({ key, label: key, state: key === 'single' ? 'present' : 'missing', itemIds: key === 'single' ? ['MLA1'] : [] })),
            items: [{ itemId: 'MLA1', variationId: false, title: 'Producto ML', url: '', status: 'active', subStatus: '', logisticType: 'self_service', manual: false,
                stock: { expected: 0, observed: 0, full: null, state: 'verified', observedAt: '2026-09-11T12:00:00Z', source: 'Observador', reason: 'Coincide' },
                price: { expected: 100, standard: null, sale: null, currency: 'ARS', state: 'unknown', observedAt: false, source: '', reason: 'Sin observar' },
                task: { state: 'pending', flow: 'stock', reason: 'Pendiente del integrador', checkedAt: false },
            }],
        }],
    };
}

QUnit.test('actual workspace sidebar mobile and ML controls retain draft state and request only local reads until explicit refresh', async (assert) => {
    const target = document.createElement('div');
    document.body.appendChild(target);
    const calls = [];
    const detail = stabilizationPayload();
    detail.product.catalogHealth = catalogRow().catalogHealth;
    const app = new App(ProductIntelligenceAction, {
        templates, test: true, props: { action: { params: { product_tmpl_id: 1 }, context: {} } },
        env: { services: {
            user: { context: { allowed_company_ids: [2] } }, notification: { add() {} }, action: { doAction() {} },
            rpc: async (route, params) => {
                calls.push({ route, params });
                if (route.endsWith('/data')) return detail;
                if (route.endsWith('/meli/product_status')) return workspaceMeliPayload();
                if (route.endsWith('/meli/refresh')) return { state: 'disabled', message: 'Consulta desactivada en fixture', job: false };
                throw new Error(`Unexpected provider or write: ${route}`);
            },
        } },
    });
    try {
        const action = await app.mount(target);
        assert.strictEqual(target.querySelectorAll('[data-detail-section]').length, 10);
        assert.strictEqual(target.querySelectorAll('.bpi-workspace-check').length, 7);
        assert.strictEqual(calls.length, 1, 'opening product does not request channel refresh or providers');
        target.querySelector('[data-detail-section="content"]').click();
        await workspacePatched();
        assert.strictEqual(action.state.activeTab, 'content');
        action.state.contentForm.description = 'Draft retained across navigation';
        await workspacePatched();
        assert.ok(target.querySelector('[data-detail-section="content"] .bpi-draft-dot'));
        const select = target.querySelector('#bpi-detail-section');
        select.value = 'seo';
        select.dispatchEvent(new Event('change', { bubbles: true }));
        await workspacePatched();
        assert.strictEqual(action.state.activeTab, 'seo');
        assert.strictEqual(calls.length, 1);
        target.querySelector('[data-detail-section="mercadolibre"]').click();
        await workspacePatched();
        assert.strictEqual(action.state.activeTab, 'mercadolibre');
        assert.strictEqual(calls[calls.length - 1].route, '/bader_product_intelligence/meli/product_status');
        assert.strictEqual(target.querySelectorAll('[data-meli-group]').length, 1);
        assert.strictEqual(target.querySelectorAll('.bpi-meli-condition').length, 3);
        assert.ok(target.querySelector('.bpi-meli-dimensions').textContent.includes('Sin verificar'));
        assert.strictEqual(action.state.contentForm.description, 'Draft retained across navigation');
        assert.notOk(target.querySelector('[data-meli-refresh]').disabled);
        target.querySelector('[data-meli-refresh]').click();
        await workspacePatched();
        assert.strictEqual(calls.filter((call) => call.route.endsWith('/meli/refresh')).length, 1);
        assert.ok(calls.every((call) => JSON.stringify(call.params.context.allowed_company_ids) === '[2]'));
        assert.notOk(action.meliPollTimer, 'disabled refresh does not begin automatic polling or retries');
    } finally { app.destroy(); target.remove(); }
});

QUnit.test('actual Odoo action beforeLeave and workspace dialog trap focus support Escape and protect native navigation', async (assert) => {
    const target = document.createElement('div');
    document.body.appendChild(target);
    const beforeLeave = new CallbackRecorder();
    let writes = 0;
    const app = new App(ProductIntelligenceAction, {
        templates, test: true, props: { action: { params: { product_tmpl_id: 1 }, context: {} } },
        env: { __beforeLeave__: beforeLeave, services: {
            user: { context: {} }, notification: { add() {} }, action: { doAction() {} },
            rpc: async (route) => {
                if (route.endsWith('/data')) return stabilizationPayload();
                if (route.endsWith('/save_all')) { writes++; return stabilizationPayload(); }
                throw new Error(`Unexpected RPC: ${route}`);
            },
        } },
    });
    try {
        const action = await app.mount(target);
        await workspacePatched();
        assert.strictEqual(beforeLeave.callbacks.length, 1, 'native action recorder registered by real useSetupAction');
        action.state.productForm.brand = 'Pending brand';
        const origin = target.querySelector('[data-bpi-back]');
        origin.focus();
        const stay = beforeLeave.callbacks[0]();
        await workspacePatched();
        const first = target.querySelector('[data-detail-leave="stay"]');
        const last = target.querySelector('[data-detail-leave="save"]');
        assert.ok(target.querySelector('[role="alertdialog"]'));
        assert.strictEqual(document.activeElement, first);
        first.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true, cancelable: true }));
        assert.strictEqual(document.activeElement, last);
        last.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true }));
        assert.strictEqual(document.activeElement, first);
        first.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }));
        assert.notOk(await stay);
        await workspacePatched();
        assert.strictEqual(document.activeElement, origin);
        assert.ok(action.detailHasUnsavedChanges());
        const ev = new Event('beforeunload', { cancelable: true });
        window.dispatchEvent(ev);
        assert.ok(ev.defaultPrevented, 'browser reload/close warns while draft exists');
        const save = beforeLeave.callbacks[0]();
        await workspacePatched();
        target.querySelector('[data-detail-leave="save"]').click();
        assert.ok(await save);
        await workspacePatched();
        assert.strictEqual(writes, 1);
        assert.notOk(target.querySelector('[role="alertdialog"]'));
        action.state.variantDrafts[0].sku = 'Independent draft';
        const discard = beforeLeave.callbacks[0]();
        await workspacePatched();
        assert.notOk(target.querySelector('[data-detail-leave="save"]'));
        target.querySelector('[data-detail-leave="discard"]').click();
        assert.ok(await discard);
        assert.strictEqual(writes, 1, 'discard never invokes independent mutations');
    } finally {
        app.destroy(); target.remove();
        assert.strictEqual(beforeLeave.callbacks.length, 0, 'native navigation callback is cleaned up');
    }
});

QUnit.test('canonical ML summary reuses selected account context while preserving already loaded same-scope groups', async (assert) => {
    const action = stabilizationAction();
    action.state.meliAccountId = '8';
    action.state.meliDetail = workspaceMeliPayload();
    action.meliDetailAccountKey = '8';
    const data = stabilizationPayload();
    data.product.meliSummary = { label: 'Resumen actualizado', linked: true };
    data.meli = { accountId: 8, available: true, accounts: [{ id: 8 }], canRefresh: true };
    action.applyDetailPayload(data);
    assert.strictEqual(action.state.meliDetail.summary.label, 'Resumen actualizado');
    assert.strictEqual(action.meliGroups().length, 1);
    let captured;
    action.rawRpc = async (_route, params) => { captured = params; };
    await action.rpcWithContext('/bader_product_intelligence/data', { product_tmpl_id: 1 });
    assert.strictEqual(captured.context.bpi_meli_account_id, 8);
    data.meli.accountId = 9;
    data.product.meliSummary.label = 'Otro ámbito';
    action.applyDetailPayload(data);
    assert.strictEqual(action.state.meliDetail.summary.label, 'Resumen actualizado', 'another account projection cannot replace selected-account summary');
    action.state.productId = 2;
    data.product.id = 2;
    data.meli.accountId = 8;
    action.applyDetailPayload(data);
    assert.deepEqual(action.meliGroups(), [], 'new product cannot retain prior listing groups');
});

QUnit.test('saving variant fields preserves its independent image draft and approved previews no longer look unsaved', async (assert) => {
    const action = stabilizationAction();
    const variant = action.currentVariants()[0];
    variant.sku = 'Submitted SKU';
    variant.imageUploadDataUrl = 'data:image/png;base64,pending';
    action.rpc = async () => stabilizationPayload();
    await action.saveVariant(variant);
    assert.strictEqual(action.currentVariants()[0].imageUploadDataUrl, 'data:image/png;base64,pending');
    assert.ok(action.detailDirtySections().some((section) => section.id === 'variants_pack'));
    action.discardDetailChanges();
    action.state.imageForm.generatedPreviewUrl = '/preview';
    await action.approveImage();
    assert.strictEqual(action.state.imageForm.generatedPreviewUrl, '');
    assert.notOk(action.detailDirtySections().some((section) => section.id === 'images'));
    action.state.imageForm.generatedPreviewUrl = '/newer-preview';
    action.acknowledgeImagePreview('/older-preview');
    assert.strictEqual(action.state.imageForm.generatedPreviewUrl, '/newer-preview');
});

QUnit.test('actual ML overview drilldown account filter and catalog link compose scope without channel mutations', async (assert) => {
    const target = document.createElement('div');
    document.body.appendChild(target);
    const calls = [];
    const context = { available: true, state: 'available', accounts: [{ id: 8, name: 'Cuenta 8' }, { id: 9, name: 'Cuenta 9' }] };
    const app = new App(ProductIntelligenceAction, {
        templates, test: true, props: { action: { params: {}, context: {} } },
        env: { services: {
            user: { context: { allowed_company_ids: [2] } }, notification: { add() {} }, action: { doAction() {} },
            rpc: async (route, params) => {
                calls.push({ route, params });
                if (route.endsWith('/dashboard_overview')) return { ...dashboardOverviewPayload(), meliOverview: { ...context, total: 1, kpis: ['linked', 'published', 'stock', 'prices', 'conditions', 'review'].map((key) => ({ key, filter: key, count: 1, percent: 100, label: key, description: key })) } };
                if (route.endsWith('/dashboard')) return { products: [{ ...catalogRow(1), meliSummary: workspaceMeliPayload().summary }], pager: { total: 1 }, meli: context };
                if (route.endsWith('/data')) return stabilizationPayload();
                if (route.endsWith('/meli/product_status')) return workspaceMeliPayload();
                throw new Error(`Unexpected ML write or refresh: ${route}`);
            },
        } },
    });
    try {
        const action = await app.mount(target);
        assert.strictEqual(target.querySelectorAll('[data-meli-kpi]').length, 6);
        const account = target.querySelector('#bpi-home-meli-account');
        account.value = '8';
        account.dispatchEvent(new Event('change', { bubbles: true }));
        await workspacePatched();
        assert.strictEqual(calls[calls.length - 1].params.meli_account_id, 8);
        target.querySelector('[data-meli-kpi="prices"]').click();
        await workspacePatched();
        assert.strictEqual(action.state.dashboardSection, 'catalog');
        assert.strictEqual(calls[calls.length - 1].params.meli_filter, 'prices');
        const filter = target.querySelector('#bpi-catalog-meli');
        filter.value = 'review';
        filter.dispatchEvent(new Event('change', { bubbles: true }));
        await workspacePatched();
        assert.strictEqual(calls[calls.length - 1].params.meli_filter, 'review');
        const count = calls.length;
        target.querySelector('[data-catalog-meli="1"]').click();
        await workspacePatched();
        assert.strictEqual(action.state.activeTab, 'mercadolibre');
        assert.strictEqual(action.state.productId, 1);
        assert.deepEqual(calls.slice(count).map((call) => call.route), ['/bader_product_intelligence/data', '/bader_product_intelligence/meli/product_status'], 'one detail plus one local ML read, without row bubbling');
        assert.strictEqual(calls[calls.length - 1].params.meli_account_id, 8);
        assert.ok(calls.every((call) => call.route.indexOf('/refresh') === -1));
    } finally { app.destroy(); target.remove(); }
});

QUnit.test('actual content generation shows safe configuration errors and preserves editable drafts', async (assert) => {
    const target = document.createElement('div'); document.body.appendChild(target);
    const calls = [], notifications = [];
    const app = new App(ProductIntelligenceAction, {
        templates, test: true, props: { action: { params: { product_tmpl_id: 1 }, context: {} } },
        env: { services: {
            user: { context: { allowed_company_ids: [3] } }, notification: { add: (message) => notifications.push(message) }, action: { doAction() {} },
            rpc: async (route, params) => {
                calls.push({ route, params });
                if (route.endsWith('/data')) return stabilizationPayload();
                if (route.endsWith('/generate_content')) throw { message: 'Odoo Server Error', data: { name: 'odoo.exceptions.UserError', message: 'Configura OpenAI API Key en Ajustes.', debug: 'Private debug never displayed' } };
                throw new Error('Unexpected write or provider request');
            },
        } },
    });
    try {
        const action = await app.mount(target);
        action.state.contentForm.description = 'Borrador comercial';
        action.state.contentForm.technicalDescription = 'Borrador técnico';
        action.state.contentForm.tone = 'tecnico';
        action.state.contentForm.audience = 'laboratorios';
        target.querySelector('[data-detail-section="content"]').click();
        await workspacePatched();
        [...target.querySelectorAll('button')].find(button => button.textContent.includes('Generar Descripciones con Nancy AI')).click();
        await workspacePatched();
        assert.deepEqual(calls.map(call => call.route), ['/bader_product_intelligence/data', '/bader_product_intelligence/generate_content']);
        assert.deepEqual(calls[1].params, { product_tmpl_id: 1, tone: 'tecnico', audience: 'laboratorios', context: { allowed_company_ids: [3] } });
        assert.deepEqual(notifications, ['Configura OpenAI API Key en Ajustes.']);
        assert.strictEqual(action.state.contentForm.description, 'Borrador comercial');
        assert.strictEqual(action.state.contentForm.technicalDescription, 'Borrador técnico');
        assert.notOk(action.state.contentBusy);
        assert.ok(action.detailHasUnsavedChanges());
    } finally { app.destroy(); target.remove(); }
});

QUnit.test('competitor collection failures warn after refresh while repeated paid actions are blocked', async (assert) => {
    for (const [method, args] of [['addCompetitor', ['Tienda', 'https://example.com/product']], ['scrapeCompetitor', [7]], ['analyzeCompetitor', [7]], ['discoverCompetitors', []], ['deleteCompetitor', [7]]]) {
        const action = stabilizationAction();
        const pending = stabilizationDeferred(); const calls = [], notices = [];
        action.notify = (message, type = 'success') => notices.push({ message, type });
        action.state.contentForm.description = 'Retained draft';
        action.rpc = (route) => { calls.push(route); return pending.promise; };
        let refreshes = 0; action.refreshDetail = async () => { refreshes++; };
        const operation = action[method](...args);
        await action[method](...args);
        assert.strictEqual(calls.length, 1, `${method}: duplicate request blocked synchronously`);
        pending.resolve({ competitor: { id: 7, scrapeStatus: 'failed', scrapeError: 'La página no respondió. Se conservan los datos anteriores.' }, competitors: [] });
        await operation;
        assert.notOk(action.state.competitorBusy);
        assert.strictEqual(action.state.contentForm.description, 'Retained draft');
        if (['addCompetitor', 'scrapeCompetitor'].includes(method)) {
            assert.strictEqual(refreshes, 1, 'reload persists failed attempt and prior valid evidence');
            assert.strictEqual(notices[0].type, 'warning', 'failed scrape never emits a green completion notice');
            assert.strictEqual(notices[0].message, 'La página no respondió. Se conservan los datos anteriores.');
        } else if (method === 'analyzeCompetitor') {
            assert.strictEqual(notices[0].type, 'success', 'a successful AI analysis is independent of historical scrape failure');
        }
    }
    const action = stabilizationAction();
    action.state.competitorForm.competitorUrl = 'https://example.com/submitted';
    const pending = stabilizationDeferred();
    action.rpc = () => pending.promise; action.refreshDetail = async () => {};
    const adding = action.addCompetitor();
    action.state.competitorForm.competitorUrl = 'https://example.com/new-draft';
    pending.resolve({ competitor: { scrapeStatus: 'done' } }); await adding;
    assert.strictEqual(action.state.competitorForm.competitorUrl, 'https://example.com/new-draft', 'completion does not discard a newer competitor URL draft');
    action.rpc = async () => ({ competitor: { scrapeStatus: 'done' } });
    await action.addCompetitor('Discovered', 'https://example.com/discovered');
    assert.strictEqual(action.state.competitorForm.competitorUrl, 'https://example.com/new-draft', 'adding a discovered result does not clear the separate URL form');
});

QUnit.test('competitor evidence distinguishes observed keywords AI suggestions and unknown prices without remote image loading', async (assert) => {
    const target = document.createElement('div'); document.body.appendChild(target);
    const detail = stabilizationPayload();
    detail.competitors = [{ id: 7, competitorName: 'Fixture competitor', competitorUrl: 'https://example.com/product',
        metaTitle: '', metaDescription: '', metaKeywords: ['observada'], metaKeywordsSource: 'page', recommendedKeywords: ['sugerida'], contentStrategy: 'Propuesta editorial',
        lastScrapedAt: '2026-09-11T12:01:00Z', lastSuccessfulScrapedAt: '2026-09-11T12:00:00Z', lastAnalyzedAt: '2026-09-11T12:02:00Z',
        scrapeStatus: 'done', scrapeSource: 'direct_http', priceStatus: 'ambiguous', priceSource: '', competitorPrice: 99, seoScore: 42,
        ogTitle: '', ogDescription: 'Descripción Open Graph', ogImage: 'http://127.0.0.1/private.png',
    }];
    const calls = [];
    const app = new App(ProductIntelligenceAction, {
        templates, test: true, props: { action: { params: { product_tmpl_id: 1 }, context: {} } },
        env: { services: { user: { context: {} }, notification: { add() {} }, action: { doAction() {} }, rpc: async route => { calls.push(route); if (route.endsWith('/data')) return detail; throw new Error('Unexpected request'); } } },
    });
    try {
        const action = await app.mount(target);
        target.querySelector('[data-detail-section="competitors"]').click(); await workspacePatched();
        const trigger = target.querySelector('[data-competitor-expand="7"]');
        assert.strictEqual(trigger.tagName, 'BUTTON', 'inspection is keyboard accessible');
        trigger.click(); await workspacePatched();
        assert.strictEqual(trigger.getAttribute('aria-expanded'), 'true');
        const observed = target.querySelector('[data-competitor-page-metadata]');
        assert.ok(observed.textContent.includes('Meta keywords de la página'));
        assert.ok(observed.textContent.includes('observada'), 'keywords-only page remains visible without title/description');
        assert.notOk(observed.textContent.includes('sugerida'), 'AI keywords never masquerade as page metadata');
        assert.ok(target.querySelector('[data-competitor-ai-recommendations]').textContent.includes('sugerida'));
        assert.ok(target.querySelector('.bpi-competitor-row__metrics').textContent.includes('No disponible'), 'ambiguous price is not presented as99 or0');
        assert.ok(target.querySelector('.bpi-competitor-expand').textContent.includes('Descripción Open Graph'));
        assert.strictEqual(target.querySelectorAll('.bpi-competitor-expand img').length, 0, 'inspection never auto-loads an untrusted OG image');
        assert.notOk(target.querySelector('a[href="http://127.0.0.1/private.png"]'));
        for (const url of ['javascript:alert(1)', 'https://user:pass@example.com/a.png', 'http://2130706433/a.png', 'http://[::1]/a.png', 'https://server.local/a.png']) assert.notOk(action.competitorExternalImageUrl(url));
        assert.strictEqual(action.competitorExternalImageUrl('https://cdn.example.com/a.png'), 'https://cdn.example.com/a.png');
        assert.strictEqual(action.competitorKeywordsLabel({ metaKeywordsSource: 'legacy_unknown' }), 'Keywords guardadas (origen no confirmado)');
        assert.strictEqual(action.competitorObservedPriceLabel({ priceStatus: 'unknown', competitorPrice: 0 }), 'No disponible');
        assert.strictEqual(action.competitorSeoEvidenceLabel({ seoScore: 0 }), 'Sin evaluar');
        action.state.competitorBusy = true; await workspacePatched();
        assert.ok(target.querySelector('[data-competitor-scrape="7"]').disabled);
        assert.ok(target.querySelector('[data-competitor-analyze="7"]').disabled);
        assert.deepEqual(calls, ['/bader_product_intelligence/data']);
    } finally { app.destroy(); target.remove(); }
});

QUnit.test('official Bader home logo stays local accessible and scoped while KPI navigation remains read-only', async (assert) => {
    const target = document.createElement('div');
    const nativeSibling = document.createElement('button');
    nativeSibling.className = 'btn btn-primary';
    nativeSibling.textContent = 'Native Odoo';
    document.body.append(target, nativeSibling);
    const bodyClasses = document.body.className;
    const calls = [];
    // This mounted navigation test needs the SEO card it clicks; keep the shared
    // minimal overview fixture unchanged for the pre-existing regression suite.
    const overview = dashboardOverviewPayload();
    overview.kpis.push({key: 'seo', label: 'Metadatos SEO completos', count: 0,
        percent: 0, filter: 'seo', description: 'Título y descripción SEO guardados.'});
    const app = new App(ProductIntelligenceAction, {
        templates, test: true, props: { action: { params: {}, context: {} } },
        env: { services: {
            user: { context: { allowed_company_ids: [1] } }, notification: { add() {} }, action: { doAction() {} },
            rpc: async (route, params) => {
                calls.push({route, params});
                if (route.endsWith('/dashboard_overview')) return overview;
                if (route.endsWith('/dashboard')) return {products: [], pager: {total: 0}};
                throw new Error('Brand navigation cannot call providers or writes: ' + route);
            },
        } },
    });
    try {
        await app.mount(target);
        assert.strictEqual(target.querySelectorAll('.o_action.bpi-app.bader-brand').length, 1);
        const logo = target.querySelector('[data-bader-brand-logo]');
        assert.ok(logo, 'home displays an official image instead of a recreated Bader wordmark');
        assert.strictEqual(logo.tagName, 'IMG');
        // Native Odoo tests/setup.js rewrites template src/alt to data-src/data-alt
        // to prevent resource loads. The real-browser harness checks src/alt.
        assert.strictEqual(logo.getAttribute('data-src'), '/bader_brand/static/src/img/bader_logotipo_verde_claro.svg');
        assert.strictEqual(logo.getAttribute('data-alt'), 'Bader');
        assert.ok(logo.closest('.bader-brand'), 'logo inherits only the owned module scope');
        assert.strictEqual(document.body.className, bodyClasses, 'never brand the global body');
        assert.strictEqual(nativeSibling.className, 'btn btn-primary', 'native sibling DOM untouched');
        assert.notOk(nativeSibling.closest('.bader-brand'));
        assert.strictEqual(calls.length, 1, 'brand adds no RPC at startup');
        target.querySelector('[data-kpi-key="seo"]').click();
        await workspacePatched();
        assert.ok(target.querySelector('.bpi-home--catalog.bpi-home'));
        assert.strictEqual(calls.length, 2);
        assert.strictEqual(calls[1].route, '/bader_product_intelligence/dashboard');
        assert.strictEqual(calls[1].params.quality_filter, 'seo');
        assert.strictEqual(target.querySelector('[data-bader-brand-logo]').getAttribute('data-src'), logo.getAttribute('data-src'));
    } finally { app.destroy(); target.remove(); nativeSibling.remove(); }
});

QUnit.test('official Bader detail scope preserves product identity editorial drafts and original section navigation', async (assert) => {
    const target = document.createElement('div');
    document.body.appendChild(target);
    const detail = stabilizationPayload();
    detail.product.brand = 'Product manufacturer';
    const calls = [];
    const app = new App(ProductIntelligenceAction, {
        templates, test: true, props: { action: { params: { product_tmpl_id: 1 }, context: {} } },
        env: { services: {
            user: { context: { allowed_company_ids: [1] } }, notification: { add() {} }, action: { doAction() {} },
            rpc: async route => {
                calls.push(route);
                if (route.endsWith('/data')) return detail;
                throw new Error('Brand detail navigation cannot request providers or writes: ' + route);
            },
        } },
    });
    try {
        const action = await app.mount(target);
        assert.strictEqual(target.querySelectorAll('.o_action.bpi-app.bader-brand').length, 1);
        assert.ok(target.querySelector('.bpi-detail-workspace').closest('.bader-brand'));
        assert.strictEqual(target.querySelector('.bpi-brand-badge').textContent, 'Product manufacturer', 'institutional brand must not overwrite manufacturer');
        assert.strictEqual(target.querySelectorAll('[data-bader-brand-logo]').length, 0, 'compact detail keeps product identity rather than inserting another logo');
        assert.deepEqual(calls, ['/bader_product_intelligence/data']);
        target.querySelector('[data-detail-section="content"]').click();
        await workspacePatched();
        assert.strictEqual(action.state.activeTab, 'content');
        action.state.contentForm.description = '<p>Editorial draft retained.</p>';
        const mobileSelect = target.querySelector('#bpi-detail-section');
        mobileSelect.value = 'seo';
        mobileSelect.dispatchEvent(new Event('change', {bubbles: true}));
        await workspacePatched();
        assert.strictEqual(action.state.activeTab, 'seo');
        assert.strictEqual(action.state.contentForm.description, '<p>Editorial draft retained.</p>');
        assert.ok(target.querySelector('[data-detail-section="content"] .bpi-draft-dot'));
        assert.deepEqual(calls, ['/bader_product_intelligence/data'], 'typography and navigation never start AI or ML refresh');
        assert.strictEqual(target.querySelectorAll('.o_action.bpi-app.bader-brand').length, 1, 'scope survives section replacement');
    } finally { app.destroy(); target.remove(); }
});

QUnit.module('Bader description templates');

function contentTemplateContext(selectionId = false, revision = 1) {
    const general = { id: 1, name: 'General Bader', revision, format: 'free', shortMinWords: 45, shortMaxWords: 70,
        longMinWords: 350, longMaxWords: 650, shortInstructions: 'Resumen comercial', longInstructions: 'Información ampliada' };
    const instrumental = { id: 2, name: 'Instrumental Bader', revision, format: 'two_sections', shortMinWords: 45,
        shortMaxWords: 70, longMinWords: 0, longMaxWords: 0, shortInstructions: 'Solo datos confirmados',
        longInstructions: '<script>instrucción no ejecutable</script> Dos párrafos y especificaciones verificadas.' };
    return {
        selectionId, effective: selectionId === 1 ? general : instrumental, options: [general, instrumental],
        internalCategory: { id: 94, name: 'Espátulas', path: 'Clínica / Instrumental / Espátulas' },
        source: selectionId ? { kind: 'manual', categoryId: false, categoryName: '', categoryPath: '' }
            : { kind: 'ancestor', categoryId: 11, categoryName: 'Instrumental', categoryPath: 'Clínica / Instrumental' },
    };
}

function contentTemplateAction(selectionId = false) {
    const action = stabilizationAction();
    action.applyDetailPayload({ ...stabilizationPayload(), contentTemplates: contentTemplateContext(selectionId) });
    return action;
}

function contentTemplateProposal(context = contentTemplateContext()) {
    return { name: 'Producto 1', descriptionHtml: '<p>Resumen propuesto</p>',
        technicalDescriptionHtml: '<h3>Descripción General</h3><p>Uno.</p><p>Dos.</p><h3>Especificaciones Técnicas</h3><p>Pendientes.</p>',
        contentTemplates: context, warnings: ['Faltan especificaciones confirmadas.'] };
}

QUnit.test('template selection is draft-only, uses internal category and explicit false restores Automatic', async (assert) => {
    const action = contentTemplateAction();
    const calls = [];
    action.rpc = async (route, params) => { calls.push({ route, params }); return contentTemplateContext(params.template_id); };
    assert.strictEqual(action.currentContentTemplate().name, 'Instrumental Bader');
    assert.ok(action.contentTemplateSourceLabel().includes('Heredado de Clínica / Instrumental'));
    assert.notOk(action.detailHasUnsavedChanges());
    action.state.contentForm.description = 'Texto pendiente';
    await action.changeContentTemplate({ target: { value: '1' } });
    assert.strictEqual(action.state.contentForm.templateId, 1);
    assert.strictEqual(action.currentContentTemplate().name, 'General Bader');
    assert.strictEqual(action.state.contentForm.description, 'Texto pendiente');
    assert.strictEqual(action.state.productForm.categoryId, '11', 'shop category is not repurposed');
    assert.strictEqual(action.state.contentTemplateContext.internalCategory.id, 94);
    assert.strictEqual(action.contentSaveValues().templateId, 1);
    assert.ok(action.detailDirtySections().some(section => section.id === 'content'));
    await action.changeContentTemplate({ target: { value: '' } });
    assert.strictEqual(action.state.contentForm.templateId, false);
    assert.strictEqual(action.contentSaveValues().templateId, false, 'explicit Automatic clears persisted override');
    assert.deepEqual(calls.map(call => call.route), Array(2).fill('/bader_product_intelligence/content_template_context'));
    assert.notOk(action.state.contentBusy, 'selection has not generated or saved content');
    const legacy = action.emptyContentForm(); delete legacy.templateId;
    assert.notOk(Object.hasOwn(action.contentSaveValues(legacy), 'templateId'), 'omitted legacy selection stays omitted');
});

QUnit.test('template targets are dynamic and Instrumental has no forced long minimum', (assert) => {
    const action = contentTemplateAction();
    assert.ok(action.contentWordCountLabel().includes('objetivo 45-70'));
    assert.ok(action.technicalDescriptionWordCountLabel().includes('sin mínimo obligatorio'));
    action.state.contentTemplateContext = contentTemplateContext(1);
    action.state.contentForm.templateId = 1;
    assert.ok(action.technicalDescriptionWordCountLabel().includes('objetivo 350-650'));
    action.state.contentTemplateContext.effective.longMinWords = 0;
    assert.strictEqual(action.contentTemplateWordTarget('long'), 'objetivo máximo 650');
    action.state.contentTemplateContext.effective.longMinWords = 100;
    action.state.contentTemplateContext.effective.longMaxWords = 0;
    assert.strictEqual(action.contentTemplateWordTarget('long'), 'objetivo mínimo 100');
});

QUnit.test('template context responses cannot cross choices, products or companies', async (assert) => {
    const action = contentTemplateAction();
    const first = stabilizationDeferred(), last = stabilizationDeferred();
    let calls = 0;
    action.rpc = () => (++calls === 1 ? first.promise : last.promise);
    const selectingFirst = action.changeContentTemplate(1);
    const selectingLast = action.changeContentTemplate(2);
    first.reject(new Error('Stale failure'));
    await selectingFirst;
    assert.ok(action.state.contentTemplateBusy, 'newer request owns busy state');
    assert.strictEqual(action.state.contentTemplateError, '');
    last.resolve(contentTemplateContext(2)); await selectingLast;
    assert.strictEqual(action.state.contentTemplateContext.selectionId, 2);
    assert.notOk(action.state.contentTemplateBusy);
    const old = stabilizationDeferred(); action.rpc = () => old.promise;
    const loading = action.refreshContentTemplateContext();
    action.invalidateProductRequests(); action.state.productId = 2;
    action.applyDetailPayload(stabilizationPayload(2));
    old.resolve(contentTemplateContext(2)); await loading;
    assert.strictEqual(action.state.contentTemplateContext, null);
    const companyAction = contentTemplateAction(); companyAction.user = { context: { allowed_company_ids: [1] } };
    const companyPending = stabilizationDeferred(); companyAction.rpc = () => companyPending.promise;
    const companyRead = companyAction.refreshContentTemplateContext();
    companyAction.user.context.allowed_company_ids = [2];
    companyPending.resolve(contentTemplateContext(1)); await companyRead;
    assert.strictEqual(companyAction.state.contentTemplateContext.selectionId, false, 'old company metadata discarded');
});

QUnit.test('generation preserves concurrent text edits and verifies current template with read-only metadata', async (assert) => {
    for (const editNameDuringGeneration of [false, true]) {
    const action = contentTemplateAction();
    action.state.contentForm.name = action.state.productForm.name = 'Nombre editado antes de generar';
    const pending = stabilizationDeferred(), calls = [];
    action.rpc = (route, params) => { calls.push({ route, params }); return route.endsWith('/generate_content') ? pending.promise : Promise.resolve(contentTemplateContext()); };
    const generating = action.generateContent();
    if (editNameDuringGeneration) action.state.contentForm.name = action.state.productForm.name = 'Nombre editado durante la generación';
    action.state.contentForm.description = 'Edición durante la generación';
    pending.resolve(contentTemplateProposal()); await generating;
    assert.strictEqual(calls.length, 2);
    assert.deepEqual(calls[0].params, { product_tmpl_id: 1, tone: 'profesional', audience: 'clinicas', template_id: false, template_revision: 1 });
    assert.strictEqual(calls[1].route, '/bader_product_intelligence/content_template_context');
    assert.strictEqual(action.state.contentForm.description, 'Edición durante la generación');
    const expectedName = editNameDuringGeneration ? 'Nombre editado durante la generación' : 'Nombre editado antes de generar';
    assert.strictEqual(action.state.contentForm.name, expectedName, 'saved-context name cannot overwrite an existing or newer draft');
    assert.strictEqual(action.state.productForm.name, expectedName, 'generation never updates canonical product name');
    assert.ok(action.state.contentForm.technicalDescription.includes('Descripción General'));
    assert.deepEqual(action.state.contentGenerationWarnings, ['Faltan especificaciones confirmadas.']);
    assert.notOk(action.state.contentBusy);
    assert.ok(action.detailHasUnsavedChanges(), 'proposal is not saved');
    }
});

QUnit.test('generation rejects template A-B-A changes even when final ID matches', async (assert) => {
    const action = contentTemplateAction();
    const pending = stabilizationDeferred(), calls = [];
    action.rpc = (route, params) => { calls.push(route); return route.endsWith('/generate_content') ? pending.promise : Promise.resolve(contentTemplateContext(params.template_id)); };
    const generating = action.generateContent();
    await action.changeContentTemplate(1); await action.changeContentTemplate(false);
    pending.resolve(contentTemplateProposal()); await generating;
    assert.strictEqual(action.state.contentForm.description, 'Resumen 1');
    assert.strictEqual(calls.filter(route => route.endsWith('/generate_content')).length, 1, 'no paid retry');
    assert.ok(action.notifications.some(message => message.includes('modelo cambió')));
    assert.notOk(action.state.contentBusy);
});

QUnit.test('generation rejects externally revised model or failed freshness check without replacing drafts', async (assert) => {
    for (const unavailable of [false, true]) {
        const action = contentTemplateAction(); const before = action.captureDrafts(); const calls = [];
        action.rpc = async (route) => {
            calls.push(route);
            if (route.endsWith('/generate_content')) return contentTemplateProposal();
            if (unavailable) throw new Error('Metadata unavailable');
            return contentTemplateContext(false, 2);
        };
        await action.generateContent();
        assert.deepEqual(action.captureDrafts(), before, 'all existing drafts remain unchanged');
        assert.strictEqual(calls.length, 2, 'one generation and one local freshness read only');
        assert.notOk(action.state.contentBusy);
        assert.ok(action.notifications.some(message => message.includes('No se aplicó la propuesta')));
    }
});

QUnit.test('incomplete template proposals and context failures preserve drafts without paid retries', async (assert) => {
    const action = contentTemplateAction(); const before = action.captureDrafts(); let calls = 0;
    action.rpc = async () => { calls++; return { ...contentTemplateProposal(), technicalDescriptionHtml: '<p><br></p>' }; };
    await action.generateContent();
    assert.strictEqual(calls, 1); assert.deepEqual(action.captureDrafts(), before);
    assert.notOk(action.state.contentBusy);
    action.rpc = async () => { calls++; throw { data: { name: 'odoo.exceptions.AccessError', message: 'No puedes consultar este modelo.' } }; };
    await action.changeContentTemplate(1);
    assert.strictEqual(action.state.contentTemplateError, 'No puedes consultar este modelo.');
    const afterFailure = calls;
    await action.generateContent();
    assert.strictEqual(calls, afterFailure, 'generation blocked until metadata can be verified');
    assert.strictEqual(action.state.contentForm.templateId, 1, 'failed read does not silently discard selection');
});

QUnit.test('atomic save retains a newer template selection and matching metadata as pending', async (assert) => {
    const action = contentTemplateAction(); const pending = stabilizationDeferred(); const calls = [];
    action.rpc = (route, params) => { calls.push({ route, params }); return route.endsWith('/save_all') ? pending.promise : Promise.resolve(contentTemplateContext(params.template_id)); };
    await action.changeContentTemplate(2);
    const saving = action.saveAll();
    await action.changeContentTemplate(1);
    action.state.contentForm.description = 'Más reciente que el guardado';
    pending.resolve({ ...stabilizationPayload(), contentTemplates: contentTemplateContext(2) }); await saving;
    const save = calls.find(call => call.route.endsWith('/save_all'));
    assert.strictEqual(save.params.content_values.templateId, 2);
    assert.strictEqual(action.state.contentForm.templateId, 1);
    assert.strictEqual(action.currentContentTemplate().name, 'General Bader', 'metadata follows retained draft, not older saved override');
    assert.strictEqual(action.state.contentForm.description, 'Más reciente que el guardado');
    assert.ok(action.detailHasUnsavedChanges());
    assert.strictEqual(calls.length, 3, 'one atomic save and explicit local selection lookups');
});

QUnit.test('failed save retains the selected template and every draft', async (assert) => {
    const action = contentTemplateAction(2);
    action.state.contentForm.templateId = false;
    action.state.contentForm.description = 'Resumen pendiente';
    const before = action.captureDrafts(); let calls = 0;
    action.rpc = async () => { calls++; throw new Error('Save rejected'); };
    await action.saveAll();
    assert.deepEqual(action.captureDrafts(), before);
    assert.strictEqual(calls, 1);
    assert.ok(action.detailHasUnsavedChanges());
    assert.notOk(action.state.saveBusy);
});

QUnit.test('model administration uses a modal and refreshes metadata only on close without losing drafts', async (assert) => {
    const action = contentTemplateAction(); let opened, options; const calls = [];
    action.user = { context: { allowed_company_ids: [2] } };
    action.state.contentForm.description = 'Rascunho conservado';
    const before = action.captureDrafts();
    action.action = { doAction: async (definition, opts) => { opened = definition; options = opts; } };
    action.rpc = async (route) => { calls.push(route); return contentTemplateContext(false, 2); };
    await action.manageContentTemplates();
    assert.strictEqual(opened.target, 'new'); assert.strictEqual(opened.res_model, 'bpi.content.template');
    assert.deepEqual(opened.context.allowed_company_ids, [2]);
    assert.strictEqual(calls.length, 0, 'opening the library does not generate or save product');
    assert.ok(action.state.contentTemplateAdminBusy);
    await options.onClose();
    assert.deepEqual(calls, ['/bader_product_intelligence/content_template_context']);
    assert.deepEqual(action.captureDrafts(), before);
    assert.strictEqual(action.currentContentTemplate().revision, 2);
    assert.notOk(action.state.contentTemplateAdminBusy);
});

QUnit.test('actual template selector exposes source instructions and manual selection without external or write calls', async (assert) => {
    const target = document.createElement('div'); document.body.appendChild(target);
    const calls = [];
    const detail = { ...stabilizationPayload(), contentTemplates: contentTemplateContext() };
    const app = new App(ProductIntelligenceAction, {
        templates, test: true, props: { action: { params: { product_tmpl_id: 1 }, context: {} } },
        env: { services: {
            user: { context: { allowed_company_ids: [2] } }, notification: { add() {} }, action: { doAction() {} },
            rpc: async (route, params) => {
                calls.push({ route, params });
                if (route.endsWith('/data')) return detail;
                if (route.endsWith('/content_template_context')) return contentTemplateContext(params.template_id);
                throw new Error('Unexpected provider or write');
            },
        } },
    });
    try {
        const action = await app.mount(target);
        target.querySelector('[data-detail-section="content"]').click(); await workspacePatched();
        const select = target.querySelector('#bpi-content-template-select');
        assert.ok(select); assert.strictEqual(select.value, '');
        assert.strictEqual(select.options.length, 3);
        assert.ok(target.querySelector('.bpi-content-template__status').textContent.includes('Clínica / Instrumental / Espátulas'));
        assert.ok(target.querySelector('.bpi-content-template__effective').textContent.includes('Instrumental Bader'));
        assert.notOk(target.querySelector('.bpi-content-template script'), 'instructions are escaped text, never executable HTML');
        const instructions = target.querySelector('.bpi-content-template__instructions');
        instructions.querySelector('summary').click(); await workspacePatched();
        assert.strictEqual(calls.length, 1, 'viewing instructions is fully local');
        assert.ok(instructions.textContent.includes('<script>instrucción no ejecutable</script>'));
        action.state.contentForm.description = 'Texto editable conservado';
        select.value = '1'; select.dispatchEvent(new Event('change', { bubbles: true })); await workspacePatched();
        assert.strictEqual(action.state.contentForm.templateId, 1);
        assert.strictEqual(target.querySelector('#bpi-content-template-select').value, '1');
        assert.ok(target.querySelector('.bpi-content-template__effective').textContent.includes('General Bader'));
        assert.strictEqual(action.state.contentForm.description, 'Texto editable conservado');
        assert.deepEqual(calls.map(call => call.route), ['/bader_product_intelligence/data', '/bader_product_intelligence/content_template_context']);
        assert.deepEqual(calls[1].params.context.allowed_company_ids, [2]);
        target.querySelector('[data-content-template-refresh]').click(); await workspacePatched();
        assert.strictEqual(calls.length, 3);
        assert.strictEqual(calls[2].route, '/bader_product_intelligence/content_template_context', 'explicit refresh reads local configuration only');
        assert.strictEqual(calls[2].params.template_id, 1, 'refresh retains the pending manual choice');
        assert.strictEqual(action.state.contentForm.description, 'Texto editable conservado');
        await action.selectDetailSection('seo'); await workspacePatched();
        assert.notOk(target.querySelector('#bpi-content-template-select'), 'leaving the section actually unmounts its select DOM');
        await action.selectDetailSection('content'); await workspacePatched();
        assert.strictEqual(target.querySelector('#bpi-content-template-select').value, '1', 'returning to section keeps selection');
        assert.ok(target.querySelector('[data-detail-section="content"] .bpi-draft-dot'));
    } finally { app.destroy(); target.remove(); }
});
