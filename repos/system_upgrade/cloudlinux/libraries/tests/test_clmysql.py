import os

import pytest

from leapp.libraries.common.clmysql import (
    ClMysqlTypeStatus,
    _clmysql_name_version_from_rpm,
    _get_clmysql_type_from_governor,
    _resolve_mysqld_path,
    get_clmysql_type,
    get_pkg_prefix,
    resolve_clmysql_module_stream,
)


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

    @pytest.mark.parametrize(
        "clmysql_type",
        [
            None,
            "",
            "postgres15",
            "unknown",
            "maria-db103",   # hyphen breaks the pattern
        ],
    )
    def test_unresolvable(self, clmysql_type):
        assert resolve_clmysql_module_stream(clmysql_type) == (None, None)


# ---------------------------------------------------------------------------
# _resolve_mysqld_path
# ---------------------------------------------------------------------------

class TestResolveMysqldPath(object):

    def test_found_via_which(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda _name: "/usr/bin/mysqld")
        assert _resolve_mysqld_path() == "/usr/bin/mysqld"

    def test_fallback_to_standard_location(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda _name: None)
        # Only /usr/libexec/mysqld "exists"
        monkeypatch.setattr(
            "os.path.isfile",
            lambda p: p == "/usr/libexec/mysqld",
        )
        assert _resolve_mysqld_path() == "/usr/libexec/mysqld"

    def test_not_found(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda _name: None)
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

    def test_governor_only(self, monkeypatch):
        """Governor file present but mysqld not found (no RPM detection)."""
        self._patch_sources(monkeypatch, "percona56", None)
        result = get_clmysql_type()
        assert result.status == ClMysqlTypeStatus.OK
        assert result.governor_type == "percona56"
        assert result.pkg_type is None
