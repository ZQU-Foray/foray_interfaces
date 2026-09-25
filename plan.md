# 开发计划

## 任务列表

- [ ] 填写**上位机 ↔ 下位机通讯协议**的消息表（`protocol/lower_link.yaml`）——算法组 + 电控组共同确定
- [ ] 该协议的生成器与生成物（只生成内容层：`MsgId` + POD 结构体 + 载荷编解码），以及 CI 校验与测试
- [ ] **`frame_id` 未定**——组织规范要求「所有消息必须带 `stamp` 与 `frame_id`」，`stamp` 已定为
      `time`（`int32` 秒 + `uint32` 纳秒，绝对时间），`frame_id` 仍缺。它是字符串，违反本协议的
      「禁变长字段」，需决定改用数值枚举还是放弃该条
- [ ] **下位机的绝对时间来源未定**——`stamp` 定为绝对时间（Unix 纪元），而 MCU 复位后没有真实
      时间，必须有握手/授时机制。这属链路层，待与电控组确认
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
