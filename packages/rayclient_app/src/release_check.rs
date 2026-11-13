//! Looks at the GitHub Releases page for a newer launcher and tells the user about it

use rayclient_events::EventBus;

use crate::constants::{RELEASES_REPO, updates_configured};
use crate::i18n::{t, tf};

pub fn spawn(events: EventBus) {
    if RELEASES_REPO.is_empty() || updates_configured() {
        tracing::info!("release check skipped: not configured or the signed updater is active");
        return;
    }
    if std::env::var_os("RAY_DISABLE_AUTOUPDATE").is_some_and(|val| val.eq_ignore_ascii_case("1")) {
        return;
    }

    tokio::spawn(async move {
        if let Err(err) = run(events).await {
            tracing::debug!("release check failed: {err:#}");
        }
    });
}

async fn run(events: EventBus) -> anyhow::Result<()> {
    let state = crate::launcher::state()?;
    let release = state
        .services
        .requester
        .latest_github_release(RELEASES_REPO)
        .await?;
    if release.draft || release.prerelease {
        return Ok(());
    }

    let latest = release.tag_name.trim_start_matches(['v', 'V']).to_string();
    if !is_newer(&latest, env!("CARGO_PKG_VERSION")) {
        tracing::info!("launcher is up to date ({latest})");
        return Ok(());
    }

    events
        .notify(t("oneclient.updater.available.title"))
        .body(tf(
            "oneclient.updater.manual.body",
            &[&latest, &release.html_url],
        ))
        .link(release.html_url.clone())
        .send();
    Ok(())
}

fn parts(version: &str) -> Vec<u64> {
    version
        .split(['.', '-', '+'])
        .map_while(|part| part.parse::<u64>().ok())
        .collect()
}

fn is_newer(latest: &str, current: &str) -> bool {
    parts(latest) > parts(current)
}

#[cfg(test)]
mod tests {
    use super::is_newer;

    #[test]
    fn compares_numerically() {
        assert!(is_newer("2.10.0", "2.9.0"));
        assert!(is_newer("3.0.0", "2.9.9"));
        assert!(!is_newer("2.9.0", "2.9.0"));
        assert!(!is_newer("2.8.5", "2.9.0"));
    }
}
