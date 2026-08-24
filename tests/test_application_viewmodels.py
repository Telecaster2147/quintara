from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from quintara.application import ProductUseCases
from quintara.contracts import DEFAULT_STRATEGY, STRATEGY_POLICIES
from quintara.dto import PageDTO, PageStatus
from quintara.onboarding import DataSourceChoice
from quintara.service import QuintaraService
from quintara.viewmodels import ApplicationViewModels, NavigationCoordinator, PageViewModel


def test_user_use_cases_expose_pages_without_raw_internal_objects(app_root):
    service = QuintaraService(app_root)
    try:
        use_cases = ProductUseCases(service)
        home = use_cases.home()
        data = use_cases.data()
        training = use_cases.training()
        assert home.status == PageStatus.READY
        assert data.status == PageStatus.EMPTY
        assert data.primary_action and data.primary_action.label == "选择数据来源"
        assert training.metadata["default_strategy"] == "balanced"
        payload = home.as_dict()
        assert "manifest" not in payload
        assert str(Path(app_root)) not in str(payload)
    finally:
        service.close()


def test_navigation_and_page_state_transitions_are_stable(app_root):
    _app = QApplication.instance() or QApplication([])
    navigation = NavigationCoordinator()
    assert navigation.currentPage == "home"
    navigation.navigate("data")
    assert navigation.currentPage == "data"
    navigation.setCompact(True)
    assert navigation.compact is True

    ready = PageViewModel(
        "sample",
        lambda: PageDTO("sample", "示例", PageStatus.EMPTY),
        app_root,
    )
    assert ready.status == "loading"
    ready.load()
    assert ready.status == "empty"

    failed = PageViewModel("sample", lambda: (_ for _ in ()).throw(RuntimeError(f"bad {app_root}")), app_root)
    failed.load()
    assert failed.status == "error"
    assert str(app_root) not in failed.payload["error"]["message"]


def test_application_viewmodels_and_strategy_policy_contract(app_root):
    service = QuintaraService(app_root)
    try:
        models = ApplicationViewModels(ProductUseCases(service))
        models.load_all()
        assert set(models.pages) == {"home", "data", "universe", "train", "results", "history", "diagnostics"}
        assert models.pages["home"].status == "ready"
        assert DEFAULT_STRATEGY == "balanced"
        assert STRATEGY_POLICIES[DEFAULT_STRATEGY]["display_name"] == "稳健平衡"
        assert all(policy["version"].endswith("-v1") for policy in STRATEGY_POLICIES.values())
    finally:
        service.close()


def test_provider_onboarding_keeps_a_concrete_data_import_next_step(app_root):
    service = QuintaraService(app_root)
    try:
        service.confirm_consent()
        service.onboarding_advance(
            2,
            source=DataSourceChoice("provider", accepted_license=True, accepted_transfer=True),
        )
        page = ProductUseCases(service).data()
        assert page.primary_action is not None
        assert page.primary_action.key == "import-provider-package"
        assert "标准生产数据" in page.summary
    finally:
        service.close()
