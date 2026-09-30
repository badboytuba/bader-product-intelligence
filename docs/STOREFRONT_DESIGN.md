# Bader storefront · 16.0.1.17.1

Opt-in QAS presentation. The addon does not activate the design on upgrade.
`website.bpi_premium_storefront_enabled` defaults to false; the website must have
its own reviewed `bpi_premium_footer_html` and `bpi_premium_footer_legal_name`.
All three fields require an administrator to write. Footer HTML is sanitized,
translated and edited through a native `t-field` in the website editor (or settings).
The copyright year is server-rendered; no network, AI or external design library.

## Product page
The existing module-owned product bridge reaches website-specific primary copies.
Never overwrite the author's `website_sale.product` arch. Include `website` in the
native cache key: toggling or changing a site's footer must not leak across sites.

The duplicate product search/breadcrumb row is omitted only when enabled. It also
contained tariff variables and the selector: recalculate and render the native
selector immediately before the price when more than one visible tariff exists.
Do not change native prices, permissions, forms, variant radio values or cart.

The native carousel remains authoritative: IDs, media order, zoom URLs and HTML
replacement on variant selection are unchanged. Scope the skin to
`.bpi-product-premium`; enhance the native carousel widget so replacement starts
its keyboard/thumbnail behavior again. Replace native animated pinning only there
with bounded CSS sticky on the gallery column at >=992px. Track header/card resize;
if the card does not fit the viewport, keep it static and fully accessible. Stop at
the native purchase row before descriptions. Keep legacy behavior on other sites. Wheel scrolling must not
change slides accidentally. The native grid option and hidden-gallery setting
remain native, not forced into a carousel.

Use image contain, stable square stage and a subtle white card. Thumbnails are a
vertical scroll rail at >=1200px and horizontal below otherwise. Cards align to
the start of the row; a taller purchase column can still have natural white space.
Do not hide saved commercial copy or payment conditions to eliminate that space.

## Footer
Late QWeb inheritance retains `$0` (the complete authored legacy footer) as the
conditional fallback. Keep `#bottom` and page `footer_visible` rules native. The
new body is a website-owned HTML field, not a module template the next upgrade
would overwrite. Its content is explicitly seeded only for the approved QAS site;
no Argentine attachment ID, contact address or fiscal URL is hardcoded in code.
Never read contact data blindly from the company: its phone may be empty while
there is an approved authored footer phone. Preserve the exact fiscal image/link.

Bader local logo/fonts/colors only. Four desktop columns, two tablet, one mobile;
current social Bader routes, relative navigation, contact and fiscal information.
No GitHub or Odoo promotion in the opt-in footer. Keep the original on disable.
Do not change the global head, header/search, WhatsApp integration or company data.

## Release gates
Test 360/768/1024/1440; the real scroll container is `#wrapwrap`, not `window`.
Validate High/Starter, many/single/no images, portrait/video/zoom, keyboard/touch,
multiple tariffs/cart, native editor, site2 and flag-off fallback. Test upgrade
idempotence, website caches and exact preservation of stored business content.
Backup outside the nearly full QAS disk; only the approved site's three new
fields may be seeded/activated. No production delivery without new authorization.

### Native response ordering
Odoo's `DropMisordered` does not prevent a callback which already mutated the DOM.
For opt-in main products only, echo a bounded numeric request token in the existing
`/sale/get_combination_info_website` response; reject stale callbacks before native
price/media mutation. Do not create another endpoint, fetch images independently,
or change the native combination payload. Flag-off calls preserve the legacy result.

### Administrar y aprobar el diseño (QAS)
En Ajustes de Producto Intelligence, elige el website y busca **Diseño Bader:
ficha y pie de página**. La opción requiere contenido y razón social revisados.
El editor nativo del sitio permite editar los textos y enlaces del nuevo pie;
**Guardar** conserva ese contenido por website. Desactivar la opción recupera el
pie anterior sin borrar el nuevo. Las imágenes y variantes se gestionan como antes.

La marca del pie debe contrastar con petróleo: utiliza el SVG oficial
`bader_logotipo_verde_claro.svg`, sin recolorearlo. En campos HTML sanitizados,
acompaña iconos sociales con texto `visually-hidden` (no dependas solo de aria-label,
que el saneamiento nativo puede retirar). Revisa también las traducciones del
website al cambiar contenido desde administración.

## 1.17.1 refinements (QAS approval)

- The user changed the earlier static-gallery choice to **bounded desktop sticky**,
  without animation. Native carousel, variant lifecycle, zoom and order remain intact.
- Reserve a 96px vertical thumbnail rail, including classic-scrollbar and focus space;
  below 1200px keep the horizontal rail. Override the native mobile dot-only rule
  inside this opt-in card so actual thumbnail images remain visible. Test real `#wrapwrap` scrolling.
- Keep native mega-menu anchoring: the search row belongs **below its stacking layer**.
  Moving the menu down creates a hover gap. Opening it closes pending autocomplete.
- Optional version-1 layout key `headingAlign` accepts left/center/right only. Default
  left aligns to the principal block inset, without rewriting saved layout or copy.
  Common and selected-variant projections share the same server style resolver.
  Designer control: **Título de la descripción**; preview/save stay explicit.
- While a current-block YouTube cover is downloading, content/all/variant saves wait.
  Old missing covers use **Obtener portadas pendientes**, not a fetch on page open.
  Custom covers and removed/stale blocks are preserved. Explicit server fetch tries
  verified HD then standard official cover; both are bounded and SSRF-protected.
  Visitors load only authorized local media; no YouTube player/network until play.
- This release changes no price, stock, classification, saved copy or native media.
  The approved TREKC pilot cover link is a separate revision-guarded QAS operation.

Source validation and deployment evidence are recorded separately. Never treat a
version bump or these notes as proof that a target environment has been upgraded.

Candidate validation: 539 isolated backend tests and 186 real Odoo QUnit tests
passed. The focused browser suite validates all four widths, real scroll boundaries,
classic-scrollbar clearance, hover reachability, native variant replacement and
actual OWL alignment preview/save/public round trip. See runtime delivery notes
for final live verification; no paid AI is used in these checks.
