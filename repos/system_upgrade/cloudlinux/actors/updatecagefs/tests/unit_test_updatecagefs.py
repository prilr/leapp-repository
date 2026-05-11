import subprocess
from unittest.mock import patch, call

from leapp.libraries.actor.updatecagefs import (
    schedule_cagefs_update,
    CAGEFS_UPDATE_SERVICE,
    CAGEFS_UPDATE_LOG,
    CAGEFSCTL,
)

_SERVICE_FILE = CAGEFS_UPDATE_SERVICE + '.service'


def test_schedule_writes_unit_and_enables_service(tmp_path):
    """Happy path: unit file written, daemon-reload and enable are called."""
    with patch('subprocess.check_call') as mock_check_call:
        error = schedule_cagefs_update(unit_dir=str(tmp_path))

    assert error is None

    unit_file = tmp_path / _SERVICE_FILE
    assert unit_file.exists()
    content = unit_file.read_text()
    assert '--force-update' in content
    assert 'After=cagefs.service' in content
    assert 'WantedBy=multi-user.target' in content
    assert CAGEFSCTL in content
    assert CAGEFS_UPDATE_LOG in content

    assert mock_check_call.call_args_list == [
        call(['systemctl', 'daemon-reload'], stdin=subprocess.DEVNULL),
        call(['systemctl', 'enable', _SERVICE_FILE], stdin=subprocess.DEVNULL),
    ]


def test_schedule_uses_custom_paths(tmp_path):
    """Custom cagefsctl and log_file paths appear in the written unit file."""
    with patch('subprocess.check_call'):
        schedule_cagefs_update(
            cagefsctl='/custom/cagefsctl',
            log_file='/custom/cagefs.log',
            unit_dir=str(tmp_path),
        )

    content = (tmp_path / _SERVICE_FILE).read_text()
    assert '/custom/cagefsctl' in content
    assert '/custom/cagefs.log' in content


def test_schedule_returns_error_when_unit_write_fails(tmp_path):
    """If writing the unit file fails, return an error without calling systemctl."""
    with patch('builtins.open', side_effect=OSError('Permission denied')):
        with patch('subprocess.check_call') as mock_check_call:
            error = schedule_cagefs_update(unit_dir=str(tmp_path))

    assert error is not None
    assert 'Permission denied' in error
    mock_check_call.assert_not_called()


def test_schedule_returns_error_when_daemon_reload_fails(tmp_path):
    """If daemon-reload fails, return an error and do not call enable."""
    def _fail_all(cmd, **kw):
        raise subprocess.CalledProcessError(1, cmd)

    with patch('subprocess.check_call', side_effect=_fail_all):
        error = schedule_cagefs_update(unit_dir=str(tmp_path))

    assert error is not None
    assert 'daemon-reload' in error


def test_schedule_returns_error_when_enable_fails(tmp_path):
    """If systemctl enable fails, return an error."""
    def _fail_enable(cmd, **kw):
        if 'enable' in cmd:
            raise subprocess.CalledProcessError(1, cmd)

    with patch('subprocess.check_call', side_effect=_fail_enable):
        error = schedule_cagefs_update(unit_dir=str(tmp_path))

    assert error is not None
    assert 'enable' in error


def test_unit_self_disables_on_success(tmp_path):
    """Unit file contains an ExecStartPost that disables the service after a
    successful run so it does not execute again on subsequent reboots."""
    with patch('subprocess.check_call'):
        schedule_cagefs_update(unit_dir=str(tmp_path))

    content = (tmp_path / _SERVICE_FILE).read_text()
    assert 'ExecStartPost' in content
    assert 'disable' in content


def test_unit_has_infinite_timeout(tmp_path):
    """Unit file sets TimeoutStartSec=infinity to allow multi-hour runs."""
    with patch('subprocess.check_call'):
        schedule_cagefs_update(unit_dir=str(tmp_path))

    content = (tmp_path / _SERVICE_FILE).read_text()
    assert 'TimeoutStartSec=infinity' in content
