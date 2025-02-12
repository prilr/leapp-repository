from __future__ import print_function
from operator import is_
import os

from leapp.actors import Actor
from leapp.tags import ApplicationsPhaseTag, IPUWorkflowTag
from leapp.libraries.common.cllaunch import run_on_cloudlinux
from leapp.libraries.common.backup import backup_and_remove
from leapp.libraries.common.config.version import get_target_major_version

REPO_DIR = '/etc/yum.repos.d'
EPEL_INSTALL_URL = 'https://dl.fedoraproject.org/pub/epel/epel-release-latest-{}.noarch.rpm'.format(get_target_major_version())


class RefreshEPEL(Actor):
    """
    Check that the EPEL repositories are correctly configured after the upgrade.

    Depending on how the upgrade went, the EPEL repositories might still be targeting the old OS version.
    This actor checks that the EPEL repositories are correctly configured and if not, it will install the
    correct EPEL release package and refresh the repositories.
    """

    name = 'refresh_epel'
    # We can't depend on InstalledRPM message because by this point
    # the system is upgraded and the RPMs are not the same as when the data was collected.
    consumes = ()
    produces = ()
    tags = (ApplicationsPhaseTag.After, IPUWorkflowTag)

    def clear_epel_repo_files(self):
        for repofile in os.listdir(REPO_DIR):
            if repofile.startswith('epel'):
                epel_file = os.path.join(REPO_DIR, repofile)
                backup_and_remove(epel_file)

    def install_epel_release_package(self, target_url):
        os.system('dnf install {}'.format(target_url))
        self.log.info('EPEL release package installed: {}'.format(target_url))

    @run_on_cloudlinux
    def process(self):
        target_version = int(get_target_major_version())
        target_epel_release = EPEL_INSTALL_URL.format(target_version)

        # EPEL release package name is 'epel-release' and the version should match the target OS version
        epel_release_package = 'epel-release'

        is_epel_installed = os.system('rpm -q {}'.format(epel_release_package)) == 0
        is_correct_version = os.system('rpm -q {}-{}'.format(epel_release_package, target_version)) == 0
        epel_files_verified = os.system('rpm -V {}'.format(epel_release_package)) == 0

        # It's possible (although unusual) that the correct EPEL release package is installed during the upgrade,
        # but the EPEL repository files still point to the old OS version.
        # This was observed on client machines before.

        if (is_epel_installed and not is_correct_version) or not epel_files_verified:
            # If the EPEL release package is installed but not the correct version, remove it
            # Same if the files from the package were modified
            os.system('rpm -e {}'.format(epel_release_package))
        if not is_epel_installed or not is_correct_version or not epel_files_verified:
            # Clear the EPEL repository files
            self.clear_epel_repo_files()
            # Install the correct EPEL release package
            self.install_epel_release_package(target_epel_release)
            # Logging for clarity
            self.log.info('EPEL release package installation invoked for: {}'.format(target_epel_release))
