# UI/UX Redundancy Cleanup Design

## Goal

Reduce duplicate UI surfaces and redundant copy while preserving the current Create, Library, Player, offline, and resume workflows.

## Scope

Remove UI that repeats information already shown elsewhere or adds maintenance weight without improving the user journey:

- Delete the dead `noscript` narration settings fallback.
- Remove cover-level status text because the card already has a status badge.
- Remove the Profile playback speed preference because the Player already controls and persists speed.
- Simplify offline card actions: use the badge for saved/offline status and make the secondary action remove the offline copy.
- Keep Create mobile tabs, sticky CTA behavior, Library search, failed recovery, resume labels, player controls, and offline helper copy.

## Non-Goals

- No backend changes.
- No new components or libraries.
- No auth changes.
- No player redesign.
- No upload flow changes.

## Success Criteria

- Fewer duplicate status/action surfaces.
- Same workflows remain available.
- UI tests assert the removed surfaces stay removed.
- Service worker cache is bumped so users receive the cleaned app shell.
