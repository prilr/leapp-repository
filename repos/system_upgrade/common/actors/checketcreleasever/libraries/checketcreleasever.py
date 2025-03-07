from leapp import reporting
from leapp.libraries.stdlib import api
from leapp.models import PkgManagerInfo, RHUIInfo
from leapp.libraries.common.config.version import get_target_major_version


def handle_etc_releasever():

    target_version = get_target_major_version()
    reporting.create_report([
        reporting.Title(
            'Release version in /etc/dnf/vars/releasever will be set to the major target release'
        ),
        reporting.Summary(
            'On this system, Leapp detected "releasever" variable is either configured through DNF/YUM configuration '
            'file and/or the system is using RHUI infrastructure. In order to avoid issues with repofile URLs '
            '(when --release option is not provided) in cases where there is the previous major.minor version value '
            'in the configuration, release version will be set to the target release version ({}). This will also '
            'ensure the system stays on the expected target version after the upgrade'.format(target_version)
        ),
        reporting.Severity(reporting.Severity.INFO),
        reporting.Groups([reporting.Groups.UPGRADE_PROCESS]),
    ])


def process():
    pkg_facts = next(api.consume(PkgManagerInfo), None)
    rhui_facts = next(api.consume(RHUIInfo), None)
    if pkg_facts and pkg_facts.etc_releasever is not None or rhui_facts:
        handle_etc_releasever()
    else:
        api.current_logger().debug(
            'Skipping execution. "releasever" is not set in DNF/YUM vars directory and no RHUIInfo has '
            'been produced'
        )
