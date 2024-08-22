from leapp.models import Model, fields
from leapp.topics import SystemFactsTopic


class WpToolkit(Model):
    """
    Records information about presence and versioning of WP Toolkit package management resources on the source system.
    """
    topic = SystemFactsTopic

    """
    States which supported "variant" of WP Toolkit seems available to the package manager.

    Currently, only `cpanel` is supported.
    """
    variant = fields.Nullable(fields.String())

    """
    States which version of the WP Toolkit package for the given variant is installed.

    If no package is installed, this will be `None`.
    """
    version = fields.Nullable(fields.String())
