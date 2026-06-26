# Local Offline Audio Retention Design

## Goal

Keep large audiobook audio files on the user's local device for this version without adding native storage, cross-device sync, or a new client-side database.

## Decision

Continue storing offline MP3 and cues files in the browser Cache Storage API. The app should guide the user to tap **Save Offline** after generation, verify the local cache contains every chapter file, then shorten the server-side retention window.

## User-Facing Behavior

- Newly generated books are available on the server for 72 hours by default.
- The Library and Player should make **Save Offline** easy to notice.
- When the user taps **Save Offline**, the browser downloads all chapter MP3 and cues JSON files into the current device's Cache Storage.
- After all files are verified in local cache, the book is shown as **Saved on This Device**.
- Once saved locally, the server copy should expire faster: 1 hour after successful local save.
- If the server copy expires but local files are still cached, the book should remain playable on that device.
- If both the server copy and local cache are unavailable, the app should tell the user to regenerate the book.

## Server Behavior

The server remains the generator and temporary distributor. It keeps output files under `out/{book_id}/` and tracks metadata in SQLite. The `/api/books/{book_id}/local-saved` endpoint marks that the current user saved the book locally and updates `server_expires_at` to 1 hour from now.

## Client Behavior

The client remains simple:

- Use Cache Storage for large MP3 and cues files.
- Use the existing cache name format: `audiobook-media-user-{user_id}`.
- Cache media using path keys like `/api/books/{book_id}/audio/{filename}` and `/api/books/{book_id}/cues/{filename}`.
- Verify every expected cache key exists after download.
- Show progress while saving.
- Do not add IndexedDB blobs, native wrappers, or cross-device sync for this version.

## Trade-Offs

Cache Storage is browser-managed and can theoretically be evicted. This is acceptable for this version because it keeps the project small and matches the current PWA architecture. The UI should be honest that saving is per-device and should verify cache presence before claiming the book is offline.
