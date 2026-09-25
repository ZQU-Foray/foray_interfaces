# foray_interfaces

> **X2** · owner 角色：架构

全部接口定义：机内接口 + 机间态势协议 + 裁判系统消息

被所有仓依赖，**不依赖任何自研仓**。变更代价全组织最高。

---

## 快速开始

> 本仓处于**初始化状态**，尚无源码。以下流程随 P0/P1 落地逐步可用。

```bash
# 1. 拉取（仓齐备后改为从元仓 foray_ws 一键拉取）
git clone git@github.com:ZQU-Foray/foray_interfaces.git
cd foray_interfaces

# 2. 依赖安装
rosdep install -y -r --from-paths . --ignore-src --rosdistro humble

# 3. 构建
colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release

# 4. 运行
# （待装配根就绪后补充）
```

## 依赖

| 类型 | 依赖 |
|---|---|
| **自研仓** | **无**（依赖链最底层） |
| **第三方** | ROS 2 Humble（`rosidl_default_generators` / `rosidl_default_runtime`） |

## 接口

本仓承载**上位机的全部跨边界契约**：

| 契约 | 内容 | 状态 |
|---|---|---|
| **上位机 ↔ 下位机链路协议** | USB CDC 帧格式 + 消息表（算法组 ↔ 电控组） | **草案 v0.1** → [`protocol/`](protocol/lower_link.md) |
| **决策层接口** | `WorldSnapshot` / `ActionMask` / `Decision` | 待冻结（P0） |
| **机间态势协议** | 哨兵 ↔ 步兵的态势消息 | 待冻结（P0） |
| 裁判系统消息 | 串口协议 `V1.7.0 (20241225)`，7 个消息 | 待迁入 |

## 上位机 ↔ 下位机链路协议

见 [`protocol/lower_link.md`](protocol/lower_link.md)。要点：

| 项 | 内容 |
|---|---|
| 物理层 | **USB CDC**（`/dev/ttyACM*`，用 udev 固定为 `/dev/foray_lower`） |
| 帧格式 | `SOF(2) + LEN(1) + SEQ(1) + MSG_ID(1) + PAYLOAD(≤250) + CRC16(2)` |
| 数据表示 | 全小端 · 单精度浮点 · `#pragma pack(1)` |
| 频率 | 控制 100–200 Hz 下行 · 状态 200 Hz 上行 · 心跳 10 Hz |
| 失联退化 | **由下位机自主执行**（硬路径），不依赖上位机 |

**三层归属**

| 产物 | 位置 |
|---|---|
| 规范 + 定义 + 生成物 | **本仓** |
| 上位机侧实现（帧同步 / 超时 / 重连） | `foray_platform`（L2 下行 HAL） |
| 下位机侧实现（编解码 / 驱动 / 安全态） | `ControllerCode` |

**两侧代码由生成器产出，禁止手写**——否则字节序、字段偏移、CRC 必然漂移。

```bash
python3 scripts/gen_lower_link.py    # 改完 protocol/lower_link.yaml 后执行
```

## 约定（必须遵守）



- 单位与坐标系遵循 **REP-103 / REP-105**

- 所有消息必须带 `stamp` 与 `frame_id`

- **估计类消息必须带置信度**

- **云台角约定全队统一**：yaw 向左为正、pitch 向下为正（与 DJI NED 约定不同，在本仓写死）

- 语义版本化；不兼容改动必须给**兼容期** + 影响面清单

- 本仓 `README.md` 是字段契约的权威文本，**必须与 `msg/` 定义同步更新**——否则会出现「文档说 A、代码做 B」



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
