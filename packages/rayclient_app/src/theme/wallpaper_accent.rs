use std::collections::HashMap;
use std::sync::{LazyLock, Mutex};

static CACHE: LazyLock<Mutex<HashMap<String, Option<String>>>> =
    LazyLock::new(|| Mutex::new(HashMap::new()));

/// Dominant vivid colour of a bundled wallpaper as `#RRGGBB`, cached per wallpaper
pub fn accent_for(path: &str) -> Option<String> {
    let mut cache = CACHE.lock().ok()?;
    cache
        .entry(path.to_string())
        .or_insert_with(|| compute(path))
        .clone()
}

fn compute(path: &str) -> Option<String> {
    let bytes = crate::wallpaper::bytes_for(path)?;
    let image = image::load_from_memory(&bytes)
        .ok()?
        .thumbnail(48, 48)
        .to_rgb8();

    const BINS: usize = 12;
    let mut weight = [0f32; BINS];
    let mut sum = [[0f32; 3]; BINS];
    for pixel in image.pixels() {
        let (h, s, v) = rgb_to_hsv(pixel[0], pixel[1], pixel[2]);
        if s < 0.25 || v < 0.25 {
            continue;
        }
        let bin = ((h / 360.0) * BINS as f32) as usize % BINS;
        let w = s * v;
        weight[bin] += w;
        for (channel, value) in sum[bin].iter_mut().zip(pixel.0) {
            *channel += f32::from(value) * w;
        }
    }

    let best = (0..BINS).max_by(|a, b| weight[*a].total_cmp(&weight[*b]))?;
    if weight[best] <= 0.0 {
        return None;
    }
    let avg = |i: usize| (sum[best][i] / weight[best]).round().clamp(0., 255.) as u8;
    let (h, s, v) = rgb_to_hsv(avg(0), avg(1), avg(2));
    // Keep it vivid and bright enough to read on dark surfaces
    let (r, g, b) = hsv_to_rgb(h, s.max(0.6), v.max(0.85));
    Some(format!("#{r:02X}{g:02X}{b:02X}"))
}

fn rgb_to_hsv(r: u8, g: u8, b: u8) -> (f32, f32, f32) {
    let (r, g, b) = (
        f32::from(r) / 255.,
        f32::from(g) / 255.,
        f32::from(b) / 255.,
    );
    let max = r.max(g).max(b);
    let min = r.min(g).min(b);
    let d = max - min;
    let h = if d == 0. {
        0.
    } else if max == r {
        60. * (((g - b) / d).rem_euclid(6.))
    } else if max == g {
        60. * ((b - r) / d + 2.)
    } else {
        60. * ((r - g) / d + 4.)
    };
    let s = if max == 0. { 0. } else { d / max };
    (h, s, max)
}

fn hsv_to_rgb(h: f32, s: f32, v: f32) -> (u8, u8, u8) {
    let c = v * s;
    let x = c * (1. - ((h / 60.) % 2. - 1.).abs());
    let m = v - c;
    let (r, g, b) = match (h / 60.) as u32 {
        0 => (c, x, 0.),
        1 => (x, c, 0.),
        2 => (0., c, x),
        3 => (0., x, c),
        4 => (x, 0., c),
        _ => (c, 0., x),
    };
    let to = |value: f32| ((value + m) * 255.).round().clamp(0., 255.) as u8;
    (to(r), to(g), to(b))
}
