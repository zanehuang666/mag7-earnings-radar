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
