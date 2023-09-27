from leapp.actors import Actor
from leapp import reporting
from leapp.reporting import Report
from leapp.tags import ChecksPhaseTag, IPUWorkflowTag
from leapp.libraries.common.cllaunch import run_on_cloudlinux


class CheckRhnVersionOverride(Actor):
    """
    Check if the up2date versionOverride option has not been set.
    """

    name = 'check_rhn_version_override'
    consumes = ()
    produces = (Report,)
    tags = (ChecksPhaseTag, IPUWorkflowTag)

    @run_on_cloudlinux
    def process(self):
        up2date_config = '/etc/sysconfig/rhn/up2date'
        with open(up2date_config, 'r') as f:
            config_data = f.readlines()
            for line in config_data:
                if line.startswith('versionOverride='):
                    stripped_line = line.strip().split("=")
                    versionOverrideValue = stripped_line[1]
                    # If the version is being overriden to 8, we can continue as is.
                    if versionOverrideValue not in ['', '8']:
                        title = 'RHN up2date: versionOverride overwritten by the upgrade'
                        summary = ("The RHN config file up2date has a set value of the versionOverride option: {}."
                                " This value will get overwritten by the upgrade process, and reset to an empty"
                                " value once it's complete.".format(versionOverrideValue))
                        reporting.create_report([
                            reporting.Title(title),
                            reporting.Summary(summary),
                            reporting.Severity(reporting.Severity.MEDIUM),
                            reporting.Tags([reporting.Tags.OS_FACTS]),
                            reporting.RelatedResource('file', '/etc/sysconfig/rhn/up2date')
                        ])
