pub const WINDOW_APP_ID: &str = "rayclient_app";
pub const WINDOW_TITLE: &str = "Ray Launcher";

// Self-update is only active when a signed update feed is supplied at build time
// (RAY_UPDATER_ENDPOINT + RAY_UPDATER_PUBKEY). Without them the updater stays off, so a
// build can never replace itself with a differently branded binary.
pub const UPDATER_PUBKEY: &str = match option_env!("RAY_UPDATER_PUBKEY") {
    Some(key) => key,
    None => "",
};
pub const UPDATER_ENDPOINT: &str = match option_env!("RAY_UPDATER_ENDPOINT") {
    Some(url) => url,
    None => "",
};
pub const RELEASES_URL: &str = match option_env!("RAY_RELEASES_URL") {
    Some(url) => url,
    None => "https://github.com/your-org/RayLauncher/releases/latest",
};

#[allow(clippy::const_is_empty)]
pub const fn updates_configured() -> bool {
    !UPDATER_ENDPOINT.is_empty() && !UPDATER_PUBKEY.is_empty()
}
