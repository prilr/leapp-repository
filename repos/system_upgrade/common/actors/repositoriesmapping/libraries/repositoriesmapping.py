import os

from leapp.exceptions import StopActorExecutionError
from leapp.libraries.common.config.version import get_source_major_version, get_target_major_version
from leapp.libraries.common.repomaputils import RepoMapData
from leapp.libraries.common.fetch import load_data_asset
from leapp.libraries.common.rpms import get_leapp_packages, LeappComponents
from leapp.libraries.stdlib import api
from leapp.models import RepositoriesMapping
from leapp.models.fields import ModelViolationError

OLD_REPOMAP_FILE = 'repomap.csv'
"""The name of the old, deprecated repository mapping file (no longer used)."""

REPOMAP_FILE = 'repomap.json'
"""The name of the new repository mapping file."""


def _inhibit_upgrade(msg):
    local_path = os.path.join('/etc/leapp/file', REPOMAP_FILE)
    hint = (
        'All official data files are nowadays part of the installed rpms.'
        ' This issue is usually encountered when the data files are incorrectly customized, replaced, or removed'
        ' (e.g. by custom scripts).'
        ' In case you want to recover the original {lp} file, remove the current one (if it still exists)'
        ' and reinstall the following packages: {rpms}.'
        .format(
            lp=local_path,
            rpms=', '.join(get_leapp_packages(component=LeappComponents.REPOSITORY))
        )
    )
    raise StopActorExecutionError(msg, details={'hint': hint})


def _read_repofile(repofile):
    # NOTE(pstodulk): load_data_assert raises StopActorExecutionError, see
    # the code for more info. Keeping the handling on the framework in such
    # a case as we have no work to do in such a case here.
    repofile_data = load_data_asset(api.current_actor(),
                                    repofile,
                                    asset_fulltext_name='Repositories mapping',
                                    docs_url='',
                                    docs_title='')
    return repofile_data


def scan_repositories(read_repofile_func=_read_repofile):
    """
    Scan the repository mapping file and produce RepositoriesMap msg.

    See the description of the actor for more details.
    """
    # TODO: add filter based on the current arch
    # TODO: deprecate the product type and introduce the "channels" ?.. more or less
    # NOTE: product type is changed, now it's channel: eus,e4s,aus,tus,ga,beta

    if os.path.exists(os.path.join('/etc/leapp/files', OLD_REPOMAP_FILE)):
        # NOTE: what about creating the report (instead of warning)
        api.current_logger().warning(
            'The old repomap file /etc/leapp/files/repomap.csv is present.'
            ' The file has been replaced by the repomap.json file and it is'
            ' not used anymore.'
        )

    json_data = read_repofile_func(REPOMAP_FILE)
    try:
        repomap_data = RepoMapData.load_from_dict(json_data)
        mapping = repomap_data.get_mappings(get_source_major_version(), get_target_major_version())

        valid_major_versions = [get_source_major_version(), get_target_major_version()]
        api.produce(RepositoriesMapping(
            mapping=mapping,
            repositories=repomap_data.get_repositories(valid_major_versions)
        ))
    except ModelViolationError as err:
        err_message = (
            'The repository mapping file is invalid: '
            'the JSON does not match required schema (wrong field type/value): {}'
            .format(err)
        )
        _inhibit_upgrade(err_message)
    except KeyError as err:
        _inhibit_upgrade(
            'The repository mapping file is invalid: the JSON is missing a required field: {}'.format(err))
    except ValueError as err:
        # The error should contain enough information, so we do not need to clarify it further
        _inhibit_upgrade('The repository mapping file is invalid: {}'.format(err))
