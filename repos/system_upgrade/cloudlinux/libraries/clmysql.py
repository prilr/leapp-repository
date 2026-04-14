import collections
import os
import re
import shutil
from enum import Enum

from leapp.libraries.stdlib import CalledProcessError, api, run


class ClMysqlTypeStatus(Enum):
    OK = "ok"
    MISMATCH = "mismatch"


ClMysqlTypeResult = collections.namedtuple(
    "ClMysqlTypeResult", ["status", "governor_type", "pkg_type"]
)

# MySQL Governor tracks the DB type in two files:
#   mysql.type           - the *desired* type set by --mysql-version (may be ahead of reality)
#   mysql.type.installed - the *actually installed* type, written after a successful --install
# For Leapp we need what is really on disk, so we read mysql.type.installed.
# Both files are present on CL7 and CL8+ when governor-mysql is installed.
GOVERNOR_INSTALLED_TYPE_FILE = "/usr/share/lve/dbgovernor/mysql.type.installed"

# This dict matches the MySQL type strings with DNF module and stream IDs.
MODULE_STREAMS = {
    "mysql55": "mysql:cl-MySQL55",
    "mysql56": "mysql:cl-MySQL56",
    "mysql57": "mysql:cl-MySQL57",
    "mysql80": "mysql:cl-MySQL80",
    "mysql84": "mysql:cl-MySQL84",
    "mariadb55": "mariadb:cl-MariaDB55",
    "mariadb100": "mariadb:cl-MariaDB100",
    "mariadb101": "mariadb:cl-MariaDB101",
    "mariadb102": "mariadb:cl-MariaDB102",
    "mariadb103": "mariadb:cl-MariaDB103",
    "mariadb104": "mariadb:cl-MariaDB104",
    "mariadb105": "mariadb:cl-MariaDB105",
    "mariadb106": "mariadb:cl-MariaDB106",
    "mariadb1011": "mariadb:cl-MariaDB1011",
    "mariadb1104": "mariadb:cl-MariaDB1104",
    "percona56": "percona:cl-Percona56",
}


def resolve_clmysql_module_stream(clmysql_type):
    """
    Return (dnf_module_name, stream) for CloudLinux Governor MySQL/MariaDB/Percona types.

    Prefer MODULE_STREAMS; if missing, derive stream from the type string (e.g. mariadb1012 ->
    mariadb:cl-MariaDB1012) so newer CL releases work before this table is updated.
    """
    if not clmysql_type:
        return None, None

    entry = MODULE_STREAMS.get(clmysql_type)
    if entry:
        mod_name, mod_stream = entry.split(":", 1)
        return mod_name, mod_stream

    match = re.match(r"^(mariadb)(\d+)$", clmysql_type)
    if match:
        return "mariadb", "cl-MariaDB{}".format(match.group(2))

    match = re.match(r"^(mysql)(\d+)$", clmysql_type)
    if match:
        return "mysql", "cl-MySQL{}".format(match.group(2))

    match = re.match(r"^(percona)(\d+)$", clmysql_type)
    if match:
        return "percona", "cl-Percona{}".format(match.group(2))

    return None, None


def _resolve_mysqld_path():
    """
    Return absolute path to mysqld: PATH first, then usual daemon locations.
    """
    path = shutil.which("mysqld")
    if path:
        return path
    for candidate in ("/usr/sbin/mysqld", "/usr/libexec/mysqld", "/usr/bin/mysqld"):
        if os.path.isfile(candidate):
            return candidate
    return None


def _clmysql_name_version_from_rpm(path):
    """
    Query the RPM that owns ``path`` and return (name_lower, version_lower) for the first
    CloudLinux cl-{mariadb,mysql,percona} package when several packages claim the file.
    """
    try:
        rpm_out = run(
            [
                "rpm",
                "-qf",
                path,
                "--queryformat",
                "%{NAME} %{VERSION}\\n",
            ]
        )["stdout"]
    except CalledProcessError as err:
        api.current_logger().info(
            "Could not query RPM owner of mysqld path {0}: {1}".format(path, str(err))
        )
        return None

    for line in rpm_out.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            api.current_logger().info(
                "Unexpected rpm --queryformat line for {0!r}: {1!r}".format(path, line)
            )
            continue
        name, version = parts[0].lower(), parts[1].lower()
        if "cl-mariadb" in name or "cl-mysql" in name or "cl-percona" in name:
            return name, version

    return None


def get_clmysql_version_from_pkg():
    """
    Detect the current installed CL-MySQL/MariaDB/Percona version from the mysqld binary.
    """
    mysqld_path = _resolve_mysqld_path()
    if not mysqld_path:
        api.current_logger().info(
            "CL-MySQL version detection failed: mysqld not found in PATH or standard locations"
        )
        return None

    pair = _clmysql_name_version_from_rpm(mysqld_path)
    if not pair:
        api.current_logger().info(
            "CL-MySQL version detection failed: no CloudLinux cl-mysql/cl-mariadb/cl-percona "
            "package owns {0}".format(mysqld_path)
        )
        return None

    name, version = pair
    if "cl-mariadb" in name:
        name = "mariadb"
    elif "cl-mysql" in name:
        name = "mysql"
    elif "cl-percona" in name:
        name = "percona"
    else:
        return None

    return "%s%s" % (name, "".join(version.split(".")[:2]))


def get_pkg_prefix(clmysql_type):
    """
    Get a Yum package prefix string from cl-mysql type.
    """
    if clmysql_type.startswith("mysql"):
        return "cl-MySQL"
    elif clmysql_type.startswith("mariadb"):
        return "cl-MariaDB"
    elif clmysql_type.startswith("percona"):
        return "cl-Percona"
    else:
        return None


def _get_clmysql_type_from_governor():
    """
    Read the actually installed DB type from the MySQL Governor cache file.

    Governor stores the desired type in `mysql.type` (written by `--mysql-version`)
    and the actually installed type in `mysql.type.installed` (written after a
    successful `--install`).  We read the installed file so that a pending
    `--mysql-version` that was never followed by `--install` does not mislead Leapp.

    Returns a type string like `mariadb106`, or None when Governor is absent,
    the file is missing/empty, or the value is `auto`.
    """
    if not os.path.isfile(GOVERNOR_INSTALLED_TYPE_FILE):
        return None
    try:
        with open(GOVERNOR_INSTALLED_TYPE_FILE, "r") as f:
            value = f.read().strip()
    except (IOError, OSError) as err:
        api.current_logger().warning(
            "Could not read Governor mysql.type.installed file: {}".format(err)
        )
        return None
    if not value or value == "auto":
        return None
    return value


def get_clmysql_type():
    """
    Get the currently active CL MySQL/MariaDB/Percona type.

    Prefer the MySQL Governor config file (authoritative when Governor manages the DB),
    fall back to detecting the type from the mysqld binary's RPM ownership.

    When both sources are available, cross-check them. On mismatch, return a
    result with :attr:`ClMysqlTypeStatus.MISMATCH` so the caller can raise an inhibitor.

    :returns: :class:`ClMysqlTypeResult` with status, resolved type, and raw detection values.
    """
    governor_type = _get_clmysql_type_from_governor()
    pkg_type = get_clmysql_version_from_pkg()

    if governor_type and pkg_type and governor_type != pkg_type:
        api.current_logger().warning(
            "Governor mysql.type.installed says '{}' but RPM-based detection says '{}'."
            .format(governor_type, pkg_type)
        )
        return ClMysqlTypeResult(
            status=ClMysqlTypeStatus.MISMATCH,
            governor_type=governor_type,
            pkg_type=pkg_type,
        )

    if governor_type:
        api.current_logger().debug(
            "CL-MySQL type from Governor file: {}".format(governor_type)
        )

    return ClMysqlTypeResult(
        status=ClMysqlTypeStatus.OK,
        governor_type=governor_type,
        pkg_type=pkg_type,
    )
