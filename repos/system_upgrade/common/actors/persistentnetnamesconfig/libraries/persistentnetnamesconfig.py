import errno
import os
import re

from leapp.libraries.common.config import get_env
from leapp.libraries.stdlib import api
from leapp.models import (
    InitrdIncludes,
    PersistentNetNamesFacts,
    PersistentNetNamesFactsInitramfs,
    RenamedInterface,
    RenamedInterfaces,
    TargetInitramfsTasks
)
from leapp.utils.deprecation import suppress_deprecation

LINK_FILE_TEMPLATE = """# Generated by LEAPP
[Match]
MACAddress={}

[Link]
Name={}
"""


def generate_link_file(interface):
    try:
        os.makedirs('/etc/systemd/network')
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    link_file = '/etc/systemd/network/10-leapp-{}.link'.format(interface.name)
    with open(link_file, 'w') as f:
        f.write(LINK_FILE_TEMPLATE.format(interface.mac, interface.name))

    return link_file


@suppress_deprecation(InitrdIncludes)
def process():

    if get_env('LEAPP_NO_NETWORK_RENAMING', '0') == '1':
        api.current_logger().info(
            'Skipping handling of possibly renamed network interfaces: leapp executed with LEAPP_NO_NETWORK_RENAMING=1'
        )
        return

    rhel7_ifaces = next(api.consume(PersistentNetNamesFacts)).interfaces
    rhel8_ifaces = next(api.consume(PersistentNetNamesFactsInitramfs)).interfaces

    rhel7_ifaces_map = {iface.mac: iface for iface in rhel7_ifaces}
    rhel8_ifaces_map = {iface.mac: iface for iface in rhel8_ifaces}

    initrd_files = []
    missing_ifaces = []
    renamed_interfaces = []

    if rhel7_ifaces != rhel8_ifaces:
        for iface in rhel7_ifaces:
            rhel7_name = rhel7_ifaces_map[iface.mac].name
            try:
                rhel8_name = rhel8_ifaces_map[iface.mac].name
            except KeyError:
                missing_ifaces.append(iface)
                api.current_logger().warning(
                    'The device with MAC "{}" is not detected in the upgrade'
                    ' environment. Required driver: "{}".'
                    ' Original interface name: "{}".'
                    .format(iface.mac, iface.driver, iface.name)
                )
                continue

            if rhel7_name != rhel8_name and get_env('LEAPP_NO_NETWORK_RENAMING', '0') != '1':
                api.current_logger().warning('Detected interface rename {} -> {}.'.format(rhel7_name, rhel8_name))

                if re.search('eth[0-9]+', iface.name) is not None:
                    api.current_logger().warning('Interface named using eth prefix, refusing to generate link file')
                    renamed_interfaces.append(RenamedInterface(**{'rhel7_name': rhel7_name,
                                                                  'rhel8_name': rhel8_name}))
                    continue

                initrd_files.append(generate_link_file(iface))

    if missing_ifaces:
        msg = (
            'Some network devices have not been detected inside the'
            ' upgrade environment and so related network interfaces'
            ' could be renamed on the upgraded system.'
        )
        # Note(pstodulk):
        # This usually happens when required (RHEL 8 compatible)
        # drivers are not included in the upgrade initramfs.
        # We can add more information later. Currently we cannot provide
        # better instructions for users before (at least):
        # a) networking work in the upgrade initramfs (PR #583)
        # b) it's possible to influence the upgrade initramfs (PR #517)
        # TODO(pstodulk): gen report msg
        api.current_logger().warning(msg)

    api.produce(RenamedInterfaces(renamed=renamed_interfaces))
    api.produce(InitrdIncludes(files=initrd_files))
    # TODO: cover actor by tests in future. I am skipping writing of tests
    # now as some refactoring and bugfixing related to this actor
    # is planned already.
    api.produce(TargetInitramfsTasks(include_files=initrd_files))
