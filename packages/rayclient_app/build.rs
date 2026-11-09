fn main() {
    #[cfg(windows)]
    {
        let mut res = winresource::WindowsResource::new();
        res.set_icon("icons/icon.ico");

        let version = env!("CARGO_PKG_VERSION");
        res.set("CompanyName", "Ray");
        res.set("ProductName", "Ray Launcher");
        res.set("FileDescription", "Ray Launcher");
        res.set("LegalCopyright", "© 2026 Ray. Based on OneLauncher © Polyfrost Inc. (GPL-3.0)");
        res.set("OriginalFilename", "rayclient_app.exe");
        res.set("InternalName", "rayclient_app");
        res.set("FileVersion", version);
        res.set("ProductVersion", version);

        res.compile()
            .expect("failed to embed Windows icon resource");
    }
}
