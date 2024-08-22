from leapp.actors import Actor
from leapp.libraries.stdlib import api
from leapp.tags import DownloadPhaseTag, IPUWorkflowTag
from leapp.libraries.stdlib import CalledProcessError, run
from leapp.libraries.common.cllaunch import run_on_cloudlinux
from leapp import reporting
from leapp.reporting import Report


class UpdateAlmaLinuxKey(Actor):
    """
    Import the AlmaLinux GPG key to the system to be able to download upgrade packages.

    The AlmaLinux 8 packages will not be accepted by the system otherwise.
    See https://almalinux.org/blog/2023-12-20-almalinux-8-key-update/
    """

    name = "update_almalinux_key"
    consumes = ()
    produces = (Report,)
    tags = (IPUWorkflowTag, DownloadPhaseTag.Before)

    alma_key_url = "https://repo.almalinux.org/almalinux/RPM-GPG-KEY-AlmaLinux"

    @run_on_cloudlinux
    def process(self):
        switch_cmd = ["rpm", "--import", self.alma_key_url]
        try:
            res = run(switch_cmd)
            self.log.debug('Command "%s" result: %s', switch_cmd, res)
        except CalledProcessError as e:
            reporting.create_report(
                [
                    reporting.Title(
                        "Failed to import the AlmaLinux GPG key."
                    ),
                    reporting.Summary(
                        "Command {} failed with exit code {}."
                        " The most probable cause of that is a network issue.".format(e.command, e.exit_code)
                    ),
                    reporting.Remediation(
                        hint="Check the state of this system's network connection and the reachability of the key URL."
                    ),
                    reporting.Severity(reporting.Severity.HIGH),
                    reporting.Groups(
                        [reporting.Groups.OS_FACTS, reporting.Groups.NETWORK]
                    ),
                    reporting.Groups([reporting.Groups.INHIBITOR]),
                ]
            )
        except OSError as e:
            api.current_logger().error(
                "Could not call an RPM command: Message: %s", str(e), exc_info=True
            )
