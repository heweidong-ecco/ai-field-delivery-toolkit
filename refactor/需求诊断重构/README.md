# 需求诊断模块 · 重构归档

> 统一的版本归档文件夹。记录本模块从当前实现(v0)到重构(v1.x)的完整决策过程、方案与版本历史,便于回溯与审查。

## 目的

重构需求:把「① 需求诊断」从**单次 LLM 打分**(无价值,不如直接用 DeepSeek 网页对话)重构为**多 Agent 对抗评审 + 三层循环 + 版本化交付**的 Agent 流程。本文档保证决策不过期、不遗忘。

## 版本时间线

| 版本 | 状态 | 说明 |
| ---- | ---- | ---- |
| v0 | 已归档 | 重构前实现:单次 LLM 打分 + 规则兜底 + 人工复核 + 报告 v2.0 |
| v1.0 | 方案已定 | 重构共识:多 Agent(Generator/Critic/Reviewer)对抗 + 三层循环 + 置信度 + 预算 + JSON 档案 |
| 一期 | ✅ **已完成** | 多 Agent 对抗 + 人工复核 + AI 再评分 + 定稿单版报告(2026-08-29 落地) |
| 二期 | ✅ **已完成** | 版本循环 + 客户反馈文件 + 增量重评 + 档案检索(2026-08-29 落地) |
| v2.0 | ✅ **已完成** | 输出深度重构:三 Agent 无长度限制完整 schema + 全链路留痕 + 报告改为多章节需求文档 + 定稿自动生成交付物 + 多轮累积变厚(2026-08-29 落地,见[更新日志-v2.0.md](./更新日志-v2.0.md)) |
| v2.1 | ✅ **已完成** | 全景可行性 + 对抗评审内联化:5 维保留为「技术可行性」+ Generator 新增 `non_tech_feasibility`/Critic 新增 `non_tech_audit`(商业/组织/集成/合规/风险,每项评估+依据+红黄绿+建议)+ 报告新增第 7 章「整体可行性评估」+ 每维正文内联「对抗评审过程」可读块(2026-08-29 落地,见[更新日志-v2.1.md](./更新日志-v2.1.md)) |
| v2.2 | ✅ **已交付，待甲方验收** | 商务提案章节:新增商务评估 LLM 调用(`run_commercial_proposal`)在定稿时起草「商务提案(供洽谈讨论)」,报告新增第 14 章(投入估算与分期/时间里程碑/甲方乙方责任清单/试点范围与退出机制/替代方案与不做的代价),明确「此为讨论用初步估算,最终以商务洽谈确认为准」,附录顺延 15/16(2026-08-29 交付,见[更新日志-v2.2.md](./更新日志-v2.2.md)) |

## 一期落地内容(2026-08-29)

- `core/llm.py` — 统一 DeepSeek 客户端(chat / chat_json,懒加载,LLMError)
- `diagnosis/agents.py` — Generator / Critic / Reviewer 三角色,边界严格 + 盲审 system prompt
- `diagnosis/archive.py` — run_id JSON 档案(`tmp/web/diagnosis/<run_id>/archive.json`)+ 置信度(一致度)+ 预算计数(≤9)
- `diagnosis/orchestrator.py` — 管线:`start`(Generator+Critic 盲审)/ `review`(人工+Reviewer 盲审)/ `finalize`(强制确认→定稿 v3.0)
- `core/api.py` — 新增 `/diagnosis/start`、`/diagnosis/review`、`/diagnosis/finalize`(旧端点保留兼容)
- `web/` — 诊断页改向导:① 输入需求 → 对抗评审结果+澄清问题 → ② 人工复核+Reviewer 再评分 → ③ 强制确认定稿
- 测试:`tests/test_api.py` 多 Agent 流程 + 置信度 + 预算(注入式),全套 90 通过

## 二期落地内容(2026-08-29)

- `diagnosis/feedback.py` — 客户反馈解析:上传 txt/pdf → pymupdf 提取 → LLM 提炼「客户意见条目」{item, dimension, intent}
- `diagnosis/orchestrator.py` — `add_client_feedback`(归档 + 触达维度)、`next_version`(incremental/full 重评,只动触达维度其余沿用,计算变更清单)、`finalize` 版本化(vN + 相对上一版变更清单)、`get_archive`/`list_runs`
- `diagnosis/archive.py` — `list_run_ids`(档案检索)
- `core/api.py` — `/diagnosis/feedback`(multipart)、`/diagnosis/next-version`、`GET /diagnosis/runs`、`GET /diagnosis/archive/{run_id}`
- `web/` — 定稿后出现「④ 客户反馈 → 生成下一版」面板(上传/粘贴 → 意见条目 → 下一版草稿 + 变更清单)+「档案 / 历史」面板
- 报告升级 `3.1`(含 version / previous_version / changelog / client_feedback)
- 测试:版本循环 v1→反馈→增量重评→v2 + 档案检索,全套 91 通过

## 文件

- [重构方案-v1.0.md](./重构方案-v1.0.md) — 两期完整方案 + 全部拍板决策(权威文档)
- [决策过程-v2.md](./决策过程-v2.md) — **grilling 全程逐字完整对话(提问原文 + 回答原文),决策依据**;v1 为总结版、无依据,已废弃
- [历史版本/v0-当前实现基线.md](./历史版本/v0-当前实现基线.md) — 重构前实现基线

## 归档约定

- 新决策/新版本 → 写新版本号文件,不覆盖旧版
- 实现一期/二期时,先读 `重构方案-v1.0.md`,按验收标准落地
- 一期完成时:更新本 README 状态 + 新增 `历史版本/` 归档
