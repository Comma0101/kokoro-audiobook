# Minimal Listening Loop Design

## Goal

Make the app feel like a complete audiobook product without adding heavy creation steps. The next milestone should improve the loop users actually repeat:

```text
Add content -> Create audiobook -> Listen -> Save offline -> Resume
```

## Product Decision

Do not add voice preview, content preview, document analysis, onboarding, sample audiobooks, or advanced cleanup controls in this version. Those ideas may be useful later, but they add workflow weight before the core listening experience feels finished.

## Scope

### Player Polish

The player is the product surface where users spend time. It should feel calm, clear, and audiobook-specific:

- Keep the current transcript/cue experience.
- Add clearer playback controls around the native audio element.
- Show current chapter context.
- Keep speed controls.
- Keep Save Offline visible when the server copy exists and the book is not saved locally.
- Avoid decorative or marketing-style player UI.

### Resume Listening

Store playback progress locally on the device. This fits the current local-first direction and avoids backend/database complexity.

- Save current chapter and current playback time per book.
- Restore that position when the user opens the book again.
- Show `Continue` instead of `Play` when progress exists.
- Show a small progress line on the Library card.

### Library Actions

Library cards should be action-oriented, not just decorative:

- Ready with no progress: `Play`.
- Ready with progress: `Continue`.
- Processing: `View status`.
- Failed: `Try again`.
- Saved locally remains secondary metadata.

### Generation Status

Keep generation feedback simple and useful:

- `Queued`
- `Creating audiobook`
- `Chapter 4 of 12` when chapter progress exists
- `Ready`
- `Failed`

Avoid a heavy progress dashboard for now.

### Error Recovery

Failed jobs should explain the likely problem and give a path forward:

- PDF/text extraction failure: suggest TXT, DOCX, or paste text.
- URL failure: suggest pasting text.
- Generic failure: suggest trying another file or pasting text.

## Non-Goals

- Voice preview.
- Content analysis/preview.
- Sample audiobook.
- Browser notifications.
- Sort/filter systems beyond current search.
- Backend resume sync.
- Multi-step wizard.

## Success Criteria

- A user can open a generated audiobook, listen, leave, and return to continue from the same place.
- Library cards clearly communicate the next action.
- Failed or processing books are understandable at a glance.
- The app still feels minimal and direct.

