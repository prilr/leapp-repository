import os
import subprocess

CAGEFSCTL = '/usr/sbin/cagefsctl'
CAGEFS_UPDATE_LOG = '/var/log/cagefs-update-post-elevate.log'
CAGEFS_UPDATE_SERVICE = 'cagefs-force-update-post-elevate'
SYSTEMD_UNIT_DIR = '/etc/systemd/system'

# %n is expanded by systemd to the full unit name at runtime.
_UNIT_TEMPLATE = (
    '[Unit]\n'
    'Description=CageFS force-update after Elevate upgrade\n'
    'After=cagefs.service\n'
    '\n'
    '[Service]\n'
    'Type=oneshot\n'
    "ExecStart=/bin/sh -c '{cagefsctl} --force-update >> {log} 2>&1'\n"
    'ExecStartPost=-/usr/bin/systemctl disable %n\n'
    'TimeoutStartSec=infinity\n'
    '\n'
    '[Install]\n'
    'WantedBy=multi-user.target\n'
)


def schedule_cagefs_update(cagefsctl=CAGEFSCTL, log_file=CAGEFS_UPDATE_LOG,
                           unit_dir=SYSTEMD_UNIT_DIR):
    """Write and enable a one-shot systemd service that runs
    'cagefsctl --force-update' after cagefs.service has started.

    Running after cagefs.service ensures --mount-skel finishes before
    --force-update begins, so the skeleton is consistent during early boot.
    The service self-disables after a successful run.  If --force-update
    fails the unit stays enabled and retries on the next reboot.

    Returns None on success or an error message string on failure.
    """
    unit_path = os.path.join(unit_dir, CAGEFS_UPDATE_SERVICE + '.service')
    unit_content = _UNIT_TEMPLATE.format(cagefsctl=cagefsctl, log=log_file)

    try:
        with open(unit_path, 'w') as fh:
            fh.write(unit_content)
    except OSError as e:
        return 'Failed to write unit file: {0}'.format(e)

    for cmd in (
        ['systemctl', 'daemon-reload'],
        ['systemctl', 'enable', CAGEFS_UPDATE_SERVICE + '.service'],
    ):
        try:
            subprocess.check_call(cmd, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.CalledProcessError) as e:
            return '{0} failed: {1}'.format(' '.join(cmd), e)

    return None
