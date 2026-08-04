# Bader Product Intelligence

Installable Odoo 16 Community product operations module with SEO, GEO, image generation, competitor analysis and product-level AI workflows.

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

Without OpenAI and Firecrawl credentials, the module installs, but AI and competitor-analysis features will not work.

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
- The public storefront bridge remains inactive; website Pack rendering is outside this release.
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

## Release 16.0.1.2.0

- Adds explicit OCA Pack dependencies and recognizes products as `simple`, `variants`, `pack` or `pack_variants`.
- Shows Pack/variant badges plus native effective price, cost and availability ranges in the dashboard and detail workspace.
- Adds the conditional **Variantes y Pack** tab for SKU, barcode, cost, active state and per-variant image overrides; Odoo continues to calculate stock and effective prices.
- Allows existing Packs to edit type, price mode, modifiable flag and per-variant compositions without converting ordinary products into Packs.
- Searches eligible components by product variant with a 20-result limit and rejects inactive additions, duplicates, self-reference, cross-company records and recursive Packs.
- Saves complete Pack compositions atomically and requires `packRevision` to prevent stale overwrites.
- Adds bounded variant/Pack context to content, SEO, categorization, image, strategy and chat prompts without creating per-variant content.
- Uses effective Pack prices and native variant min–max ranges in analytics.
- Adds secure variant image upload/reference/removal using the existing 10 MiB PNG/JPEG/WebP validation and product-owned image tokens.
