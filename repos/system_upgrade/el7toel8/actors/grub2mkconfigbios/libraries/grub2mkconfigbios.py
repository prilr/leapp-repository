from leapp import reporting
from leapp.libraries.common.config import architecture
from leapp.libraries.stdlib import api, CalledProcessError, run
from leapp.models import FirmwareFacts

GRUB_CFG_PATH = '/boot/grub2/grub.cfg'


def process():
    """
    Regenerate GRUB2 configuration on BIOS systems after the RPM upgrade transaction.

    On BIOS x86_64/aarch64 systems the grub2-pc package scriptlet may call
    grub2-mkconfig before the new kernel's BLS entries are written to
    /boot/loader/entries/, producing an empty or stale grub.cfg.  On
    multi-disk servers this consistently causes the system to enter GRUB
    rescue mode on the first reboot after the initramfs upgrade phase.

    Running grub2-mkconfig here, after TransactionCompleted (which guarantees
    all RPM %%posttrans scriptlets have finished), ensures that BLS entries
    are present and the generated config is correct.
    """
    if architecture.matches_architecture(architecture.ARCH_S390X):
        return
    if architecture.matches_architecture(architecture.ARCH_PPC64LE):
        # ppc64le BIOS mkconfig is handled by grub2mkconfig_on_ppc64
        return

    ff = next(api.consume(FirmwareFacts), None)
    if not ff or ff.firmware != 'bios':
        return

    api.current_logger().info(
        'Regenerating GRUB2 configuration after RPM upgrade transaction'
    )
    try:
        run(['grub2-mkconfig', '-o', GRUB_CFG_PATH])
    except (CalledProcessError, OSError) as e:
        api.current_logger().error(
            'Command grub2-mkconfig -o {} failed: {}'.format(GRUB_CFG_PATH, e)
        )
        reporting.create_report([
            reporting.Title('Failed to regenerate GRUB2 configuration'),
            reporting.Summary(
                'Leapp failed to regenerate the GRUB2 configuration after the RPM '
                'upgrade transaction. The system may fail to boot after the upgrade '
                'due to a missing or empty boot menu. '
                'Error: {}'.format(str(e))
            ),
            reporting.Groups([reporting.Groups.BOOT]),
            reporting.Severity(reporting.Severity.HIGH),
            reporting.Remediation(
                hint=(
                    'If the system fails to boot, boot from rescue media and run: '
                    'grub2-mkconfig -o /boot/grub2/grub.cfg'
                )
            ),
        ])
