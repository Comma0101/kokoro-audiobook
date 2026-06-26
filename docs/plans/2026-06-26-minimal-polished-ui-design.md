# Minimal Polished UI Design

## Goal

Make the audiobook web app feel more polished and app-like while keeping the current low-complexity frontend architecture.

## Decision

Keep the current frontend stack:

- Alpine.js for browser-side state and interactions.
- Tailwind CDN for utility styling.
- Static HTML/CSS/JS served by FastAPI.
- Existing service worker and Cache Storage behavior.
- No React, Vue, Svelte, npm build step, or native wrapper for this version.

## Product Direction

The UI should feel like a quiet audiobook app, not a decorative landing page or heavy dashboard. It should prioritize repeat use on phone:

- Create a book.
- See generation status.
- Save offline.
- Open player.
- Resume listening.

The interface should remain minimal, but with clearer hierarchy, calmer labels, stronger offline states, and larger touch targets.

## Screen Design

### Create

Keep one creation surface with URL, file, or text input. Reduce explanatory copy and make the submit button direct. Use plain labels and consistent input spacing.

### Library

Make the Library the primary home screen after login. Each book should show:

- Title.
- Duration when available.
- Status: `Generating`, `Ready to Save`, `Saving`, `Saved on This Device`, `Expired`, or `Failed`.
- One obvious action: `Save Offline`, `Play`, or `Regenerate/Delete` depending on state.

The current generated cover style can remain if toned down. It should not compete with status and actions.

### Player

Keep the synced cue reading experience as the main value. Improve:

- Larger, cleaner bottom controls.
- Clear chapter selector.
- A visible `Save Offline` prompt when the active book is not saved.
- Readable text with less visual noise.
- Simple status text showing whether the book is stored on this device.

## Offline Guidance

The app should clearly explain local storage without adding a tutorial:

- Use `Save Offline to This Device` where space allows.
- Show `Stored on this device` after verification.
- Avoid implying cross-device sync.
- If server copy expired but local cache exists, still allow playback.

## Service Worker Update Policy

When UI changes ship, bump the app shell cache version in `audiobook/static/sw.js` so users receive the refreshed interface instead of stale cached HTML.

## Out of Scope

- Replacing Alpine with React/Vue/Svelte.
- Componentizing into a build system.
- Native mobile wrapper.
- IndexedDB media blobs.
- Full redesign of auth.
