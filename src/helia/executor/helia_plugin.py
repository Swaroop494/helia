"""Pytest hooks recording per-node dynamic contexts and structured failures."""

import json
from pathlib import Path

import coverage
import pytest

failures: list[dict] = []
test_outcomes: dict[str, str] = {}


def context(item, phase):
    cov = coverage.Coverage.current()
    if cov:
        cov.switch_context(item.nodeid + "|" + phase)


def pytest_runtest_setup(item):
    context(item, "setup")


def pytest_runtest_call(item):
    context(item, "run")


def pytest_runtest_teardown(item):
    context(item, "teardown")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" or report.failed or report.skipped:
        test_outcomes[item.nodeid] = report.outcome
    if call.excinfo:
        failures.append(
            {
                "nodeid": item.nodeid,
                "phase": call.when,
                "type": call.excinfo.typename,
                "assertion": call.excinfo.errisinstance(AssertionError),
                "message": str(call.excinfo.value)[:2000],
            }
        )


def pytest_sessionfinish(session, exitstatus):
    Path("/work/pytest.json").write_text(
        json.dumps({"failures": failures, "test_outcomes": test_outcomes})
    )
