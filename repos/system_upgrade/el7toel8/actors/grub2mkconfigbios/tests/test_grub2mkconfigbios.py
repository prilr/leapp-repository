import pytest

from leapp import reporting
from leapp.libraries.actor import grub2mkconfigbios
from leapp.libraries.common import testutils
from leapp.libraries.common.config import architecture
from leapp.libraries.stdlib import CalledProcessError
from leapp.models import FirmwareFacts


def _raise_called_process_error(args=None):
    raise CalledProcessError(
        message='grub2-mkconfig failed',
        command=args,
        result={'signal': None, 'exit_code': 1, 'pid': 0, 'stdout': '', 'stderr': 'error'},
    )


class MockedRun(object):
    def __init__(self, raise_err=False):
        self.commands = []
        self.raise_err = raise_err

    def __call__(self, cmd, *args, **kwargs):
        self.commands.append(cmd)
        if self.raise_err:
            _raise_called_process_error(cmd)
        return {}


@pytest.mark.parametrize('arch,firmware,expect_call', [
    (architecture.ARCH_X86_64, 'bios', True),
    (architecture.ARCH_ARM64, 'bios', True),
    (architecture.ARCH_X86_64, 'efi', False),
    (architecture.ARCH_PPC64LE, 'bios', False),
    (architecture.ARCH_S390X, 'bios', False),
])
def test_grub2mkconfig_called_only_on_bios_x86_aarch64(monkeypatch, arch, firmware, expect_call):
    ff = FirmwareFacts(firmware=firmware)
    mocked_run = MockedRun()
    monkeypatch.setattr(reporting, 'create_report', testutils.create_report_mocked())
    monkeypatch.setattr(grub2mkconfigbios, 'run', mocked_run)
    monkeypatch.setattr(grub2mkconfigbios.api, 'current_actor',
                        testutils.CurrentActorMocked(msgs=[ff], arch=arch))
    grub2mkconfigbios.process()
    if expect_call:
        assert mocked_run.commands == [['grub2-mkconfig', '-o', '/boot/grub2/grub.cfg']]
    else:
        assert not mocked_run.commands
    assert not reporting.create_report.called


def test_grub2mkconfig_no_firmware_facts(monkeypatch):
    mocked_run = MockedRun()
    monkeypatch.setattr(reporting, 'create_report', testutils.create_report_mocked())
    monkeypatch.setattr(grub2mkconfigbios, 'run', mocked_run)
    monkeypatch.setattr(grub2mkconfigbios.api, 'current_actor',
                        testutils.CurrentActorMocked(msgs=[], arch=architecture.ARCH_X86_64))
    grub2mkconfigbios.process()
    assert not mocked_run.commands
    assert not reporting.create_report.called


def test_grub2mkconfig_failure_produces_report(monkeypatch):
    ff = FirmwareFacts(firmware='bios')
    mocked_run = MockedRun(raise_err=True)
    monkeypatch.setattr(reporting, 'create_report', testutils.create_report_mocked())
    monkeypatch.setattr(grub2mkconfigbios, 'run', mocked_run)
    monkeypatch.setattr(grub2mkconfigbios.api, 'current_actor',
                        testutils.CurrentActorMocked(msgs=[ff], arch=architecture.ARCH_X86_64))
    grub2mkconfigbios.process()
    assert mocked_run.commands == [['grub2-mkconfig', '-o', '/boot/grub2/grub.cfg']]
    assert reporting.create_report.called
    assert 'Failed to regenerate GRUB2 configuration' == reporting.create_report.reports[0]['title']
