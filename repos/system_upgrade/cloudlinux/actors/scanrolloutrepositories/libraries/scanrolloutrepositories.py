import os

from leapp.models import (
    CustomTargetRepositoryFile,
    CustomTargetRepository,
    UsedRepositories,
)
from leapp.libraries.stdlib import api
from leapp.libraries.common import repofileutils

from leapp.libraries.common.cl_repofileutils import (
    is_rollout_repository,
    create_leapp_repofile_copy,
    REPO_DIR,
    REPOFILE_SUFFIX,
    LEAPP_COPY_SUFFIX
)


def process_repodata(rollout_repodata, repofile_name):
    for repo in rollout_repodata.data:
        # On some systems, $releasever gets replaced by a string like "8.6", but we want
        # specifically "8" for rollout repositories - URLs with "8.6" don't exist.
        # TODO: This is actually because of the releasever being set in Leapp.
        # Maybe the better option would be to use 8 instead of 8.6 in version string?
        repo.repoid = repo.repoid + "-8"
        repo.baseurl = repo.baseurl.replace("$releasever", "8")

    for repo in rollout_repodata.data:
        api.produce(
            CustomTargetRepository(
                repoid=repo.repoid,
                name=repo.name,
                baseurl=repo.baseurl,
                enabled=repo.enabled,
            )
        )

    resdata = [{repo.repoid: [repo.name, repo.baseurl]} for repo in rollout_repodata.data]
    api.current_logger().debug("Rollout repository {} repodata: {}".format(repofile_name, resdata))

    rollout_reponame = repofile_name[:-len(REPOFILE_SUFFIX)]
    leapp_repocopy_path = create_leapp_repofile_copy(rollout_repodata, rollout_reponame)
    api.produce(CustomTargetRepositoryFile(file=leapp_repocopy_path))


def process_repofile(repofile_name, used_list):
    full_rollout_repo_path = os.path.join(REPO_DIR, repofile_name)
    rollout_repodata = repofileutils.parse_repofile(full_rollout_repo_path)

    # Ignore the repositories (and their files) that are enabled, but have no packages installed from them.
    if not any(repo.repoid in used_list for repo in rollout_repodata.data):
        api.current_logger().debug(
            "No used repositories found in {}, skipping".format(repofile_name)
        )
        return

    api.current_logger().debug("Rollout file {} has used repositories, adding".format(repofile_name))
    process_repodata(rollout_repodata, repofile_name)


def process():
    used_list = []
    for used_repos in api.consume(UsedRepositories):
        for used_repo in used_repos.repositories:
            used_list.append(used_repo.repository)

    for repofile_name in os.listdir(REPO_DIR):
        if not is_rollout_repository(repofile_name) or LEAPP_COPY_SUFFIX in repofile_name:
            continue

        api.current_logger().debug(
            "Detected a rollout repository file: {}".format(repofile_name)
        )

        process_repofile(repofile_name, used_list)
