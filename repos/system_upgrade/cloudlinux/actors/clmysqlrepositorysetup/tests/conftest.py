"""Shared fixtures for clmysqlrepositorysetup actor tests.

Leapp injects the actor context during pytest collection, so the actor's
private modules (leapp.libraries.common.clmysql, ...) are not importable at
conftest import time.  Imports therefore live inside the fixture bodies.
"""

import pytest


_MARIADB106_META_BASEURL = "http://repo.cloudlinux.com/other/cl$releasever/mysqlmeta/cl-mariadb-10.6/x86_64/"
_MYSQLCLIENT_BASEURL = "http://repo.cloudlinux.com/other/cl$releasever/mysqlmeta/mysqlclient/x86_64/"


@pytest.fixture
def patch_env(monkeypatch):
    """
    Return a callable that patches clmysql_cloudlinux dependencies.

    Defaults to a healthy mariadb106 OK detection targeting CL9.  Pass
    ``clmysql_result`` to exercise a different status (e.g. MISMATCH), or
    override ``clmysql_type`` / ``target_major`` / ``source_major`` to vary the
    scenario.
    """
    from leapp import reporting
    from leapp.libraries.common.clmysql import ClMysqlTypeResult, ClMysqlTypeStatus
    from leapp.libraries.common.testutils import (
        create_report_mocked,
        logger_mocked,
        produce_mocked,
    )
    from leapp.libraries.stdlib import api

    def _apply(clmysql_result=None, clmysql_type="mariadb106", target_major="9", source_major="8"):
        if clmysql_result is None:
            clmysql_result = ClMysqlTypeResult(
                status=ClMysqlTypeStatus.OK,
                governor_type=clmysql_type,
                pkg_type=clmysql_type,
            )
        monkeypatch.setattr(
            "leapp.libraries.actor.clmysql_cloudlinux.get_clmysql_type",
            lambda: clmysql_result,
        )
        monkeypatch.setattr(
            "leapp.libraries.actor.clmysql_cloudlinux.get_target_major_version",
            lambda: target_major,
        )
        monkeypatch.setattr(
            "leapp.libraries.common.clmysql.get_target_major_version",
            lambda: target_major,
        )
        monkeypatch.setattr(
            "leapp.libraries.common.clmysql.get_source_major_version",
            lambda: source_major,
        )
        monkeypatch.setattr(
            "leapp.libraries.actor.clmysql_cloudlinux.create_leapp_repofile_copy",
            lambda *a, **kw: "/tmp/cl-mysql-leapp.repo",
        )
        monkeypatch.setattr(api, "produce", produce_mocked())
        monkeypatch.setattr(api, "current_logger", logger_mocked())
        monkeypatch.setattr(reporting, "create_report", create_report_mocked())

    return _apply


@pytest.fixture
def make_cl_mysql_repofile():
    """Return a factory that builds a Governor-style cl-mysql.repo RepositoryFile."""
    from leapp.models import RepositoryData, RepositoryFile

    def _make(cl_mysql_meta_enabled=True, mysqlclient_enabled=False):
        return RepositoryFile(
            file="cl-mysql.repo",
            data=[
                RepositoryData(
                    repoid="cl-mysql-meta",
                    name="cl-mysql",
                    baseurl=_MARIADB106_META_BASEURL,
                    enabled=cl_mysql_meta_enabled,
                ),
                RepositoryData(
                    repoid="mysqclient",
                    name="mysqlclient",
                    baseurl=_MYSQLCLIENT_BASEURL,
                    enabled=mysqlclient_enabled,
                ),
            ],
        )

    return _make
