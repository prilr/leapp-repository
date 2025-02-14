import os
from leapp.actors import Actor
from leapp.reporting import Report
from leapp.tags import ChecksPhaseTag, IPUWorkflowTag
from leapp.libraries.common.cllaunch import run_on_cloudlinux
from leapp.libraries.stdlib import api
from leapp.models import (
    TargetUserSpacePreupgradeTasks,
    CopyFile
)


RHN_CONFIG_DIR = '/etc/sysconfig/rhn'
REQUIRED_PKGS = ['dnf-plugin-spacewalk', 'rhn-client-tools']


class CopyClLicense(Actor):
    """
    Produce task to copy CloudLinux license files to target system.
    """

    name = 'copy_rhn_client_tools_config'
    consumes = ()
    produces = (Report, TargetUserSpacePreupgradeTasks)
    tags = (ChecksPhaseTag, IPUWorkflowTag)

    @run_on_cloudlinux
    def process(self):
        """
        Produce artifacts to copy RHN configuration files
        and install packages to the target userspace,
        including up2date and systemid.
        """
        files_to_copy = []
        for dirpath, _, filenames in os.walk(RHN_CONFIG_DIR):
            for filename in filenames:
                src_path = os.path.join(dirpath, filename)
                if os.path.isfile(src_path):
                    files_to_copy.append(CopyFile(src=src_path))

        api.produce(TargetUserSpacePreupgradeTasks(
            install_rpms=REQUIRED_PKGS,
            copy_files=files_to_copy
        ))
