# Agent Instructions — Bader Product Intelligence

This repository is an Odoo 16 Community addon. It must be cloned or deployed with the technical addon directory name:

```text
bader_product_intelligence
```

## Mandatory safety rules

1. **Never commit or print secrets.** Local `.env` files may contain production host, database, GitHub token, OpenAI key, Firecrawl key, or deploy credentials. `.env` and `.env.*` are ignored; use `.env.example` only as a template.
2. **Treat any host/database in `.env` as live production** until proven otherwise. Do not deploy, restart services, run `-u all`, run destructive SQL, or change server packages unless the user explicitly asks.
3. **Develop in Git first.** Keep changes in this addon, validate locally, then push. For production/QAS, upgrade only the target module: `bader_product_intelligence`.
4. **Admin-only feature.** Backend routes and menus are intended for `base.group_system` users.
5. **Use Odoo 16 patterns.** Keep code organized in `models/`, `controllers/`, `views/`, `security/`, `data/`, `static/src/`, and add ACL rows for new persistent models.

## Skills / operating mode expected for future Codex agents

If available, use an Odoo 16/OCA development skill or equivalent senior Odoo workflow:

- read `__manifest__.py`, models, views, security, assets before editing;
- prefer small, explicit module changes;
- validate Python, XML, JS, and then Odoo install/upgrade in a real Odoo 16 runtime/QAS;
- never expose secrets from `.env`;
- for deploy/server/log work, use a safe deploy/runbook approach with backups and rollback.

Useful validation commands from this repo:

```bash
python3 -m compileall controllers models tests
python3 - <<'PY'
from pathlib import Path
import xml.etree.ElementTree as ET
for p in list(Path('views').glob('*.xml')) + list(Path('data').glob('*.xml')) + list(Path('static/src/xml').glob('*.xml')):
    ET.parse(p)
    print('XML OK', p)
PY
tmp=$(mktemp --suffix=.mjs); cp static/src/js/product_intelligence_action.js "$tmp"; node --check "$tmp"; rm -f "$tmp"
```

Odoo runtime validation, in the target environment only:

```bash
odoo-bin -d <database> -i bader_product_intelligence --stop-after-init
odoo-bin -d <database> -u bader_product_intelligence --stop-after-init
```

## Start here for context

Read these files before changing code:

1. `docs/CODEX_5_5_HANDOFF.md` — detailed architecture, current state, known issues, next recommended fixes.
2. `README.md` — install/config overview.
3. `__manifest__.py` — module dependencies, data, and assets.
4. `controllers/main.py` — JSON route surface.
5. `models/product_intelligence.py` and `models/product_template.py` — core backend behavior and payload contract.
6. `static/src/js/product_intelligence_action.js` and `static/src/xml/product_intelligence_templates.xml` — OWL UI and RPC contract.

## High-priority known issues

Before adding big new features, consider fixing these known issues documented in detail in `docs/CODEX_5_5_HANDOFF.md`:

- gallery delete sends token strings like `bpi:12` / `odoo:5` to a backend endpoint expecting an integer;
- gallery delete button appears for native Odoo images that should not be deleted by BPI;
- image Studio sends `selected_image_url` but backend currently ignores it;
- chat quick actions duplicate the user message and chat state can survive product switches;
- competitor price comparison may mix product USD with scraped ARS/USD;
- external image URL downloads follow redirects without validating each redirected URL;
- website bridge view is inactive, so storefront rendering is not active from this addon alone.
