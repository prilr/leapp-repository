import pytest

from leapp.libraries.actor import setdefaultbootkernelforclrelease as lib
from leapp.libraries.common.testutils import logger_mocked
from leapp.libraries.stdlib import CalledProcessError, api


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_run(responses):
    """Return a fake run() that maps command fragments to stdout."""

    def _run(cmd, **kwargs):
        cmd_str = ' '.join(cmd)
        for key, value in responses.items():
            if key in cmd_str:
                if isinstance(value, Exception):
                    raise value
                return value
        return {'stdout': ''}

    return _run


def _cpe(cmd=None, exit_code=1, stderr=''):
    return CalledProcessError(exit_code, cmd or ['rpm'], stderr)


# ---------------------------------------------------------------------------
# get_cl_release_minor
# ---------------------------------------------------------------------------

def test_get_cl_release_minor_normal(monkeypatch):
    monkeypatch.setattr(lib, 'run', _make_run({'cloudlinux-release': {'stdout': '9.6'}}))
    assert lib.get_cl_release_minor() == 6


def test_get_cl_release_minor_no_minor(monkeypatch):
    monkeypatch.setattr(lib, 'run', _make_run({'cloudlinux-release': {'stdout': '9'}}))
    assert lib.get_cl_release_minor() is None


def test_get_cl_release_minor_rpm_error(monkeypatch):
    monkeypatch.setattr(lib, 'run', _make_run({'cloudlinux-release': _cpe()}))
    assert lib.get_cl_release_minor() is None


# ---------------------------------------------------------------------------
# get_installed_target_kernels
# ---------------------------------------------------------------------------

def test_get_installed_target_kernels_returns_matching(monkeypatch):
    nevras = [
        'kernel-core-5.14.0-362.18.1.el9_3.x86_64',
        'kernel-core-5.14.0-503.35.1.el9_6.x86_64',
        'kernel-core-5.14.0-611.5.1.el9_7.x86_64',
    ]
    monkeypatch.setattr(lib, 'run', _make_run({'kernel-core': {'stdout': nevras}}))
    result = lib.get_installed_target_kernels('9')
    assert result == nevras


def test_get_installed_target_kernels_filters_by_major(monkeypatch):
    nevras = [
        'kernel-core-5.14.0-503.35.1.el9_6.x86_64',
        'kernel-core-4.18.0-553.el8_10.x86_64',
    ]
    monkeypatch.setattr(lib, 'run', _make_run({'kernel-core': {'stdout': nevras}}))
    result = lib.get_installed_target_kernels('9')
    assert 'el8' not in ' '.join(result)
    assert len(result) == 1


def test_get_installed_target_kernels_rpm_error(monkeypatch):
    monkeypatch.setattr(lib, 'run', _make_run({'kernel-core': _cpe()}))
    assert lib.get_installed_target_kernels('9') == []


# ---------------------------------------------------------------------------
# extract_kernel_minor
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('s,expected', [
    ('kernel-core-5.14.0-503.35.1.el9_6.x86_64', 6),
    ('kernel-core-5.14.0-611.5.1.el9_7.x86_64', 7),
    ('/boot/vmlinuz-5.14.0-503.35.1.el9_6.x86_64', 6),
    ('kernel-core-5.14.0-362.el9.x86_64', None),   # no underscore minor
    ('completely-unrelated-string', None),
])
def test_extract_kernel_minor(s, expected):
    assert lib.extract_kernel_minor(s) == expected


# ---------------------------------------------------------------------------
# get_vmlinuz_path
# ---------------------------------------------------------------------------

def test_get_vmlinuz_path_found(monkeypatch):
    files = [
        '/boot/vmlinuz-5.14.0-503.35.1.el9_6.x86_64',
        '/boot/initramfs-5.14.0-503.35.1.el9_6.x86_64.img',
        '/usr/lib/modules/5.14.0-503.35.1.el9_6.x86_64/vmlinuz',
    ]
    monkeypatch.setattr(lib, 'run', _make_run({'rpm -q -l': {'stdout': files}}))
    result = lib.get_vmlinuz_path('kernel-core-5.14.0-503.35.1.el9_6.x86_64')
    assert result == '/boot/vmlinuz-5.14.0-503.35.1.el9_6.x86_64'


def test_get_vmlinuz_path_not_found(monkeypatch):
    monkeypatch.setattr(lib, 'run', _make_run({'rpm -q -l': {'stdout': ['/boot/initramfs-X.img']}}))
    assert lib.get_vmlinuz_path('kernel-core-X') is None


def test_get_vmlinuz_path_rpm_error(monkeypatch):
    monkeypatch.setattr(lib, 'run', _make_run({'rpm -q -l': _cpe()}))
    assert lib.get_vmlinuz_path('kernel-core-X') is None


# ---------------------------------------------------------------------------
# process() - integration-level unit tests
# ---------------------------------------------------------------------------

EL9_6_NEVRA = 'kernel-core-5.14.0-503.35.1.el9_6.x86_64'
EL9_7_NEVRA = 'kernel-core-5.14.0-611.5.1.el9_7.x86_64'
EL9_6_VMLINUZ = '/boot/vmlinuz-5.14.0-503.35.1.el9_6.x86_64'
EL9_7_VMLINUZ = '/boot/vmlinuz-5.14.0-611.5.1.el9_7.x86_64'


def _run_responses_full(default_kernel=EL9_7_VMLINUZ, cl_minor=6,
                        kernels=None, vmlinuz=EL9_6_VMLINUZ):
    if kernels is None:
        kernels = [EL9_6_NEVRA, EL9_7_NEVRA]

    def _run(cmd, **kwargs):
        cmd_str = ' '.join(cmd)
        if '--queryformat' in cmd_str and 'cloudlinux-release' in cmd_str:
            return {'stdout': '9.{}'.format(cl_minor)}
        if '--default-kernel' in cmd_str:
            return {'stdout': default_kernel}
        if 'kernel-core' in cmd_str and '-l' not in cmd_str:
            return {'stdout': kernels}
        if '-q' in cmd_str and '-l' in cmd_str:
            # Return files for whichever nevra was requested
            for nevra in kernels:
                if nevra in cmd_str:
                    minor = lib.extract_kernel_minor(nevra)
                    return {'stdout': ['/boot/vmlinuz-5.14.0-X.el9_{}.x86_64'.format(minor),
                                       '/boot/initramfs-X.img']}
            return {'stdout': []}
        if '--set-default' in cmd_str:
            return {'stdout': ''}
        return {'stdout': ''}

    return _run


def test_process_corrects_when_default_minor_mismatch(monkeypatch):
    """When default is el9_7 but cloudlinux-release is 9.6, correct to el9_6."""
    set_default_calls = []

    def fake_set_default(path):
        set_default_calls.append(path)

    monkeypatch.setattr(api, 'current_logger', logger_mocked)
    monkeypatch.setattr(lib, 'run', _run_responses_full(default_kernel=EL9_7_VMLINUZ, cl_minor=6))
    monkeypatch.setattr(lib, 'set_default_kernel', fake_set_default)

    lib.process(target_major='9')

    assert len(set_default_calls) == 1
    assert 'el9_6' in set_default_calls[0]


def test_process_no_correction_when_minor_matches(monkeypatch):
    """When default is already el9_6 and cloudlinux-release is 9.6, do nothing."""
    set_default_calls = []

    monkeypatch.setattr(api, 'current_logger', logger_mocked)
    monkeypatch.setattr(lib, 'run', _run_responses_full(default_kernel=EL9_6_VMLINUZ, cl_minor=6))
    monkeypatch.setattr(lib, 'set_default_kernel', lambda p: set_default_calls.append(p))

    lib.process(target_major='9')

    assert set_default_calls == []


def test_process_skips_when_cl_release_unavailable(monkeypatch):
    """When cloudlinux-release query fails, process() returns early without calling grubby."""
    set_default_calls = []

    def fake_run(cmd, **kwargs):
        if 'cloudlinux-release' in ' '.join(cmd):
            raise _cpe()
        return {'stdout': EL9_7_VMLINUZ}

    monkeypatch.setattr(api, 'current_logger', logger_mocked)
    monkeypatch.setattr(lib, 'run', fake_run)
    monkeypatch.setattr(lib, 'set_default_kernel', lambda p: set_default_calls.append(p))

    lib.process(target_major='9')

    assert set_default_calls == []


def test_process_skips_when_grubby_fails(monkeypatch):
    """When grubby --default-kernel fails, process() returns early."""
    set_default_calls = []

    def fake_run(cmd, **kwargs):
        cmd_str = ' '.join(cmd)
        if 'cloudlinux-release' in cmd_str:
            return {'stdout': '9.6'}
        if '--default-kernel' in cmd_str:
            raise _cpe(cmd=cmd)
        return {'stdout': ''}

    monkeypatch.setattr(api, 'current_logger', logger_mocked)
    monkeypatch.setattr(lib, 'run', fake_run)
    monkeypatch.setattr(lib, 'set_default_kernel', lambda p: set_default_calls.append(p))

    lib.process(target_major='9')

    assert set_default_calls == []


def test_process_skips_when_no_matching_kernel_found(monkeypatch):
    """When no el9_6 kernel is installed but cloudlinux-release is 9.6, warn and skip."""
    set_default_calls = []

    def fake_run(cmd, **kwargs):
        cmd_str = ' '.join(cmd)
        if 'cloudlinux-release' in cmd_str:
            return {'stdout': '9.6'}
        if '--default-kernel' in cmd_str:
            return {'stdout': EL9_7_VMLINUZ}
        if 'kernel-core' in cmd_str:
            return {'stdout': [EL9_7_NEVRA]}  # only el9_7, no el9_6
        return {'stdout': ''}

    monkeypatch.setattr(api, 'current_logger', logger_mocked)
    monkeypatch.setattr(lib, 'run', fake_run)
    monkeypatch.setattr(lib, 'set_default_kernel', lambda p: set_default_calls.append(p))

    lib.process(target_major='9')

    assert set_default_calls == []


def test_process_skips_default_without_minor_pattern(monkeypatch):
    """When current default kernel has no el<major>_<minor> pattern, skip silently."""
    set_default_calls = []

    def fake_run(cmd, **kwargs):
        cmd_str = ' '.join(cmd)
        if 'cloudlinux-release' in cmd_str:
            return {'stdout': '9.6'}
        if '--default-kernel' in cmd_str:
            return {'stdout': '/boot/vmlinuz-5.14.0-362.el9.x86_64'}
        return {'stdout': ''}

    monkeypatch.setattr(api, 'current_logger', logger_mocked)
    monkeypatch.setattr(lib, 'run', fake_run)
    monkeypatch.setattr(lib, 'set_default_kernel', lambda p: set_default_calls.append(p))

    lib.process(target_major='9')

    assert set_default_calls == []
