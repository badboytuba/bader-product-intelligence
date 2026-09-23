## 2026-09-23 — Studio feedback and reusable editorial strategies

Release `16.0.1.13.4` fixes user-message contrast, separates chat-only completion
from new proposals, and auto-opens only an explicitly requested current proposal
when local preview/brief are unchanged. Preserve ID-based bounded-history detection.
Chat-to-source is a draft shortcut, never implicit evidence approval. Strategy
reuse creates an independent product-owned conversation from reviewed brief fields
only, with company/revision guards and no files/history/technical facts copied.
Read `docs/NANCY_CONTENT_STUDIO.md`. Existing product copy and proposals are not
migrated. QAS only; deployment evidence is separate from source version.

## 2026-09-21 — Video titles and independent typography

Release `16.0.1.13.3` adds optional video titles and separate title/caption style
controls (official local Bader fonts, 12–64 px, emphasis, alignment, brand colors).
Text remains escaped plain text and styles are server-allowlisted, never free CSS.
Existing captions/layouts are preserved; no default title is written on upgrade.
The public Abrir vídeo footer is removed, while cover playback/social fallbacks
remain accessible. Keep draft-only editing, atomic saves and recursive editor keys.
QAS only. Read `docs/NANCY_CONTENT_STUDIO.md` before extending this contract.

## 2026-09-21 — Nested visual editor identity hotfix

Release `16.0.1.13.2` gives each recursive `StudioRichEditor` its globally unique
block ID as an explicit OWL component key. Without it, two text children in a
container can leave rendering pending forever: clicking Diseño Bader changes
state but never displays the editor, without a console or server exception.
Keep the explicit key and test real DOM tab clicks, multiple nested siblings,
independent edits, reorder/duplicate/remove and tab re-entry. No data migration,
layout cleanup or description regeneration is needed. QAS only.

## 2026-09-19 — Video covers and responsive sizing

Release `16.0.1.13.1` adds product-owned private video posters, bounded width and
aspect controls, automatic saved MP4 dimensions, and click-to-play poster cards.
YouTube covers are obtained only on explicit editor action; public rendering stays
local. Preserve poster/media ownership, stale drafts, server-side layout validation
and website/revision gates. Only QAS is authorized. Never rewrite descriptions.

## 2026-09-18 — Nancy AI Studio and visual long descriptions

Release `16.0.1.13.0` adds explicit private shared content conversations/sources,
reviewed structured proposals applied only to drafts, and versioned visual blocks
referencing the single principal long-copy field. Read `docs/NANCY_CONTENT_STUDIO.md`.
Keep source/media privacy, revision guards, scoped requested engine, local storage
quotas, authorized Nginx delivery and no paid replay. No bulk regeneration, model
changes elsewhere, publication or production deployment is authorized.

## 2026-09-16 — Editable semantic map

Release `16.0.1.12.0` connects the product to four independent multi-value axes
in an editable mental map. Explicit Nancy proposals evaluate audiences separately;
only reviewed saved assignments feed search and the shared content/SEO/FAQ context.
Semantic labels are not technical evidence. Generation stays explicit, guarded by
saved semantic revisions, and never republishes historical descriptions on upgrade.
Read `docs/SEMANTIC_MAP.md`. QAS only; preserve exclusions, brand, ML and Git.

## 2026-09-16 — Premium tag editor

Release `16.0.1.11.0` replaces long classification checklists with four editable
chip cards and one explicit analysis action. Completed requested analyses only
complement the draft, preserving selected and manually excluded terms. Saved
exclusions persist across reopening; new words remain subject to approval.
Read `docs/TAXONOMY_SEARCH.md`. QAS only, no automatic product changes or new
public search behavior. Keep the official flat Bader palette and local fonts.

## 2026-09-16 — Reviewed classification and integrated search

Release `16.0.1.10.0` adds four per-product classification axes, an approved
canonical dictionary and explicit asynchronous Nancy proposals. Read
`docs/TAXONOMY_SEARCH.md`. Only saved approved assignments feed shared server-side
header/shop/BPI matching; legacy fields are preserved as suggestions. Website
activation and V5 migration require a checksum-guarded QAS operation, not addon
installation alone. Preserve category independence, drafts and all prior content.

## 2026-09-15 — Optional product catalogs and documents

Release `16.0.1.9.0` adds the privately stored catalog/PDF card before public
FAQs. Read `docs/PRODUCT_DOCUMENTS.md`. Preserve optional/empty semantics,
atomic content drafts, publication/company/website gates and private attachments.
QAS only; no resources are populated automatically and ML/AI remain unchanged.

## 2026-09-15 — Instrumental approved copy and separated generation

Release `16.0.1.8.1` adds `general_specs` (General short, saved specifications
long) and a private dated import receipt. Read `docs/INSTRUMENTAL_COPY.md`.
Preserve approved literal copy, report conflicting measurements without altering
Datos y precios, and never use historic prose as technical evidence. QAS only.

## 2026-09-15 — Saved technical specifications

Release `16.0.1.8.0` adds per-variant editorial cm/g measurements in Datos y
precios, separate from logistics/ML, and guarded exact-SKU imports. Read
`docs/TECHNICAL_SPECIFICATIONS.md`. Preserve empty/unknown semantics, provenance,
atomic saves, revision guards and existing content. QAS only.

## 2026-09-15 — Category-specific description models

Release `16.0.1.7.0` adds an administrator-managed description-template library,
internal-category inheritance and explicitly saved product overrides. Read
`docs/CONTENT_TEMPLATES.md` (or `CONTENT_TEMPLATES.md` beside this handoff).
Preserve atomic saves, drafts, stale-response protection and the shared Bader
brand. No historical content regeneration or publication on upgrade. QAS only;
provider configuration and MercadoLibre safety flags remain unchanged. Runtime
evidence is separate from the source version.

## 2026-09-13 — Official Bader identity

Release `16.0.1.6.2` requires the shared `bader_brand` addon from `bader_brand_addons`. Read `docs/BADER_BRAND.md` (or `BADER_BRAND.md` alongside this handoff). Scope styles to explicit owned `.bader-brand` roots; never restyle native Odoo navbar/global forms or overwrite authored content. Logos/fonts are official local assets. Category-generation templates are not part of this cosmetic release. Preserve business/API/save/ML safety behavior; QAS only.

# Bader Product Intelligence

Installable Odoo 16 Community product operations module with SEO, GEO, image generation, competitor analysis and product-level AI workflows.

## Release 16.0.1.6.1 — AI and competitor reliability (QAS only)

- Existing AI actions keep their configured models. Safe Odoo validation/access errors
  are shown instead of generic transport errors; invalid/incomplete provider responses
  never become completed proposals.
- Competitor collection preserves HTML metadata and JSON-LD regardless of attribute
  order. Prices require unambiguous amount/currency evidence; ranges, freight and
  installment amounts are not fabricated discounts.
- Page keywords are identified as observed, absent or legacy/unknown. AI keyword and
  content recommendations are separate, dated suggestions, not extracted page facts.
- Failed refreshes retain the last valid evidence and show a warning. Collection is
  explicit, bounded and admin/company scoped; opening pages performs no paid calls.
- Set keys only in protected configuration. Public HTTP collection may work without
  Firecrawl; JavaScript/blocking pages can still fail. Keep MercadoLibre external
  reads/writes disabled and dry run enabled in QAS. Production is not part of this release.
- See `docs/AI_COMPETITOR_QAS.md`; runtime evidence is recorded separately.

## Release 16.0.1.3.1 — QAS stabilization

- A single admin `/save_all` request saves a captured product workspace atomically; the category selected in Datos is authoritative.
- Async results are scoped to product, navigation generation and operation. Late responses, including A→B→A navigation, cannot replace another workspace; partial saves preserve unsaved drafts.
- SEO analysis produces a **metadata proposal**, not an automatic publication. Review and save explicitly; commercial/technical descriptions and FAQs are unchanged by analysis.
- Competitor discovery includes the missing Pack/variant prompt context and retains real-candidate/fallback behavior.
- Supported video URLs are parsed by host/path/query; reordered YouTube parameters work and invalid legacy values no longer break the product detail.
- Public exchange-rate and website-bridge methods require an administrator before privilege elevation.
- Active SEO jobs are deduplicated at database level and execution is locked across visibility commits. Interrupted expired jobs fail safely, without automatically replaying potentially paid API requests.
- This release is authorized for **QAS only**. No PROD deployment is included.

## Target Stack

- Odoo `16.0` Community
- PostgreSQL compatible with Odoo 16
- Python environment used by the target Odoo instance

## Scope

- Product intelligence dashboard in backend
- SEO/GEO fields and generated content
- Product image workflows
- Competitor discovery and analysis
- Product chat assistant
- Operational control of native product variants
- OCA Pack configuration and component composition
- Website product detail extensions for the Bader storefront

## Odoo Dependencies

- `product`
- `web`
- `website_sale`
- `product_pack`
- `sale_product_pack`
- `stock_product_pack`

These modules must be available in the target Odoo database before installation. Pack behavior follows the official OCA Product Pack modules; the addon does not create a parallel Pack model.

## Python Dependencies

- `requests`

Usually this is already present in Odoo environments, but it must exist in the same Python environment that runs Odoo.

## External Services

- OpenAI API
- Firecrawl API

## Installation

1. Clone the repository into the addons path using the technical module directory name:

```bash
git clone https://github.com/badboytuba/bader-product-intelligence.git bader_product_intelligence
```

2. Ensure the resulting folder name is exactly `bader_product_intelligence`.
3. Update the app list.
4. Install `Producto Intelligence`.

CLI example:

```bash
odoo-bin -d <database> -i bader_product_intelligence
```

Upgrade example after future changes:

```bash
odoo-bin -d <database> -u bader_product_intelligence
```

## Configuration

Use `Settings > General Settings` and open the `Producto Intelligence` block.

Core parameters:

- `OpenAI API Key`
- `OpenAI Modelo Texto`
- `OpenAI Modelo Imagen`
- `OpenAI Modelo Edición Imagen`
- `Firecrawl API Key`
- `Firecrawl Base URL`
- `Tipo de Cambio ARS`

Without an OpenAI credential, AI generation/analysis is unavailable. Competitor collection can fall back to bounded public HTTP access without Firecrawl when the site permits it; neither provider is called automatically when opening pages.

Environment fallbacks:

- `BPI_OPENAI_API_KEY` or `OPENAI_API_KEY`
- `BPI_OPENAI_TEXT_MODEL` (default: `gpt-5.5`)
- `BPI_OPENAI_IMAGE_MODEL` (default: `gpt-image-2`)
- `BPI_OPENAI_IMAGE_EDIT_MODEL` (default: `gpt-image-1.5`)

## Security / Access

- Backend usage is intended for administrators.
- Main backend routes validate `base.group_system`.
- Variant and Pack mutations validate template ownership, company, allowed fields, component eligibility and concurrent Pack revisions.

## Compatibility Notes

- This module is now independent from `bader_website`.
- The product page renders the sanitized rich BPI description when available and falls back to Odoo's native commercial description; public Pack composition rendering remains outside this release.
- Backend tests exist under `tests/test_product_intelligence.py`; OWL tests live in `static/tests/product_intelligence_tests.js`.


## Agent / Codex Handoff

For future Codex or automation agents, read:

- `AGENTS.md` — repo-specific operating rules and safety constraints.
- `docs/CODEX_5_5_HANDOFF.md` — detailed architecture, current state, validation commands, known issues, and recommended next fixes.
- `.env.example` — redacted environment variable template. Never commit real `.env` values.

This repository should be cloned/deployed with folder name `bader_product_intelligence`.

## Validation Notes

- Manifest dependencies are clean for standalone installation.
- The module no longer inherits templates from `bader_website`.
- Every release must be upgraded and tested in QAS before production approval.

## Release 16.0.1.1.14

- Restores the native eCommerce category view (including Parent Category) and binds separate enriched tree/form views to the Product Intelligence menu.
- Uses product-owned `bpi:<id>` tokens for Studio references and image deletion.
- Restricts image uploads/imports to PNG, JPEG or WebP up to 10 MiB, with strict base64, MIME/signature, redirect and SSRF validation.
- Isolates chat state and sessions per product and ignores stale frontend responses.
- Preserves competitor prices in their source currency while exposing normalized USD values for ARS/USD analytics.
- Requires product ownership for competitor scrape, analysis and deletion routes, and avoids raw external response data in logs.

## Release 16.0.1.2.1

- Adds explicit OCA Pack dependencies and recognizes products as `simple`, `variants`, `pack` or `pack_variants`.
- Shows Pack/variant badges plus native effective price, cost and availability ranges in the dashboard and detail workspace.
- Adds the conditional **Variantes y Pack** tab for SKU, barcode, cost, active state and per-variant image overrides; Odoo continues to calculate stock and effective prices.
- Allows existing Packs to edit type, price mode, modifiable flag and per-variant compositions without converting ordinary products into Packs.
- Searches eligible components by product variant with a 20-result limit and rejects inactive additions, duplicates, self-reference, cross-company records and recursive Packs.
- Saves complete Pack compositions atomically and requires `packRevision` to prevent stale overwrites.
- Adds bounded variant/Pack context to content, SEO, categorization, image, strategy and chat prompts without creating per-variant content.
- Uses effective Pack prices and native variant min–max ranges in analytics.
- Adds secure variant image upload/reference/removal using the existing 10 MiB PNG/JPEG/WebP validation and product-owned image tokens.
- Replaces the unsupported Odoo 16 OWL `.enter` event modifier with an explicit Enter-key handler in Pack component search.

## Release 16.0.1.2.2

- Adds a Word-like visual toolbar to the optimized-description editor without adding a third-party JavaScript dependency.
- Supports paragraph styles, allowlisted fonts and sizes, text/highlight colors, bold, italic, underline, strikethrough, alignment, lists, indentation, links, undo/redo and format cleanup.
- Preserves formatted HTML in `bpi_ai_generated_description` while continuing to copy plain text into Odoo's commercial description.
- Sanitizes tags, links and inline styles using a strict client allowlist plus Odoo's `fields.Html` sanitizer.
- Activates the product-page bridge so the sanitized formatted description is rendered in `website_sale.product`, with the native `description_sale` as fallback.
- Synchronizes the bridge to website-specific primary copies of `website_sale.product`, which Odoo may create without an XML ID.
- Certified in QAS with 20 backend tests and 12 QUnit tests/45 assertions, then deployed to PROD on 2026-08-10.

## Release 16.0.1.2.3

- Publishes only complete, saved Producto Intelligence FAQs on the product page; generated previews still require **Guardar Cambios** before publication.
- Places a full-width, responsive native `details`/`summary` FAQ section immediately after the main product block, visually below the internal reference.
- Loads the FAQ presentation from its own frontend SCSS asset so Odoo invalidates the compiled bundle when this feature changes.
- Keeps `bpi.product.faq` manager-only and exposes an escaped `compute_sudo` projection through `product.template`, without granting public model access.
- Adds accessible keyboard focus, a first-question-open presentation and Schema.org `FAQPage`/`Question`/`Answer` semantics matching the visible copy.
- Does not promise Google FAQ rich results: Google removed that search result feature in 2026; the markup remains semantic metadata for other consumers.
- Certified in QAS with 21 backend tests, 12 QUnit tests/45 assertions and desktop/mobile visual checks, then deployed and visually certified on PROD on 2026-08-10.

## Release 16.0.1.3.0

- Reduces newly generated optimized descriptions from 180–280 to 45–70 words, keeping the purchase area concise.
- Adds a separate sanitized rich-text technical description with a 350–650 word generation target and the same allowlisted Word-like formatting tools.
- Makes the optimized editor approximately 75% shorter visually and provides a larger technical editor for structured product information.
- Publishes saved technical content full-width below the product/image area and immediately before the FAQ section.
- Does not truncate or migrate existing descriptions automatically; an operator must generate or edit and save the split content.
- Certified in QAS at runtime commit `f65600d` with 22 backend tests, 13 QUnit tests/51 assertions, exact 33-file package verification and desktop/mobile/backend visual checks; PROD remains on `16.0.1.2.3` pending authorization.

## Executive catalog dashboard — 16.0.1.4.0

The admin home opens **Visión general**, with eight current-state coverage KPIs, publication/completeness charts, actionable priorities and the latest SEO/GEO jobs. **Catálogo** retains pagination, search, publication/star controls and the existing product workspace. Categories are shared; KPI drill-down uses the same backend predicates as the overview.

Counters now consistently refer to active saleable templates in the selected Odoo companies; the former “Nuevos” tab is correctly labeled “Sin publicar”. A finished SEO job is only a proposal, not publication. No historical trends, external analytics, paid requests or automatic content changes are triggered by opening the dashboard.

See [Executive dashboard contract](docs/EXECUTIVE_DASHBOARD.md). This release is scoped to QAS only.

## Release 16.0.1.5.0 — Catalog workbench (QAS only)

Catálogo now has prominent search, preparation filters, safe sorting, visible category/Pack/variant context, a real seven-section checklist and inline quick review linking to existing editors. Mobile rows become cards without duplicate controls. Publication/feature toggles have per-row pending state and failed-checkbox rollback. The executive overview, detail and atomic save workflows are preserved. See [`docs/CATALOG_WORKBENCH.md`](docs/CATALOG_WORKBENCH.md) for field definitions and sort semantics.

## Product workspace 16.0.1.6.0 (QAS)

The product detail uses a grouped desktop sidebar and a mobile section selector.
The seven editorial checks use canonical saved coverage; website publication is
explicitly **Publicado en tienda**. Operational alerts are rules, not AI insights.
Existing assessments are estimates, not search ranking. `analytics` remains a
compatible alias for the competitor comparison section.

**Guardar ficha** atomically saves Datos, Clasificación, Descripciones/FAQs and
SEO/GEO. Each core section also has its contextual save. Images/video,
competitors, variants and Packs retain explicit independent operations. Drafts
survive section changes; leaving the product or native Odoo action asks to stay
or discard, and offers save-and-leave only if all dirty scopes are covered by the
atomic fiche action. Edits made while saving remain pending.

Mercado Libre support is optional. Install `bader_product_intelligence_meli`
16.0.1.0.0 explicitly alongside the existing integrator; BPI alone reports the
missing extension without pretending zero products or successful verification.
The existing eight KPIs and seven editorial checks stay unchanged. Six separate
ML metrics and per-row status use normal-ACL batched local evidence, scoped by
category, account and selected companies. KPI drill-down resets search/quality
and page while preserving category/account.

The monitoring surface never publishes or synchronizes listings. Single payment,
3 and 6 installments are payment conditions, not marketplace commissions. Only
a manually requested asynchronous product/account observation may read the ML
API, when existing environment switches and manager permissions allow it. In QAS
`read_enabled=False`, `write_enabled=False`, `dry_run=True` remain mandatory.
No live API certification is implied. See the bridge README for evidence,
identity/freshness contracts and isolated observer security.
