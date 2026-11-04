# foray_interfaces

> **X2** · owner 角色：架构

全部接口定义：机内接口 + 机间态势协议 + 裁判系统消息

被所有仓依赖，**不依赖任何自研仓**。变更代价全组织最高。

---

## 快速开始

> 本仓已有协议生成物与纯 CMake 构建配置；消息表与冻结接口仍在 P0/P1 推进中，
> 以下流程随落地逐步完整。

```bash
# 1. 拉取（仓齐备后改为从元仓 foray_ws 一键拉取）
git clone git@github.com:ZQU-Foray/foray_interfaces.git
cd foray_interfaces

# 2. 依赖安装
rosdep install -y -r --from-paths . --ignore-src --rosdistro humble

# 3. 构建
colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release

# 4. 测试（生成物的契约测试，CTest）
colcon test

# 5. 运行
# （待装配根就绪后补充）
```

## 依赖

| 类型 | 依赖 |
|---|---|
| **自研仓** | **无**（依赖链最底层） |
| **第三方** | CMake ≥ 3.16 + C++17 编译器（构建生成物）；ROS 2 Humble 的 `rosidl_default_*` 为将来的 msg 预留，当前纯 CMake 形态不使用 |

## 构建与消费

本仓是 **header-only 纯 CMake 包**（`package.xml` 的 `build_type=cmake`，不依赖 ament / rosidl）：

- 独立构建与测试：`cmake -S . -B build && cmake --build build && ctest --test-dir build`
- 下游消费：`find_package(foray_interfaces REQUIRED)` 后
  `target_link_libraries(<你的 target> PRIVATE foray_interfaces::lower_link)`——
  target 自带 include 根与 `cxx_std_17`，不必再写 `-I`
- 裸机侧不经过 CMake：直接 `#include "lower_link.hpp"`（include 根为 `generated/`）

## 接口

本仓承载**上位机的全部跨边界契约**（`foray_docs/algorithm_structure.md` §6 的三份优先冻结契约中，本仓占两份）：

| 契约 | 内容 | 状态 |
|---|---|---|
| **上位机 ↔ 下位机通讯协议** | 两份候选稿并行待收敛：lower_link（仅内容层，YAML 单源，消息表待填写）/ 上下位机链路协议 v0.2（帧层 + 内容层全栈，8 条消息，含云台姿态反馈） | 候选 → [`lower_link.md`](protocol/lower_link.md) · [`robolink.md`](protocol/robolink.md) |
| **决策层接口** | `WorldSnapshot` / `ActionMask` / `Decision` | 待冻结（P0） |
| **机间态势协议** | 哨兵 ↔ 步兵的态势消息 | 待冻结（P0） |
| 裁判系统消息 | 串口协议 `V1.7.0 (20241225)`，7 个消息 | 待迁入 |

## 约定（必须遵守）



- 单位与坐标系遵循 **REP-103 / REP-105**

- 所有消息必须带 `stamp` 与 `frame_id`

- **估计类消息必须带置信度**

- **云台角约定全队统一**：yaw 向左为正、pitch 向下为正（与 DJI NED 约定不同，在本仓写死）

- 语义版本化；不兼容改动必须给**兼容期** + 影响面清单

- 字段契约的权威文本是各契约自己的规范（如 [`protocol/lower_link.md`](protocol/lower_link.md)）
  与它生成的 `msg/` 定义，**两者必须同步更新**——否则会出现「文档说 A、代码做 B」。
  `README.md` 只写定位、接口清单与上下游



## 接口字段必须写清



每个字段都要写：**语义 / 单位 / 坐标系 / 取值范围 / 缺失时如何表示**。

## 上下游

| 方向 | 对象 |
|---|---|
| **上游**（本仓依赖谁） | 无自研依赖 |
| **下游**（谁依赖本仓） | `foray_platform` · `foray_localization` · `foray_vision` · `foray_auto_aim` · `foray_navigation` · `foray_decision` · `foray_robots` · `foray_ws` |

## 参考

- [算法结构](https://github.com/ZQU-Foray/foray_docs/blob/main/algorithm_structure.md)
- [仓库结构](https://github.com/ZQU-Foray/foray_docs/blob/main/repository_structure.md)
- [组织贡献指南](https://github.com/ZQU-Foray/.github/blob/main/CONTRIBUTING.md)
