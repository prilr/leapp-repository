import pytest

# from leapp import reporting
from leapp.libraries.actor import clearpackageconflicts


@pytest.mark.parametrize(
    "problem_pkgs,lookup,expected_res",
    (
        (["cagefs"], {"cagefs", "dnf"}, True),
        (["lve-utils"], {"lve-utils", "dnf"}, True),
        (["nonexistent-pkg"], {"cagefs", "dnf"}, False),
        (["cagefs"], {"lve-utils", "dnf"}, False),
    ),
)
def test_problem_packages_installed(problem_pkgs, lookup, expected_res):
    assert expected_res == clearpackageconflicts.problem_packages_installed(problem_pkgs, lookup)
