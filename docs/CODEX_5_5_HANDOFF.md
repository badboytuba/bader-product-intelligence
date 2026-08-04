# Codex Handoff — Bader Product Intelligence

_Last updated: 2026-08-04_

This file is the operational handoff for the Odoo 16 addon. Never print or commit the local `.env`.

## Repository and release state

- Repository: `https://github.com/badboytuba/bader-product-intelligence.git`
- Technical addon directory: `bader_product_intelligence`
- Odoo app: `Producto Intelligence`
- Current feature branch: `feature/bpi-pack-variant-control`
- Release: `16.0.1.2.0`
- Certified base: `16.0.1.1.14`, commit `e359464`
- License: `LGPL-3`
- Target: Odoo Community `16.0`
- Dependencies: `product`, `web`, `website_sale`, `product_pack`, `sale_product_pack`, `stock_product_pack`

Release `1.2.0` is deliberately separate from the certified `1.1.14` stabilization. PROD must remain on its approved version until functional approval for Packs and variants.

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
- `models/product_template.py` — product kind, variant/Pack payloads, effective ranges, Pack revision and bounded AI context.
- `models/product_intelligence.py` — updates, image security, Pack validation, external services, competitors and AI workflows.
- `controllers/main.py` — admin JSON routes and template/variant ownership checks.
- `models/ai_job.py` — background SEO job and cron processing.
- `models/product_public_category.py` — category intelligence fields/payload.
- `models/res_config_settings.py` — OpenAI, Firecrawl and exchange-rate settings.

### Frontend

- `static/src/js/product_intelligence_action.js` — OWL state, dashboard/detail flows, Pack autocomplete/composition and variant mutations.
- `static/src/xml/product_intelligence_templates.xml` — dashboard, tabs, forms, image/competitor/chat UI.
- `static/src/scss/product_intelligence.scss` — scoped backend styles.
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

## Validation status for 16.0.1.2.0

Local static validation:

```bash
python3 ~/.codex/skills/bader-product-intelligence-dev/scripts/validate_addon.py . --require-node
git diff --check
```

Final QAS certification for the code tree published in the feature PR:

- backend: **20 tests**, 0 failures/errors;
- OWL QUnit: **10 tests**, **28 assertions**, 0 failures;
- live read-only payload check: existing Pack and multi-variant templates returned all required contracts;
- public `/update_pack` contract: camelCase `packRevision`;
- installed module version: `16.0.1.2.0`;
- service restored active, temporary QUnit users removed, and the preexisting view state restored.

## Safe QAS/PROD deployment

QAS full rollback backup for this release:

```text
/opt/odoo/backups/bpi_pack_variants_16.0.1.2.0_20260804T121116Z
```

Rules:

1. Preserve the parent runtime worktree and both existing `.git` directories.
2. Deploy a checksum-verified Git archive without `.git`; never use `git reset`, `git clean`, `--delete` or remote changes.
3. Upgrade only `bader_product_intelligence`.
4. Keep DB/filestore/addon backups and SHA256 metadata.
5. Confirm service, cron, module version, logs and tracked-file checksums after update.
6. Keep PROD untouched until explicit functional approval for `1.2.0`.

QAS has an unrelated preexisting `stock_inventory` mismatch: active view ID `2835` references missing field `stock_inventory_batch_size`. For isolated BPI upgrades/tests only, preserve its original active value, disable it temporarily, and restore it in a trap. Do not commit or deploy a workaround for this unrelated issue as part of BPI.

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
