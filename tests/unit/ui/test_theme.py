from tiewtrade.ui.theme import DARK_THEME


def test_dark_theme_uses_approved_workspace_palette() -> None:
    for color in (
        "#0B0E11",
        "#141A22",
        "#1B2430",
        "#2B3441",
        "#F1F5F9",
        "#94A3B8",
        "#0ECB81",
        "#F6465D",
        "#F0B90B",
    ):
        assert color in DARK_THEME

    assert "background: #F4F7FB;" not in DARK_THEME
    assert "background: #FFFFFF;" not in DARK_THEME


def test_dark_theme_defines_focus_and_semantic_states() -> None:
    assert 'QWidget[state="positive"]' in DARK_THEME
    assert 'QWidget[state="negative"]' in DARK_THEME
    assert 'QWidget[state="warning"]' in DARK_THEME
    assert "QPushButton:focus" in DARK_THEME


def test_dark_theme_covers_existing_navigation_and_content_object_names() -> None:
    for selector in (
        "QWidget#content",
        "QFrame#navigation",
        "QPushButton#navigationButton",
        "QPushButton#navigationButtonSelected",
        "QPushButton#unavailableRetryButton",
        "QLabel#eyebrow",
        "QLabel#summaryValue",
    ):
        assert f"{selector} {{" in DARK_THEME
