from leapp.actors import Actor
from leapp.libraries.actor import setdefaultbootkernelforclrelease
from leapp.libraries.common.cllaunch import run_on_cloudlinux
from leapp.libraries.common.config.version import get_target_major_version
from leapp.tags import FinalizationPhaseTag, IPUWorkflowTag


class SetDefaultBootKernelForCLRelease(Actor):
    """
    Correct the grub default kernel when it does not match the cloudlinux-release minor version.

    When the CLN channel serves a newer-minor kernel (e.g. el9_7) while the system is
    upgrading to CL9.6, the forcedefaultboottotargetkernelversion actor may set that newer
    kernel as the default boot entry. This actor runs after that and overrides the default
    back to the kernel whose minor version matches cloudlinux-release (e.g. el9_6). Without
    this correction, kernel modules like kmod-lve may fail to load because the correct module
    build is not available for the newer-minor kernel.
    """

    name = 'set_default_boot_kernel_for_cl_release'
    consumes = ()
    produces = ()
    tags = (FinalizationPhaseTag.After, IPUWorkflowTag)

    @run_on_cloudlinux
    def process(self):
        setdefaultbootkernelforclrelease.process(target_major=get_target_major_version())
