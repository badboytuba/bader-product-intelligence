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

# Agent Instructions — Bader Product Intelligence

This repository is an Odoo 16 Community addon. It must be cloned or deployed with the technical addon directory name:

```text
bader_product_intelligence
```

## Mandatory safety rules

1. **Never commit or print secrets.** Local `.env` files may contain production host, database, GitHub token, OpenAI key, Firecrawl key, or deploy credentials. `.env` and `.env.*` are ignored; use `.env.example` only as a template.
2. **Treat any host/database in `.env` as live production** until proven otherwise. Do not deploy, restart services, run `-u all`, run destructive SQL, or change server packages unless the user explicitly asks.
3. **Develop in Git first.** Keep changes in this addon, validate locally, then push. For production/QAS, upgrade only the target module: `bader_product_intelligence`.
4. **Admin-only feature.** Backend routes and menus are intended for `base.group_system` users.
5. **Use Odoo 16 patterns.** Keep code organized in `models/`, `controllers/`, `views/`, `security/`, `data/`, `static/src/`, and add ACL rows for new persistent models.

## Skills / operating mode expected for future Codex agents

If available, use an Odoo 16/OCA development skill or equivalent senior Odoo workflow:

- read `__manifest__.py`, models, views, security, assets before editing;
- prefer small, explicit module changes;
- validate Python, XML, JS, and then Odoo install/upgrade in a real Odoo 16 runtime/QAS;
- never expose secrets from `.env`;
- for deploy/server/log work, use a safe deploy/runbook approach with backups and rollback.

Useful validation commands from this repo:

```bash
python3 -m compileall controllers models tests
python3 - <<'PY'
from pathlib import Path
import xml.etree.ElementTree as ET
for p in list(Path('views').glob('*.xml')) + list(Path('data').glob('*.xml')) + list(Path('static/src/xml').glob('*.xml')):
    ET.parse(p)
    print('XML OK', p)
PY
tmp=$(mktemp --suffix=.mjs); cp static/src/js/product_intelligence_action.js "$tmp"; node --check "$tmp"; rm -f "$tmp"
```

Odoo runtime validation, in the target environment only:

```bash
odoo-bin -d <database> -i bader_product_intelligence --stop-after-init
odoo-bin -d <database> -u bader_product_intelligence --stop-after-init
```

## Start here for context

Read these files before changing code:

1. `docs/CODEX_5_5_HANDOFF.md` — detailed architecture, current state, known issues, next recommended fixes.
2. `README.md` — install/config overview.
3. `__manifest__.py` — module dependencies, data, and assets.
4. `controllers/main.py` — JSON route surface.
5. `models/product_intelligence.py` and `models/product_template.py` — core backend behavior and payload contract.
6. `static/src/js/product_intelligence_action.js` and `static/src/xml/product_intelligence_templates.xml` — OWL UI and RPC contract.

## Stabilization status

Release `16.0.1.3.1` is the 2026-09-11 QAS-only stabilization. Preserve the atomic `/save_all` contract (`product_tmpl_id`, `product_values`, `category_values`, `content_values`, `seo_data`) and canonical category in `productForm`. SEO generation is metadata-only preview and must not publish or overwrite commercial/technical content or FAQs. Job payloads contain `seoData`, not a full `detailPayload`; the frontend must only update the SEO draft. The job partial unique index and session advisory locks prevent duplicate active jobs/execution; never automatically replay an interrupted paid request. Model-level admin guards must remain in place even when controllers also check access. PROD remains explicitly out of scope.

Release `16.0.1.1.14` addresses the previously documented backend stabilization issues:

- gallery/Studio references and deletion use product-owned tokens;
- chat state is isolated per product;
- competitor analytics uses normalized ARS/USD values;
- image uploads/imports have strict format, size and redirect/SSRF validation;
- the Product Intelligence category action no longer replaces the native eCommerce category views.

The stabilization release left the website bridge inactive. Release `16.0.1.2.2` activates only the sanitized formatted product description on `website_sale.product`; public Pack composition rendering remains outside scope.

Release `16.0.1.2.1` is developed on `feature/bpi-pack-variant-control` as the Pack/variant release plus its Odoo 16 OWL compatibility hotfix:

- explicit OCA dependencies: `product_pack`, `sale_product_pack`, `stock_product_pack`;
- content/SEO/chat remain on `product.template`, while operational controls use `product.product`;
- Pack composition updates require the external RPC key `packRevision` and are saved atomically;
- Pack component search handles Enter in JavaScript because Odoo 16 OWL does not support the `.enter` event modifier;
- ordinary products can only become Packs through the standard Odoo form;
- public website Pack rendering and MRP Kits remain outside scope;
- PROD stays untouched until QAS functional approval specific to the Pack/variant release.

Release `16.0.1.2.2` was developed on `feature/bpi-rich-text-editor` and adds the optimized-description rich-text toolbar plus the active product-page description bridge. It keeps formatted HTML in the existing `fields.Html` field, keeps the Odoo sales description plain for documents/fallback, permits only an explicit set of fonts/sizes/colors/styles and synchronizes the bridge to website-specific primary template copies. Runtime commit `f05d3e5` passed 20 backend tests plus 12 QUnit tests/45 assertions in QAS before the 2026-08-10 PROD deployment.

Release `16.0.1.2.3` was developed on `feature/bpi-storefront-faq` and deployed to QAS and PROD on 2026-08-10. It renders only saved, complete FAQs through the computed `product.template.bpi_public_faqs` projection, preserving manager-only ACLs on `bpi.product.faq`. The public block belongs after `product_detail_main`, uses escaped native `details`/`summary` markup, and must remain synchronized to website-specific product template copies through the existing bridge mechanism. Runtime commit `881a580` passed 21 backend tests plus 12 QUnit tests/45 assertions in QAS; the public PROD page was certified with seven styled FAQ items, semantic schema and no new BPI errors.

Release `16.0.1.3.0` was developed on `feature/bpi-technical-description` and certified in QAS on 2026-08-10; PROD remains on `16.0.1.2.3` pending explicit authorization. It separates a 45–70 word optimized commercial summary from the new sanitized `bpi_technical_description` HTML field, generated at 350–650 words. The backend reuses the allowlisted rich editor with a compact 180 px commercial surface and a larger 420 px technical surface. Public technical content belongs after `product_detail_main` and before FAQs. Existing catalog descriptions must never be truncated or migrated automatically; the split is applied only after an operator generates/edits and saves the new content. QAS runtime commit `f65600d` passed 22 backend tests plus 13 QUnit tests/51 assertions and desktop/mobile/backend visual certification.

## Executive dashboard invariants — 16.0.1.4.0

Read `docs/EXECUTIVE_DASHBOARD.md` before changing home KPIs or filters. Keep overview counts and catalog drill-down driven by one predicate implementation, active saleable templates, current category and selected companies. Dashboard RPCs must forward captured `user.context`. Never aggregate the current page, download image binaries, call providers or construct full operational product payloads for overview. New dashboard styles are scoped and backend-only. Preserve all detail/save/job protections from 1.3.1; no PROD delivery is authorized.

## Catalog workbench invariants — 16.0.1.5.0

Read `docs/CATALOG_WORKBENCH.md` before changing catalog rows, preparation or sorting. Seven-section presence is not an AI quality/ranking score; competitors remain optional. Reuse shared batch predicates, preserve the `catalog` default ordering and explicitly label base-price sorts. Inline inspection must not make RPCs; next-section links only navigate. Keep per-row mutation pending/checkbox rollback and all prior async guards. Mobile uses the same table DOM as cards, with no horizontal page/table overflow. Catalog styles must not alter overview or detail. Delivery remains QAS-only.
