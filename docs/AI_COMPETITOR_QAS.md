# AI and competitor reliability — 16.0.1.6.1

## Scope
QAS only. Restore explicit category/content/FAQ/SEO/GEO/image actions using protected
provider configuration. No automatic generations, model migration, marketplace
activation or production changes. Keep the atomic save/draft/job contracts from 1.6.0.

## Provider errors
The shared OpenAI helper validates success/error envelopes, nested text/image types
and object JSON. Incomplete responses cannot become complete SEO proposals. No
new retry of ambiguous paid outcomes is introduced. OWL shows safe Odoo UserError,
ValidationError and AccessError messages, otherwise an operation-specific fallback;
internal traces, credentials and markup are not surfaced.

## Competitor evidence
- Explicit admin/company-scoped collection uses Firecrawl v1/scrape (rawHtml + markdown,
  full page), then public HTTP fallback if allowed. Initial URL and redirects are
  validated; credentials/nonstandard ports/private networks are rejected, responses
  are streamed with byte and time limits. No importer or ML task is reused.
- HTMLParser handles metadata/JSON-LD attribute order, entities and nested headings.
  Source parsing prefers `rawHtml`, with `html` fallback for older/custom responses:
  [V1 supports unmodified raw HTML](https://docs.firecrawl.dev/v1-welcome#scrape-formats),
  while [cleaned HTML removes scripts/styles](https://www.firecrawl.dev/blog/mastering-firecrawl-scrape-endpoint).
- Select one matching Product/Offer and currency. Multiple ambiguous prices, ranges,
  missing currency, shipping and installments do not become artificial offers. Unknown
  prices are unavailable, not a real zero and not included in price analytics.
- `meta_keywords_source`: page / not_found / legacy_unknown. Missing keywords are not
  invented from descriptions; suggested keywords and strategy remain in `analysis_data`
  with `last_analyzed_at`, separate from observed page fields.
- `last_scraped_at` is the latest attempt; `last_successful_scrape_at` the latest valid
  evidence. `firecrawl_data` is a compact normalized source/price/status summary, not a
  provider response dump. Failed attempts preserve prior observations and return a
  failed payload so Odoo commits failure state rather than rolling it back with an error.
- SEO score is an explicit heuristic, never measured search position. External Open
  Graph pictures are not fetched automatically by the detail UI.
- Refresh/analyze actions use synchronous frontend busy guards plus a competitor
  transaction lock. Navigation and unrelated typed URL drafts remain protected.

## Validation and operation
Run the existing Odoo and native OWL suites, including new provider-envelope and
competitor metadata tests. Use an isolated QAS clone and temporary fixture for bounded
real API tests, keeping provider responses/prompts/images out of reports. Record model
access, actual generation and actual scraping separately. Provider availability,
credits, rate limits, robots/access restrictions and page structure remain external
constraints. Generated suggestions and images require human review and explicit save.

Backup DB/filestore/addon immediately before upgrading only BPI. Preserve Git/remotes,
bridge and native ML hashes. QAS ML flags stay false/false/true. Rotate credentials
if exposed in chat and never commit them.
