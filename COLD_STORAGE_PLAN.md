# Cold Storage Plan — photos in AWS Glacier Deep Archive

Exploration of Daniel's idea: use AWS's coldest/cheapest storage as a very cheap place to
keep photos that people don't mind waiting for. Honest assessment first, then a design
that works with photocopier, then the go/no-go economics of turning it into a service.

## The storage class

**S3 Glacier Deep Archive** is the one you mean:

| Property | Value (eu-west/central, ~2026 — re-verify current pricing) |
|---|---|
| Storage | **~$0.00099/GB-month ≈ $1/TB/month** |
| Minimum storage duration | **180 days** (delete earlier → still billed for 180) |
| Retrieval time | Standard ~12h, Bulk ~48h |
| Retrieval cost | Standard ~$0.02/GB; Bulk ~$0.0025/GB |
| **Egress to internet** | **~$0.09/GB — the real cost: restoring 1TB ≈ $90+** |
| Per-object overhead | +8KB S3 Standard + 32KB Glacier metadata *per object*, billed |
| Upload (PUT) | ~$0.05 per 1,000 objects |

Key implications:

1. **Storage is basically free; getting data OUT is not.** This is a *deep backup of last
   resort*, not an archive you browse. The product promise must be "your photos survive a
   house fire for £1/TB/month", never "access your photos".
2. **Per-object overhead punishes small files.** 250k photos × 40KB overhead ≈ 10GB of
   billed overhead — fine. But bundling into ~1GB tar archives cuts request costs 200×
   and makes restores saner. Photocopier's date folders are natural bundle boundaries
   (one tar per `YYYY-MM` per extension tree).
3. **The 180-day minimum** means dedup matters *before* upload — photocopier's hash
   database is exactly the right gatekeeper.

## The design insight that makes it usable: hot thumbnails, cold originals

The fatal UX flaw of naive Glacier backup is that users can't see what they have. Fix:

- On upload, generate a ~30–50KB thumbnail + EXIF row per photo
- Thumbnails + manifest (SQLite/DynamoDB) stay in **S3 Standard** — 250k thumbs ≈ 10GB
  ≈ $0.24/month — trivial
- Originals (tarred by month) go to **Deep Archive**
- Browsing/searching is instant and free; users select photos/months to restore, a job
  kicks off the retrieval, and an email lands 12–48h later with a time-limited download
  link

That split — pennies for the browsable index, ~$1/TB for the vault — is the entire product.

## Phase 1 — Build it for yourself (recommended, low risk)

A `photocopier freeze` command (or sibling script) that:

1. Walks a photocopied destination tree (already organised, already deduped)
2. Tars each `EXT/YYYY-MM/` folder, uploads with `storage_class=DEEP_ARCHIVE`
   (boto3 multipart; resumable; verify via checksum)
3. Generates thumbnails → uploads to a `thumbs/` prefix in S3 Standard
4. Maintains a local + S3-hosted manifest (SQLite: hash, filename, archive key, offset)
5. `photocopier thaw 2024-06` → initiates Bulk restore, polls, downloads, untars

Cost for Daniel's own library (say 2TB): **~$2/month**, replacing reliance on two physical
drives. This directly serves "I don't want to rely on my own drives", proves the
architecture, and produces the numbers a service would need. AWS account you already have;
zero new infrastructure.

**Do this regardless of whether the service happens.**

## Phase 2 — The service ("a safety deposit box for your photos")

### Would the economics work?

Assume you charge **£2/TB/month** (≈2× raw cost):

- Storage margin: ~£1/TB/month — thin. 100 users × 1TB = ~£100/month net before
  egress/support. This is a volume business or a lifestyle side-service.
- Restores must be **charged per event** (e.g. £5 + £0.10/GB) or capped (one free
  restore/year) or egress eats you: one careless "restore everything" from a 2TB user
  costs you ~£150.
- Upload ingest is free (AWS ingress costs nothing) — onboarding is cheap.

Competition check: Backblaze personal backup (~$9/mo unlimited, hot), iCloud/Google One
(2TB ≈ £8–10/mo, instant, integrated). Your wedge is **price** (£2–4/month for 1–2TB vs
£8–10) for the "shoebox in the attic" segment that accepts 24h retrieval. That segment is
real (photographers' archives, finished projects, deceased relatives' photo collections,
"my NAS is full") but niche. It will not out-convenience iCloud; it can massively
undercut it.

### MVP shape (if Phase 1 feels good)

- Auth + billing: the leveloh/auther + Stripe patterns you now have
- Desktop uploader: photocopier itself becomes the client (`photocopier freeze
  --account daniel@…`) — presigned multipart URLs; no server touches the bytes
- Web app: browse thumbnails, request restore, download links; restore-status emails
  (Postmark pattern)
- Multi-tenant: one bucket, per-user prefix, S3 lifecycle rules; per-user KMS keys or
  client-side encryption as the trust story ("we cannot look at your photos")
- Legal care: it's a *backup* product — terms must be explicit that it's secondary
  storage, not the only copy (you already have the terms/privacy patterns from leveloh)

### Honest risks

- **Thin margins + support load**: restore hand-holding for non-technical users could eat
  the margin. Mitigate with self-serve UX and email-driven restores.
- **Trust cold-start**: "give a stranger's website all your photos" is a hard first ask.
  The photocopier-CLI-first audience (semi-technical) is the beachhead; encryption at
  rest with user-held keys is the differentiator message.
- **AWS pricing dependency**: 100% exposed to egress pricing. (Cloudflare R2 has zero
  egress but no deep-archive tier; a future hybrid — R2 for thumbs, AWS for cold — is
  plausible.)
- **The uploader is the product**: uploading 1TB from home broadband takes days. Resumable,
  throttleable, restartable upload is where the engineering effort actually goes.

## Recommendation

1. **Phase 1 now** — small, personally valuable, de-risks everything, and slots cleanly
   into photocopier as `freeze`/`thaw` commands. Worth doing even if no service ever ships.
2. Run your own library on it for 2–3 months, note real costs and friction.
3. Then decide on Phase 2 with data. If it ships, it's a Flow-Myna-adjacent trust brand
   ("boring, safe, cheap"), marketed from the photocopier site's audience.

Open questions for Daniel:
- Encrypt originals client-side before upload (stronger story, but thumbnails must then be
  generated pre-encryption and are themselves unencrypted — decide the privacy posture)?
- Bundle tars by month (cheap, coarse restores) vs per-file objects (granular restores,
  40KB/object overhead, 200× request cost)? Suggested: tar by month, restore by month.
- Region: eu-central-1 to match your other infra, or eu-west-1 (slightly cheaper)?
