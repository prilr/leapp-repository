"""
CLOS-4077 regression: cl-mysql-meta repo URL does not match the installed
DB type (e.g. cl-mariadb-10.5 baseurl on a system whose mysqld is from
cl-MariaDB1011).  The handler must inhibit the upgrade and NOT generate
target repos, otherwise DNF would try to install cl-MariaDB105-* alongside
the system's cl-MariaDB1011-* and abort with file conflicts on
libmariadb.so.3 / libmysqlclient.so.18.
"""

from leapp import reporting
from leapp.libraries.actor.clmysql_cloudlinux import clmysql_process
from leapp.libraries.actor.clmysqlrepositorysetup import MySqlRepositorySetupLibrary


_BASEURL_105 = "http://repo.cloudlinux.com/other/cl$releasever/mysqlmeta/cl-mariadb-10.5/x86_64/"


class TestClMysqlMetaUrlMismatchInhibitor:
    """cl-mysql-meta baseurl that disagrees with the detected DB type must inhibit."""

    def test_url_mismatch_inhibits_and_adds_no_repos(self, patch_env, make_cl_mysql_repofile):
        patch_env(clmysql_type="mariadb1011")

        lib = MySqlRepositorySetupLibrary()
        clmysql_process(
            lib,
            "cl-mysql",
            make_cl_mysql_repofile(cl_mysql_meta_baseurl=_BASEURL_105),
        )

        assert "cloudlinux" not in lib.mysql_types
        assert lib.custom_repo_msgs == []
        assert reporting.create_report.called == 1

    def test_url_match_does_not_inhibit(self, patch_env, make_cl_mysql_repofile):
        """Sanity check: matching baseurl and type keeps the normal flow."""
        patch_env(clmysql_type="mariadb106")

        lib = MySqlRepositorySetupLibrary()
        clmysql_process(lib, "cl-mysql", make_cl_mysql_repofile())

        assert "cloudlinux" in lib.mysql_types
        assert lib.custom_repo_msgs != []
