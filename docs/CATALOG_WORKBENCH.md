# Catalog workbench — 16.0.1.5.0

The Catálogo tab is a product work area, not a second executive dashboard. Keep the Visión general, native Odoo navbar and product detail unchanged.

## Interface

- Compact catalog-only header, prominent name/SKU/brand/category search, preparation filter and explicit sorting.
- A single semantic table becomes cards below 900px; never render duplicate product controls for mobile.
- Product identity includes thumbnail, SKU, brand, e-commerce category path and Pack/variant context.
- Preparation shows **N of 7 sections containing information**, not an AI score, quality judgment, search ranking or approval to publish.
- Inline quick review requires no RPC. Its links navigate to existing Datos, Contenido, SEO/GEO, Imágenes or Competidores tabs, without generating, saving or publishing anything.
- Price retains effective variant ranges and ARS/USD display. Margin is estimated; missing cost/nonpositive price produces “Margen no disponible”. Inventory is on-hand quantity, not an unreserved quantity or sales forecast.
- Publication, feature flag, archive/saleability and stock are separate concepts. Do not infer one from another.

## Checklist and server contract

`row.catalogHealth` contains boolean `commercial`, `technical`, `image`, `seo`, `geo`, `faq`, `category`, `competitor`, plus `completed`, `total: 7`, `percent`.

The seven counted sections are commercial description, technical description, image, SEO title+description, GEO title+description, complete FAQ and e-commerce category. Competitor URL registration is optional and excluded from completion. Technical presence is independent of commercial presence. All predicates reuse the executive dashboard batch implementation, including empty-HTML normalization, native/variant/approved-BPI image rules and normal ACL/selected-company scopes.

`complete` is the intersection of those seven sets; `needs_attention` is its complement. These optional quality filters do not change the eight overview KPI definitions. Page enrichment performs one batch only: reuse a quality-filter batch when available, otherwise inspect only the requested page. Never read Binary fields or call providers to obtain checklist flags. `isActive`, `saleOk`, `updatedAt` reflect actual current product state and last write date (UTC ISO), not an AI review date.

`/dashboard` and `/sync_catalog` accept allowlisted `sort_key`:

| Key | Meaning |
|---|---|
| `catalog` | Existing default: website_sequence ascending, name ascending, id descending |
| `recent` | Most recently modified, then id descending |
| `name_asc` / `name_desc` | Product name ascending / descending, with stable id tie-breaker |
| `price_asc` / `price_desc` | Stored **base USD list_price**, not effective Pack/variant price range; labels must explicitly say precio base |

Response `sortKey` reports the accepted sort. No arbitrary SQL/order expressions are accepted.

## State and safety

- Search, category, quality, sort and page compose on the server. Category/quality/sort changes reset page; pagination and detail return preserve context.
- Clear search/quality/sort resets page while keeping category and current base tab; the category has its own explicit selector.
- Opening another page/filter/section closes inline review, so an inspector cannot show a stale row.
- Next-section navigation selects only allowlisted detail tabs before the guarded load; an old response cannot choose a new product's tab.
- Publication/feature writes are individually requested, never bulk operations. Per-row pending state disables both controls, rejects duplicate writes and restores the native checkbox after failure. Preserve request-generation and company-context guards from 1.4.0.
- New styles are backend-only in `catalog.scss`, scoped to `.o_action.bpi-app .bpi-home.bpi-home--catalog`.

## Delivery

QAS only, with current DB/addon/filestore backup, isolated Odoo tests, real OWL template tests, mobile/desktop and keyboard certification, then exact package hash verification after targeted upgrade. No PROD approval is implied. Record actual commit, timestamps, test counts and backup locations in the delivery certificate; manifest version is not proof of deployment.
