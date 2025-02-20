from datetime import datetime

from leapp.actors import Actor
from leapp.tags import FirstBootPhaseTag, IPUWorkflowTag
from leapp.libraries.common.cllaunch import run_on_cloudlinux


class CreateFinishMarker(Actor):
    """
    Create a finish marker file to indicate that the upgrade has been completed.
    Other utilities or tests can check for the existence of this file to determine if the upgrade has been completed.
    """

    name = 'create_finish_marker'
    description = 'Create a finish marker file to indicate that the upgrade has been completed.'
    consumes = ()
    produces = ()
    # Place this actor as far as possible in the workflow, after the absolute majority of other actors have run
    tags = (FirstBootPhaseTag.After, IPUWorkflowTag)

    @run_on_cloudlinux
    def process(self):
        # Create a finish marker file to indicate that the upgrade has been completed
        with open('/var/log/leapp/leapp-upgrade-finished', 'w') as marker_file:
            marker_file.write('Leapp upgrade completed on: {}\n'.format(datetime.now()))
