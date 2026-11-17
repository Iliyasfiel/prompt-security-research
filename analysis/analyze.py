#!/usr/bin/env python3
"""Analyze completed Agent security runs from a JSONL file.

The script intentionally keeps completed model behavior in every primary-rate
denominator. Only infrastructure/protocol failures are excluded from those
rates, and they are reported separately.
"""

from __future__ import annotations

import argparse
import csv
import ctypes
import json
import math
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np


VALID_KINDS = ("attack", "benign", "extraction")
KNOWLEDGE_LEVELS = ("K0", "K75", "K100")
DEFENSES = ("D0", "Dgate")
VALID_STATUSES = ("completed", "technical_error", "protocol_invalid")
WILSON_Z = 1.959963984540054
DEFAULT_SEED = 20261117
DEFAULT_BOOTSTRAP_ITERATIONS = 10_000
_WINDOWS_RUNTIME_HANDLES: list[Any] = []

KIND_ORDER = {kind: index for index, kind in enumerate(VALID_KINDS)}
KNOWLEDGE_ORDER = {knowledge: index for index, knowledge in enumerate(KNOWLEDGE_LEVELS)}
DEFENSE_ORDER = {defense: index for index, defense in enumerate(DEFENSES)}

COUNT_COLUMNS = (
    "scope",
    "config_id",
    "kind",
    "knowledge",
    "defense",
    "total_runs",
    "completed",
    "technical_error",
    "protocol_invalid",
    "other_status",
    "invalid_total",
    "attempt_violation_true",
    "attempt_violation_false",
    "attempt_violation_missing",
    "attempt_violation_rate",
    "attempt_violation_wilson_low",
    "attempt_violation_wilson_high",
    "executed_violation_true",
    "executed_violation_false",
    "executed_violation_missing",
    "executed_violation_rate",
    "executed_violation_wilson_low",
    "executed_violation_wilson_high",
    "benign_task_success_true",
    "benign_task_success_false",
    "benign_task_success_missing",
    "benign_task_success_rate",
    "benign_task_success_wilson_low",
    "benign_task_success_wilson_high",
    "extraction_with_fact_recall",
    "fact_recall_mean",
    "extraction_with_random_fact_recall",
    "random_fact_recall_mean",
    "completed_with_tokens_in",
    "sum_tokens_in",
    "mean_tokens_in",
    "completed_with_tokens_out",
    "sum_tokens_out",
    "mean_tokens_out",
    "completed_with_duration_seconds",
    "sum_duration_seconds",
    "mean_duration_seconds",
)


@dataclass(frozen=True)
class RunRecord:
    line_no: int
    row: dict[str, Any]


def identifier(value: Any) -> str:
    """Return a stable, non-empty identifier for grouping and output."""
    if value is None:
        return "missing"
    text = str(value).strip()
    return text if text else "missing"


def normalize_kind(value: Any) -> str:
    text = identifier(value).lower()
    aliases = {
        "attack": "attack",
        "benign": "benign",
        "extraction": "extraction",
    }
    return aliases.get(text, text)


def normalize_knowledge(value: Any) -> str:
    text = identifier(value).upper()
    return text if text in KNOWLEDGE_LEVELS else text


def normalize_defense(value: Any) -> str:
    text = identifier(value)
    lower_to_canonical = {"d0": "D0", "dgate": "Dgate"}
    return lower_to_canonical.get(text.lower(), text)


def normalize_status(value: Any) -> str:
    return identifier(value).lower()


def record_kind(record: RunRecord) -> str:
    return normalize_kind(record.row.get("kind"))


def record_knowledge(record: RunRecord) -> str:
    return normalize_knowledge(record.row.get("knowledge"))


def record_defense(record: RunRecord) -> str:
    return normalize_defense(record.row.get("defense"))


def record_config(record: RunRecord) -> str:
    return identifier(record.row.get("config_id"))


def record_status(record: RunRecord) -> str:
    return normalize_status(record.row.get("status"))


def finite_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def as_behavior_success(value: Any) -> tuple[int, bool]:
    """Map a completed outcome to 0/1 while flagging malformed/missing values."""
    if value is True:
        return 1, False
    if value is False:
        return 0, False
    return 0, True


def wilson_interval(successes: int, total: int, z: float = WILSON_Z) -> tuple[float, float] | None:
    """Compute a single-condition Wilson interval for a binomial proportion."""
    if total <= 0:
        return None
    p = successes / total
    denominator = 1.0 + z * z / total
    center = (p + z * z / (2.0 * total)) / denominator
    half_width = z * math.sqrt(
        (p * (1.0 - p) + z * z / (4.0 * total)) / total
    ) / denominator
    return max(0.0, center - half_width), min(1.0, center + half_width)


def rounded(value: float | None, digits: int = 6) -> float | None:
    return None if value is None else round(float(value), digits)


def prepare_windows_plot_runtime() -> None:
    """Expose existing Conda DLL directories before importing Matplotlib on Windows."""
    if os.name != "nt":
        return
    library_bin = Path(sys.prefix) / "Library" / "bin"
    if library_bin.is_dir():
        os.environ["PATH"] = str(library_bin) + os.pathsep + os.environ.get("PATH", "")
        if hasattr(os, "add_dll_directory"):
            _WINDOWS_RUNTIME_HANDLES.append(os.add_dll_directory(str(library_bin)))

    openjpeg_candidates = [
        *(Path(sys.prefix) / "Library" / "bin").glob("openjp2.dll"),
        *(Path(sys.prefix) / "pkgs").glob("*/Library/bin/openjp2.dll"),
    ]
    for candidate in sorted(openjpeg_candidates):
        try:
            _WINDOWS_RUNTIME_HANDLES.append(ctypes.WinDLL(str(candidate)))
            break
        except OSError:
            continue


def percent(value: float | None) -> str:
    return "—" if value is None else f"{100.0 * value:.1f}%"


def percentage_points(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f} 个百分点"


def format_interval(
    successes: int,
    total: int,
    *,
    as_percent: bool = True,
) -> str:
    interval = wilson_interval(successes, total)
    if interval is None:
        return "—"
    low, high = interval
    if as_percent:
        return f"{100.0 * low:.1f}%–{100.0 * high:.1f}%"
    return f"{low:.3f}–{high:.3f}"


def read_jsonl(path: Path) -> tuple[list[RunRecord], dict[str, Any]]:
    records: list[RunRecord] = []
    malformed: list[dict[str, Any]] = []
    blank_lines = 0
    physical_lines = 0

    with path.open("r", encoding="utf-8-sig") as handle:
        for line_no, line in enumerate(handle, start=1):
            physical_lines += 1
            if not line.strip():
                blank_lines += 1
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                malformed.append(
                    {
                        "line": line_no,
                        "error": f"{exc.msg} (column {exc.colno})",
                    }
                )
                continue
            if not isinstance(payload, dict):
                malformed.append(
                    {
                        "line": line_no,
                        "error": "JSON value is not an object",
                    }
                )
                continue
            records.append(RunRecord(line_no=line_no, row=payload))

    file_stats = {
        "physical_lines": physical_lines,
        "nonblank_lines": physical_lines - blank_lines,
        "blank_lines": blank_lines,
        "parsed_records": len(records),
        "malformed_count": len(malformed),
        "malformed_json_lines": malformed,
    }
    return records, file_stats


def status_summary(records: Sequence[RunRecord]) -> dict[str, Any]:
    exact = Counter(record_status(record) for record in records)
    technical_error = exact.get("technical_error", 0)
    protocol_invalid = exact.get("protocol_invalid", 0)
    completed = exact.get("completed", 0)
    other_status = sum(
        count
        for status, count in exact.items()
        if status not in VALID_STATUSES
    )
    return {
        "total_runs": len(records),
        "completed": completed,
        "technical_error": technical_error,
        "protocol_invalid": protocol_invalid,
        "other_status": other_status,
        "invalid_total": len(records) - completed,
        "by_status": dict(sorted(exact.items())),
    }


def flag_summary(records: Sequence[RunRecord], field: str) -> dict[str, Any]:
    completed = [record for record in records if record_status(record) == "completed"]
    true_count = 0
    false_count = 0
    missing_count = 0
    for record in completed:
        value = record.row.get(field)
        if value is True:
            true_count += 1
        elif value is False:
            false_count += 1
        else:
            missing_count += 1

    denominator = len(completed)
    rate = true_count / denominator if denominator else None
    interval = wilson_interval(true_count, denominator)
    return {
        "denominator": denominator,
        "true": true_count,
        "false": false_count,
        "missing": missing_count,
        "rate": rate,
        "wilson_95": (
            {"low": interval[0], "high": interval[1]}
            if interval is not None
            else None
        ),
    }


def numeric_summary(records: Sequence[RunRecord], field: str) -> dict[str, Any]:
    completed = [record for record in records if record_status(record) == "completed"]
    values = [
        number
        for record in completed
        if (number := finite_number(record.row.get(field))) is not None
    ]
    return {
        "valid_count": len(values),
        "missing_count": len(completed) - len(values),
        "sum": sum(values) if values else None,
        "mean": sum(values) / len(values) if values else None,
        "minimum": min(values) if values else None,
        "maximum": max(values) if values else None,
    }


def sort_group_key(scope: str, kind: str, knowledge: str, defense: str, config_id: str) -> tuple:
    return (
        0 if scope == "aggregate" else 1,
        KIND_ORDER.get(kind, len(KIND_ORDER)),
        kind,
        KNOWLEDGE_ORDER.get(knowledge, len(KNOWLEDGE_ORDER)),
        knowledge,
        DEFENSE_ORDER.get(defense, len(DEFENSE_ORDER)),
        defense,
        config_id,
    )


def build_count_rows(records: Sequence[RunRecord]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[RunRecord]] = defaultdict(list)
    for record in records:
        key = (record_kind(record), record_knowledge(record), record_defense(record))
        grouped[key].append(record)

    rows: list[dict[str, Any]] = []
    for (kind, knowledge, defense), group_records in grouped.items():
        config_groups: dict[str, list[RunRecord]] = defaultdict(list)
        for record in group_records:
            config_groups[record_config(record)].append(record)

        for scope, config_id, subset in (
            ("aggregate", "", group_records),
            *[
                ("config", current_config, config_records)
                for current_config, config_records in config_groups.items()
            ],
        ):
            statuses = status_summary(subset)
            attempt = flag_summary(subset, "attempt_violation")
            executed = flag_summary(subset, "executed_violation")
            benign_success = flag_summary(subset, "benign_task_success")
            fact_recall = numeric_summary(subset, "fact_recall")
            random_fact_recall = numeric_summary(subset, "random_fact_recall")
            tokens_in = numeric_summary(subset, "tokens_in")
            tokens_out = numeric_summary(subset, "tokens_out")
            duration = numeric_summary(subset, "duration_seconds")

            row: dict[str, Any] = {
                "scope": scope,
                "config_id": config_id,
                "kind": kind,
                "knowledge": knowledge,
                "defense": defense,
                "total_runs": statuses["total_runs"],
                "completed": statuses["completed"],
                "technical_error": statuses["technical_error"],
                "protocol_invalid": statuses["protocol_invalid"],
                "other_status": statuses["other_status"],
                "invalid_total": statuses["invalid_total"],
                "attempt_violation_true": attempt["true"],
                "attempt_violation_false": attempt["false"],
                "attempt_violation_missing": attempt["missing"],
                "attempt_violation_rate": rounded(attempt["rate"]),
                "attempt_violation_wilson_low": rounded(
                    None if attempt["wilson_95"] is None else attempt["wilson_95"]["low"]
                ),
                "attempt_violation_wilson_high": rounded(
                    None if attempt["wilson_95"] is None else attempt["wilson_95"]["high"]
                ),
                "executed_violation_true": executed["true"],
                "executed_violation_false": executed["false"],
                "executed_violation_missing": executed["missing"],
                "executed_violation_rate": rounded(executed["rate"]),
                "executed_violation_wilson_low": rounded(
                    None if executed["wilson_95"] is None else executed["wilson_95"]["low"]
                ),
                "executed_violation_wilson_high": rounded(
                    None if executed["wilson_95"] is None else executed["wilson_95"]["high"]
                ),
                "benign_task_success_true": benign_success["true"],
                "benign_task_success_false": benign_success["false"],
                "benign_task_success_missing": benign_success["missing"],
                "benign_task_success_rate": rounded(benign_success["rate"]),
                "benign_task_success_wilson_low": rounded(
                    None
                    if benign_success["wilson_95"] is None
                    else benign_success["wilson_95"]["low"]
                ),
                "benign_task_success_wilson_high": rounded(
                    None
                    if benign_success["wilson_95"] is None
                    else benign_success["wilson_95"]["high"]
                ),
                "extraction_with_fact_recall": fact_recall["valid_count"],
                "fact_recall_mean": rounded(fact_recall["mean"]),
                "extraction_with_random_fact_recall": random_fact_recall["valid_count"],
                "random_fact_recall_mean": rounded(random_fact_recall["mean"]),
                "completed_with_tokens_in": tokens_in["valid_count"],
                "sum_tokens_in": rounded(tokens_in["sum"]),
                "mean_tokens_in": rounded(tokens_in["mean"]),
                "completed_with_tokens_out": tokens_out["valid_count"],
                "sum_tokens_out": rounded(tokens_out["sum"]),
                "mean_tokens_out": rounded(tokens_out["mean"]),
                "completed_with_duration_seconds": duration["valid_count"],
                "sum_duration_seconds": rounded(duration["sum"]),
                "mean_duration_seconds": rounded(duration["mean"]),
            }
            rows.append(row)

    rows.sort(
        key=lambda row: sort_group_key(
            row["scope"],
            row["kind"],
            row["knowledge"],
            row["defense"],
            row["config_id"],
        )
    )
    return rows


def metric_condition_rows(
    records: Sequence[RunRecord],
    kind: str,
    fields: Sequence[str],
    *,
    per_config: bool,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[RunRecord]] = defaultdict(list)
    for record in records:
        if record_kind(record) != kind:
            continue
        config_id = record_config(record) if per_config else ""
        key = (config_id, record_knowledge(record), record_defense(record))
        grouped[key].append(record)

    result: list[dict[str, Any]] = []
    for (config_id, knowledge, defense), subset in grouped.items():
        statuses = status_summary(subset)
        row: dict[str, Any] = {
            "config_id": config_id if per_config else None,
            "knowledge": knowledge,
            "defense": defense,
            **statuses,
        }
        for field in fields:
            summary = flag_summary(subset, field)
            row[field] = {
                "numerator": summary["true"],
                "denominator": summary["denominator"],
                "false": summary["false"],
                "missing_outcome": summary["missing"],
                "rate": rounded(summary["rate"]),
                "wilson_95": (
                    {
                        "low": rounded(summary["wilson_95"]["low"]),
                        "high": rounded(summary["wilson_95"]["high"]),
                    }
                    if summary["wilson_95"] is not None
                    else None
                ),
            }
        result.append(row)

    result.sort(
        key=lambda row: sort_group_key(
            "config" if per_config else "aggregate",
            kind,
            row["knowledge"],
            row["defense"],
            row["config_id"] or "",
        )
    )
    return result


def pair_key_details(key: tuple[str, str, str, str, str]) -> dict[str, str]:
    return {
        "config_id": key[0],
        "template": key[1],
        "goal": key[2],
        "repeat": key[3],
        "defense": key[4],
    }


def binary_outcome(record: RunRecord, field: str) -> tuple[int, bool]:
    return as_behavior_success(record.row.get(field))


def pair_effect_stats(
    pairs: Sequence[tuple[RunRecord, RunRecord]],
) -> dict[str, Any]:
    result: dict[str, Any] = {"complete_pairs": len(pairs)}
    for metric in ("attempt_violation", "executed_violation"):
        k0_values: list[int] = []
        k100_values: list[int] = []
        missing_k0 = 0
        missing_k100 = 0
        for k0_record, k100_record in pairs:
            k0_value, k0_missing = binary_outcome(k0_record, metric)
            k100_value, k100_missing = binary_outcome(k100_record, metric)
            k0_values.append(k0_value)
            k100_values.append(k100_value)
            missing_k0 += int(k0_missing)
            missing_k100 += int(k100_missing)
        n_pairs = len(pairs)
        k0_rate = sum(k0_values) / n_pairs if n_pairs else None
        k100_rate = sum(k100_values) / n_pairs if n_pairs else None
        difference = (
            (sum(k100_values) - sum(k0_values)) / n_pairs if n_pairs else None
        )
        result[metric] = {
            "k0_rate": rounded(k0_rate),
            "k100_rate": rounded(k100_rate),
            "risk_difference_k100_minus_k0_pp": (
                None if difference is None else rounded(100.0 * difference)
            ),
            "k0_numerator": sum(k0_values),
            "k100_numerator": sum(k100_values),
            "denominator": n_pairs,
            "missing_k0_outcome": missing_k0,
            "missing_k100_outcome": missing_k100,
        }
    return result


def bootstrap_config_clusters(
    config_stats: Sequence[dict[str, Any]],
    iterations: int,
    seed: int,
) -> dict[str, Any]:
    if not config_stats:
        return {
            "available": False,
            "reason": "没有同时包含 completed K0 与 K100 的配置簇",
        }

    attempt_effects = np.asarray(
        [
            stat["attempt_violation"]["risk_difference_k100_minus_k0_pp"]
            for stat in config_stats
        ],
        dtype=float,
    )
    executed_effects = np.asarray(
        [
            stat["executed_violation"]["risk_difference_k100_minus_k0_pp"]
            for stat in config_stats
        ],
        dtype=float,
    )
    rng = np.random.default_rng(seed)
    cluster_count = len(config_stats)
    indices = rng.integers(0, cluster_count, size=(iterations, cluster_count))
    attempt_draws = attempt_effects[indices].mean(axis=1)
    executed_draws = executed_effects[indices].mean(axis=1)

    def interval(values: np.ndarray) -> list[float]:
        low, high = np.quantile(values, [0.025, 0.975])
        return [round(float(low), 6), round(float(high), 6)]

    cluster_ids = [stat["config_id"] for stat in config_stats]
    instability: str | None = None
    if cluster_count == 4:
        instability = (
            "仅 4 个配置簇，cluster bootstrap 区间容易不稳定；"
            "区间只用于描述重采样波动。"
        )
    elif cluster_count < 10:
        instability = (
            f"仅 {cluster_count} 个配置簇，cluster bootstrap 区间可能不稳定；"
            "区间只用于描述重采样波动。"
        )

    return {
        "available": True,
        "estimator": "配置内完整配对差异的跨配置等权平均",
        "resampling_unit": "config_id",
        "config_clusters": cluster_ids,
        "config_cluster_count": cluster_count,
        "iterations": iterations,
        "seed": seed,
        "interval_method": "percentile",
        "interval_level": 0.95,
        "attempt_violation": {
            "point_estimate_pp": round(float(attempt_effects.mean()), 6),
            "ci_95_pp": interval(attempt_draws),
            "cluster_effects_pp": [
                round(float(value), 6) for value in attempt_effects
            ],
        },
        "executed_violation": {
            "point_estimate_pp": round(float(executed_effects.mean()), 6),
            "ci_95_pp": interval(executed_draws),
            "cluster_effects_pp": [
                round(float(value), 6) for value in executed_effects
            ],
        },
        "instability_note": instability,
    }


def compute_pairing(
    records: Sequence[RunRecord],
    bootstrap_iterations: int,
    seed: int,
) -> dict[str, Any]:
    pair_fields = ("config_id", "template", "goal", "repeat", "defense")
    candidates: dict[
        tuple[str, str, str, str, str],
        dict[str, list[RunRecord]],
    ] = defaultdict(lambda: {"K0": [], "K100": []})
    key_errors: list[dict[str, Any]] = []

    for record in records:
        if record_kind(record) != "attack" or record_defense(record) != "D0":
            continue
        knowledge = record_knowledge(record)
        if knowledge not in ("K0", "K100"):
            continue
        values = tuple(identifier(record.row.get(field)) for field in pair_fields)
        if "missing" in values:
            key_errors.append(
                {
                    "line": record.line_no,
                    "knowledge": knowledge,
                    "missing_fields": [
                        field
                        for field, value in zip(pair_fields, values)
                        if value == "missing"
                    ],
                }
            )
            continue
        candidates[values][knowledge].append(record)

    complete_pairs: list[tuple[RunRecord, RunRecord]] = []
    unpaired_keys: list[dict[str, Any]] = []
    config_report: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "candidate_pair_count": 0,
            "complete_pair_count": 0,
            "missing_k0_count": 0,
            "missing_k100_count": 0,
            "duplicate_or_conflict_count": 0,
        }
    )

    for key, groups in candidates.items():
        current_config = key[0]
        config_report[current_config]["candidate_pair_count"] += 1
        completed_k0 = sorted(
            (
                record
                for record in groups["K0"]
                if record_status(record) == "completed"
            ),
            key=lambda record: record.line_no,
        )
        completed_k100 = sorted(
            (
                record
                for record in groups["K100"]
                if record_status(record) == "completed"
            ),
            key=lambda record: record.line_no,
        )
        reasons: list[str] = []
        if not completed_k0:
            reasons.append("missing_completed_k0")
            config_report[current_config]["missing_k0_count"] += 1
        if not completed_k100:
            reasons.append("missing_completed_k100")
            config_report[current_config]["missing_k100_count"] += 1
        if len(completed_k0) > 1:
            reasons.append("duplicate_completed_k0")
        if len(completed_k100) > 1:
            reasons.append("duplicate_completed_k100")
        if len(completed_k0) > 1 or len(completed_k100) > 1:
            config_report[current_config]["duplicate_or_conflict_count"] += 1

        if reasons:
            unpaired_keys.append(
                {
                    **pair_key_details(key),
                    "reasons": reasons,
                    "completed_k0_count": len(completed_k0),
                    "completed_k100_count": len(completed_k100),
                }
            )
            continue

        complete_pairs.append((completed_k0[0], completed_k100[0]))
        config_report[current_config]["complete_pair_count"] += 1

    pairs_by_config: dict[
        str,
        list[tuple[RunRecord, RunRecord]],
    ] = defaultdict(list)
    for k0_record, k100_record in complete_pairs:
        pairs_by_config[record_config(k0_record)].append((k0_record, k100_record))

    config_stats: list[dict[str, Any]] = []
    for config_id in sorted(pairs_by_config):
        stats = pair_effect_stats(pairs_by_config[config_id])
        config_stats.append({"config_id": config_id, **stats})

    all_pair_stats = pair_effect_stats(complete_pairs)
    config_rows = [
        {
            "config_id": config_id,
            **config_report[config_id],
        }
        for config_id in sorted(config_report)
    ]

    return {
        "comparison": "D0 下 K100 - K0",
        "primary_metric": "attempt_violation",
        "secondary_metric": "executed_violation",
        "pair_key_fields": list(pair_fields),
        "only_completed_pairs_used": True,
        "candidate_pair_count": len(candidates),
        "complete_pair_count": len(complete_pairs),
        "unpaired_pair_count": len(unpaired_keys),
        "key_error_count": len(key_errors),
        "key_errors": key_errors,
        "complete_pair_outcome_summary": all_pair_stats,
        "config_stats": config_stats,
        "config_pairing_report": config_rows,
        "unpaired_pair_keys": unpaired_keys,
        "bootstrap": bootstrap_config_clusters(
            config_stats,
            iterations=bootstrap_iterations,
            seed=seed,
        ),
    }


def extraction_metric_values(
    records: Sequence[RunRecord],
    field: str,
) -> list[float]:
    return [
        number
        for record in records
        if record_status(record) == "completed"
        and (number := finite_number(record.row.get(field))) is not None
    ]


def extraction_group_summary(records: Sequence[RunRecord]) -> list[dict[str, Any]]:
    completed_records = [
        record for record in records if record_status(record) == "completed"
    ]
    grouped: dict[tuple[str, str, str, str], list[RunRecord]] = defaultdict(list)
    for record in completed_records:
        strategy = identifier(record.row.get("strategy"))
        key = (
            record_config(record),
            record_knowledge(record),
            record_defense(record),
            strategy,
        )
        grouped[key].append(record)

    rows: list[dict[str, Any]] = []
    for (config_id, knowledge, defense, strategy), subset in grouped.items():
        fact_values = extraction_metric_values(subset, "fact_recall")
        random_values = extraction_metric_values(subset, "random_fact_recall")
        paired_gaps: list[float] = []
        missing_fact = 0
        missing_random = 0
        for record in subset:
            fact = finite_number(record.row.get("fact_recall"))
            random_value = finite_number(record.row.get("random_fact_recall"))
            missing_fact += int(fact is None)
            missing_random += int(random_value is None)
            if fact is not None and random_value is not None:
                paired_gaps.append(fact - random_value)
        rows.append(
            {
                "config_id": config_id,
                "knowledge": knowledge,
                "defense": defense,
                "strategy": strategy,
                "completed": len(subset),
                "fact_recall_n": len(fact_values),
                "fact_recall_missing": missing_fact,
                "fact_recall_mean": (
                    rounded(sum(fact_values) / len(fact_values))
                    if fact_values
                    else None
                ),
                "random_fact_recall_n": len(random_values),
                "random_fact_recall_missing": missing_random,
                "random_fact_recall_mean": (
                    rounded(sum(random_values) / len(random_values))
                    if random_values
                    else None
                ),
                "paired_random_gap_n": len(paired_gaps),
                "paired_random_gap_mean": (
                    rounded(sum(paired_gaps) / len(paired_gaps))
                    if paired_gaps
                    else None
                ),
            }
        )
    rows.sort(
        key=lambda row: sort_group_key(
            "config",
            "extraction",
            row["knowledge"],
            row["defense"],
            row["config_id"],
        )
        + (row["strategy"],)
    )
    return rows


def aggregate_extraction_rows(
    config_rows: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in config_rows:
        grouped[(row["knowledge"], row["defense"], row["strategy"])].append(row)

    aggregate: list[dict[str, Any]] = []
    for (knowledge, defense, strategy), rows in grouped.items():
        completed = sum(row["completed"] for row in rows)
        fact_n = sum(row["fact_recall_n"] for row in rows)
        random_n = sum(row["random_fact_recall_n"] for row in rows)
        gap_n = sum(row["paired_random_gap_n"] for row in rows)
        fact_weighted_sum = sum(
            row["fact_recall_mean"] * row["fact_recall_n"]
            for row in rows
            if row["fact_recall_mean"] is not None
        )
        random_weighted_sum = sum(
            row["random_fact_recall_mean"] * row["random_fact_recall_n"]
            for row in rows
            if row["random_fact_recall_mean"] is not None
        )
        gap_weighted_sum = sum(
            row["paired_random_gap_mean"] * row["paired_random_gap_n"]
            for row in rows
            if row["paired_random_gap_mean"] is not None
        )
        aggregate.append(
            {
                "knowledge": knowledge,
                "defense": defense,
                "strategy": strategy,
                "completed": completed,
                "fact_recall_n": fact_n,
                "fact_recall_missing": sum(
                    row["fact_recall_missing"] for row in rows
                ),
                "fact_recall_mean": (
                    rounded(fact_weighted_sum / fact_n) if fact_n else None
                ),
                "random_fact_recall_n": random_n,
                "random_fact_recall_missing": sum(
                    row["random_fact_recall_missing"] for row in rows
                ),
                "random_fact_recall_mean": (
                    rounded(random_weighted_sum / random_n) if random_n else None
                ),
                "paired_random_gap_n": gap_n,
                "paired_random_gap_mean": (
                    rounded(gap_weighted_sum / gap_n) if gap_n else None
                ),
            }
        )
    aggregate.sort(
        key=lambda row: sort_group_key(
            "aggregate",
            "extraction",
            row["knowledge"],
            row["defense"],
            "",
        )
        + (row["strategy"],)
    )
    return aggregate


def summarize_extraction(records: Sequence[RunRecord]) -> dict[str, Any]:
    extraction_records = [
        record for record in records if record_kind(record) == "extraction"
    ]
    statuses = status_summary(extraction_records)
    config_rows = extraction_group_summary(extraction_records)
    aggregate_rows = aggregate_extraction_rows(config_rows)
    if not extraction_records:
        analysis_status = "not_present"
    elif statuses["completed"] == 0:
        analysis_status = "present_but_no_completed_runs"
    else:
        analysis_status = "completed_records_present"
    return {
        "analysis_status": analysis_status,
        "analysis_complete": False,
        "status_counts": statuses,
        "completed_strategy_groups": config_rows,
        "aggregate_completed_strategy_groups": aggregate_rows,
        "note": (
            "本字段仅说明输入中是否有 extraction 的 completed 记录，"
            "不据此宣称整个抽取实验已经完成。"
        ),
    }


def condition_coverage(records: Sequence[RunRecord]) -> dict[str, Any]:
    any_conditions = {
        (record_kind(record), record_knowledge(record), record_defense(record))
        for record in records
    }
    completed_conditions = {
        (record_kind(record), record_knowledge(record), record_defense(record))
        for record in records
        if record_status(record) == "completed"
    }
    expected = [
        (kind, knowledge, defense)
        for kind, knowledges, defenses in (
            ("attack", KNOWLEDGE_LEVELS, DEFENSES),
            ("benign", ("NONE",), DEFENSES),
            ("extraction", ("HIDDEN",), ("NONE",)),
        )
        for knowledge in knowledges
        for defense in defenses
    ]

    def details(condition: tuple[str, str, str]) -> dict[str, str]:
        return {
            "kind": condition[0],
            "knowledge": condition[1],
            "defense": condition[2],
        }

    return {
        "expected_knowledge": list(KNOWLEDGE_LEVELS),
        "expected_defenses": list(DEFENSES),
        "expected_condition_count": len(expected),
        "observed_any_count": sum(condition in any_conditions for condition in expected),
        "observed_completed_count": sum(
            condition in completed_conditions for condition in expected
        ),
        "missing_any_records": [
            details(condition)
            for condition in expected
            if condition not in any_conditions
        ],
        "missing_completed_records": [
            details(condition)
            for condition in expected
            if condition not in completed_conditions
        ],
    }


def build_summary(
    records: Sequence[RunRecord],
    file_stats: dict[str, Any],
    input_path: Path,
    bootstrap_iterations: int,
    seed: int,
) -> dict[str, Any]:
    overall_status = status_summary(records)
    kinds = sorted(
        {record_kind(record) for record in records},
        key=lambda kind: (KIND_ORDER.get(kind, len(KIND_ORDER)), kind),
    )
    status_by_kind = {
        kind: status_summary(
            [record for record in records if record_kind(record) == kind]
        )
        for kind in kinds
    }
    unknown_kind_records = [
        {"line": record.line_no, "kind": record_kind(record)}
        for record in records
        if record_kind(record) not in VALID_KINDS
    ]
    unknown_status_records = [
        {"line": record.line_no, "status": record_status(record)}
        for record in records
        if record_status(record) not in VALID_STATUSES
    ]

    attack_records = [record for record in records if record_kind(record) == "attack"]
    benign_records = [record for record in records if record_kind(record) == "benign"]

    return {
        "schema_version": 1,
        "analysis_scope": "当前输入 JSONL 的描述性汇总；不对课程实验是否完成作总体声明",
        "input": {
            "path": str(input_path.resolve()),
            **file_stats,
        },
        "analysis_policy": {
            "primary_rate_denominator": "status == completed",
            "non_completed_statuses_excluded_from_primary_rate_denominator": True,
            "invalid_runs_reported_separately": True,
            "behavior_failures_remain_completed": True,
            "missing_behavior_boolean_handling": (
                "保留在 completed 分母中，作用结果按失败计数并另报缺失数"
            ),
            "paired_analysis": (
                "仅使用 D0 下两侧均为 completed 且配对键唯一的 K0/K100 attack 记录"
            ),
            "pair_key_fields": [
                "config_id",
                "pair_id",
                "template",
                "goal",
                "repeat",
            ],
            "bootstrap_seed": seed,
            "bootstrap_iterations": bootstrap_iterations,
            "p_values_reported": False,
            "significance_claims_reported": False,
        },
        "status_counts": {
            "overall": overall_status,
            "by_kind": status_by_kind,
        },
        "data_quality": {
            "malformed_count": file_stats["malformed_count"],
            "malformed_json_lines": file_stats["malformed_json_lines"],
            "unknown_kind_count": len(unknown_kind_records),
            "unknown_kind_records": unknown_kind_records,
            "unknown_status_count": len(unknown_status_records),
            "unknown_status_records": unknown_status_records,
        },
        "condition_counts": build_count_rows(records),
        "attack": {
            "aggregate_conditions": metric_condition_rows(
                attack_records,
                "attack",
                ("attempt_violation", "executed_violation"),
                per_config=False,
            ),
            "config_conditions": metric_condition_rows(
                attack_records,
                "attack",
                ("attempt_violation", "executed_violation"),
                per_config=True,
            ),
        },
        "benign": {
            "aggregate_conditions": metric_condition_rows(
                benign_records,
                "benign",
                ("benign_task_success",),
                per_config=False,
            ),
            "config_conditions": metric_condition_rows(
                benign_records,
                "benign",
                ("benign_task_success",),
                per_config=True,
            ),
        },
        "paired_d0_k100_minus_k0": compute_pairing(
            records,
            bootstrap_iterations=bootstrap_iterations,
            seed=seed,
        ),
        "extraction": summarize_extraction(records),
        "condition_coverage": condition_coverage(records),
        "plot_note": {
            "intervals": "single-condition Wilson 95% descriptive intervals",
            "limitation": (
                "Wilson intervals ignore correlation among repeats, pairs, "
                "configurations, tasks, and templates."
            ),
        },
    }


def status_table_rows(summary: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    for kind, statuses in summary["status_counts"]["by_kind"].items():
        yield kind, statuses


def print_markdown_table(
    header: Sequence[str],
    rows: Sequence[Sequence[Any]],
) -> list[str]:
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return lines


def attack_rows_for_markdown(summary: dict[str, Any]) -> list[list[Any]]:
    result: list[list[Any]] = []
    for row in summary["attack"]["aggregate_conditions"]:
        attempt = row["attempt_violation"]
        executed = row["executed_violation"]
        result.append(
            [
                row["knowledge"],
                row["defense"],
                row["completed"],
                f'{attempt["numerator"]}/{attempt["denominator"]}',
                percent(attempt["rate"]),
                format_interval(
                    attempt["numerator"],
                    attempt["denominator"],
                    as_percent=True,
                ),
                f'{executed["numerator"]}/{executed["denominator"]}',
                percent(executed["rate"]),
                format_interval(
                    executed["numerator"],
                    executed["denominator"],
                    as_percent=True,
                ),
                row["technical_error"] + row["protocol_invalid"] + row["other_status"],
            ]
        )
    return result


def attack_config_rows_for_markdown(summary: dict[str, Any]) -> list[list[Any]]:
    result: list[list[Any]] = []
    for row in summary["attack"]["config_conditions"]:
        attempt = row["attempt_violation"]
        executed = row["executed_violation"]
        result.append(
            [
                row["config_id"],
                row["knowledge"],
                row["defense"],
                row["completed"],
                f'{attempt["numerator"]}/{attempt["denominator"]}',
                percent(attempt["rate"]),
                f'{executed["numerator"]}/{executed["denominator"]}',
                percent(executed["rate"]),
                row["technical_error"] + row["protocol_invalid"] + row["other_status"],
            ]
        )
    return result


def benign_rows_for_markdown(summary: dict[str, Any]) -> list[list[Any]]:
    result: list[list[Any]] = []
    for row in summary["benign"]["aggregate_conditions"]:
        success = row["benign_task_success"]
        result.append(
            [
                row["knowledge"],
                row["defense"],
                row["completed"],
                f'{success["numerator"]}/{success["denominator"]}',
                percent(success["rate"]),
                format_interval(
                    success["numerator"],
                    success["denominator"],
                    as_percent=True,
                ),
                success["missing_outcome"],
                row["technical_error"] + row["protocol_invalid"] + row["other_status"],
            ]
        )
    return result


def benign_config_rows_for_markdown(summary: dict[str, Any]) -> list[list[Any]]:
    result: list[list[Any]] = []
    for row in summary["benign"]["config_conditions"]:
        success = row["benign_task_success"]
        result.append(
            [
                row["config_id"],
                row["knowledge"],
                row["defense"],
                row["completed"],
                f'{success["numerator"]}/{success["denominator"]}',
                percent(success["rate"]),
                success["missing_outcome"],
                row["technical_error"] + row["protocol_invalid"] + row["other_status"],
            ]
        )
    return result


def pairing_rows_for_markdown(summary: dict[str, Any]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for row in summary["paired_d0_k100_minus_k0"]["config_stats"]:
        attempt = row["attempt_violation"]
        executed = row["executed_violation"]
        rows.append(
            [
                row["config_id"],
                row["complete_pairs"],
                percent(attempt["k0_rate"]),
                percent(attempt["k100_rate"]),
                percentage_points(attempt["risk_difference_k100_minus_k0_pp"]),
                percentage_points(executed["risk_difference_k100_minus_k0_pp"]),
            ]
        )
    return rows


def unpaired_rows_for_markdown(summary: dict[str, Any]) -> list[list[Any]]:
    return [
        [
            row["config_id"],
            row["candidate_pair_count"],
            row["complete_pair_count"],
            row["missing_k0_count"],
            row["missing_k100_count"],
            row["duplicate_or_conflict_count"],
        ]
        for row in summary["paired_d0_k100_minus_k0"]["config_pairing_report"]
    ]


def extraction_rows_for_markdown(summary: dict[str, Any]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for row in summary["extraction"]["aggregate_completed_strategy_groups"]:
        rows.append(
            [
                row["knowledge"],
                row["defense"],
                row["strategy"],
                row["completed"],
                f'{row["fact_recall_n"]} (缺 {row["fact_recall_missing"]})',
                percent(row["fact_recall_mean"]),
                f'{row["random_fact_recall_n"]} (缺 {row["random_fact_recall_missing"]})',
                percent(row["random_fact_recall_mean"]),
                percentage_points(
                    None
                    if row["paired_random_gap_mean"] is None
                    else 100.0 * row["paired_random_gap_mean"]
                ),
            ]
        )
    return rows


def missing_conditions_text(summary: dict[str, Any]) -> list[str]:
    coverage = summary["condition_coverage"]
    if not coverage["missing_any_records"]:
        return ["输入覆盖了 K×D×kind 的完整预期网格。"]

    grouped: dict[str, list[str]] = defaultdict(list)
    for item in coverage["missing_any_records"]:
        grouped[item["kind"]].append(f'{item["knowledge"]}/{item["defense"]}')
    pieces = [
        f'{kind}: ' + "、".join(conditions)
        for kind, conditions in grouped.items()
    ]
    return ["以下条件在输入中没有任何记录（不代表观测到的零风险）：", "", *[
        f"- {piece}" for piece in pieces
    ]]


def build_results_markdown(summary: dict[str, Any]) -> str:
    lines: list[str] = [
        "# Agent 安全实验结果自动汇总",
        "",
        "本文件由 `analysis/analyze.py` 根据当前 JSONL 生成，只描述输入中已有的运行记录，"
        "不据此声明课程实验已经完成。",
        "",
        "## 统计口径",
        "",
        "- 主要尝试率、执行率和正常任务成功率的分母只包含 `status=completed`。"
        "模型拒绝、输出格式错误或任务失败若由 runner 记为 completed，仍留在分母中。",
        "- `technical_error`、`protocol_invalid`、其他/缺失状态和 JSON 解析失败单列，"
        "不当作安全成功。",
        "- completed 记录中的行为布尔值若缺失，仍在分母中按失败计入，并报告缺失数。",
        "- 配对分析仅使用 D0 下完整且唯一的 K0/K100 配对；配对键为 "
        "`config_id + template + goal + repeat + defense`。",
        "- Wilson 区间是单条件二项比例的 95% 描述性区间，不处理重复、配对或配置相关性；"
        "本文件不提供 p 值，也不作显著性声明。",
        "",
        "## 输入与无效数",
        "",
        f'- 输入：`{summary["input"]["path"]}`。',
        f'- 非空行：{summary["input"]["nonblank_lines"]}；成功解析记录：'
        f'{summary["input"]["parsed_records"]}；JSON 解析失败：'
        f'{summary["input"]["malformed_count"]}。',
    ]

    status_rows = [
        [
            kind,
            statuses["total_runs"],
            statuses["completed"],
            statuses["technical_error"],
            statuses["protocol_invalid"],
            statuses["other_status"],
            statuses["invalid_total"],
        ]
        for kind, statuses in status_table_rows(summary)
    ]
    overall = summary["status_counts"]["overall"]
    status_rows.append(
        [
            "全部",
            overall["total_runs"],
            overall["completed"],
            overall["technical_error"],
            overall["protocol_invalid"],
            overall["other_status"],
            overall["invalid_total"],
        ]
    )
    lines.extend(
        print_markdown_table(
            (
                "kind",
                "总记录",
                "completed",
                "technical_error",
                "protocol_invalid",
                "其他/缺失状态",
                "无效合计",
            ),
            status_rows,
        )
    )
    lines.extend(
        [
            "",
            "`无效合计 = 总记录 - completed`。上表中的无效数已经单独报告，"
            "没有从 completed 行为率中被重复剔除。",
            "",
            "## 攻击尝试与实际执行",
            "",
        ]
    )

    attack_rows = attack_rows_for_markdown(summary)
    if attack_rows:
        lines.extend(
            print_markdown_table(
                (
                    "知识",
                    "防御",
                    "completed",
                    "尝试计数",
                    "尝试率",
                    "尝试 Wilson 95%",
                    "执行计数",
                    "执行率",
                    "执行 Wilson 95%",
                    "无效数",
                ),
                attack_rows,
            )
        )
        lines.extend(["", "逐配置 attack 条件统计："])
        lines.extend(
            print_markdown_table(
                (
                    "config_id",
                    "知识",
                    "防御",
                    "completed",
                    "尝试计数",
                    "尝试率",
                    "执行计数",
                    "执行率",
                    "无效数",
                ),
                attack_config_rows_for_markdown(summary),
            )
        )
    else:
        lines.append("输入中没有 attack 记录。")

    lines.extend(
        [
            "",
            "计数列均写成“事件数/completed 数”。执行率表示模拟后端产生符合目标的"
            "未授权状态变化，不代表模型没有尝试越权。",
            "",
            "## D0 下 K100 − K0 配对风险差",
            "",
        ]
    )
    paired = summary["paired_d0_k100_minus_k0"]
    bootstrap = paired["bootstrap"]
    lines.extend(
        [
            f'- 主指标：`attempt_violation`；次指标：`executed_violation`。',
            f'- 候选配对：{paired["candidate_pair_count"]}；完整配对：'
            f'{paired["complete_pair_count"]}；未进入估计：'
            f'{paired["unpaired_pair_count"]}；配对键字段缺失记录：'
            f'{paired["key_error_count"]}。',
        ]
    )
    if bootstrap["available"]:
        attempt_boot = bootstrap["attempt_violation"]
        executed_boot = bootstrap["executed_violation"]
        lines.extend(
            [
                f'- 尝试风险差：{attempt_boot["point_estimate_pp"]:.1f} 个百分点；'
                f'配置簇 bootstrap 95% 区间 '
                f'{attempt_boot["ci_95_pp"][0]:.1f} 至 '
                f'{attempt_boot["ci_95_pp"][1]:.1f} 个百分点。',
                f'- 执行风险差：{executed_boot["point_estimate_pp"]:.1f} 个百分点；'
                f'配置簇 bootstrap 95% 区间 '
                f'{executed_boot["ci_95_pp"][0]:.1f} 至 '
                f'{executed_boot["ci_95_pp"][1]:.1f} 个百分点。',
                f'- Bootstrap 参数：{bootstrap["iterations"]} 次，固定 seed='
                f'{bootstrap["seed"]}，{bootstrap["config_cluster_count"]} 个配置簇，'
                "百分位区间；点估计是配置内配对差异的跨配置等权平均。",
            ]
        )
        if bootstrap["instability_note"]:
            lines.append(f'- 警告：{bootstrap["instability_note"]}')
    else:
        lines.append("- 没有完整配对，配对风险差和配置簇 bootstrap 无法估计。")

    pairing_rows = pairing_rows_for_markdown(summary)
    if pairing_rows:
        lines.extend(["", "逐配置完整配对差异："])
        lines.extend(
            print_markdown_table(
                (
                    "config_id",
                    "完整配对数",
                    "K0 尝试率",
                    "K100 尝试率",
                    "尝试差",
                    "执行差",
                ),
                pairing_rows,
            )
        )

    unpaired_rows = unpaired_rows_for_markdown(summary)
    if unpaired_rows:
        lines.extend(["", "逐配置配对完整性："])
        lines.extend(
            print_markdown_table(
                (
                    "config_id",
                    "候选",
                    "完整",
                    "缺 completed K0",
                    "缺 completed K100",
                    "重复/冲突",
                ),
                unpaired_rows,
            )
        )
        if paired["unpaired_pair_count"]:
            lines.append(
                "存在未完整配对或重复冲突的键；这些键均未进入配对点估计和 bootstrap。"
                "逐键原因保存在 `summary.json` 的 `unpaired_pair_keys`。"
            )

    lines.extend(["", "## 正常任务效用", ""])
    benign_rows = benign_rows_for_markdown(summary)
    if benign_rows:
        lines.extend(
            print_markdown_table(
                (
                    "知识",
                    "防御",
                    "completed",
                    "成功计数",
                    "成功率",
                    "Wilson 95%",
                    "缺失行为值",
                    "无效数",
                ),
                benign_rows,
            )
        )
        lines.extend(["", "逐配置 benign 条件统计："])
        lines.extend(
            print_markdown_table(
                (
                    "config_id",
                    "知识",
                    "防御",
                    "completed",
                    "成功计数",
                    "成功率",
                    "缺失行为值",
                    "无效数",
                ),
                benign_config_rows_for_markdown(summary),
            )
        )
    else:
        lines.append("输入中没有 benign 记录，无法从当前数据汇总正常任务效用。")

    lines.extend(["", "## 抽取（extraction）", ""])
    extraction = summary["extraction"]
    if extraction["analysis_status"] == "not_present":
        lines.append("输入中没有 extraction 记录；**extraction 分析未完成**。")
    elif extraction["analysis_status"] == "present_but_no_completed_runs":
        statuses = extraction["status_counts"]
        lines.append(
            "输入中有 extraction 记录，但没有 completed 记录；"
            f'technical_error={statuses["technical_error"]}，'
            f'protocol_invalid={statuses["protocol_invalid"]}，'
            "因此当前无法汇总抽取效果。"
        )
    else:
        statuses = extraction["status_counts"]
        lines.append(
            f'输入中有 {statuses["completed"]} 条 completed extraction 记录；'
            "以下只汇总该输入，不表示完整抽取实验已经完成。"
        )
        rows = extraction_rows_for_markdown(summary)
        if rows:
            lines.extend(
                print_markdown_table(
                    (
                        "知识",
                        "防御",
                        "strategy",
                        "completed",
                        "fact_recall n",
                        "平均 fact_recall",
                        "random n",
                        "平均 random_fact_recall",
                        "配对均值差",
                    ),
                    rows,
                )
            )
        lines.append(
            "召回率均值只使用 completed 中可解析的数值；缺失值与样本数单列，"
            "不做插补。"
        )

    lines.extend(["", "## 条件覆盖与图", ""])
    lines.extend(missing_conditions_text(summary))
    lines.extend(
        [
            "",
            "![Attempt and execution rates](attempt_execute.png)",
            "",
            "图中柱高是 completed attack 中的观察率，柱顶写事件数/completed 数；"
            "误差线为单条件 Wilson 95% 描述性区间。该区间忽略重复、配对、配置、任务和"
            "模板之间的相关性，不能当作独立样本推断。",
        ]
    )
    return "\n".join(lines) + "\n"


def make_attempt_execute_plot(summary: dict[str, Any], output_path: Path) -> None:
    prepare_windows_plot_runtime()
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    condition_lookup = {
        (row["knowledge"], row["defense"]): row
        for row in summary["attack"]["aggregate_conditions"]
    }
    conditions = [
        (knowledge, defense)
        for defense in DEFENSES
        for knowledge in KNOWLEDGE_LEVELS
    ]
    labels = [f"{knowledge}\n{defense}" for knowledge, defense in conditions]
    x = np.arange(len(conditions), dtype=float)
    width = 0.36

    attempt_rates: list[float] = []
    executed_rates: list[float] = []
    attempt_lower: list[float] = []
    attempt_upper: list[float] = []
    executed_lower: list[float] = []
    executed_upper: list[float] = []
    attempt_labels: list[str] = []
    executed_labels: list[str] = []
    completed_counts: list[int] = []

    for condition in conditions:
        row = condition_lookup.get(condition)
        if row is None or row["completed"] == 0:
            completed_counts.append(0)
            attempt_rates.append(0.0)
            executed_rates.append(0.0)
            for lower, upper in (
                (attempt_lower, attempt_upper),
                (executed_lower, executed_upper),
            ):
                lower.append(0.0)
                upper.append(0.0)
            attempt_labels.append("no data")
            executed_labels.append("no data")
            continue

        completed_counts.append(row["completed"])
        attempt = row["attempt_violation"]
        executed = row["executed_violation"]
        attempt_rate = attempt["rate"] or 0.0
        executed_rate = executed["rate"] or 0.0
        attempt_rates.append(attempt_rate)
        executed_rates.append(executed_rate)
        attempt_interval = attempt["wilson_95"]
        executed_interval = executed["wilson_95"]
        attempt_lower.append(
            attempt_rate - attempt_interval["low"] if attempt_interval else 0.0
        )
        attempt_upper.append(
            attempt_interval["high"] - attempt_rate if attempt_interval else 0.0
        )
        executed_lower.append(
            executed_rate - executed_interval["low"] if executed_interval else 0.0
        )
        executed_upper.append(
            executed_interval["high"] - executed_rate if executed_interval else 0.0
        )
        attempt_labels.append(
            f'{attempt["numerator"]}/{attempt["denominator"]}'
        )
        executed_labels.append(
            f'{executed["numerator"]}/{executed["denominator"]}'
        )

    fig, ax = plt.subplots(figsize=(12.5, 7.2))
    attempt_x = x - width / 2.0
    executed_x = x + width / 2.0
    attempt_bars = ax.bar(
        attempt_x,
        attempt_rates,
        width,
        color="#B44A3D",
        label="Attempt violation",
        yerr=np.asarray([attempt_lower, attempt_upper]),
        capsize=4,
        error_kw={"elinewidth": 1.2, "ecolor": "#3C3C3C"},
    )
    executed_bars = ax.bar(
        executed_x,
        executed_rates,
        width,
        color="#2E6F9E",
        label="Executed violation",
        yerr=np.asarray([executed_lower, executed_upper]),
        capsize=4,
        error_kw={"elinewidth": 1.2, "ecolor": "#3C3C3C"},
    )

    maximum_height = max(attempt_rates + executed_rates, default=0.0)
    text_offset = 0.025
    for condition_index, bar in enumerate(attempt_bars):
        if completed_counts[condition_index] == 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                0.015,
                "no data",
                ha="center",
                va="bottom",
                rotation=90,
                fontsize=8,
                color="#666666",
            )
        else:
            height = attempt_rates[condition_index] + attempt_upper[condition_index]
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                min(1.04, height + text_offset),
                attempt_labels[condition_index],
                ha="center",
                va="bottom",
                fontsize=8,
            )
    for condition_index, bar in enumerate(executed_bars):
        if completed_counts[condition_index] == 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                0.015,
                "no data",
                ha="center",
                va="bottom",
                rotation=90,
                fontsize=8,
                color="#666666",
            )
        else:
            height = executed_rates[condition_index] + executed_upper[condition_index]
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                min(1.04, height + text_offset),
                executed_labels[condition_index],
                ha="center",
                va="bottom",
                fontsize=8,
            )

    ax.set_title("Attack Attempt and Execution Rates by Knowledge and Defense", pad=14)
    ax.set_ylabel("Observed rate among completed attacks")
    ax.set_xlabel("Knowledge condition and defense")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0.0, 1.10)
    ax.set_yticks(np.linspace(0.0, 1.0, 6))
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.8, alpha=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="upper left", ncols=2)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    fig.text(
        0.5,
        0.015,
        "Error bars: single-condition Wilson 95% descriptive intervals; "
        "correlation among runs and configurations is ignored.",
        ha="center",
        va="bottom",
        fontsize=8.5,
        color="#444444",
    )
    fig.tight_layout(rect=(0.0, 0.055, 1.0, 1.0))
    fig.savefig(output_path, dpi=180, facecolor="white")
    plt.close(fig)


def write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COUNT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    column: "" if row.get(column) is None else row.get(column)
                    for column in COUNT_COLUMNS
                }
            )


def write_outputs(
    summary: dict[str, Any],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "counts.csv", summary["condition_counts"])
    with (output_dir / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    (output_dir / "results.md").write_text(
        build_results_markdown(summary),
        encoding="utf-8",
    )
    make_attempt_execute_plot(summary, output_dir / "attempt_execute.png")


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("必须为正整数")
    return number


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="汇总 Agent 安全实验结果 JSONL（只读输入，生成描述性统计）。"
    )
    parser.add_argument("--input", required=True, type=Path, help="输入 JSONL 路径")
    parser.add_argument("--output", required=True, type=Path, help="输出目录")
    parser.add_argument(
        "--bootstrap-iterations",
        type=positive_int,
        default=DEFAULT_BOOTSTRAP_ITERATIONS,
        help=f"配置簇 bootstrap 次数（默认 {DEFAULT_BOOTSTRAP_ITERATIONS}）",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"bootstrap 固定随机 seed（默认 {DEFAULT_SEED}）",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.input.is_file():
        raise SystemExit(f"输入文件不存在或不是普通文件: {args.input}")

    records, file_stats = read_jsonl(args.input)
    summary = build_summary(
        records,
        file_stats=file_stats,
        input_path=args.input,
        bootstrap_iterations=args.bootstrap_iterations,
        seed=args.seed,
    )
    write_outputs(summary, args.output)
    print(f"已写入: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
