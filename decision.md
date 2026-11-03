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
---

## Decision

Date: 2026-11-03

Context: 生成物 `generated/lower_link.hpp` 是 header-only 的。下游各仓在 colcon 工作区里需要
以可链接目标的形式消费它（include 根、C++ 标准、`find_package` 入口）。此前本仓没有构建
系统，CI 用裸 `g++` 编译测试，下游只能各自写 `-I <repo>/generated`。

Decision: 本仓采用**纯 CMake 包**（`package.xml` 的 `<build_type>cmake</build_type>`），
导出 **INTERFACE target `foray_interfaces::lower_link`**（`EXPORT_NAME lower_link`），
不引入 ament_cmake / rosidl 构建依赖；`tests/lower_link_test.cpp` 接入 CTest，
CI 新增 `build-cmake` 作业构建、测试并验证安装后的 `find_package` 链路。

Reason:
- 本仓零自研依赖，当前也不产 ROS 产物（`foray_docs/naming.md` §2.1：`foray_interfaces`
  无 ROS 包）；`README.md` 依赖表里的 rosidl 只为将来的 msg 预留，现在用不上
- colcon 对 `build_type=cmake` 原生支持——工作区里 `colcon build` 与单独
  `cmake -S . -B build` 是同一套命令，CI 与本地不会漂
- INTERFACE target 把 include 根、`cxx_std_17` 与安装布局一次说清，下游不必各自写 `-I`
- 将来真正生成 ROS 消息时再拆 `diesel_interfaces` 消息包，与本包的纯 CMake 形态不冲突

Alternatives:
- `ament_cmake` 包：与 ROS 消息包生态一致，但当前没有任何 ament 产物，等于先引入 ament
  构建依赖，`.foray-layer` 的零依赖承诺也会变得含糊

Rejected:
- 只加 `CMakeLists.txt`、不加 `package.xml` —— 只能被 `add_subdirectory` / `FetchContent`
  消费，colcon 不识别为 package，下游无法 `find_package`
- 让每个下游各自 `-I generated/` —— include 根、C++ 标准与安装布局分散在各仓，一次路径
  调整就要全组织改
