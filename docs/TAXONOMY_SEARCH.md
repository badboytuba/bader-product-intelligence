# Reviewed classification and shared search — 16.0.1.10.0

QAS-only release. Four independent multi-select axes: niche, commercial nature,
technical specialty and use/procedure. Internal, store and ML categories do not
move. The canonical vocabulary is shared; approved product assignments are not.
Mayorista is a universal view of eligible products, never a clinical indication.

## Workflow

`Clasificación` exposes approved terms and reviewed versus draft state.
`Analizar con Nancy` explicitly queues an existing `bpi.ai.job` of type
`classification`; opening pages, selecting terms and searching do not call AI.
Jobs snapshot saved identity, categories, verified measurements, variants/Packs,
descriptions marked **not technical evidence**, vocabulary and company context.
The worker runs as the requesting active administrator. Changed source or
vocabulary fails before a paid call; no automatic retry of paid generation.
Completed proposals do not change product fields. `Usar propuesta en borrador`
requires matching product/source/vocabulary revisions; saving is separate.
New canonical terms remain draft dictionary records. Proposed aliases for an
existing term remain in the job proposal, never overwrite its approved aliases:
an administrator must review and edit that term explicitly in the dictionary.
Approving a term never approves its association to a product.

`Guardar sección` / atomic `/save_all` uses category_values.classification:
`{termIds, revision, vocabularyRevision}`. No store categoryId is reused.
Omitted classification preserves legacy contracts. Empty termIds clears the
individual assignments. Legacy classification is shown only as draft suggestions.
Terms in use cannot be archived/deleted without explicit same-axis replacement.
Replacement fails if any affected product is outside the administrator's companies.

## Search

`models/taxonomy_search.py` implements normalized identities/SKUs and longest
approved canonical/synonym phrase matching. OR within an axis; AND across axes.
Unmatched text still searches identity and existing description text. Ranking:
exact variant SKU, exact name, other identity, then remaining matches. Ranking
and filtering occur before pagination; no result cards are hidden client-side.
Facets are batched ACL-aware SQL aggregates over all matching visible products,
not the current page. Counts mean **current matching products**, not projected
counts after selecting additional OR values; zero-count approved options remain
selectable. Product editorial completeness keeps its existing seven items.

Header autocomplete uses the native `/website/snippet/autocomplete` contract,
including native price/currency rendering. `/shop` uses native price/category/
attribute handling and full matching IDs as required by Odoo, not full product
payloads or binaries. Public domains explicitly require published, active,
saleable and website/company-visible products. Admin BPI retains its own universe.
`bpi_terms` query parameter carries approved term IDs; chips, paging and header
submission retain the query. Invalid shop filters return HTTP400.

## Controlled header migration

`website.bpi_taxonomy_search_enabled` defaults **false**. Only enable after
backing up database, filestore, addon and website.custom_code_head. Locate exactly
one script containing `__BADER_SEARCH_V5__`, verify the expected full-head checksum,
remove only that complete script and preserve all surrounding bytes. The new
versioned `taxonomy_header.js/scss` mounts only on explicitly enabled websites.
Do not install `bader_website`, alter Odoo core, change Git/remotes, or copy .git.
Rollback restores the original head only if its post-migration checksum still
matches; concurrent user edits require manual review. Database rollback requires
stopped writers and the matching addon/filestore snapshot.

## Validation

Backend tests include term approval/protection, atomic save, revision guards,
legacy drafts, compound synonyms, variant SKU ranking, universal niche, facets,
public publication/company/website isolation and provider-free page/search.
OWL regression includes draft preservation, mid-save changes, stale proposals,
explicit apply and four-axis rendering without provider calls.
Deployment evidence belongs in the private project audit_outputs directory;
source version alone does not imply QAS/main delivery or a completed live pilot.
