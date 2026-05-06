import subprocess
from unittest.mock import patch

from leapp.libraries.actor.updatecagefs import start_cagefs_update


class FakeProcess:
    def __init__(self, pid=12345):
        self.pid = pid


def test_start_returns_pid_on_success(tmp_path):
    """Popen succeeds -> (pid, None) returned, log file opened."""
    log_file = str(tmp_path / 'cagefs-update.log')
    cagefsctl = '/usr/sbin/cagefsctl'

    fake_proc = FakeProcess(pid=42)
    with patch('subprocess.Popen', return_value=fake_proc) as mock_popen:
        pid, error = start_cagefs_update(cagefsctl=cagefsctl, log_file=log_file)

    assert error is None
    assert pid == 42
    mock_popen.assert_called_once()
    args, kwargs = mock_popen.call_args
    assert args[0] == [cagefsctl, '--force-update']
    assert kwargs['stdin'] == subprocess.DEVNULL
    assert kwargs['start_new_session'] is True


def test_start_returns_error_when_popen_fails(tmp_path):
    """OSError from Popen -> (None, error_message) returned."""
    log_file = str(tmp_path / 'cagefs-update.log')

    with patch('subprocess.Popen', side_effect=OSError('no such file')):
        pid, error = start_cagefs_update(cagefsctl='/nonexistent/cagefsctl', log_file=log_file)

    assert pid is None
    assert 'no such file' in error


def test_start_uses_devnull_when_log_file_unwritable(tmp_path):
    """If log file cannot be opened (e.g. permission denied), stdout falls back to DEVNULL."""
    log_file = str(tmp_path / 'cagefs.log')

    fake_proc = FakeProcess(pid=99)
    with patch('builtins.open', side_effect=OSError('Permission denied')):
        with patch('subprocess.Popen', return_value=fake_proc) as mock_popen:
            pid, error = start_cagefs_update(cagefsctl='/usr/sbin/cagefsctl', log_file=log_file)

    assert error is None
    assert pid == 99
    _, kwargs = mock_popen.call_args
    assert kwargs['stdout'] == subprocess.DEVNULL


def test_start_closes_log_fd_before_returning(tmp_path):
    """Log file descriptor is closed by the parent after Popen returns."""
    log_file = str(tmp_path / 'cagefs-update.log')
    open_fds = []

    real_open = open

    def tracking_open(path, mode='r', **kw):
        fd = real_open(path, mode, **kw)
        open_fds.append(fd)
        return fd

    fake_proc = FakeProcess(pid=7)
    with patch('builtins.open', side_effect=tracking_open):
        with patch('subprocess.Popen', return_value=fake_proc):
            start_cagefs_update(cagefsctl='/usr/sbin/cagefsctl', log_file=log_file)

    assert all(fd.closed for fd in open_fds), 'parent must close log fd after Popen'
