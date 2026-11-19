# 季度研究资料包

自动文章只消费已核对的资料包。路径为 `<ticker>/<YYYYQn>/preview.json` 或 `analysis.json`。

```json
{
  "cutoff": "2026-11-19T10:00:00+08:00",
  "sources": ["https://公司官方财报或监管文件的直接链接"],
  "facts": ["逐项核对过的事实、单位、财年、季度与口径"],
  "official_release_confirmed": true
}
```

`official_release_confirmed` 只用于 Analysis。Preview 的资料截止时间必须早于对应财报发布日期。资料包还记录 `verification_status`：`source_review_pending` 和 `official_source_missing` 不会触发模型；`official_release_text_collected`、`official_filing_text_collected` 或 `manual_verified` 可以生成待审阅草稿。没有合格资料包或模型凭证时，试用版保留现有 Markdown。人工稿默认优先，自动更新不会覆盖。

Intel、三星和 SK 海力士已有官方公告采集器；十家美国上市公司的 SEC 通道已接入，但当前本机对 SEC 返回 HTTP 403，部分公司 IR 也禁止直接抓取。因此尚不能宣称 13 家完整研究文章已实现无人值守更新。日历同步与文章生成是两个独立状态。
