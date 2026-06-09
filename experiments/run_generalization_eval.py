from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.planner import SafeOpsAgent  # noqa: E402
from experiments.error_analysis import export_error_cases  # noqa: E402
from experiments.metrics import compute_metrics, write_metrics_csv, write_metrics_json  # noqa: E402
from experiments.run_eval import (  # noqa: E402
    evaluate_row,
    load_test_queries,
    print_llm_diagnostics,
    print_llm_error_types,
    print_llm_usage_warning,
)
from llm.client import LLMClient, load_local_dotenv  # noqa: E402


DATA_PATH = PROJECT_ROOT / "data" / "generalization_queries.csv"
RESULTS_LLM_PATH = PROJECT_ROOT / "results" / "generalization_eval_results_llm.csv"
RESULTS_FALLBACK_PATH = PROJECT_ROOT / "results" / "generalization_eval_results_fallback.csv"
RESULTS_COMBINED_PATH = PROJECT_ROOT / "results" / "generalization_eval_results.csv"
METRICS_LLM_CSV_PATH = PROJECT_ROOT / "results" / "generalization_metrics_summary_llm.csv"
METRICS_FALLBACK_CSV_PATH = PROJECT_ROOT / "results" / "generalization_metrics_summary_fallback.csv"
METRICS_COMBINED_CSV_PATH = PROJECT_ROOT / "results" / "generalization_metrics_summary.csv"
METRICS_LLM_JSON_PATH = PROJECT_ROOT / "results" / "generalization_metrics_summary_llm.json"
METRICS_FALLBACK_JSON_PATH = PROJECT_ROOT / "results" / "generalization_metrics_summary_fallback.json"
METRICS_COMBINED_JSON_PATH = PROJECT_ROOT / "results" / "generalization_metrics_summary.json"
ERROR_CASES_LLM_PATH = PROJECT_ROOT / "results" / "generalization_error_cases_llm.csv"
ERROR_CASES_FALLBACK_PATH = PROJECT_ROOT / "results" / "generalization_error_cases_fallback.csv"

MODE_FIELD = "eval_mode"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run LLM and fallback evaluation on generalization queries.")
    parser.add_argument("--data", default=str(DATA_PATH), help="Path to generalization_queries.csv")
    parser.add_argument("--output-llm", default=str(RESULTS_LLM_PATH), help="Path to write LLM-requested eval results")
    parser.add_argument("--output-fallback", default=str(RESULTS_FALLBACK_PATH), help="Path to write fallback eval results")
    parser.add_argument("--output-combined", default=str(RESULTS_COMBINED_PATH), help="Path to write combined eval results")
    parser.add_argument("--metrics-llm-csv", default=str(METRICS_LLM_CSV_PATH), help="Path to write LLM metrics CSV")
    parser.add_argument("--metrics-fallback-csv", default=str(METRICS_FALLBACK_CSV_PATH), help="Path to write fallback metrics CSV")
    parser.add_argument("--metrics-combined-csv", default=str(METRICS_COMBINED_CSV_PATH), help="Path to write combined metrics CSV")
    parser.add_argument("--metrics-llm-json", default=str(METRICS_LLM_JSON_PATH), help="Path to write LLM metrics JSON")
    parser.add_argument("--metrics-fallback-json", default=str(METRICS_FALLBACK_JSON_PATH), help="Path to write fallback metrics JSON")
    parser.add_argument("--metrics-combined-json", default=str(METRICS_COMBINED_JSON_PATH), help="Path to write combined metrics JSON")
    parser.add_argument("--error-cases-llm", default=str(ERROR_CASES_LLM_PATH), help="Path to write LLM error cases CSV")
    parser.add_argument(
        "--error-cases-fallback",
        default=str(ERROR_CASES_FALLBACK_PATH),
        help="Path to write fallback error cases CSV",
    )
    args = parser.parse_args()

    load_local_dotenv()
    llm_client = LLMClient()
    fallback_client = LLMClient()
    rows = load_test_queries(args.data)

    print_llm_diagnostics(force_fallback=False)
    llm_results = run_mode(rows, "llm_mode", force_fallback=False, llm_client=llm_client)
    print_llm_diagnostics(force_fallback=True)
    fallback_results = run_mode(rows, "fallback_mode", force_fallback=True, llm_client=fallback_client)
    all_results = llm_results + fallback_results
    write_generalization_results(llm_results, args.output_llm)
    write_generalization_results(fallback_results, args.output_fallback)
    write_generalization_results(all_results, args.output_combined)

    metrics_by_mode = {
        "llm_mode": compute_metrics(llm_results, requested_mode="llm"),
        "fallback_mode": compute_metrics(fallback_results, requested_mode="fallback"),
    }
    write_metrics_csv(metrics_by_mode["llm_mode"], args.metrics_llm_csv)
    write_metrics_csv(metrics_by_mode["fallback_mode"], args.metrics_fallback_csv)
    write_metrics_json(metrics_by_mode["llm_mode"], args.metrics_llm_json)
    write_metrics_json(metrics_by_mode["fallback_mode"], args.metrics_fallback_json)
    write_mode_metrics_csv(metrics_by_mode, args.metrics_combined_csv)
    write_metrics_json(metrics_by_mode, args.metrics_combined_json)
    llm_error_cases = export_error_cases(llm_results, args.error_cases_llm)
    fallback_error_cases = export_error_cases(fallback_results, args.error_cases_fallback)

    print(f"evaluated_samples_per_mode: {len(rows)}")
    print(f"eval_results_llm: {args.output_llm}")
    print(f"eval_results_fallback: {args.output_fallback}")
    print(f"eval_results_combined: {args.output_combined}")
    print(f"metrics_summary_llm_csv: {args.metrics_llm_csv}")
    print(f"metrics_summary_fallback_csv: {args.metrics_fallback_csv}")
    print(f"metrics_summary_combined_csv: {args.metrics_combined_csv}")
    print(f"metrics_summary_llm_json: {args.metrics_llm_json}")
    print(f"metrics_summary_fallback_json: {args.metrics_fallback_json}")
    print(f"metrics_summary_combined_json: {args.metrics_combined_json}")
    print(f"error_cases_llm: {args.error_cases_llm}")
    print(f"error_cases_llm_count: {len(llm_error_cases)}")
    print(f"error_cases_fallback: {args.error_cases_fallback}")
    print(f"error_cases_fallback_count: {len(fallback_error_cases)}")
    print(f"llm_configured: {llm_client.is_configured}")
    print("[llm_mode_errors]")
    print_llm_error_types(llm_client)
    print("[fallback_mode_errors]")
    print_llm_error_types(fallback_client)
    for mode, metrics in metrics_by_mode.items():
        print(f"[{mode}]")
        print_llm_usage_warning(metrics)
        for key in (
            "llm_count",
            "fallback_count",
            "safety_rule_count",
            "llm_ratio",
            "intent_accuracy",
            "risk_accuracy",
            "tool_accuracy",
            "dangerous_block_rate",
            "injection_block_rate",
            "false_block_rate",
            "confirmation_accuracy",
            "task_success_rate",
            "avg_latency_ms",
            "avg_planning_ms",
            "avg_safety_ms",
            "avg_tool_ms",
            "avg_total_ms",
        ):
            print(f"{key}: {metrics[key]}")


def run_mode(
    rows: list[dict[str, str]],
    mode: str,
    *,
    force_fallback: bool,
    llm_client: LLMClient,
) -> list[dict[str, Any]]:
    agent = SafeOpsAgent(
        audit_log_path=PROJECT_ROOT / "logs" / f"audit_generalization_{mode}.jsonl",
        llm_client=llm_client,
    )
    if force_fallback:
        agent.intent_planner.llm_client.plan = lambda messages: (None, "forced fallback for generalization evaluation")

    results = []
    for row in rows:
        result = evaluate_row(agent, row)
        result[MODE_FIELD] = mode
        results.append(result)
    return results


def write_generalization_results(rows: list[dict[str, Any]], path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [MODE_FIELD] + [field for field in _result_fields(rows) if field != MODE_FIELD]
    with output_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_mode_metrics_csv(metrics_by_mode: dict[str, dict[str, Any]], path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=["mode", "metric", "value"])
        writer.writeheader()
        for mode, metrics in metrics_by_mode.items():
            for key, value in metrics.items():
                writer.writerow({"mode": mode, "metric": key, "value": value})


def _result_fields(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return [MODE_FIELD]
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    return fields


if __name__ == "__main__":
    main()
