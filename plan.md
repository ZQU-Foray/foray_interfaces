# 开发计划

> **编号**：`I1`–`I13` 为本仓任务编号，进度跟踪器（工作区 `scripts/track_progress.py`）
> 按编号对齐 plan 勾选与远端证据（commit / PR / 编号标签），无编号条目会被判「不可追溯」。
>
> **阶段归属**：按 `foray_docs/algorithm_structure.md` §9 演进阶段。`L2` / `L3` 标签表示
> 该条目承载对应层级契约，是 P0「定契约」阶段的可自动判定信号。

## 任务列表

### P0 · 定契约（当前阶段）

- [x] **I1 INTERFACE CMake target**（`foray_interfaces::lower_link`）：`find_package(foray_interfaces)`
      可用，target 自带 include 根与 `cxx_std_17`；`ctest` 跑生成物契约测试，CI 的 `build-cmake`
      作业验证安装后的消费路径（见 `decision.md` 2026-11-03）。
      **状态注记**：代码与 CI 已完成，但仍在 PR #3（`feat/lower-link-protocol → dev`）里，未落地 `dev`。
- [ ] **I2 lower_link 消息表**（L2）：填写 `protocol/lower_link.yaml` 的 `messages:`——`MsgId` 分段、
      每条消息的 `id` / `name` / `direction` / `fields`；算法组 + 电控组共同确定，改协议 = 改 YAML +
      重新生成 + 提交（CI 校验生成物与定义一致）。当前 YAML 的 `messages:` 仍为空。
- [ ] **I3 评审冻结 robolink.md v0.2**（L2）：云台角 rad、角速度前馈、`safety_state` 取值、
      `GIMBAL_ATTITUDE`；v0.1 登记稿已随 PR #2 合并，v0.2 修订稿与 lower_link 的三个待裁决点
      仍待组长裁决。
- [x] **I4 生成器与生成物**（只生成内容层：`MsgId` + POD 结构体 + 载荷编解码）：
      `scripts/gen_lower_link.py` + `generated/lower_link.hpp` + CTest 契约测试（`tests/lower_link_test.cpp`）
      + 生成器 fixture 测试（`tests/test_gen.py`）+ CI 一致性校验。链路已通，内容待 I2 填充。

### 跨组待裁决（阻塞在电控组 / 组长）

- [ ] **I5 周期与调度归链路实现**（`foray_platform` 与 `ControllerCode`）：本仓不再定义「多久发一次」，
      消息表里也没有这一列。由此产生跨组义务：电控组那侧按什么速率预期收包、看门狗设多少，
      需与 `foray_platform` 对齐。与帧格式那次是同形的跨组问题（契约落在实现仓）。
- [ ] **I6 超时与失效阈值不在本仓**：它与周期本是一对数字，现在两者都在链路侧，但没有任何地方
      承载。需确认由谁给它们一个权威落点。
- [ ] **I7 `frame_id` 未定**：组织规范要求「所有消息必须带 `stamp` 与 `frame_id`」，`stamp` 已定为
      `time`（`int32` 秒 + `uint32` 纳秒，绝对时间），`frame_id` 仍缺。它是字符串，违反本协议的
      「禁变长字段」，需决定改用数值枚举还是放弃该条。
- [ ] **I8 下位机的绝对时间来源未定**：`stamp` 定为绝对时间（Unix 纪元），MCU 复位后没有真实时间，
      必须有握手 / 授时机制。属链路层，待与电控组确认。

### 决策层与机间接口（P0 后续）

- [ ] **I9 冻结 `WorldSnapshot` 字段清单**（L3，A–F 分区）：字段、单位、坐标系、置信度字段位置。
- [ ] **I10 冻结 `ActionMask` / `Decision` 定义**（L3）：动作空间、掩码语义、决策输出结构。
- [ ] **I11 起草机间态势协议**：字段 / 单位 / TTL / 置信度 / 版本协商（哨兵 ↔ 步兵）。

### 后续迁入（P1 之后）

- [ ] **I12 迁入裁判系统消息**（`V1.7.0 (20241225)`，7 个）：串口帧 + 消息定义 + 解析夹具。
- [ ] **I13 写两个 mock decider**：验证统一签名能容纳规则与 RL 两种实现。

## 当前断点（2026-11-04）

- **做完的**：I1（INTERFACE target，PR #3 待合并）、I4（生成器 + 生成物 + 契约测试 + CI 校验）。
- **卡住的**：I2 `lower_link.yaml` 的 `messages:` 为空，等算法组与电控组共同定消息表；
  I3 robolink v0.2 的三个待裁决点（云台角系、前馈语义、`safety_state` 取值）等组长裁决。
- **无人认领**：I5/I6（周期与超时阈值的权威落点）、I7（`frame_id` 表示法）、I8（MCU 绝对时间来源）——
  这四项都落在本仓与链路实现仓的缝上，需要先定归属再动手。
- **恢复方式**：从 I2 起——消息表一旦确定，改 YAML → `python3 scripts/gen_lower_link.py` → 跑
  `cmake -S . -B build && ctest --test-dir build` → 提交，CI 会校验生成物一致性。

## 当前 Agent State

P0_CONTRACTS_IN_PROGRESS
I1/I4 done (PR #3 open) · I2/I3 blocked on cross-team review · I5–I8 need owner

## Before Snapshot

commit hash:   df61b8b
branch:        feat/lower-link-protocol
modified files: plan.md
risk level:    L1

## 模糊点与待确认项

- 本仓接口尚未冻结，任务清单为**方向性**的，落地顺序以 `foray_docs/algorithm_structure.md` §9 演进阶段为准
- 依赖的自研仓尚未建齐，跨仓任务需等对方 `README.md` 明确接口后再启动
- lower_link（仅内容层，YAML 单源）与 robolink v0.2（帧层 + 内容层全栈）两份候选稿并行，
  收敛方向未定；二者谁成为唯一权威尚未裁决
- I5–I8 四项都没有明确 owner：要么在本仓定、要么在链路实现仓定，**不能一直悬空**

## Vector Backend Status

Backend: Markdown
Status:  ready
Environment: 仓库内 Markdown 文档（无外部向量后端）
Index: 本仓 `README.md` / `tree.md` / `decision.md`
Initialization: 2026-02-19
Commit: （首次提交）

## 验收标准（Acceptance Criteria）

- [x] 本仓能独立构建：纯 CMake 包，`cmake -S . -B build && cmake --build build && ctest --test-dir build`
- [x] CI 绿灯：`build-cmake`（含安装后消费路径）+ 生成物契约测试
- [x] 每个新增模块带独立可执行测试：`tests/lower_link_test.cpp`、`tests/test_gen.py`、`tests/cmake_consumer`
- [ ] 三份优先冻结契约在本仓落定：lower_link 内容层、决策层接口、机间态势协议
- [ ] 下游能只靠 `find_package` 消费全部冻结契约，不再各自写 `-I`
