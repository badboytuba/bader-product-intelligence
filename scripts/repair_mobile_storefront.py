"""Pure, opt-in website custom-SCSS repair; not a runtime/upgrade hook.

Apply only with reviewed external backups, a website/attachment ownership check,
row lock, original hash guard and field-only rollback. Does not change HTML,
assets, module version, prices, media, fonts or global overflow behavior.
"""
MARKER = "BPI_MOBILE_STOREFRONT_V1"
BLOCK = '/* BPI_MOBILE_STOREFRONT_V1: website-scoped responsive legacy content repair.\n   Do not clip #wrapwrap: fix oversized authored headings and native toolbar\n   intrinsic widths. Preserve desktop, fonts, text, media and native controls. */\n@media (max-width: 767.98px) {\n    #wrapwrap:has(> #top .bpi-header-search) #wrap:not(.js_sale) h1 {\n        font-size: clamp(1.75rem, 7vw, 2.25rem) !important;\n        line-height: 1.2;\n        overflow-wrap: anywhere;\n    }\n    #wrapwrap:has(> #top .bpi-header-search) #wrap:not(.js_sale) h1 :is(span, font, strong, b) {\n        font-size: inherit !important;\n        line-height: inherit;\n    }\n    #wrapwrap:has(> #top .bpi-header-search) #wrap:not(.js_sale) .s_references h1 {\n        /* Authored NBSP groups stay intact without changing saved text. */\n        font-size: clamp(1.375rem, 6.5vw, 2.25rem) !important;\n    }\n}\n@media (max-width: 575.98px) {\n    #wrapwrap:has(> #top .bpi-header-search) .products_header {\n        flex-wrap: wrap !important;\n        gap: 0.75rem;\n    }\n    #wrapwrap:has(> #top .bpi-header-search) .products_header > :is(form, .input-group) {\n        flex: 1 1 100%;\n        min-width: 0;\n        max-width: 100%;\n    }\n    #wrapwrap:has(> #top .bpi-header-search) .products_header > button[data-bs-target] {\n        margin-inline-start: auto !important;\n    }\n}\n/* END_BPI_MOBILE_STOREFRONT_V1 */'


def repair_mobile_storefront(css):
    """Append exact reviewed mobile rules, retaining every original byte."""
    if not isinstance(css, str):
        raise ValueError("Expected reviewed stylesheet text")
    suffix = "\n\n" + BLOCK + "\n"
    if MARKER in css:
        if css.endswith(suffix) and css.count(MARKER) == 2:
            return css, False
        raise ValueError("Mobile override drift; review required")
    if css.count("BADER_PRODUCT_TYPOGRAPHY_V1") != 2:
        raise ValueError("Expected reviewed website typography configuration")
    if "/website/static/src/fonts/" in css:
        raise ValueError("Repair legacy font sources first")
    return css + suffix, True
