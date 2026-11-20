use std::collections::HashSet;

use freya::prelude::*;

use crate::components::overlay_popup::{DialogSurface, dialog_body, dialog_footer};
use crate::components::{Button, Icon, IconType, OverlayPopup, ScrollArea, toggle_controlled};
use crate::hooks::{use_dispatch, use_notifications_snapshot};
use crate::i18n::{t, tf};
use crate::theme::{colors, rounded, text_size};

const DIALOG_W: f32 = 460.;
const LIST_MAX_H: f32 = 306.;

#[derive(PartialEq)]
pub struct BundleChoicesPopup;

impl Component for BundleChoicesPopup {
    fn render(&self) -> impl IntoElement {
        let snapshot = use_notifications_snapshot();
        let dispatch = use_dispatch();
        let mut chosen = use_state(HashSet::<String>::new);

        let Some(choices) = snapshot.bundle_choices.clone() else {
            return rect().into_element();
        };

        let mut list = rect().vertical().width(Size::fill()).spacing(6.);
        for (name, title) in &choices.bundles {
            let key = name.clone();
            let on_toggle: EventHandler<()> = (move |()| {
                let mut next = chosen.read().clone();
                if !next.remove(&key) {
                    next.insert(key.clone());
                }
                chosen.set(next);
            })
            .into();
            list = list.child(
                rect()
                    .key(name.clone())
                    .horizontal()
                    .width(Size::fill())
                    .content(Content::Flex)
                    .cross_align(Alignment::Center)
                    .padding(Gaps::new_symmetric(8., 10.))
                    .corner_radius(rounded(8.))
                    .background(colors::component_bg())
                    .child(
                        label()
                            .text(title.clone())
                            .font_size(text_size(13.))
                            .max_lines(1)
                            .width(Size::flex(1.0))
                            .color(colors::fg_primary()),
                    )
                    .child(toggle_controlled(
                        choices.held.contains(name) != chosen.read().contains(name),
                        on_toggle,
                    )),
            );
        }

        let names: Vec<String> = choices
            .bundles
            .iter()
            .map(|(name, _)| name.clone())
            .collect();
        let held = choices.held.clone();
        let later = dispatch.clone();
        let close = dispatch.clone();

        let dialog_content = dialog_body()
            .child(
                label()
                    .text(t("oneclient.components.bundle_choices_popup.title"))
                    .font_size(text_size(18.))
                    .font_weight(FontWeight::BOLD)
                    .color(colors::fg_primary()),
            )
            .child(
                label()
                    .text(tf(
                        "oneclient.components.bundle_choices_popup.description",
                        &[&choices.cluster_name],
                    ))
                    .font_size(text_size(12.5))
                    .max_lines(4)
                    .color(colors::fg_secondary()),
            )
            .child(
                ScrollArea::new()
                    .width(Size::fill())
                    .height(Size::Inner)
                    .max_height(Size::px(LIST_MAX_H))
                    .child(list),
            );
        let dialog_actions = dialog_footer(
            rect()
                .horizontal()
                .width(Size::fill())
                .main_align(Alignment::End)
                .spacing(8.)
                .child(
                    Button::new()
                        .ghost()
                        .on_press(move |_| {
                            chosen.set(HashSet::new());
                            later.close_bundle_choices(None);
                        })
                        .text(t("oneclient.components.bundle_choices_popup.later")),
                )
                .child(
                    Button::new()
                        .primary()
                        .on_press(move |_| {
                            let flipped = chosen.read().clone();
                            let picked = names
                                .iter()
                                .filter(|name| held.contains(*name) != flipped.contains(*name))
                                .cloned()
                                .collect();
                            chosen.set(HashSet::new());
                            dispatch.close_bundle_choices(Some(picked));
                        })
                        .child(Icon::new(IconType::Check).size(15.))
                        .text(t("oneclient.components.bundle_choices_popup.confirm")),
                ),
        );
        OverlayPopup::new()
            .on_close(move |_| {
                chosen.set(HashSet::new());
                close.close_bundle_choices(None);
            })
            .child(
                rect()
                    .width(Size::window_percent(100.))
                    .height(Size::window_percent(100.))
                    .center()
                    .child(
                        rect()
                            .vertical()
                            .width(Size::px(DIALOG_W))
                            .height(Size::Inner)
                            .max_width(Size::window_percent(95.))
                            .max_height(Size::window_percent(85.))
                            .overflow(Overflow::Clip)
                            .dialog_surface()
                            .child(dialog_content)
                            .child(dialog_actions),
                    ),
            )
            .into_element()
    }
}
