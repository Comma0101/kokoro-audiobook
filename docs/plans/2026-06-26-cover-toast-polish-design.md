# Cover and Offline Toast Polish Design

## Goal

Make the generated covers and offline-save feedback feel more polished while keeping the app simple and frontend-only.

## Decisions

- Keep covers generated in the browser with deterministic CSS from the title.
- Do not generate, upload, download, or store cover image files.
- Keep the current Alpine/Tailwind/static PWA stack.
- Replace blocking browser alerts for successful offline saves with an in-app toast.
- Keep browser alerts only for exceptional errors or destructive confirmation.

## Cover Direction

Covers should read as quiet audiobook cards:

- Cleaner background gradients with a paper-like base.
- More intentional title placement.
- A subtle book depth/spine effect.
- Smaller and calmer seal treatment.
- A status badge on the cover for local/save state: `LOCAL`, `READY`, or `EXPIRED`.

The cover remains deterministic: the same title always gets the same style.

## Offline Toast

After verified local cache save, show an in-app toast:

- Title: `Stored on this device`
- Detail: `15h 15m saved locally` when duration exists.
- Verification detail: `All audio and cues verified.`

The toast should be non-blocking and auto-dismiss. It should not use `alert()` for normal success.

## Out of Scope

- Real image cover generation.
- Backend cover metadata.
- IndexedDB or filesystem storage.
- Replacing Alpine/Tailwind.
