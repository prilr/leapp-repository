from leapp.actors import Actor
from leapp.libraries.common.config import architecture
from leapp.models import FirmwareFacts, GrubDevice, UpdateGrub
from leapp.reporting import Report, create_report
from leapp import reporting
from leapp.tags import ChecksPhaseTag, IPUWorkflowTag
from leapp.utils.deprecation import suppress_deprecation


GRUB_SUMMARY = ('On legacy (BIOS) systems, GRUB core (located in the gap between the MBR and the '
                'first partition) does not get automatically updated when GRUB is upgraded.')


# TODO: remove this actor completely after the deprecation period expires
@suppress_deprecation(GrubDevice, UpdateGrub)
class CheckGrubCore(Actor):
    """
    Check whether we are on legacy (BIOS) system and instruct Leapp to upgrade GRUB core
    """

    name = 'check_grub_core'
    consumes = (FirmwareFacts, GrubDevice)
    produces = (Report, UpdateGrub)
    tags = (ChecksPhaseTag, IPUWorkflowTag)

    def process(self):
        if architecture.matches_architecture(architecture.ARCH_S390X):
            # s390x archs use ZIPL instead of GRUB
            return

        ff = next(self.consume(FirmwareFacts), None)
        if ff and ff.firmware == 'bios':
            dev = next(self.consume(GrubDevice), None)
            if dev:
                self.produce(UpdateGrub(grub_device=dev.grub_device))
                create_report([
                    reporting.Title(
                        'GRUB core will be updated during upgrade'
                    ),
                    reporting.Summary(GRUB_SUMMARY),
                    reporting.Severity(reporting.Severity.HIGH),
                    reporting.Tags([reporting.Tags.BOOT]),
                ])
            else:
                create_report([
                    reporting.Title('Leapp could not identify where GRUB core is located'),
                    reporting.Summary(
                        'We assumed GRUB2 core is located on the same device(s) as /boot, '
                        'however Leapp could not detect GRUB2 on those device(s). '
                        'This means GRUB2 core will not be updated during the upgrade process and '
                        'the system will probably ' 'boot into the old kernel after the upgrade. '
                        'GRUB2 core needs to be updated manually on legacy (BIOS) systems to '
                        'fix this.'
                    ),
                    reporting.Severity(reporting.Severity.HIGH),
                    reporting.Tags([reporting.Tags.BOOT]),
                    reporting.Remediation(
                        hint='Please run the "grub2-install <GRUB_DEVICE>" command manually '
                        'after the upgrade'),
                ])
