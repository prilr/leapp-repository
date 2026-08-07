from leapp.actors import Actor
from leapp.libraries.actor import enablemigratedtimers
from leapp.libraries.common.cllaunch import run_on_cloudlinux
from leapp.models import SystemdTimersInfoSource
from leapp.reporting import Report
from leapp.tags import FirstBootPhaseTag, IPUWorkflowTag


class EnableMigratedTimers(Actor):
    """
    Enable systemd timers that the upgrade left disabled despite a vendor preset.

    Some packages replace a cron job with a systemd timer across major versions.
    logrotate is the canonical case (EL8 ships /etc/cron.daily/logrotate, EL9
    ships logrotate.timer with preset 'enable'), and mdadm does the same with
    /etc/cron.d/raid-check and raid-check.timer. Because the package is upgraded
    rather than freshly installed, its %systemd_post scriptlet does not apply the
    timer's preset, and leapp's systemd state transition only covers '.service'
    units. The timer is therefore left disabled, silently stopping its work - no
    logs are rotated, no RAID consistency check is ever run.

    Only timers absent from the source system are considered, so a timer the
    administrator disabled deliberately is never re-enabled.
    """

    name = 'enable_migrated_timers'
    consumes = (SystemdTimersInfoSource,)
    produces = (Report,)
    tags = (FirstBootPhaseTag, IPUWorkflowTag)

    @run_on_cloudlinux
    def process(self):
        enablemigratedtimers.process()
