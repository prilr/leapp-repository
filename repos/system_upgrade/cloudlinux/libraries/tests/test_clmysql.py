import os

import pytest

from leapp.libraries.common.clmysql import (
    ClMysqlTypeStatus,
    _clmysql_name_version_from_rpm,
    _get_clmysql_type_from_governor,
    _resolve_mysqld_path,
    get_clmysql_type,
    get_clmysql_version_from_pkg,
    clmysql_module_stream_from_url,
    get_pkg_prefix,
    parse_clmysql_repo_url,
    parse_clmysql_type,
    resolve_clmysql_module_stream,
)


# ---------------------------------------------------------------------------
# normalize_clmysql_type
# ---------------------------------------------------------------------------

class TestParseClmysqlType(object):
    """
    CLOS-6809: Governor spells the same version two ways - it accepts and publishes
    mariadb1104, but caches mariadb114 in mysql.type.installed after re-deriving the
    token from the RPM version. Parsing to a numeric triple has to make them equal,
    without a table of Governor's spellings to keep in sync.
    """

    @pytest.mark.parametrize(
        "clmysql_type,expected",
        [
            ("mysql56", ("mysql", 5, 6)),
            ("mysql80", ("mysql", 8, 0)),
            ("mysql84", ("mysql", 8, 4)),
            ("mariadb102", ("mariadb", 10, 2)),
            ("mariadb106", ("mariadb", 10, 6)),
            ("mariadb1011", ("mariadb", 10, 11)),
            ("mariadb1104", ("mariadb", 11, 4)),
            ("mariadb1108", ("mariadb", 11, 8)),
            ("percona56", ("percona", 5, 6)),
        ],
    )
    def test_canonical_tokens(self, clmysql_type, expected):
        assert parse_clmysql_type(clmysql_type) == expected

    @pytest.mark.parametrize(
        "lossy,canonical",
        [
            ("mariadb114", "mariadb1104"),
            ("mariadb118", "mariadb1108"),
        ],
    )
    def test_both_spellings_are_the_same_version(self, lossy, canonical):
        assert parse_clmysql_type(lossy) == parse_clmysql_type(canonical)

    def test_future_series_needs_no_table_entry(self):
        """The 11.x padding trap must not come back for a series nobody listed yet."""
        assert parse_clmysql_type("mariadb124") == parse_clmysql_type("mariadb1204")
        assert parse_clmysql_type("mariadb124") == ("mariadb", 12, 4)

    @pytest.mark.parametrize(
        "clmysql_type",
        [None, "", "auto", "postgres15", "maria-db103"],
    )
    def test_unrecognised(self, clmysql_type):
        assert parse_clmysql_type(clmysql_type) is None


# ---------------------------------------------------------------------------
# parse_clmysql_repo_url
# ---------------------------------------------------------------------------

class TestParseClmysqlRepoUrl(object):

    @pytest.mark.parametrize(
        "baseurl,expected",
        [
            ("http://repo.cloudlinux.com/other/cl$releasever/mysqlmeta/cl-mariadb-11.04/$basearch/",
             ("mariadb", 11, 4)),
            ("http://repo.cloudlinux.com/other/cl$releasever/mysqlmeta/cl-mariadb-11.08/$basearch/",
             ("mariadb", 11, 8)),
            ("http://repo.cloudlinux.com/other/cl$releasever/mysqlmeta/cl-mariadb-10.6/$basearch/",
             ("mariadb", 10, 6)),
            ("http://repo.cloudlinux.com/other/cl$releasever/mysqlmeta/cl-mariadb-10.11/$basearch/",
             ("mariadb", 10, 11)),
            ("http://repo.cloudlinux.com/other/cl$releasever/mysqlmeta/cl-mysql-8.0/$basearch/",
             ("mysql", 8, 0)),
            ("http://repo.cloudlinux.com/other/cl$releasever/mysqlmeta/cl-percona-5.6/$basearch/",
             ("percona", 5, 6)),
        ],
    )
    def test_known_urls(self, baseurl, expected):
        assert parse_clmysql_repo_url(baseurl) == expected

    def test_padding_is_irrelevant(self):
        """11.04 and 11.4 in a URL describe the same version."""
        base = "http://repo.cloudlinux.com/other/cl8/mysqlmeta/cl-mariadb-{}/x86_64/"
        assert parse_clmysql_repo_url(base.format("11.04")) == parse_clmysql_repo_url(base.format("11.4"))

    @pytest.mark.parametrize(
        "baseurl",
        [None, "", "http://repo.cloudlinux.com/other/cl8/mysqlmeta/mysqlclient/x86_64/"],
    )
    def test_unrecognised(self, baseurl):
        assert parse_clmysql_repo_url(baseurl) is None


# ---------------------------------------------------------------------------
# resolve_clmysql_module_stream
# ---------------------------------------------------------------------------

class TestResolveClmysqlModuleStream(object):
    """Test explicit MODULE_STREAMS lookup and regex fallback."""

    @pytest.mark.parametrize(
        "clmysql_type,expected",
        [
            # Explicit MODULE_STREAMS entries
            ("mysql55", ("mysql", "cl-MySQL55")),
            ("mysql80", ("mysql", "cl-MySQL80")),
            ("mariadb103", ("mariadb", "cl-MariaDB103")),
            ("mariadb1011", ("mariadb", "cl-MariaDB1011")),
            ("mariadb1104", ("mariadb", "cl-MariaDB1104")),
            ("percona56", ("percona", "cl-Percona56")),
        ],
    )
    def test_known_streams(self, clmysql_type, expected):
        assert resolve_clmysql_module_stream(clmysql_type) == expected

    @pytest.mark.parametrize(
        "clmysql_type,expected",
        [
            # Future versions not in MODULE_STREAMS -- regex fallback
            ("mariadb1012", ("mariadb", "cl-MariaDB1012")),
            ("mysql90", ("mysql", "cl-MySQL90")),
            ("percona84", ("percona", "cl-Percona84")),
        ],
    )
    def test_fallback_derivation(self, clmysql_type, expected):
        assert resolve_clmysql_module_stream(clmysql_type) == expected

    def test_repo_url_supplies_the_stream_for_an_unlisted_series(self):
        """
        A series with no MODULE_STREAMS entry takes its stream from the repository
        rather than from the token, which cannot spell a padded minor version.
        """
        url = "http://repo.cloudlinux.com/other/cl8/mysqlmeta/cl-mariadb-12.04/$basearch/"
        assert resolve_clmysql_module_stream("mariadb124", baseurl=url) == ("mariadb", "cl-MariaDB1204")
        # Without the repository we can only fall back to the token, unpadded.
        assert resolve_clmysql_module_stream("mariadb124") == ("mariadb", "cl-MariaDB124")

    def test_confirmed_entry_wins_over_the_repo_url(self):
        """MODULE_STREAMS lists streams we verified, so it takes precedence."""
        url = "http://repo.cloudlinux.com/other/cl8/mysqlmeta/cl-mariadb-99.99/$basearch/"
        assert resolve_clmysql_module_stream("mariadb1104", baseurl=url) == ("mariadb", "cl-MariaDB1104")

    def test_mariadb_11_8_gets_its_real_stream_name_from_the_repo(self):
        """
        11.08 is deliberately absent from MODULE_STREAMS (its module is unconfirmed),
        but the repository still spells the name correctly: cl-MariaDB1108, not 118.
        """
        url = "http://repo.cloudlinux.com/other/cl8/mysqlmeta/cl-mariadb-11.08/$basearch/"
        assert resolve_clmysql_module_stream("mariadb118", baseurl=url) == ("mariadb", "cl-MariaDB1108")

    def test_rpm_derived_token_resolves_to_confirmed_stream(self):
        """
        CLOS-6809: cl-MariaDB1104 is the stream that exists in the target repo.
        Deriving cl-MariaDB114 from the lossy token would enable a module that
        the cl-mysql-meta repository does not carry.
        """
        assert resolve_clmysql_module_stream("mariadb114") == ("mariadb", "cl-MariaDB1104")


# ---------------------------------------------------------------------------
# clmysql_module_stream_from_url
# ---------------------------------------------------------------------------

class TestClmysqlModuleStreamFromUrl(object):
    """
    The repository directory keeps the digits the module stream uses, padding and
    all, so the stream can be read off it instead of guessed from the type token.
    Checked against every (repo dir, stream) pair in governor-mysql 1.2-147.
    """

    @pytest.mark.parametrize(
        "repo_dir,expected",
        [
            ("mysql-5.5", ("mysql", "cl-MySQL55")),
            ("mysql-5.6", ("mysql", "cl-MySQL56")),
            ("mysql-5.7", ("mysql", "cl-MySQL57")),
            ("mysql-8.0", ("mysql", "cl-MySQL80")),
            ("mysql-8.4", ("mysql", "cl-MySQL84")),
            ("mariadb-5.5", ("mariadb", "cl-MariaDB55")),
            ("mariadb-10.0", ("mariadb", "cl-MariaDB100")),
            ("mariadb-10.1", ("mariadb", "cl-MariaDB101")),
            ("mariadb-10.2", ("mariadb", "cl-MariaDB102")),
            ("mariadb-10.3", ("mariadb", "cl-MariaDB103")),
            ("mariadb-10.4", ("mariadb", "cl-MariaDB104")),
            ("mariadb-10.5", ("mariadb", "cl-MariaDB105")),
            ("mariadb-10.6", ("mariadb", "cl-MariaDB106")),
            ("mariadb-10.11", ("mariadb", "cl-MariaDB1011")),
            ("mariadb-11.04", ("mariadb", "cl-MariaDB1104")),
            ("mariadb-11.08", ("mariadb", "cl-MariaDB1108")),
            ("percona-5.6", ("percona", "cl-Percona56")),
        ],
    )
    def test_matches_governor_tables(self, repo_dir, expected):
        url = "http://repo.cloudlinux.com/other/cl$releasever/mysqlmeta/cl-{}/$basearch/".format(repo_dir)
        assert clmysql_module_stream_from_url(url) == expected

    @pytest.mark.parametrize(
        "repo_dir,expected",
        [
            ("mariadb-12.04", ("mariadb", "cl-MariaDB1204")),
            ("mariadb-12.10", ("mariadb", "cl-MariaDB1210")),
        ],
    )
    def test_future_series_needs_no_table_entry(self, repo_dir, expected):
        """A padded minor is exactly what the token-based guess got wrong."""
        url = "http://repo.cloudlinux.com/other/cl$releasever/mysqlmeta/cl-{}/$basearch/".format(repo_dir)
        assert clmysql_module_stream_from_url(url) == expected

    @pytest.mark.parametrize(
        "baseurl",
        [None, "", "http://repo.cloudlinux.com/other/cl8/mysqlmeta/mysqlclient/x86_64/"],
    )
    def test_unrecognised(self, baseurl):
        assert clmysql_module_stream_from_url(baseurl) == (None, None)


# ---------------------------------------------------------------------------
# _resolve_mysqld_path
# ---------------------------------------------------------------------------

class TestResolveMysqldPath(object):

    def test_found_via_which(self, monkeypatch):
        monkeypatch.setattr(
            "leapp.libraries.common.clmysql.run",
            lambda cmd: {"stdout": "/usr/bin/mysqld\n"},
        )
        assert _resolve_mysqld_path() == "/usr/bin/mysqld"

    def test_fallback_to_standard_location(self, monkeypatch):
        from leapp.libraries.stdlib import CalledProcessError

        def which_fails(cmd):
            raise CalledProcessError("not found", cmd, {})

        monkeypatch.setattr("leapp.libraries.common.clmysql.run", which_fails)
        # Only /usr/libexec/mysqld "exists"
        monkeypatch.setattr(
            "os.path.isfile",
            lambda p: p == "/usr/libexec/mysqld",
        )
        assert _resolve_mysqld_path() == "/usr/libexec/mysqld"

    def test_not_found(self, monkeypatch):
        from leapp.libraries.stdlib import CalledProcessError

        def which_fails(cmd):
            raise CalledProcessError("not found", cmd, {})

        monkeypatch.setattr("leapp.libraries.common.clmysql.run", which_fails)
        monkeypatch.setattr("os.path.isfile", lambda _p: False)
        assert _resolve_mysqld_path() is None


# ---------------------------------------------------------------------------
# _clmysql_name_version_from_rpm
# ---------------------------------------------------------------------------

class TestClmysqlNameVersionFromRpm(object):

    def _mock_run(self, stdout):
        """Return a ``run`` replacement that yields *stdout*."""
        def fake_run(cmd):
            return {"stdout": stdout}
        return fake_run

    def test_single_cl_package(self, monkeypatch):
        monkeypatch.setattr(
            "leapp.libraries.common.clmysql.run",
            self._mock_run("cl-MariaDB1011-server 10.11.6\n"),
        )
        assert _clmysql_name_version_from_rpm("/usr/sbin/mysqld") == (
            "cl-mariadb1011-server",
            "10.11.6",
        )

    def test_multiple_packages_picks_cl(self, monkeypatch):
        monkeypatch.setattr(
            "leapp.libraries.common.clmysql.run",
            self._mock_run(
                "some-other-pkg 1.0\n"
                "cl-MySQL80-server 8.0.35\n"
            ),
        )
        assert _clmysql_name_version_from_rpm("/usr/sbin/mysqld") == (
            "cl-mysql80-server",
            "8.0.35",
        )

    def test_no_cl_package(self, monkeypatch):
        monkeypatch.setattr(
            "leapp.libraries.common.clmysql.run",
            self._mock_run("mariadb-server 10.5.22\n"),
        )
        assert _clmysql_name_version_from_rpm("/usr/sbin/mysqld") is None

    def test_rpm_command_fails(self, monkeypatch):
        from leapp.libraries.stdlib import CalledProcessError

        def failing_run(cmd):
            raise CalledProcessError("rpm failed", cmd, {})

        monkeypatch.setattr("leapp.libraries.common.clmysql.run", failing_run)
        assert _clmysql_name_version_from_rpm("/usr/sbin/mysqld") is None


# ---------------------------------------------------------------------------
# _get_clmysql_type_from_governor
# ---------------------------------------------------------------------------

class TestGetClmysqlTypeFromGovernor(object):

    def test_file_present(self, monkeypatch, tmpdir):
        f = tmpdir.join("mysql.type")
        f.write("mariadb106")
        monkeypatch.setattr(
            "leapp.libraries.common.clmysql.GOVERNOR_INSTALLED_TYPE_FILE", str(f)
        )
        assert _get_clmysql_type_from_governor() == "mariadb106"

    def test_file_with_whitespace(self, monkeypatch, tmpdir):
        f = tmpdir.join("mysql.type")
        f.write("  mysql80\n")
        monkeypatch.setattr(
            "leapp.libraries.common.clmysql.GOVERNOR_INSTALLED_TYPE_FILE", str(f)
        )
        assert _get_clmysql_type_from_governor() == "mysql80"

    def test_file_missing(self, monkeypatch):
        monkeypatch.setattr(
            "leapp.libraries.common.clmysql.GOVERNOR_INSTALLED_TYPE_FILE",
            "/nonexistent/path/mysql.type",
        )
        assert _get_clmysql_type_from_governor() is None

    def test_lossy_governor_value_returned_verbatim(self, monkeypatch, tmpdir):
        """
        CLOS-6809: this is what Governor actually writes on a MariaDB 11.4 system.
        It is reported as-is; callers compare parsed versions, not spellings.
        """
        f = tmpdir.join("mysql.type.installed")
        f.write("mariadb114\n")
        monkeypatch.setattr(
            "leapp.libraries.common.clmysql.GOVERNOR_INSTALLED_TYPE_FILE", str(f)
        )
        assert _get_clmysql_type_from_governor() == "mariadb114"

    def test_file_empty(self, monkeypatch, tmpdir):
        f = tmpdir.join("mysql.type.installed")
        f.write("")
        monkeypatch.setattr(
            "leapp.libraries.common.clmysql.GOVERNOR_INSTALLED_TYPE_FILE", str(f)
        )
        assert _get_clmysql_type_from_governor() is None

    def test_auto_value_ignored(self, monkeypatch, tmpdir):
        f = tmpdir.join("mysql.type.installed")
        f.write("auto")
        monkeypatch.setattr(
            "leapp.libraries.common.clmysql.GOVERNOR_INSTALLED_TYPE_FILE", str(f)
        )
        assert _get_clmysql_type_from_governor() is None


# ---------------------------------------------------------------------------
# get_clmysql_version_from_pkg
# ---------------------------------------------------------------------------

class TestGetClmysqlVersionFromPkg(object):
    """The token derived from the mysqld owner RPM, matching Governor's own derivation."""

    def _patch_rpm(self, monkeypatch, name, version):
        monkeypatch.setattr(
            "leapp.libraries.common.clmysql._resolve_mysqld_path",
            lambda: "/usr/sbin/mysqld",
        )
        monkeypatch.setattr(
            "leapp.libraries.common.clmysql._clmysql_name_version_from_rpm",
            lambda _path: (name, version),
        )

    @pytest.mark.parametrize(
        "name,version,expected",
        [
            # CLOS-6809: the reporter's exact package version. Governor derives the
            # same lossy spelling, so the two sources agree by construction.
            ("cl-mariadb1104-server", "11.4.12", "mariadb114"),
            ("cl-mariadb1108-server", "11.8.3", "mariadb118"),
            ("cl-mariadb1011-server", "10.11.6", "mariadb1011"),
            ("cl-mariadb106-server", "10.6.16", "mariadb106"),
            ("cl-mysql80-server", "8.0.35", "mysql80"),
            ("cl-percona56-server", "5.6.51", "percona56"),
        ],
    )
    def test_canonical_token(self, monkeypatch, name, version, expected):
        self._patch_rpm(monkeypatch, name, version)
        assert get_clmysql_version_from_pkg() == expected

    def test_no_mysqld(self, monkeypatch):
        monkeypatch.setattr(
            "leapp.libraries.common.clmysql._resolve_mysqld_path", lambda: None
        )
        assert get_clmysql_version_from_pkg() is None


# ---------------------------------------------------------------------------
# get_pkg_prefix
# ---------------------------------------------------------------------------

class TestGetPkgPrefix(object):

    @pytest.mark.parametrize(
        "clmysql_type,expected",
        [
            ("mysql80", "cl-MySQL"),
            ("mysql55", "cl-MySQL"),
            ("mariadb106", "cl-MariaDB"),
            ("mariadb1011", "cl-MariaDB"),
            ("percona56", "cl-Percona"),
        ],
    )
    def test_known_types(self, clmysql_type, expected):
        assert get_pkg_prefix(clmysql_type) == expected

    def test_unknown_type(self):
        assert get_pkg_prefix("postgres15") is None


# ---------------------------------------------------------------------------
# get_clmysql_type  (integration of governor + RPM detection)
# ---------------------------------------------------------------------------

class TestGetClmysqlType(object):

    def _patch_sources(self, monkeypatch, governor_ret, pkg_ret):
        monkeypatch.setattr(
            "leapp.libraries.common.clmysql._get_clmysql_type_from_governor",
            lambda: governor_ret,
        )
        monkeypatch.setattr(
            "leapp.libraries.common.clmysql.get_clmysql_version_from_pkg",
            lambda: pkg_ret,
        )

    def test_governor_preferred(self, monkeypatch):
        self._patch_sources(monkeypatch, "mariadb106", "mariadb106")
        result = get_clmysql_type()
        assert result.status == ClMysqlTypeStatus.OK
        assert result.governor_type == "mariadb106"
        assert result.pkg_type == "mariadb106"

    def test_fallback_to_rpm(self, monkeypatch):
        self._patch_sources(monkeypatch, None, "mysql80")
        result = get_clmysql_type()
        assert result.status == ClMysqlTypeStatus.OK
        assert result.governor_type is None
        assert result.pkg_type == "mysql80"

    def test_both_none(self, monkeypatch):
        self._patch_sources(monkeypatch, None, None)
        result = get_clmysql_type()
        assert result.status == ClMysqlTypeStatus.OK
        assert result.governor_type is None
        assert result.pkg_type is None

    def test_mismatch(self, monkeypatch):
        self._patch_sources(monkeypatch, "mariadb1011", "mariadb106")
        result = get_clmysql_type()
        assert result.status == ClMysqlTypeStatus.MISMATCH
        assert result.governor_type == "mariadb1011"
        assert result.pkg_type == "mariadb106"

    def test_mariadb114_untouched_governor_file_is_not_a_mismatch(self, monkeypatch, tmpdir):
        """
        CLOS-6809 inhibitor #2: on an untouched MariaDB 11.4 system Governor writes
        'mariadb114' and the mysqld owner RPM is 11.4.12.  Both sides describe the
        same installation, so no mismatch may be reported.
        """
        f = tmpdir.join("mysql.type.installed")
        f.write("mariadb114")
        monkeypatch.setattr(
            "leapp.libraries.common.clmysql.GOVERNOR_INSTALLED_TYPE_FILE", str(f)
        )
        monkeypatch.setattr(
            "leapp.libraries.common.clmysql._resolve_mysqld_path",
            lambda: "/usr/sbin/mysqld",
        )
        monkeypatch.setattr(
            "leapp.libraries.common.clmysql._clmysql_name_version_from_rpm",
            lambda _path: ("cl-mariadb1104-server", "11.4.12"),
        )
        result = get_clmysql_type()
        assert result.status == ClMysqlTypeStatus.OK
        assert result.governor_type == "mariadb114"
        assert result.pkg_type == "mariadb114"

    def test_hand_corrected_governor_file_is_not_a_mismatch(self, monkeypatch, tmpdir):
        """
        CLOS-6809: KCS 27757797511068 tells customers to write the canonical token
        into mysql.type.installed by hand.  That must not turn into a mismatch
        against the RPM-derived token either.
        """
        f = tmpdir.join("mysql.type.installed")
        f.write("mariadb1104")
        monkeypatch.setattr(
            "leapp.libraries.common.clmysql.GOVERNOR_INSTALLED_TYPE_FILE", str(f)
        )
        monkeypatch.setattr(
            "leapp.libraries.common.clmysql._resolve_mysqld_path",
            lambda: "/usr/sbin/mysqld",
        )
        monkeypatch.setattr(
            "leapp.libraries.common.clmysql._clmysql_name_version_from_rpm",
            lambda _path: ("cl-mariadb1104-server", "11.4.12"),
        )
        result = get_clmysql_type()
        assert result.status == ClMysqlTypeStatus.OK
        assert result.governor_type == "mariadb1104"
        assert result.pkg_type == "mariadb114"

    def test_real_mismatch_still_detected(self, monkeypatch):
        """Normalization must not paper over a genuine version disagreement."""
        self._patch_sources(monkeypatch, "mariadb1104", "mariadb1011")
        result = get_clmysql_type()
        assert result.status == ClMysqlTypeStatus.MISMATCH

    def test_governor_only(self, monkeypatch):
        """Governor file present but mysqld not found (no RPM detection)."""
        self._patch_sources(monkeypatch, "percona56", None)
        result = get_clmysql_type()
        assert result.status == ClMysqlTypeStatus.OK
        assert result.governor_type == "percona56"
        assert result.pkg_type is None
