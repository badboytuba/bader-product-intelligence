# Copy-only unsaved-change guard — 16.0.1.17.2

## Reproduction and cause

Open Producto Intelligence for a source and a destination product. Select/copy
the source description, focus/edit/save the destination, then leave the source.
The source can incorrectly report unsaved content despite no input there.

Editors render normalized/sanitized HTML, while the initial draft and its baseline
retain the original saved representation. A plain description becomes paragraphs;
HTML may lose editor-only classes, serialize `<br/>` as `<br>`, canonicalize colors
or convert legacy `<font>` tags. The old blur handlers always assigned this display
HTML to the draft. Thus loss of focus—not another window's save—created a false
local edit. No cross-tab storage listener is involved.

## Fix and invariants

- Short/long description blur compares normalized DOM HTML with the normalized
  current form value. If equivalent, it leaves the original form value unchanged.
- Studio rich editors notify their owner only when sanitized display content
  actually differs. This also protects previews and auxiliary design blocks.
- User input, paste and formatting changes still update drafts. Genuine pending
  edits still block navigation/close and survive another workspace's save.
- Plain inherited variant descriptions stay inherited; saved intentional empty
  overrides stay customized. No revision, baseline or draft cache is cleared.
- No backend contract, content migration, automatic save or publication changes.

## Tests

Five new QUnit regressions cover both description fields, original plain/HTML/
legacy/empty values, real text/formatting changes, unload protection, inheritance,
two independently mounted workspaces with copy/save, and mounted Studio blur.
Their RPCs use synthetic fixtures and never write real products.

Local verification on 2026-10-05: the identical five tests fail against the
original runtime code and pass **37 assertions** after this fix. The entire
frontend suite passes **191 tests / 1,477 assertions**, with no browser exception
or attempted external/application request. Static addon and RPC checks pass.

The portable runner loads the **actual current OWL components and XML in Chromium**
using mocked Odoo services; it is not a native QAS registry/asset-upgrade test.
It accepts only local library paths and serves on loopback, blocks other network
origins and writes source hashes plus results to the chosen artifact directory.
No library/dependency is added to the installed application.

```bash
BPI_OWL_FILE=/path/to/odoo/addons/web/static/lib/owl/owl.js \
BPI_QUNIT_FILE=/path/to/qunit.js \
BPI_PLAYWRIGHT_MODULE=/path/to/node_modules/playwright \
BPI_TEST_ARTIFACTS=/private/path/to/results \
node tests/browser_copy_drafts.cjs
```

For all 191 frontend tests, additionally provide the local native Odoo 16
`action_hook.js` via `BPI_ACTION_HOOK_FILE`, `BPI_TEST_FILTER=''` and
`BPI_EXPECTED_TESTS=191`. The runner mimics native test-only image-attribute
suppression; it never changes source templates or public markup.

## Runtime delivery — 2026-10-05

The user separately authorized **QAS and PROD**, with maintenance now after tests
and backups. Runtime source `0e6213b` was installed as **16.0.1.17.2**, QAS first;
PROD began only after live QAS acceptance. Only the manifest, two editor JS files
and their two QUnit test files were copied. Server Git/remotes, configuration,
unrelated addon files and native cron activation/schedule were preserved.

Gates and evidence:
- Fresh coherent database/filestore/private-media/addon/configuration backups,
  verified outside each server; rollback prepared before the maintenance window.
- Disposable QAS snapshot, neutralized providers/crons and loopback-only isolated
  networking: **539 native backend tests**, zero failures/errors.
- Actual native QUnit asset compilation: **191 tests / 1,477 assertions**, zero
  browser errors, unknown writes or external requests.
- Two real native browser tabs on synthetic **clone-only** products: select/copy
  plain and HTML descriptions, paste/edit and save the destination through the
  actual backend; source data unchanged and clean exit without a false warning.
  A genuine source edit still invokes the leave guard. No live product was used
  for this write pilot. Long rich copy is `bpiTechnicalDescriptionHtml`; the
  payload's `technicalDescription` denotes the legacy internal description.
- Protected data hashes frozen with the live service stopped stayed identical
  after each target-only upgrade: catalog, variants, native prices/Packs,
  editorial/media/document/FAQ/classification data, website settings, custom
  assets and system parameters. No historical content migration or draft reset.
- Live compiled backend bundles contain all three no-op guards and the registered
  action. Public read-only smoke passed **8 QAS** and **16 PROD** route/width cases
  (360/1440 px; home/shop/product/contact, including PROD website2 controls), with
  zero page errors, asset failures or unknown writes. Target upgrade and inspected
  post-start log windows had no BPI error/critical events.
- Main service downtime measured **36.83 seconds QAS / 48.95 seconds PROD**;
  both services active and installed/manifest version matched at acceptance.

Private proof and backups: `audit_outputs/copy_drafts_deploy_20261005/` (workspace,
not deployed or committed). Live acceptance certificates bind source, upgrade,
compiled assets and smoke receipts; no credentials or business bodies are in
this document. The older local proof remains a separate certificate.

**Operator reload:** save genuine pending work first, then reload **both** windows
with Ctrl+F5. Already-open browser tabs retain their previous JavaScript until
reloaded; deployment never clears their drafts automatically.

For subsequent installations, repeat explicit environment/window approval,
isolated native tests, fresh external backup/rollback and QAS-before-PROD gates.
Source version alone is never a deployment certificate.
