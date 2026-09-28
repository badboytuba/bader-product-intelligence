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


## Premium editor —16.0.1.11.0

Four compact tag cards replace the full vocabulary lists. `Analizar producto`
queues or resumes an explicitly requested analysis and complements the draft
when complete. It never saves. Current selections survive; removed labels are
kept in `excludedTermIds`, a private validated per-product list saved atomically
with classification. Re-selecting a label explicitly clears its exclusion.
Existing clients may omit excludedTermIds without erasing prior exclusions.
Fresh source/vocabulary/product revisions and local product/content draft
fingerprints are checked before automatic completion; edits made while fetching
results are merged conservatively. Old completed jobs do not apply on page open.

`Añadir etiqueta` searches approved terms locally, accent-insensitive. Creating
a word opens a focused Odoo form defaulting to draft; approving and assigning
remain distinct explicit steps. Dictionary management, historical suggestions,
justifications and proposed synonyms move to collapsible secondary details.
Removing a chip affects this product only. No new paid pilot/mass generation is
part of this cosmetic/interaction delivery; validate async responses with mocks.

## Search recovery — 16.0.1.14.2

The enabled website now renders a real search form in the header, outside the
collapsible navigation. It remains usable before/without JavaScript. The scoped
Bader palette and inline SVG do not depend on external icon fonts. Suggestions
show native local image URLs, template SKU when unambiguous, native price, result
count and a full-results action. Unknown/external image URLs are rejected. Broken
thumbnails fall back locally; no product/gallery images are modified.

The public widget uses 180 ms debounce, abort plus sequence guards, a ten-second
request deadline and immediate stale keyboard-target invalidation. Opening pages
never queries autocomplete or an AI provider. Query/approved filters are retained
when entering the shop or product. Mobile gets the same always-visible field.

Normalized stored fields are already ASCII lowercase. Escaped `=like` keeps the
same normalized text coverage; normalized fields explicitly use `unaccent=False`
to avoid PostgreSQL repeating accent removal and locale case folding
over large historical descriptions. The displayed language name is also matched directly (AR and ES titles may differ).
A direct displayed-name/SKU tier precedes category-only
matches, still before pagination and behind exact SKU/name. No full-catalog client
load, shared price cache, external engine or new database extension. Public
visibility, native pricing and the common BPI/server matching service remain in
place. Custom head and homepage carousels are not rewritten by this upgrade.

Backend regressions cover description-only accent matching, direct-name ranking
versus category matches across pages, and SKU/native image/price contracts.
Browser regression harness: `tests/browser_search.cjs` (Playwright; explicit clone
base URL). Deployment evidence remains separate from source version.
