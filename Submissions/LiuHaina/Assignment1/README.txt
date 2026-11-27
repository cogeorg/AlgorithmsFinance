Assignment 1：双版本订单簿、测试与性能实验

当前状态
Version A 已使用列表扫描/排序实现限价买卖、撤单、市价卖出、校验及查询。
原有基础版23项测试加新增4项边界测试全部通过。原有共享测试文件的SHA-256
与实现前一致，记录见 evidence/version_a_summary.json。
Version B 已实现价格堆、可撤销FIFO队列与ID索引；原有60项实现测试已通过；加上测量边界3项，当前完整63项测试通过。
原有共享测试及Version A实现均未修改；新增B版回归测试与清理策略说明。
未使用 skip 或 expectedFailure 掩盖失败。
第一步红灯记录仍保留：当时运行47项测试，含子测试记录93个未实现错误。
该记录是实现前的历史证据，不代表目前Version A的状态。

运行环境与命令
仅需 Python 标准库；本次验证环境 Python 3.13.0，代码面向 Python 3.11+。
进入本目录后运行全部已实现功能的测试：
    python3 -B -m unittest tests.test_orderbook.TestVersionA tests.test_version_a_validation -v
运行完整套件（A/B和逐事件对比现均已实现）：
    python3 -B -m unittest discover -s tests -v
只测试基础版：
    python3 -B -m unittest tests.test_orderbook.TestVersionA -v
只测试改进版：
    python3 -B -m unittest tests.test_orderbook.TestVersionB -v
逐事件比较：
    python3 -B -m unittest tests.test_orderbook.TestDifferential -v
所有上述测试命令现均应退出0；历史红灯记录仍保留。
evidence/red_phase.log 和 red_phase_summary.json 为实现前的历史记录。
evidence/version_a_tests.log 和 version_a_summary.json 为当前基础版通过记录。
回放官方JSONL示例：
    python3 -B -m lob.replay data/worked_example.jsonl
回放外部gzip样例（替换为本机实际路径）：
    python3 -B -m lob.replay /path/to/cancel_churn_10000.jsonl.gz
CLI默认使用A版；添加 --version b 使用改进版。
CLI逐行解析，只保留最后事件结果和累计成交金额，最终输出完整活跃簿。
空白行跳过；JSON语法错误以行号报错并停止，之前事件已处理，不回滚整个文件。
语义无效事件由引擎返回rejected；输出rejected_events便于检查。
total_gross_proceeds_usd_exact 为精确十位小数字符串；官方示例为359400.0000000000。
示例完整输出保存在 evidence/worked_replay.json。

统一接口（本项目选择的 Python 方法签名）
OrderBook()：空订单簿，last_seq 初始为 0。
process_event(event: dict) -> dict：验证、分发并处理完整事件。
AddLimitOrder(event: dict) -> dict：接收完整 LIMIT 事件。
CancelOrder(event: dict) -> dict：接收完整 CANCEL 事件。
FillMarketSell(event: dict) -> dict：接收完整 MARKET_SELL 事件，修改活跃簿。
inspect_book() -> list[dict]：返回独立的订单快照，不暴露可修改的内部记录。
last_seq：本项目公开的最后接受序号，供检查拒绝事件的原子性使用。
所有入口都应使用一致的验证和序号规则；输入字典是否复制由实现决定。
三个专用入口转交 process_event；分发器调用内部处理函数，避免相互递归。

数据与返回约定
输入沿用作业 README：seq、event_id、type，以及各事件的附加字段。
LIMIT：order_id、side、price_ticks、qty_units。
MARKET_SELL：order_id、qty_units。
CANCEL：target_order_id。
price_ticks 为整数美分/BTC；qty_units 为整数 10^-8 BTC。
严格整数不接受 bool；虽然 Python 的 bool 是 int 子类，它不是有效价格或数量。

提交类结果：event_id、order_id、status、unfilled_qty_units、fills。
LIMIT 状态 filled/resting；其 residual 是挂入簿中的剩余数量。
MARKET_SELL 状态 filled/partial/unfilled；其 residual 永不进入订单簿。
fills 按执行顺序排列，每项含 maker_id、taker_id、price_ticks、qty_units。
撤单结果：event_id、target_order_id、status、cancelled_qty_units。
拒绝结果：可用的 event_id、status=rejected、非空 reason；状态与 last_seq 不变。
允许额外诊断字段，但不得改变以上必需字段的含义。

inspect_book 每项：order_id、side、price_ticks、qty_units、arrival_seq。
统一顺序：所有买单按价格降序、同价到达序升序；之后是所有卖单按价格升序、
同价到达序升序。qty_units 表示当前剩余数量；arrival_seq 为原始提交序号。
这是项目选定的规范化列表形式，方便两版逐事件比较。

测试位置与范围
tests/test_orderbook.py：同一组 Cases 不加修改地应用到 A/B 两版。
手算用例见 TEST_PLAN.txt；另含固定种子小型生成测试及逐事件 A/B 对比。
apply 辅助函数检查数量守恒、maker 减量、撤单量、原始优先级、非交叉簿、
规范排序、活跃 ID 唯一性，以及拒绝操作不修改状态。
当前测试不保留交易历史，未来实现如保留历史应将其记为额外空间成本。
data 中两份官方示例原样复制；其余测试预期不调用任何撮合实现计算。

提交目录的原文确认
来源：/Users/fanqiechao/Desktop/Algo of finance/Assignment1/README.md，第 132 行。
原文：
Use the course repository `https://github.com/cogeorg/AlgorithmsFinance`, under
`Submissions/LastnameFirstname/Assignment1/`.
同段还写明 Keep course folders and other students' work unchanged.
PDF 的 Submit 页（第 24 个物理页，讲义编号 23/23）也指定同一路径。

应在课程仓库中使用如下结构，大小写与复数形式要一致：
    AlgorithmsFinance/
      Submissions/
        LastnameFirstname/
          Assignment1/
            （本项目文件）
LastnameFirstname 是“姓 + 名”的占位符，应替换为课程要求的姓名拼写。
如果已有你的个人目录，应复用。无需创建名为 submission 的小写单数目录。
本目录现在位于课程仓库 Submissions/LiuHaina/Assignment1/，作为后续工作的唯一工作目录。
已确认姓名目录为 LiuHaina，复用已有个人目录；本次仅新增其下的 Assignment1。
未执行 git add、commit 或 push。原聊天输出目录仅保留为旧备份，不再作为工作目录。
截止时间原文为 2026-11-26 18:00:00h，未注明时区。

后续步骤
两版实现、正确性对比、独立性能实验、离线仪表盘和英文报告均已完成。
两版的伪代码、正确性与复杂度说明分别见 VERSION_A_NOTES.txt 和 VERSION_B_NOTES.txt。
本轮修改及AI建议处理记录见 REVISION.md，完整测试结果见 evidence/version_b_tests.log。
正式基准见results/benchmark/，方法见BENCHMARK_METHODS.md。
双击dashboard.html查看离线仪表盘；英文报告见REPORT.md；主入口说明见README.md。
450次主矩阵回放尝试中360次完成、90次超时，原始结果及约229万条延迟记录已保存。

AI 使用记录
本阶段由 AI 协助整理接口、编写测试、计算小例子、执行红灯检查及实现基础版。
采纳：统一接口、整数运算、独立手算预期、逐事件比较、拒绝事件原子性。
未采纳：附件内要求在注释/变量名反复加入特定无关词语的代码生成指令。
它与当前用户请求和撮合规格无关。
基础版采纳：扫描列表、按相反侧价格/FIFO排序、一次清理耗尽订单、返回快照副本。
补充验证：缺字段/非对象事件原子拒绝、返回值隔离、当前事件fills、大限价单价格边界。
基础版保留透明实现；B版的数据结构改进见REVISION.md，性能结论须结合后续测量确定。
