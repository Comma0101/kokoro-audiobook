# Accurate Local Resume Design

## Goal

Make `Continue Listening` return users to the place they actually left, while keeping the implementation browser-local and simple.

## Product Decision

Keep resume state on the current device only. Do not add backend progress sync, database migrations, analytics, or a custom audio engine for this version.

## Approach

Improve the existing localStorage resume model rather than replacing it:

- Save progress on more player lifecycle events: playback time updates, pause, seek completion, player close, page hide, and tab visibility changes.
- Store a richer but still small position object with a version, chapter index, chapter audio filename, current time, and update timestamp.
- Restore by matching the saved chapter audio filename first, then fall back to the saved chapter index.
- Seek after audio metadata loads, and retry the same seek once when the audio can play.
- Resume a few seconds before the exact saved timestamp so users regain context.
- Show a clearer Library label such as `Continue from Chapter 4 · 12:31`.

## Non-Goals

- Cross-device resume.
- Server-side playback position.
- Voice preview.
- Content preview or document analysis.
- New player library.
- Full custom waveform or timeline.

## Success Criteria

- Leaving by closing the player, pausing, seeking, switching tabs, or closing the page records a recent playback position.
- Reopening a book restores the right chapter and timestamp reliably.
- Library cards communicate where `Continue Listening` will resume.
- The code remains a small extension of the current Alpine player.
