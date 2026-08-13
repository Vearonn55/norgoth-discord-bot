"""Future Content Notifications provider OAuth architecture notes.

MVP CN platforms (Twitch, YouTube, Kick, X-poll) use operator app credentials only.
This module documents the callback contract for Phase 6 Connect flows so
implementers do not conflate OAuth with ``/webhooks/...`` receivers.

Planned routes (not mounted until a Connect product ships):

- ``GET /api/v1/oauth/{provider}/authorize`` — guild-manager session required;
  creates ``ProviderOAuthStateService`` state (+ PKCE for Kick/TikTok/X).
- ``GET /api/v1/oauth/{provider}/callback`` — validates state, exchanges code
  server-side, encrypts tokens with ``SecretBox``, upserts a future
  ``provider_oauth_connections`` Postgres row, redirects to allowlisted
  dashboard path.

Providers: ``twitch`` (optional cost-0 EventSub), ``tiktok`` (Display self-only),
``kick`` / ``x`` only if a product need appears.

Do not enable Connect buttons in the dashboard until these routes are mounted
and the runbook credentials for that provider are approved.
"""

from __future__ import annotations

PLANNED_OAUTH_PROVIDERS = ("twitch", "tiktok")
PLANNED_CALLBACK_PREFIX = "/api/v1/oauth"
