from leapp.actors import Actor
from leapp.tags import PreparationPhaseTag, IPUWorkflowTag
from leapp.libraries.common.cllaunch import run_on_cloudlinux

import os

class UnsetClnCacheOnlyFlag(Actor):
    """
    Remove the flag for the dnf-spacewalk-plugin to not attempt to contact the CLN server during transaction.
    """

    name = 'unset_cln_cache_only_flag'
    consumes = ()
    produces = ()
    tags = (IPUWorkflowTag, PreparationPhaseTag)

    @run_on_cloudlinux
    def process(self):
        os.remove('/var/lib/leapp/el8userspace/etc/cln_leapp_in_progress', 'w')
