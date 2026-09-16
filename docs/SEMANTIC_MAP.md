# Editable semantic map — 16.0.1.12.0

## User journey

`Clasificación` presents the saved product at the root of four independent,
multi-value branches: Nicho → Aplicación comercial → Aplicación técnica →
Uso / Procedimiento. The visual order is a reading aid, not a restrictive
parent/child taxonomy. An instrument can serve several audiences and uses.

One explicit `Analizar producto` request produces a reviewable draft. Operators
can keep, remove or add approved terms and propose a new word for administrative
approval. Manual exclusions persist. Merely selecting, opening or searching never
calls AI. New words and intent phrases are not automatically approved synonyms.
Approving a dictionary term does not associate it with a product automatically.

`Guardar sección` / `Guardar ficha` preserve the atomic save contract. Only saved
approved associations feed the local public search and editorial context. Neither
generation nor upgrades publish or replace descriptions automatically.

## Multi-audience reasoning

Nancy evaluates each non-universal approved niche independently. Educational
audiences need a reason grounded in the identified instrument and its ordinary
training/purchasing use; they are not limited to products named “student”. This
also does not make every specialist spare part or installation suitable for a
student. Lack of evidence is explicit. Mayorista remains the existing universal
eligible-product view, not an inferred clinical application.

Optional `nicheEvaluations` explain suggested/not-suggested/insufficient-evidence
decisions. Optional `intentPhrases` illustrate how someone could search using the
selected concepts. Both are bounded and checked against approved same-axis terms;
they are informative proposals, not new indexed claims or unrestricted keywords.
Older provider/job responses that omit these optional arrays remain supported.

## Shared saved semantic context

`product.template._bpi_semantic_context()` exposes active approved saved terms,
approved aliases, definitions, revisions and the classification review date.
`detail.semanticContext` is administrative; it is not a public record dump.
Universal Mayorista, drafts, archived or pending terms are excluded.

Description, SEO/GEO and FAQ generation consume this context separately from
confirmed specifications. Categories and old generated prose are not evidence
for material, dimensions, sterilization, certifications, warranty or clinical
compatibility. Editorial tone/audience can focus copy without deleting the other
approved audiences. Avoid keyword stuffing and promises of ranking/indexation.

The context fingerprint covers the selected vocabulary and its aliases/revisions
as well as saved classification revision. Description template contracts add
`semanticRevision`; new SEO jobs snapshot the semantic revision, company context
and requester. Recheck saved context before/after paid work and reject stale
results; legacy queued jobs retain their old response envelope. Frontend guards
also preserve edits made during generation. No automatic paid retries.

## Shared search

The existing header autocomplete, `/shop` and internal catalog continue to use
`taxonomy_search.py` before pagination. Longest canonical phrases are recognized
first. Standalone Spanish connectors (for example `para`, `de`, `los`) in a
meaningful multi-part query are not independent requirements. Thus “instrumental
para estudiantes” can match both approved concepts. Exact SKUs, negation (`sin`),
connector-containing canonical phrases and all-connector literal queries are
preserved. The user's displayed text and URL are never rewritten.

## Delivery and non-goals

- QAS only, backup plus guarded rollback before upgrading only BPI.
- No AI batch classification, autosave, mass regeneration or automatic publication.
- No changes to MercadoLibre transport, flags, synchronization or other addons.
- Preserve website header custom code, approved descriptions, documents and cm/g
  specifications, private draft semantics and native Odoo category independence.
- Tests cover shared context, prompts, revision races, permissions, optional
  response validation, semantic search and the OWL editable map. Runtime evidence
  is recorded separately under `audit_outputs/semantic_map_20260916/`.
- Better semantic content aids relevance but does not guarantee Google indexing,
  rankings or inclusion in LLM answers. Saved relevant public text remains the
  source for public content; no hidden keyword dump or special AI markup is added.
