from leapp.actors import Actor
from leapp.libraries.stdlib import api
from leapp.models import (
    RepositoriesFacts,
    VendorSourceRepos,
    ActiveVendorList,
)
from leapp.tags import FactsPhaseTag, IPUWorkflowTag


class CheckEnabledVendorRepos(Actor):
    """
    Create a list of vendors whose repositories are present on the system and enabled.
    Only those vendors' configurations (new repositories, PES actions, etc.)
    will be included in the upgrade process.
    """

    name = "check_enabled_vendor_repos"
    consumes = (RepositoriesFacts, VendorSourceRepos)
    produces = (ActiveVendorList)
    tags = (IPUWorkflowTag, FactsPhaseTag.Before)

    def process(self):
        repoid_to_vendorname = {}
        active_vendors = set()

        # Permanently active vendors - no matter if their repos are present.
        always_active_vendors = [
            "epel"
        ]
        active_vendors.update(always_active_vendors)

        # Make a dict for easy mapping of repoid -> corresponding vendor name.
        for vendor_src_repodata in api.consume(VendorSourceRepos):
            for vendor_src_repoid in vendor_src_repodata.source_repoids:
                repoid_to_vendorname[vendor_src_repoid] = vendor_src_repodata.vendor

        # Is the repo listed in the vendor map as from_repoid present on the system?
        for repos_facts in api.consume(RepositoriesFacts):
            for repo_file in repos_facts.repositories:
                for repo_data in repo_file.data:
                    self.log.debug(
                        "Looking for repository {} in vendor maps".format(repo_data.repoid)
                    )
                    if repo_data.enabled and repo_data.repoid in repoid_to_vendorname:
                        # If the vendor's repository is present in the system and enabled, count the vendor as active.
                        new_vendor = repoid_to_vendorname[repo_data.repoid]
                        self.log.debug(
                            "Repository {} found and enabled, enabling vendor {}".format(
                                repo_data.repoid, new_vendor
                            )
                        )
                        active_vendors.add(new_vendor)

        if active_vendors:
            self.log.debug("Active vendor list: {}".format(active_vendors))
            api.produce(ActiveVendorList(data=list(active_vendors)))
        else:
            self.log.info("No active vendors found, vendor list not generated")
