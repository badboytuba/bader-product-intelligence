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

## Delivery boundary

This release is a **source candidate**. Before installation, obtain specific
environment approval, test native Odoo QUnit/assets in an isolated runtime,
verify fresh external backups and prepare rollback. Install QAS first. PROD
requires separate authorization. No server, stored text or price has been
modified by the local correction.
