# 关键工程决策日志

> 记录 fork patch、换版本、**破坏性接口变更**、架构取舍。
> 格式见 `foray_docs/repository_structure.md` §7.2。

---

## Decision

Date: 2026-02-19

Context: 本仓从 0 初始化。需要确定它在整体架构中的位置与依赖边界。

Decision: 本仓定位为 **X2** 层，owner 角色为「架构」，
依赖层级 无。

Reason:
- 切分判据 C1–C6 见 `foray_docs/repository_structure.md` §1
- 粒度结论：**一个仓 = 一个团队角色 + 一个变更率档位**
- 被所有仓依赖，**不依赖任何自研仓**。变更代价全组织最高

Alternatives:
- 并入相邻仓（减少仓库数量，但违反团队边界或变更率差异）

Rejected:
- 按 ROS 2 package 粒度切仓 —— 会导致版本矩阵地狱
- 按分层机械切仓 —— 会切断团队边界（Conway）

---

## Decision

Date: 2026-10-23

Context: `protocol/robolink.md` v0.1 候选稿在云台角单位上自相矛盾（§0 写全 SI、云台行又写视觉按 deg），
目标角写成"与反馈同一累计角系"，`gimbal_yaw_rate` / `gimbal_pitch_rate` 写成"速度模式目标、由 mode 选择"，
但 mode 枚举里没有对应的速度模式；`safety_state` 取值未冻结；协议里没有云台姿态反馈，视觉无法把画面目标
换算到世界系。v0.1 从未上线，无兼容性负担。

Decision: 修订为 v0.2（破坏性接口变更，仅涉及候选稿）：
- 云台目标与反馈统一为世界系 rad、不区分圈数，MCU 按最短路径跟踪（偏差 ≥ 150° 锁定转向）；
- `gimbal_yaw_rate` / `gimbal_pitch_rate` 改为目标角速度前馈（目标角对时间的导数），0 表示静止目标；
- 冻结 `safety_state` 取值（0 未收到快照 · 1 快照有效 · 2 控制失联 · 3 急停）与各模式可驱动的子系统；
- 新增 `GIMBAL_ATTITUDE`（0x30，MCU→PC，36 B，1 kHz 起步）：四元数 + 去零偏角速度 + 与帧头同钟的采样时刻
  + IMU 就绪状态；只在 PC 的 HELLO 声明支持时发送。

Reason:
- 不记圈数：累计角把跨圈计算推给每个上位机程序，且 MCU 重启后累计值归零，旧目标会让云台连转数圈；
  最短路径无此状态。参考 TongjiSuperPower/sp_vision_25 的哨兵全向感知同样按 ±π 下发
- 前馈而非速度模式：视觉轨迹规划能给出目标速度，前馈让匀速目标无稳态滞后，仍由 MCU 的轨迹约束限幅；
  速度模式需要额外的模式选择位，且与"角度为唯一目标"冲突
- 四元数而非欧拉角：没有万向节奇异，PC 可按需分解；采样时刻与帧头同钟，PC 侧可以单端换算到本机时间
- IMU 就绪状态：冷启动标定期间（约 30 s）MCU 不接受世界系目标，PC 需要知道原因而不是只看到执行序号不前进

Alternatives:
- 保留 deg：与"全 SI"冲突，且角速度为 rad/s 时出现混用
- 角速度字段本版保留不用：改动最小，但视觉跟踪少了前馈

Rejected:
- 累计角系（见 Reason）
- 发送欧拉角 yaw/pitch：ZYX 分解在 pitch ±90° 附近奇异，且丢失 roll
