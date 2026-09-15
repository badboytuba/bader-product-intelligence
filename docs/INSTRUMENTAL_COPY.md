# Instrumental copy and separated generation — 16.0.1.8.1

QAS only. `general_specs` is an additional editorial format; `free` and
`two_sections` retain their contracts. Existing recipes are noupdate and are not
rewritten by upgrades. The explicit QAS rollout updates the audited Instrumental
recipe to the new format and removes its former short 45–70-word target.

## Explicit generation

- Two validated General paragraphs go in the short field. Long contains only
  technical evidence rendered by the server, with all saved per-variant cm/g
  measurements, even if the provider omits those IDs. Unknown data stays pending.
- Measurements and revision guards come from Datos y precios; drafts, previous
  AI prose and imported copy are never technical evidence.
- A new generation is a proposal, not a literal reproduction of imported copy.
  Warnings tell the operator to review before explicitly saving. No paid retries.
- Provider transport/configuration, SEO/GEO, FAQs, ML, publication and ordinary
  saves remain unchanged.

## Approved-document import (separate, audited operation)

User-approved mapping: General → short; all remaining sections, including
highlights and care recommendations → long. Preserve words and numeric values
literally; normalize only unsafe/export formatting. No truncation or AI call.

The dated administrator-only `bpi_editorial_import` JSON receipt records source
hash, SKU, anchor, timestamp, saved-content hash and discrepancies **at import**.
It is copied neither to duplicates nor to public payloads. Its BPI UI projection
shows whether saved content has since changed. Discrepancies are explicitly a
snapshot, not a live comparison. They never overwrite saved technical fields.

Audit artifacts in the workspace (not the addon) contain frozen source exports,
exact-SKU mappings, report and rollback. Refuse ambiguous/multi-variant matches,
changed measurements/recipe and edits after import; no fuzzy or name-only match.
An import compares all non-target product data, variants, specifications, FAQ,
stock, AI jobs and ML tables before commit. No importer is registered on upgrade
or cron. Rollout scripts must separately verify exact source/package hashes.

Tests use controlled responses. Runtime evidence and delivery status belong in
`audit_outputs/instrumental_copy_20260915/DELIVERY.md`; source version alone is
not deployment proof.
