import os

from leapp.actors import Actor
from leapp import reporting
from leapp.reporting import Report, create_report
from leapp.tags import FirstBootPhaseTag, IPUWorkflowTag
from leapp.libraries.common.cllaunch import run_on_cloudlinux
from leapp.libraries.actor.updatecagefs import (
    CAGEFSCTL, CAGEFS_UPDATE_LOG, CAGEFS_UPDATE_SERVICE, schedule_cagefs_update
)


class UpdateCagefs(Actor):
    """
    Schedule a post-boot CageFS force-update.

    cagefs should reflect the massive package changes made in previous phases.
    The update is registered as a one-shot systemd service that runs after
    cagefs.service (which mounts the skeleton) so the skeleton is consistent
    before --force-update begins.  The service runs in the background relative
    to other multi-user.target services and self-disables on success.
    On servers with many users or large numbers of installed packages,
    cagefsctl --force-update can take a very long time (potentially hours).
    """

    name = 'update_cagefs'
    consumes = ()
    produces = (Report,)
    tags = (FirstBootPhaseTag, IPUWorkflowTag)

    @run_on_cloudlinux
    def process(self):
        if not os.path.exists(CAGEFSCTL):
            return

        error = schedule_cagefs_update()

        if error:
            self.log.error('Failed to schedule cagefsctl --force-update: %s', error)
            create_report([
                reporting.Title('Failed to schedule CageFS update'),
                reporting.Summary(
                    'Could not schedule "cagefsctl --force-update" as a systemd service: {error}. '
                    'Run "cagefsctl --force-update" manually after the upgrade.'.format(error=error)
                ),
                reporting.Severity(reporting.Severity.HIGH),
                reporting.Groups([reporting.Groups.FAILURE, reporting.Groups.POST]),
            ])
            return

        self.log.info('CageFS update scheduled as %s.service', CAGEFS_UPDATE_SERVICE)
        create_report([
            reporting.Title('CageFS update scheduled'),
            reporting.Summary(
                'The command "cagefsctl --force-update" has been scheduled to run '
                'after cagefs.service starts on the upgraded system. '
                'On servers with many users or many installed packages, '
                'this update can take a significant amount of time. '
                'Monitor progress in {log} or via '
                '"journalctl -u {service}.service". '
                'If the update fails, run "cagefsctl --force-update" '
                'manually.'.format(log=CAGEFS_UPDATE_LOG, service=CAGEFS_UPDATE_SERVICE)
            ),
            reporting.Severity(reporting.Severity.INFO),
            reporting.Groups([reporting.Groups.POST]),
        ])
