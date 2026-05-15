import os
import re

from leapp import reporting
from leapp.libraries.common.rpms import has_package
from leapp.libraries.stdlib import api
from leapp.models import DistributionSignedRPM

POSTGRESQL_CONF_PATH = '/var/lib/pgsql/data/postgresql.conf'

# Matches the start of an active (uncommented) setting line for
# unix_socket_directories. PostgreSQL config syntax allows optional leading
# whitespace; a line is a comment if its first non-whitespace char is '#'.
_UNIX_SOCKET_DIRECTORIES_RE = re.compile(r'^\s*unix_socket_directories\s*=')

# Summary for postgresql-server report
report_server_inst_summary = (
    'PostgreSQL server component will be upgraded. Since RHEL-8 includes'
    ' PostgreSQL server 10 by default, which is incompatible with 9.2'
    ' included in RHEL-7, it is necessary to proceed with additional steps'
    ' for the complete upgrade of the PostgreSQL data.'
)

report_server_inst_hint = (
    'Back up your data before proceeding with the upgrade.'
    ' The upgrade keeps your PostgreSQL data directory in the old (9.2)'
    ' on-disk format - postgresql will refuse to start on the upgraded'
    ' system until you migrate the data. After the upgrade completes:\n'
    '  1. Install the postgresql-upgrade package (provides the old'
    ' server binaries needed by the migration helper):\n'
    '       dnf install postgresql-upgrade\n'
    '  2. Migrate the database files to the new format:\n'
    '       postgresql-setup --upgrade\n'
    '  3. Start PostgreSQL:\n'
    '       systemctl start postgresql\n'
    'For more details see the documentation section'
    ' "Migrating to a RHEL 8 version of PostgreSQL".'
)

# Link URL for postgresql-server report
report_server_inst_link_url = 'https://red.ht/rhel-8-migrate-postgresql-server'

# List of dropped extensions from postgresql-contrib package
report_contrib_inst_dropext = ['dummy_seclabel', 'test_parser', 'tsearch2']

# Summary for postgresql-contrib report
report_contrib_inst_summary = (
    'Please note that some extensions have been dropped from the'
    ' postgresql-contrib package and might not be available after'
    ' the upgrade:{}'
    .format(''.join(['\n    - {}'.format(i) for i in report_contrib_inst_dropext]))
)

# Summary / remediation for the unix_socket_directories config-incompat report.
# RHEL-7's PG 9.2 ships with a forward-compatible patch that accepts the newer
# (PG 9.3+) plural parameter name unix_socket_directories. RHEL-8's
# postgresql-upgrade package ships an unpatched 9.2 server binary that rejects
# the plural form with a FATAL config error and aborts on startup; that breaks
# postgresql-setup --upgrade post-Elevate. The default CL7 postgresql.conf has
# this line commented out by default, but admin edits, cPanel tooling, and
# config-management commonly uncomment or rewrite it.
report_plural_socket_param_summary = (
    'PostgreSQL configuration file {conf} contains an active'
    ' "unix_socket_directories" setting. RHEL-7 PostgreSQL 9.2 accepts this'
    ' plural parameter name (added in PG 9.3 and back-ported by RHEL into 9.2),'
    ' but the unpatched 9.2 server binary shipped in RHEL-8\'s postgresql-upgrade'
    ' package does not. As a result, "postgresql-setup --upgrade" will fail'
    ' post-upgrade with "unrecognized configuration parameter'
    ' unix_socket_directories" and PostgreSQL will refuse to start on the'
    ' upgraded system until the parameter is renamed.'
).format(conf=POSTGRESQL_CONF_PATH)

report_plural_socket_param_hint = (
    'Before running the upgrade, rename the parameter on the affected line of'
    ' {conf} from "unix_socket_directories" (plural) to "unix_socket_directory"'
    ' (singular). For example:\n'
    '       sed -i \'s/^unix_socket_directories/unix_socket_directory/\' {conf}\n'
    'If you have already upgraded and PostgreSQL is failing to start, apply the'
    ' same rename to the same file (which post-upgrade may have been renamed to'
    ' /var/lib/pgsql/data-old/postgresql.conf by postgresql-setup), then re-run:\n'
    '       postgresql-setup --upgrade'
).format(conf=POSTGRESQL_CONF_PATH)


def _report_server_installed():
    """
    Create report on postgresql-server package installation detection.

    Should remind user about present PostgreSQL server package
    installation, warn them about necessary additional steps, and
    redirect them to online documentation for the upgrade process.
    """
    reporting.create_report([
        reporting.Title('PostgreSQL (postgresql-server) has been detected on your system'),
        reporting.Summary(report_server_inst_summary),
        reporting.Severity(reporting.Severity.MEDIUM),
        reporting.Groups([reporting.Groups.SERVICES]),
        reporting.ExternalLink(title='Migrating to a RHEL 8 version of PostgreSQL',
                               url=report_server_inst_link_url),
        reporting.RelatedResource('package', 'postgresql-server'),
        reporting.Remediation(hint=report_server_inst_hint),
        ])


def _report_contrib_installed():
    """
    Create report on postgresql-contrib package installation detection.

    Should remind user about present PostgreSQL contrib package
    installation and provide them with a list of extensions no longer
    shipped with this package.
    """
    reporting.create_report([
        reporting.Title('PostgreSQL (postgresql-contrib) has been detected on your system'),
        reporting.Summary(report_contrib_inst_summary),
        reporting.Severity(reporting.Severity.MEDIUM),
        reporting.Groups([reporting.Groups.SERVICES]),
        reporting.RelatedResource('package', 'postgresql-contrib')
        ])


def _postgresql_conf_uses_plural_socket_param(path=POSTGRESQL_CONF_PATH):
    """
    Return True if `path` contains an active (uncommented) line setting the
    plural parameter name `unix_socket_directories`.

    Missing files or unreadable lines are treated as "not affected" - the
    caller already knows postgresql-server is installed, but the data dir may
    never have been initialized (initdb not yet run), in which case no
    postgresql.conf exists. We don't want to scare users with a warning for
    a state that can't trigger the bug.
    """
    if not os.path.isfile(path):
        return False
    try:
        with open(path, 'r') as fp:
            for raw_line in fp:
                if _UNIX_SOCKET_DIRECTORIES_RE.match(raw_line):
                    return True
    except (IOError, OSError):
        # Permissions or transient I/O issue. Conservatively return False;
        # if the file truly contains the bad line, postgresql-setup --upgrade
        # will surface it after the upgrade and the generic hint covers it.
        return False
    return False


def _report_plural_socket_param_detected():
    """
    Create report when postgresql.conf contains an active
    unix_socket_directories (plural) setting, which will break the post-upgrade
    data migration. See module docstring for the full mechanism.
    """
    reporting.create_report([
        reporting.Title(
            'PostgreSQL configuration uses "unix_socket_directories"'
            ' which will break post-upgrade data migration'
        ),
        reporting.Summary(report_plural_socket_param_summary),
        reporting.Severity(reporting.Severity.HIGH),
        reporting.Groups([reporting.Groups.SERVICES]),
        reporting.RelatedResource('package', 'postgresql-server'),
        reporting.RelatedResource('file', POSTGRESQL_CONF_PATH),
        reporting.Remediation(hint=report_plural_socket_param_hint),
        ])


def report_installed_packages(_context=api):
    """
    Create reports according to detected PostgreSQL packages.

    Create the report if the postgresql-server rpm (RH signed) is installed.
    Additionally, create another report if the postgresql-contrib rpm
    is installed, and another if postgresql.conf contains an active
    unix_socket_directories (plural) setting.
    """
    has_server = has_package(DistributionSignedRPM, 'postgresql-server', context=_context)
    has_contrib = has_package(DistributionSignedRPM, 'postgresql-contrib', context=_context)

    if has_server:
        # postgresql-server
        _report_server_installed()
        if has_contrib:
            # postgresql-contrib
            _report_contrib_installed()
        if _postgresql_conf_uses_plural_socket_param():
            _report_plural_socket_param_detected()
