import json
from pathlib import Path

ROOT = Path(__file__).parent
INDEX = (ROOT / "audiobook" / "static" / "index.html").read_text(encoding="utf-8")
SW = (ROOT / "audiobook" / "static" / "sw.js").read_text(encoding="utf-8")
MANIFEST = json.loads((ROOT / "audiobook" / "static" / "manifest.webmanifest").read_text(encoding="utf-8"))


def test_offline_copy_is_device_specific():
    assert "Save Offline to This Device" in INDEX
    assert "Saved offline on this device" in INDEX


def test_library_uses_clear_ready_state():
    assert "Ready to Save" in INDEX
    assert "Saved offline on this device" in INDEX
    assert "Server Copy Expired" in INDEX


def test_player_has_offline_status_surface():
    assert "activeJobOfflineLabel" in INDEX
    assert "Save offline on this device." in INDEX
    assert "For the most reliable offline listening, add Audiobook to your Home Screen." in INDEX


def test_offline_success_uses_in_app_toast():
    assert "toast: null" in INDEX
    assert "showToast(" in INDEX
    assert "Saved offline on this device" in INDEX
    assert "All audio and cues verified." in INDEX


def test_cover_keeps_generated_art_without_duplicate_status():
    assert "cover-waveform" in INDEX
    assert "coverStatusLabel(job)" not in INDEX
    assert "cover-status" not in INDEX


def test_redundant_ui_surfaces_removed():
    forbidden = [
        "voiceSelectNoScript",
        "<noscript>",
        "Default Playback Speed",
        "Preferences",
        "create-submit-inline",
    ]
    for text in forbidden:
        assert text not in INDEX
    assert "Remove Offline Copy" in INDEX
    assert INDEX.count('type="submit"') == 1


def test_us_market_branding_removed_cjk_identity():
    forbidden = [
        "font-brush",
        "Zhi Mang Xing",
        "Noto Serif SC",
        "書",
        "藏",
        "sealChar",
        "text-seal",
    ]
    for token in forbidden:
        assert token not in INDEX


def test_create_flow_is_tabbed_and_plain_language():
    for text in [
        "Create an audiobook",
        "Upload a document, paste text, or add an article URL",
        "Article URL",
        "Upload File",
        "Paste Text",
        "Drop a file here or click to browse",
        "Supported: PDF, EPUB, TXT, DOCX",
        "Only upload content you own or have permission to convert.",
    ]:
        assert text in INDEX


def test_narration_settings_are_consumer_friendly():
    for text in [
        "Narration settings",
        "Ava — Warm female voice",
        "Noah — Clear male voice",
        "Emma — Calm narrator",
        "Read numbers and currency naturally",
        "0.8x",
        "1.0x",
        "1.2x",
        "1.5x",
        "Create Audiobook",
        "Creating audiobook...",
    ]:
        assert text in INDEX


def test_library_is_modern_saas_copy():
    for text in [
        "Your generated audiobooks.",
        "+ New Audiobook",
        "Search audiobooks",
        "No audiobooks yet",
        "Create your first audiobook from a PDF, EPUB, article, or pasted text.",
        "status-badge",
        "audiobook-card",
        "cover-waveform",
    ]:
        assert text in INDEX


def test_premium_shell_uses_one_design_system():
    for text in [
        "app-header",
        "app-container",
        "page-kicker",
        "page-title",
        "account-button",
        "nav-cluster",
        "view !== 'player'",
    ]:
        assert text in INDEX


def test_navbar_is_refined_command_bar():
    for text in [
        "topbar",
        "brand-lockup",
        "brand-symbol",
        "brand-name",
        "brand-submark",
        "nav-cluster",
        "nav-item",
        "account-button",
        "account-dot",
    ]:
        assert text in INDEX
    assert "avatar-button" not in INDEX
    assert "shell-divider" not in INDEX


def test_library_cards_use_clean_premium_metadata():
    for text in [
        "displayTitle(job)",
        "coverDisplayTitle(job)",
        "cleanSourceLabel(job)",
        "book-card-title",
        "book-card-meta",
        "book-card-footer",
    ]:
        assert text in INDEX


def test_player_reads_as_same_product_in_listening_mode():
    for text in [
        "player-header",
        "player-listening-surface",
        "player-transcript",
        "player-meta",
        "player-page-title",
    ]:
        assert text in INDEX


def test_ui_uses_ancient_natural_palette_tokens():
    for text in [
        "--color-parchment: #F6F0E4",
        "--color-limestone: #E7DDCC",
        "--color-cedar: #4F5F3A",
        "--color-olive: #6B7C45",
        "--color-umber: #8A6442",
        "--color-clay: #B9855A",
    ]:
        assert text in INDEX


def test_player_removes_creepy_chapter_dropdown():
    assert "chapterLabel(activeJob, activeChapterIdx)" in INDEX
    assert "player-chapter-label" in INDEX
    assert "player-chapter-select" not in INDEX
    assert '<select x-model="activeChapterIdx"' not in INDEX


def test_player_stays_on_shared_light_natural_theme():
    for text in [
        "player-paper",
        "player-reading-card",
        "background: var(--color-parchment)",
        "color: var(--color-text)",
    ]:
        assert text in INDEX
    assert "#100D0F" not in INDEX
    assert "#151012" not in INDEX


def test_auth_screen_uses_product_positioning():
    assert "Start creating audiobooks" in INDEX
    assert "Turn documents, articles, and pasted text into listenable audio." in INDEX
    assert "Join" not in INDEX


def test_auth_errors_are_inline_and_actionable():
    assert "authError: null" in INDEX
    assert "setAuthError(" in INDEX
    assert "Google sign-in is not authorized for this address." in INDEX
    assert "Open http://localhost:8000" in INDEX
    assert "Google Login Error" not in INDEX


def test_frontend_caches_query_token_for_api_requests():
    assert "URLSearchParams(window.location.search)" in INDEX
    assert "audiobook_access_token" in INDEX
    assert "opt.headers['X-Token']" in INDEX
    assert "fetch('/api/auth/me', reqOpt())" in INDEX
    assert "fetch('/api/auth/me')" not in INDEX


def test_frontend_redirects_loopback_ip_to_firebase_safe_localhost():
    assert "normalizeLocalAuthOrigin()" in INDEX
    assert "window.location.hostname === '127.0.0.1'" in INDEX
    assert "window.location.replace" in INDEX


def test_upload_submit_uses_reactive_file_state():
    assert "selectedFile: null" in INDEX
    assert "this.selectedFile = file" in INDEX
    assert "if (this.inputMethod === 'upload') return !!this.selectedFile;" in INDEX
    assert "fd.append('file', this.selectedFile)" in INDEX


def test_selected_upload_filename_is_mobile_safe():
    assert "selected-file-name" in INDEX
    assert "overflow-wrap: anywhere" in INDEX
    assert "word-break: break-word" in INDEX


def test_pwa_install_guidance_is_available_without_modal():
    assert "install-card" in INDEX
    assert "Add to Home Screen" in INDEX
    assert "For the most reliable offline listening" in INDEX
    assert "beforeinstallprompt" in INDEX
    assert "installApp()" in INDEX


def test_pwa_manifest_uses_real_installable_icons():
    icons = MANIFEST["icons"]
    icon_sizes = {icon["sizes"] for icon in icons}

    assert "192x192" in icon_sizes
    assert "512x512" in icon_sizes
    assert any("maskable" in icon.get("purpose", "") for icon in icons)
    assert all(not icon["src"].startswith("data:") for icon in icons)
    assert all(icon.get("type") == "image/png" for icon in icons)


def test_mobile_pwa_guidance_does_not_depend_only_on_browser_prompt():
    assert "isMobileDevice()" in INDEX
    assert "installInstructions()" in INDEX
    assert "Open your browser menu, then choose Add to Home screen." in INDEX
    assert "this.canPromptInstall() || this.isIosDevice() || this.isMobileDevice()" in INDEX


def test_service_worker_uses_network_first_for_navigation_shell():
    assert "e.request.mode === 'navigate'" in SW
    assert "fetch(e.request)" in SW


def test_resume_listening_ui_contract():
    for text in [
        "savePlaybackPosition",
        "getPlaybackPosition",
        "clearPlaybackPosition",
        "Continue Listening",
        "Start Listening",
        "progressLabel(job)",
    ]:
        assert text in INDEX


def test_player_has_minimal_audiobook_controls():
    for text in [
        "Rewind 15 seconds",
        "Forward 30 seconds",
        "Chapter",
        "Save Offline to This Device",
    ]:
        assert text in INDEX


def test_player_has_minimal_ambient_treatment():
    for text in [
        "player-ambient",
        "playerAmbientStyle(activeJob)",
        "--ambient-1",
        "--ambient-2",
        "player-control-panel",
        "player-primary-control",
        "player-progress",
        "@media (prefers-reduced-motion: no-preference)",
    ]:
        assert text in INDEX


def test_player_uses_clear_custom_controls():
    for text in [
        "togglePlayback",
        "seekPlayer",
        "playerCurrentTime",
        "playerDuration",
        "playerPlaying",
        "Play audiobook",
        "Pause audiobook",
        "formatClock(playerCurrentTime)",
    ]:
        assert text in INDEX


def test_failure_recovery_copy_exists():
    for text in [
        "We couldn’t create this audiobook",
        "Try a TXT, DOCX, or paste the text.",
        "Try again",
        "Paste text instead",
    ]:
        assert text in INDEX


def test_resume_saves_on_player_lifecycle_events():
    for text in [
        '@pause="savePlaybackPosition()"',
        '@seeked="savePlaybackPosition()"',
        '@canplay="restorePlaybackPosition()"',
        "window.addEventListener('pagehide'",
        "document.addEventListener('visibilitychange'",
    ]:
        assert text in INDEX


def test_resume_restores_with_context_and_rewind():
    for text in [
        "resumeRewindSeconds: 3",
        "chapterFile",
        "resolvePlaybackChapterIdx(job, pos)",
        "restorePlaybackPosition()",
        "positionSummary(job)",
        "Continue from",
    ]:
        assert text in INDEX


def test_create_page_has_mobile_first_structure():
    for text in [
        "create-shell",
        "create-copy-mobile",
        "mobile-sticky-create",
        "Upload",
        "Paste",
        "URL",
    ]:
        assert text in INDEX


def test_narration_settings_collapse_on_mobile():
    for text in [
        "settingsCollapsed",
        "settings-summary",
        "Narration",
        "voiceLabel(jobForm.voice)",
        "x-show=\"!settingsCollapsed\"",
    ]:
        assert text in INDEX


def test_mobile_create_css_contract():
    for text in [
        "@media (max-width: 720px)",
        ".create-shell",
        ".mobile-sticky-create",
        "position: fixed",
        "padding-bottom: calc",
    ]:
        assert text in INDEX


def test_service_worker_cache_version_bumped():
    assert "audiobook-app-v29" in SW


if __name__ == "__main__":
    for test in [
        test_offline_copy_is_device_specific,
        test_library_uses_clear_ready_state,
        test_player_has_offline_status_surface,
        test_offline_success_uses_in_app_toast,
        test_cover_keeps_generated_art_without_duplicate_status,
        test_redundant_ui_surfaces_removed,
        test_us_market_branding_removed_cjk_identity,
        test_create_flow_is_tabbed_and_plain_language,
        test_narration_settings_are_consumer_friendly,
        test_library_is_modern_saas_copy,
        test_premium_shell_uses_one_design_system,
        test_navbar_is_refined_command_bar,
        test_library_cards_use_clean_premium_metadata,
        test_player_reads_as_same_product_in_listening_mode,
        test_ui_uses_ancient_natural_palette_tokens,
        test_player_removes_creepy_chapter_dropdown,
        test_player_stays_on_shared_light_natural_theme,
        test_auth_screen_uses_product_positioning,
        test_auth_errors_are_inline_and_actionable,
        test_frontend_caches_query_token_for_api_requests,
        test_frontend_redirects_loopback_ip_to_firebase_safe_localhost,
        test_upload_submit_uses_reactive_file_state,
        test_selected_upload_filename_is_mobile_safe,
        test_pwa_install_guidance_is_available_without_modal,
        test_pwa_manifest_uses_real_installable_icons,
        test_mobile_pwa_guidance_does_not_depend_only_on_browser_prompt,
        test_service_worker_uses_network_first_for_navigation_shell,
        test_resume_listening_ui_contract,
        test_player_has_minimal_audiobook_controls,
        test_player_has_minimal_ambient_treatment,
        test_player_uses_clear_custom_controls,
        test_failure_recovery_copy_exists,
        test_resume_saves_on_player_lifecycle_events,
        test_resume_restores_with_context_and_rewind,
        test_create_page_has_mobile_first_structure,
        test_narration_settings_collapse_on_mobile,
        test_mobile_create_css_contract,
        test_service_worker_cache_version_bumped,
    ]:
        test()
    print("ui polish tests passed")
