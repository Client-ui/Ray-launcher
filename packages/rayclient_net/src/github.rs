use serde::Deserialize;

use crate::{RequestClient, RequestError};

#[derive(Debug, Clone, Deserialize)]
pub struct GithubRelease {
    pub tag_name: String,
    pub html_url: String,
    #[serde(default)]
    pub prerelease: bool,
    #[serde(default)]
    pub draft: bool,
}

impl RequestClient {
    /// The newest published, non-prerelease release of `repo` (`owner/name`)
    pub async fn latest_github_release(&self, repo: &str) -> Result<GithubRelease, RequestError> {
        let request = self
            .http()
            .get(format!(
                "https://api.github.com/repos/{repo}/releases/latest"
            ))
            .header("Accept", "application/vnd.github+json")
            .header("User-Agent", "RayLauncher")
            .build()?;
        self.send_as(request).await
    }
}
