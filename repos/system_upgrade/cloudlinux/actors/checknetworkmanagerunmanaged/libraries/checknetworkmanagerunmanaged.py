import os
import re

from leapp import reporting
from leapp.libraries.common.config.version import get_target_major_version
from leapp.libraries.stdlib import api

NM_CONFD_DIR = '/etc/NetworkManager/conf.d'

# Matches a NetworkManager keyfile entry that marks *every* device as unmanaged.
# Targeted forms (``unmanaged-devices=mac:...``, ``=interface-name:eth1``) are
# deliberately not matched: they exclude named devices, and deciding whether the
# excluded one carries the host's connectivity is not something this check can
# do reliably. The wildcard is unambiguous.
UNMANAGED_WILDCARD_RE = re.compile(r'^\s*unmanaged-devices\s*=\s*\*\s*$')

FMT_LIST_SEPARATOR = '\n    - '


def _has_wildcard_override(path):
    """
    Return True if any non-comment line in ``path`` sets unmanaged-devices to
    the wildcard. Comments start with '#' (NetworkManager keyfile syntax).
    """
    try:
        with open(path, 'r') as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith('#'):
                    continue
                if UNMANAGED_WILDCARD_RE.match(line):
                    return True
    except (IOError, OSError) as exc:
        api.current_logger().info(
            'Could not read NetworkManager configuration {0}: {1}'.format(path, exc)
        )
    return False


def find_unmanaged_overrides():
    if not os.path.isdir(NM_CONFD_DIR):
        return []
    found = []
    for name in sorted(os.listdir(NM_CONFD_DIR)):
        if not name.endswith('.conf'):
            continue
        path = os.path.join(NM_CONFD_DIR, name)
        if os.path.isfile(path) and _has_wildcard_override(path):
            found.append(path)
    return found


def process():
    # Only a problem when the target no longer ships network-scripts. On
    # CloudLinux 8 the legacy network.service is still there to bring the
    # interfaces up instead, so the same configuration is survivable and
    # inhibiting a 7->8 upgrade over it would be a false positive.
    if int(get_target_major_version()) < 9:
        return

    overrides = find_unmanaged_overrides()
    if not overrides:
        return

    api.current_logger().info(
        'NetworkManager unmanaged-devices=* override(s) found: {0}'.format(
            ', '.join(overrides)
        )
    )

    reporting.create_report([
        reporting.Title(
            'NetworkManager is configured not to manage any device'
        ),
        reporting.Summary(
            'CloudLinux {target} does not ship the network-scripts package, so '
            'NetworkManager is the only thing that can bring network interfaces '
            'up. The configuration below tells it to leave every device '
            'unmanaged. Upgrading with it in place would leave this system with '
            'no network connectivity after the reboot, reachable only from the '
            'console.\n\n'
            'On OpenNebula guests this file is typically written at boot by '
            'one-context (loc-10-network.d/functions), not shipped by any '
            'package, so it is not removed when one-context is. Files with the '
            'problematic configuration:{files}'.format(
                target=get_target_major_version(),
                files=''.join(
                    '{0}{1}'.format(FMT_LIST_SEPARATOR, path) for path in overrides
                ),
            )
        ),
        reporting.Remediation(
            hint=(
                'Remove the listed file(s), or drop the "unmanaged-devices=*" '
                'entry from them, so NetworkManager manages the interfaces after '
                'the upgrade. If specific devices must stay unmanaged, replace '
                'the wildcard with the explicit device list documented in '
                'NetworkManager.conf(5).'
            )
        ),
        reporting.Severity(reporting.Severity.HIGH),
        reporting.Groups([reporting.Groups.NETWORK, reporting.Groups.SERVICES]),
        reporting.Groups([reporting.Groups.INHIBITOR]),
        reporting.RelatedResource('package', 'NetworkManager'),
    ] + [
        reporting.RelatedResource('file', path) for path in overrides
    ])
