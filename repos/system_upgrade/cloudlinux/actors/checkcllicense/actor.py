from leapp.actors import Actor
from leapp import reporting
from leapp.reporting import Report
from leapp.tags import ChecksPhaseTag, IPUWorkflowTag
from leapp.libraries.stdlib import CalledProcessError, run, api
from leapp.libraries.common.cllaunch import run_on_cloudlinux

from leapp.models import (
    TargetUserSpacePreupgradeTasks,
    TargetUserSpaceUpgradeTasks,
    CopyFile
)

import os

RHN_CONFIG_DIR = '/etc/sysconfig/rhn'
REQUIRED_PKGS = ['dnf-plugin-spacewalk', 'rhn-client-tools']


def rhn_to_target_userspace():
    """
    Produce messages to copy RHN configuration files and packages to the target userspace
    """
    files_to_copy = []
    for dirpath, _, filenames in os.walk(RHN_CONFIG_DIR):
        for filename in filenames:
            src_path = os.path.join(dirpath, filename)
            if os.path.isfile(src_path):
                files_to_copy.append(CopyFile(src=src_path))

    api.produce(TargetUserSpacePreupgradeTasks(install_rpms=REQUIRED_PKGS, copy_files=files_to_copy))
    api.produce(TargetUserSpaceUpgradeTasks(install_rpms=REQUIRED_PKGS, copy_files=files_to_copy))


class CheckClLicense(Actor):
    """
    Check if the server has a CL license
    """

    name = 'check_cl_license'
    consumes = ()
    produces = (Report, TargetUserSpacePreupgradeTasks, TargetUserSpaceUpgradeTasks)
    tags = (ChecksPhaseTag, IPUWorkflowTag)

    system_id_path = '/etc/sysconfig/rhn/systemid'
    rhn_check_bin = '/usr/sbin/rhn_check'

    # # Copy RHN data independent from RHSM config
    # if os.path.isdir('/etc/sysconfig/rhn'):
    #     run(['rm', '-rf', os.path.join(target_etc, 'sysconfig/rhn')])
    #     context.copytree_from('/etc/sysconfig/rhn', os.path.join(target_etc, 'sysconfig/rhn'))

    @run_on_cloudlinux
    def process(self):
        res = None
        if os.path.exists(self.system_id_path):
            res = run([self.rhn_check_bin])
            self.log.debug('rhn_check result: %s', res)
        if not res or res['exit_code'] != 0 or res['stderr']:
            title = 'Server does not have an active CloudLinux license'
            summary = 'Server does not have an active CloudLinux license. This renders key CloudLinux packages ' \
                      'inaccessible, inhibiting the upgrade process.'
            remediation = 'Activate a CloudLinux license on this machine before running Leapp again.'
            reporting.create_report([
                reporting.Title(title),
                reporting.Summary(summary),
                reporting.Severity(reporting.Severity.HIGH),
                reporting.Groups([reporting.Groups.OS_FACTS]),
                reporting.Groups([reporting.Groups.INHIBITOR]),
                reporting.Remediation(hint=remediation),
            ])
        else:
            rhn_to_target_userspace()
