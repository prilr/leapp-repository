import pytest

from leapp import reporting
from leapp.libraries.actor import enablemigratedtimers
from leapp.libraries.common.testutils import create_report_mocked, CurrentActorMocked, logger_mocked
from leapp.libraries.stdlib import api, CalledProcessError
from leapp.models import SystemdTimersInfoSource


class _RunMocked(object):
    """
    Fake leapp `run` that answers `systemctl list-unit-files --type=timer` with
    the configured target timer states and records every command issued.
    `enable --now` can be made to fail.
    """

    def __init__(self, target_states=None, enable_raises=False):
        self.target_states = target_states or {}
        self.enable_raises = enable_raises
        self.commands = []

    def __call__(self, cmd, split=False, checked=True):
        self.commands.append(cmd)
        if cmd[:3] == ['systemctl', 'list-unit-files', '--type=timer']:
            return {'stdout': ['{} {}'.format(n, s) for n, s in sorted(self.target_states.items())]}
        if cmd[:3] == ['systemctl', 'enable', '--now']:
            if self.enable_raises:
                raise CalledProcessError('boom', cmd, {})
            return {'stdout': []}
        return {'stdout': []}


def _setup(monkeypatch, run_mock, presets, source_timers=None, no_source_msg=False):
    msgs = [] if no_source_msg else [SystemdTimersInfoSource(timers=source_timers or [])]
    monkeypatch.setattr(api, 'current_actor', CurrentActorMocked(msgs=msgs))
    monkeypatch.setattr(api, 'current_logger', logger_mocked())
    monkeypatch.setattr(enablemigratedtimers, 'run', run_mock)
    monkeypatch.setattr(
        enablemigratedtimers.systemd, 'get_system_unit_presets', lambda suffix: presets
    )
    reports = create_report_mocked()
    monkeypatch.setattr(reporting, 'create_report', reports)
    return reports


def _enabled_units(run_mock):
    return [c[3] for c in run_mock.commands if c[:3] == ['systemctl', 'enable', '--now']]


def _reported_units(reports):
    """
    Pull the listed units out of the report summary.

    The summary prose names logrotate.timer and raid-check.timer as examples, so
    a plain substring check would pass regardless of what was actually enabled.
    Only the bulleted list reflects the units this run touched.
    """
    summary = reports.report_fields['summary']
    return [
        line.strip() for line in summary.split(enablemigratedtimers.FMT_LIST_SEPARATOR)[1:]
    ]


def test_new_preset_enabled_timer_is_enabled_and_reported(monkeypatch):
    run_mock = _RunMocked(target_states={'logrotate.timer': 'disabled'})
    reports = _setup(monkeypatch, run_mock, presets={'logrotate.timer': 'enable'}, source_timers=[])

    enablemigratedtimers.process()

    assert _enabled_units(run_mock) == ['logrotate.timer']
    assert reports.called == 1
    assert _reported_units(reports) == ['logrotate.timer']


def test_raid_check_timer_is_enabled_alongside_logrotate(monkeypatch):
    """
    mdadm migrates /etc/cron.d/raid-check to raid-check.timer on EL8->EL9 exactly
    like logrotate does, so the weekly RAID consistency scrub silently stops. Both
    must be re-enabled by a single run.
    """
    run_mock = _RunMocked(target_states={
        'logrotate.timer': 'disabled',
        'raid-check.timer': 'disabled',
    })
    reports = _setup(
        monkeypatch,
        run_mock,
        presets={'logrotate.timer': 'enable', 'raid-check.timer': 'enable'},
        source_timers=['dnf-makecache.timer'],
    )

    enablemigratedtimers.process()

    assert sorted(_enabled_units(run_mock)) == ['logrotate.timer', 'raid-check.timer']
    assert reports.called == 1
    assert _reported_units(reports) == ['logrotate.timer', 'raid-check.timer']


def test_timer_present_on_source_is_left_alone(monkeypatch):
    """
    A timer that existed on the source system may have been disabled deliberately
    by the administrator, so its state must never be overridden.
    """
    run_mock = _RunMocked(target_states={'dnf-makecache.timer': 'disabled'})
    reports = _setup(
        monkeypatch,
        run_mock,
        presets={'dnf-makecache.timer': 'enable'},
        source_timers=['dnf-makecache.timer'],
    )

    enablemigratedtimers.process()

    assert _enabled_units(run_mock) == []
    assert reports.called == 0


@pytest.mark.parametrize('preset', ['disable', None])
def test_new_timer_without_enable_preset_is_left_alone(monkeypatch, preset):
    run_mock = _RunMocked(target_states={'rear.timer': 'disabled'})
    presets = {} if preset is None else {'rear.timer': preset}
    reports = _setup(monkeypatch, run_mock, presets=presets, source_timers=[])

    enablemigratedtimers.process()

    assert _enabled_units(run_mock) == []
    assert reports.called == 0


@pytest.mark.parametrize('state', ['enabled', 'static', 'masked', 'generated'])
def test_new_timer_not_in_disabled_state_is_left_alone(monkeypatch, state):
    run_mock = _RunMocked(target_states={'logrotate.timer': state})
    reports = _setup(monkeypatch, run_mock, presets={'logrotate.timer': 'enable'}, source_timers=[])

    enablemigratedtimers.process()

    assert _enabled_units(run_mock) == []
    assert reports.called == 0


def test_missing_source_message_is_a_no_op(monkeypatch):
    """
    Without the source inventory there is no way to tell a new timer from one the
    administrator disabled, so nothing may be touched.
    """
    run_mock = _RunMocked(target_states={'logrotate.timer': 'disabled'})
    reports = _setup(
        monkeypatch, run_mock, presets={'logrotate.timer': 'enable'}, no_source_msg=True
    )

    enablemigratedtimers.process()

    assert _enabled_units(run_mock) == []
    assert reports.called == 0
    assert api.current_logger().warnmsg


def test_enable_failure_is_swallowed_and_not_reported(monkeypatch):
    run_mock = _RunMocked(target_states={'logrotate.timer': 'disabled'}, enable_raises=True)
    reports = _setup(monkeypatch, run_mock, presets={'logrotate.timer': 'enable'}, source_timers=[])

    enablemigratedtimers.process()

    assert _enabled_units(run_mock) == ['logrotate.timer']
    # enabling failed, so nothing should be reported as enabled
    assert reports.called == 0


def test_one_failure_does_not_block_the_other_timer(monkeypatch):
    class _PartialFailRun(_RunMocked):
        def __call__(self, cmd, split=False, checked=True):
            if cmd[:3] == ['systemctl', 'enable', '--now'] and cmd[3] == 'logrotate.timer':
                self.commands.append(cmd)
                raise CalledProcessError('boom', cmd, {})
            return super(_PartialFailRun, self).__call__(cmd, split=split, checked=checked)

    run_mock = _PartialFailRun(target_states={
        'logrotate.timer': 'disabled',
        'raid-check.timer': 'disabled',
    })
    reports = _setup(
        monkeypatch,
        run_mock,
        presets={'logrotate.timer': 'enable', 'raid-check.timer': 'enable'},
        source_timers=[],
    )

    enablemigratedtimers.process()

    assert reports.called == 1
    assert _reported_units(reports) == ['raid-check.timer']


def test_no_timers_on_target_is_a_no_op(monkeypatch):
    run_mock = _RunMocked(target_states={})
    reports = _setup(monkeypatch, run_mock, presets={}, source_timers=[])

    enablemigratedtimers.process()

    assert _enabled_units(run_mock) == []
    assert reports.called == 0
