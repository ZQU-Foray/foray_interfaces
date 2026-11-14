# 视觉前后端契约（vision）v0.1.0 · draft

> 机器可读定义：[`vision.yaml`](vision.yaml)（唯一事实来源）。
> 本文是人读说明；两者冲突时以 `vision.yaml` 与它生成的 `msg/` 为准。

## 定位

`diesel_vision_frontend` 逐帧输出**观测**，`diesel_vision_backend` 消费观测并输出**世界快照**与**云台指令**。
三个角色各自不关心对方内部实现：

```
相机 → frontend（检测 + PnP）─ ObservationArray ─→ backend（融合 + 跟踪 + 瞄准）
                                                     ├─ WorldSnapshot ─→ decision
                                                     └─ GimbalCommand ─→ 链路
```

## 消息

| 消息 | 方向 | 说明 |
|---|---|---|
| `Observation` | frontend → backend | 单个目标的单帧观测 |
| `ObservationArray` | frontend → backend | 一帧的全部观测 |
| `TrackedTarget` | 内嵌 | 后端维护的单条轨迹 |
| `WorldSnapshot` | backend → decision / 自瞄 | 世界模型快照 |
| `GimbalCommand` | backend → 链路 | 云台角指令 |

字段明细见 [`generated/vision_table.md`](../generated/vision_table.md)（自动生成，禁止手写）。

## 约定

- **坐标系**：观测在相机光学系（`frame_id` 填相机光学系），快照在世界系（REP-105 `map`），
  指令在云台系（`gimbal`）。单位米 / 弧度，遵循 REP-103 / REP-105。
- **云台角**：yaw 向左为正、pitch 向下为正，全队统一（与 DJI NED 不同）。
- **时间**：`stamp` 是图像采集时刻（不是处理完成时刻），绝对时间、Unix 纪元。
  下游据此判断新鲜度，而不是靠「收到就新鲜」。
- **置信度**：估计类消息必须带 `confidence`（0–1），未知时不得填 1。
- **缺失语义**：未解算的位姿填 0 并由 `normal_valid` / `valid` 显式标记；
  未编号的装甲板与无轨迹的指令用 `-1`，不得用 0 混充「第一号板」。
- **固定容量**：C++ 侧一帧最多 32 个观测、快照最多 8 条轨迹（`vision.hpp` 的
  `kVisionMaxObservations` / `kVisionMaxTracks`）。上限固定是为了后端跟踪环
  满足 1–10 ms 的硬实时预算——超限时丢弃置信度最低者并计数，不动态扩容。
- **不定义**：话题名、QoS、发送周期、超时阈值归装配根与各仓运行时配置，本仓只定义字段与语义。

## 变更流程

1. 改 `vision.yaml`；
2. `python3 scripts/gen_vision.py` 重新生成（禁止手写 `generated/`）；
3. 同步更新本文与 `generated/vision_table.md` 之外的一切人读说明；
4. 不兼容改动必须给兼容期与影响面清单（见仓库 README 的约定）。

CI 的 `gen-check` 作业会重新生成并 `git diff --exit-code`，不一致即失败；
`tests/vision_test.cpp` 编译并运行真实生成物，`tests/test_gen_vision.py` 测生成器本身。
