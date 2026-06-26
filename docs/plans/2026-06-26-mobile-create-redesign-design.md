# Mobile Create Redesign Design

## Goal

Make the Create page feel designed for phone users instead of a desktop form stacked vertically.

## Product Decision

Keep the existing creation capabilities and default to `Upload File`. Do not add voice preview, content preview, analysis, onboarding, or new libraries. The redesign should reduce scroll, keep the main action visible, and make Paste Text and Article URL one tap away.

## Mobile UX Direction

On mobile, the Create page should become a compact creation surface:

- Short page title and copy.
- Horizontal segmented input selector: `Upload`, `Paste`, `URL`.
- One visible input panel at a time.
- Shorter upload dropzone, optimized for tapping rather than drag-and-drop.
- Compact selected-file row with replace/remove actions.
- Narration settings collapsed by default into a summary row.
- Sticky bottom Create button on mobile only.

Desktop can keep the current roomy card layout, with minor class hooks shared by mobile.

## Interaction Details

The collapsed narration summary should show the current voice, speed, and natural-number setting. Tapping it expands the same existing voice/speed/checkbox controls. No settings are removed.

The sticky mobile CTA should submit the same form and use the existing `canSubmit()` disabled logic. On desktop, the normal inline button remains.

## Non-Goals

- Backend changes.
- New routing.
- Multi-step wizard.
- Preview/analyze flow.
- Voice preview.
- New component library.

## Success Criteria

- On a phone, users can see the input selector and main input quickly.
- The primary action is always easy to reach.
- Existing desktop layout remains polished.
- Existing create, upload, paste, URL, narration, and validation behavior remains intact.
