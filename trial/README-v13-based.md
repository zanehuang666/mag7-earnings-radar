# V13 基础上的扩展日历试用版

打开 `v13-based/trial-offline.html` 查看本地试用页面。`v13-based/calendar.html` 与 `v13-based/data/` 是可部署的静态页面与数据；原有 `mag7-earnings-radar-debug` 和线上 `main` 未被修改。

## 数据与更新

- 原有 Mag 7 数据来自 V13 同步脚本。
- 扩展美股公司 2024 年以来的发布日期来自逐日扫描的 Nasdaq 历史财报日历；`nasdaq-history-2024.json` 保存 754 个已检查工作日的匹配行与各日来源。最近四场的 EPS 结果另来自 Nasdaq `earnings-surprise` 接口；`history-cache.json` 保留原始响应和来源 URL。
- SK hynix 与 Samsung Electronics 的 2024 年以来发布日期来自公司官方季度业绩稿，见 `foreign-history-2024.json`。SpaceX 没有公开的标准季度财报日历，不生成季度事件。
- 扩展公司的未来预计日期复用原有 `us_earnings_candidates.json`，不增加逐公司的未来日历请求。
- 每家扩展美股公司显示四个未来槽位；Nasdaq 收录日期标记为 `estimated`，其余根据历史间隔标记为低置信度 `projected`。推算日期不是财报公告日期。
- 公司研究报告集中在 `v13-based/reports/<ticker>/overview.html`，五类源数据在相邻 `data/`（如有），状态和来源见 `v13-based/data/report_index.json`。第一梯队 13 家均有 HTML：6 家由指定 Skill 的数据合同重建并通过静态检查，2 家为只含 2026Q3 的硬件 Skill 诊断报告，5 家仍为尚未迁入新 Skill 的旧版草稿；均未认定为逐值核实的正式版。
- 第一梯队季度 Preview/Analysis 改为 `research/<ticker>/<YYYYQn>/<stage>.md`，网页从 `data/research_index.json` 读取状态与正文。`seed_markdown_baselines.py` 参考正式版的 Nasdaq 确定性资料层，为 139 场已发布财报的 Preview/Analysis 和 47 个未来 Preview 建立可读 Markdown；其中 321 篇标为“自动资料索引”，不能算逐季核验的完整研究。Google 和 Intel 的 2026Q4 Preview、2026Q3 Analysis 是现有的 4 篇人工样稿。具备官方资料与 Paratera 凭证时，生成流程逐篇将索引升级为完整草稿，保留人工文章。
- 2024 年至今的第一梯队季度事件已建立逐季资料包索引：Intel 11 季、SK hynix 11 季、Samsung Electronics 11 季采集了官方季度公告正文；另外九家上市公司的最近已发布季度均有人工核对官方公告的关键事实资料包。六家公司既有报告数据的其他 2024+ 季度仍是待逐值复核线索，其余季度标明官方正文待补。准确覆盖数量见 `research-coverage.md`。SpaceX 无公开标准季度财报事件。
- `collect_official_packets.py` 从已有研究数据和韩国官方公告建立资料包；`add_latest_official_packets.py` 补入九家上市公司最近一期已核对的官方关键事实；`collect_intel_packets.py` 读取 Intel 官方财务新闻归档；`collect_sec_packets.py` 为十家美国上市公司准备 SEC 10-Q/10-K 采集通道。当前本机访问 SEC 及多家 IR 网站返回 HTTP 403，程序记录缺口而不伪造资料。10-K 年报不能自动冒充独立 Q4 季报。
- `prepare_previews.py` 给尚未发布的下一季准备上季资料，也可把已发布季度之前的官方资料封装为“历史资料重建”前瞻输入。重建稿必须明确标识，不能冒充当时发表的预测；Analysis 不把它当成真实同期 Preview 来复核。`research_pipeline.py` 默认每次最多 3 次 Paratera 调用，可用 `RESEARCH_CALL_LIMIT` 调整，按近期 Preview、最近 Analysis、较早季度的顺序排队。
- 本地运行 `./run_research_trial.ps1` 会安全提示输入 Paratera 密钥并构建试用版，密钥不写入文件。已有线上仓库 Actions 引用了 `PARATERA_*` Secrets，但本地环境无法读取 Secrets，试用版也没有单独启用远程定时任务。
- `prompts/quarterly-research.txt` 是新生成提示词。`research_pipeline.py` 只在存在明确官方资料包 `source-packets/<ticker>/<YYYYQn>/<stage>.json` 且配置 `PARATERA_API_KEY`、`PARATERA_BASE_URL`、`PARATERA_MODEL` 时调用模型。资料包须含 `facts`、`sources`、`cutoff`，Analysis 另须 `official_release_confirmed: true`。自动稿标记待核；人工稿永不由定时任务覆盖，自动稿在来源内容变化时归档旧版后更新。
- `update_trial.py` 在日历抓取出现新增上游错误时回滚隔离数据并报错，保留上次试用网页。不能把一次失败的上游请求显示为成功更新。
- 运行 `python update_trial.py` 会在隔离的 `source-snapshot` 中依次执行原有日历、行情、宏观与研究同步，再刷新每天最多一次的新增公司历史缓存，最后重建试用页面。若将试用版部署到独立分支，可沿用正式 workflow 的北京时间工作日 09:37 和 21:37 调度；当前未部署，也未启用远程定时任务。

## 已知边界

- Nasdaq 的 `earnings-surprise` 接口只返回最近四条；完整 2024 年以来的日期必须用逐日历史日历回填。新上市或重组公司只从自身可比较的披露期开始：CoreWeave 与 SanDisk 从 2025 年、Nebius 排除重组前的旧主体记录。
- 日历目标从 2024 年开始；研究 HTML 按各自 Skill 从 FY2021Q1 开始。两者起点不同。
- SpaceX 无公开季度财报日期，保留公司研究页而不编造事件。
- 第一梯队旧 Preview/Analysis 不迁入新 Markdown 数据库。历史 Preview 如能核实前一季已公开资料，可做清楚标记的事后重建；没有可核实的财报前资料时保持空缺，不能使用目标季度结果倒写。自动写作还需要来源资料包与模型凭证；未配置时只刷新状态，不会凭空生成文章。
- 当前自动来源采集尚未覆盖所有 139 个已发布季度；对已采集但未逐值复核的旧数据包，程序仍拒绝调用模型。所有日期虽已生成 Markdown 资料索引，但这些索引不等于完整研究；只有官方正文或人工核对事实加上 Paratera 配置才能升级成自动草稿，草稿仍标注待审阅。
- Google、Microsoft、Amazon 的公司研究 HTML 仍是 cloud-earnings-report Skill 草稿，逐值来源与浏览器视觉尚待验收。
- Google、Microsoft、Amazon、NVIDIA、AMD、美光的五类 JSON 已通过对应 Skill 的数据校验，但来源逐点与浏览器视觉仍待验收。其他七份旧报告尚未按新 Skill 重新构建。
- 当前所有第一梯队上市公司均已接入 2024 年以来可得的历史日历日期，但仍需对每家公司公告与 Nasdaq 历史行做逐季交叉复核。每日两次自动调度需未来将试用版部署到独立分支后才能实际启用和验证。
- 静态 GitHub Pages 页面允许浏览源 JSON；多人直接上传仍需身份验证和审核流程。
