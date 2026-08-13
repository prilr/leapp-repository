"""
CLOS-6809 regression: a Governor-managed MariaDB 11.4 (or 11.8) system was
inhibited even though nothing on it was wrong.

Governor derives the token it caches in mysql.type.installed by concatenating the
RPM major and minor version, so an 11.4.12 install is recorded as 'mariadb114'.
The canonical Governor token is 'mariadb1104' and the published repository
directory is cl-mariadb-11.04, so predicting the URL fragment from the cached
token produced 'cl-mariadb-11.4' - a path that does not exist - and the handler
inhibited the upgrade with a remediation hint pointing at a 404.

The handler now compares parsed versions instead of predicting the spelling, so
either spelling of the token agrees with either spelling of the URL. These tests
drive it with the cached token exactly as it appears on disk, against the
repofile Governor actually writes.
"""

from leapp import reporting
from leapp.libraries.actor.clmysql_cloudlinux import clmysql_process
from leapp.libraries.actor.clmysqlrepositorysetup import MySqlRepositorySetupLibrary

# Verbatim from http://repo.cloudlinux.com/other/cl8/mysqlmeta/cl-mariadb-11.04-common.repo
_BASEURL_1104 = "http://repo.cloudlinux.com/other/cl$releasever/mysqlmeta/cl-mariadb-11.04/$basearch/"
_BASEURL_1108 = "http://repo.cloudlinux.com/other/cl$releasever/mysqlmeta/cl-mariadb-11.08/$basearch/"
# A URL whose version component Leapp cannot read at all.
_BASEURL_UNREADABLE = "http://repo.cloudlinux.com/other/cl$releasever/mysqlmeta/current/$basearch/"


class TestGovernorTokenSpelling:

    def test_mariadb_11_4_is_not_inhibited(self, patch_env, make_cl_mysql_repofile):
        patch_env(clmysql_type="mariadb114")

        lib = MySqlRepositorySetupLibrary()
        clmysql_process(
            lib,
            "cl-mysql",
            make_cl_mysql_repofile(cl_mysql_meta_baseurl=_BASEURL_1104),
        )

        assert "cloudlinux" in lib.mysql_types
        assert lib.custom_repo_msgs != []
        assert reporting.create_report.called == 0

    def test_mariadb_11_8_is_not_inhibited(self, patch_env, make_cl_mysql_repofile):
        patch_env(clmysql_type="mariadb118")

        lib = MySqlRepositorySetupLibrary()
        clmysql_process(
            lib,
            "cl-mysql",
            make_cl_mysql_repofile(cl_mysql_meta_baseurl=_BASEURL_1108),
        )

        assert "cloudlinux" in lib.mysql_types
        assert lib.custom_repo_msgs != []
        assert reporting.create_report.called == 0

    def test_canonical_token_against_padded_url_is_not_inhibited(self, patch_env, make_cl_mysql_repofile):
        """The other spelling pairing: canonical token, padded URL."""
        patch_env(clmysql_type="mariadb1104")

        lib = MySqlRepositorySetupLibrary()
        clmysql_process(
            lib,
            "cl-mysql",
            make_cl_mysql_repofile(cl_mysql_meta_baseurl=_BASEURL_1104),
        )

        assert "cloudlinux" in lib.mysql_types
        assert reporting.create_report.called == 0

    def test_genuinely_wrong_repofile_still_inhibits(self, patch_env, make_cl_mysql_repofile):
        """An 11.4 install pointed at the 10.6 repository is still a real problem."""
        patch_env(clmysql_type="mariadb114")

        lib = MySqlRepositorySetupLibrary()
        clmysql_process(lib, "cl-mysql", make_cl_mysql_repofile())

        assert "cloudlinux" not in lib.mysql_types
        assert lib.custom_repo_msgs == []
        assert reporting.create_report.called == 1

    def test_remediation_does_not_point_at_a_guessed_url(self, patch_env, make_cl_mysql_repofile):
        """
        The old hint told customers to curl a predicted -common.repo file, which 404s
        for MariaDB 11.x. Re-running Governor regenerates the file by definition.
        """
        patch_env(clmysql_type="mariadb114")

        lib = MySqlRepositorySetupLibrary()
        clmysql_process(lib, "cl-mysql", make_cl_mysql_repofile())

        hint = reporting.create_report.report_fields["detail"]["remediations"][0]["context"]
        assert "-common.repo" not in hint
        assert "mysqlgovernor.py --install --yes" in hint


class TestUnreadableRepoUrl:
    """
    A cl-mysql-meta URL whose version cannot be read must inhibit. Comparing parsed
    versions replaced a substring test that inhibited on anything unrecognised, and
    for a while an unreadable URL slipped through: the repository was copied,
    force-enabled and handed to the upgrade without ever being checked.
    """

    def test_unreadable_url_inhibits(self, patch_env, make_cl_mysql_repofile):
        patch_env(clmysql_type="mariadb114")

        lib = MySqlRepositorySetupLibrary()
        clmysql_process(
            lib,
            "cl-mysql",
            make_cl_mysql_repofile(cl_mysql_meta_baseurl=_BASEURL_UNREADABLE),
        )

        assert reporting.create_report.called == 1
        assert "cloudlinux" not in lib.mysql_types
        assert lib.custom_repo_msgs == []

    def test_unreadable_url_says_why(self, patch_env, make_cl_mysql_repofile):
        patch_env(clmysql_type="mariadb114")

        lib = MySqlRepositorySetupLibrary()
        clmysql_process(
            lib,
            "cl-mysql",
            make_cl_mysql_repofile(cl_mysql_meta_baseurl=_BASEURL_UNREADABLE),
        )

        summary = reporting.create_report.report_fields["summary"]
        assert "does not name a database version" in summary
        assert _BASEURL_UNREADABLE in summary
