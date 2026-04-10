import os
import re

from leapp.libraries.stdlib import CalledProcessError, api, run

# This file contains the data on the currently active MySQL installation type and version.
CL7_MYSQL_TYPE_FILE = "/usr/share/lve/dbgovernor/mysql.type"

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


def get_clmysql_version_from_pkg():
    """
    Detect the current installed CL-MySQL version.
    """
    try:
        mysqld_safe_cmd = run(["which", "mysqld"])
    except CalledProcessError as err:
        api.current_logger().info(
            "CL-MySQL version detection failed - unable to determine mysqld bin path: {}".format(str(err))
        )
        return None

    try:
        rpm_qf_cmd = run(["rpm", "-qf", r'--qf="%{name} %{version}"', mysqld_safe_cmd["stdout"].strip()])
    except CalledProcessError as err:
        api.current_logger().info("Could not get CL-MySQL package version from RPM: {}".format(str(err)))
        return None

    name, version = rpm_qf_cmd["stdout"].lower().split(" ")
    if "cl-mariadb" in name:
        name = "mariadb"
    elif "cl-mysql" in name:
        name = "mysql"
    elif "cl-percona" in name:
        name = "percona"
    else:
        # non-CL SQL package
        return None

    return "%s%s" % (name, "".join(version.split(".")[:2]))


def get_pkg_prefix(clmysql_type):
    """
    Get a Yum package prefix string from cl-mysql type.
    """
    if "mysql" in clmysql_type:
        return "cl-MySQL"
    elif "mariadb" in clmysql_type:
        return "cl-MariaDB"
    elif "percona" in clmysql_type:
        return "cl-Percona"
    else:
        return None


def get_clmysql_type():
    """
    Get the currently active MySQL type from the Governor configuration file.
    """
    # if os.path.isfile(CL7_MYSQL_TYPE_FILE):
    #     with open(CL7_MYSQL_TYPE_FILE, "r") as mysql_f:
    #         return mysql_f.read()
    return get_clmysql_version_from_pkg()
