# Mag 7 Earnings Radar

一个面向 Mag 7 财报日历、Preview 与 Aftercheck 的可审计 Demo。

当前版本先以 Microsoft 为完整样例：

- 公司 IR 日期检查
- 历史财报日期回溯
- 正式模式与历史演示模式分离
- Paratera 生成 Preview / Aftercheck
- 无模型调用时保留已核验快照
- GitHub Actions 定时同步
- GitHub Pages 自动发布

## Microsoft 三期深度研究样本

`frontend/data/msft_research.json` 固定展示三期，便于先小范围校准研究质量：

- `2026-01-28 · FY26 Q2`：过往已发布样本；
- `2026-07-29 · FY26 Q4`：最近已发布样本；
- `2026-11-04 · FY27 Q1`：未来预计样本（Nasdaq estimated，Microsoft IR 尚未确认）。

每份 Preview 都保留发布前信息截止时间、公司指引/市场共识、核心观察点、风险和逐项来源；已发布样本的 Analysis 另列预期、实际、差值、管理层指引变化及 MSFT 相对 QQQ 表现。数字、长摘要与引用由确定性数据层锁定，模型只接收两段已核验结论句并压缩 verdict，不能改数字或来源；输出若引入草稿中不存在的数字会被拒绝。未来事件在结果发布前不生成 Analysis，避免把预测写成事实。

为节省 token，`backend/sync_msft_research.py` 默认不调用模型；只有距离事件一天（T-1）或手动运行工作流并勾选 `refresh_research` 时才调用 Paratera，且每个事件最多一次、全批最多三次、单次最多 1,100 output tokens。该编辑任务关闭模型思考模式并请求 JSON 输出；为兼容部分推理模型把唯一文本放在 `reasoning_content` 的情况，正文为空时会读取该字段，但仍执行同样的严格 JSON/字段校验。调试时可把 `research_call_limit` 设为 1，也可用 `research_event_id` 只重试单期。已经通过校验的模型结论会被保留，单次失败不会覆盖它；完全没有可用模型文案时则回退到可审计的已核验快照。

探索版另提供 `frontend/calendar.html`：

- Mag 7 可点击月历
- 正式追踪 / 历史验证双模式
- Preview / Aftercheck 研究卡片
- 模拟时间推进按钮，用于验证完整财报流程
- “自动更新验证台”显示日历、行情与候选索引的真实生成时间，并可绕过缓存检查线上新版本
- AEHR（预计 2026-10-05）作为免 LLM 的短期真实样本：发布后自动从 `estimated` 切换为 `reported`
- 默认 `index.html` 会进入该日历页

## 日期同步机制

`backend/sync_mag7_calendar.py` 不使用 LLM 判断日期：

1. 以逐项核验过的 2024 年历史日期作为稳定种子；
2. 使用 Nasdaq earnings-surprise 接口校准每家公司最近四次已发布日期；
3. 扫描未来 120 天的 Nasdaq earnings calendar，未来事件统一标记为 `estimated`；
4. 对市场日历尚未覆盖的后续季度，依据各公司最近季度间隔生成 `projected` 日期和 ±7 天区间；
5. 公司 IR 正式公告可写入 `confirmed` 层，并覆盖同一季度的预计或推算事件；
6. 保存日期来源、置信状态、更新时间和同步错误；
7. GitHub Actions 在工作日北京时间约 09:37 和 21:37 自动刷新；周末 09:37 运行一次心跳验证，也支持手动运行。

当前正式日历包含 2024-01-01 以来的已发布事件，并展示未来预计事件。预计日期可能调整，最终应以公司 IR 公告为准。

日期阶段的定时任务不调用 LLM。旧 Microsoft 研究脚本仍保留，但已从自动工作流暂停，待 Preview / Analysis 阶段统一调整后再启用。

页面中的日期状态依次为：`projected`（历史节奏推算）→ `estimated`（市场日历预计）→ `confirmed`（公司 IR 正式确认）→ `reported`（已经发布）。每家公司展示四期未来事件。

## 自选股搜索

定时任务同时生成未来 120 天的美股财报候选索引，并为少量明确支持的扩展股票生成“历史 + 推算”档案。用户可以在日历上方输入股票代码：

- 搜索命中后，该股票会出现在公司栏和日历中；
- 普通命中使用市场日历预计日期，后续季度使用简化节奏推算；MU 即使下一期尚未进入未来日历，也可从 Nasdaq 最近四次已发布记录生成四期低置信度推算；
- 自选股保存在当前浏览器的 `localStorage`；
- 自选股同时保留最后一次可用事件缓存；即使某只股票暂时离开未来 120 天索引，在用户主动删除前仍保留在当前浏览器；
- Mag 7 固定且不可删除，其他股票可以点击右侧 `×` 删除；
- 如果未来 120 天没有公开预计日期、也不在受支持历史档案中，页面会拒绝加入，而不是编造日期。

由于 GitHub Pages 是静态网站，浏览器无法直接跨域调用 Nasdaq。候选索引由 GitHub Actions 定时生成，再由页面本地搜索。

Mag 7 使用绿色 `M7` 标签且固定不可删除；新增股票使用紫色 `自选` 标签并保留删除按钮。

## 市场行情

`backend/sync_market_data.py` 无需 API key，通过 GitHub Actions 服务端抓取 QQQ 与 Mag 7 日线并缓存为 `frontend/data/market_qqq.json`。页面把所有序列以 2024 年首个交易日归一为 100；未选公司时七只个股半透明展示，选择公司后只突出该公司与 QQQ，并把已发布财报节点放在对应公司的价格线上。悬停节点可查看当日收盘价、区间表现、相对 QQQ 表现与 EPS 判断。

行情与财报日期使用同一个工作流，在工作日北京时间约 09:37、21:37 更新两次，周末 09:37 额外运行一次心跳。它不是实时行情：Yahoo 当日数据是否已经形成完整收盘值，取决于美股交易时段。抓取失败时保留上一版快照，避免公开页面因临时数据源错误而不可用。

行情图只有已存在结构化 `research.analysis.result_tone` 的事件使用绿/红/橙研究结论色；仅有发布日期或单项 EPS surprise 的其他事件统一显示为空心灰点，避免把单项 EPS 结果误写成完整财报判断。研究卡片和图表均提供明确颜色图例。

浏览器只读取仓库中的静态快照，不会直接请求 Yahoo。该免密钥来源适合小型笔试 Demo，但并非正式 SLA 数据服务；若产品化，应替换为授权行情源并保持相同 JSON 契约。

## 目录

```text
frontend/                 静态网页与发布数据
backend/                  数据同步和 Paratera 调用
tests/                    数据契约测试
.github/workflows/        自动同步、测试与 Pages 发布
```

## 本地更新数据

```powershell
python .\backend\sync.py
python .\backend\sync_mag7_calendar.py
python .\backend\sync_market_data.py
python .\backend\sync_msft_research.py
python -m unittest discover -s tests -v
```

Paratera 为可选配置：

```powershell
$env:PARATERA_API_KEY = "..."
$env:PARATERA_BASE_URL = "https://llmapi.paratera.com"
$env:PARATERA_MODEL = "DeepSeek-V4-Flash"
$env:MSFT_RESEARCH_FORCE = "true"
python .\backend\sync_msft_research.py
```

## 数据状态

- `confirmed`：公司 IR 正式公告
- `estimated`：第三方预计日期
- `reported`：结果已发布
- `not_announced`：公司尚未公布下一次日期
- `source_error`：来源访问或解析失败

模型不是事实来源。页面会分别展示公司 IR 来源、数据更新时间与研究生成模式。
