# Plan Rework — ReviewReply AI

## Security & Compliance
- [ ] Add CSRF protection for all POST forms (per-session token in base layout, middleware validator).
- [ ] Harden rate limiting: per-user + per-route buckets; move to persistent (Redis) if deployed multi-instance.
- [ ] Replace admin backdoor with OTP-based owner login or remove entirely; guard admin pages with signed tokens.
- [ ] Encrypt at-rest secrets (Google refresh, Slack/Telegram webhooks) or store in KMS; mask in logs/admin.

## Data & Migrations
- [ ] Introduce Alembic migrations (cover new business fields, notification_prefs, team_memberships).
- [ ] Backfill existing records with safe defaults; migration to populate account_id/role for legacy sessions.
- [ ] Add indexes on `reviews.business_id`, `responses.review_id`, `team_memberships.account_id`.

## Notifications & Background Work
- [ ] Move notifications to a background queue (Celery/RQ/Arq) with retries, timeouts, and dead-letter logging.
- [ ] Add templated Slack/Telegram messages and per-event opt-out UI; include deep links to the exact review.
- [ ] Add daily/weekly digest email with stats (publish rate, time-to-reply, negatives handled).

## Google & External Integrations
- [ ] Add scheduled sync of Google reviews (cron/worker) and token refresh monitoring + alert on failures.
- [ ] Add “Publish to Google” audit log (who/when, text) and show in dashboard history.
- [ ] Support multi-location mapping per account (currently assumes first business when linking Google).

## Analytics & Dashboard UX
- [ ] Add charts: replies over time, avg time-to-publish, rating delta (pre/post usage), negative-recovery rate.
- [ ] Add status tabs or server-side filters; keep client filters for instant slicing.
- [ ] Add search box over reviews (text + author) and sort by rating/date/status.
- [ ] Add bulk actions: approve all 4–5★, regenerate all pending, publish queue.
- [ ] Show brand facts/banned phrases preview tooltip on review cards.
- [ ] Infinite scroll or numbered pagination with per-page selector.

## Review Generation Quality
- [ ] Add per-business “fact sheet” editor with structure (hours, services, policies) and inject into prompt.
- [ ] Add guardrails: banned phrases enforced post-generation (regex scrub), toxicity/PII check before approve/publish.
- [ ] Allow model selection / temperature controls per business; configurable max tokens.
- [ ] Cache generation cost metrics per account; show estimated spend/savings.

## Team & Roles
- [ ] Implement role enforcement on all routes (publish, delete, settings) and add Admin role with billing rights.
- [ ] Add invitation acceptance flow (tokenized link) instead of silent auto-attach by email.
- [ ] Add audit trail for member actions (approve/publish/regenerate/delete).

## Billing & Plans
- [ ] Align pricing page claims with live features (analytics, priority support); gate features by plan.
- [ ] Enforce response limits per plan (Starter 50/mo) with soft/hard cap warnings.
- [ ] Add trial countdown banner + upgrade CTA in dashboard header; send trial-ending reminders via email.

## Reliability & Observability
- [ ] Centralized logging (structured) and error alerts (Sentry/Logtail/etc.).
- [ ] Health checks for external APIs (Anthropic/Stripe/Google) with fallback messaging in UI.
- [ ] Add uptime/probe endpoint and basic metrics (Prometheus-compatible) for worker and web.

## Testing & Tooling
- [ ] Add pytest smoke/e2e for signup→onboarding→generate→approve→publish flows.
- [ ] Add factory/data seeding for local dev; sample DB with reviews.
- [ ] Prettier/Tailwind lint or at least HTML lint for templates.

## Email & Deliverability
- [ ] Switch to Postmark/SES with DKIM/SPF; track bounce/complaint; include unsubscribe footer for digests.
- [ ] Templated emails (Jinja) for notifications; local preview mode.

## Performance
- [ ] Add caching for stats queries; pagination to avoid heavy joins; use async DB driver or move to Postgres.
- [ ] Lazy-load review cards (skeletons) and debounce filter/search.

## Misc UX
- [ ] Add keyboard shortcuts (approve/regenerate) and focus states.
- [ ] Add inline help/tooltips for new settings (auto-approve, banned phrases, brand facts).
- [ ] Localize copy (UK/US English switch) and adjust spelling rules accordingly.

## Deployment
- [ ] Add container healthchecks, env validation, and reproducible `.env.example` with all new vars.
- [ ] CI pipeline: lint, tests, build image, push to registry.
