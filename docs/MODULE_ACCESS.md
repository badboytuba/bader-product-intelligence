# Per-user module access — 16.0.1.18.0 candidate

## Delivery status

Local source preparation only, 2026-11-17. Not installed in QAS or PROD and no
real account permissions changed. Existing PROD was inspected read-only at
`16.0.1.17.2`. Static/offline checks do not certify a native registry upgrade.

## Checkbox

After an authorized installation, a user-rights administrator opens
**Ajustes → Usuarios y compañías → Usuarios → Derechos de acceso → Otros** and
checks **Acceso a Producto Intelligence** for an active internal account, then
saves. Unchecking and saving revokes the module role. Reload the backend after
rights change; subsequent server requests recheck access even in an already-open
tab. Genuine unsaved drafts are not discarded by a permission change.

Technical group: `bader_product_intelligence.group_bpi_user`. The group has no
application category: Odoo 16's native uncategorized-group form generates a
Boolean `in_group_<id>` field, rather than the single-group selection generated
for an application category. No hardcoded numeric group ID, writable custom user
field, duplicated flag or new user-management privilege is introduced.

The group implies **only** `base.group_user`. It does not imply Settings,
Administration/Access Rights, product management, website management or Mercado
Libre permissions. Public/portal and inactive accounts cannot use the module.
Existing active system administrators retain access independently of the box;
unchecking this box does not revoke their existing global administrative rights.
Trusted server-side superuser mode continues to support installation and workers,
including inactive OdooBot; client context values never enable superuser mode.

No automatic assignment to existing users or the default/new-user template is
included. The requested active PROD accounts were identified as Male (uid20),
Facundo Colombo (uid22) and Nicolás Pollicino (uid19). The old inactive Facundo
(uid21) is excluded. Assignment is a separate authorized runtime operation.

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

## Validation and rollout gates

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
- On approval assign the group only to the three active accounts, verify access
  as each user without sharing/changing passwords, then certify service/logs.

Rollback access by removing only this group, retaining unrelated rights. A source
rollback must first revoke the new role and explicitly retire its ACL/menu/rule
records; loading an old manifest alone does not remove new XML IDs from the DB.
Use the reviewed backup/rollback plan rather than deleting permission records
ad hoc or restoring an entire live database over unrelated work.
