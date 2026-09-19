/** @odoo-module **/
import { App } from "@odoo/owl";
import { templates } from "@web/core/assets";
import { ProductIntelligenceAction } from "@bader_product_intelligence/js/product_intelligence_action";
import { emptyContentStudio, defaultDescriptionLayout } from "@bader_product_intelligence/js/content_studio";

QUnit.module("Nancy AI Studio and description design");
const copy = value => JSON.parse(JSON.stringify(value));
const later = () => { let resolve; const promise = new Promise(done => resolve = done); return { promise, resolve }; };
const patch = () => new Promise(resolve => requestAnimationFrame(() => setTimeout(resolve, 0)));
function payload(id = 1) {
    return { product: { id, name: "ALICATE 139 ANGLE PLANA", sku: "9/007-1", description: "<p>Guardado</p>", referenceImages: [] },
        seoData: { seoTitle: "Actual", seoKeywords: [], geoKeywords: [], geoFeatures: [], geoFaq: [] },
        images: [], variants: [], pack: { isPack: false, compositions: [] }, editorialRevision: 4,
        descriptionLayout: defaultDescriptionLayout(),
        classification: { revision: 1, vocabularyRevision: "v1", termIds: [3], terms: [{ id: 3, axis: "niche", name: "Estudiantes" }] } };
}
function proposal(id = 10) {
    return { id, revision: id, descriptionHtml: "<p>Resumen Nancy</p>", technicalDescriptionHtml: "<h3>Detalles</h3><p>Texto largo</p>",
        seoData: { seoTitle: "Nuevo SEO", seoDescription: "Descripción SEO", seoKeywords: ["alicate"], geoTitle: "Nuevo GEO", geoDescription: "Descripción GEO", geoKeywords: ["ortodoncia"], geoFeatures: ["precisión"] },
        warnings: [], conflicts: [], stale: false };
}
function envelope(proposals = [], sources = []) {
    return { session: { id: 7, productId: 1, revision: 2, brief: { ...emptyContentStudio().brief, nicheIds: [3] }, sources, messages: [], proposals, job: false },
        sessions: [{ id: 7, name: "Estrategia" }], availability: { enabled: true, reason: "" } };
}
function action() {
    const result = Object.create(ProductIntelligenceAction.prototype);
    result.state = { productId: 1, viewMode: "detail", activeTab: "content", contentStudio: emptyContentStudio(), descriptionMedia: [],
        playground: { messages: [], canvasUrl: "", inputText: "" } };
    result.user = { context: { allowed_company_ids: [2] } };
    result.applyDetailPayload(payload()); result.notify = () => {};
    result.syncContentDescriptionEditor = result.syncTechnicalDescriptionEditor = () => {};
    result.studioEnvelope(envelope([proposal()]), { brief: true, proposal: true });
    result.studioDraftBaseline = result.captureDrafts();
    return result;
}

QUnit.test("opening Studio performs one local request and preserves current product drafts", async assert => {
    const a = action(), calls = [];
    a.state.contentStudio = emptyContentStudio(); a.state.contentForm.description = "Unsaved description";
    a.rpc = async (route, params) => { calls.push({ route, params }); return envelope(); };
    await a.openContentStudio();
    assert.strictEqual(calls.length, 1); assert.ok(calls[0].route.endsWith("/content_studio/open"));
    assert.strictEqual(a.state.contentForm.description, "Unsaved description");
    assert.ok(a.state.contentStudio.open); assert.notOk(a.studioPollTimer);
    assert.deepEqual(a.state.contentStudio.brief.nicheIds, [3]);
});

QUnit.test("old product and company Studio responses cannot overwrite another scope", async assert => {
    for (const changed of ["product", "company"]) {
        const a = action(), pending = later(); a.state.contentStudio = emptyContentStudio();
        a.rpc = () => pending.promise; const opening = a.openContentStudio();
        if (changed === "product") { a.invalidateProductRequests(); a.state.productId = 2; }
        else a.user.context.allowed_company_ids = [5];
        pending.resolve(envelope()); await opening;
        assert.notOk(a.state.contentStudio.session, changed);
    }
});

QUnit.test("source review is explicit and pending evidence disables generation", async assert => {
    const a = action(), calls = [];
    a.studioEnvelope(envelope([], [{ id: 2, state: "pending", name: "Fabricante", facts: [{ id: "f1", text: "Dato" }] }]));
    assert.notOk(a.studioCanGenerate());
    a.rpc = async (route, params) => { calls.push({ route, params }); return envelope([], [{ id: 2, state: "reviewed" }]); };
    await a.studioReviewSource(a.state.contentStudio.session.sources[0], "approve");
    assert.strictEqual(calls.length, 1); assert.ok(calls[0].route.endsWith("review_source"));
    assert.ok(a.studioCanGenerate());
});

QUnit.test("draft-only apply sends explicit selections and never changes name, dimensions, FAQs or layout", async assert => {
    const a = action(), calls = [];
    a.state.contentForm.descriptionLayout.enabled = true;
    a.state.contentForm.faqs = [{ question: "Guardada", answer: "Conservar" }];
    const before = copy(a.state.contentForm);
    a.rpc = async (route, params) => { calls.push({ route, params }); return { contentValues: { descriptionHtml: "<p>Nueva corta</p>", technicalDescriptionHtml: "<p>Nueva larga</p>", editorialRevision: 4 }, seoData: proposal().seoData, proposalId: 10 }; };
    await a.studioApply();
    assert.strictEqual(calls.length, 1); assert.ok(calls[0].route.endsWith("prepare_apply"));
    assert.strictEqual(a.state.contentForm.description, "<p>Nueva corta</p>");
    assert.strictEqual(a.state.contentForm.name, before.name); assert.deepEqual(a.state.contentForm.faqs, before.faqs);
    assert.deepEqual(a.state.contentForm.descriptionLayout, before.descriptionLayout);
    assert.strictEqual(a.state.seoForm.seoTitle, "Nuevo SEO"); assert.ok(a.detailHasUnsavedChanges());
    assert.notOk(calls.some(call => /save|publish/.test(call.route)));
});

QUnit.test("apply keeps edits performed while prepare_apply is in flight", async assert => {
    const a = action(), pending = later(); a.rpc = () => pending.promise;
    const applying = a.studioApply(); a.state.contentForm.description = "Edición durante la solicitud";
    pending.resolve({ contentValues: { descriptionHtml: "Old proposal", technicalDescriptionHtml: "Long valid", editorialRevision: 4 }, seoData: {}, proposalId: 10 });
    await applying;
    assert.strictEqual(a.state.contentForm.description, "Edición durante la solicitud");
    assert.strictEqual(a.state.contentForm.technicalDescription, "Long valid");
    assert.ok(a.state.contentStudio.error.includes("Se conservaron"));
});

QUnit.test("changed baseline requires explicit overwrite and stale proposal is never applied", async assert => {
    const a = action(); let calls = 0; a.rpc = async () => { calls++; return {}; };
    a.state.contentForm.description = "User changed"; await a.studioApply();
    assert.strictEqual(calls, 0); assert.ok(a.state.contentStudio.error.includes("La ficha cambió"));
    a.state.contentStudio.replaceChanged = true; a.state.contentStudio.session.proposals[0].stale = true;
    await a.studioApply(); assert.strictEqual(calls, 0);
});

QUnit.test("polling preserves preview edits, brief drafts and initial intent", async assert => {
    const a = action(); a.state.contentStudio.preview.descriptionHtml = "<p>Edición local</p>";
    a.state.contentStudio.brief.intent = "Foco educativo"; a.state.contentStudio.input = "Mensaje pendiente";
    a.rpc = async () => envelope([proposal(11), proposal(10)]);
    await a.studioRefresh();
    assert.strictEqual(a.state.contentStudio.preview.descriptionHtml, "<p>Edición local</p>");
    assert.strictEqual(a.state.contentStudio.brief.intent, "Foco educativo");
    assert.strictEqual(a.state.contentStudio.input, "Mensaje pendiente"); assert.ok(a.state.contentStudio.pendingProposals);
    a.studioSelectProposal(11); assert.strictEqual(a.state.contentStudio.proposalId, 10, "unsaved preview isn't discarded by version selection");
});

QUnit.test("explicit refinement sends UUID and structured edited metadata without paid retries", async assert => {
    const a = action(), calls = []; a.state.contentStudio.input = "Más natural";
    a.rpc = async (route, params) => { calls.push({ route, params }); throw new Error("provider raw private detail"); };
    await a.studioSend();
    assert.strictEqual(calls.length, 1); assert.ok(calls[0].route.endsWith("/start"));
    assert.ok(/^[0-9a-f-]{36}$/i.test(calls[0].params.request_key));
    assert.deepEqual(calls[0].params.draft.seoData.seoKeywords, ["alicate"]);
    assert.strictEqual(a.state.contentStudio.input, "Más natural");
    assert.notOk(a.state.contentStudio.error.includes("provider")); assert.notOk(a.studioPollTimer);
});

QUnit.test("canonical main block cannot be duplicated or removed and regeneration preserves media", assert => {
    const a = action(), original = a.state.contentForm.technicalDescription;
    a.addDescriptionBlock("columns");
    const columns = a.descriptionLayout().blocks[1];
    columns.children[0].mediaId = 42;
    a.duplicateDescriptionBlock("principal"); a.removeDescriptionBlock("principal");
    a.duplicateDescriptionBlock(columns.children[0].id);
    assert.strictEqual(columns.children.length, 2, "columns stay within limit");
    assert.strictEqual(a.descriptionLayout().blocks.filter(block => block.type === "main").length, 1);
    assert.strictEqual(a.state.contentForm.technicalDescription, original, "enabling design never rewrites copy");
    a.state.contentForm.technicalDescription = "New canonical copy";
    assert.strictEqual(columns.children[0].mediaId, 42, "media is independent of canonical copy");
    assert.notOk("url" in a.newDescriptionBlock("image")); assert.notOk("alt" in a.newDescriptionBlock("video"));
});

QUnit.test("layout unlink and disabling do not delete underlying gallery media", assert => {
    const a = action(); a.rpc = () => { throw new Error("No mutation allowed"); };
    a.addDescriptionBlock("image"); a.descriptionLayout().blocks[1].mediaId = 21;
    a.removeDescriptionBlock(a.descriptionLayout().blocks[1].id);
    a.toggleDescriptionDesign({ target: { checked: false } });
    assert.deepEqual(a.descriptionLayout().blocks.map(block => block.type), ["main"]);
    assert.notOk(a.descriptionLayout().enabled);
});

QUnit.test("layout and private source changes are protected by the existing leave flow", assert => {
    const a = action(); a.addDescriptionBlock("callout");
    assert.ok(a.detailDirtySections().some(section => section.id === "content"));
    a.state.contentStudio.sourceText = "Texto sin adjuntar";
    assert.ok(a.detailDirtySections().some(section => section.id === "studio"));
    assert.notOk(a.detailCanSaveBeforeLeave(), "Guardar ficha can't claim to save unfinished source notes");
});

QUnit.test("partial save metadata rebases only from exact atomic acknowledgement", async assert => {
    const a = action(); const request = a.beginRequest("save", true); request.editorialAck = 5;
    a.state.contentForm.description = "Keep unsaved content";
    a.applyDetailUpdate({ ...payload(), editorialRevision: 5 }, request, { productForm: true });
    assert.strictEqual(a.state.contentForm.editorialRevision, 5); assert.strictEqual(a.state.contentForm.description, "Keep unsaved content");
    const stale = a.beginRequest("save", true); stale.editorialAck = 6;
    a.rpc = async () => ({ ...payload(), editorialRevision: 7 });
    await a.refreshDetail(stale, { seoForm: true });
    assert.strictEqual(a.state.contentForm.editorialRevision, 5, "newer third-party state cannot authorize stale drafts");
});

QUnit.test("actual mounted modal and designer render, edit, preserve drafts and never call generators on open", async assert => {
    const target = document.createElement("div"); document.body.appendChild(target);
    const calls = [];
    const app = new App(ProductIntelligenceAction, { templates, test: true,
        props: { action: { params: { product_tmpl_id: 1 }, context: {} } },
        env: { services: { user: { context: { allowed_company_ids: [2] } }, notification: { add() {} }, action: { doAction() {} },
            rpc: async (route, params) => { calls.push({ route, params });
                if (route.endsWith("/data")) return payload();
                if (route.endsWith("/content_studio/open")) return envelope([proposal()]);
                if (route.endsWith("/description_media/list")) return { media: [] };
                throw new Error("Unexpected provider/write: " + route);
            } } } });
    try {
        const a = await app.mount(target); await a.selectDetailSection("content"); await patch();
        a.state.contentForm.description = "Draft principal";
        await a.openContentStudio(); await patch();
        assert.ok(target.querySelector('[role="dialog"]')); assert.ok(target.querySelector(".bpi-studio-rich__surface"));
        assert.strictEqual(target.querySelectorAll(".bpi-studio__niches input").length, 1);
        assert.strictEqual(target.querySelector(".bpi-studio__mobile-tabs [role=tab]").getAttribute("aria-selected"), "true", "OWL must render the ARIA string, not an empty boolean attribute");
        assert.strictEqual(target.querySelector(".bpi-studio__preview-tabs [role=tab]").getAttribute("aria-selected"), "true");
        assert.strictEqual(target.querySelectorAll(".bpi-studio__preview-tabs [aria-selected=false]").length, 3);
        const editor = target.querySelector(".bpi-studio-rich__surface"); editor.focus(); editor.innerHTML = "<p>Edited preview</p>";
        editor.dispatchEvent(new Event("input", { bubbles: true })); await patch();
        assert.strictEqual(a.state.contentStudio.preview.descriptionHtml, "<p>Edited preview</p>");
        a.closeContentStudio(); await patch(); assert.strictEqual(a.state.contentForm.description, "Draft principal");
        a.setDescriptionMode("design"); a.addDescriptionBlock("columns"); await patch();
        assert.ok(target.querySelector(".bpi-designer")); assert.strictEqual(target.querySelectorAll(".bpi-design-columns .bpi-design-block").length, 2);
        assert.strictEqual(target.querySelectorAll(".bpi-description-mode [aria-selected=true]").length, 1);
        assert.ok(target.querySelector(".bpi-description-mode [aria-selected=true]").textContent.includes("Diseño"));
        a.addDescriptionBlock("video"); await patch();
        const videoBlock = a.descriptionLayout().blocks.at(-1);
        const width = target.querySelector('[aria-label="Ancho del vídeo"]');
        width.value = "55"; width.dispatchEvent(new Event("input", { bubbles: true })); await patch();
        assert.strictEqual(videoBlock.videoWidth, 55, "OWL width handler converts values outside template globals");
        a.state.descriptionMedia = [{id: 43, kind: "image", state: "ready", filename: "Portada"}]; await patch();
        const poster = target.querySelector('[aria-label="Portada del vídeo"]');
        poster.value = "43"; poster.dispatchEvent(new Event("change", { bubbles: true })); await patch();
        assert.strictEqual(videoBlock.posterMediaId, 43, "OWL cover selector saves a numeric draft ID");
        poster.value = ""; poster.dispatchEvent(new Event("change", { bubbles: true })); await patch();
        assert.strictEqual(videoBlock.posterMediaId, false);
        assert.ok(calls.every(call => /\/(data|open|list)$/.test(call.route)), "no generation, fetching sources or persistence");
        assert.ok(calls.every(call => call.params.context.allowed_company_ids[0] === 2), "all RPCs carry company context");
    } finally { app.destroy(); target.remove(); }
});

QUnit.test("successful content acknowledgement consumes only the applied one-shot reference", assert => {
    const a = action(); a.state.contentForm.studioProposalId = 10;
    const request = a.beginRequest("save", true); request.editorialAck = 5;
    a.applyDetailUpdate({ ...payload(), editorialRevision: 5 }, request, { contentForm: true });
    assert.notOk(a.state.contentForm.studioProposalId);
    a.state.contentForm.studioProposalId = 11;
    const laterSave = a.beginRequest("save", true); a.state.contentForm.studioProposalId = 12;
    a.applyDetailUpdate({ ...payload(), editorialRevision: 6 }, laterSave, { contentForm: true });
    assert.strictEqual(a.state.contentForm.studioProposalId, 12, "newly applied proposal isn't consumed by an older save");
});

QUnit.test("resumable video retries same selected file without duplicate start and preserves company context", async assert => {
    const a = action(), original = window.fetch, calls = [], chunks = [];
    a.addDescriptionBlock("video"); const block = a.descriptionLayout().blocks[1];
    const file = new File([new Uint8Array(2 * 1048576)], "demo.mp4", { type: "video/mp4", lastModified: 120 });
    let fail = true;
    a.rpc = async (route, params) => {
        calls.push({ route, params });
        if (route.endsWith("/start")) return { id: 55, offset: 0, chunkSize: 1048576, csrfToken: "controlled-csrf" };
        if (route.endsWith("/complete")) return { id: 55, kind: "video", state: "ready", previewUrl: "/private/55" };
        throw new Error("Unexpected mutation");
    };
    window.fetch = async (_url, options) => {
        const offset = Number(options.body.get("offset")); chunks.push(offset);
        assert.strictEqual(JSON.parse(options.body.get("context")).allowed_company_ids[0], 2);
        assert.strictEqual(options.body.get("csrf_token"), "controlled-csrf");
        if (offset === 1048576 && fail) { fail = false; throw new Error("Connection lost"); }
        return { ok: true, json: async () => ({ offset: offset + 1048576 }) };
    };
    try {
        await a.uploadDescriptionMedia({ target: { files: [file], value: "" } }, block.id);
        assert.ok(a.state.descriptionMediaError); assert.strictEqual(a.descriptionUploadSession.offset, 1048576);
        await a.uploadDescriptionMedia({ target: { files: [file], value: "" } }, block.id);
        assert.deepEqual(chunks, [0, 1048576, 1048576]); assert.strictEqual(calls.filter(call => call.route.endsWith("/start")).length, 1);
        assert.strictEqual(block.mediaId, 55); assert.notOk(a.descriptionUploadSession);
    } finally { window.fetch = original; }
});

QUnit.test("Studio displays safe quota guidance but hides provider details", assert => {
    const a = action(), fallback = "Nancy AI no está disponible.";
    assert.strictEqual(a.studioError({ data: { name: "odoo.exceptions.UserError", message: "Conserva al menos 3 GiB libres." } }, fallback), "Conserva al menos 3 GiB libres.");
    for (const message of ["OpenAI missing", "gpt-6-astra unavailable", "reasoning.effort failed", "Traceback internal"]) {
        assert.strictEqual(a.studioError({ data: { name: "odoo.exceptions.UserError", message } }, fallback), fallback);
    }
});

QUnit.test("selective apply changes only checked fields and keeps unselected SEO GEO long drafts", async assert => {
    const a = action(), before = a.captureDrafts();
    a.state.contentStudio.selected = { short: true, long: false, seo: false, geo: false };
    a.rpc = async (route, params) => {
        assert.deepEqual(params.selected, ["short"]);
        return { contentValues: { descriptionHtml: "<p>Solo corta</p>", editorialRevision: 4 }, seoData: {}, proposalId: 10 };
    };
    await a.studioApply();
    assert.strictEqual(a.state.contentForm.description, "<p>Solo corta</p>");
    assert.strictEqual(a.state.contentForm.technicalDescription, before.contentForm.technicalDescription);
    assert.deepEqual(a.state.seoForm, before.seoForm);
});

QUnit.test("shared strategy refresh updates clean brief but flags concurrent operator drafts", assert => {
    const a = action(), first = envelope([proposal()]);
    first.session.revision = 3; first.session.brief.intent = "Nueva estrategia del equipo";
    a.studioEnvelope(first);
    assert.strictEqual(a.state.contentStudio.brief.intent, "Nueva estrategia del equipo");
    assert.notOk(a.state.contentStudio.briefConflict);
    a.state.contentStudio.brief.intent = "Mi edición pendiente";
    const second = envelope([proposal()]); second.session.revision = 4; second.session.brief.intent = "Otra edición guardada";
    a.studioEnvelope(second);
    assert.strictEqual(a.state.contentStudio.brief.intent, "Mi edición pendiente");
    assert.ok(a.state.contentStudio.briefConflict); assert.notOk(a.studioCanGenerate());
    a.studioDiscardLocal();
    assert.strictEqual(a.state.contentStudio.brief.intent, "Otra edición guardada"); assert.notOk(a.state.contentStudio.briefConflict);
});

QUnit.test("video sizing keeps saved text and layout independent", assert => {
    const a = action(), text = a.state.contentForm.technicalDescription;
    a.addDescriptionBlock("video");
    const v = a.descriptionLayout().blocks.at(-1);
    assert.strictEqual(v.videoWidth, 100); assert.strictEqual(v.videoRatio, "auto");
    a.updateDescriptionBlock(v.id, "videoWidth", 50); a.updateDescriptionBlock(v.id, "videoRatio", "9:16");
    assert.ok(a.descriptionVideoStyle(v).includes("width:50%")); assert.ok(a.descriptionVideoStyle(v).includes("ratio:9/16"));
    assert.strictEqual(a.state.contentForm.technicalDescription, text);
    v.videoRatio = "auto"; v.mediaId = 17; a.state.descriptionMedia = [{id:17,width:1080,height:1920}];
    assert.ok(a.descriptionVideoStyle(v).includes("1080/1920"));
});

QUnit.test("a late video cover never replaces a changed URL or chosen cover", async assert => {
    const a = action(), pending = later(); a.addDescriptionBlock("video");
    const v = a.descriptionLayout().blocks.at(-1); v.url = "https://youtu.be/abcdefghijk";
    a.rpc = () => pending.promise;
    const work = a.fetchDescriptionPoster(v.id); v.url = "https://youtu.be/12345678901"; v.posterMediaId = 81;
    pending.resolve({media:{id:99,kind:"image",state:"ready"}}); await work;
    assert.strictEqual(v.posterMediaId,81); assert.notOk(a.state.descriptionMediaBusy);
});

QUnit.test("explicit video poster fetch applies only private draft reference", async assert => {
    const a = action(); a.addDescriptionBlock("video");
    const v = a.descriptionLayout().blocks.at(-1); v.url = "https://youtu.be/abcdefghijk";
    a.rpc = async (url,params) => { assert.ok(url.endsWith("/video_poster")); assert.strictEqual(params.product_tmpl_id,1); return {media:{id:82,kind:"image",state:"ready"}}; };
    await a.fetchDescriptionPoster(v.id); assert.strictEqual(v.posterMediaId,82); assert.strictEqual(a.state.descriptionMedia.length,1);
});
