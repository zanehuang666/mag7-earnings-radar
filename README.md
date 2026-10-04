# Mag 7 Earnings Radar

当前版本：`2026-10-04 · V13`

- 在线页面：https://zanehuang666.github.io/mag7-earnings-radar/calendar.html
- 历史验证：https://zanehuang666.github.io/mag7-earnings-radar/calendar.html?mode=replay
- 简短项目说明：[`docs/final/2026-10-04_V13_简短项目说明.md`](docs/final/2026-10-04_V13_简短项目说明.md)
- 完整交接说明：[`docs/final/2026-10-04_V13_完整项目交接说明.md`](docs/final/2026-10-04_V13_完整项目交接说明.md)

这是一个可审计的 Mag 7 财报日历与研究 Demo。系统覆盖 2024 年以来 77 场已发布财报，并为当前 28 条未来事件生成结构化 Preview；财报发布后再生成 Analysis。日期、EPS、行情和状态变化由确定性程序处理，AI 只用于受约束的文字压缩。

## 项目结构

| 目录 | 用途 |
|---|---|
| `frontend/` | GitHub Pages 页面及公开 JSON 数据 |
| `backend/` | 日历、行情、宏观数据和研究同步脚本 |
| `tests/` | 数据、来源、研究结构和 UI 契约测试 |
| `.github/workflows/` | 自动同步、测试与 Pages 部署 |
| `docs/final/` | V13 当前交付文档，仅保留正式文件 |
| `docs/process/` | V1–V12 探索、错误记录和历史归档，不参与运行 |

正式运行文件使用稳定名称，不能按版本改名，因为网页和 GitHub Actions 直接依赖这些路径。版本统一记录在 `VERSION.json`、页面标识、研究 JSON 和正式文档中。

## 数据流

```text
Nasdaq 财报日历与 EPS ─┐
公司 Investor Relations ├─> Python 同步与校验 ─> frontend/data/*.json
Yahoo Finance 行情 ─────┤                              │
宏观公开数据 ────────────┘                              └─> calendar.html ─> GitHub Pages
```

主要原则：

- `projected`、`estimated`、`confirmed`、`reported` 严格区分；
- 市场预计不能冒充公司 IR 确认；
- Preview 不使用财报发布后的信息；
- Analysis 只在正式结果可得后生成；
- 模型不能修改数字、日期或来源；
- 生成失败时保留上一份安全快照。

## 自动更新

GitHub Actions 的目标触发时间为北京时间：

- 工作日约 09:37、21:37；
- 周末约 09:37。

GitHub 定时任务可能延迟，页面展示实际快照时间及对应 Actions 运行记录。每次运行依次更新日历、行情、宏观数据、研究缓存，执行契约测试，再提交数据并部署 Pages。

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

打开 `http://127.0.0.1:8765/calendar.html`。

Research demo only. Not investment advice.
