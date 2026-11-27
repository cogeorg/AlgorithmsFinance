# Assignment 1 — LiuHaina

当前工作目录为课程仓库中的 `Submissions/LiuHaina/Assignment1/`。后续实现、测试、实验和报告均放在此目录。

## 当前进度

- 已完成统一接口、独立预期测试、Version A 列表基础版和 Version B 价格堆改进版。
- 全部 63 项测试通过，包含 A/B 原有测试、边界回归、堆清理、随机流对比与测量边界测试。
- 两版可通过同一回放命令选择；原有共享测试和 Version A 实现未修改。
- 已完成正式性能实验并核查：主矩阵450次回放尝试，360次完成、90次超时；另保存180次计划的大额卖出记录。
- 已保存约229万条逐事件延迟，以及独立内存和操作诊断。
- 已完成离线仪表盘 `dashboard.html` 和英文报告 `REPORT.md`，均读取/引用保存的证据。

## 先打开仪表盘

在 Finder 中双击本目录的 `dashboard.html`，或在 VS Code 的仓库根目录终端执行：

```sh
open Submissions/LiuHaina/Assignment1/dashboard.html
```

这是离线单文件页面，无需启动服务、安装依赖或重跑实验。在 VS Code 左侧直接点击 HTML 通常显示源代码；用上面的命令可在默认浏览器中查看。

顶部筛选控制场景、种子和详细规模；曲线展示三个规模。大额卖出固定seed42，使用独立的价格档数/卖出比例筛选。构建、reset和sell成本单列；停止及未运行项不会画成零。Raw records可分页查看完整重复、打开原始JSON详情和下载当前筛选的CSV。

英文报告在 `REPORT.md`。测量版尚未commit，报告区分了Git基础提交与实际源码指纹，未把基础提交误作提交版本。

## 运行

在仓库根目录的 VS Code 终端执行：

```sh
cd Submissions/LiuHaina/Assignment1
python3 -B -m unittest discover -s tests -v
python3 -B -m lob.replay data/worked_example.jsonl
python3 -B -m lob.replay data/worked_example.jsonl --version b
```

撮合、生成器和构建器仅需 Python 标准库，使用 Python 3.11 或更新版本。正式测量及含deadline的完整测试使用POSIX信号定时器，需要macOS或Linux；Windows可用WSL。基准版本记录和提交前检查还需Git命令行。Node/Chrome仅用于可选的界面开发检查。

官方示例预期依次成交 `b1:1、b2:1、b3:3、b4:1 BTC`；收入 `359400.0000000000` 美元；`b4` 剩余 4 BTC，`a1` 不变。

## 文件导航

- `lob/version_a.py`：基础版撮合实现。
- `lob/version_b.py`：价格堆、FIFO队列与活跃ID索引改进版。
- `lob/contract.py`：统一接口。
- `lob/replay.py`：JSONL/gzip 事件回放。
- `tests/test_orderbook.py`：原有共享测试及 A/B 逐事件对比。
- `tests/test_version_a_validation.py`：新增基础版边界测试。
- `tests/test_version_b.py`：改进版边界、堆清理、随机流对比测试。
- `verify_versions.py`：逐事件比较文件回放的结果、规范订单簿和序号。
- `TEST_PLAN.txt`：独立预期与手算用例。
- `VERSION_A_NOTES.txt`：基础版伪代码、不变量及复杂度分析。
- `VERSION_B_NOTES.txt`：改进版结构、清理策略、伪代码、不变量及复杂度。
- `REVISION.md`：修改理由、限制和 AI 使用记录。
- `generate_orders.py`：作业提供的独立合成输入生成器。
- `benchmark.py`、`benchmark_worker.py`：串行、隔离的正式测量与资源监管。
- `BENCHMARK_METHODS.md`：计时/延迟/内存边界、停止规则与复现说明。
- `REPORT.md`：英文报告，覆盖规格、正确性、复杂度、内存、实测瓶颈、修订与限制。
- `dashboard.html`：可双击打开的离线仪表盘。
- `dashboard/`：可编辑的界面模板、CSS和JavaScript源文件。
- `tools/build_dashboard.py`：仅从保存结果构建仪表盘。
- `tools/validate_dashboard.py`：检查嵌入数据、分布样本数、源码指纹与浏览器证据。
- `tools/preflight_submission.py`：不暂存文件，在排除忽略文件的副本中检查复现流程。
- `SUBMISSION_CHECKLIST.md`：逐项要求及尚未执行的最终提交步骤。
- `results/benchmark/FINDINGS.md`：从保存数据生成的实测结果摘录。
- `results/benchmark/raw_results.csv`、`raw_results.jsonl`：原始测量表。
- `results/benchmark/summary.json`、`validation.json`：中位数和完整性核查。
- `README.txt`：详细接口与规格约定。
- `evidence/`：红灯阶段、基础版及迁移验证记录。

## 文件级正确性复核

```sh
python3 -B verify_versions.py data/worked_example.jsonl --out evidence/parity_worked.json
```

同一命令支持多个 JSONL/gzip 路径；将提供的五类 `.jsonl.gz` 路径作为参数可重现样例对比。此脚本在每个事件后构造两版快照，属于正确性检查，不能用其耗时作为引擎基准。

## 性能实验

```sh
python3 -B benchmark.py --smoke --out work/smoke_results
python3 -B benchmark.py --out results/benchmark --phase-limit 5 --rss-mib 512
python3 -B tools/validate_benchmarks.py
python3 -B tools/summarize_findings.py
```

主矩阵覆盖五类场景、1,000/10,000/100,000事件、种子42/43/44和两版，每组五次计时。时间、延迟、内存分开测量，单阶段上限5秒、进程RSS预算512MiB；未完成项保留原因而非估造时间。

本机seed42的mixed 10,000事件回放中位数：A约784ms，B约14.9ms；cancel_churn 100,000事件中A约106ms，B约110ms，说明改进并非对所有场景占优。完整数据和边界见方法说明及结果摘录。

百万事件mixed已在相同预算下尝试：A先发生回放超时，之后RSS超限；B也因RSS超限停止，没有完整百万事件回放结果。RSS预算包含输入，不将该结果解释为单独的撮合容量。

`work/`内的生成输入被忽略，包括百万事件文件。`input_manifest.json`保留全部46个输入的生成命令及校验和。清洁环境可重建同一输入；不同机器/Python版本的计时自然可能不同。benchmark会拒绝将不同代码指纹混入同一结果目录；需要重新测量变更版本时，请另选`--out`目录。

若希望在本机实际重新测量一遍，而不是恢复已保存的完成任务，使用新的结果目录，例如：

```sh
python3 -B benchmark.py --out results/local_run --phase-limit 5 --rss-mib 512
python3 -B tools/validate_benchmarks.py --results results/local_run
```

直接打开现有仪表盘不需要生成`work/`输入；仅在核验输入校验和或重跑测量时需要按manifest命令重建它们。

## 重建与核查仪表盘

从本作业目录运行：

```sh
python3 -B tools/build_dashboard.py
```

该命令只读取已有结果，将完整原始表和延迟分布嵌入HTML，不导入撮合引擎或启动实验。构建后的页面不读取网络资源。原始2538条测量记录保留，90组延迟分布共2292107个样本，无抽样丢弃。

可选的开发界面检查需要Node.js及本机Chrome，不是运行作业/查看页面的依赖：

```sh
node tools/qa_dashboard.mjs
python3 -B tools/validate_dashboard.py
```

界面检查遍历180组全局筛选与18组大额卖出筛选，检查详情、分页、CSV下载、内存切换、浏览器异常及390px手机宽度。测试使用专用`work/dashboard-qa/`配置；受限沙箱内可能需要额外浏览器执行权限。证据保存在`evidence/dashboard_browser_qa.json`及`dashboard_data_validation.json`。重建后HTML指纹会改变，需重新做界面检查才能生成与该版本对应的新证据。

当前实现、实验、仪表盘与报告已齐备，尚未形成最终提交commit。查看结果无需重跑实验。

## 新克隆中的保存结果检查

生成输入按要求不纳入提交。没有本地`work/benchmark_inputs/`时，可直接检查已提交的测量记录、分位数和源码指纹：

```sh
python3 -B tools/validate_benchmarks.py --skip-input-check --out work/saved_results_audit.json
python3 -B tools/validate_dashboard.py
```

第一条明确跳过未携带输入的SHA-256重算，将该项记为“未检查”，其余记录检查仍执行；结果写到单独文件，保留原始`results/benchmark/validation.json`。`--skip-input-check`必须搭配`--out`，防止将原始完整验证记录误覆盖。若要重新验证输入本身，请先按`input_manifest.json`生成输入，再执行不带跳过选项的验证。

## 提交前复现检查

```sh
python3 -B tools/preflight_submission.py
```

脚本只读取Git候选文件列表，将排除`work/`和其他忽略文件的内容复制到临时副本，在副本中验证63项测试、两版示例、无生成输入的保存结果检查、仪表盘精确重建及10个小规模基准组合的50次完整回放。临时副本检查结束后清理，日志保留在`evidence/submission_review/`。它不执行`git add`、commit、push或正式大规模实验。

本次已通过。接下来需要你审阅报告与页面；最终commit及其标识、向课程仓库提交仍未执行，须得到授权后再进行。

未暂存、提交或推送。现有 `Submissions/LiuHaina/` 中的其他作业保持原样。
