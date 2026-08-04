/** @odoo-module **/

import {
    ProductIntelligenceAction,
    canDeleteGalleryImage,
    competitorComparablePriceUsd,
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
