from leapp.actors import Actor
from leapp.exceptions import StopActorExecutionError
from leapp.libraries.actor import scansystemdtimerssource
from leapp.libraries.common.cllaunch import run_on_cloudlinux
from leapp.libraries.stdlib import CalledProcessError
from leapp.models import SystemdTimersInfoSource
from leapp.tags import FactsPhaseTag, IPUWorkflowTag


class ScanSystemdTimersSource(Actor):
    """
    Provide the list of systemd timer unit files present on the source system.

    Leapp's own systemd scan is restricted to '.service' units, so timers are
    recorded nowhere else. :class:`EnableMigratedTimers` needs this inventory on
    the target system to tell a timer that is new on the target apart from one
    that already existed on the source, whose state the administrator may have
    chosen deliberately.
    """

    name = 'scan_systemd_timers_source'
    consumes = ()
    produces = (SystemdTimersInfoSource,)
    tags = (FactsPhaseTag, IPUWorkflowTag)

    @run_on_cloudlinux
    def process(self):
        try:
            timers = scansystemdtimerssource.get_source_timers()
        except CalledProcessError as err:
            raise StopActorExecutionError(
                message='Cannot obtain the list of systemd timer unit files.',
                details={'details': str(err), 'stderr': err.stderr}
            )

        self.produce(SystemdTimersInfoSource(timers=timers))
