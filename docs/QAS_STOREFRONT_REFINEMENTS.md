# QAS delivery · BPI 16.0.1.17.1 · 2026-09-30

Runtime source **78fde6f** on QAS website1 Bader Iberoamérica only. This
delivery note is separate from deployed runtime hashes. Production excluded.

## Delivered
- Native Productos menu above search; autocomplete closes on menu opening without
  reopening when native hover restores prior input focus.
- Bounded desktop gallery follows real `#wrapwrap` scrolling, stops at purchase-row
  bottom, no animated pinning. Static below992px or when the card cannot fit.
- Vertical96px thumbnail rail >=1200px reserves classic scrollbar/focus space.
  Smaller widths use horizontal real thumbnails; reset native mobile hidden div
  AND Bootstrap negative dot indentation. Preserve native zoom/order/variant media.
- **Descripciones y FAQs → Diseño Bader → Título de la descripción** selects
  left/center/right. Default left shares the principal text inset. Preview and save
  remain explicit; common/edition context and revision guards remain intact.
- YouTube cover retrieval verifies official HD then standard fallback. Saves wait
  for current pending covers. **Obtener portadas pendientes** is explicit recovery
  for old missing references, never an automatic fetch on page opening.

## Approved pilot
TREKC M2 product1713 retained its existing YouTube URL `HC1lu775ezI`. Added only
`posterMediaId=15` to its existing video block through revision-guarded common
content save (revision32→33). Official480x360 cover used because HD unavailable.
All other product columns, text, prices, layout blocks and prior media preserved.
Image bytes load locally through authorized saved-reference URLs; player waits
for interaction. An unversioned media URL correctly returns404.

## Evidence
- 539 isolated Odoo backend tests;186 actual Odoo QUnit tests, all passed.
- Browser suites: full variant shop/editor/documents/media plus focused real
  menu, classic scrollbar, keyboard, four widths360/768/1024/1440, native variant
  gallery replacement and real OWL heading preview/save/storefront round trip.
- Live QAS HTTP/browser PASS, including official cover200 before player loading,
  High/Starter, noindex, home/shop/contact and exact heading alignment.
-131 deployed source hashes match; zero recent Odoo errors; Odoo/Nginx active.
- Exact pre/post-upgrade business snapshots match BEFORE the separately authorized
  pilot. Website2, authored page views, custom head, Git configs and Nginx unchanged.
- Fresh external backup20260930T184148Z verified: DB313625807B, addon589471B,
  configs9474B, filestore/editorialmedia4505302163B. Immutable upload guard passed;
  temporary hardlink snapshot removed. Rollback prepared before upgrade.
- Disposable clone removed; approximately4.42GB free on QAS after cleanup.

Private operations evidence/screenshots/backup stay outside Git under local
`audit_outputs/storefront_refinements_20260930/`. Never commit credentials, DB,
filestore, configuration archives or customer content. User visual approval is
the remaining step; no production promotion is authorized.

## Rollback cautions
Baseline1.17.0 can be restored from this verified source backup after pausing edits.
Archive any newer layouts first: its validator does not recognize `headingAlign`;
remove only that optional key with revision protection or backport the compatible
validator. Do not delete layouts, variants or media. The pilot cover is backward
compatible and normally remains. Never restore the entire historical DB over new
business edits without separate approval/reconciliation. Git/Nginx remain untouched.
