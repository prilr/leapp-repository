import os
import errno
import shutil

from leapp.actors import Actor
from leapp.libraries.common.rpms import has_package
from leapp.models import InstalledRPM
from leapp.tags import DownloadPhaseTag, IPUWorkflowTag
from leapp.libraries.common.cllaunch import run_on_cloudlinux


class ClearPackageConflicts(Actor):
    """
    Remove several python package files manually to resolve conflicts between versions of packages to be upgraded.
    """

    name = "clear_package_conflicts"
    consumes = (InstalledRPM,)
    produces = ()
    tags = (DownloadPhaseTag.Before, IPUWorkflowTag)

    @run_on_cloudlinux
    def process(self):
        problem_packages = [
            "alt-python37-six",
            "alt-python37-pytz",
        ]

        problem_packages_installed = False
        for pkg in problem_packages:
            if has_package(InstalledRPM, pkg):
                self.log.debug("Conflicting package {} detected".format(pkg))
                problem_packages_installed = True
                break

        if problem_packages_installed:
            problem_dirs = [
                "/opt/alt/python37/lib/python3.7/site-packages/six-1.15.0-py3.7.egg-info",
                "/opt/alt/python37/lib/python3.7/site-packages/pytz-2017.2-py3.7.egg-info",
            ]
            problem_files = []

            for p_dir in problem_dirs:
                try:
                    if os.path.isdir(p_dir):
                        shutil.rmtree(p_dir)
                        self.log.debug("Conflicting directory {} removed".format(p_dir))
                except OSError as e:
                    if e.errno != errno.ENOENT:
                        raise

            for p_file in problem_files:
                try:
                    if os.path.isfile(p_file):
                        os.remove(p_file)
                        self.log.debug("Conflicting file {} removed".format(p_file))
                except OSError as e:
                    if e.errno != errno.ENOENT:
                        raise
