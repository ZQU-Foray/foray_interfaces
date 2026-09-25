# 开发计划

## 任务列表

- [x] 起草上位机 ↔ 下位机链路协议**结构**（USB CDC 帧格式 + 生成器 + CI 校验）
- [x] 生成物契约测试（CRC 标准 check value / 固定帧字节序列 / 组帧解帧往返 / 失步重同步）
- [x] 帧内偏移与 CRC 覆盖范围改为从 `frame` 段推导；补强类型 `encode` / `decode` 与长度表
- [ ] **填写消息表**（`protocol/lower_link.yaml` 的 `messages:`）——算法组 + 电控组共同确定，见规范「消息表」一节
- [ ] 把**链路管理消息**（握手 / 心跳 / 错误上报）内置为协议结构，不随消息表下放给业务组
- [ ] 补 **Python 侧生成物**（消息号 + 帧编解码）——`msg/*.msg` 里没有消息号常量，
      上位机若用 Python 就没有可用产物
- [ ] `status: proposed` 的消息暂不生成代码，只在文档表格中出现
- [ ] 用 `id_ranges` 校验消息号与方向的对应关系（生成器现只建议、不强制）
- [ ] 通知电控组修 `ControllerCode` 里对本规范的章节引用——`README.md` 的 `§6.3`、
      `plan.md` 的 `§9` 在本次精简后已失效（开火三层并入「安全与失效」，待确认项变为 §6）。
      跨仓引用本仓 grep 不到，只能人盯
- [ ] 填写各链路频率与超时阈值（见规范「待确认」#4）
- [ ] 确认 `ControllerCode` 是否已有在用帧格式——若有，规范「帧」一节要改为兼容现有格式
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
