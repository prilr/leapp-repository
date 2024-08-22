from leapp.actors import Actor
from leapp.libraries.stdlib import api
from leapp.models import ActiveVendorList, WpToolkit, VendorSourceRepos, InstalledRPM
from leapp.tags import IPUWorkflowTag, FactsPhaseTag
from leapp.libraries.common.rpms import package_data_for

VENDOR_NAME = 'wp-toolkit'
SUPPORTED_VARIANTS = ['cpanel', ]


class WpToolkitFacts(Actor):
    """
    Find out whether a supported WP Toolkit repository is present and whether the appropriate package is installed.
    """

    name = 'wp_toolkit_facts'
    consumes = (ActiveVendorList, VendorSourceRepos, InstalledRPM)
    produces = (WpToolkit,)
    tags = (IPUWorkflowTag, FactsPhaseTag)

    def process(self):

        active_vendors = []
        for vendor_list in api.consume(ActiveVendorList):
            active_vendors.extend(vendor_list.data)

        if VENDOR_NAME in active_vendors:
            api.current_logger().info('Vendor {} is active. Looking for information...'.format(VENDOR_NAME))

            repo_list = []
            for src_info in api.consume(VendorSourceRepos):
                if src_info.vendor == VENDOR_NAME:
                    repo_list = src_info.source_repoids
                    break

            variant = None
            version = None
            for maybe_variant in SUPPORTED_VARIANTS:
                if '{}-{}'.format(VENDOR_NAME, maybe_variant) in repo_list:
                    variant = maybe_variant
                    api.current_logger().info('Found WP Toolkit variant {}'.format(variant))

                    pkgData = package_data_for(InstalledRPM, u'wp-toolkit-{}'.format(variant))
                    # name, arch, version, release
                    if pkgData:
                        version = pkgData['version']

                    break

                api.current_logger().debug('Did not find WP Toolkit variant {}'.format(maybe_variant))

            api.produce(WpToolkit(variant=variant, version=version))

        else:
            api.current_logger().info('{} not an active vendor: skipping actor'.format(VENDOR_NAME))
