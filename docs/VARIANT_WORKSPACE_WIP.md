# Full variant workspace — BPI 16.0.1.17.0

Release **16.0.1.17.0**, authorized for QAS website1 only. Production
and website2 are excluded. Source version and test results are not a deployment
certificate; external backup, rollback and activation must be verified separately.

## QAS delivery — 2026-09-30

Runtime **73a02e6** installed and enabled only on website1 (Bader Iberoamérica).
Production and website2 are unchanged. A fresh verified external backup and
rollback instructions are retained privately with the deployment evidence.

- 534 backend + 183 actual Odoo/Chrome QUnit tests passed, plus public/editor/
  document/media integration tests on an isolated disposable clone.
- Live read-only QAS checks passed: High1750/Starter2080, SSR metadata/canonical,
  invalid-edition404, rapid selection, native price/SKU/gallery, 360/768/1024/1440,
  real page scrolling, no JavaScript/asset errors and healthy home/shop/contact.
- No historical profiles were created. All business data were preserved. Stored
  index initialization updated `product.product.write_date` on1616 records and
  `write_uid` on1; an exact row comparison against the fresh backup confirmed
  that these were the only non-index changes. Do not reset audit dates or mask
  unexplained differences in future preservation checks.
- Host-only QAS `X-Robots-Tag` and robots exclusion were verified; other hosts
  were not opted in. Server Git configurations remained byte-identical.
- Disposable clone/database/tunnel removed; main services healthy and roughly
  4.5GiB available afterward. Private backup/credentials/logs are not addon assets.

The final source documentation can be newer than the pinned runtime commit;
that does not imply an untested runtime deployment. Subsequent business edits
must never be overwritten by restoring this pre-upgrade backup indiscriminately.

## Data and boundaries

- `bpi.variant.content`: unique optional profile per `product.product`, admin-only,
  company-scoped. Absent JSON key means inheritance; an explicit empty value means
  intentional empty content. No products, historical copy or conversations are
  duplicated during upgrade.
- `_bpi_effective_variant` resolves common + edition content; `_bpi_resolve_variant`
  additionally supplies private base/profile revisions and a supporting-context
  fingerprint. Editor, Studio, website and search use this same source of truth.
- `product_variant_id` is optional on new/extended controllers. Common calls omit
  it; legacy behavior remains. Private RPC context uses `bpi_product_variant_id`.
  Never confuse variant IDs with hash PTAV IDs.
- Saves serialize against the template and reject stale base/profile/context
  revisions. Common writes are blocked in a selected-edition context. Technical
  specifications and manual copy can be saved atomically; a proposal cannot be
  approved while changing the facts on which it was generated.
- Drafts are separated by product + edition; navigating between editions does not
  save. In-flight responses carry scope/generation guards. A saved section cannot
  overwrite a different dirty section or edits made while the request was running.

## Content and menus

Descriptions, recipe, tone, audience, FAQs, SEO/GEO, keywords, design, videos,
references in the gallery, commercial classification, public categories and
curated documents support overrides. Internal ERP category remains common.

- Main design block references the effective long description, including an
  intentionally empty main block; complementary media survive text regeneration.
- Native image and approved BPI gallery references do not duplicate binaries.
  Public BPI image delivery requires published/website/company/active-combination
  validation, exact saved gallery membership and current base/profile revision.
  Removing a reference revokes delivery without deleting the original image.
  Generic private image ACLs remain unchanged.
- Documents are copied only on an explicit customized save. Returning to common
  inheritance retains the previous panel privately; repersonalizing uses the
  current common files, not stale retained bytes.
- Nancy Studio conversations/sources/proposals/jobs and classification jobs are
  edition-specific. Strategies copy editorial directions only. Paid legacy common
  generation cannot run under a variant context. Opening Studio does not generate.
- The chat menu opens the selected edition's Studio. Legacy competitive scraping
  and strategy records are still explicitly **common-only**; the edition menu
  links to common context instead of showing misleading SKU-specific prices or
  silently applying a common strategy. This is not a new per-variant competitor
  analysis engine.
- Native SKU/cost/image/stock and Pack controls remain native. Pack editing in
  an edition is limited to that edition's composition. Shared Pack type/settings
  are edited in common context. MercadoLibre reads reuse bridge permissions and
  identity evidence, filtering the selected SKU; observer requests remain common
  and never start a new publication or synchronization.

## Native tariffs

`variant_pricing/data` consults `_get_product_price_rule` with list, currency,
quantity and date; no parallel calculation. `variant_pricing/save` creates or
edits only native SKU-specific fixed/percentage rules, with revision, minimum
quantity and dates. General rules/formulas are not indirectly edited. The
post-save quotation keeps the original queried quantity/date. Fiscal positions
and taxes continue to be applied by Odoo at sale time. Editorial saves never
change tariffs.

## Public contract

- Per-website `bpi_variant_content_enabled`, off by default and on copied sites.
- `/shop/<product>?variant=<product.product.id>` selects a valid complete native
  combination on the server, with effective HTML/image/meta/canonical/ProductGroup.
  Invalid explicit selections return 404. Hash-only links retain native behavior;
  an explicit query takes priority over a stale hash.
- Native combination responses carry a request token. Guard **before** native
  price/product_id/gallery callbacks and exclusions, not only after their promise.
  Pending requests hide old content/price and disable purchase. Failure explains
  the issue with manual retry; no silent wrong-SKU cart or paid retry.
- Changing edition pauses old videos and replaces editorial/player markup. Native
  carousel/zoom remains native. Social players load only on visitor interaction.
- Public projection never returns profiles, source documents, proposals, private
  history or draft values. Public document/media routes enforce owned saved refs.
- Stored effective search fields include only saved copy/classification/categories.
  Query + taxonomy/category filters must match the same edition before template
  grouping. SKU/edition matches link to that edition with its image/native price;
  ambiguous matches do not guess. One catalog card per template.
- Variant sitemap entries respect publication/website/company/combination and
  indexing settings. QAS noindex must be verified at its real proxy before deploy.

## Validation

Evidence is outside this addon under `audit_outputs/variant_workspace_20260930/`.
The disposable DB is `bpi_variant_test_20260930`, not the live `bader` DB. Clone
HTTP uses loopback, cron/provider credentials are disabled, outbound network is
restricted. All fixtures and their prices are clone-only.

Verified backend candidate: **534 tests**, zero failures/errors (BPI plus ML bridge).
This covers multi-attribute editions, archived/wrong-owner selection, no-variant
options, Packs, currency/customer native pricelists and read-only advanced rules,
revision/concurrency guards, scoped Studio/jobs, empty/inherited content, effective
search and private references. Browser certificates are generated separately:
- `variant_browser_results.json`: public SSR/canonical/invalid404, grouped SKU,
  native price/copy/SEO/gallery, concurrent saves, delayed responses, history,
  manual retry, native cart SKU, four widths, feature-off/site2.
- `workspace_browser_results.json`: real OWL selector/drafts/selective save,
  empty/reinherit, scoped Studio entry, no automatic generation, four widths.
- `documents_browser_results.json`: own saved PDF only, wrong SKU/stale/generic
  private route rejected; inheritance revokes delivery without deleting history.
- `media_browser_results.json`: native keyboard/touch/zoom, pending player stop,
  carousel rebuild and intentionally empty gallery.
- `clone_qunit_certificate.json`: **183 real Odoo/Chrome QUnit tests**, zero failures,
  including10 variant tests and173 existing regressions. Check status/count/current
  code hashes; do not treat an older file as certification of newer changes.

The real QAS initially lacked robots/noindex protection; activation requires a
host-scoped QAS proxy protection (not a production or second-website change).

## Release gate / next steps

1. Verify all current-candidate certificates listed above and review editor/storefront
   screenshots; keep clone fixtures and prices out of live QAS.
2. Review diff, secrets, security, performance, feature-off and repeat upgrade;
   preserve noindex and second website. Update release/handoff evidence.
3. Commit/push validated work and package the exact certified runtime.
4. Take a **fresh verified off-server** DB/filestore/addon/config backup and prepare
   rollback. Never restore an old DB over concurrent editorial work.
5. Deploy only BPI on QAS, activate only website1, certify assets/logs/business
   preservation and user-facing pilot. Production needs separate authorization.

## Portable public browser regression

`tests/browser_variant_workspace.cjs` requires an existing disposable cloned
Odoo database and Playwright. It refuses a non-loopback origin or a database name
without the `bpi_variant_test_` prefix. It creates/updates fixtures and clone
website flags: **never use against the team's QAS or production**.

Provide `BPI_TEST_BASE`, `BPI_TEST_DB`, `BPI_TEST_CREDENTIALS` (protected JSON file
containing only disposable login/password), `BPI_TEST_ARTIFACTS` and optionally
`BPI_PLAYWRIGHT_MODULE`. Never commit credentials, session storage or raw logs.

## Uso rápido (administradores)

1. Elige **Contenido común** o **Edición · SKU** en «Estás editando».
2. «Heredado» utiliza la base común; **Personalizar** crea un borrador propio.
   Un campo personalizado vacío significa no mostrarlo. **Volver a heredar**
   recupera la base sin guardar automáticamente.
3. Cambia de menú/edición sin perder borradores. El aviso de cambios pendientes
   identifica otras ediciones: guardar una no guarda las demás.
4. **Guardar sección** guarda su sección; **Guardar ficha** guarda el contenido
   seleccionado. Tarifas, imágenes nativas, variantes y Packs tienen controles
   propios. Publicación y categoría ERP se editan en Contenido común.
5. En Datos, consulta una tarifa, cantidad y fecha. Las reglas generales/formuladas
   son informativas; modifica solo reglas nativas específicas de este SKU.
   Guardar una descripción nunca modifica tarifas.
6. Nancy abre la conversación de la edición. Reutilizar estrategia copia orientación,
   nunca medidas ni pruebas técnicas de otro SKU. Aplicar solo llena borradores.
7. Selecciona/reordena referencias en la galería sin duplicar archivos. Diseño Bader
   conserva los medios al regenerar la descripción principal efectiva.
8. Comparte `?variant=ID`. Una selección inválida no abre otra edición en silencio.
   Precios o imágenes heredados iguales no significan que el selector esté fallando.

## Ejecutar regresiones de navegador

Después del harness público, ejecuta en orden `tests/browser_variant_editor.cjs`,
`tests/browser_variant_documents.cjs` y `tests/browser_variant_media.cjs` con las mismas
variables. Son pruebas destructivas para datos sintéticos de un clon, no contra
el QAS del equipo. No ejecutes en paralelo: comparten perfiles y revisiones.
No publiques credenciales, logs privados o archivos de diagnóstico como assets.
