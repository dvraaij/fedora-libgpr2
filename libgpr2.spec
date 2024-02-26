# The test suite is normally run. It can be disabled with "--without=check".
%bcond_without check

# Upstream source information.
%global upstream_owner         AdaCore
%global upstream_name          gpr
%global upstream_version       24.0.0
%global upstream_release_date  20230920
%global upstream_gittag        v%{upstream_version}

Name:           libgpr2
Version:        %{upstream_version}
Release:        1%{?dist}
Summary:        The GNAT project manager library

License:        Apache-2.0 WITH LLVM-Exception

URL:            https://github.com/%{upstream_owner}/%{upstream_name}
Source:         %{url}/archive/%{upstream_gittag}/%{upstream_name}-%{upstream_version}.tar.gz

# [Fedora-specific] Link all tools dynamically.
Patch:          %{name}-link-tools-dynamically.patch
# [Fedora-specific] Set the library so version.
Patch:          %{name}-set-library-so-version.patch
# [Fedora-specific] Customize testing for Fedora.
Patch:          %{name}-adapt-tests-for-fedora.patch

BuildRequires:  gcc-gnat gprbuild make sed
# A fedora-gnat-project-common that contains GPRbuild_flags is needed.
BuildRequires:  fedora-gnat-project-common >= 3.17
BuildRequires:  gprconfig-kb
BuildRequires:  gnatcoll-core-devel
BuildRequires:  gnatcoll-gmp-devel
BuildRequires:  gnatcoll-iconv-devel
%if %{with check}
BuildRequires:  python-devel
BuildRequires:  python-setuptools
BuildRequires:  python3-e3-testsuite
%endif

# Build only on architectures where GPRbuild is available.
ExclusiveArch:  %{GPRbuild_arches}

# Cannot be installed with the "next" version of libgpr2.
Conflicts:      libgpr2_next

%global common_description_en \
An Ada library for handling GNAT project files.

%description %{common_description_en}


#################
## Subpackages ##
#################

%package devel
Summary:        Development files for the GNAT project manager library
Requires:       %{name}%{?_isa} = %{version}-%{release}
Requires:       fedora-gnat-project-common
Requires:       libgpr-devel
Requires:       gnatcoll-core-devel
Requires:       gnatcoll-gmp-devel
Requires:       gnatcoll-iconv-devel
Requires:       xmlada-devel

%description devel %{common_description_en}

This package contains source code and linking information for developing
applications that use the GNAT project manager library.


%package tools
Summary:        Tools based the GNAT project manager library
License:        GPL-3.0-or-later
Requires:       %{name}%{?_isa} = %{version}-%{release}
Requires:       fedora-gnat-project-common
# These tools replace their former versions.
Conflicts:      gprbuild

%description tools %{common_description_en}

This package contains tools to manage and build GNAT projects. Most of these
tools superseed the tools provided in package gprbuild.

#############
## Prepare ##
#############

%prep
%autosetup -n %{upstream_name}-%{upstream_version} -p1

# Update some release specific information in the source code. The substitutions
# are scoped to specific lines to increase the chance of detecting code changes
# at this point. Sed should exit with exit code 0 if the substitution succeeded
# (using `t`, jump to end of script) or exit with a non-zero exit code if the
# substitution failed (using `q1`, quit with exit code 1).
sed --in-place \
    --expression='11 { s,18.0w,%{upstream_version},         ; t; q1 }' \
    --expression='14 { s,19940713,%{upstream_release_date}, ; t; q1 }' \
    --expression='16 { s,"2016",Date (1 .. 4),              ; t; q1 }' \
    --expression='21 { s,Gnatpro,GPL,                       ; t; q1 }' \
    src/lib/gpr2-version.ads

# Initialize some variables.
make LIBGPR2_TYPES='relocatable' PYTHON='%{python3}' \
     GPR2KBDIR='%{_datadir}/gprconfig' FORCE_PARSER_GEN=force \
     setup


###########
## Build ##
###########

%build

export VERSION=%{version}

# Build the library.
%{make_build} GPRBUILD_OPTIONS='%{GPRbuild_flags}' build-lib-relocatable

# Additional flags to link the executables dynamically with the GNAT runtime
# and make the executables (tools) position independent.
%global GPRbuild_flags_pie -cargs -fPIC -largs -pie -bargs -shared -gargs

# Build the tools.
%{make_build} GPRBUILD_OPTIONS='%{GPRbuild_flags} %{GPRbuild_flags_pie} \
              -XGPR2_EDGE_TOOLS_PREFIX="gpr"' build-tools


#############
## Install ##
#############

%install

# Install the library.
gprinstall %{GPRinstall_flags} --no-build-var \
           -XVERSION=%{version} -XGPR2_BUILD=release \
           -XLIBRARY_TYPE=relocatable -XXMLADA_BUILD=relocatable \
           -P gpr2.gpr

# Install the tools.
gprinstall --create-missing-dirs --no-manifest \
           --prefix=%{buildroot}%{_prefix} --mode=usage \
           -XVERSION=%{version} -XGPR2_BUILD=release -XGPR2_EDGE_TOOLS_PREFIX="gpr" \
           -XLIBRARY_TYPE=relocatable -XXMLADA_BUILD=relocatable \
           -P tools/gpr2-tools.gpr

# Fix up some things that GPRinstall does wrong.
ln --symbolic --force %{name}.so.%{version} %{buildroot}%{_libdir}/%{name}.so

# Make the generated usage project file architecture-independent.
sed --regexp-extended --in-place \
    '--expression=1i with "directories";' \
    '--expression=/^--  This project has been generated/d' \
    '--expression=s|^( *for +Source_Dirs +use +).*;$|\1(Directories.Includedir \& "/%{name}");|i' \
    '--expression=s|^( *for +Library_Dir +use +).*;$|\1Directories.Libdir;|i' \
    '--expression=s|^( *for +Library_ALI_Dir +use +).*;$|\1Directories.Libdir \& "/%{name}";|i' \
    %{buildroot}%{_GNAT_project_dir}/gpr2.gpr
# The Sed commands are:
# 1: Insert a with clause before the first line to import the directories
#    project.
# 2: Delete a comment that mentions the architecture.
# 3: Replace the value of Source_Dirs with a pathname based on
#    Directories.Includedir.
# 4: Replace the value of Library_Dir with Directories.Libdir.
# 5: Replace the value of Library_ALI_Dir with a pathname based on
#    Directories.Libdir.

cat %{buildroot}%{_GNAT_project_dir}/gpr2.gpr


###########
## Check ##
###########

%if %{with check}
%check

# Create an override for directories.gpr.
mkdir testsuite/multilib
cat << EOF > ./testsuite/multilib/directories.gpr
abstract project Directories is
   Libdir     := "%{buildroot}%{_libdir}";
   Includedir := "%{buildroot}%{_includedir}";
end Directories;
EOF

# Make the files installed in the buildroot and the override for directories.gpr
# visible to the test runner.
export PATH=%{buildroot}%{_bindir}:$PATH
export LIBRARY_PATH=%{buildroot}%{_libdir}:$LIBRARY_PATH
export LD_LIBRARY_PATH=%{buildroot}%{_libdir}:$LD_LIBRARY_PATH
export GPR_PROJECT_PATH=${PWD}/testsuite/multilib:%{buildroot}%{_GNAT_project_dir}:$GPR_PROJECT_PATH
export PYTHONPATH=%{buildroot}%{python3_sitearch}:%{buildroot}%{python3_sitelib}:$PYTHONPATH

# Rename gprbuild to gpr2build. This alternative name is used by upstream during
# development and testing. It prevents the executable from interfering with the
# "classic" gprbuild.
mv %{buildroot}%{_bindir}/gprbuild \
   %{buildroot}%{_bindir}/gpr2build

# Run the tests.
%python3 testsuite/testsuite.py \
         --show-error-output \
         --max-consecutive-failures=4

# Undo rename.
mv %{buildroot}%{_bindir}/gpr2build \
   %{buildroot}%{_bindir}/gprbuild

%endif


###########
## Files ##
###########

%files
%license LICENSE
%doc README*
%{_libdir}/%{name}.so.%{version}


%files devel
%{_GNAT_project_dir}/gpr2.gpr
%{_includedir}/%{name}
%dir %{_libdir}/%{name}
%attr(444,-,-) %{_libdir}/%{name}/*.ali
%{_libdir}/%{name}.so


%files tools
%license COPYING3
%{_bindir}/gprbuild
%{_bindir}/gprclean
%{_bindir}/gprconfig
%{_bindir}/gprdoc
%{_bindir}/gprdump
%{_bindir}/gprinspect
%{_bindir}/gprinstall
%{_bindir}/gprls
%{_bindir}/gprremote


###############
## Changelog ##
###############

%changelog
* Sun Dec 03 2023 Dennis van Raaij <dvraaij@fedoraproject.org> - 24.0.0-1
- Updated to v24.0.0.
- Updated license: LLVM exception added to library package.
- Removed the gprname tool; it's no longer available (commit 8c5980f).
- Removed build dependency on 'libadalang-devel'.
- Added new build dependency on GNATcoll (core, GMP and iconv).

* Thu Mar 09 2023 Dennis van Raaij <dvraaij@fedoraproject.org> - 23.0.0-1
- New package.
