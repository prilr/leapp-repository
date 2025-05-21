import pytest

# from leapp import reporting
from leapp.libraries.actor import checkcldeployrepofile


@pytest.mark.parametrize(
    "repo_file_paths,expected_res",
    (
        (
            [
                "/etc/yum.repos.d/almalinux-appstream.repo",
                "/etc/yum.repos.d/cloudlinux.repo",
                "/etc/yum.repos.d/cloudlinux-rollout.repo",
                "/etc/yum.repos.d/repo.cloudlinux.com_cloudlinux_8_BaseOS_x86_64_os_",
            ],
            [
                "/etc/yum.repos.d/repo.cloudlinux.com_cloudlinux_8_BaseOS_x86_64_os_",
            ],
        ),
        (
            [
                "/etc/yum.repos.d/almalinux-appstream.repo",
                "/etc/yum.repos.d/cloudlinux.repo",
                "/etc/yum.repos.d/cloudlinux-rollout.repo",
            ],
            [],
        ),
    ),
)
def test_problem_packages_installed(repo_file_paths, expected_res):
    assert expected_res == checkcldeployrepofile.get_cldeploy_repo_files(repo_file_paths)
