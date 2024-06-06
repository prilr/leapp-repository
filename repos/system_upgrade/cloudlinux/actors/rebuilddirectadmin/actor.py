import os

from leapp.actors import Actor
from leapp.libraries.stdlib import run, CalledProcessError
from leapp.reporting import Report, create_report
from leapp.tags import FirstBootPhaseTag, IPUWorkflowTag
from leapp.libraries.common.cllaunch import run_on_cloudlinux
from leapp.models import InstalledControlPanel

from leapp.libraries.common.detectcontrolpanel import DIRECTADMIN_NAME


class UpdateDirectAdmin(Actor):
    """
    Automatically rebuild directadmin.
    """

    name = 'update_directadmin'
    consumes = (InstalledControlPanel,)
    produces = (Report,)
    tags = (FirstBootPhaseTag, IPUWorkflowTag)

    @run_on_cloudlinux
    def process(self):
        panel = next(self.consume(InstalledControlPanel), None)
        if panel is None:
            raise StopActorExecutionError(message=("Missing information about the installed web panel."))

        if panel.name != DIRECTADMIN_NAME:
            self.log.debug('DirectAdmin not detected, skip rebuilding')
            return

        try:
            run(['/bin/da', 'build', 'all'], checked=True)
            self.log.info('DirectAdmin update was successful')
        except CalledProcessError as e:
            self.log.error(
                'Command "da build all" finished with exit code {}, '
                'the system might be unstable.\n'
                'Check /usr/local/directadmin/custombuild/custombuild.log, '
                'rerun "da build all" after fixing the issues. '
                'Contact DirectAdmin support for help.'.format(e.exit_code)
            )
