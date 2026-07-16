"""MSAL client factory for Entra ID (Azure AD) sign-in.

Pure and dependency-isolated on purpose: the two routes that use this
(app/routes/auth.py's login_entra/auth_callback) never talk to msal
directly — they only ever call build_msal_app() — so tests can monkeypatch
that one function to a fake and never touch the network or a real tenant.
See docs/auth-gate-guide.md's "Migrating to SSO" section.
"""
import msal

# The minimal sign-in scope — name + email, nothing else. This app only
# needs to know who's signing in, not to call Graph API on their behalf.
SCOPES = ["User.Read"]


def build_msal_app(tenant_id: str, client_id: str, client_secret: str) -> msal.ConfidentialClientApplication:
    return msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
    )
