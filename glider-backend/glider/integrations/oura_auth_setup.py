"""
One-time OAuth setup script for Oura Ring integration.

Usage:
    python -m glider.integrations.oura_auth_setup

This will:
1. Open a browser for Oura OAuth consent
2. Start a local server to capture the callback
3. Exchange the code for tokens
4. Save the tokens to the configured path
"""

import json
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import httpx

from glider.config import settings
from glider.integrations.oura import AUTH_URL, SCOPES, TOKEN_URL


class CallbackHandler(BaseHTTPRequestHandler):
    """Handler for OAuth callback."""

    auth_code: str | None = None
    error: str | None = None

    def do_GET(self):
        """Handle the OAuth callback."""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "error" in params:
            CallbackHandler.error = params["error"][0]
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Error</h1><p>Authorization failed.</p>")
        elif "code" in params:
            CallbackHandler.auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Success!</h1><p>You can close this window.</p>")
        else:
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Error</h1><p>Missing code parameter.</p>")

    def log_message(self, format, *args):
        """Suppress logging."""
        pass


def main() -> None:
    """Run the OAuth consent flow and save credentials."""
    client_id = settings.oura_client_id
    client_secret = settings.oura_client_secret
    redirect_uri = settings.oura_redirect_uri
    tokens_path = settings.oura_tokens_path

    if not client_id or not client_secret:
        print("Error: Oura credentials not configured.")
        print("\nTo set up Oura integration:")
        print("1. Go to https://cloud.ouraring.com/oauth/applications")
        print("2. Create a new application")
        print(f"3. Add redirect URI: {redirect_uri}")
        print("4. Set OURA_CLIENT_ID and OURA_CLIENT_SECRET environment variables")
        return

    # Build authorization URL
    auth_params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": " ".join(SCOPES),
    }
    auth_url = f"{AUTH_URL}?" + "&".join(f"{k}={v}" for k, v in auth_params.items())

    print("Starting OAuth flow...")
    print("A browser window will open for you to authorize the application.")

    # Extract port from redirect URI
    parsed_uri = urlparse(redirect_uri)
    port = parsed_uri.port or 8092

    # Start local server
    server = HTTPServer(("localhost", port), CallbackHandler)

    # Open browser
    webbrowser.open(auth_url)

    # Wait for callback
    print(f"\nWaiting for callback on port {port}...")
    server.handle_request()

    if CallbackHandler.error:
        print(f"\nError: {CallbackHandler.error}")
        return

    if not CallbackHandler.auth_code:
        print("\nError: No authorization code received.")
        return

    print("\nExchanging code for tokens...")

    # Exchange code for tokens
    with httpx.Client() as client:
        response = client.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": CallbackHandler.auth_code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
        response.raise_for_status()
        data = response.json()

    # Save tokens
    tokens_path.parent.mkdir(parents=True, exist_ok=True)
    with open(tokens_path, "w") as f:
        json.dump(
            {
                "access_token": data["access_token"],
                "refresh_token": data["refresh_token"],
                "expires_at": time.time() + data["expires_in"] - 60,
            },
            f,
        )

    print(f"\nSuccess! Tokens saved to {tokens_path}")
    print("You can now use the Oura integration.")


if __name__ == "__main__":
    main()
