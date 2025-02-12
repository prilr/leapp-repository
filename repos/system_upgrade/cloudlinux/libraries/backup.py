"""
Backup functionality for CloudLinux system upgrade process.

This module provides utilities for backing up and restoring system configuration files
during the CloudLinux upgrade process. It includes functions for:
- Backing up files to a specified backup directory
- Creating in-place backups with .leapp-backup suffix
- Backing up and removing files
- Restoring files from backups

Typically used in other CloudLinux upgrade actors to ensure that some specific configuration files
are preserved and can be restored in case of issues during the upgrade process.
"""

import os
import shutil
from leapp.libraries.stdlib import api

CLSQL_BACKUP_FILES = [
    "/etc/container/dbuser-map",
    "/etc/container/ve.cfg",
    "/etc/container/mysql-governor.xml",
    "/etc/container/governor_package_limit.json"
]

BACKUP_DIR = "/var/lib/leapp/cl_backup"
LEAPP_BACKUP_SUFFIX = ".leapp-backup"


def backup_and_remove(path):
    # type: (str) -> None
    """
    Backup the file in-place and remove the original file.

    :param path: Path of the file to backup and remove.
    """
    backup_file_in_place(path)
    os.unlink(path)


def backup_file_in_place(path):
    # type: (str) -> None
    """
    Backup file in place, creating a copy of it with the same name and .leapp-backup suffix.

    :param path: Path of the file to backup.
    """
    backup_file(path, path + LEAPP_BACKUP_SUFFIX)


def backup_file(source, destination, backup_directory=""):
    # type: (str, str, str) -> None
    """
    Backup file to a backup directory.

    :param source: Path of the file to backup.
    :param destination: Destination name of a file in the backup directory.
    If an absolute path is provided, it will be used as the destination path.
    :param backup_directory: Backup directory override, defaults to None
    """
    # If destination is an absolute path, use it as the destination path
    if os.path.isabs(destination):
        dest_path = destination
    else:
        if not backup_directory:
            backup_directory = BACKUP_DIR
        if not os.path.isdir(backup_directory):
            os.makedirs(backup_directory)
        dest_path = os.path.join(backup_directory, destination)

    api.current_logger().debug('Backing up file: {} to {}'.format(source, dest_path))
    shutil.copy(source, dest_path)


def restore_file(source, destination, backup_directory=""):
    # type: (str, str, str) -> None
    """
    Restore file from a backup directory.

    :param source: Name of a file in the backup directory.
    :param destination: Destination path to restore the file to.
    :param dir: Backup directory override, defaults to None
    """
    if not backup_directory:
        backup_directory = BACKUP_DIR
    src_path = os.path.join(backup_directory, source)

    api.current_logger().debug('Restoring file: {} to {}'.format(src_path, destination))
    shutil.copy(src_path, destination)
