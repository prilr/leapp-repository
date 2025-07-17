import os
import copy

from leapp.models import (
    InstalledMySqlTypes,
    CustomTargetRepositoryFile,
    CustomTargetRepository,
    RpmTransactionTasks,
    InstalledRPM,
    RepositoriesMapping,
    RepoMapEntry,
    PESIDRepositoryEntry,
    Module,
)
from leapp.libraries.stdlib import api
from leapp.libraries.common import repofileutils
from leapp import reporting
from leapp.libraries.common.clmysql import get_clmysql_type, get_pkg_prefix, MODULE_STREAMS
from leapp.libraries.common.cl_repofileutils import (
    create_leapp_repofile_copy,
    REPO_DIR,
    LEAPP_COPY_SUFFIX,
    REPOFILE_SUFFIX,
)
from leapp.models import RepositoryFile
from leapp.libraries.common.config.version import get_source_major_version, get_target_major_version

CL_MARKERS = ["cl-mysql", "cl-mariadb", "cl-percona"]
MARIA_MARKERS = ["MariaDB"]
MYSQL_MARKERS = ["mysql-community"]
OLD_CLMYSQL_VERSIONS = ["5.0", "5.1"]
OLD_MYSQL_UPSTREAM_VERSIONS_CL7 = ["5.7", "5.6", "5.5"]
OLD_MYSQL_UPSTREAM_VERSIONS_CL8 = ["5.7", "5.6"]  # adjust as needed for CL8


def build_install_list(prefix):
    """
    Find the installed cl-mysql packages that match the active
    cl-mysql type as per Governor config.

    :param prefix: Package name prefix to search for.
    :return: List of matching packages.
    """
    to_upgrade = []
    if prefix:
        for rpm_pkgs in api.consume(InstalledRPM):
            for pkg in rpm_pkgs.items:
                if pkg.name.startswith(prefix):
                    to_upgrade.append(pkg.name)
        api.current_logger().debug("cl-mysql packages to upgrade: {}".format(to_upgrade))
    return to_upgrade


def make_pesid_repo(pesid, major_version, repoid, arch='x86_64', repo_type='rpm', channel='ga', rhui=''):
    """
    PESIDRepositoryEntry factory function allowing shorter data description by providing default values.
    """
    return PESIDRepositoryEntry(
        pesid=pesid,
        major_version=major_version,
        repoid=repoid,
        arch=arch,
        repo_type=repo_type,
        channel=channel,
        rhui=rhui
    )


def construct_repomap_data(source_id, target_id):
    """
    Construct the repository mapping data.
    """
    source_major = get_source_major_version()
    target_major = get_target_major_version()
    return RepositoriesMapping(
        mapping=[RepoMapEntry(source=source_id, target=[target_id])],
        repositories=[
            make_pesid_repo(source_id, source_major, source_id),
            make_pesid_repo(target_id, target_major, target_id)
        ]
    )


class MySqlRepositorySetupLibrary(object):
    """
    Detect the various MySQL/MariaDB variants that may be installed on the system
    and prepare the repositories for the target system.
    Not all configurations can be handled by normal static Leapp configurations,
    so we need custom code to handle them.
    """

    def __init__(self):
        self.mysql_types = set()
        self.clmysql_type = None
        # Messages to send about custom generated package repositories.
        self.custom_repo_msgs = []
        self.mapping_msgs = []

    def clmysql_process(self, repofile_name, repofile_data):
        """
        Process CL-provided MySQL options.
        """
        self.clmysql_type = get_clmysql_type()
        if not self.clmysql_type:
            api.current_logger().warning("CL-MySQL type detection failed, skipping repository mapping")
            return
        api.current_logger().debug("Detected CL-MySQL type: {}".format(self.clmysql_type))

        data_to_log = [
            (repo_data.repoid, "enabled" if repo_data.enabled else "disabled") for repo_data in repofile_data.data
        ]

        api.current_logger().debug("repoids from CloudLinux repofile {}: {}".format(repofile_name, data_to_log))

        cl_target_repofile_list = []
        target_major = get_target_major_version()

        # Were any repositories enabled?
        for source_repo in repofile_data.data:
            # cl-mysql URLs look like this:
            # baseurl=http://repo.cloudlinux.com/other/cl$releasever/mysqlmeta/cl-mariadb-10.3/$basearch/
            # We don't want any duplicate repoid entries - they'd cause yum/dnf to fail.
            # Make everything unique by adding -<target_major> to the repoid.
            target_repo = copy.deepcopy(source_repo)
            target_repo.repoid = "{}-{}".format(target_repo.repoid, target_major)
            # releasever may be something like 8.6, while only 8 is acceptable.
            target_repo.baseurl = target_repo.baseurl.replace("/cl$releasever/", "/cl{}/".format(target_major))

            # Old CL MySQL versions (5.0 and 5.1) won't be available in CL8+.
            if any(ver in target_repo.baseurl for ver in OLD_CLMYSQL_VERSIONS):
                reporting.create_report(
                    [
                        reporting.Title("An old CL-MySQL version will no longer be available in EL{}".format(target_major)),
                        reporting.Summary(
                            "An old CloudLinux-provided MySQL version is installed on this system. "
                            "It will no longer be available on the target system. "
                            "This situation cannot be automatically resolved by Leapp. "
                            "Problematic repository: {0}".format(target_repo.repoid)
                        ),
                        reporting.Severity(reporting.Severity.MEDIUM),
                        reporting.Groups([reporting.Groups.REPOSITORY]),
                        reporting.Groups([reporting.Groups.INHIBITOR]),
                        reporting.Remediation(
                            hint=(
                                "Upgrade to a more recent MySQL version, or "
                                "uninstall the deprecated MySQL packages and disable the repository. "
                                "Note that you will also need to update any bindings (e.g., PHP or Python) "
                                "that are dependent on this MySQL version."
                            )
                        ),
                    ]
                )

            # mysqlclient is usually disabled when installed from CL MySQL Governor.
            # However, it should be enabled for the Leapp upgrade, seeing as some packages
            # from it won't update otherwise.
            if target_repo.enabled or target_repo.repoid == "mysqclient-{}".format(target_major):
                api.current_logger().debug("Generating custom cl-mysql repo: {}".format(target_repo.repoid))
                self.custom_repo_msgs.append(
                    CustomTargetRepository(
                        repoid=target_repo.repoid,
                        name=target_repo.name,
                        baseurl=target_repo.baseurl,
                        enabled=True,
                    )
                )
                self.mapping_msgs.append(
                    construct_repomap_data(source_repo.repoid, target_repo.repoid)
                )
                # Gather the enabled repositories for the new repofile.
                # They'll be used to create a new custom repofile for the target userspace.
                cl_target_repofile_list.append(target_repo)

        if any(repo.enabled for repo in repofile_data.data):
            self.mysql_types.add("cloudlinux")
            # Provide the object with the modified repository data to the target userspace.
            cl_target_repofile_data = RepositoryFile(data=cl_target_repofile_list, file=repofile_data.file)
            leapp_repocopy = create_leapp_repofile_copy(cl_target_repofile_data, repofile_name)
            api.produce(CustomTargetRepositoryFile(file=leapp_repocopy))
        else:
            api.current_logger().debug("No repos from CloudLinux repofile {} enabled, ignoring".format(repofile_name))

    def mariadb_process(self, repofile_name, repofile_data):
        """
        Process upstream MariaDB options.

        Versions of MariaDB installed from https://mariadb.org/.
        """
        cl_target_repofile_list = []
        target_major = get_target_major_version()
        source_major = get_source_major_version()

        for source_repo in repofile_data.data:
            # Maria URLs look like this:
            # baseurl = https://archive.mariadb.org/mariadb-10.3/yum/centos/7/x86_64
            # baseurl = https://archive.mariadb.org/mariadb-10.7/yum/centos7-ppc64/
            # We want to replace the source_major in OS name after /yum/ with target_major
            target_repo = copy.deepcopy(source_repo)
            target_repo.repoid = "{}-{}".format(target_repo.repoid, target_major)
            # Replace the first occurrence of source_major with target_major after 'yum'
            url_parts = target_repo.baseurl.split("yum", 1)
            if len(url_parts) == 2:
                # Replace only the first digit (source_major) after 'yum'
                url_parts[1] = url_parts[1].replace(str(source_major), str(target_major), 1)
                target_repo.baseurl = "yum".join(url_parts)

            if target_repo.enabled:
                api.current_logger().debug("Generating custom MariaDB repo: {}".format(target_repo.repoid))
                self.custom_repo_msgs.append(
                    CustomTargetRepository(
                        repoid=target_repo.repoid,
                        name=target_repo.name,
                        baseurl=target_repo.baseurl,
                        enabled=target_repo.enabled,
                    )
                )
                self.mapping_msgs.append(
                    construct_repomap_data(source_repo.repoid, target_repo.repoid)
                )
                cl_target_repofile_list.append(target_repo)

        if any(repo.enabled for repo in repofile_data.data):
            # Since MariaDB URLs have major versions written in, we need a new repo file
            # to feed to the target userspace.
            self.mysql_types.add("mariadb")
            cl_target_repofile_data = RepositoryFile(data=cl_target_repofile_list, file=repofile_data.file)
            leapp_repocopy = create_leapp_repofile_copy(cl_target_repofile_data, repofile_name)
            api.produce(CustomTargetRepositoryFile(file=leapp_repocopy))
        else:
            api.current_logger().debug("No repos from MariaDB repofile {} enabled, ignoring".format(repofile_name))

    def mysql_process(self, repofile_name, repofile_data):
        """
        Process upstream MySQL options.

        Versions of MySQL installed from https://mysql.com/.
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
                self.custom_repo_msgs.append(
                    CustomTargetRepository(
                        repoid=target_repo.repoid,
                        name=target_repo.name,
                        baseurl=target_repo.baseurl,
                        enabled=target_repo.enabled,
                    )
                )
                self.mapping_msgs.append(
                    construct_repomap_data(source_repo.repoid, target_repo.repoid)
                )
                cl_target_repofile_list.append(target_repo)

        if any(repo.enabled for repo in repofile_data.data):
            # MySQL typically has multiple repo files, so we want to make sure we're
            # adding the type to list only once.
            self.mysql_types.add("mysql")
            cl_target_repofile_data = RepositoryFile(data=cl_target_repofile_list, file=repofile_data.file)
            leapp_repocopy = create_leapp_repofile_copy(cl_target_repofile_data, repofile_name)
            api.produce(CustomTargetRepositoryFile(file=leapp_repocopy))
        else:
            api.current_logger().debug("No repos from MySQL repofile {} enabled, ignoring".format(repofile_name))

    def finalize(self):
        """Use the data collected to produce messages and reports."""
        if len(self.mysql_types) == 0:
            api.current_logger().debug("No installed MySQL/MariaDB detected")
        else:
            reporting.create_report(
                [
                    reporting.Title("MySQL database backup recommended"),
                    reporting.Summary(
                        "A MySQL/MariaDB installation has been detected on this machine. "
                        "It is recommended to make a database backup before proceeding with the upgrade."
                    ),
                    reporting.Severity(reporting.Severity.HIGH),
                    reporting.Groups([reporting.Groups.REPOSITORY]),
                ]
            )

            for msg in self.custom_repo_msgs:
                api.produce(msg)
            for msg in self.mapping_msgs:
                api.produce(msg)

            if len(self.mysql_types) == 1:
                api.current_logger().debug(
                    "Detected MySQL/MariaDB type: {}, version: {}".format(list(self.mysql_types)[0], self.clmysql_type)
                )
            else:
                api.current_logger().warning("Detected multiple MySQL types: {}".format(", ".join(self.mysql_types)))
                reporting.create_report(
                    [
                        reporting.Title("Multpile MySQL/MariaDB versions detected"),
                        reporting.Summary(
                            "Package repositories for multiple distributions of MySQL/MariaDB "
                            "were detected on the system. "
                            "Leapp will attempt to update all distributions detected. "
                            "To update only the distribution you use, disable YUM package repositories for all "
                            "other distributions. "
                            "Detected: {0}".format(", ".join(self.mysql_types))
                        ),
                        reporting.Severity(reporting.Severity.MEDIUM),
                        reporting.Groups([reporting.Groups.REPOSITORY, reporting.Groups.OS_FACTS]),
                    ]
                )

        if "cloudlinux" in self.mysql_types and self.clmysql_type in MODULE_STREAMS.keys():
            mod_name, mod_stream = MODULE_STREAMS[self.clmysql_type].split(":")
            modules_to_enable = [Module(name=mod_name, stream=mod_stream)]
            pkg_prefix = get_pkg_prefix(self.clmysql_type)

            api.current_logger().debug("Enabling DNF module: {}:{}".format(mod_name, mod_stream))
            api.produce(
                RpmTransactionTasks(to_upgrade=build_install_list(pkg_prefix), modules_to_enable=modules_to_enable)
            )

        api.produce(
            InstalledMySqlTypes(
                types=list(self.mysql_types),
                version=self.clmysql_type,
            )
        )

    def process(self):
        """Main processing function."""

        for repofile_full in os.listdir(REPO_DIR):
            # Don't touch non-repository files or copied repofiles created by Leapp.
            if repofile_full.endswith(LEAPP_COPY_SUFFIX) or not repofile_full.endswith(REPOFILE_SUFFIX):
                continue
            # Cut the .repo part to get only the name.
            repofile_name = repofile_full[: -len(REPOFILE_SUFFIX)]
            full_repo_path = os.path.join(REPO_DIR, repofile_full)
            repofile_data = repofileutils.parse_repofile(full_repo_path)

            # Parse any repository files that may have something to do with MySQL or MariaDB.

            if any(mark in repofile_name for mark in CL_MARKERS):
                api.current_logger().debug(
                    "Processing CL-related repofile {}, full path: {}".format(repofile_full, full_repo_path)
                )
                self.clmysql_process(repofile_name, repofile_data)

            # Process MariaDB options.
            elif any(mark in repofile_name for mark in MARIA_MARKERS):
                api.current_logger().debug(
                    "Processing MariaDB-related repofile {}, full path: {}".format(repofile_full, full_repo_path)
                )
                self.mariadb_process(repofile_name, repofile_data)

            # Process MySQL options.
            elif any(mark in repofile_name for mark in MYSQL_MARKERS):
                api.current_logger().debug(
                    "Processing MySQL-related repofile {}, full path: {}".format(repofile_full, full_repo_path)
                )
                self.mysql_process(repofile_name, repofile_data)

        self.finalize()
