from leapp.models import fields, Model
from leapp.topics import SystemInfoTopic


class SystemdTimersInfoSource(Model):
    """
    Names of the systemd timer unit files present on the source system.

    Leapp's own systemd scan covers '.service' units only, so timers are not
    represented anywhere else. This information is needed on the target system
    to tell a timer that is new on the target (and therefore never seen, let
    alone disabled, by the administrator) apart from one that already existed
    on the source system, whose state must be left alone.
    """

    topic = SystemInfoTopic

    timers = fields.List(fields.String(), default=[])
    """
    Names of all installed systemd timer unit files, including the '.timer'
    suffix. Template units are included; instances of templates are not, as
    they have no unit file of their own.
    """
