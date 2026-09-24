/** @odoo-module **/
// Content Studio uses the product action's scope, company and draft protections.
import { markup, Component, useRef, onMounted, onPatched } from "@odoo/owl";

const STUDIO = "/bader_product_intelligence/content_studio/";
const MEDIA = "/bader_product_intelligence/description_media/";
const SEO_KEYS = ["seoTitle", "seoDescription", "seoKeywords"];
const GEO_KEYS = ["geoTitle", "geoDescription", "geoKeywords", "geoFeatures"];
const clone = (value) => JSON.parse(JSON.stringify(value));
const uid = () => {
    if (window.crypto?.randomUUID) return window.crypto.randomUUID();
    const bytes = window.crypto.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128;
    const h = [...bytes].map(value => value.toString(16).padStart(2, "0")).join("");
    return `${h.slice(0,8)}-${h.slice(8,12)}-${h.slice(12,16)}-${h.slice(16,20)}-${h.slice(20)}`;
};

// DOM ownership while typing avoids cursor resets from controlled HTML updates.
export class StudioRichEditor extends Component {
    setup() {
        this.editor = useRef("studioRichEditor");
        onMounted(() => this.sync());
        onPatched(() => this.sync());
    }
    sync() {
        const el = this.editor.el;
        if (el && document.activeElement !== el && el.innerHTML !== this.props.value) el.innerHTML = this.props.value || "";
    }
    change() { this.props.onChange(this.editor.el?.innerHTML || ""); }
    blur() { this.change(); }
    paste(ev) {
        ev.preventDefault();
        const rich = ev.clipboardData?.getData("text/html");
        const text = ev.clipboardData?.getData("text/plain") || "";
        const container = document.createElement("div"); container.textContent = text;
        const safe = this.props.sanitize(rich || container.innerHTML.replace(/\n/g, "<br>"));
        this.editor.el?.focus(); document.execCommand("insertHTML", false, safe); this.change();
    }
    command(command) { this.editor.el?.focus(); document.execCommand(command, false); this.change(); }
}
StudioRichEditor.template = "bader_product_intelligence.StudioRichEditor";
StudioRichEditor.props = { value: { type: String, optional: true }, onChange: Function, sanitize: Function, label: String };

export function emptyContentStudio() {
    return { open: false, busy: false, loading: false, error: "", notice: "", session: null,
        sessions: [], availability: {}, nicheOptions: [], mobileTab: "conversation", previewTab: "short", compareId: "",
        brief: { objective: "consultivo", tone: "profesional", nicheIds: [], shortFocus: "", longFocus: "", intent: "" },
        input: "", sourceKind: "text", sourceName: "", sourceText: "", sourceUrl: "", sourceSelections: {},
        proposalId: false, preview: { descriptionHtml: "", technicalDescriptionHtml: "", seoData: {} },
        selected: { short: true, long: true, seo: true, geo: true }, replaceChanged: false, closeConfirm: false,
        savedBrief: "", briefConflict: false, savedPreview: "", pendingProposals: false, previewDrafts: {},
        awaitedJobId: false, generationPreview: "", generationProposalId: false,
        reuseOpen: false, reuseSearch: "", reuseOptions: [], reuseId: "", reuseBrief: null, reuseReviewed: false,
    };
}

export function defaultDescriptionLayout() {
    return { version: 1, enabled: false, blocks: [{ id: "principal", type: "main", preset: "white", align: "left", effect: "none", spacing: "normal" }] };
}

export function findDescriptionBlock(blocks, id) {
    for (let index = 0; index < (blocks || []).length; index++) {
        const block = blocks[index];
        if (block.id === id) return { block, index, siblings: blocks };
        const nested = findDescriptionBlock(block.children, id);
        if (nested) return nested;
    }
    return null;
}

export const contentStudioMethods = {
    studioError(error, fallback) {
        const message = this.errorMessage(error, fallback);
        return /(?:openai|gpt[- ]|astra|reasoning[._ ]effort)/i.test(message) ? fallback : message;
    },
    studioHasLocalChanges({ ignoreReuse = false } = {}) {
        const studio = this.state.contentStudio;
        return !!studio?.session && ((!ignoreReuse && !!studio.reuseBrief) || !!studio.input.trim() || !!studio.sourceText.trim() || !!studio.sourceUrl.trim() ||
            JSON.stringify(studio.brief) !== studio.savedBrief ||
            Object.keys(studio.previewDrafts || {}).length > 0 ||
            (studio.savedPreview && JSON.stringify(studio.preview) !== studio.savedPreview));
    },
    studioCanGenerate() {
        const s = this.state.contentStudio;
        return !!s?.session && !!s.availability.enabled && !s.briefConflict && !s.busy && !s.loading && !this.studioJobActive() &&
            !this.studioSourceBlockers().length;
    },
    studioSourceBlockers() {
        return (this.state.contentStudio.session?.sources || []).filter(source => source.state !== "excluded" &&
            (source.state !== "reviewed" || source.linkOnly || source.needsReview || source.conflicts?.length));
    },
    studioJobActive() { return ["pending", "running"].includes(this.state.contentStudio?.session?.job?.state); },
    studioNicheOptions() { return this.state.contentStudio.nicheOptions?.length ? this.state.contentStudio.nicheOptions : (this.state.detail?.classification?.terms || []).filter(term => term.axis === "niche"); },
    studioToggleNiche(id) {
        const ids = this.state.contentStudio.brief.nicheIds;
        this.state.contentStudio.brief.nicheIds = ids.includes(id) ? ids.filter(value => value !== id) : [...ids, id];
    },
    studioSessionCurrent(request, id) {
        return this.isRequestCurrent(request) && String(this.state.contentStudio?.session?.id || "") === String(id || "");
    },
    studioEnvelope(result, { brief = false, proposal = false } = {}) {
        const studio = this.state.contentStudio;
        const envelope = result?.result || result;
        if (!envelope?.session || String(envelope.session.productId) !== String(this.state.productId)) throw new Error("Invalid conversation scope");
        const previous = studio.session;
        if (previous && previous.id === envelope.session.id && envelope.session.revision < previous.revision) return null;
        if (previous && previous.id !== envelope.session.id) {
            studio.proposalId = false; studio.preview = emptyContentStudio().preview; studio.savedPreview = "";
            studio.compareId = ""; studio.pendingProposals = false; studio.replaceChanged = false; studio.awaitedJobId = false;
            studio.previewDrafts = {}; studio.sourceSelections = {};
        }
        studio.session = envelope.session;
        studio.sessions = envelope.sessions || studio.sessions;
        studio.nicheOptions = envelope.nicheOptions || studio.nicheOptions;
        studio.availability = envelope.availability || studio.availability;
        const remoteBrief = { ...emptyContentStudio().brief, ...clone(envelope.session.brief || {}) };
        const remoteBriefKey = JSON.stringify(remoteBrief);
        if (brief || JSON.stringify(studio.brief) === studio.savedBrief) {
            studio.brief = remoteBrief;
            studio.savedBrief = remoteBriefKey;
            studio.briefConflict = false;
        } else if (studio.savedBrief && remoteBriefKey !== studio.savedBrief) {
            studio.savedBrief = remoteBriefKey;
            studio.briefConflict = true;
            studio.notice = "Otro operador cambió la estrategia. Tus notas se conservan: revísalas y pulsa Guardar estrategia antes de generar.";
        }
        const proposals = envelope.session.proposals || [];
        if (proposal && proposals.length) this.studioSelectProposal(proposals[0].id);
        else if (proposals.length && proposals[0].id !== studio.proposalId &&
            !(previous?.proposals || []).some(row => row.id === proposals[0].id)) studio.pendingProposals = true;
        const job = envelope.session.job;
        if (job && job.id === studio.awaitedJobId && ["done", "failed", "cancelled"].includes(job.state)) {
            studio.awaitedJobId = false;
            const generated = proposals.find(row => row.id === job.resultPayload?.proposalId);
            if (generated) {
                const untouched = JSON.stringify(studio.preview) === studio.generationPreview && studio.proposalId === studio.generationProposalId &&
                    JSON.stringify(studio.brief) === studio.savedBrief && !studio.briefConflict;
                if (untouched && !generated.stale) this.studioSelectProposal(generated.id);
                studio.notice = untouched && !generated.stale ? "Nueva propuesta lista en la previa. Revísala; la ficha no se ha guardado." : "Nueva propuesta disponible. Conservamos tus ediciones; ábrela cuando termines de revisarlas.";
            } else if (job.state === "done") {
                studio.notice = "Nancy respondió en el chat, sin crear una nueva propuesta. La previa anterior no cambió. Si aportaste datos técnicos, usa Revisar como fuente.";
            } else {
                studio.error = this.studioJobError(job);
                studio.notice = "";
            }
        }
        return envelope;
    },
    studioChooseSession(ev) { return this.openContentStudio(false, Number(ev.target.value)); },
    async openContentStudio(newSession = false, sessionId = false) {
        if (!this.state.productId) return;
        const studio = this.state.contentStudio || (this.state.contentStudio = emptyContentStudio());
        if (studio.session && !newSession && !sessionId) {
            studio.open = true; this.studioNeedsFocus = true;
            if (this.studioJobActive()) this.scheduleStudioPoll();
            return;
        }
        if (studio.busy || studio.loading) return;
        if ((newSession || sessionId) && this.studioHasLocalChanges()) {
            studio.error = "Conserva tu propuesta en la ficha, guarda la estrategia o descarta los cambios del Studio antes de cambiar de conversación.";
            return;
        }
        this.studioReturnFocus = document.activeElement;
        studio.open = true; studio.loading = true; studio.error = ""; this.studioNeedsFocus = true;
        const request = this.beginRequest("studioOpen");
        this.studioDraftBaseline = this.captureDrafts();
        try {
            const data = await this.rpc(STUDIO + "open", { product_tmpl_id: request.productId, session_id: sessionId || undefined, new_session: !!newSession });
            if (!this.isRequestCurrent(request)) return;
            this.studioEnvelope(data, { brief: true, proposal: true });
            if (this.studioJobActive()) this.scheduleStudioPoll();
        } catch (_) {
            if (this.isRequestCurrent(request)) studio.error = "No se pudo abrir Nancy AI Studio. Tus borradores se conservan. Vuelve a intentarlo.";
        } finally { if (this.isRequestCurrent(request)) studio.loading = false; }
    },
    closeContentStudio() {
        const studio = this.state.contentStudio;
        if (studio.busy || studio.loading) { studio.error = "Espera a que termine esta operación. No se ha guardado la ficha."; return; }
        studio.open = false;
        clearTimeout(this.studioPollTimer);
        this.studioReturnFocus?.focus?.();
    },
    studioDiscardLocal() {
        const s = this.state.contentStudio;
        if (!s) return;
        s.reuseBrief = null; s.reuseReviewed = false;
        s.previewDrafts = {};
        s.brief = JSON.parse(s.savedBrief || "{}"); s.briefConflict = false; s.input = ""; s.sourceText = ""; s.sourceUrl = "";
        if (s.savedPreview) s.preview = JSON.parse(s.savedPreview);
        s.notice = "Cambios locales del Studio descartados. La ficha y el historial no se modificaron.";
    },
    syncStudioFocus() {
        if (!this.state.contentStudio?.open || !this.studioNeedsFocus || !this.contentStudioRef?.el) return;
        this.studioNeedsFocus = false; this.contentStudioRef.el.focus();
    },
    onStudioKeydown(ev) {
        if (ev.key === "Escape") { ev.preventDefault(); ev.stopPropagation(); this.closeContentStudio(); }
        if (ev.key !== "Tab") return;
        const focusable = [...(this.contentStudioRef?.el?.querySelectorAll('button:not([disabled]),input:not([disabled]),textarea:not([disabled]),select:not([disabled]),a[href],[contenteditable="true"]') || [])].filter(el => el.getClientRects().length);
        if (!focusable.length) { ev.preventDefault(); return; }
        const first = focusable[0], last = focusable[focusable.length - 1];
        if (ev.shiftKey && (document.activeElement === first || document.activeElement === this.contentStudioRef.el)) { ev.preventDefault(); last.focus(); }
        else if (!ev.shiftKey && document.activeElement === last) { ev.preventDefault(); first.focus(); }
    },
    async studioMutation(route, params = {}, { updateBrief = false, selectProposal = false, failure = "No se pudo completar la operación. Tus cambios se conservan." } = {}) {
        const s = this.state.contentStudio;
        if (!s.session || s.busy) return false;
        const id = s.session.id, request = this.beginRequest("studioMutation");
        this.beginRequest("studioPoll");
        const briefBefore = JSON.stringify(s.brief);
        s.busy = true; s.error = "";
        try {
            const result = await this.rpc(STUDIO + route, { product_tmpl_id: request.productId, session_id: id, revision: s.session.revision, ...params });
            if (!this.studioSessionCurrent(request, id)) return false;
            if (result.session || result.result?.session) {
                const changed = briefBefore !== JSON.stringify(s.brief);
                const retained = clone(s.brief);
                this.studioEnvelope(result, { brief: updateBrief, proposal: selectProposal });
                if (changed && updateBrief) s.brief = retained;
            }
            return result;
        } catch (error) {
            if (this.studioSessionCurrent(request, id)) s.error = this.studioError(error, failure);
            return false;
        } finally { if (this.studioSessionCurrent(request, id)) s.busy = false; }
    },
    async studioSaveBrief() {
        return this.studioMutation("save_brief", { brief: clone(this.state.contentStudio.brief) }, { updateBrief: true, failure: "No se pudo guardar la estrategia. Puede haber una edición de otro operador: actualiza la conversación sin descartar tus notas." });
    },
    async studioActivate() {
        const s = this.state.contentStudio;
        const result = await this.studioMutation("activate", {}, { failure: "Nancy AI no está disponible. Revisa la configuración con un administrador." });
        if (result) s.availability = result.availability || result;
    },
    async studioRefresh() {
        const s = this.state.contentStudio;
        if (!s.session || s.busy || s.loading) return;
        const request = this.beginRequest("studioPoll"), id = s.session.id;
        try {
            const result = await this.rpc(STUDIO + "status", { product_tmpl_id: request.productId, session_id: id });
            if (this.studioSessionCurrent(request, id)) this.studioEnvelope(result);
        } catch (_) { if (this.studioSessionCurrent(request, id)) s.error = "No se pudo consultar el progreso. El trabajo no se repetirá automáticamente. Usa Actualizar."; }
    },
    scheduleStudioPoll() {
        clearTimeout(this.studioPollTimer);
        this.studioPollTimer = setTimeout(async () => {
            if (!this.state.contentStudio?.open || this.destroyed) return;
            await this.studioRefresh();
            if (this.studioJobActive() && !this.state.contentStudio.error) this.scheduleStudioPoll();
        }, 3000);
    },
    async studioSend({ review = false } = {}) {
        const s = this.state.contentStudio;
        if (!this.studioCanGenerate()) return;
        const text = review ? "Revisa esta previa seleccionada con la estrategia y fuentes actuales. Conserva sus ediciones compatibles; corrige u omite afirmaciones incompatibles. Explica las omisiones en notas privadas y genera una nueva versión aplicable sin inventar datos." : (s.input.trim() || "Prepara una propuesta de descripción corta, larga y metadatos siguiendo la estrategia y las fuentes revisadas.");
        if (text.length > 12000) { s.error = "Resume tu mensaje a 12.000 caracteres. Puedes adjuntar textos extensos como fuente."; return; }
        if (JSON.stringify(s.brief) !== s.savedBrief && !(await this.studioSaveBrief())) return;
        const before = s.input;
        s.generationPreview = JSON.stringify(s.preview); s.generationProposalId = s.proposalId;
        this.studioDraftBaseline = this.captureDrafts();
        const result = await this.studioMutation("start", { message: text, request_key: uid(), draft: s.proposalId ? this.studioPreviewPayload() : undefined,
            review_proposal_id: review ? s.proposalId : false }, { failure: "Nancy AI no pudo iniciar la propuesta. Revisa las fuentes, la disponibilidad y si otro operador modificó esta conversación; no se ha repetido ninguna generación." });
        if (result) {
            if (!review && s.input === before) s.input = "";
            if (result.job && !s.session.job) s.session.job = result.job;
            s.awaitedJobId = result.job?.id || s.session.job?.id;
            s.notice = "Nancy AI está trabajando en tu solicitud. Nada se guardará en la ficha.";
            this.scheduleStudioPoll();
        }
    },
    studioJobError(job = this.state.contentStudio.session?.job) {
        const message = job?.errorMessage || "Nancy AI no pudo completar la solicitud. El diagnóstico de este trabajo antiguo no está disponible. Tus borradores se conservan; no se repitió automáticamente.";
        return /(?:openai|gpt[- ]|astra|reasoning[._ ]effort)/i.test(message) ? "Nancy AI no pudo completar la solicitud. Comunica el número de trabajo al administrador." : message;
    },
    studioReviewPreview() { return this.studioSend({ review: true }); },
    studioGoSources() {
        this.state.contentStudio.mobileTab = "conversation";
        requestAnimationFrame(() => {
            const panel = this.contentStudioRef?.el?.querySelector(".bpi-studio__sources");
            if (panel) { panel.open = true; panel.scrollIntoView({ block: "start", behavior: "smooth" }); panel.querySelector("summary")?.focus(); }
        });
    },
    onStudioMessageKeydown(ev) { if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) { ev.preventDefault(); this.studioSend(); } },
    studioOutcome() {
        const s = this.state.contentStudio, job = s.session?.job;
        if (job?.state === "failed") return "La última solicitud falló. Tus borradores se conservan; no se repitió automáticamente.";
        if (!job || job.state !== "done") return "";
        if (job.resultPayload?.sourceId) return "Fuente analizada: revisa sus datos antes de generar.";
        if (job.resultPayload?.proposalId) {
            const current = job.resultPayload.proposalId === s.proposalId;
            return current ? "Estás revisando la propuesta de la última solicitud." : "La última solicitud creó otra propuesta. Usa el selector de versión para revisarla.";
        }
        return "Última solicitud: respuesta en el chat, sin nueva propuesta. " + (s.proposalId ? "La previa sigue mostrando una versión anterior." : "Todavía no hay una propuesta para aplicar.");
    },
    studioMessageAsSource(message) {
        const s = this.state.contentStudio;
        if (message.role !== "user" || s.busy || this.studioJobActive()) return;
        if (s.sourceText.trim() || s.sourceUrl.trim()) { s.error = "Conserva o borra primero la fuente que estás preparando. No hemos reemplazado tu texto."; return; }
        s.sourceKind = "text"; s.sourceName = "Información del equipo — " + (message.author || "Operador");
        s.sourceText = message.content; s.mobileTab = "conversation";
        s.notice = "Revisa y deja solo los datos de este SKU. Pulsa Añadir fuente y confirma los fragmentos pertinentes. El chat no se aprueba automáticamente.";
        const panel = this.contentStudioRef?.el?.querySelector(".bpi-studio__sources");
        if (panel) { panel.open = true; requestAnimationFrame(() => { panel.scrollIntoView({ block: "nearest" }); panel.querySelector("textarea")?.focus(); }); }
    },
    async studioOpenReuse() {
        const s = this.state.contentStudio;
        if (s.busy || s.loading || this.studioJobActive()) return;
        s.reuseOpen = !s.reuseOpen;
        if (s.reuseOpen) await this.studioSearchStrategies();
    },
    async studioSearchStrategies() {
        const s = this.state.contentStudio;
        if (!s.session || s.busy) return;
        const request = this.beginRequest("studioStrategies"), id = s.session.id;
        s.busy = true; s.error = "";
        try {
            const data = await this.rpc(STUDIO + "strategies", { product_tmpl_id: request.productId, search: s.reuseSearch });
            if (this.studioSessionCurrent(request, id)) s.reuseOptions = data.strategies || [];
        } catch (error) { if (this.studioSessionCurrent(request, id)) s.error = this.studioError(error, "No se pudieron consultar las estrategias."); }
        finally { if (this.studioSessionCurrent(request, id)) s.busy = false; }
    },
    studioChooseReuse(ev) {
        const s = this.state.contentStudio;
        if (s.reuseBrief) { s.error = "Descarta la selección anterior antes de elegir otra estrategia. Tus ajustes se conservan."; return; }
        s.reuseId = ev.target.value;
        const source = s.reuseOptions.find(row => String(row.id) === s.reuseId);
        s.reuseBrief = source ? { ...emptyContentStudio().brief, ...clone(source.brief) } : null;
        s.reuseReviewed = false;
    },
    studioResetReuse() { const s = this.state.contentStudio; s.reuseId = ""; s.reuseBrief = null; s.reuseReviewed = false; },
    async studioReuseStrategy() {
        const s = this.state.contentStudio;
        if (!s.reuseBrief || !s.reuseReviewed || s.busy || s.loading || this.studioJobActive()) return;
        if (this.studioHasLocalChanges({ ignoreReuse: true })) { s.error = "Guarda o descarta tus cambios actuales del Studio antes de crear otra estrategia. La ficha conserva sus borradores."; return; }
        const source = s.reuseOptions.find(row => String(row.id) === s.reuseId);
        if (!source) return;
        const request = this.beginRequest("studioReuse"), id = s.session.id;
        this.beginRequest("studioPoll");
        s.busy = true; s.error = "";
        try {
            const result = await this.rpc(STUDIO + "reuse_strategy", { product_tmpl_id: request.productId,
                source_session_id: source.id, source_revision: source.revision, brief: clone(s.reuseBrief), reviewed: true });
            if (!this.studioSessionCurrent(request, id)) return;
            this.studioEnvelope(result, { brief: true, proposal: true });
            this.studioResetReuse(); s.reuseOpen = false;
            s.notice = "Estrategia independiente creada. No se copiaron fuentes, conversaciones ni descripciones. Revisa los públicos y añade los datos de este producto antes de generar.";
        } catch (error) { if (this.studioSessionCurrent(request, id)) s.error = this.studioError(error, "No se pudo reutilizar la estrategia. Revisa las orientaciones y vuelve a consultar si cambió el origen."); }
        finally { if (this.isRequestCurrent(request)) s.busy = false; }
    },
    async studioAddSource() {
        const s = this.state.contentStudio, kind = s.sourceKind;
        const original = kind === "url" ? s.sourceUrl : s.sourceText;
        if (!original.trim()) return;
        const result = await this.studioMutation("add_source", { kind, name: s.sourceName, text: kind === "text" ? original : undefined, url: kind === "url" ? original : undefined }, { failure: "No se pudo añadir la fuente. Usa texto o un enlace público permitido y respeta el límite de cinco archivos." });
        if (result) { if (kind === "url" && s.sourceUrl === original) s.sourceUrl = ""; if (kind === "text" && s.sourceText === original) s.sourceText = ""; s.sourceName = ""; }
    },
    async studioUploadSource(ev) {
        const file = ev.target.files?.[0]; ev.target.value = "";
        const s = this.state.contentStudio;
        if (!file || s.busy || !s.session) return;
        if (!/\.(pdf|docx|txt)$/i.test(file.name) || !file.size || file.size > 10 * 1024 * 1024) { s.error = "Usa PDF, DOCX o TXT de hasta 10 MiB. Convierte los archivos .doc antiguos."; return; }
        const request = this.beginRequest("studioUpload"), id = s.session.id;
        this.beginRequest("studioPoll");
        const form = this.studioFormData({ product_tmpl_id: request.productId, session_id: id, revision: s.session.revision }); form.append("file", file);
        s.busy = true; s.error = "";
        try {
            const response = await fetch(STUDIO + "upload_source", { method: "POST", credentials: "same-origin", body: form });
            const data = await response.json();
            if (!response.ok) throw { data: { name: "odoo.exceptions.ValidationError", message: data.error } };
            if (this.studioSessionCurrent(request, id)) this.studioEnvelope(data);
        } catch (error) { if (this.studioSessionCurrent(request, id)) s.error = this.studioError(error, "No se pudo cargar el archivo. Revisa su formato, tamaño y permisos. No se ha enviado a Nancy AI."); }
        finally { if (this.studioSessionCurrent(request, id)) s.busy = false; }
    },
    studioFormData(values) {
        const form = new FormData();
        form.append("csrf_token", window.odoo?.csrf_token || "");
        form.append("context", JSON.stringify(this.user?.context || {}));
        for (const [key, value] of Object.entries(values)) form.append(key, String(value));
        return form;
    },
    studioSourceFactChecked(source, fact) { return !this.state.contentStudio.sourceSelections[source.id] || this.state.contentStudio.sourceSelections[source.id].includes(fact.id); },
    studioToggleSourceFact(source, fact) {
        const s = this.state.contentStudio;
        const ids = s.sourceSelections[source.id] || (source.facts || []).map(row => row.id);
        s.sourceSelections[source.id] = ids.includes(fact.id) ? ids.filter(id => id !== fact.id) : [...ids, fact.id];
    },
    async studioReviewSource(source, action) {
        const result = await this.studioMutation("review_source", { source_id: source.id, action, fact_ids: this.state.contentStudio.sourceSelections[source.id] }, { failure: "No se pudo revisar la fuente. Excluye los datos incompatibles o corrige y guarda primero la identidad o las medidas del producto." });
        if (result && action === "reopen") this.state.contentStudio.sourceSelections[source.id] = (source.reviewedFacts || []).map(f => f.id);
        return result;
    },
    async studioConvertLink(source) { return this.studioMutation("convert_link", { source_id: source.id }, { failure: "No se pudo preparar el enlace. La fuente original se conserva." }); },
    async studioRemoveSource(source) {
        return this.studioMutation("remove_source", { source_id: source.id });
    },
    studioCanReadSource(source) { return source.state === "unreadable" || (source.state === "pending" && source.kind === "file" && /\.pdf$/i.test(source.filename || "")); },
    async studioProcessSource(source) {
        const result = await this.studioMutation("process_source", { source_id: source.id, request_key: uid() }, { failure: "No se pudo iniciar el análisis de la fuente. La ficha no se ha modificado." });
        if (result) { if (result.job) this.state.contentStudio.session.job = result.job; this.scheduleStudioPoll(); }
    },
    studioSourceState(source) { return ({ pending: "Revisión pendiente", reviewed: "Revisada", excluded: "Excluida", unreadable: "Requiere lectura", queued: "Enlace pendiente" })[source.state] || "Pendiente"; },
    studioSelectProposal(id) {
        const s = this.state.contentStudio;
        const proposal = (s.session?.proposals || []).find(row => Number(row.id) === Number(id));
        if (!proposal) return;
        if (Number(id) === Number(s.proposalId)) return;
        s.previewDrafts = s.previewDrafts || {};
        if (s.proposalId && s.savedPreview && JSON.stringify(s.preview) !== s.savedPreview) {
            s.previewDrafts[s.proposalId] = clone(s.preview);
        } else if (s.proposalId) delete s.previewDrafts[s.proposalId];
        s.proposalId = proposal.id;
        s.preview = { descriptionHtml: this.sanitizeDescriptionHtml(proposal.descriptionHtml || ""), technicalDescriptionHtml: this.sanitizeDescriptionHtml(proposal.technicalDescriptionHtml || ""), seoData: clone(proposal.seoData || {}) };
        for (const key of ["seoKeywords", "geoKeywords", "geoFeatures"]) if (Array.isArray(s.preview.seoData[key])) s.preview.seoData[key] = s.preview.seoData[key].join(", ");
        s.savedPreview = JSON.stringify(s.preview);
        if (s.previewDrafts[proposal.id]) s.preview = clone(s.previewDrafts[proposal.id]);
        s.pendingProposals = false; s.error = "";
    },
    studioCurrentProposal() { const s = this.state.contentStudio; return (s.session?.proposals || []).find(row => row.id === s.proposalId) || {}; },
    studioCompareProposal() { return (this.state.contentStudio.session?.proposals || []).find(row => String(row.id) === String(this.state.contentStudio.compareId)); },
    studioUpdatePreview(field, value) { this.state.contentStudio.preview[field] = this.sanitizeDescriptionHtml(value); },
    studioSafeHtml(value) { return markup(this.sanitizeDescriptionHtml(value || "")); },
    studioPreviewWordCount() {
        const s = this.state.contentStudio, key = s.previewTab === "short" ? "descriptionHtml" : "technicalDescriptionHtml";
        const text = this.descriptionPlainText(s.preview[key] || "");
        return text.trim() ? text.trim().split(/\s+/).length : 0;
    },
    studioPreviewText(value) { return this.descriptionPlainText(value || ""); },
    studioPreviewPayload() {
        const edits = clone(this.state.contentStudio.preview);
        for (const key of ["seoKeywords", "geoKeywords", "geoFeatures"]) if (typeof edits.seoData[key] === "string") edits.seoData[key] = edits.seoData[key].split(",").map(item => item.trim()).filter(Boolean);
        return edits;
    },
    async studioApply() {
        const s = this.state.contentStudio;
        if (!s.proposalId || s.busy || this.studioCurrentProposal().stale || this.studioCurrentProposal().conflicts?.length || this.studioSourceBlockers().length) return;
        const selected = Object.keys(s.selected).filter(key => s.selected[key]);
        if (!selected.length) { s.error = "Selecciona al menos un contenido para aplicar."; return; }
        const before = this.captureDrafts(), baseline = this.studioDraftBaseline || before;
        const changed = (selected.includes("short") && before.contentForm.description !== baseline.contentForm.description) ||
            (selected.includes("long") && before.contentForm.technicalDescription !== baseline.contentForm.technicalDescription) ||
            [...(selected.includes("seo") ? SEO_KEYS : []), ...(selected.includes("geo") ? GEO_KEYS : [])].some(key => before.seoForm[key] !== baseline.seoForm[key]);
        if (changed && !s.replaceChanged) { s.error = "La ficha cambió desde que se abrió esta propuesta. Revisa y confirma abajo si deseas reemplazar esos borradores."; return; }
        const request = this.beginRequest("studioApply", true), sessionId = s.session.id;
        const edits = this.studioPreviewPayload();
        const result = await this.studioMutation("prepare_apply", { proposal_id: s.proposalId, selected, edits }, { failure: "No se puede aplicar esta versión: revisa conflictos, fuentes o cambios en los datos guardados. Los borradores permanecen intactos." });
        if (!result || !this.studioSessionCurrent(request, sessionId)) return;
        const content = result.contentValues || {}, pending = [];
        const applyField = (form, key, value) => {
            if (value === undefined) return;
            if (JSON.stringify(this.state[form][key]) !== JSON.stringify(request.drafts[form][key])) { pending.push(key); return; }
            this.state[form][key] = value;
        };
        if (selected.includes("short")) applyField("contentForm", "description", content.descriptionHtml);
        if (selected.includes("long")) applyField("contentForm", "technicalDescription", content.technicalDescriptionHtml);
        for (const key of [...(selected.includes("seo") ? SEO_KEYS : []), ...(selected.includes("geo") ? GEO_KEYS : [])]) {
            const value = result.seoData?.[key]; applyField("seoForm", key, Array.isArray(value) ? value.join(", ") : value);
        }
        if (content.editorialRevision !== undefined) this.state.contentForm.editorialRevision = content.editorialRevision;
        this.state.contentForm.studioProposalId = result.proposalId || s.proposalId;
        this.seoPreviewVersion = (this.seoPreviewVersion || 0) + 1;
        if (selected.includes("seo") || selected.includes("geo")) this.state.seoPreviewPending = true;
        this.syncContentDescriptionEditor(true); this.syncTechnicalDescriptionEditor(true);
        s.savedPreview = JSON.stringify(s.preview); s.replaceChanged = false;
        delete (s.previewDrafts || {})[s.proposalId];
        if (pending.length) { s.error = "Se conservaron ediciones realizadas mientras se aplicaba la propuesta. Revisa los campos pendientes antes de salir."; return; }
        s.open = false; clearTimeout(this.studioPollTimer);
        this.notify("Propuesta aplicada a los borradores. Guardar sección conserva solo el contenido; usa Guardar ficha para incluir SEO y GEO.", "success");
    },

    descriptionLayout() { return this.state.contentForm.descriptionLayout || defaultDescriptionLayout(); },
    ensureDescriptionLayout() { if (!this.state.contentForm.descriptionLayout) this.state.contentForm.descriptionLayout = defaultDescriptionLayout(); return this.state.contentForm.descriptionLayout; },
    setDescriptionMode(mode) { this.state.descriptionMode = mode; if (mode === "design") this.loadDescriptionMedia(); },
    toggleDescriptionDesign(ev) { this.ensureDescriptionLayout().enabled = !!ev.target.checked; },
    descriptionBlockLabel(type) { return ({ main: "Texto principal", text: "Texto complementario", image: "Imagen", video: "Vídeo", columns: "Imagen y texto", container: "Contenedor", callout: "Destacado", divider: "Separador" })[type] || type; },
    newDescriptionBlock(type) {
        const block = { id: uid(), type, preset: "white", align: "left", effect: "none", spacing: "normal" };
        if (["text", "callout"].includes(type)) block.html = "";
        if (["image", "video"].includes(type)) Object.assign(block, { mediaId: false, caption: "", ...(type === "image" ? { alt: "" } : { url: "" }) });
        if (type === "video") Object.assign(block, { videoWidth: 100, videoRatio: "auto", posterMediaId: false });
        if (type === "columns") block.children = [this.newDescriptionBlock("image"), this.newDescriptionBlock("text")];
        if (type === "container") block.children = [this.newDescriptionBlock("text")];
        return block;
    },
    addDescriptionBlock(type, parentId = false) {
        const layout = this.ensureDescriptionLayout();
        const list = parentId ? findDescriptionBlock(layout.blocks, parentId)?.block.children : layout.blocks;
        if (!list || list.length >= 30) return;
        if (parentId && list.length >= 20) return;
        const block = this.newDescriptionBlock(type); list.push(block); layout.enabled = true;
        this.state.descriptionSelectedBlock = block.id;
    },
    chooseDescriptionMedia(id, value) {
        this.updateDescriptionBlock(id, "mediaId", Number(value) || false);
        const block = findDescriptionBlock(this.ensureDescriptionLayout().blocks, id)?.block;
        if (block?.type === "video" && value) block.url = "";
    },
    setDescriptionVideoUrl(id, value) {
        this.updateDescriptionBlock(id, "url", value);
        if (value) this.updateDescriptionBlock(id, "mediaId", false);
        this.updateDescriptionBlock(id, "posterMediaId", false);
        if (/youtube\.com|youtu\.be/.test(value)) this.fetchDescriptionPoster(id);
    },
    async fetchDescriptionPoster(id) {
        const block = findDescriptionBlock(this.ensureDescriptionLayout().blocks, id)?.block;
        if (!block?.url || this.state.descriptionMediaBusy) return;
        const request = this.beginRequest("descriptionPoster"), url = block.url, previous = block.posterMediaId;
        this.state.descriptionMediaBusy = true; this.state.descriptionMediaError = "";
        try {
            const result = await this.rpc(MEDIA + "video_poster", { product_tmpl_id: request.productId, url });
            if (!this.isRequestCurrent(request)) return;
            const current = findDescriptionBlock(this.ensureDescriptionLayout().blocks, id)?.block;
            if (!current || current.url !== url || current.posterMediaId !== previous) return;
            this.state.descriptionMedia.push(result.media); current.posterMediaId = result.media.id;
        } catch (_) { if (this.isRequestCurrent(request)) this.state.descriptionMediaError = "No se pudo obtener la portada. Puedes subir una imagen o volver a intentarlo."; }
        finally { if (this.isRequestCurrent(request)) this.state.descriptionMediaBusy = false; }
    },
    setDescriptionVideoWidth(id, value) { this.updateDescriptionBlock(id, "videoWidth", Number(value)); },
    descriptionVideoTextStyle(block, field) {
        return { font: field === "title" ? "display" : "body", size: field === "title" ? 28 : 14,
            bold: false, italic: false, align: "inherit", color: "auto", ...(block[field + "Style"] || {}) };
    },
    setDescriptionVideoTextStyle(id, field, property, value) {
        if (!["title", "caption"].includes(field)) return;
        const block = findDescriptionBlock(this.descriptionLayout().blocks, id)?.block;
        if (!block || block.type !== "video") return;
        const style = this.descriptionVideoTextStyle(block, field);
        if (property === "size") {
            value = Number(value);
            if (!Number.isInteger(value) || value < 12 || value > 64) return;
        }
        this.updateDescriptionBlock(id, field + "Style", { ...style, [property]: value });
    },
    setDescriptionVideoTextSize(id, field, ev) {
        const block = findDescriptionBlock(this.descriptionLayout().blocks, id)?.block;
        if (!block) return;
        const value = Number(ev.target.value);
        if (!Number.isInteger(value) || value < 12 || value > 64) {
            ev.target.value = this.descriptionVideoTextStyle(block, field).size;
            this.notification.add("Usa un tamaño de 12 a 64 px.", { type: "warning" });
            return;
        }
        this.setDescriptionVideoTextStyle(id, field, "size", value);
    },
    descriptionVideoTextCss(block, field) {
        const style = this.descriptionVideoTextStyle(block, field);
        const font = style.font === "display" ? "var(--bader-font-display)" : "var(--bader-font-body)";
        const size = Number.isInteger(style.size) && style.size >= 12 && style.size <= 64 ? style.size : 14;
        const align = ["inherit", "left", "center", "right"].includes(style.align) ? style.align : "inherit";
        const color = ({ auto: "inherit", petrol: "#003841", green: "#2f7d32" })[style.color] || "inherit";
        return `font-family:${font};font-size:${size}px;font-weight:${style.bold ? 700 : 400};font-style:${style.italic ? "italic" : "normal"};text-align:${align};color:${color}`;
    },
    chooseDescriptionPoster(id, value) { this.updateDescriptionBlock(id, "posterMediaId", Number(value) || false); },
    descriptionVideoStyle(block) {
        const media = this.descriptionMediaById(block.mediaId);
        let ratio = block.videoRatio || "auto";
        if (ratio === "auto") ratio = media?.width && media?.height ? media.width + "/" + media.height : /tiktok\.com/.test(block.url || "") ? "9/16" : "16/9";
        return "--bpi-video-width:" + (Number(block.videoWidth) || 100) + "%;--bpi-video-ratio:" + ratio.replace(":", "/");
    },
    updateDescriptionBlock(id, key, value) {
        const found = findDescriptionBlock(this.ensureDescriptionLayout().blocks, id);
        if (!found) return;
        found.block[key] = key === "html" ? this.sanitizeDescriptionHtml(value) : value;
    },
    moveDescriptionBlock(id, offset) {
        const found = findDescriptionBlock(this.ensureDescriptionLayout().blocks, id);
        if (!found || found.index + offset < 0 || found.index + offset >= found.siblings.length) return;
        const [item] = found.siblings.splice(found.index, 1); found.siblings.splice(found.index + offset, 0, item);
    },
    descriptionContainsMain(block) { return block.type === "main" || (block.children || []).some(child => this.descriptionContainsMain(child)); },
    duplicateDescriptionBlock(id) {
        const found = findDescriptionBlock(this.ensureDescriptionLayout().blocks, id);
        if (!found || this.descriptionContainsMain(found.block) || found.siblings.length >= 30) return;
        const parent = this.descriptionParentBlock(this.ensureDescriptionLayout().blocks, id);
        if (parent && found.siblings.length >= (parent.type === "columns" ? 2 : 20)) return;
        const duplicate = clone(found.block);
        const renew = block => { block.id = uid(); (block.children || []).forEach(renew); }; renew(duplicate);
        found.siblings.splice(found.index + 1, 0, duplicate);
    },
    removeDescriptionBlock(id) {
        const found = findDescriptionBlock(this.ensureDescriptionLayout().blocks, id);
        if (!found || this.descriptionContainsMain(found.block)) return;
        if (this.descriptionParentBlock(this.ensureDescriptionLayout().blocks, id) && found.siblings.length === 1) return;
        found.siblings.splice(found.index, 1);
        // Unlinking a block never calls gallery or media deletion.
    },
    descriptionParentBlock(blocks, id) {
        for (const block of blocks) {
            if ((block.children || []).some(child => child.id === id)) return block;
            const parent = this.descriptionParentBlock(block.children || [], id); if (parent) return parent;
        }
        return null;
    },
    descriptionMediaById(id) { return (this.state.descriptionMedia || []).find(item => Number(item.id) === Number(id)); },
    descriptionMediaPreview(block) {
        const row = this.descriptionMediaById(block.mediaId);
        return row?.previewUrl || (block.mediaId ? MEDIA + block.mediaId + "/preview" : "");
    },
    async discardDescriptionUpload() {
        if (!this.descriptionUploadSession || this.state.descriptionMediaBusy) return;
        const upload = this.descriptionUploadSession, request = this.beginRequest("descriptionCancel");
        this.state.descriptionMediaBusy = true;
        try {
            await this.rpc(MEDIA + upload.id + "/remove", { product_tmpl_id: request.productId });
            if (!this.isRequestCurrent(request)) return;
            if (this.descriptionUploadSession === upload) this.descriptionUploadSession = null;
            this.state.descriptionMediaError = "";
            this.state.descriptionMedia = this.state.descriptionMedia.filter(row => row.id !== upload.id);
        } catch (_) { if (this.isRequestCurrent(request)) this.state.descriptionMediaError = "No se pudo descartar el archivo. No se eliminan archivos utilizados por un diseño guardado."; }
        finally { if (this.isRequestCurrent(request)) this.state.descriptionMediaBusy = false; }
    },
    async loadDescriptionMedia() {
        const request = this.beginRequest("descriptionMedia");
        try {
            const result = await this.rpc(MEDIA + "list", { product_tmpl_id: request.productId });
            if (this.isRequestCurrent(request)) this.state.descriptionMedia = result.media || [];
        } catch (_) { if (this.isRequestCurrent(request)) this.state.descriptionMediaError = "No se pudo cargar la biblioteca privada. Vuelve a intentarlo."; }
    },
    async uploadDescriptionMedia(ev, blockId, asPoster = false) {
        const file = ev.target.files?.[0]; ev.target.value = "";
        if (!file || this.state.descriptionMediaBusy) return;
        const block = findDescriptionBlock(this.ensureDescriptionLayout().blocks, blockId)?.block;
        if (!block) return;
        const kind = asPoster ? "image" : block.type === "video" ? "video" : "image";
        if (!file.size || file.size > (kind === "video" ? 200 : 10) * 1024 * 1024 ||
            (kind === "video" ? !/\.mp4$/i.test(file.name) : !["image/jpeg", "image/png", "image/webp"].includes(file.type))) {
            this.state.descriptionMediaError = kind === "video" ? "Selecciona un MP4 H.264/AAC de hasta 200 MiB." : "Selecciona una imagen JPG, PNG o WebP de hasta 10 MiB."; return;
        }
        const selectionBefore = JSON.stringify([block.url, block.mediaId, block.posterMediaId]);
        const signature = [this.state.productId, file.name, file.size, file.lastModified, kind].join(":");
        const request = this.beginRequest("descriptionUpload");
        this.state.descriptionMediaBusy = true; this.state.descriptionMediaError = "";
        this.state.descriptionUpload = { filename: file.name, percent: 0 };
        try {
            let upload = this.descriptionUploadSession?.signature === signature ? this.descriptionUploadSession : null;
            if (!upload) {
                upload = { ...(await this.rpc(MEDIA + "start", { product_tmpl_id: request.productId, filename: file.name, size: file.size, kind })), signature };
                if (!this.isRequestCurrent(request)) return;
                this.descriptionUploadSession = upload;
            }
            const chunkSize = Math.min(Number(upload.chunkSize) || 1048576, 1048576);
            while (upload.offset < file.size) {
                if (!this.isRequestCurrent(request)) return;
                const end = Math.min(upload.offset + chunkSize, file.size);
                const form = this.studioFormData({ product_tmpl_id: request.productId, offset: upload.offset });
                if (upload.csrfToken) form.set("csrf_token", upload.csrfToken);
                form.append("file", file.slice(upload.offset, end), file.name);
                const response = await fetch(MEDIA + upload.id + "/chunk", { method: "POST", body: form, credentials: "same-origin" });
                const result = await response.json();
                if (!response.ok) throw { data: { name: "odoo.exceptions.ValidationError", message: result.error } };
                if (!this.isRequestCurrent(request)) return;
                const offset = Number((result.result || result).offset);
                if (!Number.isFinite(offset) || offset <= upload.offset || offset > file.size) throw new Error("Invalid offset");
                upload.offset = offset; this.state.descriptionUpload.percent = Math.floor(offset * 100 / file.size);
            }
            const data = await this.rpc(MEDIA + upload.id + "/complete", { product_tmpl_id: request.productId });
            if (!this.isRequestCurrent(request)) return;
            const media = data.media || data;
            const target = findDescriptionBlock(this.ensureDescriptionLayout().blocks, blockId)?.block;
            this.state.descriptionMedia = [...(this.state.descriptionMedia || []).filter(row => row.id !== media.id), media];
            if (target && JSON.stringify([target.url, target.mediaId, target.posterMediaId]) === selectionBefore) { if (asPoster) target.posterMediaId = media.id; else { target.mediaId = media.id; if (target.type === "video") target.url = ""; } }
            this.descriptionUploadSession = null;
        } catch (error) {
            if (this.isRequestCurrent(request)) this.state.descriptionMediaError = this.studioError(error, "No se pudo completar el archivo. Comprueba formato y espacio disponible; selecciona el mismo archivo para continuar la carga, o usa un enlace de vídeo.");
        } finally { if (this.isRequestCurrent(request)) { this.state.descriptionMediaBusy = false; this.state.descriptionUpload = null; } }
    },
};
