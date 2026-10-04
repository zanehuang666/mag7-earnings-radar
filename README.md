# Mag 7 Earnings Radar

当前交付版本：`2026-10-04 · V12`

公开网页：https://zanehuang666.github.io/mag7-earnings-radar/calendar.html

这是一个面向 Mag 7 的可审计财报跟踪 Demo。正式日历覆盖 2024-01-01 至今的 77 场已发布财报，并展示未来预计/推算日期；每场历史财报都有财报前 Preview、财报后 Analysis、EPS 实际值与公开一致预期、相对 QQQ 的 1 日/5 日表现、来源和风险边界。

## 快速验收

1. 打开公开网页，点击任意日期或公司；
2. 在公司历史列表中打开任意一次财报，切换 Preview / Analysis；
3. 打开“历史验证”，点击“运行完整时间模拟”，观察 Microsoft FY26 Q2 从 T-1 Preview 推进至 T+1 Analysis；
4. 在正式日历点击 CPI、非农、FOMC 或 PCE，查看已公布数据和来源；
5. 点击“检查最新数据”，对比浏览器缓存和线上快照时间。

## 最终运行文件

| 分类 | 文件 | 版本/时间 | 内容 |
|---|---|---|---|
| 前端 | `frontend/calendar.html` | V12 / 2026-10-04 | 主网页、日历、研究卡片、行情图、宏观事件和历史模拟 |
| 前端 | `frontend/index.html` | V12 / 2026-10-04 | GitHub Pages 稳定入口，跳转至主网页 |
| 财报数据 | `frontend/data/mag7.json` | 自动更新 | 财报日期、状态、未来日期和同步审计 |
| 全量研究 | `frontend/data/mag7_research.json` | V12 / 增量更新 | 77 场历史研究 + Microsoft 深度覆盖；日常不重复调用模型 |
| 深度研究 | `frontend/data/msft_research.json` | V10 / 按需更新 | Microsoft 三期经来源核验的深度样本 |
| 行情 | `frontend/data/market_qqq.json` | 自动更新 | QQQ 与 Mag 7 日线快照 |
| 宏观 | `frontend/data/macro_events.json` | 自动更新 | 已公布的 FOMC、CPI、非农和 PCE |
| 搜索 | `frontend/data/us_earnings_candidates.json` | 自动更新 | 自选股候选索引与 AEHR 验证样本 |
| 同步 | `backend/sync_mag7_calendar.py` | V10+ | 日期、状态、自选候选和预测层级 |
| 同步 | `backend/sync_market_data.py` | V8+ | 免密钥行情快照 |
| 同步 | `backend/sync_macro_events.py` | V11 | 已公布宏观事件 |
| 研究 | `backend/sync_msft_research.py` | V10 | Microsoft 深度研究及 Paratera 可选压缩 |
| 研究 | `backend/sync_mag7_research.py` | V12 | 全量历史研究的确定性增量缓存 |
| 自动化 | `.github/workflows/sync-and-deploy.yml` | V12 | 抓取、研究更新、测试、提交数据和 Pages 发布 |
| 测试 | `tests/test_contract.py` | V12 | 数据契约、覆盖率、来源、UI 和低 token 约束 |
| 配置 | `.env.example` | 2026-10 | 可选 Paratera 环境变量模板，不包含密钥 |
| 版本 | `VERSION.json` | V12 / 2026-10-04 | 交付版本和覆盖范围 |

更完整的文件说明见 `docs/final/2026-10-04_V12_最终文件说明_README.md`；新对话接手时优先阅读 `docs/final/2026-10-04_V12_完整项目交接说明.md`。

## 更新与 token 策略

GitHub Actions 的目标触发时间为：

- 工作日北京时间约 09:37、21:37；
- 周末北京时间约 09:37。

GitHub 的 schedule 属于尽力调度，实际启动可能延迟甚至偶发丢弃。页面显示的是实际快照时间，不把目标 cron 时间伪装成成功时间。

日历、行情、宏观和 77 场基线研究均不调用 LLM。`sync_mag7_research.py` 会保留已经成熟的历史记录；正常更新只为新出现的已发布财报生成确定性记录，并在 5 个交易日行情窗口尚未完整时小范围补算该新事件，绝不重写全部历史。Microsoft 深度研究默认复用缓存，只有 T-1 或手动要求时才允许 Paratera 调用，并受单次/全批调用上限约束。

## 本地验证

```powershell
python .\backend\sync_mag7_calendar.py
python .\backend\sync_market_data.py
python .\backend\sync_macro_events.py
python .\backend\sync_msft_research.py
python .\backend\sync_mag7_research.py
python -m unittest discover -s tests -v
python -m http.server 8765 --directory frontend
```

然后打开 `http://127.0.0.1:8765/calendar.html`。

## 资料分区

- `docs/final/`：最终说明和新对话交接文件；
- `docs/process/`：执行器错误、早期探索、分支试验和 V1 旧文件，不参与正式运行；
- `frontend/`、`backend/`、`tests/`、`.github/`：正式运行与测试文件。

Research demo only. Not investment advice.
