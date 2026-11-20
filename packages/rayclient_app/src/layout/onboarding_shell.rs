use std::collections::HashSet;

use freya::prelude::*;
use freya::router::{Outlet, use_route};

use crate::Route;
use crate::components::OnboardingNavbar;
use crate::hooks::{
    OnboardingSelectionState, has_migration_data, onboarding_bundles_items, use_launcher,
    use_migration, use_onboarding_bundles, use_provide_onboarding_selection, use_settings_snapshot,
};
use crate::i18n::t;
use crate::theme::{colors, rounded, text_size};
use crate::view::onboarding::{default_selection, onboarding_step_index, onboarding_total};

#[derive(PartialEq)]
pub struct OnboardingShell;

impl Component for OnboardingShell {
    fn render(&self) -> impl IntoElement {
        let mut selected = use_state(HashSet::new);
        let user_touched = use_state(|| false);
        let migrated_categories = use_state(|| None::<Vec<String>>);
        let language = use_state(|| "English".to_string());
        let reduce_motion = use_state(|| false);
        let import_folder = use_state(|| None::<String>);
        let import_dedicated = use_state(|| false);
        let picks_location = use_state({
            let fresh = use_launcher().needs_location;
            move || fresh
        });
        let route = use_route::<Route>();
        let chrome_opacity = use_state({
            let welcome = matches!(route, Route::OnboardingWelcome {});
            move || if welcome { 0. } else { 1. }
        });
        use_provide_onboarding_selection(OnboardingSelectionState {
            selected,
            user_touched,
            migrated_categories,
            language,
            reduce_motion,
            import_folder,
            import_dedicated,
            picks_location,
            chrome_opacity,
        });

        let migration_query = use_migration();
        let detected_migration = has_migration_data(&migration_query);

        let choosing_location = *picks_location.read();
        let step_index = onboarding_step_index(&route, detected_migration, choosing_location);

        let onboarded = use_settings_snapshot().settings.seen_onboarding;
        let reconsent = onboarded && matches!(&route, Route::OnboardingTerms {});

        let bundles = use_onboarding_bundles();

        use_side_effect(move || {
            if *user_touched.peek() {
                return;
            }
            let Some(items) = onboarding_bundles_items(&bundles) else {
                return;
            };
            let categories = migrated_categories.read().clone();
            let defaults = default_selection(&items, categories.as_deref());
            if *selected.peek() != defaults {
                selected.set(defaults);
            }
        });

        let chrome = *chrome_opacity.read();

        rect()
            .vertical()
            .width(Size::fill())
            .height(Size::fill())
            .background(colors::page())
            .color(colors::fg_primary())
            .overflow(Overflow::Clip)
            .child(top_glow())
            .child(
                rect()
                    .vertical()
                    .width(Size::fill())
                    .height(Size::fill())
                    .content(Content::Flex)
                    .layer(Layer::Relative(30))
                    .maybe_child((!reconsent).then(|| {
                        rect()
                            .width(Size::fill())
                            .opacity(chrome)
                            .child(progress_bar(
                                step_index,
                                onboarding_total(detected_migration, choosing_location),
                            ))
                            .into_element()
                    }))
                    .child(
                        rect()
                            .width(Size::fill())
                            .opacity(chrome)
                            .child(OnboardingNavbar),
                    )
                    .child(
                        rect()
                            .width(Size::fill())
                            .height(Size::flex(1.0))
                            .overflow(Overflow::Clip)
                            .child(Outlet::<Route>::new())
                            .child(copyright(chrome)),
                    ),
            )
    }
}

fn progress_bar(step_index: usize, total: usize) -> impl IntoElement {
    let mut pills = rect()
        .horizontal()
        .main_align(Alignment::Center)
        .cross_align(Alignment::Center)
        .spacing(6.);

    for i in 0..total {
        let active = i == step_index;
        let done = i < step_index;
        pills = pills.child(
            rect()
                .width(Size::px(if active { 28. } else { 8. }))
                .height(Size::px(8.))
                .corner_radius(rounded(4.))
                .background(if active {
                    colors::brand()
                } else if done {
                    colors::brand_glow(110)
                } else {
                    colors::ghost_overlay_hover()
                }),
        );
    }

    rect()
        .width(Size::fill())
        .center()
        .padding(Gaps::new_symmetric(10., 0.))
        .child(pills)
}

/// A soft brand wash across the top of the page
fn top_glow() -> impl IntoElement {
    rect()
        .position(Position::new_absolute().top(0.).left(0.))
        .interactive(false)
        .width(Size::fill())
        .height(Size::px(320.))
        .background(
            LinearGradient::new()
                .angle(0.)
                .stop((colors::brand_glow(34), 0.))
                .stop((colors::brand_glow(0), 100.)),
        )
}

fn copyright(opacity: f32) -> impl IntoElement {
    rect()
        .position(Position::new_absolute().bottom(16.).left(24.))
        .interactive(false)
        .opacity(opacity)
        .child(
            label()
                .text(t("oneclient.layout.onboarding.copyright"))
                .font_size(text_size(11.))
                .color(colors::fg_secondary()),
        )
}
