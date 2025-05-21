from leapp.actors import Actor
from leapp.libraries.common.cllaunch import run_on_cloudlinux
from leapp.models import Report, RepositoriesFacts
from leapp.tags import ChecksPhaseTag, IPUWorkflowTag
from leapp.libraries.actor import checkcldeployrepofile


class CheckCldeployRepofile(Actor):
    """
    Check for leftover repository configuration files from a cldeploy conversion.

    These repofiles, also known as "base repos" in the cldeploy context, are
    used to bootstrap the CL systems during the conversion process.
    Normally, they are removed by the cldeploy tool itself, but in some
    cases, they may be left behind.
    If that happens, they can cause problems with the upgrade process,
    since neither leapp nor the upgrade process itself expect them to be present.

    This actor checks for the presence of these files and warns the user to remove them if found.

    The files are located in the /etc/yum.repos.d directory and have names based on
    the URL of the repository they point to. For example:
    repo.cloudlinux.com_cloudlinux_8_BaseOS_x86_64_os_.repo
    """

    name = "check_cldeploy_repofile"
    consumes = (RepositoriesFacts,)
    produces = (Report,)
    tags = (ChecksPhaseTag, IPUWorkflowTag)

    @run_on_cloudlinux
    def process(self):
        checkcldeployrepofile.process()
