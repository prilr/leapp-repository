"""
Handler for upstream (mariadb.org) MariaDB repositories.
"""
import copy

from leapp import reporting
from leapp.libraries.common.cl_repofileutils import create_leapp_repofile_copy
from leapp.libraries.common.clmysql import construct_repomap_data
from leapp.libraries.common.config.version import get_source_major_version, get_target_major_version
from leapp.libraries.stdlib import api
from leapp.models import (
    CustomTargetRepository,
    CustomTargetRepositoryFile,
    RepositoryFile,
)

OLD_MARIADB_UPSTREAM_VERSIONS_CL8 = ["10.3", "10.4"]


def _make_upgrade_mariadb_url(mariadb_url, source_major, target_major):
    """
    Rewrite an upstream MariaDB repo URL for the target OS version.

    Maria URLs look like this::

        baseurl = https://archive.mariadb.org/mariadb-10.3/yum/centos/7/x86_64
        baseurl = https://archive.mariadb.org/mariadb-10.7/yum/centos7-ppc64/
        baseurl = https://distrohub.kyiv.ua/mariadb/yum/11.8/rhel/$releasever/$basearch
        baseurl = https://mariadb.gb.ssimn.org/yum/12.0/centos/$releasever/$basearch
        baseurl = https://mariadb.gb.ssimn.org/yum/12.0/almalinux8-amd64/$releasever/$basearch

    We replace the parts of the URL to make them work with the target OS version.
    """
    if not mariadb_url:
        api.current_logger().warning("Unsupported repository URL={}, skipping".format(mariadb_url))
        return None
    # Replace the first occurrence of source_major with target_major after 'yum'
    url_parts = mariadb_url.split("yum", 1)
    if len(url_parts) == 2 and url_parts[1]:
        # Replace major version in "/centos/7/" and /12.0/almalinux9-amd64/,
        # but do not replace it in /mariadb-10.7/yum/
        url_parts[1] = url_parts[1].replace("/{}/".format(source_major), "/{}/".format(target_major))
        url_parts[1] = url_parts[1].replace("{}-".format(source_major), "{}-".format(target_major))
        # Replace $releasever because upstream repos expect major version
        # and cloudlinux provides major.minor as $releasever
        url_parts[1] = url_parts[1].replace('$releasever', str(target_major))
        new_url = "yum".join(url_parts)
        # Treat as unsupported if no version replacement was made (e.g. "example.com/mariadb/yum")
        if new_url == mariadb_url and "/{}/".format(target_major) not in new_url:
            api.current_logger().warning("Unsupported repository URL={}, skipping".format(mariadb_url))
            return None
        return new_url
    else:
        api.current_logger().warning("Unsupported repository URL={}, skipping".format(mariadb_url))
        return None


def mariadb_process(lib, repofile_name, repofile_data):
    """
    Process upstream MariaDB options.

    Versions of MariaDB installed from https://mariadb.org/.

    :param lib: :class:`MySqlRepositorySetupLibrary` instance (shared state).
    :param repofile_name: repository file name without ``.repo`` suffix.
    :param repofile_data: parsed :class:`RepositoryFile`.
    """

    cl_target_repofile_list = []
    target_major = get_target_major_version()
    source_major = get_source_major_version()

    for source_repo in repofile_data.data:
        target_repo = copy.deepcopy(source_repo)
        target_repo.repoid = "{}-{}".format(target_repo.repoid, target_major)
        target_repo.baseurl = _make_upgrade_mariadb_url(source_repo.baseurl, source_major, target_major)

        if target_repo.enabled:
            # MariaDB 10.4 is not compatible with Leapp upgrade
            if str(source_major) == "8" and any(ver in target_repo.baseurl for ver in OLD_MARIADB_UPSTREAM_VERSIONS_CL8):
                reporting.create_report(
                    [
                        reporting.Title("MariaDB version is not compatible with Leapp upgrade"),
                        reporting.Summary(
                            "MariaDB is installed on this system but its version is not compatible with Leapp upgrade process. "
                            "The upgrade is blocked to prevent system instability. "
                            "This situation cannot be automatically resolved by Leapp. "
                            "Problematic repository: {0}".format(target_repo.repoid)
                        ),
                        reporting.Severity(reporting.Severity.MEDIUM),
                        reporting.Groups([reporting.Groups.REPOSITORY]),
                        reporting.Groups([reporting.Groups.INHIBITOR]),
                        reporting.Remediation(
                            hint=(
                                "Upgrade to a more recent MariaDB version, or "
                                "uninstall the MariaDB packages and disable the repository. "
                                "Note that you will also need to update any bindings (e.g., PHP or Python) "
                                "that are dependent on this MariaDB version."
                            )
                        ),
                    ]
                )

            api.current_logger().debug("Generating custom MariaDB repo: {}".format(target_repo.repoid))
            lib.custom_repo_msgs.append(
                CustomTargetRepository(
                    repoid=target_repo.repoid,
                    name=target_repo.name,
                    baseurl=target_repo.baseurl,
                    enabled=target_repo.enabled,
                )
            )
            lib.mapping_msgs.append(
                construct_repomap_data(source_repo.repoid, target_repo.repoid)
            )
            cl_target_repofile_list.append(target_repo)

    if any(repo.enabled for repo in repofile_data.data):
        # Since MariaDB URLs have major versions written in, we need a new repo file
        # to feed to the target userspace.
        lib.mysql_types.add("mariadb")
        cl_target_repofile_data = RepositoryFile(data=cl_target_repofile_list, file=repofile_data.file)
        leapp_repocopy = create_leapp_repofile_copy(cl_target_repofile_data, repofile_name)
        api.produce(CustomTargetRepositoryFile(file=leapp_repocopy))
    else:
        api.current_logger().debug("No repos from MariaDB repofile {} enabled, ignoring".format(repofile_name))
