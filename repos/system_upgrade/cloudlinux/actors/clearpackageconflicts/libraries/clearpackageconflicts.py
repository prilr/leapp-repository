import os
import errno
from re import L
import shutil

from leapp.libraries.stdlib import api
from leapp.models import InstalledRPM


def problem_packages_installed(problem_packages, lookup):
    """
    Check whether any of the problem packages are present in the system.
    """
    for pkg in problem_packages:
        if pkg in lookup:
            api.current_logger().debug("Conflicting package {} detected".format(pkg))
            return True
    return False


def clear_problem_files(problem_files, problem_dirs):
    """
    Go over the list of problem files and directories and remove them if they exist.
    They'll be replaced by the new packages.
    """
    for p_dir in problem_dirs:
        try:
            if os.path.isdir(p_dir):
                shutil.rmtree(p_dir)
                api.current_logger().debug("Conflicting directory {} removed".format(p_dir))
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise

    for p_file in problem_files:
        try:
            if os.path.isfile(p_file):
                os.remove(p_file)
                api.current_logger().debug("Conflicting file {} removed".format(p_file))
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise


def alt_python37_handle(package_lookup):
    """
    These alt-python37 packages are conflicting with their own builds for EL8.
    """
    problem_packages = [
        "alt-python37-six",
        "alt-python37-pytz",
    ]
    problem_files = []
    problem_dirs = [
        "/opt/alt/python37/lib/python3.7/site-packages/six-1.15.0-py3.7.egg-info",
        "/opt/alt/python37/lib/python3.7/site-packages/pytz-2017.2-py3.7.egg-info",
    ]

    if problem_packages_installed(problem_packages, package_lookup):
        clear_problem_files(problem_files, problem_dirs)


def lua_cjson_handle(package_lookup):
    """
    lua-cjson package is conflicting with the incoming lua-cjson package for EL8.
    """
    problem_packages = [
        "lua-cjson"
    ]
    problem_files = [
        "/usr/lib64/lua/5.1/cjson.so",
        "/usr/share/lua/5.1/cjson/tests/bench.lua",
        "/usr/share/lua/5.1/cjson/tests/genutf8.pl",
        "/usr/share/lua/5.1/cjson/tests/test.lua",
    ]
    problem_dirs = []

    if problem_packages_installed(problem_packages, package_lookup):
        clear_problem_files(problem_files, problem_dirs)


def process():
    rpm_lookup = {rpm.name for rpm in api.consume(InstalledRPM)}
    alt_python37_handle(rpm_lookup)
