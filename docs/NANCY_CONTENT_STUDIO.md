# Nancy AI Studio and editorial composition — 16.0.1.13.0

Target: **QAS only**. Source version is not evidence of deployment or live AI
validation; see the separate delivery certificate in the workspace audit folder.

## Editorial workflow

The visible generation action opens a product-scoped Studio, not a paid request.
Shared administrator conversations retain the initial intent, current brief,
category recipe, communication objective, several niches, and independent short
and long objectives. Selecting a niche here does not classify the product.

Sources and conversations are private working information, not website downloads.
PDF/DOCX/TXT and pasted excerpts must be reviewed for this exact product. Public
links are fetched only after an explicit request and use the existing bounded
SSRF protections without modifying competitor records. Old DOC must be converted.
Files are limited to 10 MiB each, five per conversation, 50 pages per PDF and
100 PDF pages per conversation. Scanned PDFs require explicit analysis and review.

Saved Odoo dimensions/weight remain authoritative and variant-specific. Historical
prose and semantic labels are not evidence of materials, clinical indications or
sterilization. In particular, the source saying Angle Larga cannot silently
reidentify SKU9/007-1 Angle Plana. Conflicts are private and prevent application.
The narrator omits unsupported topics rather than padding public copy with data
quality disclaimers. Global editorial templates and old saved descriptions are
never regenerated on installation.

Studio jobs have one active turn per conversation and request-key deduplication.
The internal requested engine is `gpt-6-astra`, reasoning `high`, Responses API,
`store=False`; this does not change other feature model defaults. Operator UI and
errors identify only Nancy AI. Explicit administrator activation verifies model
access using the existing protected credential. No fallback or automatic replay
of an uncertain paid request is allowed.

Proposals contain short/long text HTML and SEO/GEO metadata, not product identity.
Apply selected fields updates only OWL drafts. Guardar sección saves its section;
Guardar ficha persists content and selected metadata atomically. Source, template,
product, semantic and editorial revisions guard old proposals and concurrent work.

## Visual layout

`bpi_technical_description` remains the canonical principal copy. The optional
versioned layout contains exactly one principal reference plus allowlisted text,
callout, image, video, separator, container and two-column blocks. Regenerating
principal copy preserves media/layout; direct native writes remain compatible.
Disabled/no layout follows the legacy website renderer. The website-specific
primary bridges must be synchronized during upgrade as before.

Only allowlisted Bader presets, text HTML and generated social embeds are accepted;
there is no free CSS, scripting or arbitrary iframe source. Short copy remains the
existing compact text editor. Photos include alternative text and captions;
keyboard move buttons supplement visual ordering. Public social embeds load only
after a click and retain an external-link fallback.

## Storage and deployment prerequisites

- The final approved choice is the current QAS server disk, not Cloudflare or a
  new media server. Social links support YouTube, TikTok, Instagram and Facebook.
- Local uploads: JPEG/PNG/WebP <=10 MiB; MP4 H.264/AAC <=200 MiB. No transcoding.
- Shared feature quota: 1 GiB including staged/orphan/temporary files and private
  Studio attachments; preserve 3 GiB free. Refuse new uploads safely when full.
- Install/verify `ffprobe` before accepting MP4; missing validation fails closed.
- Private media directory is configurable with `bpi.description_media_root`.
  QAS planned path: `/var/lib/bpi-description-media`, owner `odoo:www-data`, 2750.
  Child directories/files must permit Nginx group read without general access.
- A dedicated internal Nginx alias `/_bpi_private_media/` points to that directory.
  Odoo authenticates previews and validates saved layout/revision/publication/
  company/website for public delivery before issuing `X-Accel-Redirect`.
  The alias must be `internal`; direct requests must return404. Preserve Range,
  content type and `nosniff`; private/no-store caching prevents stale access grants.
- Chunk uploads are authenticated, product-owned and CSRF-protected, with bounded
  bodies and resumable offsets. No 200 MiB JSON/base64 payload through Odoo.
- The daily local cleanup handles expired incomplete uploads, not referenced
  media, galleries, approved copy or active source attachments.

The shared editorial revision also advances on native content/metadata writes.
New UI calls submit it; legacy callers may omit new optional layout fields and
keep their current behavior. Changing an already-visible product's saved copy
still updates its public content; Studio application alone never does.

## Validation and rollback

Run backend tests plus OWL/browser checks; static syntax alone is insufficient.
Cover stale jobs/drafts, concurrent editors, identity/specification conflicts,
private files, SSRF/MIME abuse, uploads/resume/quotas, social click-to-load, public
media gates, legacy API/content, and responsive 360/768/1024/1440 layouts.
Provider-mocked tests must never be reported as live model generation.

Before QAS upgrade make a verified **off-server** DB/filestore/addon/config backup
(the QAS root disk was95% full at planning), prepare rollback, compare runtime
source hashes and Git metadata, then upgrade only BPI. Keep the optional ML bridge
and integrator configuration read=False/write=False/dry_run=True. Do not restore
an old database over concurrent operator changes without explicit review.

## Key Learnings:
1. A conversational source is not automatically product evidence or public media.
2. One principal-copy reference prevents duplicated text and lost media.
3. Paid work, draft application and final persistence are separate boundaries.

## Video covers and sizing — 16.0.1.13.1

A video block accepts `posterMediaId` (same-product ready image), `videoWidth`
(integer25..100; default100) and `videoRatio` (auto,16:9,9:16,1:1,4:3).
Auto uses saved MP4 dimensions; social ratios use a labeled provider convention
(YouTube16:9/TikTok9:16), not a claim of measured remote dimensions. Override as
needed. Mobile expands to available width; video itself is never stretched/cropped.
YouTube posters use explicit private acquisition through pinned public HTTPS and
existing image normalization/quota. Other providers/custom covers use image upload
or the product library. Existing links need an explicit cover action once; no
external calls happen on product/shop opens. Poster references participate in all
public gates, retention and deletion checks. Apply/save remain explicit.
Playback starts only on the visitor's play click. YouTube iframe sends origin-only
cross-site Referer rather than suppressing identity, following
[official embedded-player requirements](https://developers.google.com/youtube/terms/required-minimum-functionality).

## Nested editor identity — 16.0.1.13.2

Every rich editor inside recursive DescriptionBlock has an explicit block-ID
component key. Odoo 16 OWL does not preserve the enclosing loop identity across
recursive t-call boundaries; without the explicit key, multiple nested editors
can stall the entire render without raising an error. The backend already
requires IDs to be globally unique. Regression coverage mounts the full action
and opens the design tab by DOM click, then edits, reorders, duplicates and removes
nested text blocks before switching tabs. Saved text/layout are never migrated.

## Video title and caption typography — 16.0.1.13.3

Video blocks optionally accept `title` (plain text, 200 characters) and independent
`titleStyle` / `captionStyle` objects. The existing `caption` stays plain text up to
500 characters. Supported style keys: `font` (display/body, official Bader Sans or
Helvetica), integer `size` (12–64 px), boolean `bold`/`italic`, `align`
(inherit/left/center/right), `color` (auto/petrol/green). Unknown keys, CSS, HTML
formatting, remote fonts and invalid types are rejected; text is escaped on render.
Defaults are read-only until explicitly edited: title display28px, caption body14px,
normal emphasis, inherited alignment/color. Empty text produces no empty markup.

Title sits above the video; caption sits below, aligned to the configured video
width. Preview and public projection generate CSS only from these bounded values.
Bold/italic synthesis is scoped to these two text elements, not global Bader fonts.
The redundant Abrir vídeo footer is gone; the accessible play button and original
social-link fallback on non-embeddable networks remain. Opening the editor makes
no provider/font calls and does not rewrite old text, media or layout records.

Rollback to1.13.2 does not understand the three new optional JSON keys. Preserve
newly authored title/styles outside the old validator before any downgrade; never
strip them or restore an old database over operator edits without explicit review.

## Clear chat outcomes and reusable strategies — 16.0.1.13.4

User message paragraphs and timestamps inherit the white foreground on the dark
Bader bubble. A completed chat-only turn explicitly says that no proposal was
created; it no longer leaves the preparing notice. Only the operator's requested
job may open its new non-stale proposal automatically, and only while the preview
and brief remain untouched. Other/newer proposals use the explicit version
selector. Detect new IDs rather than array length (history is capped at30).

**Revisar como fuente** copies a user message into the local source draft, without
calling AI or approving facts. The operator trims unrelated text, adds the source,
selects pertinent excerpts and explicitly confirms them. A source may be researched
information supplied by an administrator; it is not falsely described as an
independent verification. Existing source notes cannot be silently replaced.

**Reutilizar estrategia** explicitly lists up to30 strategies from other accessible
products, searchable by product/SKU. The operator reviews/edits only objective,
tone, audiences, intent and short/long focus. Confirming creates an independent
conversation on the destination product. No initial message, history, proposals,
files, sources or product facts are copied; the destination category recipe and
saved dimensions remain authoritative. Source revisions and company/admin access
are checked; source SKUs and physical measurements in the reusable brief are
rejected. General prose still requires operator review to remove product-specific
claims. Unsaved current Studio work must be saved/applied or explicitly discarded.

The generation instructions explain that template IDs and variant IDs occupy
different Odoo namespaces. They must never be treated as a technical conflict
simply because their numbers differ. Historical proposal warnings are not evidence
and must not be inherited without checking current facts. These instructions are
covered with controlled tests, not a claim of live paid-model validation.
