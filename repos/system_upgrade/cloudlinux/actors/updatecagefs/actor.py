import os

from leapp.actors import Actor
from leapp import reporting
from leapp.reporting import Report, create_report
from leapp.tags import FirstBootPhaseTag, IPUWorkflowTag
from leapp.libraries.common.cllaunch import run_on_cloudlinux
from leapp.libraries.actor.updatecagefs import (
    CAGEFSCTL, CAGEFS_UPDATE_LOG, start_cagefs_update
)


class UpdateCagefs(Actor):
    """
    Force update of cagefs.

    cagefs should reflect massive changes in system made in previous phases.
    The update runs asynchronously to avoid blocking the upgrade process, since
    on servers with many users or large numbers of installed packages, cagefsctl
    --force-update can take a very long time (potentially hours).
    """

    name = 'update_cagefs'
    consumes = ()
    produces = (Report,)
    tags = (FirstBootPhaseTag, IPUWorkflowTag)

    @run_on_cloudlinux
    def process(self):
        if not os.path.exists(CAGEFSCTL):
            return

        pid, error = start_cagefs_update()

        if error:
            self.log.error('Failed to start cagefsctl --force-update: %s', error)
            create_report([
                reporting.Title('Failed to start CageFS update'),
                reporting.Summary(
                    'Could not start "cagefsctl --force-update": {error}. '
                    'Run "cagefsctl --force-update" manually after the upgrade.'.format(error=error)
                ),
                reporting.Severity(reporting.Severity.HIGH),
                reporting.Groups([reporting.Groups.FAILURE, reporting.Groups.POST]),
            ])
            return

        self.log.info('CageFS update started in background (PID: %d)', pid)
        create_report([
            reporting.Title('CageFS update is running in the background'),
            reporting.Summary(
                'The command "cagefsctl --force-update" was started in the background '
                'to avoid blocking the upgrade process. '
                'On servers with many users or many installed packages, '
                'this update can take a significant amount of time. '
                'Monitor progress in: {log}. '
                'If the update fails, run "cagefsctl --force-update" manually.'.format(
                    log=CAGEFS_UPDATE_LOG
                )
            ),
            reporting.Severity(reporting.Severity.INFO),
            reporting.Groups([reporting.Groups.POST]),
        ])
