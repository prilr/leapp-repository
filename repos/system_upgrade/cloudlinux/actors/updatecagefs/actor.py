import os

from leapp.actors import Actor
from leapp.libraries.stdlib import run, CalledProcessError
from leapp.reporting import Report, create_report
from leapp.tags import FirstBootPhaseTag, IPUWorkflowTag
from leapp.libraries.common.cllaunch import run_on_cloudlinux


class UpdateCagefs(Actor):
    """
    Force update of cagefs and re-run CloudLinux Selector setup.

    cagefs should reflect massive changes in system made in previous phases.
    `--force-update` rebuilds the skeleton but does not regenerate the native
    PHP Selector wiring under /usr/selector/* and /usr/selector.etc/, which is
    the job of `--setup-cl-selector` (see cagefsctl.setup_cl_alt). Running it
    here is a safe no-op when no selector setup is needed and a partial repair
    when /etc/cl.selector/native.conf still resolves to existing binaries.
    """

    name = 'update_cagefs'
    consumes = ()
    produces = (Report,)
    tags = (FirstBootPhaseTag, IPUWorkflowTag)

    @run_on_cloudlinux
    def process(self):
        if not os.path.exists('/usr/sbin/cagefsctl'):
            return

        try:
            run(['/usr/sbin/cagefsctl', '--force-update'], checked=True)
            self.log.info('cagefs update was successful')
        except CalledProcessError as e:
            # cagefsctl prints errors in stdout
            self.log.error(e.stdout)
            self.log.error(
                'Command "cagefsctl --force-update" finished with exit code {}, '
                'the filesystem inside cagefs may be out-of-date.\n'
                'Check cagefsctl output above and in /var/log/cagefs-update.log, '
                'rerun "cagefsctl --force-update" after fixing the issues.'.format(e.exit_code)
            )

        try:
            run(['/usr/sbin/cagefsctl', '--setup-cl-selector'], checked=True)
            self.log.info('CloudLinux Selector setup was successful')
        except CalledProcessError as e:
            self.log.error(e.stdout)
            self.log.error(
                'Command "cagefsctl --setup-cl-selector" finished with exit code {}, '
                'native PHP Selector / CageFS integration may be incomplete.\n'
                'Check cagefsctl output above and rerun "cagefsctl --setup-cl-selector" '
                'after fixing the issues.'.format(e.exit_code)
            )
