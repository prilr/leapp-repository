from leapp import reporting
from leapp.libraries.actor import checkpanelmemory
from leapp.libraries.common.testutils import create_report_mocked, CurrentActorMocked
from leapp.libraries.stdlib import api
from leapp.models import MemoryInfo, InstalledControlPanel
from leapp.utils.report import is_inhibitor

from leapp.libraries.common.detectcontrolpanel import (
    UNKNOWN_NAME,
    INTEGRATED_NAME,
    CPANEL_NAME,
)


def test_check_memory_low(monkeypatch):
    monkeypatch.setattr(api, "current_actor", CurrentActorMocked())
    # _check_memory(panel_name, mem_info): panel must be string key for required_memory
    minimum_req_error = checkpanelmemory._check_memory(
        INTEGRATED_NAME, MemoryInfo(mem_total=1024)
    )
    assert minimum_req_error


def test_check_memory_high(monkeypatch):
    monkeypatch.setattr(api, "current_actor", CurrentActorMocked())
    minimum_req_error = checkpanelmemory._check_memory(
        CPANEL_NAME, MemoryInfo(mem_total=16273492)
    )
    assert not minimum_req_error


def _mock_consume(panel_name, memory_info):
    """Return a consume that yields the right model type for process()."""

    def consume(model):
        if model is InstalledControlPanel:
            return iter([InstalledControlPanel(name=panel_name)])
        if model is MemoryInfo:
            return iter([memory_info])
        return iter([])

    return consume


def test_report(monkeypatch):
    title_msg = "Minimum memory requirements for panel {} are not met".format(
        UNKNOWN_NAME
    )
    monkeypatch.setattr(api, "current_actor", CurrentActorMocked())
    monkeypatch.setattr(
        api,
        "consume",
        _mock_consume(UNKNOWN_NAME, MemoryInfo(mem_total=129)),
    )
    monkeypatch.setattr(reporting, "create_report", create_report_mocked())
    checkpanelmemory.process()
    assert reporting.create_report.called
    assert title_msg == reporting.create_report.report_fields["title"]
    assert is_inhibitor(reporting.create_report.report_fields)
