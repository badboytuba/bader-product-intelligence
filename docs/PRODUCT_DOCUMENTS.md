# Product catalogs and documents — 16.0.1.9.0

QAS-only release. Optional card in Descripciones y FAQs: cover, title, intro and
three labeled slots (HTTPS URL or uploaded static PDF). No existing products are
populated by upgrade. The public card sits before FAQs, including when no FAQ
exists, and is absent unless at least one complete resource is saved.

## Storage and visibility

`bpi.product.document.panel` is administrator-only, company-scoped and unique per
product template. Binary fields use private ir.attachments owned by this private
model, never attachment.public or access tokens. Product copies start empty.

A public GET route validates product read access, active/saleable/published
state, website and company before narrowly elevating to the exact panel. Removed,
unpublished, cross-website and obsolete-version resources fail closed. Admins
may preview their authorized saved documents before publishing. Responses are
inline with MIME, nosniff, no-store, sandbox CSP and safe disposition filenames.
The browser may download instead of previewing according to its PDF settings.
Public projection contains only curated button/cover metadata, never binaries.

HTTPS links are navigation only; no DNS resolution, fetching or remote scraping
occurs on save or render. Do not use secret/private/token-bearing links: supplied
URLs will be publicly visible with the product. Link destinations remain the
operator’s responsibility; an external page can change after save.

PDFs: max10MB each,20MB combined,500pages; validate base64/magic/parser, reject
encryption, JS/automatic actions/embedded files and unsupported active content.
This is validation, not antivirus or a guarantee against every PDF vulnerability.
Some interactive PDFs must be exported as static PDF, or referenced by a reviewed
HTTPS URL. Covers: JPG/PNG/WebP up to2MB/16megapixels, nonanimated; re-encodedPNG
and resized to1000px, stripping original metadata. No HTML/SVG uploads.

## Saving and compatibility

`documents` is an optional content-save field; omitted means unchanged.
Full and contextual content saves are atomic, including validation failures.
Saved document revisions and parent row serialization protect stale/concurrent
saves. Opening pages never creates a panel or performs external requests.
Metadata-only payloads preserve legacy consumers. Browser file reads are scoped
to product/selection; navigation and acknowledged uploads cannot restore stale
buffers. Mid-save edits remain pending, with acknowledged revisions rebased.

Shared Bader styling is scoped to the new card; native Odoo, editor text,
seven-item quality checklist, existing KPIs, ML and AI transport are unchanged.
Website-specific primary template clones use the existing bridge sync.

Runtime proof and rollback are kept separately in
`audit_outputs/product_documents_20260915/`, never inferred from this version.
