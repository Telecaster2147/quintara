"""User-oriented application use cases over the authoritative domain service."""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from .contracts import DEFAULT_STRATEGY, STRATEGY_POLICIES
from .core import JobState, UniverseMode
from .dto import PageDTO, PageStatus, RecoveryActionDTO, TechnicalDetailsDTO
from .service import QuintaraService


def _bytes(value: int | None) -> str:
    size = float(value or 0)
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    index = 0
    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1
    return f"{size:.1f} {units[index]}"


def _technical(title: str, value: dict[str, Any]) -> TechnicalDetailsDTO:
    entries = tuple((str(key), str(item)) for key, item in value.items() if item is not None)
    return TechnicalDetailsDTO(
        title=title,
        entries=entries,
        copy_text=json.dumps(value, ensure_ascii=False, indent=2, default=str),
    )


class ProductUseCases:
    """One presentation-safe boundary shared by GUI and human CLI summaries."""

    PAGE_KEYS = ("home", "data", "universe", "train", "results", "history", "settings", "diagnostics")

    def __init__(self, service: QuintaraService) -> None:
        self.service = service

    def environment(self) -> PageDTO:
        report = self.service.doctor()
        findings = report.get("findings", [])
        blocked = any(item.get("severity") == "FAIL" for item in findings)
        gpu = report.get("gpu", {})
        runtime = report.get("runtime", {})
        disk = report.get("disk", {})
        cards = (
            {"title": "CPU 研究路径", "value": f"{runtime.get('cpu_count', 1)} 核", "tone": "warning" if blocked else "success"},
            {"title": "内存", "value": f"{runtime.get('memory_gib') or '未知'} GiB", "tone": "neutral"},
            {"title": "可用磁盘", "value": _bytes(disk.get("free_bytes")), "tone": "warning" if blocked else "success"},
            {"title": "GPU 实验加速", "value": gpu.get("name") or "未启用", "tone": "info"},
        )
        return PageDTO(
            key="diagnostics",
            title="环境诊断",
            eyebrow="本机运行能力",
            status=PageStatus.READY,
            summary="CPU 路径满足日常研究要求。" if not blocked else "存在需要处理的运行条件。",
            cards=cards,
            notices=tuple(
                {"tone": str(item.get("severity", "PASS")).lower(), "text": str(item.get("message", ""))}
                for item in findings
            ),
            technical=_technical(
                "环境技术详情",
                {
                    "系统": report.get("os", {}).get("system"),
                    "系统版本": report.get("os", {}).get("release"),
                    "Python": runtime.get("python"),
                    "架构": runtime.get("machine"),
                    "GUI 平台": report.get("gui_platform", "待启动探测"),
                },
            ),
        )

    def data(self) -> PageDTO:
        status = self.service.data_status()
        active = status.get("active")
        if not active:
            onboarding = self.service.onboarding_status()
            source = onboarding.get("source") or {}
            source_kind = source.get("kind") if isinstance(source, dict) else str(source)
            if source_kind == "provider":
                primary = RecoveryActionDTO("import-provider-package", "导入标准数据包", "data", True)
                actions = (
                    RecoveryActionDTO("initialize-baostock", "从 BaoStock 初始化", "data"),
                    RecoveryActionDTO("import-bundled-data", "使用安装包自带数据", "data"),
                    RecoveryActionDTO("choose-data", "重新选择数据来源", "onboarding"),
                    RecoveryActionDTO("import-csv", "改用自己的 CSV", "data"),
                )
                summary = "已选择 Quintara 标准生产数据。请导入安装介质中的数据包，或在可联网环境使用受控更新。"
            elif source_kind == "bundled":
                primary = RecoveryActionDTO("import-bundled-data", "导入安装包自带数据", "data", True)
                actions = (
                    RecoveryActionDTO("initialize-baostock", "从 BaoStock 初始化", "data"),
                    RecoveryActionDTO("choose-data", "重新选择数据来源", "onboarding"),
                    RecoveryActionDTO("import-csv", "选择自己的 CSV", "data"),
                )
                summary = "已选择随应用安装的开发者数据。应用会先核对包内文件大小和 SHA-256，再建立活动数据版本。"
            elif source_kind == "baostock":
                primary = RecoveryActionDTO("initialize-baostock", "从 BaoStock 一键初始化", "data", True)
                actions = (
                    RecoveryActionDTO("import-bundled-data", "离线使用安装包自带数据", "data"),
                    RecoveryActionDTO("import-csv", "选择自己的 CSV", "data"),
                    RecoveryActionDTO("choose-data", "重新选择数据来源", "onboarding"),
                )
                summary = "连接 BaoStock 后会先显示目标交易日、股票池、字段、预计下载量和保存位置；确认后在暂存区构建完整版本。"
            elif source_kind == "csv":
                primary = RecoveryActionDTO("import-csv", "选择并检查 CSV", "data", True)
                actions = (
                    RecoveryActionDTO("initialize-baostock", "从 BaoStock 初始化", "data"),
                    RecoveryActionDTO("import-bundled-data", "使用安装包自带数据", "data"),
                    RecoveryActionDTO("choose-data", "重新选择数据来源", "onboarding"),
                )
                summary = "已选择自己的 CSV。先完成只读检查，通过后才会复制到本机数据仓库。"
            else:
                primary = RecoveryActionDTO("choose-data", "选择数据来源", "onboarding", True)
                actions = (
                    RecoveryActionDTO("import-bundled-data", "使用安装包自带数据", "data"),
                    RecoveryActionDTO("initialize-baostock", "从 BaoStock 初始化", "data"),
                    RecoveryActionDTO("import-csv", "导入 CSV", "data"),
                )
                summary = "可选择安装包自带数据、BaoStock 在线初始化或自己的 CSV，三条路径都在发布前完成校验。"
            return PageDTO(
                key="data",
                title="研究数据",
                eyebrow="本地数据仓库",
                status=PageStatus.EMPTY,
                summary=summary,
                primary_action=primary,
                actions=actions,
            )
        metadata = active.get("metadata") or {}
        route = str(metadata.get("membership_route", "未标记"))
        cards = (
            {"title": "数据版本", "value": active.get("generation", "—"), "tone": "neutral"},
            {"title": "截止日期", "value": active.get("date_max", "—"), "tone": "success"},
            {"title": "覆盖股票", "value": f"{active.get('market_stocks', 0)} 只", "tone": "neutral"},
            {"title": "研究路线", "value": route, "tone": "warning" if route == UniverseMode.NON_PIT_FALLBACK.value else "info"},
            {"title": "占用空间", "value": _bytes(sum(int(item.get("bytes", 0)) for item in active.get("files", {}).values())), "tone": "neutral"},
            {"title": "来源与许可", "value": str(metadata.get("license", active.get("source", "本地导入"))), "tone": "info"},
            {"title": "最近更新", "value": f"BaoStock · {metadata.get('incremental_sessions', 0)} 个交易日" if metadata.get("connector") == "baostock" else "当前来源版本", "tone": "info"},
        )
        return PageDTO(
            key="data",
            title="研究数据",
            eyebrow="活动数据已校验",
            status=PageStatus.READY,
            summary="本地数据已准备完成，可以检查股票池并开始训练。",
            primary_action=RecoveryActionDTO("update-data", "一键更新至最新交易日", "data", True),
            actions=(
                RecoveryActionDTO("import-bundled-data", "重新导入安装包数据", "data"),
                RecoveryActionDTO("import-csv", "导入 CSV", "data"),
            ),
            cards=cards,
            technical=_technical(
                "数据技术详情",
                {
                    "generation": active.get("generation"),
                    "source": active.get("source"),
                    "date_min": active.get("date_min"),
                    "date_max": active.get("date_max"),
                    "files": len(active.get("files", {})),
                    "integrity": "SHA-256 已校验",
                    "local_path": str(self.service.paths.data_generations / str(active.get("generation"))),
                    "difference": status.get("difference"),
                    "derived_from_source": metadata.get("derived_from_source"),
                    "actual_latest_full_session": metadata.get("actual_latest_full_session"),
                    "adjustflag": metadata.get("adjustflag"),
                    "unit_contract": metadata.get("unit_contract"),
                    "checkpoint_identity": metadata.get("checkpoint_identity"),
                },
            ),
        )

    def universes(self) -> PageDTO:
        rows = self.service.universes()
        if not rows:
            return PageDTO(
                key="universe",
                title="股票池",
                eyebrow="研究范围",
                status=PageStatus.EMPTY,
                summary="数据准备完成后，Quintara 会建立匹配的研究股票池。",
                primary_action=RecoveryActionDTO("open-data", "前往数据", "data", True),
            )
        view_rows = []
        for row in rows:
            definition = row.get("definition") or {}
            codes = definition.get("codes", [])
            view_rows.append(
                {
                    "id": row.get("id"),
                    "name": row.get("name"),
                    "mode": row.get("mode"),
                    "count": len(codes),
                    "active": bool(row.get("active")),
                    "status": "可训练" if row.get("mode") != UniverseMode.CUSTOM_UNIVERSE.value or len(codes) >= 100 else "需补足",
                }
            )
        return PageDTO(
            key="universe",
            title="股票池",
            eyebrow="研究范围",
            status=PageStatus.READY,
            summary="同一时刻只有一个活动股票池，模型和结果按股票池隔离。",
            primary_action=RecoveryActionDTO("create-universe", "新建股票池", "universe", True),
            rows=tuple(view_rows),
        )

    def training(self) -> PageDTO:
        data_ready = self.service.data.active_manifest() is not None
        active = self.service.registry.active_universe()
        consent_ready = self.service.consent_status()["status"] == "CONFIRMED"
        gates = (
            {"title": "风险声明", "ready": consent_ready, "text": "已确认" if consent_ready else "等待确认"},
            {"title": "活动数据", "ready": data_ready, "text": "已校验" if data_ready else "等待准备"},
            {"title": "活动股票池", "ready": active is not None, "text": str(active["name"]) if active is not None else "等待选择"},
        )
        ready = all(item["ready"] for item in gates)
        cards = tuple(
            {
                "key": key,
                "title": policy["display_name"],
                "summary": policy["summary"],
                "selected": key == DEFAULT_STRATEGY,
                "version": policy["version"],
            }
            for key, policy in STRATEGY_POLICIES.items()
        )
        return PageDTO(
            key="train",
            title="训练与预测",
            eyebrow="CPU 权威研究路径",
            status=PageStatus.READY if ready else PageStatus.EMPTY,
            summary="准备完成，可以使用稳健平衡策略开始训练。" if ready else "完成下列准备项后即可训练。",
            primary_action=RecoveryActionDTO("start-training", "开始训练", "train", True) if ready else RecoveryActionDTO("complete-setup", "完成准备", "home", True),
            cards=cards,
            rows=gates,
            metadata={"default_strategy": DEFAULT_STRATEGY},
        )

    def results(self, run_id: str | None = None) -> PageDTO:
        runs = self.service.runs(100)
        selected = next((row for row in runs if row.get("id") == run_id), None) if run_id else None
        selected = selected or next(
            (row for row in runs if row.get("state") in {JobState.SUCCEEDED.value, JobState.CACHED.value}),
            None,
        )
        if selected is None:
            return PageDTO(
                key="results",
                title="研究结果",
                eyebrow="Top-5 组合",
                status=PageStatus.EMPTY,
                summary="完成一次训练后，这里会优先展示五只研究组合及其依据。",
                primary_action=RecoveryActionDTO("open-train", "前往训练", "train", True),
            )
        source_run = str(selected["id"])
        if selected.get("state") == JobState.CACHED.value:
            events = self.service.job_events(source_run)
            source_run = str((events[-1].get("context") or {}).get("source_run", source_run)) if events else source_run
        details = self.service.result_details(source_run)
        manifest = details["manifest"]
        explanations = details.get("explanations", {})
        risk = details.get("risk", {})
        rows = tuple(
            {
                "rank": index + 1,
                "name": item.get("name") or item.get("stock_name") or item.get("code_name") or "名称待补充",
                "code": str(item.get("stock_id", "")).zfill(6),
                "exchange": item.get("exchange") or "A股",
                "weight": float(item.get("weight", 0)),
                "score": float(item.get("prediction", 0)),
                "explanation": (
                    f"主要影响：{(explanations.get(str(item.get('stock_id', '')).zfill(6)) or [{}])[0].get('feature', '数据特征')}"
                ),
                "risk": risk.get(str(item.get("stock_id", "")).zfill(6), {}),
                "special_status": (
                    "正常"
                    if str(item.get("status") or item.get("trade_status") or "正常").lower()
                    in {"1", "normal", "正常"}
                    else item.get("status") or item.get("trade_status")
                ),
            }
            for index, item in enumerate(details.get("result_view", []))
        )
        policy = STRATEGY_POLICIES.get(str(manifest.get("strategy", DEFAULT_STRATEGY)), STRATEGY_POLICIES[DEFAULT_STRATEGY])
        notices = [
            {"tone": "info", "text": f"{policy['display_name']}策略：{policy['summary']}"},
            {"tone": "info", "text": "模型评分用于研究排序，不代表收益保证或交易指令。"},
            {"tone": "info", "text": "数据质量：活动 generation、成员区间与模型身份已通过闭包校验。"},
        ]
        if details.get("pit_warning"):
            notices.insert(0, {"tone": "warning", "text": str(details["pit_warning"])})
        return PageDTO(
            key="results",
            title="研究结果",
            eyebrow="Top-5 组合",
            status=PageStatus.READY,
            summary=f"{manifest.get('strategy', DEFAULT_STRATEGY)} 策略 · 数据截止 {manifest.get('provenance', {}).get('data_date_max', '—')}",
            primary_action=RecoveryActionDTO("export-result", "导出 CSV", "results", True),
            rows=rows,
            notices=tuple(notices),
            technical=_technical(
                "数据与模型依据",
                {
                    "run": source_run,
                    "data_generation": manifest.get("data_generation"),
                    "model_generation": manifest.get("model_generation"),
                    "kernel": manifest.get("model_identity", {}).get("kernel_version"),
                    "label": manifest.get("label_contract"),
                    "route": manifest.get("route"),
                    "consent_version": manifest.get("provenance", {}).get("consent_version"),
                },
            ),
        )

    def history(self, *, mode: str | None = None, strategy: str | None = None) -> PageDTO:
        rows = self.service.runs(100)
        view = []
        for row in rows:
            if mode and row.get("mode") != mode:
                continue
            item = dict(row)
            if strategy and item.get("result_generation"):
                try:
                    if self.service.result_manifest(str(item["id"])).get("strategy") != strategy:
                        continue
                except Exception:
                    continue
            view.append(
                {
                    "id": item.get("id"),
                    "state": item.get("state"),
                    "mode": item.get("mode"),
                    "universe": item.get("universe_id"),
                    "updated": item.get("updated_at"),
                    "stage": item.get("stage"),
                }
            )
        return PageDTO(
            key="history",
            title="运行历史",
            eyebrow="本地可追溯记录",
            status=PageStatus.READY if view else PageStatus.EMPTY,
            summary="按日期、股票池、策略和研究路线复查本机运行。" if view else "完成一次训练后会在这里留下可追溯记录。",
            rows=tuple(view),
        )

    def home(self) -> PageDTO:
        data = self.data()
        universe = self.universes()
        train = self.training()
        result_ready = any(
            row.get("state") in {JobState.SUCCEEDED.value, JobState.CACHED.value}
            for row in self.service.runs(1)
        )
        results = PageDTO(
            key="results",
            title="研究结果",
            eyebrow="Top-5 组合",
            status=PageStatus.READY if result_ready else PageStatus.EMPTY,
            summary="最近一次 Top-5 结果已就绪。" if result_ready else "完成一次训练后会在这里展示研究组合。",
        )
        cards = tuple(
            {
                "title": item.title,
                "status": item.status.value,
                "summary": item.summary,
                "target": item.key,
            }
            for item in (data, universe, train, results)
        )
        if data.status == PageStatus.EMPTY:
            primary = data.primary_action or RecoveryActionDTO("choose-data", "选择数据来源", "onboarding", True)
            summary = data.summary or "先选择本地研究数据，Quintara 会引导你完成后续步骤。"
        elif train.status == PageStatus.EMPTY:
            primary = RecoveryActionDTO("complete-setup", "完成训练准备", "train", True)
            summary = "数据已经就绪，继续完成声明和股票池检查。"
        else:
            primary = RecoveryActionDTO("start-training", "开始本周研究", "train", True)
            summary = "所有准备项已就绪，可以开始一次新的本地训练。"
        return PageDTO(
            key="home",
            title="研究工作台",
            eyebrow="本周概览",
            status=PageStatus.READY,
            summary=summary,
            primary_action=primary,
            cards=cards,
            notices=({"tone": "info", "text": "所有数据、模型和结果都保存在本机。"},),
        )

    def page(self, key: str) -> PageDTO:
        providers: dict[str, Callable[[], PageDTO]] = {
            "home": self.home,
            "data": self.data,
            "universe": self.universes,
            "train": self.training,
            "results": self.results,
            "history": self.history,
            "diagnostics": self.environment,
        }
        if key not in providers:
            raise KeyError(f"unknown product page: {key}")
        return providers[key]()
