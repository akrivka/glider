"""
One-time OAuth setup script for Google Calendar integration.

Usage:
    python -m glider.integrations.google_auth_setup

This will:
1. Open a browser for Google OAuth consent
2. Save the resulting tokens to the configured tokens path
"""

from google_auth_oauthlib.flow import InstalledAppFlow

from glider.config import settings
from glider.integrations.google_calendar import SCOPES


def main() -> None:
    """Run the OAuth consent flow and save credentials."""
    client_secret_path = settings.google_client_secret_path
    tokens_path = settings.google_tokens_path

    if not client_secret_path.exists():
        print(f"Error: Client secret file not found at {client_secret_path}")
        print("\nTo set up Google Calendar integration:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create or select a project")
        print("3. Enable the Google Calendar API")
        print("4. Create OAuth 2.0 credentials (Desktop application)")
        print(f"5. Download and save as {client_secret_path}")
        return

    print("Starting OAuth flow...")
    print("A browser window will open for you to authorize the application.")

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
    creds = flow.run_local_server(port=8090)

    tokens_path.parent.mkdir(parents=True, exist_ok=True)
    with open(tokens_path, "w") as f:
        f.write(creds.to_json())

    print(f"\nSuccess! Tokens saved to {tokens_path}")
    print("You can now use the Google Calendar integration.")


if __name__ == "__main__":
    main()
