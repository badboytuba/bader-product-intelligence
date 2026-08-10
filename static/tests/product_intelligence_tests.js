/** @odoo-module **/

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

QUnit.test("gallery deletion is conditioned by canDelete and bpi token", async (assert) => {
    assert.notOk(canDeleteGalleryImage({ canDelete: false, referenceToken: "main" }));
    assert.notOk(canDeleteGalleryImage({ canDelete: true, referenceToken: "odoo:8" }));
    assert.ok(canDeleteGalleryImage({ canDelete: true, referenceToken: "bpi:8" }));

    const calls = [];
    const action = Object.create(ProductIntelligenceAction.prototype);
    action.state = { productId: 7, imageBusy: false };
    action.rpc = async (route, payload) => calls.push({ route, payload });
    action.loadDetail = async () => {};
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
        seoData: {},
        images: [],
        chatHistory: [{ role: "assistant", content: "Historial B" }],
        chatSessionId: "session-b",
        exchangeRate: 1650,
    });

    assert.deepEqual(action.state.chatMessages, [{ role: "assistant", content: "Historial B" }]);
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
