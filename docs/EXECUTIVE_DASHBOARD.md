# Executive dashboard — 16.0.1.4.0

## Scope and navigation

Corporate hybrid home in Spanish, with **Visión general / Catálogo**. The native Odoo navbar and product detail are unchanged. The overview is a current snapshot, not historical telemetry. No new persistent models, cron, provider calls, sales/traffic analytics or API cost estimates are introduced.

Category selection is shared. A KPI/priority switches to the catalog, clears its text search and page, selects the normal saleable tab and sets the corresponding quality filter. Category changes reset the page. Opening a product and returning preserves the home section, category, quality filter, search and page. Explicit refresh and returning from detail reload current data; there is no continuous polling. Base catalog tabs clear quality filters while preserving category/search.

## Universe and metrics

Primary universe: active `product.template` records with `sale_ok`, shared or in the currently selected companies, subject to normal user ACLs/record rules. Category filtering uses e-commerce categories and descendants; multiple category memberships never duplicate a template. Variants and Packs count once per template.

| Key | Meaning |
|---|---|
| `all` | Entire primary universe |
| `published` / `unpublished` | Current website publication state |
| `content` | Commercial text using the existing BPI/native description fallback, plus real text in `bpi_technical_description` |
| `image` | Image available under the existing native gallery/variant/approved-BPI fallback; previews do not count |
| `seo` | Saved SEO title and description with real text |
| `geo` | Saved GEO title and description with real text |
| `faq` | At least one complete question/answer pair |
| `competitor` | At least one nonblank registered competitor URL, regardless of collection state |
| `category` | At least one e-commerce category |

HTML-only markup, whitespace and nonbreaking spaces do not constitute content. Every percentage uses the same filtered universe; empty universes produce zero, never NaN. SEO/GEO coverage is not ranking, an AI evaluation, or proof of an analysis. Existing score zero and `bpi_last_analyzed_at` are not used as analysis provenance.

Priorities, in order: `published_missing_image`, `published_missing_content` (commercial text only), `missing_seo`, `missing_geo`, `missing_category`. Groups can overlap. All filters use the same coverage-set builder as their KPI counts.

“Sin publicar” retains the legacy wire tab `new`; it never means recently created. The `discontinued` tab is explicitly labeled “Archivados / No disponibles para venta” and includes archived or nonsaleable templates. Its filters intersect that separate universe.

## Internal JSON interfaces

- `/bader_product_intelligence/dashboard_overview(category_id=false)` returns `generatedAt`, `categoryId`, `categories`, `total`, `kpis`, `publication`, `coverage`, `priorities`, `jobs`, `exchangeRate`.
- Metric entries: `key`, `label`, `count`, `percent`, `description`, `filter`. Filters are allowlisted string keys.
- `jobs`: current pending/running counts and total done/failed counts, plus at most five recent SEO jobs in the same product scope. Recent entries contain identifiers, product name, state, creation and completion dates; no prompts, result payloads or provider error bodies.
- `/dashboard` and `/sync_catalog` retain legacy parameters/payload keys and accept `category_id` and `quality_filter`. Pager/tab counts include category, quality and text search. Legacy `stats` refers to the active saleable category universe.
- Browser dashboard requests send an immutable `context` snapshot from Odoo's user service, including `allowed_company_ids`. Invalid categories/filters/types raise controlled errors.

Dates are UTC ISO strings with `Z`. The browser displays the actual fetch timestamp rather than a synthetic real-time badge. Finished jobs are proposals requiring review/save, not automatic publication.

## Engineering and safety

The `models/dashboard.py` abstract service extension centralizes bounded related-model reads, explicit content fields and attachment-size metadata. Do not build detail/Pack/stock payloads for overview. Keep publication dependencies preloaded and avoid per-product queries. Image presence uses `ir.attachment` metadata restricted to accessible origin records, never binary fields, downloads or filesystem reads. In Odoo 16 a cold computed `datas` field can still load raw files despite `bin_size=True`; cold-cache tests must prohibit `_file_read`.

Routes and public service entrypoints require administrator membership; there is no broad sudo. Home section/category changes invalidate request generations. Old responses cannot change the current section/category/product. Catalog mutation buttons are disabled while rows are refreshing; overview actions are disabled while refreshing and unavailable on error.

Visual changes live under `.o_action.bpi-app .bpi-home`; `dashboard.scss` is included only in `web.assets_backend`. No external chart/font dependency. Mobile tables may scroll internally, never overflow the page. Labels, focus, keyboard activation, reduced motion and loading/error/empty states are required.

## Validation and delivery

Retain existing stabilization tests; add exact-count/drill-down, empty HTML, alternative images, category hierarchy, archive/Pack/variant, selected-company/record-rule, no-provider/binary read, query-scaling and async navigation tests. Certify actual Odoo/QUnit, plus overview/catalog at 360/768/1024/1440px and detail-return behavior. Browser certification must route or intercept the native bus WebSocket correctly; a direct HTTP tunnel is not the evented port.

Upgrade only this addon to `16.0.1.4.0` after QAS backups and isolated certification. Preserve server `.git` and remotes. PROD is not authorized. Record actual release commit, package hashes and certification separately; a source manifest version alone is not evidence of deployment.
