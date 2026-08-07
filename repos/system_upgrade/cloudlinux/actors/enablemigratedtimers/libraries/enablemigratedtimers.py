from leapp import reporting
from leapp.libraries.common import systemd
from leapp.libraries.stdlib import api, CalledProcessError, run
from leapp.models import SystemdTimersInfoSource

FMT_LIST_SEPARATOR = '\n    - '

_LIST_TIMERS_CMD = ['systemctl', 'list-unit-files', '--type=timer', '--all', '--plain', '--no-legend']


def _get_target_timer_states():
    """
    Get the state of every systemd timer unit file on the upgraded system.

    :return: Dictionary mapping timer unit names to their state
    :rtype: dict[str, str]
    """
    states = {}
    for entry in run(_LIST_TIMERS_CMD, split=True)['stdout']:
        columns = entry.split()
        if len(columns) >= 2:
            states[columns[0]] = columns[1]
    return states


def _timers_to_enable(source_timers, target_states, presets):
    """
    Pick the timers that the upgrade left disabled against their vendor preset.

    A timer qualifies only when it does not exist on the source system. Such a
    timer was never visible to the administrator, so a 'disabled' state cannot
    express an explicit choice - it can only be the upgrade failing to apply the
    vendor preset. Timers that existed on the source keep whatever state the
    regular systemd state transition gave them.

    :return: Sorted names of the timers to enable
    :rtype: list[str]
    """
    return sorted(
        name for name, state in target_states.items()
        if name not in source_timers and state == 'disabled' and presets.get(name) == 'enable'
    )


def process():
    source_info = next(api.consume(SystemdTimersInfoSource), None)
    if source_info is None:
        # Without the source inventory a new timer cannot be told apart from one
        # the administrator disabled on purpose, so nothing may be touched.
        api.current_logger().warning(
            'No SystemdTimersInfoSource message found, skipping the systemd timer check.'
        )
        return

    source_timers = set(source_info.timers)
    target_states = _get_target_timer_states()
    presets = systemd.get_system_unit_presets('.timer')

    enabled = []
    for unit in _timers_to_enable(source_timers, target_states, presets):
        try:
            run(['systemctl', 'enable', '--now', unit])
        except CalledProcessError as err:
            api.current_logger().warning(
                'Failed to enable systemd timer {}: {}'.format(unit, err)
            )
            continue
        enabled.append(unit)

    if not enabled:
        return

    reporting.create_report([
        reporting.Title('Enabled systemd timers left disabled by the upgrade'),
        reporting.Summary(
            'The following systemd timers are new on the upgraded system and are'
            ' enabled by vendor preset, but were left disabled by the upgrade:'
            ' the owning package already existed on the source system, so its'
            ' scriptlet did not apply the preset, and leapp does not transition'
            ' non-service units. Leapp has enabled and started them to restore'
            ' the behavior of a freshly installed system (e.g. logrotate.timer'
            ' rotates system logs and raid-check.timer runs the weekly software'
            ' RAID consistency check; left disabled they fail silently):{}{}'.format(
                FMT_LIST_SEPARATOR, FMT_LIST_SEPARATOR.join(enabled)
            )
        ),
        reporting.Severity(reporting.Severity.INFO),
        reporting.Groups([reporting.Groups.POST, reporting.Groups.SERVICES]),
    ])
