# US-Market Audiobook Redesign Design

## Goal

Redesign the app into a clean US-market audiobook creation platform. The app should communicate that users can upload a document, paste text, or provide an article URL, then turn that content into natural narration.

## Direction

Keep the existing Alpine and Tailwind CDN frontend. Do not introduce React, Vue, a build step, or a component framework for this version. The redesign should feel like a premium minimal SaaS/editorial tool, not a decorative library.

## Brand

- Remove all Chinese visual elements, including glyphs, brush fonts, CJK font fallback, and decorative seal marks.
- Use a simple wordmark with a universal book/audio icon built from inline SVG.
- Keep the product name as `Audiobook`.
- Use warm neutral colors, dark text, subtle borders, and a restrained green accent.

## Create Flow

The Create page becomes the primary workflow:

- Centered container around 720-860px.
- Title: `Create an audiobook`.
- Subtitle: `Upload a document, paste text, or add an article URL. We’ll turn it into natural narration.`
- Input method tabs: `Article URL`, `Upload File`, `Paste Text`.
- Show only the active input method.
- Default to `Upload File`.
- File upload uses a keyboard-accessible drag/drop-style area backed by the existing file input.
- Paste text shows a character count and rough estimated audio length.
- Article URL shows a simple ready hint when filled.

## Narration Settings

Use a compact settings card:

- Friendly voice names mapped to existing backend voice IDs.
- Speed as segmented choices: `0.8x`, `1.0x`, `1.2x`, `1.5x`.
- Copy: `Read numbers and currency naturally`.
- Include disabled visual placeholders for future options only if they do not create fake enabled behavior.

## Submit Feedback

The primary button says `Create Audiobook`. While submitting it says `Creating audiobook...` and an inline progress card lists the creation stages. This is a frontend status surface only; backend job progress still appears from polling on the Library cards.

## Library

Library becomes a clean responsive card grid:

- Heading: `Library`.
- Subcopy: `Your generated audiobooks.`
- Action: `+ New Audiobook`.
- Search input filters visible cards client-side.
- Empty state says `No audiobooks yet` and guides the user to create the first audiobook.
- Cards show cover, title, source/status, duration, size, device state, and a clear action.
- Remove old-world copy such as `volume` and `shelf`.
- Do not show piracy-associated sample/source text in UI copy.

## Covers

Covers remain deterministic CSS generated in the browser, so no new image generation or asset storage is required. The new cover style uses:

- Soft modern gradients.
- A small waveform mark.
- Clean title typography.
- No stamp/seal, CJK symbols, or unexplained numeric badges.

## Accessibility

- Keep labels as real labels, not placeholders.
- Ensure focus states are visible.
- Use at least 44px-tall primary clickable controls where reasonable.
- Keep disabled/loading states visually distinct.
- Make upload control keyboard-accessible.

## Testing

Add static UI tests that verify:

- CJK/brush/seal identity has been removed.
- New product copy exists.
- Create tabs and upload dropzone are present.
- Friendly voice labels and segmented speeds are present.
- Library copy, search, status badges, and new card classes exist.
- Service worker cache version is bumped.

