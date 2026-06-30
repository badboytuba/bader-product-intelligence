# Codex 5.5 Handoff — Bader Product Intelligence

_Last updated: 2026-06-30_

This document is intentionally detailed because the next development agent may only have access to GitHub and not to local Engram memory, local skills, IDE history, or `.env`.

## Repository / module identity

- GitHub repo observed locally: `https://github.com/badboytuba/bader-product-intelligence.git`
- Current local branch at handoff time: `main`
- Odoo technical addon directory name required at install/deploy time: `bader_product_intelligence`
- Odoo app name: `Producto Intelligence`
- Odoo target: Community `16.0`
- License in manifest: `LGPL-3`
- Main dependencies: `product`, `web`, `website_sale`
- Main UI: backend OWL client action registered as `bader_product_intelligence.action`

If another GitHub repository is part of the user’s workflow, it was not configured as a remote in this checkout. This checkout only exposes `origin` for `badboytuba/bader-product-intelligence`.

## What this app does

The addon brings Product Intelligence workflows into Odoo:

- backend catalog dashboard with tabs for active, new/unpublished, and discontinued products;
- product detail workspace with tabs for overview, data, categorization, content, images, SEO, competitors, analytics, and chat;
- SEO/GEO generation through OpenAI Responses API;
- AI-generated descriptions, FAQ generation, and taxonomy suggestions;
- image generation/editing through OpenAI image endpoints;
- gallery/reference-image handling for Odoo product images plus BPI-generated images;
- competitor discovery via DuckDuckGo HTML search plus AI reranking;
- competitor scraping through Firecrawl when configured, with fallback direct HTTP scraping;
- product-level AI chat assistant;
- cron-backed background job for SEO/GEO generation.

## Important secret handling

The local `.env` can contain production/deploy credentials and API keys. Never print or commit it.

The repo includes `.env.example` with only key names/default placeholders. Real values belong in Odoo system parameters, server environment, or a local untracked `.env`.

Environment fallback keys currently supported by backend code:

- `BPI_OPENAI_API_KEY` or `OPENAI_API_KEY`
- `BPI_OPENAI_TEXT_MODEL`
- `BPI_OPENAI_IMAGE_MODEL`
- `BPI_OPENAI_IMAGE_EDIT_MODEL`
- `BPI_OPENAI_REASONING_EFFORT`
- `BPI_OPENAI_TEXT_VERBOSITY`
- `BPI_FIRECRAWL_API_KEY` or `FIRECRAWL_API_KEY`
- `BPI_FIRECRAWL_BASE_URL`

## Code map

### Manifest / bootstrapping

- `__manifest__.py`
  - version currently `16.0.1.1.13` at handoff time;
  - data files include ACLs, AI job cron, product/category/settings/action views, inactive website bridge stub;
  - assets include backend SCSS/JS/XML, QWeb template, and frontend SCSS.
- `__init__.py`
  - imports controllers and models.
- `models/__init__.py`
  - imports `product_template`, `product_public_category`, `product_intelligence`, `ai_job`, `res_config_settings`.

### Controllers

- `controllers/main.py`
  - all routes are `type="json"`, `auth="user"`;
  - `_ensure_manager()` enforces `base.group_system`;
  - routes:
    - `/bader_product_intelligence/dashboard`
    - `/bader_product_intelligence/sync_catalog`
    - `/bader_product_intelligence/update_exchange_rate`
    - `/bader_product_intelligence/data`
    - `/bader_product_intelligence/update_product`
    - `/bader_product_intelligence/generate_content`
    - `/bader_product_intelligence/save_content`
    - `/bader_product_intelligence/generate_faq`
    - `/bader_product_intelligence/save_category`
    - `/bader_product_intelligence/reclassify_category`
    - `/bader_product_intelligence/analyze_seo` (legacy/direct sync route)
    - `/bader_product_intelligence/ai_job/start_seo`
    - `/bader_product_intelligence/ai_job/status`
    - `/bader_product_intelligence/save_seo`
    - `/bader_product_intelligence/save_video`
    - `/bader_product_intelligence/generate_image`
    - `/bader_product_intelligence/approve_image`
    - `/bader_product_intelligence/add_image_url`
    - `/bader_product_intelligence/delete_image`
    - `/bader_product_intelligence/discover_competitors`
    - `/bader_product_intelligence/add_competitor`
    - `/bader_product_intelligence/scrape_competitor`
    - `/bader_product_intelligence/analyze_competitor`
    - `/bader_product_intelligence/delete_competitor`
    - `/bader_product_intelligence/generate_strategy`
    - `/bader_product_intelligence/chat`

### Core models/service

- `models/product_template.py`
  - extends `product.template` with BPI fields: brand, slug, previous price, featured, GEO title/description/features, AI description/tone/audience, SEO/GEO/competitiveness scores, video URL/embed, competitive strategy JSON, intelligent categorization fields, One2manys for keywords/FAQs/images/competitors/chat sessions;
  - helper payload builders:
    - `_bpi_native_gallery_payload()` returns native Odoo main/gallery/variant images with IDs like `main`, `odoo:<id>`, `variant:<id>`;
    - `_bpi_reference_images_payload()` returns selectable reference tokens for image generation;
    - `_bpi_gallery_payload()` combines native images and BPI images, with BPI image IDs like `bpi:<id>`;
    - `bpi_dashboard_payload()` drives dashboard rows;
    - `bpi_build_payload()` drives full detail UI.
- `models/product_public_category.py`
  - extends `product.public.category` with category intelligence metadata and `bpi_to_payload()`.
- `models/product_intelligence.py`
  - defines persistent models:
    - `bpi.product.keyword`
    - `bpi.product.faq`
    - `bpi.product.image`
    - `bpi.product.competitor`
    - `bpi.product.chat.session`
    - `bpi.product.chat.message`
  - defines abstract service `bpi.service` containing most business logic:
    - config/environment fallback;
    - OpenAI request/response helpers;
    - JSON parsing and image extraction;
    - image reference conversion;
    - external URL validation;
    - dashboard/search/tab pagination;
    - product update/save routines;
    - content/FAQ/category/SEO generation;
    - image generation/save/import/delete;
    - competitor discovery/search/rerank/scrape/analyze/strategy;
    - product chat.
- `models/ai_job.py`
  - model `bpi.ai.job` for background AI processing;
  - current job type: `seo`;
  - `create_seo_job()` deduplicates active jobs by product/type/audience;
  - `_cron_process_pending_jobs(limit=1)` processes pending jobs;
  - `_process_job()` writes running/done/failed states and commits for UI polling visibility;
  - `_process_seo_job()` calls `bpi.service.analyze_seo()` and stores `seoData` + refreshed detail payload.
- `models/res_config_settings.py`
  - Odoo settings fields for OpenAI API/model/reasoning/verbosity, Firecrawl key/base URL, and exchange rate.

### Views / data / security

- `security/ir.model.access.csv`
  - grants full CRUD to `base.group_system` for BPI persistent models including `bpi.ai.job`.
- `data/ai_job_cron.xml`
  - cron `Producto Intelligence: procesar jobs IA`, every 1 minute, `model._cron_process_pending_jobs(limit=1)`, user `base.user_root`.
- `views/product_views.xml`
  - adds a product form stat button to open the BPI client action.
- `views/category_views.xml`
  - tree/form views for category intelligence.
- `views/product_intelligence_action.xml`
  - client action and admin menu items.
- `views/res_config_settings_views.xml`
  - settings block for OpenAI/Firecrawl/exchange rate.
- `views/website_product_templates.xml`
  - inactive deprecated QWeb stub only. It does not currently render BPI data on the storefront.

### Frontend

- `static/src/js/product_intelligence_action.js`
  - OWL component `ProductIntelligenceAction`;
  - registered in action registry under `bader_product_intelligence.action`;
  - state includes dashboard, detail forms, busy flags, SEO job polling, image playground, competitor forms, chat;
  - important methods:
    - `loadDashboard`, `applyDashboardPayload`;
    - `loadDetail`, `applyDetailPayload`;
    - `saveProductData`, `saveCategoryData`, `saveContentData`, `saveSeoData`, `saveAll`;
    - `analyzeSeo`, `pollSeoJob`;
    - `generateContent`, `generateFaq`, `reclassifyCategory`;
    - `generateImage`, `openImageModal`, `generateFromForm`, `sendPlaygroundMessage`, `saveGeneratedImage`, `addImageUrl`, `deleteImage`, `saveVideo`;
    - `discoverCompetitors`, `addCompetitor`, `scrapeCompetitor`, `analyzeCompetitor`, `deleteCompetitor`, `generateStrategy`;
    - `sendChatMessage`, `loadChatHistory`.
- `static/src/xml/product_intelligence_templates.xml`
  - all OWL markup for dashboard/detail tabs/modals/chat.
- `static/src/scss/product_intelligence.scss`
  - scoped styling under `.o_action.bpi-app` plus image playground styles.

## Current behavior and contracts

### Dashboard

- Base domain is currently empty.
- `all` tab means active saleable products: `active=True` and `sale_ok=True`.
- `new` tab means active saleable and not website published.
- `discontinued` means inactive OR `sale_ok=False`, using `active_test=False`.
- Stats currently count active products only for `total`, `published`, `featured`, and `pending`.
- `tabCounts.all` counts active saleable, not every product.

Important: the test `test_dashboard_payload_is_paginated` currently expects `stats.total == 4`, but `_dashboard_stats()` counts active products only. If run in a real Odoo DB, this assertion may need adjustment depending on intended dashboard semantics.

### SEO/GEO generation

- Frontend now starts SEO generation through `/ai_job/start_seo` and polls `/ai_job/status`.
- The older `/analyze_seo` route still exists and directly runs the analysis synchronously.
- OpenAI text calls use `/v1/responses`, JSON object format for structured calls, and `store: False`.
- Configurable text model default in code/docs is `gpt-5.5`; verify model availability for the API project before relying on this default.
- Reasoning payload is added only if model name starts with `gpt-5` and effort is one of `none|minimal|low|medium|high|xhigh`.

### Image generation

- `generate_image()` uses:
  - configured/default image generation model when no references exist;
  - configured/default image edit model when reference images or uploaded reference exist;
  - up to 8 reference images.
- BPI-generated/imported images are saved in `bpi.product.image` only. They are not mirrored into native `product.image` at the moment.
- Native Odoo product images are used as references and displayed in the combined gallery but not owned by BPI.

### Competitor intelligence

- Discovery uses DuckDuckGo HTML/Lite scraping and filters candidates locally.
- AI reranking is attempted; if OpenAI fails, deterministic fallback ranking is used.
- Scraping uses Firecrawl when API key exists, fallback direct HTTP when Firecrawl fails or is absent.
- Direct HTTP scraper manually follows redirects up to 6 times and validates each redirect URL with `_validate_external_url()`.
- External image import currently uses `requests.get(clean_url, timeout=90)` with default redirects; this should be hardened.

### Chat

- Chat sessions are stored per product with a `session_key` UUID.
- Detail payload returns latest chat session/messages.
- Frontend lazy-loads history when chat tab is selected.

## Known issues / recommended first fixes

### 1. Gallery delete mismatch

Current payload IDs:

- native main image: `main`
- native extra image: `odoo:<id>`
- native variant image: `variant:<id>`
- BPI image: `bpi:<id>`

Current JS calls:

```js
this.deleteImage(image.id)
```

Current controller expects:

```python
def delete_image(self, image_id, **kwargs):
    image = self._image(image_id)  # int(image_id)
```

So deleting a BPI image likely sends `bpi:123`, causing `int('bpi:123')` failure. Native images also show the delete button despite `canDelete=False` in payload.

Suggested fix:

- In XML, render delete button only when `image.canDelete` is true.
- In JS, normalize token before RPC: only allow `bpi:<id>` or numeric IDs; strip `bpi:`.
- In backend, validate that image belongs to current product if product id is included.
- Do not allow deleting `main`, `odoo:*`, or `variant:*` via the BPI endpoint unless a separate explicit native-image delete feature is designed.

### 2. Image Studio selected gallery reference is ignored

`generateFromForm()` sends `selected_image_url`, but controller/service signatures ignore it. Clicking a gallery image in the Studio currently only changes UI selection; it is not sent as a reference token unless the image is also selected in `selectedReferences`.

Suggested fix options:

- Better: in the Studio, selecting product images should toggle their existing reference token, not only URL.
- Or: backend accepts a selected gallery token, not arbitrary URL, and resolves it safely to a product-owned image.
- Avoid accepting arbitrary internal `/web/image/...` URLs as server-side fetch input.

### 3. Chat quick action duplicates user message

Current code:

```js
useChatQuickAction(action) {
    this.state.chatMessages.push({ role: "user", content: action });
    this.sendChatMessage(action);
}
```

`sendChatMessage()` also pushes the user message. Remove the push from `useChatQuickAction()`.

### 4. Chat state can survive product switches

`applyDetailPayload()` does not reset `state.chatMessages`/`state.chatSessionKey` from detail payload. If user opens product A then B in the same OWL action, chat state can remain from A.

Suggested fix:

- In `applyDetailPayload(data)`, set `chatMessages` from `data.chatHistory || []` and `chatSessionKey` from `data.chatSessionId || ""`; or reset them whenever `product.id` differs from previous product.

### 5. Competitor price comparison mixes currencies

Product price is `product.list_price`, treated by the UI as USD. Scraped competitor prices are often ARS. `_detect_price_comparison(product.list_price, compared_price)` can therefore produce bad comparisons.

Suggested fix:

- Normalize competitor scraped prices to product currency before comparison.
- If `competitor_currency == 'ARS'`, divide by `product._bpi_exchange_rate()` before comparing with USD list price, or store both raw and normalized values.
- Update UI labels to show currency correctly.

### 6. External image import redirect SSRF hardening

`_validate_external_url()` is good for initial URL and blocks private/reserved/local networks. But `add_image_from_url()` uses default `requests.get`, which follows redirects automatically. A public URL could redirect to a private IP.

Suggested fix:

- Set `allow_redirects=False`, manually follow limited redirects, validate every `Location` with `_validate_external_url()`, similar to `_fetch_competitor_direct()`.
- Re-check final response content type and size.

### 7. Website storefront integration is inactive

`views/website_product_templates.xml` is an inactive stub. If the user asks for storefront rendering, add an active inherit of `website_sale.product` or the actual Bader website template and render BPI description/FAQ/video/gallery carefully.

Important: the README currently says the website module can optionally render Product Intelligence content if `bader_website` is installed. This standalone addon currently does not actively render content.

### 8. Synchronous long operations

Still synchronous in JSON requests:

- image generation/editing;
- competitor discovery/scraping/analysis;
- strategy generation;
- chat.

SEO has a background job now. Consider reusing `bpi.ai.job` or adding job types for images/competitors if worker timeouts are observed.

### 9. Image model defaults must be verified

Defaults in this code are `gpt-image-2` and `gpt-image-1.5`. Confirm availability in the user’s OpenAI project before deployment. If not available, adjust defaults and README/settings.

## Validation performed before this handoff

Static validation in local checkout:

```bash
python3 -m compileall controllers models tests
# Result: OK
```

```bash
python3 - <<'PY'
from pathlib import Path
import xml.etree.ElementTree as ET
for p in list(Path('views').glob('*.xml')) + list(Path('data').glob('*.xml')) + list(Path('static/src/xml').glob('*.xml')):
    ET.parse(p)
    print('XML OK', p)
PY
# Result: OK for all XML files
```

```bash
tmp=$(mktemp --suffix=.mjs); cp static/src/js/product_intelligence_action.js "$tmp"; node --check "$tmp"; rm -f "$tmp"
# Result: OK
```

A plain `node --check static/src/js/product_intelligence_action.js` fails because Odoo JS uses ES module imports and the repo has no `package.json` with `type=module`. The temporary `.mjs` check is the useful syntax check.

No real Odoo 16 install/upgrade test was run from this local checkout during handoff. A future agent should test in QAS/Odoo runtime before production.

## Suggested next workflow for future agents

1. Pull latest `main` from GitHub.
2. Confirm module directory name is `bader_product_intelligence` in the Odoo addons path.
3. Read this handoff, `AGENTS.md`, and `README.md`.
4. Run static validation commands.
5. Fix high-priority bugs before large new feature work unless user directs otherwise.
6. Add/adjust tests for every bugfix where feasible:
   - URL validation/redirect behavior;
   - gallery token delete parsing;
   - taxonomy normalization;
   - dashboard count semantics;
   - currency comparison logic.
7. Validate in Odoo 16 QAS:
   - update app list;
   - install on fresh DB if possible;
   - upgrade on QAS copy of production if possible;
   - check backend assets load;
   - test each tab in the client action;
   - watch Odoo logs.
8. Only deploy to production with explicit user approval, backup, and rollback plan.

## Deployment notes

CLI examples:

```bash
odoo-bin -d <database> -i bader_product_intelligence --stop-after-init
odoo-bin -d <database> -u bader_product_intelligence --stop-after-init
```

Production-safe checklist:

- backup DB;
- backup filestore;
- backup current addon directory;
- deploy only this addon;
- update only this module;
- restart only if required by the environment;
- monitor logs immediately after update;
- keep rollback tar/commit ready.

## Testing notes

Existing tests live in `tests/test_product_intelligence.py` and are tagged `post_install`.

At handoff time, tests cover:

- dashboard payload/pagination;
- product slug generation and featured write;
- category normalization from free-text AI-like values;
- external URL validation blocking private networks.

Recommended additional tests:

- `_validate_external_url()` blocks IPv6 loopback/link-local/private and redirect targets;
- `add_image_from_url()` does not follow unsafe redirect chains;
- BPI image delete accepts only product-owned BPI images;
- `save_seo_payload()` normalizes invalid `aiTargetAudience` values;
- competitor price normalization when scraped ARS prices are compared with USD list price;
- `_parse_price_number()` for Argentine formats (`$ 1.234,56`, `ARS 123.456`, `USD 12.50`).

## Notes for UI changes

The OWL component is large. When editing:

- keep RPC payload names aligned with controller method arguments;
- after backend payload changes, update `applyDetailPayload()` and template uses;
- avoid silently keeping stale state when switching products;
- use `t-att-disabled` for busy flags consistently;
- keep destructive actions behind clear UI constraints (`canDelete`, product ownership checks);
- check the browser console/Odoo asset logs after changes.

## Notes for OpenAI changes

The code uses direct `requests` calls instead of the OpenAI Python SDK. If changing API behavior:

- verify against official OpenAI docs for current endpoint schemas;
- keep `store: False` unless the user wants stored responses;
- avoid logging prompts that may contain product/private data;
- surface user-friendly `UserError` messages;
- keep model names configurable in settings and environment variables;
- do not hardcode real API keys.
