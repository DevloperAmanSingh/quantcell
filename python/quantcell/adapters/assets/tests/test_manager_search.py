"""Search fan-out must not wait on a source that hangs."""

import threading
import time
from dataclasses import dataclass, field
from typing import List

import pytest

from quantcell.adapters.assets import manager as manager_module
from quantcell.adapters.assets.manager import AdapterManager
from quantcell.adapters.assets.types import (
    AssetSearchQuery,
    AssetSearchResult,
    AssetType,
    DataSource,
)

SHORT_TIMEOUT_S = 0.2
# Upper bound for a search that respects the deadline (timeout + slack).
MAX_ELAPSED_S = 1.0


@dataclass(eq=False)
class FakeAdapter:
    """Duck-typed stand-in for a BaseDataAdapter's search interface."""

    source: DataSource
    results: List[AssetSearchResult] = field(default_factory=list)
    release: threading.Event | None = None

    def search_assets(self, query: AssetSearchQuery) -> List[AssetSearchResult]:
        if self.release is not None:
            self.release.wait()
        return self.results


def _result(ticker: str) -> AssetSearchResult:
    return AssetSearchResult(
        ticker=ticker,
        asset_type=AssetType.STOCK,
        names={"en-US": ticker},
        exchange=ticker.split(":")[0],
        country="US",
    )


def test_search_returns_fast_results_when_another_source_hangs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(manager_module, "SEARCH_TIMEOUT_S", SHORT_TIMEOUT_S)
    hang = threading.Event()
    manager = AdapterManager()
    manager.adapters = {
        DataSource.YFINANCE: FakeAdapter(
            DataSource.YFINANCE, results=[_result("NASDAQ:AAPL")]
        ),
        DataSource.BAOSTOCK: FakeAdapter(DataSource.BAOSTOCK, release=hang),
    }

    started = time.monotonic()
    try:
        results = manager.search_assets(AssetSearchQuery(query="apple"))
    finally:
        hang.set()  # let the stuck worker thread exit
    elapsed = time.monotonic() - started

    assert [r.ticker for r in results] == ["NASDAQ:AAPL"]
    assert elapsed < MAX_ELAPSED_S


def test_source_that_timed_out_is_skipped_on_the_next_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(manager_module, "SEARCH_TIMEOUT_S", SHORT_TIMEOUT_S)
    hang = threading.Event()
    slow = FakeAdapter(DataSource.BAOSTOCK, release=hang)
    manager = AdapterManager()
    manager.adapters = {
        DataSource.YFINANCE: FakeAdapter(
            DataSource.YFINANCE, results=[_result("NASDAQ:AAPL")]
        ),
        DataSource.BAOSTOCK: slow,
    }
    calls: List[str] = []
    original = slow.search_assets
    monkeypatch.setattr(
        slow, "search_assets", lambda q: calls.append(q.query) or original(q)
    )

    try:
        manager.search_assets(AssetSearchQuery(query="first"))
        started = time.monotonic()
        results = manager.search_assets(AssetSearchQuery(query="second"))
        elapsed = time.monotonic() - started
    finally:
        hang.set()

    assert calls == ["first"]
    assert [r.ticker for r in results] == ["NASDAQ:AAPL"]
    assert elapsed < SHORT_TIMEOUT_S
