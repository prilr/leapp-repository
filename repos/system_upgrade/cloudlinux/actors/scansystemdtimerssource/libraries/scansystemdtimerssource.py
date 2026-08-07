from leapp.libraries.stdlib import run

_LIST_TIMERS_CMD = ['systemctl', 'list-unit-files', '--type=timer', '--all', '--plain', '--no-legend']


def get_source_timers():
    """
    Get the names of all systemd timer unit files on the source system.

    Only the unit names are read: systemd 239 (EL8) prints just the name and the
    state, while newer versions add a PRESET column, and the preset of the
    source system is irrelevant for this purpose anyway.

    :return: Names of the timer unit files, including the '.timer' suffix
    :rtype: list[str]
    :raises: CalledProcessError: if the `systemctl` command fails
    """
    timers = []
    for entry in run(_LIST_TIMERS_CMD, split=True)['stdout']:
        columns = entry.split()
        if columns:
            timers.append(columns[0])
    return timers
