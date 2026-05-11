"""
Tests for the Governor/RPM mismatch inhibitor in clmysql_cloudlinux.

When MySQL Governor's recorded type does not match the installed mysqld
binary, the handler must inhibit the upgrade and not register any target
repos (a wrong module stream would otherwise be enabled).
"""

from leapp import reporting
from leapp.libraries.actor.clmysql_cloudlinux import clmysql_process
from leapp.libraries.actor.clmysqlrepositorysetup import MySqlRepositorySetupLibrary
from leapp.libraries.common.clmysql import ClMysqlTypeResult, ClMysqlTypeStatus


class TestMismatchInhibitor:
    """Governor/RPM type mismatch must create an inhibitor and skip repo setup."""

    def test_mismatch_inhibits_and_adds_no_repos(self, patch_env, make_cl_mysql_repofile):
        patch_env(
            clmysql_result=ClMysqlTypeResult(
                status=ClMysqlTypeStatus.MISMATCH,
                governor_type="mariadb106",
                pkg_type="mysql80",
            )
        )

        lib = MySqlRepositorySetupLibrary()
        clmysql_process(lib, "cl-mysql", make_cl_mysql_repofile())

        assert "cloudlinux" not in lib.mysql_types
        assert lib.custom_repo_msgs == []
        assert reporting.create_report.called == 1
