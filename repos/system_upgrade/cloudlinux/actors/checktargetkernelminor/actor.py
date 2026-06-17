from leapp.actors import Actor
from leapp.libraries.actor import checktargetkernelminor
from leapp.libraries.common.cllaunch import run_on_cloudlinux
from leapp.libraries.stdlib import api
from leapp.models import TargetUserSpaceInfo
from leapp.reporting import Report
from leapp.tags import IPUWorkflowTag, TargetTransactionChecksPhaseTag


class CheckTargetKernelMinor(Actor):
    """
    Inhibit the upgrade when target CloudLinux repositories would deliver
    a kernel from a newer minor than the rest of the CloudLinux userland.

    Detects the gradual-rollout-leak behind CLOS-3716 (ZD 268790): the CLN
    package channel serves the latest-minor kernel ahead of the matching
    userland during a staged minor rollout.  Installing such a kernel on
    the older-minor userland breaks per-kernel-minor modules like kmodlve,
    so we refuse the upgrade until the rollout is complete or repos are
    pinned to one minor.

    See the `checktargetkernelminor` library docstring for the detection
    details.
    """

    name = 'check_target_kernel_minor'
    consumes = (TargetUserSpaceInfo,)
    produces = (Report,)
    tags = (IPUWorkflowTag, TargetTransactionChecksPhaseTag)

    @run_on_cloudlinux
    def process(self):
        info = next(api.consume(TargetUserSpaceInfo), None)
        if info is None:
            self.log.info(
                'No TargetUserSpaceInfo available; skipping kernel-minor check.'
            )
            return
        checktargetkernelminor.process(installroot=info.path)
