import ctypes
import ctypes.util
import hashlib
import json
import math
import os

import numpy as np
import pandas as pd

LGBM_FEATURE_COLUMNS = [
    "log_open",
    "log_close",
    "log_volume",
    "log_amount",
    "amplitude",
    "change",
    "turnover",
    "pct_chg",
    "return_1",
    "return_5",
    "return_10",
    "return_20",
    "close_sma5_ratio",
    "close_sma20_ratio",
    "volume_ma5_ratio",
    "volume_ma20_ratio",
    "amount_ma5_ratio",
    "volatility_5",
    "volatility_10",
    "volatility_20",
    "high_low_spread",
    "open_close_spread",
    "intraday_position",
    "turnover_ma5",
    "turnover_ma20",
    "turnover_gap5",
    "reversal_5",
]

LABEL_MODES = {"competition"}


def opencl_platform_count():
    """Return the number of usable OpenCL platforms visible to this process."""
    library = ctypes.util.find_library("OpenCL")
    if not library:
        return 0
    try:
        opencl = ctypes.CDLL(library)
        count = ctypes.c_uint()
        status = opencl.clGetPlatformIDs(0, None, ctypes.byref(count))
    except (AttributeError, OSError):
        return 0
    return int(count.value) if status == 0 else 0


def resolve_lgbm_device_type(model_config=None):
    """Resolve gpu/cpu, with automatic CPU fallback when OpenCL is absent."""
    config = model_config or {}
    requested = os.environ.get(
        "LGBM_DEVICE_TYPE", config.get("lgbm_device_type", "auto")
    )
    requested = str(requested).strip().lower()
    if requested in ("", "auto"):
        return "gpu" if opencl_platform_count() > 0 else "cpu"
    if requested in ("cpu", "none"):
        return "cpu"
    if requested == "gpu":
        if opencl_platform_count() < 1:
            raise RuntimeError(
                "LGBM_DEVICE_TYPE=gpu requested but no OpenCL platform is visible"
            )
        return "gpu"
    raise ValueError(f"Unsupported LGBM device type: {requested}")


def _rolling_mean(series, window):
    return series.rolling(window, min_periods=1).mean()


def _rolling_std(series, window):
    return series.rolling(window, min_periods=2).std().fillna(0.0)


def _reported_return_price_path(open_, close, pct_chg):
    reported_return = (
        pd.to_numeric(pct_chg, errors="coerce")
        .div(100.0)
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
    )
    gross_return = (1.0 + reported_return).clip(lower=1e-6)
    cumulative = gross_return.cumprod()
    if len(cumulative):
        cumulative = cumulative / float(cumulative.iloc[0])
    anchor = max(float(close.iloc[0]), 1e-6) if len(close) else 1.0
    adjusted_close = cumulative * anchor
    intraday_open_ratio = (
        open_.div(close.replace(0.0, np.nan))
        .replace([np.inf, -np.inf], np.nan)
        .fillna(1.0)
    )
    adjusted_open = adjusted_close * intraday_open_ratio
    return adjusted_open, adjusted_close, reported_return


def _discontinuity_adjusted_price_path(open_, close, pct_chg, threshold=0.05):
    raw_open = open_.to_numpy(dtype=np.float64)
    raw_close = close.to_numpy(dtype=np.float64)
    reported = (
        pd.to_numeric(pct_chg, errors="coerce").div(100.0).to_numpy(dtype=np.float64)
    )
    adjusted_open = np.empty(len(raw_open), dtype=np.float64)
    adjusted_close = np.empty(len(raw_close), dtype=np.float64)
    scale = 1.0
    for index in range(len(raw_close)):
        if index > 0 and np.isfinite(reported[index]):
            previous = adjusted_close[index - 1]
            scaled_close = raw_close[index] * scale
            if abs(previous) > 1e-12 and abs(raw_close[index]) > 1e-12:
                observed_return = scaled_close / previous - 1.0
                if abs(observed_return - reported[index]) > threshold:
                    scale = previous * (1.0 + reported[index]) / raw_close[index]
        adjusted_open[index] = raw_open[index] * scale
        adjusted_close[index] = raw_close[index] * scale
    return (
        pd.Series(adjusted_open, index=open_.index),
        pd.Series(adjusted_close, index=close.index),
    )


def _engineer_group(group, price_scale_mode="reported_return", label_mode="competition"):
    group = group.sort_values("日期").copy()
    open_ = group["开盘"].astype(float)
    close = group["收盘"].astype(float)
    high = group["最高"].astype(float)
    low = group["最低"].astype(float)
    volume = group["成交量"].astype(float)
    amount = group["成交额"].astype(float)
    turnover = group["换手率"].astype(float)
    pct_chg = group["涨跌幅"].astype(float)
    amplitude = group["振幅"].astype(float)
    change = group["涨跌额"].astype(float)

    if price_scale_mode == "reported_return":
        feature_open, feature_close, return_1 = _reported_return_price_path(
            open_, close, pct_chg
        )
        feature_change = feature_close.diff().fillna(0.0)
    elif price_scale_mode == "discontinuity_adjusted":
        feature_open, feature_close = _discontinuity_adjusted_price_path(
            open_, close, pct_chg
        )
        feature_change = feature_close.diff().fillna(0.0)
        return_1 = (
            feature_close.pct_change(fill_method=None)
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0.0)
        )
    elif price_scale_mode == "raw":
        feature_open = open_
        feature_close = close
        feature_change = change
        return_1 = (
            close.pct_change(fill_method=None)
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0.0)
        )
    else:
        raise ValueError(f"unsupported lgbm_price_scale_mode={price_scale_mode}")

    return_5 = feature_close.pct_change(5, fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return_10 = feature_close.pct_change(10, fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return_20 = feature_close.pct_change(20, fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)

    sma5 = _rolling_mean(feature_close, 5)
    sma20 = _rolling_mean(feature_close, 20)
    volume_ma5 = _rolling_mean(volume, 5)
    volume_ma20 = _rolling_mean(volume, 20)
    amount_ma5 = _rolling_mean(amount, 5)
    turnover_ma5 = _rolling_mean(turnover, 5)
    turnover_ma20 = _rolling_mean(turnover, 20)

    group["log_open"] = np.log1p(np.maximum(feature_open, 0.0))
    group["log_close"] = np.log1p(np.maximum(feature_close, 0.0))
    group["log_volume"] = np.log1p(np.maximum(volume, 0.0))
    group["log_amount"] = np.log1p(np.maximum(amount, 0.0))
    group["amplitude"] = amplitude
    group["change"] = feature_change
    group["turnover"] = turnover
    group["pct_chg"] = pct_chg
    group["return_1"] = return_1
    group["return_5"] = return_5
    group["return_10"] = return_10
    group["return_20"] = return_20
    group["close_sma5_ratio"] = feature_close / (sma5 + 1e-12) - 1.0
    group["close_sma20_ratio"] = feature_close / (sma20 + 1e-12) - 1.0
    group["volume_ma5_ratio"] = volume / (volume_ma5 + 1e-12) - 1.0
    group["volume_ma20_ratio"] = volume / (volume_ma20 + 1e-12) - 1.0
    group["amount_ma5_ratio"] = amount / (amount_ma5 + 1e-12) - 1.0
    group["volatility_5"] = _rolling_std(return_1, 5)
    group["volatility_10"] = _rolling_std(return_1, 10)
    group["volatility_20"] = _rolling_std(return_1, 20)
    group["high_low_spread"] = (high - low) / (close + 1e-12)
    group["open_close_spread"] = (close - open_) / (open_ + 1e-12)
    group["intraday_position"] = (close - low) / (high - low + 1e-12)
    group["turnover_ma5"] = turnover_ma5
    group["turnover_ma20"] = turnover_ma20
    group["turnover_gap5"] = turnover - turnover_ma5
    group["reversal_5"] = -return_5

    group["open_t1"] = feature_open.shift(-1)
    group["open_t5"] = feature_open.shift(-5)
    group["label_end_date"] = group["日期"].shift(-5)
    valid_prices = (group["open_t1"] > 1e-4) & (group["open_t5"] > 1e-4)
    group["competition_label"] = np.where(
        valid_prices,
        (group["open_t5"] - group["open_t1"]) / (group["open_t1"] + 1e-12),
        np.nan,
    )
    if label_mode not in LABEL_MODES:
        raise ValueError(
            f"unsupported lgbm_label_mode={label_mode}; expected one of {sorted(LABEL_MODES)}"
        )
    group["label"] = group["competition_label"]

    group[LGBM_FEATURE_COLUMNS] = (
        group[LGBM_FEATURE_COLUMNS]
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
    )
    return group


def build_feature_frame(
    df,
    feature_drop=None,
    price_scale_mode="reported_return",
    label_mode="competition",
):
    df = df.copy()
    df["股票代码"] = df["股票代码"].astype(str).str.zfill(6)
    df["日期"] = pd.to_datetime(df["日期"])
    df = df.sort_values(["股票代码", "日期"]).reset_index(drop=True)

    groups = []
    for _, group in df.groupby("股票代码", sort=False):
        groups.append(
            _engineer_group(
                group,
                price_scale_mode=price_scale_mode,
                label_mode=label_mode,
            )
        )
    feature_df = pd.concat(groups, ignore_index=True)
    feature_df["日期"] = pd.to_datetime(feature_df["日期"])
    feature_df["label_end_date"] = pd.to_datetime(feature_df["label_end_date"])
    drop = {str(name) for name in (feature_drop or [])}
    features = [name for name in LGBM_FEATURE_COLUMNS if name not in drop]
    return feature_df, features


def split_train_val_for_lgbm(
    feature_df,
    val_months=6,
    embargo_days=5,
    cutoff_date=None,
):
    feature_df = feature_df.copy()
    feature_df = feature_df.sort_values(["日期", "股票代码"]).reset_index(drop=True)
    feature_df["日期"] = pd.to_datetime(feature_df["日期"], errors="raise")
    feature_df["label_end_date"] = pd.to_datetime(
        feature_df["label_end_date"], errors="coerce"
    )
    last_date = (
        pd.Timestamp(cutoff_date)
        if cutoff_date is not None
        else pd.Timestamp(feature_df["日期"].max())
    )
    if (feature_df["日期"] > last_date).any():
        feature_df = feature_df[feature_df["日期"] <= last_date].copy()
    val_start = (last_date - pd.DateOffset(months=val_months)).normalize()
    all_dates = np.array(sorted(feature_df["日期"].dropna().unique()))
    first_val_pos = int(np.searchsorted(all_dates, np.datetime64(val_start), side="left"))
    train_end_pos = first_val_pos - embargo_days - 1
    if train_end_pos < 0:
        raise ValueError("训练/验证切分失败：验证起点前没有足够的 embargo 交易日")
    train_end_date = pd.Timestamp(all_dates[train_end_pos])

    labeled = feature_df.dropna(subset=["label", "label_end_date"]).copy()
    labeled = labeled[labeled["label_end_date"] <= last_date].copy()
    train_df = labeled[labeled["label_end_date"] <= train_end_date].copy()
    train_df = train_df[train_df["日期"] <= train_end_date].copy()
    val_df = labeled[
        (labeled["日期"] >= val_start)
        & (labeled["日期"] <= last_date)
        & (labeled["label_end_date"] <= last_date)
    ].copy()
    if not train_df.empty and train_df["label_end_date"].max() > train_end_date:
        raise AssertionError("training labels cross the embargo boundary")
    if not val_df.empty and val_df["label_end_date"].max() > last_date:
        raise AssertionError("validation labels cross the cutoff boundary")
    return train_df, val_df, val_start


def _portfolio_returns_from_predictions(frame, pred_col):
    returns = []
    for _, day in frame.groupby("日期", sort=True):
        day = day.sort_values(pred_col, ascending=False).head(5)
        if len(day) < 5:
            continue
        returns.append(float(day["label"].mean()))
    return returns


def evaluate_predictions(frame, pred_col="prediction"):
    returns = _portfolio_returns_from_predictions(frame, pred_col)
    if not returns:
        raise ValueError("验证集没有可用的按日组合收益")
    best = max(returns)
    drop_best = returns.copy()
    drop_best.remove(best)
    return {
        "model_portfolio_return": float(np.mean(returns)),
        "model_portfolio_median": float(np.median(returns)),
        "model_portfolio_min": float(np.min(returns)),
        "positive_count": int(sum(r > 0 for r in returns)),
        "drop_best_mean": float(np.mean(drop_best if drop_best else returns)),
    }


def evaluate_rank_ic(frame, pred_col="prediction", label_col="label", method="spearman"):
    values = []
    for _, day in frame.groupby("日期", sort=True):
        pred = pd.to_numeric(day[pred_col], errors="coerce")
        label = pd.to_numeric(day[label_col], errors="coerce")
        valid = pd.DataFrame({"prediction": pred, "label": label}).dropna()
        if len(valid) < 2:
            continue
        if valid["prediction"].nunique() < 2 or valid["label"].nunique() < 2:
            continue
        corr = valid["prediction"].corr(valid["label"], method=method)
        if pd.notna(corr):
            values.append(float(corr))
    metric_name = f"rank_ic_{method}"
    return {
        metric_name: float(np.mean(values)) if values else 0.0,
        "rank_ic_group_count": int(len(values)),
    }


def evaluate_lgbm_validation_metric(frame, metric_name="portfolio_return", pred_col="prediction"):
    metric_name = str(metric_name or "portfolio_return")
    if metric_name == "portfolio_return":
        value = evaluate_predictions(frame, pred_col=pred_col)["model_portfolio_return"]
        return "model_portfolio_return", float(value), True
    if metric_name == "rank_ic_spearman":
        value = evaluate_rank_ic(frame, pred_col=pred_col, method="spearman")["rank_ic_spearman"]
        return "rank_ic_spearman", float(value), True
    if metric_name == "rank_ic_pearson":
        value = evaluate_rank_ic(frame, pred_col=pred_col, method="pearson")["rank_ic_pearson"]
        return "rank_ic_pearson", float(value), True
    raise ValueError(f"unsupported lgbm_validation_metric={metric_name}")


def compute_time_decay_sample_weight(frame, model_config):
    half_life_days = model_config.get("lgbm_time_decay_half_life_days")
    if half_life_days in (None, "", 0):
        return None
    half_life_days = float(half_life_days)
    if half_life_days <= 0:
        raise ValueError(f"lgbm_time_decay_half_life_days must be positive, got {half_life_days}")
    dates = pd.to_datetime(frame["日期"])
    age_days = (dates.max() - dates).dt.days.astype(np.float64)
    weights = np.power(0.5, age_days / half_life_days).astype(np.float32)
    mean_weight = float(weights.mean())
    if mean_weight <= 0 or not math.isfinite(mean_weight):
        raise ValueError("invalid time-decay sample weights")
    return weights / mean_weight


def _selection_relevance_target(
    frame,
    label_col="label",
    portfolio_size=5,
    relevance_pool_size=20,
):
    labels = pd.to_numeric(frame[label_col], errors="coerce")
    dates = pd.to_datetime(frame["日期"], errors="raise")
    target = pd.Series(index=frame.index, dtype=np.float64)
    portfolio_size = int(portfolio_size)
    relevance_pool_size = int(relevance_pool_size)
    if portfolio_size <= 0 or relevance_pool_size < portfolio_size:
        raise ValueError(
            "invalid relevance cutoffs: "
            f"portfolio_size={portfolio_size}, relevance_pool_size={relevance_pool_size}"
        )
    for _, index in dates.groupby(dates).groups.items():
        values = labels.loc[index]
        # Equal realised returns are economically indistinguishable.  Using
        # ``method="first"`` made CSV/groupby row order an accidental target
        # feature and could change the learned Top-5 model after a harmless
        # permutation.  Average rank keeps the target order-invariant.
        ranks = values.rank(method="average", ascending=False)
        day_target = pd.Series(0.0, index=index, dtype=np.float64)
        day_target.loc[ranks <= relevance_pool_size] = 1.0
        day_target.loc[values > 0.0] = np.maximum(day_target.loc[values > 0.0], 0.5)
        day_target.loc[ranks <= portfolio_size] = 2.0
        if len(day_target) > 1:
            day_target = day_target - float(day_target.mean())
        target.loc[index] = day_target
    return target.to_numpy(dtype=np.float32)


def compute_training_target(frame, model_config):
    labels = _selection_relevance_target(
        frame,
        portfolio_size=model_config.get("portfolio_size", 5),
        relevance_pool_size=model_config.get("relevance_pool_size", 20),
    )
    quantiles = model_config.get("lgbm_label_winsorize_quantiles")
    if quantiles in (None, "", []):
        return labels
    if not isinstance(quantiles, (list, tuple)) or len(quantiles) != 2:
        raise ValueError("lgbm_label_winsorize_quantiles must be a two-value list like [0.01, 0.99]")
    lower_q, upper_q = (float(quantiles[0]), float(quantiles[1]))
    if not (0.0 <= lower_q < upper_q <= 1.0):
        raise ValueError(f"invalid lgbm_label_winsorize_quantiles={quantiles}")
    finite = labels[np.isfinite(labels)]
    if finite.size == 0:
        raise ValueError("cannot winsorize empty or non-finite LGBM labels")
    lower, upper = np.quantile(finite, [lower_q, upper_q])
    return np.clip(labels, lower, upper).astype(np.float32)


def lgbm_device_params(model_config):
    device_type = resolve_lgbm_device_type(model_config)
    if device_type == "cpu":
        return {
            "device_type": "cpu",
            "deterministic": True,
            "force_col_wise": True,
        }
    return {
        "device_type": "gpu",
        "gpu_platform_id": int(model_config.get("lgbm_gpu_platform_id", os.environ.get("LGBM_GPU_PLATFORM_ID", 0))),
        "gpu_device_id": int(model_config.get("lgbm_gpu_device_id", os.environ.get("LGBM_GPU_DEVICE_ID", 0))),
        "max_bin": int(model_config.get("lgbm_max_bin", 255)),
        "gpu_use_dp": bool(model_config.get("lgbm_gpu_use_dp", True)),
    }


def lgbm_seed_params(model_config):
    params = {}
    for config_key, lgbm_key in (
        ("lgbm_bagging_seed", "bagging_seed"),
        ("lgbm_feature_fraction_seed", "feature_fraction_seed"),
        ("lgbm_data_random_seed", "data_random_seed"),
        ("lgbm_extra_seed", "extra_seed"),
        ("lgbm_objective_seed", "objective_seed"),
    ):
        if config_key in model_config:
            params[lgbm_key] = int(model_config[config_key])
    return params


def _import_lightgbm():
    try:
        import lightgbm as lgb
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "lightgbm is required for the LGBM model family. "
            "Install it in the active environment before running train.sh/test.sh."
        ) from exc
    return lgb


def _lgbm_params(model_config):
    params = {
        "objective": "regression",
        "metric": "None",
        "learning_rate": model_config.get("lgbm_learning_rate", 0.04),
        "num_leaves": model_config.get("lgbm_num_leaves", 31),
        "min_data_in_leaf": model_config.get("lgbm_min_data_in_leaf", 200),
        "feature_fraction": model_config.get("lgbm_feature_fraction", 0.8),
        "bagging_fraction": model_config.get("lgbm_bagging_fraction", 0.8),
        "bagging_freq": 1,
        "lambda_l1": model_config.get("lgbm_lambda_l1", 1.0),
        "lambda_l2": model_config.get("lgbm_lambda_l2", 5.0),
        "num_threads": model_config.get("lgbm_num_threads", max(os.cpu_count() - 1, 1)),
        "max_bin": model_config.get("lgbm_max_bin", 255),
        "seed": model_config.get("seed", 42),
        "verbosity": model_config.get("lgbm_verbosity", -1),
    }
    params.update(lgbm_seed_params(model_config))
    params.update(lgbm_device_params(model_config))
    return params


def train_regressor(train_df, val_df, features, model_config):
    lgb = _import_lightgbm()
    train_matrix = train_df[features].to_numpy(dtype=np.float32)
    train_label = compute_training_target(train_df, model_config)
    val_matrix = val_df[features].to_numpy(dtype=np.float32)
    val_label = val_df["label"].to_numpy(dtype=np.float32)
    train_weight = compute_time_decay_sample_weight(train_df, model_config)

    dtrain = lgb.Dataset(train_matrix, label=train_label, weight=train_weight, feature_name=features)
    dvalid = lgb.Dataset(val_matrix, label=val_label, feature_name=features, reference=dtrain)
    val_dates = val_df["日期"].to_numpy()
    validation_metric = model_config.get("lgbm_validation_metric", "portfolio_return")

    def validation_eval(preds, dataset):
        frame = pd.DataFrame(
            {
                "日期": val_dates,
                "prediction": preds,
                "label": dataset.get_label(),
            }
        )
        return evaluate_lgbm_validation_metric(frame, metric_name=validation_metric, pred_col="prediction")

    params = _lgbm_params(model_config)
    selection_mode = str(model_config.get("lgbm_selection_mode", "early_stopping"))
    if selection_mode not in {"early_stopping", "fixed_rounds"}:
        raise ValueError(f"unsupported lgbm_selection_mode={selection_mode}")
    selected_rounds = int(
        model_config.get(
            "lgbm_fixed_rounds" if selection_mode == "fixed_rounds" else "lgbm_num_boost_round",
            120,
        )
    )
    if selected_rounds <= 0:
        raise ValueError("selected LightGBM round count must be positive")
    callbacks = [lgb.log_evaluation(period=model_config.get("lgbm_log_period", 1))]
    if selection_mode == "early_stopping":
        callbacks.insert(0, lgb.early_stopping(model_config.get("lgbm_early_stopping_rounds", 20), verbose=True))
    booster = lgb.train(
        params,
        dtrain,
        num_boost_round=selected_rounds,
        valid_sets=[dvalid],
        valid_names=["valid"],
        feval=validation_eval,
        callbacks=callbacks,
    )

    best_iteration = int(booster.best_iteration or selected_rounds)
    val_pred = booster.predict(val_matrix, num_iteration=best_iteration)
    val_frame = val_df[["日期", "股票代码", "label"]].copy()
    val_frame["prediction"] = val_pred
    metrics = evaluate_predictions(val_frame, pred_col="prediction")
    metrics.update(evaluate_rank_ic(val_frame, pred_col="prediction", method="spearman"))
    metrics.update(evaluate_rank_ic(val_frame, pred_col="prediction", method="pearson"))
    metrics["lgbm_validation_metric"] = str(validation_metric)
    metrics["best_iteration"] = best_iteration
    metrics["selection_mode"] = selection_mode
    metrics["selection_train_rows"] = int(len(train_df))
    metrics["validation_rows"] = int(len(val_df))
    return booster, metrics, val_frame


def fit_regressor_fixed_rounds(training_df, features, model_config, num_boost_round):
    """Fit the production model on every known label after early stopping."""
    lgb = _import_lightgbm()
    rounds = int(num_boost_round)
    if rounds <= 0:
        raise ValueError(f"num_boost_round must be positive, got {rounds}")
    matrix = training_df[features].to_numpy(dtype=np.float32)
    labels = compute_training_target(training_df, model_config)
    weights = compute_time_decay_sample_weight(training_df, model_config)
    dataset = lgb.Dataset(matrix, label=labels, weight=weights, feature_name=features)
    booster = lgb.train(
        _lgbm_params(model_config),
        dataset,
        num_boost_round=rounds,
        callbacks=[lgb.log_evaluation(period=model_config.get("lgbm_log_period", 0))],
    )
    return booster


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_input_files(data_dir, manifest_path):
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    for file_name, metadata in manifest["files"].items():
        path = os.path.join(data_dir, file_name)
        digest = str(metadata["sha256"])
        actual = file_sha256(path)
        if actual != digest:
            raise ValueError(f"input hash mismatch: {path}: {actual} != {digest}")


def strict_train_val_split(feature_frame, cutoff, model_config):
    train, validation, _ = split_train_val_for_lgbm(
        feature_frame,
        val_months=int(model_config.get("val_months", 6)),
        embargo_days=int(model_config.get("label_embargo_days", 5)),
    )
    cutoff = pd.Timestamp(cutoff).normalize()
    train = train[train["label_end_date"] <= cutoff].copy()
    validation = validation[validation["label_end_date"] <= cutoff].copy()
    if train.empty or validation.empty:
        raise ValueError("strict train/validation split is empty")
    return train, validation


def all_known_labeled_rows(feature_frame, cutoff):
    cutoff = pd.Timestamp(cutoff).normalize()
    rows = feature_frame.dropna(subset=["label", "label_end_date"]).copy()
    rows = rows[
        (rows["日期"] <= cutoff)
        & (pd.to_datetime(rows["label_end_date"], errors="coerce") <= cutoff)
    ].copy()
    if rows.empty:
        raise ValueError("no known labeled rows are available for final fitting")
    return rows.sort_values(["日期", "股票代码"]).reset_index(drop=True)


def prediction_rows_at_cutoff(feature_frame, cutoff):
    rows = feature_frame[feature_frame["日期"] == pd.Timestamp(cutoff).normalize()].copy()
    if rows.empty or not rows["股票代码"].is_unique:
        raise ValueError("invalid exact-cutoff prediction rows")
    return rows.sort_values("股票代码").reset_index(drop=True)


def predict_ranking(booster, rows, features):
    best_iteration = int(getattr(booster, "best_iteration", 0) or 0)
    scores = booster.predict(
        rows[features].to_numpy(dtype=np.float32),
        num_iteration=best_iteration if best_iteration > 0 else booster.num_trees(),
    )
    ranking = pd.DataFrame({
        "stock_id": rows["股票代码"].astype(str).str.zfill(6),
        "prediction": scores,
    })
    ranking["predicted_rank"] = ranking["prediction"].rank(
        method="average", ascending=False
    )
    # Stock ID is only a stable presentation order.  It is never consulted
    # when comparing the fifth and sixth portfolio rows.
    ranking = ranking.sort_values(
        ["prediction", "stock_id"], ascending=[False, True], kind="mergesort"
    ).reset_index(drop=True)
    return ranking


def build_portfolio(ranking, config):
    ranked_stocks = ranking.sort_values(
        ["prediction", "stock_id"], ascending=[False, True], kind="mergesort"
    ).reset_index(drop=True)
    portfolio_size = int(config.get("portfolio_size", 5))
    if len(ranked_stocks) <= portfolio_size:
        raise ValueError("portfolio ranking requires at least six cutoff rows")
    selected_scores = ranked_stocks.head(portfolio_size)["prediction"].to_numpy(dtype=float)
    if any(
        np.isclose(selected_scores[index], selected_scores[index + 1], rtol=0.0, atol=1e-12)
        for index in range(len(selected_scores) - 1)
    ):
        raise ValueError("unresolved prediction tie inside portfolio selection")
    if np.isclose(
        float(ranked_stocks.iloc[portfolio_size - 1]["prediction"]),
        float(ranked_stocks.iloc[portfolio_size]["prediction"]),
        rtol=0.0,
        atol=1e-12,
    ):
        raise ValueError("unresolved prediction tie at the portfolio boundary")
    ranked_stocks["portfolio_score"] = ranked_stocks["prediction"]
    result = ranked_stocks.head(portfolio_size)[["stock_id"]].copy()
    result["weight"] = [float(value) for value in config["portfolio_rank_weights"]]
    return result, ranked_stocks


def validate_result(result, eligible_stocks=None):
    if list(result.columns) != ["stock_id", "weight"]:
        raise ValueError("result columns must be stock_id,weight")
    normalized = result.copy()
    normalized["stock_id"] = normalized["stock_id"].astype(str).str.zfill(6)
    if not normalized["stock_id"].str.fullmatch(r"\d{6}").all():
        raise ValueError("result stock_id must be exactly six digits")
    if not 0 < len(normalized) <= 5 or not normalized["stock_id"].is_unique:
        raise ValueError("result must contain 1-5 distinct stocks")
    weights = pd.to_numeric(normalized["weight"], errors="raise")
    if not np.isfinite(weights).all() or (weights <= 0).any() or float(weights.sum()) > 1.0 + 1e-12:
        raise ValueError("result weights are invalid")
    if eligible_stocks is not None:
        eligible = {str(value).zfill(6) for value in eligible_stocks}
        if len(eligible) != 300:
            raise ValueError(f"eligible cutoff universe must contain 300 stocks, got {len(eligible)}")
        if not set(normalized["stock_id"]).issubset(eligible):
            raise ValueError("result contains a stock outside the cutoff universe")
    return normalized
