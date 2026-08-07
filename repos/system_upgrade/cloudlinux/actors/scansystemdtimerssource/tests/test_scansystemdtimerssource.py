import pytest

from leapp.libraries.actor import scansystemdtimerssource
from leapp.libraries.stdlib import CalledProcessError


class _RunMocked(object):
    """
    Fake leapp `run` answering `systemctl list-unit-files --type=timer ...`.
    """

    def __init__(self, stdout=None, raises=False):
        self.stdout = stdout or []
        self.raises = raises
        self.commands = []

    def __call__(self, cmd, split=False):
        self.commands.append(cmd)
        if self.raises:
            raise CalledProcessError('boom', cmd, {})
        return {'stdout': self.stdout}


def test_timer_names_are_parsed(monkeypatch):
    run_mock = _RunMocked(stdout=[
        'logrotate.timer                enabled  enabled',
        'dnf-makecache.timer            enabled  enabled',
        'mdadm-last-resort@.timer       disabled disabled',
    ])
    monkeypatch.setattr(scansystemdtimerssource, 'run', run_mock)

    assert scansystemdtimerssource.get_source_timers() == [
        'logrotate.timer', 'dnf-makecache.timer', 'mdadm-last-resort@.timer'
    ]
    assert run_mock.commands[0][:3] == ['systemctl', 'list-unit-files', '--type=timer']


def test_two_column_output_is_parsed(monkeypatch):
    """
    systemd 239 (EL8) prints no PRESET column; only the name is needed here.
    """
    run_mock = _RunMocked(stdout=['logrotate.timer  enabled'])
    monkeypatch.setattr(scansystemdtimerssource, 'run', run_mock)

    assert scansystemdtimerssource.get_source_timers() == ['logrotate.timer']


def test_blank_lines_are_ignored(monkeypatch):
    run_mock = _RunMocked(stdout=['logrotate.timer enabled', '', '   '])
    monkeypatch.setattr(scansystemdtimerssource, 'run', run_mock)

    assert scansystemdtimerssource.get_source_timers() == ['logrotate.timer']


def test_no_timers_gives_empty_list(monkeypatch):
    monkeypatch.setattr(scansystemdtimerssource, 'run', _RunMocked(stdout=[]))

    assert scansystemdtimerssource.get_source_timers() == []


def test_systemctl_failure_propagates(monkeypatch):
    monkeypatch.setattr(scansystemdtimerssource, 'run', _RunMocked(raises=True))

    with pytest.raises(CalledProcessError):
        scansystemdtimerssource.get_source_timers()
