%bcond_without check

#global rc_ver 1
%global lld_srcdir lld-%{maj_ver}.%{min_ver}.%{patch_ver}%{?rc_ver:rc%{rc_ver}}.src
%global maj_ver 15
%global min_ver 0
%global patch_ver 7

# Don't include unittests in automatic generation of provides or requires.
%global __provides_exclude_from ^%{_libdir}/lld/.*$
%global __requires_exclude ^libgtest.*$

%bcond_with ld_alternative
%bcond_with testpkg

Name:		lld
Version:	%{maj_ver}.%{min_ver}.%{patch_ver}%{?rc_ver:~rc%{rc_ver}}
Release:	1%{?rc_ver:.rc%{rc_ver}}%{?dist}
Summary:	The LLVM Linker

License:	NCSA
URL:		http://llvm.org
Source0:	https://github.com/llvm/llvm-project/releases/download/llvmorg-%{maj_ver}.%{min_ver}.%{patch_ver}%{?rc_ver:-rc%{rc_ver}}/%{lld_srcdir}.tar.xz
Source1:	https://github.com/llvm/llvm-project/releases/download/llvmorg-%{maj_ver}.%{min_ver}.%{patch_ver}%{?rc_ver:-rc%{rc_ver}}/%{lld_srcdir}.tar.xz.sig
Source2:	release-keys.asc
Source3:	run-lit-tests
Source4:	lit.lld-test.cfg.py

ExcludeArch:	s390x

Patch0:		0001-PATCH-lld-CMake-Check-for-gtest-headers-even-if-lit..patch

# Bundle libunwind header need during build for MachO support
Patch1:		0002-PATCH-lld-Import-compact_unwind_encoding.h-from-libu.patch

BuildRequires:	gcc
BuildRequires:	gcc-c++
BuildRequires:	cmake
BuildRequires:	ninja-build
BuildRequires:	llvm-devel = %{version}
BuildRequires:	llvm-test = %{version}
BuildRequires:	ncurses-devel
BuildRequires:	zlib-devel
BuildRequires:	python3-devel

# For make check:
BuildRequires:	python3-rpm-macros
BuildRequires:	python3-lit
BuildRequires:	llvm-googletest = %{version}

# For gpg source verification
BuildRequires:	gnupg2

%if %{with ld_alternative}
Requires(post): %{_sbindir}/alternatives
Requires(preun): %{_sbindir}/alternatives
%endif

Requires: lld-libs = %{version}-%{release}

%description
The LLVM project linker.

%package devel
Summary:	Libraries and header files for LLD
Requires: lld-libs%{?_isa} = %{version}-%{release}
# lld tools are referenced in the cmake files, so we need to add lld as a
# dependency.
Requires: %{name}%{?_isa} = %{version}-%{release}

%description devel
This package contains library and header files needed to develop new native
programs that use the LLD infrastructure.

%package libs
Summary:	LLD shared libraries

%description libs
Shared libraries for LLD.

%if %{with testpkg}
%package test
Summary: LLD regression tests
Requires:	%{name}%{?_isa} = %{version}-%{release}
Requires:	python3-lit
Requires:	llvm-test(major) = %{maj_ver}
Requires:	lld-libs = %{version}-%{release}

%description test
LLVM regression tests.
%endif

%prep
%{gpgverify} --keyring='%{SOURCE2}' --signature='%{SOURCE1}' --data='%{SOURCE0}'
%autosetup -n %{lld_srcdir} -p2


%build

# Disable lto since it causes the COFF/libpath.test lit test to crash.
%global _lto_cflags %{nil}

mkdir -p %{_vpath_builddir}
cd %{_vpath_builddir}

%cmake .. \
	-GNinja \
	-DLLVM_LINK_LLVM_DYLIB:BOOL=ON \
	-DLLVM_DYLIB_COMPONENTS="all" \
	-DCMAKE_SKIP_RPATH:BOOL=ON \
	-DPYTHON_EXECUTABLE=%{__python3} \
	-DLLVM_INCLUDE_TESTS=ON \
	-DLLVM_MAIN_SRC_DIR=%{_datadir}/llvm/src \
	-DLLVM_EXTERNAL_LIT=%{_bindir}/lit \
	-DLLVM_LIT_ARGS="-sv \
	--path %{_libdir}/llvm" \
%if 0%{?__isa_bits} == 64
	-DLLVM_LIBDIR_SUFFIX=64
%else
	-DLLVM_LIBDIR_SUFFIX=
%endif

%cmake_build

%if %{with testpkg}
# Build the unittests so we can install them.
%cmake_build --target lld-test-depends
%endif

%install
%if %{with testpkg}
%global lit_cfg test/%{_arch}.site.cfg.py
%global lit_unit_cfg test/Unit/%{_arch}.site.cfg.py
%global lit_lld_test_cfg_install_path %{_datadir}/lld/lit.lld-test.cfg.py

# Generate lit config files.  Strip off the last line that initiates the
# test run, so we can customize the configuration.
head -n -1 %{__cmake_builddir}/test/lit.site.cfg.py >> %{lit_cfg}
head -n -1 %{__cmake_builddir}/test/Unit/lit.site.cfg.py >> %{lit_unit_cfg}

# Patch lit config files to load custom config:
for f in %{lit_cfg} %{lit_unit_cfg}; do
  echo "lit_config.load_config(config, '%{lit_lld_test_cfg_install_path}')" >> $f
done

# Install test files
install -d %{buildroot}%{_datadir}/lld/src
cp %{SOURCE4} %{buildroot}%{_datadir}/lld/

# The various tar options are there to make sur the archive is the same on 32 and 64 bit arch, i.e.
# the archive creation is reproducible. Move arch-specific content out of the tarball
mv %{lit_cfg} %{buildroot}%{_datadir}/lld/src/%{_arch}.site.cfg.py
mv %{lit_unit_cfg} %{buildroot}%{_datadir}/lld/src/%{_arch}.Unit.site.cfg.py
tar --sort=name --mtime='UTC 2020-01-01' -c test/ | gzip -n > %{buildroot}%{_datadir}/lld/src/test.tar.gz

install -d %{buildroot}%{_libexecdir}/tests/lld
install -m 0755 %{SOURCE3} %{buildroot}%{_libexecdir}/tests/lld

# Install unit test binaries
install -d %{buildroot}%{_libdir}/lld/

rm -rf `find %{buildroot}%{_libdir}/lld/ -iname '*make*'`

# Install gtest libraries
cp %{__cmake_builddir}/%{_lib}/libgtest*so* %{buildroot}%{_libdir}/lld/
%endif

# Install libraries and binaries
pushd %{_vpath_builddir}
%cmake_install
popd


# This is generated by Patch1 during build and (probably) must be removed afterward
rm %{buildroot}%{_includedir}/mach-o/compact_unwind_encoding.h

%if %{with ld_alternative}
# Required when using update-alternatives:
# https://docs.fedoraproject.org/en-US/packaging-guidelines/Alternatives/
touch %{buildroot}%{_bindir}/ld

%post
%{_sbindir}/update-alternatives --install %{_bindir}/ld ld %{_bindir}/ld.lld 1

%postun
if [ $1 -eq 0 ] ; then
  %{_sbindir}/update-alternatives --remove ld %{_bindir}/ld.lld
fi
%endif

%check
cd %{_vpath_builddir}

# armv7lhl tests disabled because of arm issue, see https://koji.fedoraproject.org/koji/taskinfo?taskID=33660162
%ifnarch %{arm}
%if %{with check}
%cmake_build --target check-lld
%endif
%endif

%ldconfig_scriptlets libs

%files
%license LICENSE.TXT
%if %{with ld_alternative}
%ghost %{_bindir}/ld
%endif
%{_bindir}/lld*
%{_bindir}/ld.lld
%{_bindir}/ld64.lld
%{_bindir}/wasm-ld

%files devel
%{_includedir}/lld
%{_libdir}/liblld*.so
%{_libdir}/cmake/lld/

%files libs
%{_libdir}/liblld*.so.*

%if %{with testpkg}
%files test
%{_libexecdir}/tests/lld/
%{_libdir}/lld/
%{_datadir}/lld/src/test.tar.gz
%{_datadir}/lld/src/%{_arch}.site.cfg.py
%{_datadir}/lld/src/%{_arch}.Unit.site.cfg.py
%{_datadir}/lld/lit.lld-test.cfg.py
%endif

%changelog
* Thu Jan 19 2023 Tom Stellard <tstellar@redhat.com> - 15.0.7-1
- Update to LLVM 15.0.7

* Tue Sep 06 2022 Nikita Popov <npopov@redhat.com> - 15.0.0-1
- Update to LLVM 15.0.0

* Tue Jun 28 2022 Tom Stellard <tstellar@redhat.com> - 14.0.6-1
- 14.0.6 Release

* Fri May 06 2022 Timm Bäder <tbaeder@redhat.com> - 14.0.0-2
- Backport ignoring --no-add-needed

* Thu Apr 07 2022 Timm Bäder <tbaeder@redhat.com> - 14.0.0-1
- Update to 14.0.0

* Thu Feb 03 2022 Tom Stellard <tstellar@redhat.com> - 13.0.1-1
- 13.0.1 Release

* Thu Dec 09 2021 Tom Stellard <tstellar@redhat.com> - 13.0.0-2
- Drop lld-test package

* Fri Oct 15 2021 Tom Stellard <tstellar@redhat.com> - 13.0.0-1
- 13.0.0 Release

* Fri Jul 16 2021 sguelton@redhat.com - 12.0.1-1
- 12.0.1 release

* Thu May 6 2021 sguelton@redhat.com - 12.0.0-1
- 12.0.0 release

* Mon Nov 09 2020 sguelton@redhat.com - 11.0.0-3
- Exclude s390x, see rhbz#1894927

* Thu Oct 29 2020 sguelton@redhat.com - 11.0.0-1
- 11.0.0 final

* Fri Sep 18 2020 sguelton@redhat.com - 11.0.0-0.1.rc2
- 11.0.0-rc2 Release

* Fri Jul 24 2020 sguelton@redhat.com - 10.0.1-1
- 10.0.1 release

* Mon Jul 20 2020 sguelton@redhat.com - 10.0.0-2
- Fix arch-dependent tarball

* Thu Apr 9 2020 sguelton@redhat.com - 10.0.0-1
- 10.0.0 final

* Thu Dec 19 2019 Tom Stellard <tstellar@redhat.com> -9.0.1-1
- 9.0.1 Release

* Fri Dec 13 2019 Tom Stellard <tstellar@redhat.com> - 9.0.0-5
- Fix some rpmdiff errors

* Fri Dec 13 2019 Tom Stellard <tstellar@redhat.com> - 9.0.0-4
- Remove build artifacts installed with unittests

* Thu Dec 05 2019 Tom Stellard <tstellar@redhat.com> - 9.0.0-3
- Add lld-test package

* Thu Nov 14 2019 Tom Stellard <tstellar@redhat.com> - 9.0.0-2
- Add explicit lld-libs requires to fix rpmdiff errors

* Thu Sep 26 2019 Tom Stellard <tstellar@redhat.com> - 9.0.0-1
- 9.0.0 Release

* Thu Aug 1 2019 sguelton@redhat.com - 8.0.1-1
- 8.0.1 release

* Mon Jun 17 2019 sguelton@redhat.com - 8.0.1-0.2.rc2
- Remove unnecessary threading patch

* Thu Jun 13 2019 sguelton@redhat.com - 8.0.1-0.1.rc2
- 8.0.1rc2 Release

* Tue Apr 16 2019 sguelton@redhat.com - 8.0.0-1
- 8.0.0 Release

* Mon Jan 14 2019 sguelton@redhat.com - 7.0.1-3
- Fix lld + annobin integration & Setup basic CI tests

* Sat Dec 15 2018 Tom Stellard <tstellar@redhat.com> - 7.0.1-2
- Bump required python3-lit version

* Fri Dec 14 2018 Tom Stellard <tstellar@redhat.com> - 7.0.1-1
- 7.0.1-1 Release

* Mon Dec 10 2018 Tom Stellard <tstellar@redhat.com> - 7.0.1-0.2.rc3
- 7.0.1-rc3 Release

* Tue Nov 27 2018 Tom Stellard <tstellar@redhat.com> - 7.0.0-1
- 7.0.0 Release

* Mon Oct 01 2018 Tom Stellard <tstellar@redhat.com> - 6.0.1-2
- Drop scl macros

* Wed Jun 27 2018 Tom Stellard <tstellar@redhat.com> - 6.0.1-1
- 6.0.1 Release

* Fri May 11 2018 Tom Stellard <tstellar@redhat.com> - 6.0.1-0.1.rc1
- 6.0.1-rc1 Release

* Thu Mar 08 2018 Tom Stellard <tstellar@redhat.com> - 6.0.0-1
- 6.0.0 Release

* Tue Feb 13 2018 Tom Stellard <tstellar@redhat.com> - 6.0.0-0.3.rc2
- 6.0.0-rc2 Release

* Thu Feb 08 2018 Fedora Release Engineering <releng@fedoraproject.org> - 6.0.0-0.2.rc1
- Rebuilt for https://fedoraproject.org/wiki/Fedora_28_Mass_Rebuild

* Thu Jan 25 2018 Tom Stellard <tstellar@redhat.com> - 6.0.0-0.1.rc1
- 6.0.0-rc1 Release

* Thu Dec 21 2017 Tom Stellard <tstellar@redhat.com> - 5.0.1-1
- 5.0.1 Release

* Mon Sep 11 2017 Tom Stellard <tstellar@redhat.com> - 5.0.0-1
- 5.0.0 Release

* Thu Aug 03 2017 Fedora Release Engineering <releng@fedoraproject.org> - 4.0.1-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Binutils_Mass_Rebuild

* Wed Jul 26 2017 Fedora Release Engineering <releng@fedoraproject.org> - 4.0.1-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Thu Jul 06 2017 Tom Stellard <tstellar@redhat.com> - 4.0.1-2
- Backport r307092

* Tue Jul 04 2017 Tom Stellard <tstellar@redhat.com> - 4.0.1-1
- 4.0.1 Release

* Tue Jul 04 2017 Tom Stellard <tstellar@redhat.com> - 4.0.0-4
- Fix build without llvm-static

* Wed May 31 2017 Tom Stellard <tstellar@redhat.com> - 4.0.0-3
- Remove llvm-static dependency

* Mon May 15 2017 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 4.0.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_27_Mass_Rebuild

* Tue Mar 14 2017 Tom Stellard <tstellar@redhat.com> - 4.0.0-1
- lld 4.0.0 Final Release
