# 开发计划

## 任务列表

- [x] 起草上位机 ↔ 下位机链路协议（USB CDC）—— 草案 v0.1，待电控组确认
- [ ] **与电控组逐条确认消息表**（`protocol/lower_link.md` §9 的 6 个待确认项）
- [ ] 确认后升为 v1.0 并冻结（走 D2：≥2 人评审 + 兼容性影响评估）
- [ ] 冻结 `WorldSnapshot` 字段清单（A–F 分区）
- [ ] 冻结 `ActionMask` / `Decision` 定义
- [ ] 起草机间态势协议（字段 / 单位 / TTL / 置信度 / 版本协商）
- [ ] 迁入裁判系统消息（`V1.7.0`，7 个）
- [ ] 写两个 mock decider 验证统一签名能容纳规则与 RL

## 当前 Agent State

PLAN_READY

## Before Snapshot

commit hash:   （首次提交）
branch:        main
modified files: （首次初始化）
risk level:    L1

## 模糊点与待确认项

- 本仓接口尚未冻结，任务清单为**方向性**的，落地顺序以 `foray_docs/algorithm_structure.md` §9 演进阶段为准
- 依赖的自研仓尚未建齐，跨仓任务需等对方 `README.md` 明确接口后再启动

## Vector Backend Status

Backend: Markdown
Status:  ready
Environment: 仓库内 Markdown 文档（无外部向量后端）
Index: 本仓 `README.md` / `tree.md` / `decision.md`
Initialization: 2026-02-19
Commit: （首次提交）

## Acceptance Criteria

- [ ] 本仓能独立 `colcon build`（无代码时跳过）
- [ ] CI 绿灯
- [ ] 每个新增模块带独立可执行测试
