"""
Regression tests for clmysql_cloudlinux.py - Governor-managed DB handler.

Key scenario (CLOS-2882): Governor writes cl-mysql.repo with both repos
disabled (enabled=0).  The handler must still force-enable cl-mysql-meta-N
and mysqclient-N for the target userspace so DNF can resolve the
mariadb:cl-MariaDB106 (or equivalent) module stream and upgrade the packages.

Without the fix the module metadata is absent from the target userspace DNF
cache, which causes:
  Error: Problems in request: missing groups or modules: mariadb:cl-MariaDB106
"""

from leapp.libraries.actor.clmysql_cloudlinux import clmysql_process
from leapp.libraries.actor.clmysqlrepositorysetup import MySqlRepositorySetupLibrary


class TestDisabledReposForceEnabled:
    """
    CLOS-2882 regression: disabled cl-mysql repos must appear in the
    target userspace for the module stream to be resolvable.
    """

    def test_both_repos_disabled_still_in_target(self, patch_env, make_cl_mysql_repofile):
        """Disabled cl-mysql-meta and mysqclient repos must both be force-enabled."""
        patch_env()

        lib = MySqlRepositorySetupLibrary()
        clmysql_process(
            lib,
            "cl-mysql",
            make_cl_mysql_repofile(cl_mysql_meta_enabled=False, mysqlclient_enabled=False),
        )

        repoids = {msg.repoid for msg in lib.custom_repo_msgs}
        assert "cl-mysql-meta-9" in repoids
        assert "mysqclient-9" in repoids

    def test_target_repos_enabled_true(self, patch_env, make_cl_mysql_repofile):
        """Target repo messages must have enabled=True regardless of source state."""
        patch_env()

        lib = MySqlRepositorySetupLibrary()
        clmysql_process(
            lib,
            "cl-mysql",
            make_cl_mysql_repofile(cl_mysql_meta_enabled=False, mysqlclient_enabled=False),
        )

        for msg in lib.custom_repo_msgs:
            assert msg.enabled, "target repo {} must be enabled=True".format(msg.repoid)

    def test_cloudlinux_type_always_registered(self, patch_env, make_cl_mysql_repofile):
        """'cloudlinux' must be added to mysql_types even when all repos are disabled."""
        patch_env()

        lib = MySqlRepositorySetupLibrary()
        clmysql_process(
            lib,
            "cl-mysql",
            make_cl_mysql_repofile(cl_mysql_meta_enabled=False, mysqlclient_enabled=False),
        )

        assert "cloudlinux" in lib.mysql_types

    def test_releasever_substituted_in_target_baseurl(self, patch_env, make_cl_mysql_repofile):
        """Target repo baseurls must have $releasever replaced with the target major version."""
        patch_env(target_major="9")

        lib = MySqlRepositorySetupLibrary()
        clmysql_process(
            lib,
            "cl-mysql",
            make_cl_mysql_repofile(cl_mysql_meta_enabled=False, mysqlclient_enabled=False),
        )

        for msg in lib.custom_repo_msgs:
            assert "$releasever" not in msg.baseurl
            assert "/cl9/" in msg.baseurl

    def test_enabled_repos_also_pass_through(self, patch_env, make_cl_mysql_repofile):
        """Normal case: enabled cl-mysql-meta still appears in target repos."""
        patch_env()

        lib = MySqlRepositorySetupLibrary()
        clmysql_process(
            lib,
            "cl-mysql",
            make_cl_mysql_repofile(cl_mysql_meta_enabled=True, mysqlclient_enabled=False),
        )

        repoids = {msg.repoid for msg in lib.custom_repo_msgs}
        assert "cl-mysql-meta-9" in repoids
        assert "cloudlinux" in lib.mysql_types
