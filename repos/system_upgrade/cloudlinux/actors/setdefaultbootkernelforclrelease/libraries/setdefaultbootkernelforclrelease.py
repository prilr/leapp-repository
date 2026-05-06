import os
import re

from leapp.libraries.stdlib import CalledProcessError, api, run


def get_cl_release_minor():
    """Return the minor version integer of cloudlinux-release, or None on error."""
    try:
        result = run(['rpm', '-q', '--queryformat', '%{VERSION}', 'cloudlinux-release'])
        version = result['stdout'].strip()
        parts = version.split('.')
        if len(parts) >= 2:
            return int(parts[1])
    except (CalledProcessError, ValueError, IndexError):
        pass
    return None


def get_installed_target_kernels(target_major):
    """Return list of kernel-core NEVRAs matching target_major."""
    pattern = re.compile(r'\.el{}[._]'.format(re.escape(str(target_major))))
    try:
        result = run(['rpm', '-q', 'kernel-core'], split=True)
        return [n for n in result['stdout'] if pattern.search(n)]
    except CalledProcessError:
        return []


def extract_kernel_minor(nevra_or_path):
    """Extract the el<major>_<minor> minor integer from a NEVRA string or path, or None."""
    match = re.search(r'el\d+_(\d+)', nevra_or_path)
    if match:
        return int(match.group(1))
    return None


def get_vmlinuz_path(nevra):
    """Return the /boot/vmlinuz-* path for the given kernel NEVRA, or None."""
    try:
        result = run(['rpm', '-q', '-l', nevra], split=True)
        for path in result['stdout']:
            if os.path.dirname(path) == '/boot' and os.path.basename(path).startswith('vmlinuz'):
                return path
    except CalledProcessError:
        pass
    return None


def get_current_default_kernel():
    """Return the current grubby default kernel path, or None on error."""
    try:
        result = run(['grubby', '--default-kernel'])
        return result['stdout'].strip()
    except (CalledProcessError, OSError):
        return None


def set_default_kernel(vmlinuz_path):
    """Set the grubby default kernel; raises CalledProcessError or OSError on failure."""
    run(['grubby', '--set-default', vmlinuz_path])


def process(target_major='9'):
    cl_minor = get_cl_release_minor()
    if cl_minor is None:
        api.current_logger().warning(
            'Cannot determine cloudlinux-release minor version; skipping kernel default correction'
        )
        return

    current_default = get_current_default_kernel()
    if not current_default:
        api.current_logger().warning(
            'Cannot determine current grub default kernel; skipping kernel default correction'
        )
        return

    default_minor = extract_kernel_minor(current_default)
    if default_minor is None:
        api.current_logger().debug(
            'No el<major>_<minor> pattern in default kernel path %s; skipping', current_default
        )
        return

    if default_minor == cl_minor:
        api.current_logger().debug(
            'Default boot kernel minor (%s) already matches cloudlinux-release minor (%s); no correction needed',
            default_minor, cl_minor
        )
        return

    api.current_logger().warning(
        'Default boot kernel minor (el%s_%s) does not match cloudlinux-release minor (%s). '
        'Attempting to correct the default boot entry.',
        target_major, default_minor, cl_minor
    )

    kernels = get_installed_target_kernels(target_major)
    matching_nevra = None
    for nevra in kernels:
        if extract_kernel_minor(nevra) == cl_minor:
            matching_nevra = nevra
            break

    if not matching_nevra:
        api.current_logger().warning(
            'No el%s_%s kernel-core found; cannot correct default boot entry',
            target_major, cl_minor
        )
        return

    vmlinuz = get_vmlinuz_path(matching_nevra)
    if not vmlinuz:
        api.current_logger().warning(
            'Cannot find vmlinuz path for %s; skipping kernel default correction', matching_nevra
        )
        return

    try:
        set_default_kernel(vmlinuz)
        api.current_logger().info(
            'Set grub default to %s (el%s_%s) to match cloudlinux-release %s.%s',
            vmlinuz, target_major, cl_minor, target_major, cl_minor
        )
    except (CalledProcessError, OSError):
        api.current_logger().error(
            'Failed to set grub default to %s', vmlinuz, exc_info=True
        )
