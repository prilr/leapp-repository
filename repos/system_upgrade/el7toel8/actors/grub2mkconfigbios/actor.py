from leapp.actors import Actor
from leapp.libraries.actor import grub2mkconfigbios
from leapp.models import FirmwareFacts, TransactionCompleted
from leapp.reporting import Report
from leapp.tags import IPUWorkflowTag, RPMUpgradePhaseTag


class Grub2MkconfigBios(Actor):
    """
    Regenerate GRUB2 config after the el7-to-el8 RPM upgrade transaction on BIOS systems.

    On BIOS (non-EFI) x86_64 and aarch64 systems the grub2-pc package
    scriptlet may run grub2-mkconfig before the new kernel's BLS entries are
    in place, leaving grub.cfg empty or stale.  On multi-disk servers this
    consistently causes the system to enter GRUB rescue mode on the first
    reboot after the initramfs upgrade phase.

    This actor runs grub2-mkconfig after TransactionCompleted to ensure all
    BLS entries exist and the resulting configuration is correct.
    """

    name = 'grub2mkconfig_bios'
    consumes = (FirmwareFacts, TransactionCompleted)
    produces = (Report,)
    tags = (RPMUpgradePhaseTag, IPUWorkflowTag)

    def process(self):
        grub2mkconfigbios.process()
