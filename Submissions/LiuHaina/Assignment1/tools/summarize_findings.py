"""Build a short, traceable findings note from SAVED measurements only."""
import argparse
from collections import Counter
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results",type=Path,default=ROOT/"results/benchmark")
    args = parser.parse_args()
    folder = args.results
    rows = [json.loads(s) for s in (folder/"raw_results.jsonl").read_text().splitlines()]
    summaries = json.loads((folder/"summary.json").read_text())
    settings = json.loads((folder/"settings.json").read_text())
    def find(phase,version,scenario,count,levels=1000,sale_percent=None):
        return next((r for r in summaries if r["phase"]==phase and r["version"]==version
            and r["scenario"]==scenario and r["event_count"]==count and r["seed"]==42
            and r["levels"]==levels and r.get("sale_percent")==sale_percent),None)
    def timing(row):
        if row is None:
            return "未测"
        if row["median_elapsed_seconds"] is None:
            return "未完成，见停止状态"
        label=f"{row['median_elapsed_seconds']*1000:.3f}"
        if row["completed_repeats"]!=5:
            label+=f"（仅{row['completed_repeats']}/5完成）"
        return label
    primary = [r for r in rows if r["phase"]=="replay" and r["event_count"] in settings["sizes"]]
    lines=["# 性能实验结果摘录", "",
        "以下结论由保存的原始结果生成，不重新运行实验。时间采用毫秒；表中仅展示 seed42，完整种子42/43/44及全部原始重复见主结果表。",
        "",f"每测量阶段上限 {settings['phase_limit_seconds']} 秒，整个工作进程 RSS 预算 {settings['rss_limit_bytes']//1024**2} MiB。停止运行不作为完成结果，也不外推其完整耗时。",
        "", "## 完成情况", "",f"主矩阵共记录 {len(primary)} 次引擎回放尝试：`{dict(Counter(r['status'] for r in primary))}`。每个组合的五次记录均保留。",
        "", "## 完整回放", "", "| 场景 | 事件数 | A 中位数 ms | B 中位数 ms |", "|---|---:|---:|---:|"]
    for scenario in settings["scenarios"]:
        for count in settings["sizes"]:
            lines.append(f"| {scenario} | {count:,} | {timing(find('replay','A',scenario,count))} | {timing(find('replay','B',scenario,count))} |")
    lines += ["", "这里只比较相同输入。事件总量不是活跃订单量：cancel_churn 在高 M 下仍只保留极小活跃簿；mixed/sweep 的成交量和价格分布也不同，不能只按 M 将五种场景混合拟合。",
        "", "## 延迟和撤单后内存", "", "| 版本 | 场景 | M | median µs | P95 µs | P99 µs |", "|---|---|---:|---:|---:|---:|"]
    for version in ("A","B"):
        for scenario in ("buildup","mixed","cancel_churn"):
            r=find("latency",version,scenario,100000)
            if r and r["completed_repeats"]:
                lines.append(f"| {version} | {scenario} | 100,000 | {r['median_seconds']*1e6:.3f} | {r['p95_seconds']*1e6:.3f} | {r['p99_seconds']*1e6:.3f} |")
            else:
                lines.append(f"| {version} | {scenario} | 100,000 | 未完成 | — | — |")
    lines += ["", "P95/P99使用nearest-rank；延迟在独立仪表运行中测得，不是吞吐量倒数。完整逐事件数据、类型分组和早/晚窗口见 latency 文件及 raw/summary 表。", ""]
    for version in ("A","B"):
        r=find("memory",version,"cancel_churn",100000)
        if r and r.get("traced_current_bytes") is not None:
            lines.append(f"- {version}：100,000次撤单交替事件结束后，当前增量traced分配 {r['traced_current_bytes']:,.0f} 字节，峰值 {r['traced_peak_bytes']:,.0f} 字节。包括小探针缓存及当次返回结果，排除预加载输入的旧分配。")
    lines += ["", "这些字节不是纯订单簿大小，也不是进程RSS；不能将最后当前分配与0活跃订单直接等同。", "", "## 独立大额卖出", "",
        "| 初始买单数 | 可用价格数 | 卖出比例 | A 中位数 ms | B 中位数 ms |", "|---:|---:|---:|---:|---:|"]
    for count in (1000,10000,100000):
        for levels in (4,1000):
            for ratio in (10,100,200):
                lines.append(f"| {count:,} | {levels} | {ratio}% | {timing(find('individual_sale','A','liquidation',count,levels,ratio))} | {timing(find('individual_sale','B','liquidation',count,levels,ratio))} |")
    lines += ["", "每次从未修改的模板深拷贝出新簿；上述表仅为sell阶段。模板构建和每次reset均在原始表单独计时，不应将它们视作免费。构建超限时后续sale没有测量值。所有完成sale逐笔通过独立价格/FIFO前缀预期检查。",
        "", "## 瓶颈解释", ""]
    traced = [r for r in rows if r["phase"]=="operation_counts" and r["scenario"]=="buildup"]
    for r in traced:
        selected=[x for x in r["line_counts"] if ('if any(' in x["source"] or 'for resting in self._orders' in x["source"] or 'if event["order_id"] in self._orders' in x["source"])]
        for item in selected:
            lines.append(f"- {r['version']}，前{r['events_processed']}个事件：`{item['source']}` 对应源码行记录 {item['executions']:,} 次line事件。")
    lines += ["", "A每次提交既扫描活跃ID，又扫描maker候选，再过滤活跃列表；在被动建簿场景中，虽然F=0，仍反复处理不断增大的B。B用活跃ID字典及价格队列避免这些整簿扫描。上述是行追踪事件数，并不等于CPU指令或统一单位的容器操作数。",
        "", "改进不保证每种操作都更快：小活跃簿的撤单场景中，A的短列表与B的多重索引维护开销不同；一次性扫完整个大买盘时，A可以一次排序后顺序扫描，而B逐个维护队列和索引。判断输赢应查看对应场景、N/P/F及实测值。",
        "", "## 百万事件尝试", ""]
    million=[r for r in rows if r["event_count"]==1000000 and r["phase"] in ("worker","replay")]
    if million:
        for version in ("A","B"):
            subset=[r for r in million if r["version"]==version]
            lines.append(f"- {version}：`{dict(Counter(r['status'] for r in subset))}`。未记录完整回放的重复没有完整引擎耗时，RSS预算覆盖输入及引擎全部分配，不能据此隔离判断撮合容量。")
            observed=[r for r in subset if r["phase"]=="replay" and r.get("events_processed") is not None]
            for r in observed:
                lines.append(f"  已观测回放重复{r['repeat']}：完成前缀 {r['events_processed']:,} 个事件，{r['elapsed_seconds']:.3f}秒后停止；不是完整百万事件结果。")
    else:
        lines.append("本次未请求百万事件尝试。")
    lines += ["", "## 证据与限制", "",
        "完整原始重复、延迟、内存、停止原因、设置和输入校验和均在同目录；validation.json检查覆盖范围、代码/输入指纹、中位数及分位数。当前为单机、串行、受限时长实验，尚未制作仪表盘。",
        "", "代码未提交，实际测量版本由settings.json中的源码SHA-256映射标识；Git基础提交不代表这些未提交文件。"]
    (folder/"FINDINGS.md").write_text("\n".join(lines)+"\n")
    print(f"Wrote {folder/'FINDINGS.md'}")


if __name__=="__main__":
    main()
