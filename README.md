# 安全智能运维 Agent

NLP 课程项目 MVP：基于大语言模型的操作系统安全智能运维 Agent。

## 安装依赖

```bash
conda create -n safe_ops_agent python=3.10 -y
conda activate safe_ops_agent
pip install -r requirements.txt
```

## 配置大模型

项目使用 OpenAI 兼容接口，读取环境变量：

```bash
export LLM_API_KEY="your_api_key"
export LLM_BASE_URL="https://your-openai-compatible-endpoint.example/v1"
export LLM_MODEL_NAME="your-model-name"
```

未配置或 API 调用失败时，会自动使用规则 fallback，便于本地演示。

`.env` 可放在项目根目录用于本地实验配置，但不应提交到版本库；实验脚本只输出配置是否存在，不会打印 API key。

## 启动

```bash
python app.py
```

浏览器打开控制台中显示的 Gradio 地址。

## 实验评估

推荐按以下顺序运行，保证沙箱状态和结果文件可复现：

```bash
cd /home/miaoyunlong/projects/safe_ops_agent
source ~/miniconda3/etc/profile.d/conda.sh
conda activate safe_ops_agent

python3 scripts/reset_sandbox.py

python3 experiments/run_eval.py
python3 experiments/run_eval.py --force-fallback

python3 experiments/run_generalization_eval.py

python3 experiments/run_security_eval.py

python3 experiments/run_ablation.py
python3 experiments/error_analysis.py
python3 experiments/plot_results.py
```

实验前可重置沙箱样例文件：

```bash
python3 scripts/reset_sandbox.py
```

基础测试集评估：

```bash
python3 experiments/run_eval.py
```

本地规则 fallback 基线：

```bash
python3 experiments/run_eval.py --force-fallback
```

泛化表达测试集评估会分别统计 LLM 请求模式和 fallback 模式：

```bash
python3 experiments/run_generalization_eval.py
```

安全攻击分层测试：

```bash
python3 experiments/run_security_eval.py
```

消融实验：

```bash
python3 experiments/run_ablation.py
```

LLM 模式是“请求使用 LLM”的模式；只有结果中的 `source` 出现 `llm`，或 summary 中 `effective_llm_count > 0`，才算真正调用了 API。如果 LLM 配置缺失或 API 调用失败，系统会安全降级到 fallback，并输出 `warning: LLM not actually used.`。

fallback 是确定性规则基线，通常在标准表达上延迟更低、结果更稳定。`safety_rule` 表示输入级安全规则在规划前直接拦截。

阶段耗时字段 `planning_ms`、`safety_ms`、`tool_ms`、`total_ms` 由实验脚本对规划器、安全护栏和工具调用进行近似计时，用于报告中的效率分析。

`no_safety_guard_dry_run` 和 `no_confirmation_dry_run` 均为 dry-run 消融版本；它们不会执行真实危险命令，也不会执行 sandbox 外写操作。

运行后生成：

```text
results/eval_results_llm.csv
results/eval_results_fallback.csv
results/metrics_summary_llm.csv
results/metrics_summary_fallback.csv
results/metrics_summary_llm.json
results/metrics_summary_fallback.json
results/error_cases_llm.csv
results/error_cases_fallback.csv
results/generalization_eval_results_llm.csv
results/generalization_eval_results_fallback.csv
results/generalization_eval_results.csv
results/generalization_metrics_summary_llm.csv
results/generalization_metrics_summary_fallback.csv
results/generalization_metrics_summary.csv
results/generalization_metrics_summary_llm.json
results/generalization_metrics_summary_fallback.json
results/generalization_error_cases_llm.csv
results/generalization_error_cases_fallback.csv
results/security_attack_results.csv
results/security_attack_summary.csv
results/security_attack_summary.json
results/security_error_cases.csv
results/ablation_results.csv
results/ablation_summary.csv
```

生成图表：

```bash
python3 experiments/plot_results.py
```

图表输出到：

```text
results/figures/
```

主要图表文件包括：

```text
results/figures/standard_llm_vs_fallback_metrics.svg
results/figures/generalization_llm_vs_fallback_metrics.svg
results/figures/standard_vs_generalization_success.svg
results/figures/security_attack_block_rates.svg
results/figures/ablation_results.svg
results/figures/stage_latency_breakdown.svg
results/figures/source_distribution.svg
```
