# Per-user module access — 16.0.1.18.0 delivered

## Delivery status

Installed in QAS, then PROD on 2026-11-17 following explicit authorization and
native certification. Both targets upgraded from `16.0.1.17.2` to `16.0.1.18.0`;
services and live acceptance passed. Only the dedicated module group was added
to the three reviewed active internal accounts in each environment. Existing
administrative and unrelated memberships were preserved. Individual assignments
and account identifiers are retained in private audit receipts, not this guide.

Runtime source: `ba92d8691572c4814b045577fa253501badbc584`.
Exact 33-file package SHA256:
`81c8c635d3c091e9348c7fe8348cf765ae35556fca9da2aff91fba82aed5821c`.
This delivery-documentation update is a separate source commit, not a repackaging
or a second runtime deployment. Server documentation still reflects the original
certified package; runtime file identity is recorded by the deployment receipts.

## Checkbox

A user-rights administrator opens
**Ajustes → Usuarios y compañías → Usuarios → Permisos de acceso → Producto Intelligence** and
checks **Acceso a Producto Intelligence** for an active internal account, then
saves. Unchecking and saving revokes the module role. Reload the backend after
rights change; subsequent server requests recheck access even in an already-open
tab. Genuine unsaved drafts are not discarded by a permission change.

Technical group: `bader_product_intelligence.group_bpi_user`. The group has no
application category: Odoo 16's native uncategorized-group form generates a
Boolean `in_group_<id>` field, rather than the single-group selection generated
for an application category. Its automatic section is debug-only in this Odoo16
runtime, so an explicit inherited normal user form displays that SAME virtual
field with XML-loader ID interpolation. No numeric hardcode, writable custom user
field, duplicated permission flag or new user-management privilege is introduced.

The group implies **only** `base.group_user`. It does not imply Settings,
Administration/Access Rights, product management, website management or Mercado
Libre permissions. Public/portal and inactive accounts cannot use the module.
Existing active system administrators retain access independently of the box;
unchecking this box does not revoke their existing global administrative rights.
Trusted server-side superuser mode continues to support installation and workers,
including inactive OdooBot; client context values never enable superuser mode.

No automatic assignment to existing users or the default/new-user template is
included. The separate authorized runtime operation added exactly three reviewed
memberships per environment. The inactive legacy duplicate account was excluded;
no account was reactivated and no password was changed.

## Scope and boundaries

- Operational menus, routes, model methods, required protected fields and private
  document previews use the same module authorization check.
- Existing native product/category/Pack/media ACLs remain authoritative: module
  access does not automatically grant catalog write rights. A user with native
  read-only native product permissions may open the module but cannot bypass
  those ACLs when writing native product/category fields. BPI-owned editorial
  records (for example FAQs and keywords) have their own CRUD permissions through
  this checkbox; it is not a read-only-module role. Do not solve native denials
  with blanket `sudo()`. Native inventory/MRP read denials are shown as unknown
  inventory, not zero stock; this checkbox never grants inventory/MRP roles.
- New operator company rules also protect direct ORM/RPC access to legacy
  keywords, FAQs, images, competitors, chats and all job types. Existing company,
  ownership, private attachment and revision guards remain in place.
- Provider credentials, raw diagnostics/import receipts, global exchange-rate
  configuration, Nancy availability activation, website configuration and view
  synchronization remain system-admin-only. Operators see the configured rate
  read-only and ask an administrator to verify Nancy availability when required.
- AI actions remain explicit and can incur configured provider consumption.
  Operators cannot forge requester identities, enqueue raw jobs or rewrite/delete
  worker jobs. Approved constructors carry an in-process capability unavailable
  to JSON/RPC context and clear it from returned records. Workers revalidate the
  actual requester of new requester-bound jobs before paid work; revocation
  prevents those queued jobs proceeding. Historical admin-created SEO jobs with
  an empty `semantic_request` retain their legacy trusted-worker fallback.
- The optional Mercado Libre bridge and its independent permissions are not
  changed. No ML group, external read/write switch or account is enabled.

## Completed certification and live acceptance

- The exact package passed **565 native backend tests**, including 26 access
  regressions, with zero failures/errors in the isolated QAS clone.
- **193 native QUnit tests / 1,488 assertions** passed with zero browser errors,
  asset failures or blocked writes. The native browser pilot verified the normal
  Users administration action (without debug), the actual Boolean checkbox and
  retained system-admin exchange-rate controls.
- Live QAS and PROD acceptance verified the explicit normal-form view, compiled
  backend assets/action, HTTP 200 for `/web/login` and `/shop`, and zero target
  upgrade-log errors. Each real account passed menu, dashboard and actual product
  detail checks; native product-write rights were already present, not granted.
- Target-only upgrades measured **59.13 seconds** stopped in QAS and **48.49
  seconds** in PROD. Frozen catalog/pricing/Pack/media/website/config/user/contact
  data matched before/after upgrade. Server Git/config, BPI cron activation and
  next-call settings, and unrelated user memberships were preserved.
- Post-start log inspection found zero BPI errors and zero critical events in
  both environments. PROD also recorded two database-serialization events; these
  are not represented as an entirely error-free server log.
- Verified external database, filestore/media and addon/config recovery chains
  are retained. The exact disposable clone was removed with ownership checks;
  task-owned snapshot pins were released after full external re-verification.
  No unrelated backup, runtime path, shared inode permission or live DB is removed.
- Final read-only checks after resuming the interrupted desktop session confirmed
  both services active, version `16.0.1.18.0`, zero pending modules, all deployed
  file hashes exact and Git/config unchanged. Approximately 4.06 GB remained free
  in QAS and 111.85 GB in PROD at that check; unrelated backups were not purged.

Private evidence directory in the deployment workspace:
`audit_outputs/bpi_access_deploy_20261117/` (not part of this addon repository).
Key evidence: `clone_backend_certificate.json`,
`clone_qunit/clone_qunit_certificate.json`,
`clone_pilot/clone_pilot_certificate.json`, and the QAS/PROD upgrade, acceptance,
grant, final-role, post-start-log and owned-cleanup certificates. Do not publish
private account details, archive contents, configuration or credentials.

## Future validation and rollout gates

- Run the addon static validator and `git diff --check`.
- Run the offline OWL suite via `tests/browser_copy_drafts.cjs`: this uses real
  OWL/Chromium with mocked Odoo services, not native server authorization.
- In an **authorized isolated QAS clone**, upgrade only this addon and run
  `tests/test_module_access.py` plus all existing backend and native QUnit tests.
  In addition to the new SEO revocation regression, certify classification and
  Studio enqueue/revoke/worker paths as a native non-admin operator.
  Confirm no external calls, temporary users or historical catalog changes.
- In the real user form verify the checkbox is a Boolean, can be managed only by
  an existing rights administrator, grant/revoke takes effect in routes and menus,
  and module-only users cannot alter Settings or access another company.
- Inspect native write permissions of the three real accounts before promising
  full editing functionality. Preserve unrelated groups exactly as found.
- A live QAS/PROD upgrade requires explicit authorization, verified addon/database/
  filestore backups, rollback and a maintenance window if a restart is needed.
  Preserve all server `.git` directories/remotes and upgrade only this addon.
- On approval assign the group only to reviewed active accounts, verify access
  as each user without sharing/changing passwords, then certify service/logs.

Retire the explicit user-form view before deleting its group during rollback.
Rollback access by removing only this group, retaining unrelated rights. A source
rollback must first revoke the new role and explicitly retire its ACL/menu/rule
records; loading an old manifest alone does not remove new XML IDs from the DB.
Use the reviewed backup/rollback plan rather than deleting permission records
ad hoc or restoring an entire live database over unrelated work.
