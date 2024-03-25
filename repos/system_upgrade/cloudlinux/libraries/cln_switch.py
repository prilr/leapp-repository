from leapp.libraries.stdlib import api
from leapp.libraries.stdlib import run

SWITCH_BIN = "/usr/sbin/cln-switch-channel"

def cln_switch(target):
    switch_cmd = [SWITCH_BIN, "-t", str(target), "-o", "-f"]
    yum_clean_cmd = ["yum", "clean", "all"]
    res = run(switch_cmd)
    api.current_logger().debug('Channel switch result: %s', res)
    res = run(yum_clean_cmd)  # required to update the repolist
    api.current_logger().debug('yum cleanup result: %s', res)
