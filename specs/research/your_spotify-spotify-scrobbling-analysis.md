# Spotify Scrobbling Analysis

This document provides a comprehensive analysis of how the Your Spotify application implements Spotify scrobbling functionality.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Spotify API Endpoints](#spotify-api-endpoints)
- [Request Timing & Scheduling](#request-timing--scheduling)
- [Data Storage](#data-storage)
- [Code Flow](#code-flow)
- [Key Implementation Details](#key-implementation-details)

---

## Overview

Your Spotify implements a continuous scrobbling system that polls the Spotify API every 2 minutes to fetch recently played tracks for all registered users. The scrobbled data is stored in MongoDB with comprehensive metadata about tracks, albums, and artists.

**Core Components:**
- **Backend Polling Loop** (`apps/server/src/spotify/looper.ts`)
- **Metadata Fetching** (`apps/server/src/spotify/dbTools.ts`)
- **API Wrapper** (`apps/server/src/tools/apis/spotifyApi.ts`)
- **Request Queue** (`apps/server/src/tools/queue.ts`)
- **Database Schemas** (`apps/server/src/database/schemas/`)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    SERVER STARTUP                            │
│  (apps/server/src/bin/www.ts)                               │
│                       │                                      │
│                       ├──> Initialize MongoDB               │
│                       ├──> Start Express Server             │
│                       └──> Start dbLoop()                   │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    SCROBBLING LOOP                           │
│  (apps/server/src/spotify/looper.ts:dbLoop)                 │
│                                                              │
│  while (true) {                                             │
│    ┌─────────────────────────────────────────┐            │
│    │ For each user in database:              │            │
│    │   ├──> Call loop(user)                  │            │
│    │   └──> Catch & log errors               │            │
│    └─────────────────────────────────────────┘            │
│    await wait(120 seconds)                                 │
│  }                                                          │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│              PER-USER SCROBBLING (loop function)             │
│  (apps/server/src/spotify/looper.ts:loop)                   │
│                                                              │
│  1. Build API URL with lookback timestamp                  │
│     /me/player/recently-played?after={timestamp - 2 hours} │
│                                                              │
│  2. Fetch all pages of recently played tracks              │
│     while (nextUrl) {                                       │
│       response = spotifyApi.raw(nextUrl)                   │
│       items.push(...response.data.items)                   │
│       nextUrl = response.data.next                         │
│     }                                                       │
│                                                              │
│  3. Get track/album/artist metadata                        │
│     getTracksAlbumsArtists(userId, spotifyTracks)          │
│                                                              │
│  4. Filter duplicates (±30 seconds)                        │
│     getCloseTrackId(userId, trackId, date, 30)             │
│                                                              │
│  5. Build Infos records with played_at timestamps          │
│                                                              │
│  6. Store everything to database                           │
│     storeIterationOfLoop(...)                              │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│              METADATA FETCHING & STORAGE                     │
│  (apps/server/src/spotify/dbTools.ts)                       │
│                                                              │
│  getTracksAlbumsArtists():                                  │
│  1. Check which tracks already exist in DB                 │
│  2. Fetch missing tracks:                                  │
│     GET /tracks?ids={id1,id2,...}  (max 50 at once)       │
│  3. Extract album/artist IDs from tracks                   │
│  4. Fetch missing albums:                                  │
│     GET /albums?ids={id1,id2,...}  (max 20 at once)       │
│  5. Fetch missing artists:                                 │
│     GET /artists?ids={id1,id2,...} (max 50 at once)       │
│                                                              │
│  storeIterationOfLoop():                                    │
│  1. Acquire database write lock                            │
│  2. Insert new Track/Album/Artist records                  │
│  3. Create Infos records (scrobbles)                       │
│  4. Update user.lastTimestamp                              │
│  5. Update user.firstListenedAt if earlier                 │
│  6. Release database lock                                  │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    REQUEST QUEUE                             │
│  (apps/server/src/tools/queue.ts)                          │
│                                                              │
│  All Spotify API calls go through PromiseQueue:            │
│  - Serializes requests (one at a time)                     │
│  - Adds 1-second delay between requests                    │
│  - Prevents rate limiting                                  │
│  - Auto-refreshes access tokens if needed                  │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                     MONGODB STORAGE                          │
│                                                              │
│  Collections:                                               │
│  ├─ users      (user info, tokens, lastTimestamp)          │
│  ├─ infos      (scrobbles: track plays with timestamps)    │
│  ├─ tracks     (track metadata)                            │
│  ├─ albums     (album metadata)                            │
│  └─ artists    (artist metadata)                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Spotify API Endpoints

### Primary Scrobbling Endpoint

**Location:** `apps/server/src/spotify/looper.ts:25-27`

```typescript
const url = `/me/player/recently-played?after=${
  user.lastTimestamp - 1000 * 60 * 60 * 2
}`;
```

**Endpoint:** `GET https://api.spotify.com/v1/me/player/recently-played`

**Parameters:**
- `after` - Unix timestamp in milliseconds
- Lookback window: 2 hours before the last recorded timestamp

**Pagination:**
- Response includes `data.next` URL for next page
- Loop continues until `nextUrl` is null

**Response Structure:**
```typescript
{
  items: [
    {
      track: SpotifyTrack,
      played_at: "2024-01-18T12:34:56.789Z"
    },
    ...
  ],
  next: "url-to-next-page" | null
}
```

### Metadata Endpoints

**Location:** `apps/server/src/spotify/dbTools.ts`

#### 1. Get Tracks (Batch)
```
GET https://api.spotify.com/v1/tracks?ids={id1,id2,...}
```
- **Max IDs per request:** 50
- **Implementation:** Lines 51-75
- **Usage:** Fetch full track metadata for missing tracks

#### 2. Get Albums (Batch)
```
GET https://api.spotify.com/v1/albums?ids={id1,id2,...}
```
- **Max IDs per request:** 20
- **Implementation:** Lines 77-101
- **Usage:** Fetch album metadata

#### 3. Get Artists (Batch)
```
GET https://api.spotify.com/v1/artists?ids={id1,id2,...}
```
- **Max IDs per request:** 50
- **Implementation:** Lines 103-120
- **Usage:** Fetch artist metadata

### Additional Endpoints

**Location:** `apps/server/src/tools/apis/spotifyApi.ts`

- `GET /me` - Get current user information (line 82-88)
- `PUT /me/player/play` - Play a track (line 73-80)
- `GET /me/playlists` - List user playlists (line 90-105)
- `POST /playlists/{id}/tracks` - Add tracks to playlist (line 107-121)
- `POST /users/{spotifyId}/playlists` - Create playlist (line 130-144)
- `GET /search?q=track:{track}+artist:{artist}&type=track` - Search tracks (line 155-176)

---

## Request Timing & Scheduling

### Main Polling Loop

**Location:** `apps/server/src/spotify/looper.ts:99-135`

**Polling Interval:**
```typescript
const WAIT_MS = 120 * 1000;  // 120 seconds = 2 minutes
```

**Loop Behavior:**
```typescript
while (true) {
  // Process all users
  for (let i = 0; i < nbUsers; i += 1) {
    const users = await getUser(i);
    for (const us of users) {
      await loop(us);  // Sequential processing
    }
  }
  await wait(WAIT_MS);  // Wait 2 minutes before next iteration
}
```

**Key Characteristics:**
- Runs indefinitely on server startup
- Processes users sequentially (not in parallel)
- Waits 2 minutes between complete cycles
- Catches errors per-user without stopping the loop
- Exits on MongoDB connection failure

### Request Queue

**Location:** `apps/server/src/tools/queue.ts`

**Implementation:** `PromiseQueue` class

```typescript
execQueue = async () => {
  while (this.q.length > 0) {
    const item = this.q[0];
    const data = await item.fn();
    item.onResolve(data);
    await wait(1000);  // 1-second delay between requests
    this.q.shift();
  }
}
```

**Features:**
- All Spotify API calls are serialized (one at a time)
- 1-second delay between consecutive requests
- Prevents rate limiting
- Global queue shared across all API calls (`squeue` in `spotifyApi.ts:10`)

### Token Refresh

**Location:** `apps/server/src/tools/apis/spotifyApi.ts:31-62`

**Timing:**
```typescript
if (Date.now() > user.expiresIn - 1000 * 120) {
  // Refresh if token expires within 2 minutes
  const infos = await Spotify.refresh(user.refreshToken);
  await storeInUser("_id", user._id, infos);
}
```

**Characteristics:**
- Checked before every API request
- Refreshes proactively (2 minutes before expiry)
- Uses OAuth refresh token flow
- Updates stored access token in database

### Retry Mechanism

**Location:** `apps/server/src/spotify/looper.ts:34-39`

```typescript
const response = await retryPromise(
  () => spotifyApi.raw(nextUrl),
  10,   // Max retries
  30,   // Delay between retries (seconds)
);
```

**Features:**
- Retries failed requests up to 10 times
- 30-second delay between retries
- Used for fetching recently-played tracks and metadata

### Batch Processing

**Location:** `apps/server/src/spotify/dbTools.ts:18-49`

When fetching metadata for multiple IDs:
```typescript
// Split IDs into chunks based on API limits
const chunkNb = Math.ceil(ids.length / max);
for (let i = 0; i < chunkNb; i += 1) {
  const id = idsArray[i];
  const builtUrl = `${url}?ids=${id.join(",")}`;
  const { data } = await retryPromise(() => spotifyApi.raw(builtUrl), 10, 30);
  datas.push(...data[arrayPath]);
}
```

**Processing is sequential within loop** (intentional to avoid rate limits)

---

## Data Storage

### Database Schema

**Technology:** MongoDB with Mongoose ODM

### Collections & Schemas

#### 1. Infos Collection (Scrobbles)

**Location:** `apps/server/src/database/schemas/info.ts`

**Purpose:** Stores individual track plays with timestamps

```typescript
{
  owner: ObjectId,              // Reference to User
  id: String,                   // Spotify track ID (indexed)
  albumId: String,              // Spotify album ID (indexed)
  primaryArtistId: String,      // Primary artist ID (indexed)
  artistIds: [String],          // All artist IDs for this track
  durationMs: Number,           // Track duration in milliseconds
  played_at: Date,              // When track was played (indexed)
  blacklistedBy?: "artist"      // Optional blacklist flag
}
```

**Virtual Fields:**
- `track` - Populated from Track collection (id → id)
- `album` - Populated from Album collection (albumId → id)
- `artist` - Populated from Artist collection (primaryArtistId → id)

**Indexes:**
- `id` (track ID)
- `albumId`
- `primaryArtistId`
- `played_at`

#### 2. Track Collection

**Location:** `apps/server/src/database/schemas/track.ts`

```typescript
{
  id: String,                   // Spotify track ID (unique)
  name: String,                 // Track name
  album: String,                // Album ID reference
  artists: [String],            // Artist ID references
  duration_ms: Number,
  popularity: Number,
  external_ids: Object,         // ISRC, etc.
  external_urls: Object,        // Spotify URLs
  preview_url: String,
  // ... other Spotify track metadata
}
```

#### 3. Album Collection

**Location:** `apps/server/src/database/schemas/album.ts`

```typescript
{
  id: String,                   // Spotify album ID (unique)
  name: String,                 // Album name
  artists: [String],            // Artist ID references
  release_date: Date,
  release_date_precision: String,
  total_tracks: Number,
  album_type: String,           // album, single, compilation
  images: [Object],             // Cover art URLs
  external_urls: Object,
  // ... other album metadata
}
```

#### 4. Artist Collection

**Location:** `apps/server/src/database/schemas/artist.ts`

```typescript
{
  id: String,                   // Spotify artist ID (unique)
  name: String,                 // Artist name
  genres: [String],             // Genre tags
  popularity: Number,
  followers: Object,
  images: [Object],             // Artist images
  external_urls: Object,
  // ... other artist metadata
}
```

#### 5. User Collection

**Location:** `apps/server/src/database/schemas/user.ts`

```typescript
{
  username: String,
  spotifyId: String,            // Spotify user ID
  accessToken: String,
  refreshToken: String,
  expiresIn: Number,            // Token expiry timestamp

  lastTimestamp: Number,        // Last scrobble fetch timestamp
  firstListenedAt: Date,        // Earliest recorded play date

  settings: {
    blacklistedArtists: [String],
    // ... other user settings
  },

  // ... other user data
}
```

### Storage Flow

**Location:** `apps/server/src/spotify/dbTools.ts:208-240`

```typescript
async function storeIterationOfLoop(
  userId: string,
  iterationTimestamp: number,
  tracks: Track[],
  albums: Album[],
  artists: Artist[],
  infos: Omit<Infos, "owner">[],
) {
  await longWriteDbLock.lock();  // Prevent concurrent writes

  // 1. Store metadata (only new records)
  await storeTrackAlbumArtist({ tracks, albums, artists });

  // 2. Create Infos (scrobble) records
  await addTrackIdsToUser(userId, infos);

  // 3. Update user's last timestamp
  await storeInUser("_id", userId, {
    lastTimestamp: iterationTimestamp,
  });

  // 4. Update firstListenedAt if this is earlier
  const minPlayedAt = minOfArray(infos, item => item.played_at);
  if (minPlayedAt) {
    await storeFirstListenedAtIfLess(userId, minPlayedAt);
  }

  longWriteDbLock.unlock();
}
```

### Duplicate Prevention

**Location:** `apps/server/src/spotify/looper.ts:61-67`

```typescript
const duplicate = await getCloseTrackId(
  user._id.toString(),
  item.track.id,
  date,
  30,  // ±30 seconds tolerance
);
if (duplicate.length === 0) {
  // Store this play
}
```

**Logic:**
- Checks for same track played within ±30 seconds
- Prevents duplicate scrobbles from API overlaps
- Uses database query with date range

### Artist Blacklisting

**Location:** `apps/server/src/spotify/looper.ts:68-82`

```typescript
const isBlacklisted = user.settings.blacklistedArtists.find(
  a => a === item.track.artists[0]?.id,
);
infos.push({
  // ... other fields
  ...(isBlacklisted ? { blacklistedBy: "artist" } : {}),
});
```

**Features:**
- Marks scrobbles from blacklisted artists
- Still stores the play but marks it
- Can be filtered out in queries

### Metadata Deduplication

**Location:** `apps/server/src/spotify/dbTools.ts:135-186`

```typescript
// Only fetch tracks that don't exist in DB
const storedTracks = await TrackModel.find({ id: { $in: ids } });
const missingTrackIds = ids.filter(
  id => !storedTracks.find(stored => stored.id === id)
);

// Same for albums and artists
const storedAlbums = await AlbumModel.find({ id: { $in: relatedAlbums } });
const missingAlbumIds = relatedAlbums.filter(...);

const storedArtists = await ArtistModel.find({ id: { $in: relatedArtists } });
const missingArtistIds = relatedArtists.filter(...);
```

**Characteristics:**
- Checks database before API calls
- Only fetches missing metadata
- Reduces Spotify API usage
- Stores unique records (using `uniqBy` helper)

---

## Code Flow

### 1. Server Startup

**Location:** `apps/server/src/bin/www.ts`

```typescript
// After Express server starts
import { dbLoop } from "../spotify/looper";
dbLoop();  // Start infinite scrobbling loop
```

### 2. Main Loop Iteration

**Function:** `dbLoop()` in `apps/server/src/spotify/looper.ts:101-135`

**Steps:**
1. Get user count from database
2. Iterate through all users (batched)
3. For each user, call `loop(user)`
4. Catch and log any errors (per user)
5. Wait 120 seconds
6. Repeat

### 3. Per-User Scrobbling

**Function:** `loop(user)` in `apps/server/src/spotify/looper.ts:15-97`

**Steps:**

1. **Build API URL** (line 25-27)
   ```typescript
   const url = `/me/player/recently-played?after=${
     user.lastTimestamp - 1000 * 60 * 60 * 2
   }`;
   ```

2. **Fetch all pages** (line 30-43)
   ```typescript
   const items: RecentlyPlayedTrack[] = [];
   let nextUrl = url;
   do {
     const response = await spotifyApi.raw(nextUrl);
     items.push(...response.data.items);
     nextUrl = response.data.next;
   } while (nextUrl);
   ```

3. **Extract tracks** (line 52)
   ```typescript
   const spotifyTracks = items.map(e => e.track);
   ```

4. **Fetch metadata** (line 53-56)
   ```typescript
   const { tracks, albums, artists } = await getTracksAlbumsArtists(
     user._id.toString(),
     spotifyTracks,
   );
   ```

5. **Build Infos records** (line 58-85)
   - Filter duplicates (±30 second window)
   - Check artist blacklist
   - Create Infos objects with `played_at` timestamps

6. **Store to database** (line 86-93)
   ```typescript
   await storeIterationOfLoop(
     user._id.toString(),
     lastTimestamp,
     tracks,
     albums,
     artists,
     infos,
   );
   ```

### 4. Metadata Fetching

**Function:** `getTracksAlbumsArtists()` in `apps/server/src/spotify/dbTools.ts:135-186`

**Steps:**

1. **Check existing tracks** (line 140-143)
   ```typescript
   const storedTracks = await TrackModel.find({ id: { $in: ids } });
   const missingTrackIds = ids.filter(
     id => !storedTracks.find(stored => stored.id === id)
   );
   ```

2. **Fetch missing tracks** (line 154-158)
   ```typescript
   const { tracks, artists, albums } =
     await getTracksAndRelatedAlbumArtists(userId, missingTrackIds);
   ```

3. **Extract related IDs** (line 154-158)
   - Get album IDs from tracks
   - Get artist IDs from tracks

4. **Check existing albums/artists** (line 160-172)
   - Query database for existing records
   - Filter to missing IDs

5. **Fetch missing albums/artists** (line 174-179)
   ```typescript
   const albums = missingAlbumIds.length > 0
     ? await getAlbums(userId, missingAlbumIds)
     : [];
   const artists = missingArtistIds.length > 0
     ? await getArtists(userId, missingArtistIds)
     : [];
   ```

6. **Return all metadata**

### 5. Database Storage

**Function:** `storeIterationOfLoop()` in `apps/server/src/spotify/dbTools.ts:208-240`

**Steps:**

1. **Acquire lock** (line 216)
   ```typescript
   await longWriteDbLock.lock();
   ```

2. **Store metadata** (line 218-222)
   ```typescript
   await storeTrackAlbumArtist({ tracks, albums, artists });
   // Creates Track, Album, Artist documents
   ```

3. **Create scrobbles** (line 224)
   ```typescript
   await addTrackIdsToUser(userId, infos);
   // Creates Infos documents with played_at timestamps
   ```

4. **Update user timestamp** (line 226-228)
   ```typescript
   await storeInUser("_id", userId, {
     lastTimestamp: iterationTimestamp,
   });
   ```

5. **Update first listen date** (line 230-237)
   ```typescript
   const min = minOfArray(infos, item => item.played_at);
   if (min) {
     await storeFirstListenedAtIfLess(userId, minInfo);
   }
   ```

6. **Release lock** (line 239)
   ```typescript
   longWriteDbLock.unlock();
   ```

---

## Key Implementation Details

### 1. Lookback Window Strategy

**Why 2 hours?**
```typescript
user.lastTimestamp - 1000 * 60 * 60 * 2
```

- Spotify's recently-played endpoint has limits on how far back it can look
- Using 2-hour lookback ensures no data loss between polling cycles
- Provides overlap buffer for reliability
- Duplicate detection handles overlapping plays

### 2. Sequential User Processing

```typescript
for (let i = 0; i < nbUsers; i += 1) {
  const users = await getUser(i);
  for (const us of users) {
    await loop(us);  // Sequential, not parallel
  }
}
```

**Why sequential?**
- Respects API rate limits
- Uses shared request queue
- Prevents overwhelming Spotify API
- Simpler error handling

### 3. Request Queue Design

**Why a global queue?**
```typescript
export const squeue = new PromiseQueue();  // Singleton
```

- Serializes all Spotify API requests
- Prevents concurrent requests from different users
- 1-second delay prevents rate limiting
- Simpler than complex rate limiting logic

### 4. Database Locking

```typescript
await longWriteDbLock.lock();
// ... database operations
longWriteDbLock.unlock();
```

**Purpose:**
- Prevents concurrent writes from multiple user loops
- Ensures atomic updates to user records
- Prevents race conditions on timestamp updates

### 5. Metrics Tracking

**Location:** `apps/server/src/spotify/dbTools.ts`

```typescript
Metrics.ingestedTracksTotal.inc({ user: userId }, tracks.length);
Metrics.ingestedAlbumsTotal.inc({ user: userId }, albums.length);
Metrics.ingestedArtistsTotal.inc({ user: userId }, artists.length);
```

**Tracks:**
- Number of new tracks/albums/artists ingested per user
- Useful for monitoring and debugging

### 6. Error Handling

**Per-user error catching:**
```typescript
try {
  await loop(us);
} catch (error) {
  logger.error(`[${us.username}]: Error during refresh`, error);
  // Continue to next user
}
```

**Global error handling:**
```typescript
if (error instanceof MongoServerSelectionError) {
  logger.error("Exiting because mongo is unreachable");
  process.exit(1);  // Fatal error - exit process
}
```

### 7. Token Management

**Proactive refresh:**
- Checks token before every request
- Refreshes 2 minutes before expiry
- Stores new token immediately
- No request failures due to expired tokens

### 8. Pagination Handling

```typescript
let nextUrl = url;
do {
  const response = await spotifyApi.raw(nextUrl);
  items.push(...response.data.items);
  nextUrl = response.data.next;
} while (nextUrl);
```

**Features:**
- Handles paginated responses automatically
- Fetches all pages until `next` is null
- Accumulates all items before processing

---

## Summary

Your Spotify's scrobbling system is a well-architected continuous polling system that:

1. **Polls every 2 minutes** for all users sequentially
2. **Uses Spotify's recently-played endpoint** with 2-hour lookback
3. **Fetches comprehensive metadata** (tracks, albums, artists) in batches
4. **Queues all API requests** with 1-second delays to respect rate limits
5. **Stores data in MongoDB** with normalized collections and indexes
6. **Prevents duplicates** using ±30 second window detection
7. **Handles errors gracefully** with retries and per-user isolation
8. **Manages tokens proactively** to prevent expiration issues

The system balances reliability, API efficiency, and data integrity through careful design of timing, queuing, and storage mechanisms.
