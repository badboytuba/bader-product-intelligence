# Bader official identity — 16.0.1.6.2

Brand-only release, QAS only. No category prompt/template implementation.

## Dependency and source

Requires `bader_brand` 16.0.1.0.0 from sibling repository `bader_brand_addons`.
Place that repository in addons_path (or deploy the technical addon directories).
The optional native Google/ML brand adapters belong to the same shared repository.
The existing `bader_product_intelligence_meli` bridge keeps its code/version. Odoo
reloads this installed dependent during BPI upgrade; preserve its cron configuration
and ML safety flags and rerun its tests, rather than promising unchanged module metadata.

Official rules: https://brand.bader4business.com/bader/ai/brand.md
Official tokens: https://brand.bader4business.com/bader/ai/tokens.json
Identity version 1.0.0 (2026-09-10), verified 2026-09-13. All assets served locally;
font/logo provenance and hashes are tracked by `bader_brand`.

## Scope and preservation

- Explicit `.bader-brand` root on the owned OWL action and BPI public description,
  technical/FAQ blocks. Only BPI category primary views/settings/smart-button
  fragments opt into native presentation. Do not modify shared Odoo forms/navbar.
- Official local SVG replaces home text wordmark; manufacturer labels and product
  images retain their business meaning. The existing app icon is already official.
- Institutional #003841, accent #70D44B with dark text, action #2F7D32 and official
  shades/mist/white. Error/warning/status semantics remain explicit and accessible.
- Helvetica Neue LT Pro for UI, Bader Sans 400 for the large home heading only;
  no synthesized 600/650/750/800 weights. Legacy rich editor font/color choices
  and authored saved HTML remain unchanged.
- Decorative gradients/glows/rings removed; functional publication donut kept.
- No Python/JS business, RPC, generation, save, async/draft, KPI/filter or marketplace
  behavior changes; all previous 1.6.1 invariants continue.
- Native ML/Google adapters are view-only and do not require upgrading those
  functional integrations. Keep ML read/write False and dry_run True in QAS.

## Validation

Run shared offline identity validator, BPI static validator, isolated Odoo tests,
full mounted QUnit suite and real read-only browser checks at360/768/1024/1440.
Check actual fonts rendered (not just CSS declarations), official SVG aspect/alt,
contrast, native Odoo isolation, drafts/navigation and no external brand requests.
Evidence: workspace audit_outputs/bader_brand_20260913. Deployment status and
hashes are recorded there; source version alone is not proof of QAS deployment.

The image Studio retains its two desktop panes and stacks them below900px.
Form and results content scroll independently; the form header and close action
remain visible. Flex/grid minimum sizes prevent the420px desktop results column
from displacing mobile controls. Check both panes, content overflow and close
accessibility at all four widths; opening or closing Studio must not call providers.
