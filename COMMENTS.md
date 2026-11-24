# Guest comments

The blog stays on GitHub Pages. New comments are stored separately in the Time Turner Comments Supabase project (`uyncwplmenormkebmecn`); historic comments remain in `content/comments/`.

## Current rollout

Enabled on 24 November 2026. The private database migration, `blog-comments` Edge Function and hostname-restricted Cloudflare Turnstile widget are live. An actual guest submission was verified in the database as `pending`, `is_author = false`, and excluded from the public endpoint. Failed spam checks and direct anonymous database access are denied. The unlinked verification page was removed after testing.

The single `Connection test` submission is retained privately for verification, never approved or shown publicly. It can be rejected in the dashboard without deleting it. Historic comments remain intact. The function checks Turnstile server-side; the secret is stored only in Supabase's protected function settings.

## Approval email alerts

Enabled and tested on 24 November 2026. A real guest comment remained pending and private while its notification reached the owner address with Resend status **Delivered**. Each alert contains the post title, comment preview, article link, moderation link and comment ID. The current sender is `Time Turner <onboarding@resend.dev>` and the recipient is the Resend account owner. This is a moderation alert, not a reader subscription service.

The sending-only Resend key and recipient/sender settings are stored in protected Edge Function secrets: `RESEND_API_KEY`, `COMMENTS_NOTIFY_TO`, `COMMENTS_NOTIFY_FROM`. `COMMENTS_NOTIFY_TOKEN` authenticates the private retry worker; its matching value is encrypted in Vault as `blog_comments_notify_token`. Never save actual values in Git or chat. Moving to a custom sender requires verifying that domain in Resend first.

`202611240002_comment_notifications.sql` adds a private outbox and service-only claim/prepare/finish functions. `schedule-comment-notifications.sql` installs the active `blog-comment-alerts` job, once per minute. The guest endpoint attempts delivery after saving a comment, and the job retries queued failures. A delivery failure never discards a comment or blocks its submission. Exact email payloads and stable idempotency keys are retained across retries. Retries stop after 8 attempts or 23 hours; inspect private `blog_comment_notifications` for failed records. Already moderated or withdrawn posts are skipped before sending. Existing comments are not backfilled.

The retry route is `POST /functions/v1/blog-comments?task=notify`, protected by `x-comments-notify-token`; public browser keys cannot invoke it. To pause alerts, disable the named cron job and remove the notification configuration from the function. Do not alter public comment permissions. The additional `Notification test` comment is retained pending and must not be approved as reader content.

## Readers

Each published article has a collapsed **Leave a comment** form. Readers supply a name and comment, without an account or email address. Every new comment is pending until approved. Only approved comments and their public fields are returned to visitors. Replies to new approved comments are supported. Archived comments remain read-only.

The permanent source post ID joins both the original URL and `/read/.../` address to the same discussion. The builder emits `comments-posts.json` containing only published post IDs; withdrawn posts cannot be read or commented on through the endpoint. The manifest cache lasts 15 seconds, in addition to website deployment/cache propagation.

## Approving and replying

Open the Supabase project, then **Table Editor → blog_comments**. Filter `status` to `pending` and review the name, body and post ID. Set `status` to `approved` to publish, or `rejected` to keep a submission off the site. Refresh the article to see approved comments. A rejected comment remains in the table and can be restored; deleting rows is unnecessary.

For an owner reply, add a row in the Table Editor with the same `post_id`, the original comment's UUID in `parent_id`, your name/body, `status = approved` and `is_author = true`. Leave `id` and `created_at` at their defaults. Guest submissions cannot set author status or approval. Do not mark a visitor's comment as your own.

Original comments in `content/comments/` remain managed in source and are not copied into Supabase. A fresh clone includes the archive, not the new live comments.

## Configuration and deployment

- `content/comments.json`: enabled flag, project URL, **publishable** key and Turnstile **site** key only. These are public browser configuration. Never put a secret/service-role key here.
- `supabase/migrations/202611240001_blog_comments.sql`: tables, constraints, RLS, revoked guest privileges and server-only submission function. Apply once through Supabase SQL Editor before deploying the endpoint.
- `supabase/functions/blog-comments/index.ts`: dependency-free Edge Function; deploy as `blog-comments`.
- `supabase/config.toml`: `verify_jwt = false` for this guest endpoint. The handler checks the publishable `apikey` itself and validates Turnstile server-side. No other endpoint's authentication should be changed.
- `theme/comments.js`: client form, safe text rendering, pagination and lazy spam check.

Create a Turnstile widget restricted to `indiantripper.in` and `www.indiantripper.in`. Store its **secret** only as `TURNSTILE_SECRET_KEY` in **Supabase → Edge Functions → Secrets**. Put the public site key in `content/comments.json`. Never commit, log or send the secret through chat.

Supabase supplies `SUPABASE_URL`, `SUPABASE_SECRET_KEYS` and `SUPABASE_PUBLISHABLE_KEYS`; the function uses the `default` key from each dictionary. Legacy fallback variables are `SUPABASE_SERVICE_ROLE_KEY` and `COMMENTS_PUBLISHABLE_KEY`. The server key is never sent to readers. The handler uses the default production origin/hostname pair; only override `COMMENTS_SITE_URL`, `COMMENTS_ORIGINS` or `COMMENTS_HOSTNAMES` deliberately. No local origins are enabled in production.

For any future redeployment, confirm the endpoint can read approved comments, rejects invalid submissions/withdrawn posts and holds a real guest submission for approval. Then set `enabled` to true and publish. Local `--preview` builds show the form but intentionally make no comment/captcha requests or submissions.

## Abuse controls and privacy

Database tables and submission RPC have no `anon` or `authenticated` grants. An Edge Function performs public filtering and server-side insertion. Pending, rejected and abuse-control records are private. Input is validated, request bodies capped, HTML rendered as text, challenge hostname/action/post binding checked, and retry IDs prevent duplicate writes.

Atomic database limits allow 3 submissions per client per 10 minutes and 20 per 24 hours; global ceilings are 30 per minute and 300 per hour. These are a spam backstop, not a guarantee against all abuse or request-volume costs. A keyed hash of the proxy-provided client address is stored in `blog_comment_receipts`, not the raw address. Receipts older than 24 hours are cleaned on the next submission. Supabase and Cloudflare may keep their own service logs under their policies.

The frontend loads comments as the reader approaches the section and loads Turnstile only when composing. An outage leaves article text and archived comments readable and keeps failed submission text in the form.

## Moving the blog later

Export **all rows** of `blog_comments` from Supabase as CSV, including pending/rejected rows if you want to retain moderation history. Keep the export private. Preserve `id`, `post_id`, `parent_id`, `created_at`, `status` and `is_author` when importing elsewhere. Keep the source post IDs unchanged. The schema and endpoint code travel with the repository; the live database and dashboard access do not.

`blog_comment_receipts` is temporary abuse-control data and is not needed for a migration. Do not delete or reset the Supabase project until the exported comments are checked in the replacement service. Enable appropriate Supabase backups or make periodic private exports according to the project's plan; GitHub alone does not back up new comments.

## Checks

Use Python with `requirements.txt` installed and Node 20+:

```sh
python -m unittest discover -s tests -v
node --test tests/comments-function.test.mjs tests/comment-notifications.test.mjs
python build.py
```

To pause new commenting, set `enabled` to false and publish; archived comments remain visible. The backend remains deployed, so also pause the function if you intend to stop all direct submissions. Do not change table privileges to troubleshoot a frontend error.
