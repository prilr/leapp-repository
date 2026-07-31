from leapp.actors import Actor
from leapp.libraries.actor import checknetworkmanagerunmanaged
from leapp.libraries.common.cllaunch import run_on_cloudlinux
from leapp.reporting import Report
from leapp.tags import ChecksPhaseTag, IPUWorkflowTag


class CheckNetworkManagerUnmanaged(Actor):
    """
    Inhibit the upgrade when NetworkManager is configured to manage no device.

    A keyfile under /etc/NetworkManager/conf.d setting ``unmanaged-devices=*``
    is survivable while network-scripts is installed, because the legacy
    network.service brings the interfaces up instead. CloudLinux 9 drops
    network-scripts, so the same configuration leaves the upgraded host with no
    network at all - reachable only from the console.

    Upstream's el8toel9 checkifcfg actor covers the equivalent ``NM_CONTROLLED=no``
    setting in ifcfg files, but does not look at conf.d at all, so this class of
    configuration reaches the reboot unreported. This actor closes that gap the
    same way: it surfaces the problem and lets the administrator decide, rather
    than editing network configuration on their behalf.

    See CLOS-4330 (one-context leaves such an override behind on OpenNebula guests).
    """

    name = 'check_network_manager_unmanaged'
    consumes = ()
    produces = (Report,)
    tags = (ChecksPhaseTag, IPUWorkflowTag)

    @run_on_cloudlinux
    def process(self):
        checknetworkmanagerunmanaged.process()
