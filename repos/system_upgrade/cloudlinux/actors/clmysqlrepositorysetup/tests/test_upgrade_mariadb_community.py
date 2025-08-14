import pytest

from leapp.libraries.actor import clmysqlrepositorysetup


@pytest.mark.parametrize(
    "source_url,source_major,target_major,expected_url",
    [
        # Test cases from docstring
        (
            "https://archive.mariadb.org/mariadb-10.3/yum/centos/7/x86_64",
            7, 8,
            "https://archive.mariadb.org/mariadb-10.3/yum/centos/8/x86_64",
        ),
        (
            "https://archive.mariadb.org/mariadb-10.7/yum/centos7-ppc64/",
            7, 8,
            "https://archive.mariadb.org/mariadb-10.7/yum/centos8-ppc64/",
        ),
        (
            "https://distrohub.kyiv.ua/mariadb/yum/11.8/rhel/7/x86_64",
            7, 8,
            "https://distrohub.kyiv.ua/mariadb/yum/11.8/rhel/8/x86_64",
        ),
        (
            "https://mariadb.gb.ssimn.org/yum/12.0/centos/7/x86_64",
            7, 8,
            "https://mariadb.gb.ssimn.org/yum/12.0/centos/8/x86_64",
        ),
        (
            "https://mariadb.gb.ssimn.org/yum/12.0/almalinux8-amd64/",
            8, 9,
            "https://mariadb.gb.ssimn.org/yum/12.0/almalinux9-amd64/",
        ),

        # Test with trailing slash
        (
            "https://archive.mariadb.org/mariadb-10.3/yum/centos/7/x86_64/",
            7, 8,
            "https://archive.mariadb.org/mariadb-10.3/yum/centos/8/x86_64/",
        ),

         # Test cases based on SSIMN.org mirror patterns
         # RHEL patterns
         (
             "https://mariadb.gb.ssimn.org/yum/12.0/rhel8-amd64/",
             8, 9,
             "https://mariadb.gb.ssimn.org/yum/12.0/rhel9-amd64/",
         ),

         # Rocky Linux patterns
         (
             "https://mariadb.gb.ssimn.org/yum/12.0/rocky8-amd64/",
             8, 9,
             "https://mariadb.gb.ssimn.org/yum/12.0/rocky9-amd64/",
         ),
         (
             "https://mariadb.gb.ssimn.org/yum/12.0/rockylinux8-amd64/",
             8, 9,
             "https://mariadb.gb.ssimn.org/yum/12.0/rockylinux9-amd64/",
         ),

        # Test cases that should return None and log warning
        (
            "https://example.com/mariadb/repo/centos/7/x86_64",
            7, 8,
            None,
        ),
        (
            "https://example.com/mariadb/yum",
            7, 8,
            None,
        ),
        (
            "",
            7, 8,
            None,
        ),
        (
            None,
            7, 8,
            None,
        ),
    ]
)
def test_make_upgrade_mariadb_url(source_url, source_major, target_major, expected_url):
    """Test URL transformation for various MariaDB repository URLs."""
    library = clmysqlrepositorysetup.MySqlRepositorySetupLibrary()
    result = library._make_upgrade_mariadb_url(source_url, source_major, target_major)

    assert result == expected_url
