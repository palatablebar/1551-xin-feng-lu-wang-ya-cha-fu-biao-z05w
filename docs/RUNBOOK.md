# AIR / SERVICE运行手册

更换班次或复算派单时使用。先确认 `/health` 返回 `ok`，再检查以下入口和凭证中的 `run_id`。

| 文档或路由 | 用途 |
|---|---|
| `sample_data/duct_checklists_sample.json` | 同时提供拟合、校准、回放和当班的样例 |
| `sample_data/filter_receipts_sample.json` | 换网实测回执样例，覆盖销单、占位与隔离 |
| `GET /api/ductwatch/overview` | 默认额度和样例处置 |
| `POST /api/ductwatch/run` | 用 `capacity` 和 `strategy` 调整派单，也可同时提供 `records` 与 `as_of` |
| `GET /api/ductwatch/stages/<环节>` | 样例的分环节核对，可传相同额度、策略 |

导入 JSON 对象时 `records` 为 1–2500 条单据，`as_of` 为整数工日；默认第 96 日。额度接受 1–60，策略接受 `balanced` 或 `focus`。入站异常保留于第一环节。整批缺少成熟窗口时响应 422 并给出原因。可附 `receipts` 数组（不超过 2500 条）核销已派复标单，回执字段与单据一致；核销结果在响应的 `settlement` 中，不附回执时为 `null`。

```sh
docker compose exec -T app python -m ductwatch.entry evaluate --input sample_data/duct_checklists_sample.json --capacity 9
docker compose exec -T app python -m ductwatch.entry evaluate --receipts sample_data/filter_receipts_sample.json
```

在网页筛选单号、作业区或原因，点击结果中的单号查看完整字段与处置证据。下载 JSON 可检视结果、对照原始资料摘要和模型特征版本。
