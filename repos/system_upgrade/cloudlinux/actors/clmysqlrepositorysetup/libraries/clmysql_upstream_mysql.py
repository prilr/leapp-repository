"""
Handler for upstream (mysql.com) MySQL Community repositories.
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

OLD_MYSQL_UPSTREAM_VERSIONS_CL7 = ["5.7", "5.6", "5.5"]
OLD_MYSQL_UPSTREAM_VERSIONS_CL8 = ["5.7", "5.6"]


def mysql_process(lib, repofile_name, repofile_data):
    """
    Process upstream MySQL options.

    Versions of MySQL installed from https://mysql.com/.

    :param lib: :class:`MySqlRepositorySetupLibrary` instance (shared state).
    :param repofile_name: repository file name without ``.repo`` suffix.
    :param repofile_data: parsed :class:`RepositoryFile`.
    """

    cl_target_repofile_list = []
    target_major = get_target_major_version()
    source_major = get_source_major_version()

    # Select the correct list of old MySQL versions for the source major version
    if str(source_major) == "7":
        old_mysql_versions = OLD_MYSQL_UPSTREAM_VERSIONS_CL7
    else:
        old_mysql_versions = OLD_MYSQL_UPSTREAM_VERSIONS_CL8

    for source_repo in repofile_data.data:
        # URLs look like this:
        # baseurl = https://repo.mysql.com/yum/mysql-8.0-community/el/7/x86_64/
        # Remember that we always want to modify names, to avoid "duplicate repository" errors.
        target_repo = copy.deepcopy(source_repo)
        target_repo.repoid = "{}-{}".format(target_repo.repoid, target_major)
        # Replace /el/<source_major>/ with /el/<target_major>/
        target_repo.baseurl = target_repo.baseurl.replace("/el/{}/".format(source_major), "/el/{}/".format(target_major))
        # releasever may be something like 8.6, while only 8 is acceptable.
        target_repo.baseurl = target_repo.baseurl.replace("/$releasever/", "/{}/".format(target_major))

        if target_repo.enabled:
            # MySQL package repos don't have these versions available for EL8 anymore.
            # There's only 8.0 available.
            # There'll be nothing to upgrade to.
            # CL repositories do provide them, though.
            if any(ver in target_repo.name for ver in old_mysql_versions):
                reporting.create_report(
                    [
                        reporting.Title("An old MySQL version will no longer be available in EL{}".format(target_major)),
                        reporting.Summary(
                            "A yum repository for an old MySQL version is enabled on this system. "
                            "It will no longer be available on the target system. "
                            "This situation cannot be automatically resolved by Leapp. "
                            "Problematic repository: {0}".format(target_repo.repoid)
                        ),
                        reporting.Severity(reporting.Severity.MEDIUM),
                        reporting.Groups([reporting.Groups.REPOSITORY]),
                        reporting.Groups([reporting.Groups.INHIBITOR]),
                        reporting.Remediation(
                            hint=(
                                "Upgrade to a more recent MySQL version, "
                                "uninstall the deprecated MySQL packages and disable the repository, "
                                "or switch to CloudLinux MySQL Governor-provided version of MySQL to "
                                "continue using the old MySQL version."
                            )
                        ),
                    ]
                )
            api.current_logger().debug("Generating custom MySQL repo: {}".format(target_repo.repoid))
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
        # MySQL typically has multiple repo files, so we want to make sure we're
        # adding the type to list only once.
        lib.mysql_types.add("mysql")
        cl_target_repofile_data = RepositoryFile(data=cl_target_repofile_list, file=repofile_data.file)
        leapp_repocopy = create_leapp_repofile_copy(cl_target_repofile_data, repofile_name)
        api.produce(CustomTargetRepositoryFile(file=leapp_repocopy))
    else:
        api.current_logger().debug("No repos from MySQL repofile {} enabled, ignoring".format(repofile_name))
