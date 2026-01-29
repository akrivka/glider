# YourSpotify OAuth Authentication Analysis

## Executive Summary

YourSpotify implements Spotify's **Authorization Code Flow** for OAuth 2.0 authentication. **Users are required to create their own Spotify developer application** and provide credentials as environment variables. The system features **automatic token refresh** with minimal user intervention, though users must manually reauthenticate if they revoke access on Spotify.

---

## 1. OAuth Implementation Overview

### Authentication Flow

YourSpotify uses the standard OAuth 2.0 Authorization Code Flow:

1. **Authorization Request** → User redirected to `https://accounts.spotify.com/authorize`
2. **User Consent** → User authorizes the application on Spotify
3. **Callback** → Spotify redirects to `{API_ENDPOINT}/oauth/spotify/callback` with authorization code
4. **Token Exchange** → Server exchanges code for access token and refresh token
5. **Session Creation** → Server issues JWT token stored in HTTP-only cookie

### Implementation Location

- Primary OAuth logic: `/apps/server/src/tools/oauth/Provider.ts`
- Token refresh mechanism: `/apps/server/src/tools/apis/spotifyApi.ts`
- Spotify API wrapper: `/apps/server/src/tools/apis/spotifyApi.ts`

### Security Features

- **CSRF Protection**: Random 32-character state parameter validation
- **Secure Cookies**: HTTP-only, strict SameSite policy, secure flag for HTTPS
- **Token Separation**: Spotify access tokens for API calls, JWT for session management
- **Automatic Refresh**: Tokens refreshed proactively with 120-second buffer before expiration

---

## 2. Developer App Requirement

### ✅ YES - Users MUST Create Their Own Spotify Developer App

**Setup Requirements:**

1. **Create Spotify Application**
   - Visit: https://developer.spotify.com/dashboard/applications
   - Create a new application
   - Enable "Web API" in application settings

2. **Configure Redirect URI**
   - Must register in Spotify dashboard: `{API_ENDPOINT}/oauth/spotify/callback`
   - Examples:
     - Local development: `http://localhost:8080/oauth/spotify/callback`
     - Production: `http://home.mydomain.com/your_spotify_backend/oauth/spotify/callback`

3. **Obtain Credentials**
   - Copy Client ID → set as `SPOTIFY_PUBLIC` environment variable
   - Copy Client Secret → set as `SPOTIFY_SECRET` environment variable

4. **User Management** (Production/Extended Quota Mode)
   - Register authorized users via Spotify Dashboard → User Management
   - App creator is automatically authorized
   - Additional users must be manually added to allowlist

### Required Environment Variables

```bash
SPOTIFY_PUBLIC=your_spotify_client_id
SPOTIFY_SECRET=your_spotify_client_secret
API_ENDPOINT=http://localhost:8080        # Backend URL
CLIENT_ENDPOINT=http://localhost:3000      # Frontend URL
```

### Why This Approach?

- **Self-Hosted Architecture**: Each instance uses unique credentials
- **User Control**: Full ownership of data and API access
- **Compliance**: Follows Spotify's API terms of service
- **Privacy**: No central authentication server collecting user tokens

---

## 3. Token Management & Reauthentication Frequency

### Token Storage

Tokens are stored in MongoDB with each user document:

```typescript
{
  accessToken: string,      // Short-lived access token
  refreshToken: string,     // Long-lived refresh token
  expiresIn: number        // Absolute timestamp (Date.now() + seconds * 1000)
}
```

### Automatic Token Refresh

**Refresh Trigger**: Before every Spotify API call, if token expires within 120 seconds:

```typescript
// From spotifyApi.ts - checkToken() method
if (Date.now() > user.expiresIn - 1000 * 120) {
  const infos = await Spotify.refresh(token);
  await storeInUser("_id", user._id, infos);
}
```

**Refresh Process:**
- Uses `refresh_token` grant type
- Sends client credentials via Basic Auth header
- Returns new `accessToken` and updated `expiresIn` timestamp
- Automatically updates database

**Background Polling:**
- Backend polls Spotify API every **120 seconds** (2 minutes)
- Fetches recently played tracks for data collection
- Token refresh happens seamlessly during polling

### User Reauthentication Requirements

#### ❌ Minimal Manual Reauthentication Required

**Normal Operation:**
- **No manual reauthentication needed** during regular use
- Tokens refresh automatically in the background
- Refresh tokens typically valid for **~60 days** (Spotify's default)

**Manual Reauthentication Required When:**
1. **User Revokes Access** on Spotify dashboard
2. **Refresh Token Expires** (after ~60 days of inactivity)
3. **Spotify App Credentials Change** (client secret rotated)

**Reauthentication Process:**
- Application displays error message
- User navigates to Settings → "Relog to Spotify" button
- Redirected through OAuth flow again
- New tokens issued

### Session Management

**JWT Token (for YourSpotify session):**
- Default validity: **1 hour** (configurable via `COOKIE_VALIDITY_MS`)
- Stored in HTTP-only cookie
- Independent from Spotify token expiration

**Cookie Configuration:**
```typescript
{
  sameSite: "strict",
  httpOnly: true,
  secure: true,           // When using HTTPS
  maxAge: COOKIE_VALIDITY_MS  // Default: "1h"
}
```

---

## 4. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     User's Browser                          │
└───────────────┬────────────────────────────────┬────────────┘
                │                                │
        1. Login Request                3. Auth Code
                │                                │
                ▼                                ▼
┌─────────────────────────┐        ┌─────────────────────────┐
│  YourSpotify Backend    │        │   Spotify OAuth Server  │
│  (Self-Hosted)          │◄───────┤   (accounts.spotify.com)│
│                         │ 2. Redirect               │
│  - Exchanges code       │        │                         │
│  - Stores tokens        │        └─────────────────────────┘
│  - Issues JWT session   │
│  - Auto-refreshes       │
│    every 120s           │
└───────────┬─────────────┘
            │
            ▼
    ┌──────────────────┐
    │    MongoDB       │
    │  User Tokens     │
    └──────────────────┘
```

---

## 5. Key Findings

### ✅ Advantages

1. **User Privacy**: Self-hosted, no central token storage
2. **Automatic Refresh**: Seamless background token renewal
3. **Minimal Intervention**: Users rarely need to reauthenticate manually
4. **Security**: CSRF protection, secure cookies, automatic token rotation
5. **Full Control**: Users own their Spotify API credentials

### ⚠️ Considerations

1. **Setup Complexity**: Users must create Spotify developer app
2. **User Management**: Need to register users in Spotify dashboard (production mode)
3. **Quota Limits**: Spotify enforces rate limits on developer apps
4. **Refresh Token Expiry**: Manual reauth needed after ~60 days of inactivity
5. **Single Point of Failure**: If Spotify app is deleted/suspended, all users lose access

---

## 6. Comparison: Developer App Models

| Aspect | YourSpotify (User-Created App) | Centralized App Model |
|--------|-------------------------------|----------------------|
| Setup Effort | High (create app, configure env vars) | Low (just login) |
| Privacy | Excellent (self-hosted tokens) | Poor (central server has tokens) |
| Rate Limits | Per-instance (dedicated quota) | Shared across all users |
| Reauthentication | Rare (~60 days) | Varies by implementation |
| User Control | Full control of credentials | Dependent on service provider |
| Spotify Compliance | ✅ Follows ToS | ⚠️ May violate ToS |

---

## 7. Documentation Quality

### Available Documentation

- **README.md**: Comprehensive setup guide with environment variables
- **LOCAL_INSTALL.md**: Non-Docker installation instructions
- **docker-compose-example.yml**: Configuration templates
- **apps/server/README.md**: API endpoint documentation

### Setup Instructions Clarity

- ✅ Clear step-by-step Spotify app creation process
- ✅ Environment variable reference table
- ✅ Redirect URI configuration examples
- ✅ Docker and non-Docker setup paths
- ⚠️ Could improve: Troubleshooting common OAuth errors

---

## 8. Recommendations

### For End Users

1. **Bookmark Spotify Developer Dashboard**: You'll need it for user management
2. **Document Your Credentials**: Store `SPOTIFY_PUBLIC` and `SPOTIFY_SECRET` securely
3. **Monitor Quota Usage**: Check Spotify dashboard for API rate limits
4. **Enable HTTPS**: Use secure cookies in production deployments
5. **Set Up Monitoring**: Alert if automatic polling fails (indicates auth issues)

### For Developers

1. **Consider Adding**:
   - Proactive refresh token renewal before 60-day expiry
   - User notification system for approaching token expiration
   - Health check endpoint showing token validity status
   - Better error messages for common OAuth failures

2. **Security Enhancements**:
   - Implement token encryption at rest in MongoDB
   - Add audit logging for authentication events
   - Consider PKCE extension for additional security

---

## Conclusion

YourSpotify requires users to create their own Spotify developer application, which increases initial setup complexity but provides superior privacy, control, and quota isolation. The automatic token refresh mechanism is well-implemented, requiring manual reauthentication only when users revoke access or after extended inactivity (~60 days). This architecture aligns well with self-hosted privacy-focused applications, though it may not be ideal for users seeking a turnkey solution.

**Reauthentication Frequency**: Rare (typically every 60+ days, or only when access is revoked)

**Developer App Requirement**: Yes (mandatory for deployment)
