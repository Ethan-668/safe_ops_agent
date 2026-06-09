from __future__ import annotations

import argparse
import csv
import html
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STANDARD_LLM_METRICS_PATH = PROJECT_ROOT / "results" / "metrics_summary_llm.csv"
STANDARD_FALLBACK_METRICS_PATH = PROJECT_ROOT / "results" / "metrics_summary_fallback.csv"
GENERALIZATION_LLM_METRICS_PATH = PROJECT_ROOT / "results" / "generalization_metrics_summary_llm.csv"
GENERALIZATION_FALLBACK_METRICS_PATH = PROJECT_ROOT / "results" / "generalization_metrics_summary_fallback.csv"
SECURITY_SUMMARY_PATH = PROJECT_ROOT / "results" / "security_attack_summary.csv"
ABLATION_SUMMARY_PATH = PROJECT_ROOT / "results" / "ablation_summary.csv"
STANDARD_LLM_RESULTS_PATH = PROJECT_ROOT / "results" / "eval_results_llm.csv"
STANDARD_FALLBACK_RESULTS_PATH = PROJECT_ROOT / "results" / "eval_results_fallback.csv"
GENERALIZATION_LLM_RESULTS_PATH = PROJECT_ROOT / "results" / "generalization_eval_results_llm.csv"
GENERALIZATION_FALLBACK_RESULTS_PATH = PROJECT_ROOT / "results" / "generalization_eval_results_fallback.csv"
SECURITY_RESULTS_PATH = PROJECT_ROOT / "results" / "security_attack_results.csv"
FIGURES_DIR = PROJECT_ROOT / "results" / "figures"


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot evaluation metrics if matplotlib is installed.")
    parser.add_argument("--output-dir", default=str(FIGURES_DIR), help="Directory for generated figures")
    args = parser.parse_args()

    global plt  # noqa: PLW0603 - optional plotting dependency is imported lazily.
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        plt = None
        print("matplotlib 未安装，使用 SVG 后备方式生成图表。")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    standard_llm = load_metrics(STANDARD_LLM_METRICS_PATH)
    standard_fallback = load_metrics(STANDARD_FALLBACK_METRICS_PATH)
    generalization_llm = load_metrics(GENERALIZATION_LLM_METRICS_PATH)
    generalization_fallback = load_metrics(GENERALIZATION_FALLBACK_METRICS_PATH)
    security_summary = load_metrics(SECURITY_SUMMARY_PATH)
    ablation_rows = load_rows(ABLATION_SUMMARY_PATH)

    plot_metrics_comparison(
        standard_llm,
        standard_fallback,
        output_dir / "standard_llm_vs_fallback_metrics.svg",
        "Standard Set: LLM vs Fallback",
    )
    plot_metrics_comparison(
        generalization_llm,
        generalization_fallback,
        output_dir / "generalization_llm_vs_fallback_metrics.svg",
        "Generalization Set: LLM vs Fallback",
    )
    plot_standard_vs_generalization_success(
        standard_llm,
        standard_fallback,
        generalization_llm,
        generalization_fallback,
        output_dir / "standard_vs_generalization_success.svg",
    )
    plot_security_attack_rates(security_summary, output_dir / "security_attack_block_rates.svg")
    plot_ablation_results(ablation_rows, output_dir / "ablation_results.svg")
    plot_stage_latency_breakdown(
        standard_llm,
        standard_fallback,
        generalization_llm,
        generalization_fallback,
        security_summary,
        output_dir / "stage_latency_breakdown.svg",
    )
    plot_source_distribution(build_source_rows(), output_dir / "source_distribution.svg")
    print(f"figures_dir: {output_dir}")


def load_metrics(path: str | Path) -> dict[str, float]:
    metrics: dict[str, float] = {}
    input_path = Path(path)
    if not input_path.exists():
        return metrics
    with input_path.open("r", encoding="utf-8", newline="") as fp:
        for row in csv.DictReader(fp):
            try:
                metrics[row["metric"]] = float(row["value"])
            except (KeyError, ValueError):
                continue
    return metrics


def load_mode_metrics(path: str | Path) -> dict[str, dict[str, float]]:
    metrics: dict[str, dict[str, float]] = defaultdict(dict)
    input_path = Path(path)
    if not input_path.exists():
        return {}
    with input_path.open("r", encoding="utf-8", newline="") as fp:
        for row in csv.DictReader(fp):
            try:
                metrics[row["mode"]][row["metric"]] = float(row["value"])
            except (KeyError, ValueError):
                continue
    return dict(metrics)


def load_rows(path: str | Path) -> list[dict[str, str]]:
    input_path = Path(path)
    if not input_path.exists():
        return []
    with input_path.open("r", encoding="utf-8", newline="") as fp:
        return list(csv.DictReader(fp))


def plot_bar(values: dict[str, float], output_path: Path, title: str, ylabel: str) -> None:
    if not values:
        return
    labels = list(values)
    scores = [values[label] for label in labels]
    if plt is None:
        write_bar_svg(labels, scores, output_path.with_suffix(".svg"), title, ylabel)
        return

    width = max(8, len(labels) * 1.2)
    plt.figure(figsize=(width, 4.5))
    plt.bar(labels, scores, color="#2f6f73")
    plt.title(title)
    plt.ylabel(ylabel)
    plt.ylim(0, max(1.0, max(scores) * 1.15))
    plt.xticks(rotation=25, ha="right")
    plt.tight_layout()
    plt.savefig(output_path, dpi=160)
    plt.close()


def plot_llm_vs_fallback_accuracy(metrics_by_mode: dict[str, dict[str, float]], output_path: Path) -> None:
    if not metrics_by_mode:
        return
    keys = ["intent_accuracy", "risk_accuracy", "tool_accuracy", "task_success_rate"]
    labels = ["Intent", "Risk", "Tool", "Task"]
    plot_grouped_bars(
        labels=labels,
        series={
            "LLM mode": [metrics_by_mode.get("llm_mode", {}).get(key, 0.0) for key in keys],
            "Fallback mode": [metrics_by_mode.get("fallback_mode", {}).get(key, 0.0) for key in keys],
        },
        output_path=output_path,
        title="Generalization Accuracy",
        ylabel="score",
        ylim_max=1.05,
    )


def plot_llm_vs_fallback_latency(metrics_by_mode: dict[str, dict[str, float]], output_path: Path) -> None:
    if not metrics_by_mode:
        return
    values = {
        "LLM mode": metrics_by_mode.get("llm_mode", {}).get("avg_latency_ms", 0.0),
        "Fallback mode": metrics_by_mode.get("fallback_mode", {}).get("avg_latency_ms", 0.0),
    }
    plot_bar(values, output_path, "Generalization Latency", "avg latency (ms)")


def plot_metrics_comparison(
    llm_metrics: dict[str, float],
    fallback_metrics: dict[str, float],
    output_path: Path,
    title: str,
) -> None:
    if not llm_metrics and not fallback_metrics:
        return
    keys = ["intent_accuracy", "risk_accuracy", "tool_accuracy", "confirmation_accuracy", "task_success_rate"]
    labels = ["Intent", "Risk", "Tool", "Confirm", "Task"]
    plot_grouped_bars(
        labels=labels,
        series={
            "LLM requested": [llm_metrics.get(key, 0.0) for key in keys],
            "Fallback": [fallback_metrics.get(key, 0.0) for key in keys],
        },
        output_path=output_path,
        title=title,
        ylabel="score",
        ylim_max=1.05,
    )


def plot_standard_vs_generalization_success(
    standard_llm: dict[str, float],
    standard_fallback: dict[str, float],
    generalization_llm: dict[str, float],
    generalization_fallback: dict[str, float],
    output_path: Path,
) -> None:
    values = {
        "Standard LLM": standard_llm.get("task_success_rate", 0.0),
        "Standard Fallback": standard_fallback.get("task_success_rate", 0.0),
        "Generalization LLM": generalization_llm.get("task_success_rate", 0.0),
        "Generalization Fallback": generalization_fallback.get("task_success_rate", 0.0),
    }
    plot_bar(values, output_path, "Standard vs Generalization Success", "task success rate")


def plot_security_attack_rates(metrics: dict[str, float], output_path: Path) -> None:
    if not metrics:
        return
    values = {
        "Direct dangerous": metrics.get("direct_dangerous_block_rate", 0.0),
        "Sensitive path": metrics.get("sensitive_path_block_rate", 0.0),
        "Prompt injection": metrics.get("prompt_injection_block_rate", 0.0),
        "Confirmation attack": metrics.get("confirmation_attack_block_rate", 0.0),
        "Benign false block": metrics.get("benign_false_block_rate", 0.0),
    }
    plot_bar(values, output_path, "Security Attack Block Rates", "rate")


def plot_stage_latency_breakdown(
    standard_llm: dict[str, float],
    standard_fallback: dict[str, float],
    generalization_llm: dict[str, float],
    generalization_fallback: dict[str, float],
    security_summary: dict[str, float],
    output_path: Path,
) -> None:
    labels = ["Std LLM", "Std FB", "Gen LLM", "Gen FB", "Security"]
    metrics = [standard_llm, standard_fallback, generalization_llm, generalization_fallback, security_summary]
    plot_grouped_bars(
        labels=labels,
        series={
            "Planning": [item.get("avg_planning_ms", 0.0) for item in metrics],
            "Safety": [item.get("avg_safety_ms", 0.0) for item in metrics],
            "Tool": [item.get("avg_tool_ms", 0.0) for item in metrics],
        },
        output_path=output_path,
        title="Stage Latency Breakdown",
        ylabel="avg latency (ms)",
    )


def build_source_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for label, path in [
        ("standard_llm", STANDARD_LLM_RESULTS_PATH),
        ("standard_fallback", STANDARD_FALLBACK_RESULTS_PATH),
        ("generalization_llm", GENERALIZATION_LLM_RESULTS_PATH),
        ("generalization_fallback", GENERALIZATION_FALLBACK_RESULTS_PATH),
        ("security", SECURITY_RESULTS_PATH),
    ]:
        for row in load_rows(path):
            item = dict(row)
            item["eval_mode"] = label
            rows.append(item)
    return rows


def plot_source_distribution(rows: list[dict[str, str]], output_path: Path) -> None:
    if not rows:
        return
    modes = sorted({row.get("eval_mode", "unknown") for row in rows})
    sources = sorted({row.get("source", "unknown") for row in rows})
    counts = {
        source: [
            sum(1 for row in rows if row.get("eval_mode", "unknown") == mode and row.get("source", "unknown") == source)
            for mode in modes
        ]
        for source in sources
    }
    plot_grouped_bars(
        labels=modes,
        series=counts,
        output_path=output_path,
        title="Planning Source Distribution",
        ylabel="sample count",
    )


def plot_ablation_results(rows: list[dict[str, str]], output_path: Path) -> None:
    if not rows:
        return
    labels = [row.get("variant", "") for row in rows]
    series = {
        "Task success": [_float(row.get("task_success_rate")) for row in rows],
        "Danger block": [_float(row.get("dangerous_block_rate")) for row in rows],
        "Confirmation": [_float(row.get("confirmation_accuracy")) for row in rows],
    }
    plot_grouped_bars(
        labels=labels,
        series=series,
        output_path=output_path,
        title="Ablation Results",
        ylabel="score",
        ylim_max=1.05,
    )


def plot_grouped_bars(
    *,
    labels: list[str],
    series: dict[str, list[float]],
    output_path: Path,
    title: str,
    ylabel: str,
    ylim_max: float | None = None,
) -> None:
    if not labels or not series:
        return
    x_positions = list(range(len(labels)))
    series_names = list(series)
    width = min(0.8 / max(len(series_names), 1), 0.28)
    colors = ["#2f6f73", "#b85750", "#5c6fa8", "#8a7a35", "#75607d"]
    if plt is None:
        write_grouped_bar_svg(labels, series, output_path.with_suffix(".svg"), title, ylabel, colors, ylim_max)
        return

    plt.figure(figsize=(max(8, len(labels) * 1.45), 4.8))
    for index, name in enumerate(series_names):
        offset = (index - (len(series_names) - 1) / 2) * width
        values = series[name]
        plt.bar(
            [position + offset for position in x_positions],
            values,
            width=width,
            label=name,
            color=colors[index % len(colors)],
        )

    plt.title(title)
    plt.ylabel(ylabel)
    if ylim_max is not None:
        plt.ylim(0, ylim_max)
    plt.xticks(x_positions, labels, rotation=25, ha="right")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=160)
    plt.close()


def _float(value: str | None) -> float:
    try:
        return float(value or 0)
    except ValueError:
        return 0.0


def write_bar_svg(labels: list[str], values: list[float], output_path: Path, title: str, ylabel: str) -> None:
    max_value = max(values) if values else 1.0
    scale_max = max(1.0, max_value * 1.15)
    width = max(760, 90 * len(labels))
    height = 420
    margin_left = 72
    margin_bottom = 98
    chart_width = width - margin_left - 32
    chart_height = height - 70 - margin_bottom
    slot = chart_width / max(len(labels), 1)
    bar_width = slot * 0.58

    parts = svg_header(width, height, title, ylabel)
    for index, (label, value) in enumerate(zip(labels, values)):
        bar_height = 0 if scale_max <= 0 else chart_height * value / scale_max
        x = margin_left + index * slot + (slot - bar_width) / 2
        y = 70 + chart_height - bar_height
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{bar_height:.1f}" fill="#2f6f73"/>')
        parts.append(svg_text(x + bar_width / 2, y - 6, f"{value:.3g}", 11, "middle"))
        parts.append(svg_text(x + bar_width / 2, height - 76, label, 11, "end", rotate=-28))
    parts.extend(svg_axes(margin_left, 70, chart_width, chart_height, scale_max))
    parts.append("</svg>")
    output_path.write_text("\n".join(parts), encoding="utf-8")


def write_grouped_bar_svg(
    labels: list[str],
    series: dict[str, list[float]],
    output_path: Path,
    title: str,
    ylabel: str,
    colors: list[str],
    ylim_max: float | None,
) -> None:
    series_names = list(series)
    all_values = [value for values in series.values() for value in values]
    max_value = max(all_values) if all_values else 1.0
    scale_max = ylim_max if ylim_max is not None else max(1.0, max_value * 1.15)
    width = max(820, 122 * len(labels))
    height = 460
    margin_left = 72
    margin_bottom = 122
    chart_width = width - margin_left - 36
    chart_height = height - 76 - margin_bottom
    slot = chart_width / max(len(labels), 1)
    bar_width = min(slot * 0.72 / max(len(series_names), 1), 26)

    parts = svg_header(width, height, title, ylabel)
    for group_index, label in enumerate(labels):
        group_center = margin_left + group_index * slot + slot / 2
        for series_index, name in enumerate(series_names):
            values = series[name]
            value = values[group_index] if group_index < len(values) else 0.0
            bar_height = 0 if scale_max <= 0 else chart_height * value / scale_max
            offset = (series_index - (len(series_names) - 1) / 2) * (bar_width + 4)
            x = group_center + offset - bar_width / 2
            y = 76 + chart_height - bar_height
            color = colors[series_index % len(colors)]
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{bar_height:.1f}" fill="{color}"/>')
        parts.append(svg_text(group_center, height - 92, label, 11, "end", rotate=-28))

    legend_x = margin_left + chart_width - 210
    for index, name in enumerate(series_names):
        y = 28 + index * 18
        color = colors[index % len(colors)]
        parts.append(f'<rect x="{legend_x}" y="{y}" width="12" height="12" fill="{color}"/>')
        parts.append(svg_text(legend_x + 18, y + 10, name, 11, "start"))

    parts.extend(svg_axes(margin_left, 76, chart_width, chart_height, scale_max))
    parts.append("</svg>")
    output_path.write_text("\n".join(parts), encoding="utf-8")


def svg_header(width: int, height: int, title: str, ylabel: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        svg_text(width / 2, 28, title, 18, "middle", weight="700"),
        svg_text(20, height / 2, ylabel, 12, "middle", rotate=-90),
    ]


def svg_axes(left: int, top: int, chart_width: float, chart_height: float, scale_max: float) -> list[str]:
    bottom = top + chart_height
    right = left + chart_width
    parts = [
        f'<line x1="{left}" y1="{bottom:.1f}" x2="{right:.1f}" y2="{bottom:.1f}" stroke="#333"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom:.1f}" stroke="#333"/>',
    ]
    for tick in range(5):
        ratio = tick / 4
        value = scale_max * ratio
        y = bottom - chart_height * ratio
        parts.append(f'<line x1="{left - 4}" y1="{y:.1f}" x2="{right:.1f}" y2="{y:.1f}" stroke="#e6e6e6"/>')
        parts.append(svg_text(left - 8, y + 4, f"{value:.2g}", 10, "end"))
    return parts


def svg_text(
    x: float,
    y: float,
    text: str,
    size: int,
    anchor: str,
    *,
    rotate: int | None = None,
    weight: str = "400",
) -> str:
    transform = f' transform="rotate({rotate} {x:.1f} {y:.1f})"' if rotate is not None else ""
    safe_text = html.escape(text)
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="Arial, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" fill="#222"{transform}>{safe_text}</text>'
    )


if __name__ == "__main__":
    main()
