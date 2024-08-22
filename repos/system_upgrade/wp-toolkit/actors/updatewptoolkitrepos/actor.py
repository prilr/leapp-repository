import os
import shutil

from leapp.actors import Actor
from leapp.libraries.stdlib import api, run
from leapp.models import ActiveVendorList, WpToolkit
from leapp.tags import IPUWorkflowTag, FirstBootPhaseTag

VENDOR_NAME = 'wp-toolkit'

VENDORS_DIR = '/etc/leapp/files/vendors.d'
REPO_DIR = '/etc/yum.repos.d'

class UpdateWpToolkitRepos(Actor):
    """
    Replaces the WP Toolkit's old repo file from the CentOS 7 version with one appropriate for the new OS.
    """

    name = 'update_wp_toolkit_repos'
    consumes = (ActiveVendorList, WpToolkit)
    produces = ()
    tags = (IPUWorkflowTag, FirstBootPhaseTag)

    def process(self):

        active_vendors = []
        for vendor_list in api.consume(ActiveVendorList):
            active_vendors.extend(vendor_list.data)

        if VENDOR_NAME in active_vendors:

            wptk_data = next(api.consume(WpToolkit), WpToolkit())

            src_file = api.get_file_path('{}-{}.el8.repo'. format(VENDOR_NAME, wptk_data.variant))
            dst_file = '{}/{}-{}.repo'.format(REPO_DIR, VENDOR_NAME, wptk_data.variant)

            try:
                os.rename(dst_file, dst_file + '.bak')
            except OSError as e:
                api.current_logger().warn('Could not rename {} to {}: {}'.format(e.filename, e.filename2, e.strerror))

            api.current_logger().info('Updating WPTK package repository file at {} using {}'.format(dst_file, src_file))

            try:
                shutil.copy(src_file, dst_file)
            except OSError as e:
                api.current_logger().error('Could not update WPTK package repository file {}: {}'.format(e.filename2, e.strerror))
        else:
            api.current_logger().info('{} not an active vendor: skipping actor'.format(VENDOR_NAME))
