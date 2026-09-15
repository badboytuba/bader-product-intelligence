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

## 2026-09-11 — AI/provider and competitor reliability patch

Release target `16.0.1.6.1`, QAS only. Read `AI_COMPETITOR_QAS.md` for
provider-boundary validation, safe UI errors and competitor evidence semantics.
New competitor fields require a normal BPI upgrade. The optional ML bridge and
native integrator remain unchanged with read/write disabled and dry-run enabled.
Runtime proof: workspace `audit_outputs/bpi_ai_enable_20260911/`; never infer
live verification from model authentication or mocked tests alone.

---

## 2026-09-11 — Product workspace + optional Mercado Libre bridge

Release target: BPI `16.0.1.6.0` plus explicitly installed
`bader_product_intelligence_meli` `16.0.1.0.0`, **QAS only**.

- Product detail: corporate compact hero, desktop sidebar/mobile selector,
  canonical seven-check editorial status, operational alerts, contextual saves,
  native Odoo leave guard and independent media/Pack/variant/competitor actions.
- ML projection: six separate home metrics, catalog summaries and account-aware
  detail grouping by variant / User Product / category / payment conditions.
  Existing eight BPI KPIs and seven editorial checklist items are unchanged.
- Base `models/meli_provider.py` supplies optional hooks; without the bridge the
  interface reports unavailable rather than fabricating zeros. Canonical saved
  product payload includes ML context/summary; stale account permission errors
  cannot roll back otherwise valid BPI saves.
- Bridge performs batched normal-ACL local projections only on navigation.
  Manual async observer has isolated protected cache/jobs, strict source identity
  and source-record permissions, bounded GET requests, no importer/task ACK or
  integration writes. Read/write ML settings are never changed by the addon.
- Keep QAS `read_enabled=False`, `write_enabled=False`, `dry_run=True`.
  Test external paths with controlled responses, not live marketplace calls.
  Stock and prices need individual current-generation evidence <=60min; expected
  values displayed are explicitly last stored integrator targets, not draft or
  new pricelist/free_qty calculations. ML publication is distinct from website.
- Deployment evidence belongs to workspace artifact directory
  `audit_outputs/bpi_detail_meli_20260911/`. Never commit private credentials,
  database dumps, filestore backups or `.env`.

---

# Codex Handoff — Bader Product Intelligence

_Last updated: 2026-09-11_

## Catalog workbench — 16.0.1.5.0 (QAS only)

User approved the executive home and requested a more useful Catálogo. Read `CATALOG_WORKBENCH.md` for the new per-row seven-section presence contract, `complete`/`needs_attention`, allowlisted `sort_key` (default `catalog`, price sorts explicitly base USD), inline review and editor shortcuts. All reads retain company/ACL scope; reuse one metadata-only batch. New `catalog.scss` is scoped to catalog state only; a single table becomes mobile cards. Preserve per-row toggle pending/DOM rollback, async guards and prior atomic saves. Actual deployment proof belongs in the delivery certificate; PROD remains unauthorized.

## Executive home — 16.0.1.4.0 (QAS-only delivery)

Branch: `feature/bpi-executive-dashboard`, based on certified QAS runtime `32b12c1` / `16.0.1.3.1`. The user approved an executive hybrid petroleum/light dashboard, separate **Visión general / Catálogo**, eight current-state coverage KPIs and exact catalog drill-down. Historical trends, sales integration, automatic generation and PROD are outside scope.

- See `EXECUTIVE_DASHBOARD.md` for metric/filter semantics and validation invariants.
- `/dashboard_overview` is read-only, admin-only and uses the same coverage predicates as `/dashboard` filters. Every primary KPI counts active saleable templates in selected companies/category; no historical series or real search-ranking claims.
- Overview loads lazily without operational product payloads or external calls. Catalog remains paginated. Both reads forward a captured `user.context` so the selected Odoo companies are respected.
- Section/category navigation invalidates stale operations. Detail return restores the originating home section, filters and page. Preserve the `16.0.1.3.1` atomic-save, draft and SEO-preview invariants.
- New `dashboard.scss` is backend-only and scoped to `.bpi-home`; do not apply it to the product detail or storefront.
- Delivery certification is recorded separately; do not infer deployment from this source version. Server Git directories/remotes must remain untouched.

## Previous stabilization — 16.0.1.3.1 (certified QAS)


Branch: `fix/bpi-qas-stabilization-20260911`. User authorized fixing the seven priority findings and updating QAS only; PROD is excluded. The older certification records below remain historical evidence.

- `/save_all` accepts `product_tmpl_id`, `product_values`, `category_values`, `content_values`, `seo_data` and returns the full detail payload. It uses a savepoint within one HTTP transaction; the Datos category takes precedence, and SEO metadata cannot overwrite content saved in that transaction.
- All async workspace operations use product/navigation-generation/request identity. Partial detail updates merge against submitted snapshots rather than replacing every draft. SEO and dashboard polling discard stale responses.
- `analyze_seo` now returns normalized metadata proposals without database writes. `save_seo_payload` uses PATCH semantics: omitted descriptions, FAQs and keyword types remain unchanged. The content generator keeps its 45–70 / 350–650 word split.
- Jobs return `{"seoData": ...}` only. A partial unique index enforces one pending/running job per product/type/audience. Real SQLSTATE40001 lets Odoo retry conflicting creation. Session advisory locks survive visibility commits; terminal-state recovery only retries database persistence, never the provider. Unlocked jobs running over 30 minutes are failed by the next cron rather than replayed.
- Video parsing validates supported hosts and query parameters. Invalid legacy URLs yield an empty embed; new invalid saves are rejected before writing.
- Exchange-rate and bridge-sync public model methods validate `base.group_system` before `sudo()`.
- Backend suite: 45 actual test methods passed on an isolated restored QAS DB, plus three real-transaction concurrency/final-commit/lock-release checks. Frontend suite expanded to 30 QUnit tests; integrated browser certification is tracked with release delivery evidence.

Do not replace the server Git directories or reset dirty runtime worktrees. The QAS runtime is a deployed file tree, not its old Git HEAD. Stage/backup/upgrade only `bader_product_intelligence`.

This file is the operational handoff for the Odoo 16 addon. Never print or commit the local `.env`.

## Repository and release state

- Repository: `https://github.com/badboytuba/bader-product-intelligence.git`
- Technical addon directory: `bader_product_intelligence`
- Odoo app: `Producto Intelligence`
- Current feature branch: `feature/bpi-technical-description`
- PROD deployed release: `16.0.1.2.3`
- QAS certified candidate: `16.0.1.3.0`
- PROD certified runtime: `881a580e295e9ce57c2107d42783fa1d8c1efea7`; package SHA256 `d7a77f2c928258e47ec4929af75ea31ff45dc8bb3e58c8abf596599c9e3d5123`
- QAS candidate runtime: `f65600d`; package SHA256 `c9804160e9e06d01aff71d01c3f40e25578ea5d3bc0f4dee16df2db4a1476c31`
- License: `LGPL-3`
- Target: Odoo Community `16.0`
- Dependencies: `product`, `web`, `website_sale`, `product_pack`, `sale_product_pack`, `stock_product_pack`

Release `1.2.2` builds on the certified `1.2.1` Pack/variant release and adds a safe Word-like editor toolbar for the optimized product description. It passed its own QAS certification and was deployed to PROD on 2026-08-10.

Release `1.2.3` publishes saved, complete Producto Intelligence FAQs below the main product block. It uses a `compute_sudo` JSON projection on `product.template`, so public visitors receive only escaped question/answer copy while `bpi.product.faq` keeps its manager-only ACL. The section uses native `details`/`summary` controls, a dedicated frontend SCSS asset path and Schema.org FAQ semantics; Google removed FAQ rich results in 2026, so this markup is semantic metadata rather than a rich-result promise. The release passed QAS certification and was deployed and certified in PROD on 2026-08-10.

Release `1.3.0` is the separate short-commercial/long-technical content release. Nancy returns a 45–70 word optimized summary plus a 350–650 word technical HTML document. Both use the same frontend allowlist and Odoo HTML sanitization; the compact summary stays beside the purchase area and the full-width technical section renders after the product/image block and before FAQs. Existing descriptions are not automatically shortened or copied, so no catalog data changes until an operator saves new content. Runtime `f65600d` is certified in QAS; PROD authorization is still pending.

## Rich-text description behavior

The Content tab uses the existing `contenteditable` surface with an addon-owned toolbar rather than a third-party editor. It supports headings/paragraphs, allowlisted font families and sizes, text/highlight colors, emphasis, alignment, lists, indentation, HTTP(S) links, undo/redo and format cleanup.

The frontend converts legacy browser `<font>` markup to safe `<span style="...">` HTML and retains only explicitly permitted tags, links and CSS properties. Odoo's `fields.Html` sanitizer is also enabled with style sanitization. The formatted value remains in `bpi_ai_generated_description`; `description_sale` continues to receive the corresponding plain text for native Odoo compatibility and storefront fallback.

The active `bader_product_intelligence.bpi_product_detail_extensions` view inherits `website_sale.product` at priority 90 and replaces only the standard short-description node. It renders the formatted BPI HTML when present and otherwise preserves the native `description_sale`. Because Odoo Website can create XML-ID-less website-specific primary copies of that template, `ir.ui.view.bpi_sync_product_description_bridges()` creates a module-owned child extension for every active copy during module update. This bridge does not render Pack composition or introduce a dependency on `bader_website`.

## Scope

The addon provides:

- backend catalog dashboard and product workspace;
- SEO/GEO, content, taxonomy and FAQ generation;
- product-owned gallery/Studio image workflows;
- competitor discovery, scrape, normalization, analytics and strategy;
- product-isolated Nancy AI chat;
- background SEO jobs;
- native `product.product` operational controls for variants;
- existing OCA Pack configuration and per-variant compositions.

Content, SEO, category, competitors and chat remain owned by `product.template`. No new model, column or data migration was introduced for Packs/variants.

## Pack and variant behavior

### Product kinds and payloads

`/dashboard` and `/data` identify each template as:

- `simple`
- `variants`
- `pack`
- `pack_variants`

The detail payload includes:

- `variantSummary`: count, active/available counts and effective price/cost/stock ranges;
- `variants[]`: IDs, attribute values, SKU, barcode, active state, native price extra/effective price, cost, stock and own-image metadata;
- `pack`: OCA configuration, SHA-256 `revision`, metrics, warnings and composition for each Pack variant.

Dashboard rows expose kind/count badges and native effective ranges. Analytics uses the effective Pack price or the variant min–max interval rather than an arbitrary template base price.

### Variant mutations

`/bader_product_intelligence/update_variant` requires `product_tmpl_id`, `product_variant_id` and an allowlisted `values` object. Editable fields are:

- `sku`
- `barcode`
- `costUsd`
- `active`

Price and stock stay read-only and are calculated by Odoo/OCA.

`/bader_product_intelligence/set_variant_image` accepts exactly one operation:

- `image_token` belonging to the same template;
- `image_data_url` validated as PNG/JPEG/WebP up to 10 MiB;
- `remove=true` to clear only `image_variant_1920`.

### Pack mutations

`/bader_product_intelligence/search_pack_components` performs a bounded variant search (maximum 20) and does not load the entire catalog.

`/bader_product_intelligence/update_pack` requires:

- `product_tmpl_id`
- camelCase `packRevision`
- full `values` containing Pack configuration and all per-variant compositions

The service writes the composition atomically and rejects stale revisions, unknown enums, missing Pack variants, duplicates, quantities `<= 0`, discounts outside `0..100`, self-reference, inactive new components, cross-company components and recursive Pack graphs. Existing archived components are preserved with warnings unless the operator explicitly changes the composition.

Ordinary products cannot be converted to Packs in this workspace; `pack_ok=True` must be configured in the standard Odoo form.

OCA modes remain native:

- Pack type: `detailed`, `non_detailed`
- Component price mode: `ignored`, `totalized`, `detailed`
- Stock/availability: official `stock_product_pack` computation

## AI context

Content, SEO, category, image, competitor strategy and chat prompts receive a bounded safe summary of the variants or Pack components. This helps Nancy understand the commercial product while retaining one content/SEO/chat identity per template.

## Code map

### Backend

- `__manifest__.py` — version, OCA dependencies, views and asset bundles.
- `models/product_template.py` — product kind, variant/Pack payloads, effective ranges, Pack revision, bounded AI context, sanitized technical description and the ACL-safe public FAQ projection.
- `models/ir_ui_view.py` — synchronizes the formatted-description bridge to website-specific product template copies.
- `models/product_intelligence.py` — updates, image security, Pack validation, external services, competitors and AI workflows.
- `controllers/main.py` — admin JSON routes and template/variant ownership checks.
- `models/ai_job.py` — background SEO job and cron processing.
- `models/product_public_category.py` — category intelligence fields/payload.
- `models/res_config_settings.py` — OpenAI, Firecrawl and exchange-rate settings.

### Frontend

- `static/src/js/product_intelligence_action.js` — OWL state, dashboard/detail flows, Pack autocomplete/composition and variant mutations.
- `static/src/xml/product_intelligence_templates.xml` — dashboard, tabs, forms, image/competitor/chat UI.
- `static/src/scss/product_intelligence.scss` — scoped backend styles.
- `static/src/scss/storefront_technical_description.scss` — responsive public technical-description layout.
- `static/tests/product_intelligence_tests.js` — QUnit tests.

### Views/security/tests

- `views/category_views.xml` — separate primary BPI category tree/form with Parent Category restored in the native screen.
- `views/product_intelligence_action.xml` — client action/menu.
- `security/ir.model.access.csv` — persistent-model ACLs for `base.group_system`.
- `tests/test_product_intelligence.py` — backend TransactionCase coverage.

## Security rules retained from 1.1.14

- Backend routes require `base.group_system`.
- Gallery/Studio references and deletion use product-owned tokens.
- Image input enforces strict base64, MIME, signature and 10 MiB limits.
- URL import validates every redirect, rejects private/reserved destinations and bounds redirect/byte counts.
- Chat sessions and late responses are isolated by product.
- Competitor mutations validate product ownership.
- Competitor analytics uses normalized USD values while preserving original amount/currency.
- Logs omit raw external bodies, sensitive URLs and raw provider errors.

## Validation status for 16.0.1.2.1

Local static validation:

```bash
python3 ~/.codex/skills/bader-product-intelligence-dev/scripts/validate_addon.py . --require-node
git diff --check
```

Final QAS certification for the code tree published in the feature PR:

- backend: **18 tests**, 0 failures/errors;
- OWL QUnit: **11 tests**, **32 assertions**, 0 failures;
- live read-only payload check: existing Pack and multi-variant templates returned all required contracts;
- public `/update_pack` contract: camelCase `packRevision`;
- installed module version: `16.0.1.2.1` after the OWL compatibility hotfix;
- normal and `debug=assets` action openings: dashboard rendered, 0 dialogs/runtime exceptions;
- real Pack search Enter: default prevented and component results returned;
- service restored active, temporary QUnit users removed, and the preexisting view state restored.

## Final validation status for 16.0.1.2.2

- Local addon validator with Node required: passed.
- Python compile, XML parse, JavaScript syntax, RPC contract, Git hygiene and SCSS compilation: passed.
- QAS backend: **20 tests**, 0 failures/errors.
- QAS OWL QUnit: **12 tests**, **45 assertions**, 0 failures.
- QAS product 107: both Odoo origin and authenticated edge rendered `data-bpi-description="formatted"`, formatted paragraphs/list/emphasis and no native fallback text.
- QAS package: 31 files matched the certified archive; service active, zero open AI jobs, zero temporary QUnit users and the nested addon Git config preserved.
- PROD product 170: both origin and public edge rendered formatted BPI HTML with paragraphs, list and emphasis instead of literal formatting characters.
- PROD module `16.0.1.2.2`: service active, website-specific bridge active, zero open AI jobs and checksum-verified rollback assets present.

## Final validation status for 16.0.1.2.3

- Local addon validator with Node required, Python compilation, XML parsing, RPC/Git hygiene and standalone SCSS compilation: passed.
- QAS backend: **21 tests**, 0 failures/errors.
- QAS OWL QUnit: **12 tests**, **45 assertions**, 0 failures; temporary user removed.
- QAS product 107: seven FAQ items rendered after `Referencia interna`, with first item open, semantic schema, compiled CSS and successful desktop/mobile visual inspection.
- PROD product 170: public edge and Odoo origin rendered seven complete FAQ items with the expected copy, placement, schema, first-open behavior and compiled styles.
- QAS and PROD runtime: all **32 files** matched the certified archive; services active, zero open AI jobs and no new BPI errors.
- PROD rollback evidence: database dump passed `pg_restore -l`, addon tar listing passed and the hard-linked filestore snapshot file list matched.

## Final validation status for 16.0.1.3.0 (QAS)

- Local addon validator with Node required, Python compilation, XML parsing, JavaScript syntax, RPC/Git hygiene and asset invariants: passed.
- QAS backend: **22 tests**, 0 failures/errors and no cache deprecation warnings.
- QAS OWL QUnit: **13 tests**, **51 assertions**, 0 failures.
- Real backend Content tab: compact optimized editor measured **180 px** and technical editor **420 px**, both with independent allowlisted rich-text toolbars.
- Public product test: technical content rendered full-width before seven FAQs on desktop/mobile without overflow; the temporary sample was restored and product 107 technical content remains empty.
- QAS runtime: all **33 files** matched package SHA256 `c9804160e9e06d01aff71d01c3f40e25578ea5d3bc0f4dee16df2db4a1476c31`; service active, zero open AI jobs, zero temporary visual users and Git configs preserved.
- QAS rollback evidence: database dump passed `pg_restore -l`, addon snapshots exist and the hard-linked filestore snapshot list contains the same **17,603** entries as the baseline.
- PROD remains on `16.0.1.2.3`; do not deploy `1.3.0` without explicit authorization.

## Safe QAS/PROD deployment

Full rollback backups for the rich-text release:

```text
QAS:  /opt/odoo/backups/bpi_rich_text_16.0.1.2.2_20260810T141150Z
PROD: /opt/odoo/backups/bpi_rich_text_16.0.1.2.2_20260810T144036Z
```

Full rollback backups for the storefront FAQ release:

```text
QAS:  /opt/odoo/backups/bpi_storefront_faq_16.0.1.2.3_20260810T150124Z
PROD: /opt/odoo/backups/bpi_storefront_faq_16.0.1.2.3_20260810T152108Z
```

Full rollback backup for the QAS technical-description candidate:

```text
QAS:  /opt/odoo/backups/bpi_technical_description_16.0.1.3.0_20260810T155913Z
PROD: not deployed
```

Rules:

1. Preserve the parent runtime worktree and both existing `.git` directories.
2. Deploy a checksum-verified Git archive without `.git`; never use `git reset`, `git clean`, `--delete` or remote changes.
3. Upgrade only `bader_product_intelligence`.
4. Keep DB/filestore/addon backups and SHA256 metadata.
5. Confirm service, cron, module version, logs and tracked-file checksums after update.
6. Reuse the certified package hash above for any rollback/redeploy verification.

The former QAS `stock_inventory` code/view mismatch was remediated separately on 2026-08-04. Do not disable view 2835 during BPI upgrades; validate it normally with the official `stock_inventory` 16.0.3.0.0 runtime.

## Secrets and external services

Real configuration belongs in Odoo system parameters, server environment or the ignored local `.env`.

Supported environment fallbacks include:

- `BPI_OPENAI_API_KEY` / `OPENAI_API_KEY`
- `BPI_OPENAI_TEXT_MODEL`
- `BPI_OPENAI_IMAGE_MODEL`
- `BPI_OPENAI_IMAGE_EDIT_MODEL`
- `BPI_OPENAI_REASONING_EFFORT`
- `BPI_OPENAI_TEXT_VERBOSITY`
- `BPI_FIRECRAWL_API_KEY` / `FIRECRAWL_API_KEY`
- `BPI_FIRECRAWL_BASE_URL`

The code uses direct HTTP requests, not the OpenAI Python SDK. Keep model names configurable, `store: false`, product/private data out of logs, and provider errors user-safe.

## Deferred scope

- Public website Pack rendering and `website_sale_product_pack`.
- MRP phantom Kits/BoMs.
- New background job types beyond SEO.
- Automatic propagation of changes to Pack components.
