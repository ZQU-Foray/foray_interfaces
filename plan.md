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
- [ ] 通知电控组修 `ControllerCode` 里对本规范的章节引用——`README.md:66` 的 `§6.3`、
      `plan.md:9` 的「§9 的 6 项」（实为 §6 四行）在文档精简后已失效。
      跨仓引用本仓 grep 不到，只能人盯
- [ ] 回写 `foray_docs`：`algorithm_structure.md:524-525` 那段「规范放 `foray_platform`
      会让电控组必须读算法组的仓」是本次 `decision.md` 决策**点名反驳**的对象，需随裁决修订。
      注意该文件当前在**未合并**分支 `docs/lower-link-contract` 上
- [ ] 填写各链路频率与超时阈值（见规范「待确认」）
- [x] 确认 `ControllerCode` 是否已有在用帧格式——**已查清：没有**。USB 链路是纯字节管道
      （4096 B 环形队列无定界），`UsbCdc::TryRead/TryWrite` 零调用者，链路还没有消费者任务。
      无需兼容既有格式，可直接上新格式
- [x] USB 外设全速还是高速——**已查清：全速**（`usbd_conf.c:319` `PCD_SPEED_FULL`，48 MHz）。
      1 ms 帧预算，宿主侧 `latency_timer=1` 不是可选项
- [ ] **【阻塞】把帧格式迁出本仓**——协议只定义包的内容，帧的实现归两侧
      （见 `decision.md` 2026-09-25 条）。**需电控组先签收**：他们四处文档写着
      「禁止手写帧解析」，不先签收就会进入「帧实现没了、规则又禁止自己写」的死锁。
      签收后另开 PR：删 `frame:` 段、删 `frame_layout()`/`crc_region()`/CRC/`encode_frame`/
      `decode_frame`/`FrameView`、文档 §1 改为「链路必须满足的约束」、§2/§4/§5 移出本仓、
      `tests/lower_link_test.cpp`（100% 帧测试）删除或移交
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
