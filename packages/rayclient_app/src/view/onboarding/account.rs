use freya::prelude::*;
use freya::query::MutationStateData;
use rayclient_auth::MinecraftAccount;

use crate::components::{Avatar, Button, Icon, IconType, TextInput, use_microsoft_login};
use crate::hooks::{
    AddOfflineAccountKeys, try_default_account, use_add_offline_account, use_current_account,
};
use crate::i18n::t;
use crate::routes::Route;
use crate::theme::{colors, text_size};
use crate::view::onboarding::{
    onboarding_illustration, onboarding_nav, onboarding_page, step_heading,
};

#[derive(PartialEq)]
pub struct OnboardingAccount;

impl Component for OnboardingAccount {
    fn render(&self) -> impl IntoElement {
        let account_query = use_current_account();
        let msa = use_microsoft_login();
        let add_offline = use_add_offline_account();
        let username = use_state(String::new);

        let account = try_default_account(&account_query);
        let has_account = account.is_some();

        let content = rect()
            .vertical()
            .width(Size::fill())
            .spacing(24.)
            .child(step_heading(
                t("oneclient.onboarding.account.title"),
                t("oneclient.onboarding.account.subtitle"),
            ))
            .child(match &account {
                Some(account) => account_preview(account).into_element(),
                None => {
                    let start = msa.clone();
                    let offline_error = match &*add_offline.read().state() {
                        MutationStateData::Settled { res: Err(err), .. } => Some(err.to_string()),
                        _ => None,
                    };
                    let on_offline = move |_| {
                        let name = username.peek().trim().to_string();
                        if !name.is_empty() {
                            add_offline.mutate(AddOfflineAccountKeys { username: name });
                        }
                    };
                    sign_in_card(
                        msa.pending,
                        msa.error.clone().or(offline_error),
                        username,
                        move |_| start.start(),
                        on_offline,
                    )
                    .into_element()
                }
            })
            .into_element();

        let page = onboarding_page(
            onboarding_illustration(IconType::OnboardingAccount),
            content,
            onboarding_nav(
                Some(Route::OnboardingLanguage {}),
                Route::OnboardingBundles {},
                has_account,
            ),
        );

        rect()
            .width(Size::fill())
            .height(Size::fill())
            .child(page)
            .maybe_child(msa.popup())
    }
}

fn account_preview(account: &MinecraftAccount) -> impl IntoElement {
    rect()
        .horizontal()
        .width(Size::fill())
        .spacing(24.)
        .child(
            rect()
                .horizontal()
                .spacing(12.)
                .cross_align(Alignment::Center)
                .child(
                    Avatar::new(account.id.to_string())
                        .width(Size::px(48.))
                        .height(Size::px(48.)),
                )
                .child(
                    rect()
                        .vertical()
                        .spacing(4.)
                        .child(
                            label()
                                .text(account.username.clone())
                                .font_size(text_size(16.))
                                .font_weight(FontWeight::SEMI_BOLD)
                                .color(colors::fg_primary()),
                        )
                        .child(
                            label()
                                .text(account.id.to_string())
                                .font_size(text_size(12.))
                                .color(colors::fg_secondary()),
                        ),
                ),
        )
        .into_element()
}

fn sign_in_card(
    pending: bool,
    error: Option<String>,
    username: State<String>,
    on_add: impl FnMut(Event<PressEventData>) + 'static,
    on_offline: impl FnMut(Event<PressEventData>) + 'static,
) -> impl IntoElement {
    rect()
        .vertical()
        .spacing(12.)
        .cross_align(Alignment::Start)
        .child(
            Button::new()
                .primary()
                .large()
                .enabled(!pending)
                .on_press(on_add)
                .child(Icon::new(IconType::Globe01).size(16.))
                .text(if pending {
                    t("oneclient.onboarding.account.signing_in")
                } else {
                    t("oneclient.onboarding.account.add")
                }),
        )
        .child(
            label()
                .text(t("oneclient.onboarding.account.or_offline"))
                .font_size(text_size(12.))
                .color(colors::fg_secondary()),
        )
        .child(
            rect()
                .horizontal()
                .cross_align(Alignment::Center)
                .spacing(8.)
                .child(
                    rect()
                        .width(Size::px(240.))
                        .child(TextInput::new(username).placeholder(t(
                            "oneclient.settings.accounts.offline.username_placeholder",
                        ))),
                )
                .child(
                    Button::new()
                        .secondary()
                        .on_press(on_offline)
                        .child(Icon::new(IconType::Plus).size(16.))
                        .text(t("oneclient.onboarding.account.add_offline")),
                ),
        )
        .maybe_child(error.map(|message| {
            rect()
                .horizontal()
                .cross_align(Alignment::Center)
                .spacing(6.)
                .child(
                    Icon::new(IconType::AlertTriangle)
                        .size(13.)
                        .color(colors::danger()),
                )
                .child(
                    label()
                        .text(message)
                        .font_size(text_size(12.))
                        .color(colors::danger()),
                )
                .into_element()
        }))
        .into_element()
}
