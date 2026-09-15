# Technical specifications — 16.0.1.8.0 / QAS

Datos y precios has a Bader-branded **Especificaciones técnicas** card for each
product variant, including Packs. Dimensions (Alto, Ancho máximo, Ancho mínimo,
Largo, Diámetro) are centimeters; Peso neto is grams. These are measurements of
the product **without packaging**, confirmed by the operator for the source sheet.

Values are optional, positive, finite, at most 1,000,000 and six decimal places.
Decimal comma and decimal point are accepted, but thousands separators are not.
Unknown values stay blank, never zero. Minimum width cannot exceed maximum width.
Each saved field carries a source/date. Editing changes provenance only for the
changed fields. Clear a field and save to remove its evidence.

The dedicated admin-only `bpi.product.specification` model is keyed uniquely by
`product.product`, with company record rules. Measurements do not overwrite
native logistics weight/volume, prices, stock or MercadoLibre data. Packs retain
their own measurements; component measurements are not summed or inferred.

Rows participate in the existing Datos and full-workspace save transactions.
A stale revision rejects the save without losing drafts. Concurrent edits during
a successful save retain their values while adopting the resulting row revision.
Opening/navigating the card makes no external requests. Existing descriptions
remain unchanged; saved measurements become evidence on the next explicit Nancy
generation, with variant labels, decimal commas and units. Dedicated net weight
supersedes native logistics weight in that generation's facts only. Specification
revision participates in server and frontend generation freshness checks.

## Controlled spreadsheet import

The private service helpers `_prepare_specification_import` and
`_apply_specification_import` are not RPC endpoints. An audited operator script
reads a frozen UTF-8 CSV snapshot, validates its expected headers and hash, and
passes only the six measurement columns plus exact internal SKU and source row.
No descriptions, suppliers, categories, SEO, or other sheet fields are imported.
No periodic Google Sheets sync is installed.

- SKU keeps punctuation, case and leading zeros; only outer whitespace is trimmed.
- Duplicate source SKUs and ambiguous Odoo SKUs are not resolved heuristically.
- Missing/unmatched/archived SKUs are skipped and reported; no products are created.
- Invalid/zero cells are skipped, not converted to zero; inverted width pairs are
  omitted while other valid fields can be imported.
- Existing nonempty conflicting values are preserved and reported.
- Apply verifies saved revisions and variant/SKU identity. The whole batch is
  transactional. Re-running the same source makes no changes.
- Import writes only specification records, never product or integration records.

Runtime proof, source snapshots, unmatched SKUs and exception reports belong in
workspace audit outputs, not portable addon data. QAS backup/rollback and actual
Odoo/OWL validation are required before deployment; production is out of scope.
