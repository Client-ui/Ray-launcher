use std::time::Duration;

use freya::prelude::*;
use freya::router::RouterContext;
use rayclient_core::settings::LauncherSettings;

use super::settings_page;
use crate::components::{
    BUNDLED_WALLPAPERS, ColorPicker, IconType, Segment, SegmentedControl, link_button, toggle,
};
use crate::hooks::{Actions, use_debounced, use_dispatch, use_settings_snapshot};
use crate::i18n::t;
use crate::routes::Route;
use crate::theme::{
    SYSTEM_THEME,
    colors::{self, Palette},
    resolve_theme, rounded, system_aware, text_size, themes,
};
use crate::ui::border_all_color;
use crate::view::app::settings::{resettable, settings_row};
use crate::wallpaper;

#[derive(PartialEq)]
pub struct SettingsAppearance;

impl Component for SettingsAppearance {
    fn render(&self) -> impl IntoElement {
        let settings = use_settings_snapshot().settings;
        let defaults = LauncherSettings::default();
        let dispatch = use_dispatch();

        let dynamic_bg = use_state({
            let v = settings.dynamic_background_enabled;
            move || v
        });

        let animations_on = use_state({
            let v = settings.animations_enabled;
            move || v
        });

        let mut first = use_state(|| true);
        let persist = dispatch.clone();
        use_side_effect(move || {
            let parallax = *dynamic_bg.read();
            let animations = *animations_on.read();
            if *first.peek() {
                first.set(false);
                return;
            }
            persist.edit_settings(|settings| {
                settings.dynamic_background_enabled = parallax;
                settings.animations_enabled = animations;
            });
        });

        let wallpaper_accent = use_state({
            let v = settings.wallpaper_accent;
            move || v
        });
        let mut wallpaper_ready = use_state(|| false);
        let persist_wallpaper_accent = dispatch.clone();
        use_side_effect(move || {
            let value = *wallpaper_accent.read();
            if !*wallpaper_ready.peek() {
                wallpaper_ready.set(true);
                return;
            }
            persist_wallpaper_accent.edit_settings(|settings| settings.wallpaper_accent = value);
        });

        let dim = use_state({
            let v = settings.wallpaper_dim;
            move || v
        });
        let mut dim_ready = use_state(|| false);
        let persist_dim = dispatch.clone();
        use_side_effect(move || {
            let value = *dim.read();
            if !*dim_ready.peek() {
                dim_ready.set(true);
                return;
            }
            persist_dim.edit_settings(|settings| settings.wallpaper_dim = value);
        });

        let accent = use_state({
            let v = settings.accent_color.clone();
            move || v
        });
        let settled_accent = use_debounced(accent.read().clone(), Duration::from_millis(250));
        let mut accent_ready = use_state(|| false);
        let persist_accent = dispatch.clone();
        use_side_effect_with_deps(&settled_accent.read().clone(), move |value| {
            if !*accent_ready.peek() {
                accent_ready.set(true);
                return;
            }
            let value = value.clone();
            persist_accent.edit_settings(|settings| settings.accent_color = value);
        });

        settings_page()
            .child(theme_section(&settings.theme, dispatch.clone()))
            .child(
                rect()
                    .vertical()
                    .width(Size::fill())
                    .spacing(4.)
                    .padding(Gaps::new(8., 0., 0., 0.))
                    .child(accent_color_row(accent, defaults.accent_color.clone()))
                    .child(custom_theme_row())
                    .child(dynamic_background_row(
                        dynamic_bg,
                        defaults.dynamic_background_enabled,
                    ))
                    .child(animations_row(animations_on, defaults.animations_enabled)),
            )
            .child(settings_row(
                IconType::Eye,
                t("oneclient.settings.appearance.wallpaper_accent.title"),
                t("oneclient.settings.appearance.wallpaper_accent.description"),
                resettable(
                    toggle(wallpaper_accent),
                    wallpaper_accent,
                    defaults.wallpaper_accent,
                ),
            ))
            .child(settings_row(
                IconType::Eye,
                t("oneclient.settings.appearance.wallpaper_dim.title"),
                t("oneclient.settings.appearance.wallpaper_dim.description"),
                SegmentedControl::new(dim).segments([
                    Segment::new(0u8).label(t("oneclient.settings.appearance.wallpaper_dim.off")),
                    Segment::new(1u8).label(t("oneclient.settings.appearance.wallpaper_dim.light")),
                    Segment::new(2u8)
                        .label(t("oneclient.settings.appearance.wallpaper_dim.medium")),
                    Segment::new(3u8)
                        .label(t("oneclient.settings.appearance.wallpaper_dim.strong")),
                ]),
            ))
            .child(wallpaper_section(
                settings.wallpaper.clone(),
                dispatch.clone(),
            ))
            .child(
                rect().padding(Gaps::new(8., 0., 0., 0.)).child(
                    label()
                        .text(t("oneclient.settings.appearance.language_hint"))
                        .font_size(text_size(12.))
                        .color(colors::fg_primary()),
                ),
            )
            .into_element()
    }
}

fn theme_section(selected: &str, dispatch: Actions) -> impl IntoElement {
    let system_dark =
        *Platform::get().current_window().preferred_theme.read() == PreferredTheme::Dark;
    let active = resolve_theme(system_aware(selected, system_dark));

    rect()
        .horizontal()
        .spacing(16.)
        .child(big_preview(active.colors))
        .child(theme_cards(selected, dispatch))
        .into_element()
}

pub(crate) fn theme_cards(selected: &str, dispatch: Actions) -> impl IntoElement {
    let system_dark =
        *Platform::get().current_window().preferred_theme.read() == PreferredTheme::Dark;
    let active = resolve_theme(system_aware(selected, system_dark));
    let (dark, light) = (resolve_theme("dark"), resolve_theme("light"));

    let system = ThemeCard {
        id: SYSTEM_THEME.to_string(),
        name: "System".to_string(),
        background: LinearGradient::new()
            .angle(-90.)
            .stop((dark.colors.page.0, 0.))
            .stop((dark.colors.page.0, 50.))
            .stop((light.colors.page.0, 50.))
            .stop((light.colors.page.0, 100.))
            .into(),
        preview: dark.colors,
        radius_scale: dark.radius_scale,
        selected: selected == SYSTEM_THEME,
    };
    let cards: Vec<ThemeCard> = std::iter::once(system)
        .chain(themes().iter().map(|theme| ThemeCard {
            id: theme.id.clone(),
            name: theme.name.clone(),
            background: theme.colors.page.0.into(),
            preview: theme.colors,
            radius_scale: theme.radius_scale,
            selected: selected != SYSTEM_THEME && theme.id == active.id,
        }))
        .collect();

    rect()
        .vertical()
        .spacing(16.)
        .children(cards.chunks(3).map(|row| {
            rect()
                .horizontal()
                .spacing(16.)
                .children(row.iter().map(|card| theme_card(card, dispatch.clone())))
                .into_element()
        }))
        .into_element()
}

fn big_preview(theme: Palette) -> impl IntoElement {
    rect()
        .width(Size::px(296.))
        .height(Size::px(183.))
        .corner_radius(rounded(16.))
        .background(colors::page())
        .border(border_all_color(3., Color::from_argb(26, 255, 255, 255)))
        .center()
        .child(
            rect()
                .vertical()
                .width(Size::px(168.))
                .height(Size::px(123.))
                .corner_radius(rounded(8.))
                .background(theme.page.0)
                .border(border_all_color(1., colors::component_border()))
                .padding(20.)
                .spacing(20.)
                .child(mock_line(108., theme.accent.0))
                .child(mock_line(84., line_tint(theme)))
                .child(split_bar(theme.accent.0, 96.)),
        )
        .into_element()
}

struct ThemeCard {
    id: String,
    name: String,
    background: Fill,
    preview: Palette,
    radius_scale: f32,
    selected: bool,
}

fn theme_card(card: &ThemeCard, dispatch: Actions) -> Element {
    let id = card.id.clone();
    let border_color = if card.selected {
        colors::brand()
    } else {
        colors::component_border()
    };

    rect()
        .vertical()
        .spacing(6.)
        .cursor(CursorIcon::Pointer)
        .on_press(move |_| {
            dispatch.edit_settings(|settings| settings.theme = id.clone());
        })
        .child(
            rect()
                .vertical()
                .width(Size::px(126.))
                .height(Size::px(78.))
                .corner_radius(CornerRadius::new_all(8. * card.radius_scale))
                .background(card.background.clone())
                .border(border_all_color(1., border_color))
                .padding(8.)
                .spacing(20.)
                .child(mock_line(108., line_tint(card.preview)))
                .child(split_bar(card.preview.accent.0, 96.)),
        )
        .child(
            label()
                .text(card.name.clone())
                .width(Size::px(126.))
                .max_lines(1)
                .text_overflow(TextOverflow::Ellipsis)
                .font_size(text_size(12.))
                .font_weight(if card.selected {
                    FontWeight::MEDIUM
                } else {
                    FontWeight::NORMAL
                })
                .color(if card.selected {
                    colors::fg_primary()
                } else {
                    colors::fg_secondary()
                }),
        )
        .into_element()
}

fn mock_line(width: f32, color: Color) -> impl IntoElement {
    rect()
        .width(Size::px(width))
        .height(Size::px(10.))
        .corner_radius(rounded(4.))
        .background(color)
        .into_element()
}

fn split_bar(accent: Color, width: f32) -> impl IntoElement {
    rect()
        .horizontal()
        .width(Size::px(width))
        .height(Size::px(16.))
        .corner_radius(rounded(4.))
        .background(accent.with_a(128))
        .child(
            rect()
                .width(Size::px(width / 3.))
                .height(Size::fill())
                .corner_radius(rounded(4.))
                .background(accent),
        )
        .into_element()
}

fn line_tint(theme: Palette) -> Color {
    if theme.light {
        Color::from_argb(38, 0, 0, 0)
    } else {
        Color::from_argb(46, 255, 255, 255)
    }
}

fn accent_color_row(accent: State<Option<String>>, default: Option<String>) -> impl IntoElement {
    let shown = accent
        .read()
        .as_deref()
        .and_then(colors::parse_hex)
        .map_or_else(colors::brand, |(r, g, b)| Color::from_rgb(r, g, b));

    settings_row(
        IconType::PaintPour,
        t("oneclient.settings.appearance.accent_color.title"),
        t("oneclient.settings.appearance.accent_color.description"),
        resettable(
            ColorPicker::new(shown, move |picked: Color| {
                let mut accent = accent;
                accent.set(Some(colors::format_hex(picked)));
            })
            .into_element(),
            accent,
            default,
        ),
    )
}

fn custom_theme_row() -> impl IntoElement {
    settings_row(
        IconType::Colors,
        t("oneclient.settings.appearance.custom_theme.title"),
        t("oneclient.settings.appearance.custom_theme.description"),
        link_button().on_press(|_| {
            let _ = RouterContext::get().push(Route::SettingsThemeEditor {});
        }),
    )
}

fn dynamic_background_row(enabled: State<bool>, default: bool) -> impl IntoElement {
    settings_row(
        IconType::Eye,
        t("oneclient.settings.appearance.parallax_background.title"),
        t("oneclient.settings.appearance.parallax_background.description"),
        resettable(toggle(enabled), enabled, default),
    )
}

fn animations_row(animations_on: State<bool>, default: bool) -> impl IntoElement {
    settings_row(
        IconType::Play,
        t("oneclient.settings.appearance.animations.title"),
        t("oneclient.settings.appearance.animations.description"),
        resettable(toggle(animations_on), animations_on, default),
    )
}

fn wallpaper_section(selected: Option<String>, dispatch: Actions) -> impl IntoElement {
    let custom_selected = selected
        .as_deref()
        .filter(|path| wallpaper::is_custom(path));

    let auto_dispatch = dispatch.clone();
    let mut tiles: Vec<Element> = vec![wallpaper_tile(
        glyph_preview("\u{2726}"),
        t("oneclient.settings.appearance.wallpaper.automatic"),
        selected.is_none(),
        move || auto_dispatch.edit_settings(|settings| settings.wallpaper = None),
    )];

    let upload_dispatch = dispatch.clone();
    tiles.push(wallpaper_tile(
        glyph_preview("+"),
        t("oneclient.settings.appearance.wallpaper.upload"),
        false,
        move || {
            let dispatch = upload_dispatch.clone();
            spawn(async move {
                let Some(handle) = rfd::AsyncFileDialog::new()
                    .set_title(t("oneclient.settings.appearance.wallpaper.upload_title"))
                    .add_filter("Images", &["png", "jpg", "jpeg"])
                    .pick_file()
                    .await
                else {
                    return;
                };
                if let Some(path) = wallpaper::import(handle.path().to_path_buf()).await {
                    dispatch.edit_settings(|settings| {
                        settings.wallpaper = Some(path);
                        settings.wallpaper_accent = true;
                    });
                }
            });
        },
    ));

    if let Some(path) = custom_selected {
        tiles.push(wallpaper_tile(
            image_preview(path.to_string()),
            t("oneclient.settings.appearance.wallpaper.custom"),
            true,
            || {},
        ));
    }

    for path in BUNDLED_WALLPAPERS {
        let dispatch = dispatch.clone();
        let name = wallpaper_name(path);
        tiles.push(wallpaper_tile(
            image_preview(path.to_string()),
            name,
            selected.as_deref() == Some(path),
            move || {
                dispatch.edit_settings(|settings| settings.wallpaper = Some(path.to_string()));
            },
        ));
    }

    rect()
        .vertical()
        .width(Size::fill())
        .spacing(8.)
        .padding(Gaps::new(12., 0., 0., 0.))
        .child(
            label()
                .text(t("oneclient.settings.appearance.wallpaper.title"))
                .font_size(text_size(15.))
                .font_weight(FontWeight::MEDIUM)
                .color(colors::fg_primary()),
        )
        .child(
            label()
                .text(t("oneclient.settings.appearance.wallpaper.description"))
                .font_size(text_size(12.))
                .color(colors::fg_secondary()),
        )
        .child(
            rect()
                .horizontal()
                .width(Size::fill())
                .content(Content::Wrap {
                    wrap_spacing: Some(12.),
                })
                .spacing(12.)
                .children(tiles),
        )
}

fn glyph_preview(glyph: &'static str) -> Element {
    rect()
        .width(Size::fill())
        .height(Size::fill())
        .center()
        .child(
            label()
                .text(glyph)
                .font_size(text_size(22.))
                .color(colors::brand()),
        )
        .into_element()
}

fn image_preview(path: String) -> Element {
    ImageViewer::new((
        format!("wallpaper-thumb|{path}"),
        wallpaper::bytes_for(&path).unwrap_or_default(),
    ))
    .width(Size::fill())
    .height(Size::fill())
    .aspect_ratio(AspectRatio::Max)
    .image_cover(ImageCover::Center)
    .into_element()
}

/// `backgrounds/RayEmber.jpg` -> `Ember`
fn wallpaper_name(path: &str) -> String {
    let stem = path
        .rsplit('/')
        .next()
        .and_then(|file| file.strip_suffix(".jpg"))
        .unwrap_or(path);
    stem.strip_prefix("Ray").unwrap_or(stem).to_string()
}

fn wallpaper_tile(
    preview: Element,
    name: impl Into<String>,
    selected: bool,
    on_pick: impl Fn() + 'static,
) -> Element {
    let border_color = if selected {
        colors::brand()
    } else {
        colors::component_border()
    };

    rect()
        .vertical()
        .spacing(6.)
        .cursor(CursorIcon::Pointer)
        .on_press(move |_| on_pick())
        .child(
            rect()
                .width(Size::px(150.))
                .height(Size::px(84.))
                .corner_radius(CornerRadius::new_all(8.))
                .overflow(Overflow::Clip)
                .background(colors::component())
                .border(border_all_color(
                    if selected { 2. } else { 1. },
                    border_color,
                ))
                .child(preview),
        )
        .child(
            label()
                .text(name.into())
                .width(Size::px(150.))
                .max_lines(1)
                .text_overflow(TextOverflow::Ellipsis)
                .font_size(text_size(12.))
                .font_weight(if selected {
                    FontWeight::MEDIUM
                } else {
                    FontWeight::NORMAL
                })
                .color(if selected {
                    colors::fg_primary()
                } else {
                    colors::fg_secondary()
                }),
        )
        .into_element()
}
