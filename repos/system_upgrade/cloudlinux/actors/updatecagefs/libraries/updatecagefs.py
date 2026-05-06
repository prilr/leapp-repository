import subprocess


CAGEFSCTL = '/usr/sbin/cagefsctl'
CAGEFS_UPDATE_LOG = '/var/log/cagefs-update-post-elevate.log'


def start_cagefs_update(cagefsctl=CAGEFSCTL, log_file=CAGEFS_UPDATE_LOG):
    """Start cagefsctl --force-update asynchronously.

    Returns (pid, None) on success or (None, error_message) on failure.
    The process runs in a new session so it survives the leapp first-boot
    service exiting.
    """
    log_fd = None
    try:
        log_fd = open(log_file, 'w')
    except OSError:
        pass

    try:
        proc = subprocess.Popen(
            [cagefsctl, '--force-update'],
            stdout=log_fd if log_fd is not None else subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as e:
        return None, str(e)
    finally:
        if log_fd is not None:
            log_fd.close()

    return proc.pid, None
