%global debug_package %{nil}
%global __strip /bin/true
%global _appname RayLauncher
%global _rpmfile %{_appname}_%{version}_linux_x86_64.rpm

Name:           rayclient-bin
Version:        2.0.1
Release:        1%{?dist}
Summary:        Next-generation open source Minecraft launcher (prebuilt)

License:        GPL-3.0-only
URL:            https://github.com/your-org/RayLauncher
Source0:        %{url}/releases/download/rayclient-%{version}/%{_rpmfile}

ExclusiveArch:  x86_64
BuildRequires:  bsdtar
Requires:       libxdo
Requires:       dbus-libs
Provides:       rayclient = %{version}-%{release}

%description
RayLauncher is a next-generation open source Minecraft launcher.
This package ships the prebuilt binaries from the upstream release.

%prep
%setup -q -c -T
# Repackages the upstream release rpm; bsdtar reads its cpio payload directly.
bsdtar -xf %{SOURCE0}

%install
mkdir -p %{buildroot}
cp -a usr %{buildroot}/
ln -s rayclient_app %{buildroot}%{_bindir}/rayclient

%files
%{_bindir}/rayclient_app
%{_bindir}/rayclient
%{_datadir}/applications/*.desktop
%{_datadir}/icons/hicolor/*/apps/*

%changelog
* Wed Sep 09 2026 Ray <maintainer@example.com> - 2.0.1-1
- See upstream release notes.
