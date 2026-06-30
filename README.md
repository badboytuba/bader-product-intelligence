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
- Website product detail extensions for the Bader storefront

## Odoo Dependencies

- `product`
- `web`
- `website_sale`

These modules must be available in the target Odoo database before installation.

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

## Compatibility Notes

- This module is now independent from `bader_website`.
- If `bader_website` is installed, the website module can optionally render Product Intelligence content on the product page.
- Backend tests already exist under `tests/test_product_intelligence.py`.


## Agent / Codex Handoff

For future Codex or automation agents, read:

- `AGENTS.md` — repo-specific operating rules and safety constraints.
- `docs/CODEX_5_5_HANDOFF.md` — detailed architecture, current state, validation commands, known issues, and recommended next fixes.
- `.env.example` — redacted environment variable template. Never commit real `.env` values.

This repository should be cloned/deployed with folder name `bader_product_intelligence`.

## Validation Notes

- Manifest dependencies are clean for standalone installation.
- The module no longer inherits templates from `bader_website`.
- A real `odoo-bin -i/-u` run in the target environment is still recommended before production use.
