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

- Gemini API
- Firecrawl API

## Installation

1. Copy `bader_product_intelligence` into an Odoo addons path.
2. Update the app list.
3. Install `Producto Intelligence`.

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

- `Gemini API Key`
- `Gemini Modelo Texto`
- `Gemini Modelo Imagen`
- `Gemini Modelo Imagen Pro`
- `Firecrawl API Key`
- `Firecrawl Base URL`
- `Tipo de Cambio ARS`

Without Gemini and Firecrawl credentials, the module installs, but AI and competitor-analysis features will not work.

## Security / Access

- Backend usage is intended for administrators.
- Main backend routes validate `base.group_system`.

## Compatibility Notes

- This module is now independent from `bader_website`.
- If `bader_website` is installed, the website module can optionally render Product Intelligence content on the product page.
- Backend tests already exist under `tests/test_product_intelligence.py`.

## Validation Notes

- Manifest dependencies are clean for standalone installation.
- The module no longer inherits templates from `bader_website`.
- A real `odoo-bin -i/-u` run in the target environment is still recommended before production use.
