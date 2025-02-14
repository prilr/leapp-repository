from leapp.actors import Actor
from leapp.models import InstalledRPM
from leapp.tags import DownloadPhaseTag, IPUWorkflowTag
from leapp.libraries.common.cllaunch import run_on_cloudlinux
from leapp.libraries.actor import clearpackageconflicts


class ClearPackageConflicts(Actor):
    """
    Remove several Python package files manually to resolve conflicts
    between versions of packages to be upgraded.

    When the corresponding packages are detected,
    the conflicting files are removed to allow for an upgrade to the new package versions.

    While most packages are handled automatically by the package manager,
    some specific packages require direct intervention to resolve conflicts
    between their own versions on different OS releases.
    """

    name = "clear_package_conflicts"
    consumes = (InstalledRPM,)
    produces = ()
    tags = (DownloadPhaseTag.Before, IPUWorkflowTag)

    @run_on_cloudlinux
    def process(self):
        clearpackageconflicts.process()
