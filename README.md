# Bader Product Intelligence

Installable Odoo 16 Community product operations module with SEO, GEO, image generation, competitor analysis and product-level AI workflows.

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

## External Services

- Gemini API
- Firecrawl API

## Installation

1. Copy `bader_product_intelligence` into an Odoo addons path.
2. Update the app list.
3. Install `Producto Intelligence`.

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

## Compatibility Notes

- This module is now independent from `bader_website`.
- If `bader_website` is installed, the website module can optionally render Product Intelligence content on the product page.
- Backend tests already exist under `tests/test_product_intelligence.py`.
