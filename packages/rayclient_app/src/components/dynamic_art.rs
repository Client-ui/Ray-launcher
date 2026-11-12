use std::path::PathBuf;
use std::sync::LazyLock;

use bytes::Bytes;
use freya::animation::{
    AnimNum, Ease, Function, OnChange, OnCreation, OnFinish, use_animation_with_dependencies,
};
use freya::prelude::*;
use rayclient_common::domain::GameLoader;
use rayclient_common::{VersionKey, parse_mc_version};
use rayclient_core::clusters::Cluster;
use rayclient_core::images::{DEFAULT_IMAGE_EDGE, PREVIEW_IMAGE_EDGE};

use crate::AppAssets;
use crate::hooks::{
    loaded_image, resolve_art_url, settled_or_loading, use_cached_image, use_local_image,
    use_settings_snapshot, use_version_art, use_version_metadata,
};
use crate::layout::HOME_BACKGROUND_ASSET;
use crate::theme::colors;
use crate::ui::ImageFallbackExt;

pub const ART_PREVIEW_EDGE: u32 = PREVIEW_IMAGE_EDGE;

#[derive(PartialEq, Clone)]
pub struct DynamicArt {
    major: Option<u32>,
    key: Option<VersionKey>,
    loader: Option<GameLoader>,
    cover: Option<PathBuf>,
    cover_picked: bool,
    max_edge: u32,
    preview_edge: Option<u32>,
    url: Option<String>,
    skeleton: bool,
    /// Picks which bundled wallpaper stands in when there is no remote or custom art
    seed: u64,
}

impl DynamicArt {
    pub fn for_version(major: u32, key: Option<VersionKey>, loader: Option<GameLoader>) -> Self {
        Self {
            major: Some(major),
            key,
            loader,
            ..Self::fallback()
        }
    }

    pub fn for_cluster(cluster: &Cluster) -> Self {
        let parsed = parse_mc_version(&cluster.mc_version);
        Self {
            major: parsed.as_ref().map(|p| p.major),
            key: parsed.and_then(|p| p.key()),
            loader: Some(cluster.mc_loader),
            cover: cluster.cover_file(),
            seed: cluster.id.unsigned_abs(),
            ..Self::fallback()
        }
    }

    pub fn for_url(url: String) -> Self {
        Self {
            url: Some(url),
            ..Self::fallback()
        }
    }

    pub fn fallback() -> Self {
        Self {
            major: None,
            key: None,
            loader: None,
            cover: None,
            cover_picked: false,
            max_edge: DEFAULT_IMAGE_EDGE,
            preview_edge: None,
            url: None,
            skeleton: false,
            seed: 0,
        }
    }

    /// Choose a different bundled wallpaper, e.g. per card in a list
    #[must_use]
    pub fn seed(mut self, seed: u64) -> Self {
        self.seed = seed;
        self
    }

    #[must_use]
    pub fn cover(mut self, cover: Option<PathBuf>) -> Self {
        self.cover = cover;
        self
    }

    #[must_use]
    pub fn picked_cover(mut self, cover: Option<PathBuf>) -> Self {
        self.cover = cover;
        self.cover_picked = true;
        self
    }

    #[must_use]
    pub fn skeleton(mut self, skeleton: bool) -> Self {
        self.skeleton = skeleton;
        self
    }

    #[must_use]
    pub fn max_edge(mut self, max_edge: u32) -> Self {
        self.max_edge = max_edge;
        self
    }

    /// Stand in with a smaller cached variant until the full-size art downloads
    #[must_use]
    pub fn preview_edge(mut self, preview_edge: u32) -> Self {
        self.preview_edge = Some(preview_edge);
        self
    }

    pub fn use_bytes(&self) -> (String, Bytes) {
        use_art_bytes(self)
    }
}

pub fn use_art_bytes(art: &DynamicArt) -> (String, Bytes) {
    let max_edge = art.max_edge;
    let chosen = use_settings_snapshot().settings.wallpaper;
    use_resolved_art(art).unwrap_or_else(|| {
        chosen_art(max_edge, chosen.as_deref())
            .unwrap_or_else(|| bundled_art(max_edge, art.variant_with(chosen.as_deref())))
    })
}

/// Every wallpaper that ships inside the launcher; picked by seed so instances differ
pub const BUNDLED_WALLPAPERS: [&str; 22] = [
    HOME_BACKGROUND_ASSET,
    "backgrounds/RayAurora.jpg",
    "backgrounds/RayCyber.jpg",
    "backgrounds/RayDawn.jpg",
    "backgrounds/RayDunes.jpg",
    "backgrounds/RayDusk.jpg",
    "backgrounds/RayEmbers.jpg",
    "backgrounds/RayFlare.jpg",
    "backgrounds/RayForest.jpg",
    "backgrounds/RayHorizon.jpg",
    "backgrounds/RayLava.jpg",
    "backgrounds/RayMono.jpg",
    "backgrounds/RayNebula.jpg",
    "backgrounds/RayNeon.jpg",
    "backgrounds/RayOcean.jpg",
    "backgrounds/RayRays.jpg",
    "backgrounds/RaySakura.jpg",
    "backgrounds/RaySparks.jpg",
    "backgrounds/RayStarfield.jpg",
    "backgrounds/RaySunset.jpg",
    "backgrounds/RayTwilight.jpg",
    "backgrounds/RayWaves.jpg",
];

impl DynamicArt {
    /// The user's chosen wallpaper wins over the automatic per-instance pick
    fn variant_with(&self, chosen: Option<&str>) -> usize {
        chosen
            .and_then(|path| BUNDLED_WALLPAPERS.iter().position(|w| *w == path))
            .unwrap_or_else(|| self.variant())
    }

    /// Index into [`BUNDLED_WALLPAPERS`]; mixes the version too so each release differs
    fn variant(&self) -> usize {
        let mut h = self.seed.wrapping_mul(0x9E37_79B9_7F4A_7C15);
        if let Some(major) = self.major {
            h ^= u64::from(major).wrapping_mul(0xC2B2_AE3D_27D4_EB4F);
        }
        if let Some((minor, patch)) = self.key {
            h ^= (u64::from(minor) << 8 | u64::from(patch.unwrap_or(0)))
                .wrapping_mul(0x1656_67B1_9E37_79F9);
        }
        ((h >> 32) as usize) % BUNDLED_WALLPAPERS.len()
    }
}

/// The user's own imported wallpaper, if that is what they picked
fn chosen_art(max_edge: u32, chosen: Option<&str>) -> Option<(String, Bytes)> {
    let chosen = chosen.filter(|path| crate::wallpaper::is_custom(path))?;
    let bytes = crate::wallpaper::bytes_for(chosen)?;
    Some((format!("{max_edge}|{chosen}"), bytes))
}

fn bundled_art(max_edge: u32, variant: usize) -> (String, Bytes) {
    static ART: LazyLock<Vec<Bytes>> = LazyLock::new(|| {
        BUNDLED_WALLPAPERS
            .iter()
            .map(|path| AppAssets::get_bytes(path).unwrap_or_default())
            .collect()
    });
    let index = variant % BUNDLED_WALLPAPERS.len();
    (
        format!("{max_edge}|{}", BUNDLED_WALLPAPERS[index]),
        ART[index].clone(),
    )
}

fn use_resolved_art(art: &DynamicArt) -> Option<(String, Bytes)> {
    let DynamicArt {
        major,
        key,
        loader,
        cover,
        cover_picked,
        max_edge,
        preview_edge,
        url,
        skeleton: _,
        seed: _,
    } = art.clone();

    let cover_query = use_local_image(
        cover.clone().unwrap_or_default(),
        max_edge,
        cover_picked,
        false,
    );

    let cover_bytes = cover.as_ref().and_then(|path| {
        settled_or_loading(&cover_query)
            .filter(|bytes: &Bytes| !bytes.is_empty())
            .map(|bytes| (format!("{max_edge}|{}", path.display()), bytes))
    });

    let curated = use_version_metadata(major, key, loader);
    let candidates = use_version_art(major, key);
    let art_url = url.or_else(|| resolve_art_url(curated.as_ref(), &candidates));

    let image_query = use_cached_image(art_url.clone(), max_edge);

    let preview_edge = preview_edge.filter(|edge| *edge != max_edge);
    let preview_query = match preview_edge {
        Some(edge) => use_cached_image(art_url.clone(), edge),
        None => use_cached_image(None, 0),
    };

    let full = loaded_image(art_url.as_deref(), &image_query)
        .map(|(url, bytes)| (format!("{max_edge}|{url}"), bytes));
    let preview = || {
        let edge = preview_edge?;
        loaded_image(art_url.as_deref(), &preview_query)
            .map(|(url, bytes)| (format!("{edge}|{url}"), bytes))
    };

    cover_bytes.or(full).or_else(preview)
}

impl Component for DynamicArt {
    fn render(&self) -> impl IntoElement {
        let chosen = use_settings_snapshot().settings.wallpaper;
        let resolved = use_resolved_art(self);
        let show_skeleton = self.skeleton && resolved.is_none();
        let (key, bytes) = resolved.clone().unwrap_or_else(|| {
            chosen_art(self.max_edge, chosen.as_deref())
                .unwrap_or_else(|| bundled_art(self.max_edge, self.variant_with(chosen.as_deref())))
        });

        // New art eases in rather than popping, so swapping wallpapers feels smooth
        let fade = use_animation_with_dependencies(&key, |conf, _| {
            conf.on_creation(OnCreation::Run);
            conf.on_change(OnChange::Rerun);
            AnimNum::new(0., 1.)
                .time(420)
                .ease(Ease::Out)
                .function(Function::Cubic)
        });
        let fade_v = fade.read().value();

        let pulse = use_animation_with_dependencies(&show_skeleton, |conf, show| {
            conf.on_change(OnChange::Rerun);

            if *show {
                conf.on_creation(OnCreation::Run);
                conf.on_finish(OnFinish::reverse());
            }

            AnimNum::new(0.4, 0.9)
                .time(800)
                .ease(Ease::InOut)
                .function(Function::Sine)
        });
        let pulse_v = pulse.read().value();

        if show_skeleton {
            return rect()
                .width(Size::fill())
                .height(Size::fill())
                .background(colors::component_bg())
                .opacity(pulse_v)
                .into_element();
        }

        rect()
            .width(Size::fill())
            .height(Size::fill())
            .opacity(fade_v)
            .child(
                ImageViewer::new((key, bytes))
                    .width(Size::fill())
                    .height(Size::fill())
                    .aspect_ratio(AspectRatio::Max)
                    .image_cover(ImageCover::Center)
                    .fallback(rect().width(Size::fill()).height(Size::fill())),
            )
            .into_element()
    }
}
