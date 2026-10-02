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

探索版另提供 `frontend/calendar.html`：

- Mag 7 可点击月历
- 正式追踪 / 历史验证双模式
- Preview / Aftercheck 研究卡片
- 模拟时间推进按钮，用于验证完整财报流程
- 默认 `index.html` 会进入该日历页

## 日期同步机制

`backend/sync_mag7_calendar.py` 不使用 LLM 判断日期：

1. 以逐项核验过的 2024 年历史日期作为稳定种子；
2. 使用 Nasdaq earnings-surprise 接口校准每家公司最近四次已发布日期；
3. 扫描未来 120 天的 Nasdaq earnings calendar，未来事件统一标记为 `estimated`；
4. 保存日期来源、置信状态、更新时间和同步错误；
5. GitHub Actions 在工作日北京时间约 09:37 和 21:37 自动刷新，也支持手动运行。

当前正式日历包含 2024-01-01 以来的已发布事件，并展示未来预计事件。预计日期可能调整，最终应以公司 IR 公告为准。

日期阶段的定时任务不调用 LLM。旧 Microsoft 研究脚本仍保留，但已从自动工作流暂停，待 Preview / Analysis 阶段统一调整后再启用。

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
python -m unittest discover -s tests -v
```

Paratera 为可选配置：

```powershell
$env:PARATERA_API_KEY = "..."
$env:PARATERA_BASE_URL = "https://llmapi.paratera.com"
$env:PARATERA_MODEL = "DeepSeek-V4-Flash"
python .\backend\sync.py
```

## 数据状态

- `confirmed`：公司 IR 正式公告
- `estimated`：第三方预计日期
- `reported`：结果已发布
- `not_announced`：公司尚未公布下一次日期
- `source_error`：来源访问或解析失败

模型不是事实来源。页面会分别展示公司 IR 来源、数据更新时间与研究生成模式。
