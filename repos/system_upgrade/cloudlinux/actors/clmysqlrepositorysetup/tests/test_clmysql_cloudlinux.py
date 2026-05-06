"""
Regression tests for clmysql_cloudlinux.py — Governor-managed DB handler.

Key scenario (CLOS-2882): Governor writes cl-mysql.repo with both repos
disabled (enabled=0).  The handler must still force-enable cl-mysql-meta-N
and mysqclient-N for the target userspace so DNF can resolve the
mariadb:cl-MariaDB106 (or equivalent) module stream and upgrade the packages.

Without the fix the module metadata is absent from the target userspace DNF
cache, which causes:
  Error: Problems in request: missing groups or modules: mariadb:cl-MariaDB106
"""
import pytest

from leapp import reporting
from leapp.libraries.actor.clmysql_cloudlinux import clmysql_process
from leapp.libraries.actor.clmysqlrepositorysetup import MySqlRepositorySetupLibrary
from leapp.libraries.common.clmysql import ClMysqlTypeResult, ClMysqlTypeStatus
from leapp.libraries.common.testutils import create_report_mocked, logger_mocked, produce_mocked
from leapp.libraries.stdlib import api
from leapp.models import CustomTargetRepository, CustomTargetRepositoryFile, RepositoryData, RepositoryFile


_MARIADB106_META_BASEURL = (
    "http://repo.cloudlinux.com/other/cl$releasever/mysqlmeta/cl-mariadb-10.6/x86_64/"
)
_MYSQLCLIENT_BASEURL = (
    "http://repo.cloudlinux.com/other/cl$releasever/mysqlmeta/mysqlclient/x86_64/"
)


def _make_cl_mysql_repofile(cl_mysql_meta_enabled=True, mysqlclient_enabled=False):
    """Return a RepositoryFile that mimics a Governor-written cl-mysql.repo."""
    return RepositoryFile(
        file="cl-mysql.repo",
        data=[
            RepositoryData(
                repoid="cl-mysql-meta",
                name="cl-mysql",
                baseurl=_MARIADB106_META_BASEURL,
                enabled=cl_mysql_meta_enabled,
            ),
            RepositoryData(
                repoid="mysqclient",
                name="mysqlclient",
                baseurl=_MYSQLCLIENT_BASEURL,
                enabled=mysqlclient_enabled,
            ),
        ],
    )


def _patch_env(monkeypatch, clmysql_type="mariadb106", target_major="9"):
    """Patch all external dependencies of clmysql_cloudlinux."""
    monkeypatch.setattr(
        "leapp.libraries.actor.clmysql_cloudlinux.get_clmysql_type",
        lambda: ClMysqlTypeResult(
            status=ClMysqlTypeStatus.OK,
            governor_type=clmysql_type,
            pkg_type=clmysql_type,
        ),
    )
    monkeypatch.setattr(
        "leapp.libraries.actor.clmysql_cloudlinux.get_target_major_version",
        lambda: target_major,
    )
    monkeypatch.setattr(
        "leapp.libraries.actor.clmysql_cloudlinux.create_leapp_repofile_copy",
        lambda *a, **kw: "/tmp/cl-mysql-leapp.repo",
    )
    monkeypatch.setattr(api, "produce", produce_mocked())
    monkeypatch.setattr(api, "current_logger", logger_mocked())
    monkeypatch.setattr(reporting, "create_report", create_report_mocked())


class TestDisabledReposForceEnabled:
    """
    CLOS-2882 regression: disabled cl-mysql repos must appear in the
    target userspace for the module stream to be resolvable.
    """

    def test_both_repos_disabled_still_in_target(self, monkeypatch):
        """Disabled cl-mysql-meta and mysqclient repos must both be force-enabled."""
        _patch_env(monkeypatch)

        lib = MySqlRepositorySetupLibrary()
        clmysql_process(lib, "cl-mysql", _make_cl_mysql_repofile(
            cl_mysql_meta_enabled=False, mysqlclient_enabled=False
        ))

        repoids = {msg.repoid for msg in lib.custom_repo_msgs}
        assert "cl-mysql-meta-9" in repoids
        assert "mysqclient-9" in repoids

    def test_target_repos_enabled_true(self, monkeypatch):
        """Target repo messages must have enabled=True regardless of source state."""
        _patch_env(monkeypatch)

        lib = MySqlRepositorySetupLibrary()
        clmysql_process(lib, "cl-mysql", _make_cl_mysql_repofile(
            cl_mysql_meta_enabled=False, mysqlclient_enabled=False
        ))

        for msg in lib.custom_repo_msgs:
            assert msg.enabled, "target repo {} must be enabled=True".format(msg.repoid)

    def test_cloudlinux_type_always_registered(self, monkeypatch):
        """'cloudlinux' must be added to mysql_types even when all repos are disabled."""
        _patch_env(monkeypatch)

        lib = MySqlRepositorySetupLibrary()
        clmysql_process(lib, "cl-mysql", _make_cl_mysql_repofile(
            cl_mysql_meta_enabled=False, mysqlclient_enabled=False
        ))

        assert "cloudlinux" in lib.mysql_types

    def test_releasever_substituted_in_target_baseurl(self, monkeypatch):
        """Target repo baseurls must have $releasever replaced with the target major version."""
        _patch_env(monkeypatch, target_major="9")

        lib = MySqlRepositorySetupLibrary()
        clmysql_process(lib, "cl-mysql", _make_cl_mysql_repofile(
            cl_mysql_meta_enabled=False, mysqlclient_enabled=False
        ))

        for msg in lib.custom_repo_msgs:
            assert "$releasever" not in msg.baseurl
            assert "/cl9/" in msg.baseurl

    def test_enabled_repos_also_pass_through(self, monkeypatch):
        """Normal case: enabled cl-mysql-meta still appears in target repos."""
        _patch_env(monkeypatch)

        lib = MySqlRepositorySetupLibrary()
        clmysql_process(lib, "cl-mysql", _make_cl_mysql_repofile(
            cl_mysql_meta_enabled=True, mysqlclient_enabled=False
        ))

        repoids = {msg.repoid for msg in lib.custom_repo_msgs}
        assert "cl-mysql-meta-9" in repoids
        assert "cloudlinux" in lib.mysql_types


class TestMismatchInhibitor:
    """Governor/RPM type mismatch must create an inhibitor and skip repo setup."""

    def test_mismatch_inhibits_and_adds_no_repos(self, monkeypatch):
        monkeypatch.setattr(
            "leapp.libraries.actor.clmysql_cloudlinux.get_clmysql_type",
            lambda: ClMysqlTypeResult(
                status=ClMysqlTypeStatus.MISMATCH,
                governor_type="mariadb106",
                pkg_type="mysql80",
            ),
        )
        monkeypatch.setattr(
            "leapp.libraries.actor.clmysql_cloudlinux.get_target_major_version",
            lambda: "9",
        )
        monkeypatch.setattr(
            "leapp.libraries.actor.clmysql_cloudlinux.create_leapp_repofile_copy",
            lambda *a, **kw: "/tmp/cl-mysql-leapp.repo",
        )
        monkeypatch.setattr(api, "produce", produce_mocked())
        monkeypatch.setattr(api, "current_logger", logger_mocked())
        monkeypatch.setattr(reporting, "create_report", create_report_mocked())

        lib = MySqlRepositorySetupLibrary()
        clmysql_process(lib, "cl-mysql", _make_cl_mysql_repofile())

        assert "cloudlinux" not in lib.mysql_types
        assert lib.custom_repo_msgs == []
        assert reporting.create_report.called == 1
