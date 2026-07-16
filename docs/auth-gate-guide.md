# Adding a single-credential login gate to a Flask app

A reusable pattern for putting a simple login page in front of an internal
Flask tool: one shared username/password, sourced from a Kubernetes secret,
fail-closed if misconfigured, with a clean seam for swapping in SSO later.
This repo (Ethos Dev Console) is the **second** real implementation of this
pattern — the first is Conductor Companion (`tfinnerdu/conductor-tools`,
`app/auth.py`). Both live at `app/auth.py` / `app/routes/auth.py` /
`app/templates/login.html` in their respective repos. This guide explains
the pattern well enough to port into a third Flask app.

## When this fits

- An internal tool with **one small, trusted group of users** who can share
  a single credential for now.
- You want a real login **page**, not a browser-native Basic Auth popup.
- The credential will live in a **Kubernetes secret**, delivered to the
  container as an env var (not stored/hashed by the app itself — your
  cluster's secret store already encrypts at rest).
- You expect to move to **SSO (OIDC/SAML) eventually**, and want today's
  quick solution to not be thrown away when that happens.

## When this doesn't fit

- **Public-internet-facing** without SSO or another real identity provider —
  a single shared credential is not an acceptable long-term posture for
  anything reachable outside a trusted network.
- You need **per-user accountability** (who did what) from the login system
  itself. A shared credential can't give you that — see "What this explicitly
  does not give you" below.
- High-value write actions that need real access control per user, not just
  "is someone logged in at all."

## Architecture

Three pieces, deliberately kept separate so only one of them changes when you
move to SSO:

```
                    ┌─────────────────────────────┐
  every request ──▶ │ before_request gate          │  (auth.py)
                    │  - exempt paths pass through │
                    │  - fail-closed if misconfig'd│
                    │  - else check session cookie │
                    └───────────────┬─────────────┘
                                    │ not authenticated
                                    ▼
                    ┌─────────────────────────────┐
                    │ /login  GET + POST           │  (routes/auth.py)
                    │  - render form               │
                    │  - verify_credentials()  ◀────── THIS is what SSO replaces
                    │  - set session, redirect      │
                    └─────────────────────────────┘
```

1. **The gate** (`before_request` hook) — runs on every request, decides
   authenticated vs. not, redirects/blocks accordingly. This piece **does
   not change** when you move to SSO.
2. **The session primitives** (`is_authenticated()`, `login()`, `logout()`) —
   thin wrappers around Flask's built-in signed-cookie `session`. These
   **do not change** either; an OIDC flow still ends by calling `login()`.
3. **The credential check** (`verify_credentials()` + the `/login` POST
   handler) — this is the **only piece that changes** for SSO. Today it's a
   constant-time string compare; later it becomes "redirect to the identity
   provider, verify the callback, call `login()` with the real username it
   gave you."

## Step by step

### 1. The gate module (`app/auth.py`)

Core pieces, in order:

- `is_configured()` — both credential env vars are set.
- `secret_key_is_default()` — your Flask app's `SECRET_KEY` (which signs the
  session cookie) is still whatever placeholder you shipped in source control.
  **This check matters as much as the credential check** — a default,
  publicly-known `SECRET_KEY` lets anyone forge a valid "authenticated"
  cookie without ever calling `verify_credentials()`. Treat "configured but
  signed with the default key" the same as "not configured at all." Match
  this against your app's *actual* default string — the two implementations
  of this pattern so far have used two different literals
  (`"dev-secret-key-change-in-prod"` vs. `"dev-secret-change-in-prod"`);
  copying the wrong one silently defeats the check.
- `verify_credentials(username, password)` — `hmac.compare_digest()` on both
  fields (constant-time, avoids timing side-channels). Plaintext compare is
  fine here specifically because the secret arrives at the app as plaintext
  from an already-encrypted-at-rest k8s Secret; if your credential source
  hands you a hash instead, use `werkzeug.security.check_password_hash()`
  here instead of a raw compare.
- `login(username)` / `logout()` / `is_authenticated()` — thin wrappers
  around Flask's `session`. Call `session.permanent = True` and set
  `PERMANENT_SESSION_LIFETIME` on the app so sessions expire — there's no
  per-user revocation with a shared credential, so a bounded lifetime is the
  only mitigation for a leaked cookie.
- An exemption list/function for paths that must work with **no** session at
  all: your login page, your logout endpoint, static assets, and — critically
  — **liveness/readiness health-check endpoints** (`/api/health/live` here).
  If your health check is gated, a misconfigured credential turns into your
  orchestrator crash-looping the pod, instead of the pod staying up and just
  refusing to serve the UI. Get your health-check paths exempted before
  anything else. Double-check whether any OTHER route is exempt today only
  by accident (no decorator applied, rather than a deliberate design choice)
  — this repo had one (`/api/health/token`, an internal token-status poller)
  that the global gate now deliberately tightens rather than preserving.
- The `before_request` hook itself:
  1. Skip entirely if the app is running under your test suite (see Testing,
     below) or the path is exempt.
  2. If not "safely configured" (credential set AND `SECRET_KEY` not default)
     → **fail closed**: API-style paths get a 503 JSON error, page paths
     redirect to the login page (which itself shows a clear "not configured"
     notice instead of a form that can never succeed).
  3. If not authenticated → API paths get 401, page paths redirect to login
     with a sanitized `?next=` back to where they were headed.
  4. Otherwise, let the request through.
- A tiny bit of brute-force friction: log failed attempts (username tried +
  remote address, **never** the password) and add a small fixed delay
  (~1 second) before responding to a failed login. This is not a real
  rate-limiter — if this ever faces adversarial traffic, add one (e.g.
  Flask-Limiter) or move up your SSO timeline.
- A `safe_next_path()` helper: only allow a same-origin relative path (starts
  with a single `/`, not `//`) as the post-login redirect target, or you've
  built an open-redirect via a crafted `?next=`.

### 2. The routes (`app/routes/auth.py`)

Just two endpoints:
- `GET/POST /login` — render the form; on POST, verify credentials, call
  `login()`, redirect to the sanitized `next`. Wrong credentials re-render
  the form with one generic message ("Invalid username or password") — never
  say which field was wrong.
- `GET /logout` — call `logout()`, redirect to `/login`.

### 3. The login page (`app/templates/login.html`)

Keep it a **standalone** template, not extending your app's normal page shell
— there's usually no nav/sidebar to show before someone's logged in. Reuse
your existing CSS for brand consistency; the form itself just needs a
username field, a password field, a hidden `next` field, and an error slot.

### 4. Wire it up

In your app factory:
- Configure `SECRET_KEY` from an env var (never hardcode a real one).
- Set `SESSION_COOKIE_SAMESITE="Lax"`, `SESSION_COOKIE_SECURE` (true except
  for local http dev), and `PERMANENT_SESSION_LIFETIME`.
- Register the auth blueprint.
- Call your `register_auth_gate(app)` function — do this early, before your
  other blueprints are registered (right after `db.init_app(app)` here;
  right after a per-request-id hook in the first implementation — the exact
  spot doesn't matter much, just get it in before anything it should cover).

**Watch for a config-caching trap if your app centralizes config in a class.**
This repo's `config.py` reads every env var exactly once, at import time,
into frozen `Config` class attributes — the rest of the app reads
`current_app.config.get(...)`, never `os.environ` directly. If your app does
this too (check for a similar `Config` class before assuming otherwise),
`verify_credentials()`/`is_configured()` must read `current_app.config`, not
`os.environ` — and your tests must set credentials via `app.config[...] = ...`
after the app is built, not `monkeypatch.setenv(...)` (which has no effect
once the module has already been imported once in the process). The first
implementation of this pattern didn't have this problem — a fresh app in
that repo, or in one without this style of config module, reads `os.environ`
live on every call, so either testing style works there.

### 5. Kubernetes wiring

Add the credential (and `SECRET_KEY`) to your existing secret. Two common
patterns, both fine — use whichever this repo's Deployment already follows:

```yaml
# Pattern A — individual secretKeyRef entries (explicit, one line per key)
env:
  - name: SECRET_KEY
    valueFrom:
      secretKeyRef: { name: your-app-secrets, key: SECRET_KEY }
  - name: AUTH_USERNAME
    valueFrom:
      secretKeyRef: { name: your-app-secrets, key: AUTH_USERNAME }
  - name: AUTH_PASSWORD
    valueFrom:
      secretKeyRef: { name: your-app-secrets, key: AUTH_PASSWORD }

# Pattern B — bulk import (this repo's convention): every key in the Secret
# becomes an env var automatically; adding a new key needs no Deployment edit.
envFrom:
  - secretRef: { name: ethos-console-secrets }
```

Leave your liveness/readiness `httpGet` probes pointed at your (exempt)
health path — they should never depend on the auth gate being configured.

### 6. Testing

The gate should be **inert during your normal test suite** — you don't want
to add login flows to every existing test. The cleanest way: check
`current_app.testing` at the top of the `before_request` hook and return
immediately if true. Most test setups already flip `TESTING: True` in their
app-factory config override for the whole suite, so this "just works" for
every existing test with zero changes — but grep for anything that exercises
your *old* auth mechanism for real despite `TESTING=True` (a contract-test
file that toggles the old gate's config value directly, say) before assuming
nothing else needs touching. This repo had exactly one such file; conductor-
tools (the first implementation, built from scratch with no prior gate) had
none, so this is easy to miss if you've only ported the pattern once before.

Then write **one dedicated test file** that builds its own app instance
*without* `TESTING: True`, so the gate actually runs, and test it for real:
unconfigured → blocked; default `SECRET_KEY` → still blocked; configured, no
session → redirect/401; wrong credentials → rejected; right credentials →
session set, subsequent requests pass; `next` sanitization; logout clears the
session. If your app has a session-scoped (not function-scoped) test fixture,
build a genuinely separate app instance per test rather than mutating the
shared one, or a forgotten config mutation leaks into unrelated tests.

## What this explicitly does not give you

- **Per-user identity or audit trail.** Everyone shares one credential; the
  session says "authenticated," not "authenticated as whom." If you need to
  know *who* did something, this pattern alone won't give it to you — that's
  exactly the gap SSO closes.
- **CSRF protection on the login form.** Low-risk here specifically because
  there's no per-user identity to steal — "logging in" a victim as the one
  shared user isn't a meaningfully different attack than not bothering. If
  you add per-user accounts later, add CSRF protection at the same time.
- **Rate limiting beyond a fixed delay.** Fine for a small internal audience;
  not a substitute for a real rate-limiter if this is ever exposed more
  broadly.
- **Authorization / roles.** This is a yes/no gate on the whole app, not a
  permissions system. If different users need different access levels,
  that's a separate, later piece of work — probably worth doing together
  with the SSO migration, once you have real per-user identity to hang roles
  off of.

## Migrating to SSO later

When you're ready:
1. Replace `verify_credentials()` and the `/login` POST handler with your
   OIDC/SAML client's login-initiation and callback-verification flow. The
   callback handler ends the same way today's form does: call `login()` (or
   whatever it becomes) to mark the session authenticated — just now with a
   real, per-user identity instead of a shared string.
2. `is_authenticated()`, `logout()`, the `before_request` gate, the exemption
   list, and the fail-closed-when-misconfigured behavior all stay as they
   are — none of that logic is specific to a shared-credential model.
3. Retire `AUTH_USERNAME`/`AUTH_PASSWORD`; add whatever your OIDC/SAML
   provider needs instead (client ID/secret, discovery URL, etc.) — same
   k8s-secret wiring pattern.
4. Now's the time to revisit CSRF protection and any per-user
   authorization/roles you were deferring — you finally have a real identity
   to attach them to.

**This has now actually happened in this repo** — Ethos Dev Console added
Entra ID (Azure AD) SSO via MSAL alongside (not yet replacing) the shared
credential: `app/auth_entra.py` (the MSAL client factory), the
`login_entra`/`auth_callback` routes in `app/routes/auth.py`, and the gate's
auto-redirect-to-Entra-when-configured logic in `app/auth.py`. It kept step 3
optional rather than mandatory — `AUTH_USERNAME`/`AUTH_PASSWORD` stayed as a
fallback reachable at `/login` — since a hard cutover the same day Entra
goes live leaves no manual override if the app registration or admin consent
isn't fully sorted yet. A live, tested reference if you're porting this
pattern into a fourth Flask app.
