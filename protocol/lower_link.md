# 上位机 ↔ 下位机链路协议

> **X2 契约** · 归属 `foray_interfaces`
> 状态：**草案 v0.1** —— 消息表待电控组逐条确认后冻结
>
> 本文件是**唯一权威文本**。机器可读定义见 [`lower_link.yaml`](lower_link.yaml)，
> 两侧代码由 [`../scripts/gen_lower_link.py`](../scripts/gen_lower_link.py) 生成——**禁止手写**。

---

## 0. 三层归属

| 产物 | 位置 | 维护 |
|---|---|---|
| 规范（本文件）· 定义（YAML）· 生成物 | **`foray_interfaces`** | 架构组，**算法 + 电控共同评审** |
| 上位机侧实现（帧同步 · 编解码 · 超时 · 重连） | `foray_platform`（L2 下行 HAL） | 平台组 |
| 下位机侧实现（编解码 · 驱动 · 安全态） | `ControllerCode` | 电控组 |

**为什么规范不放 `foray_platform`**：判据 **C1**（接口不得被实现私有化）+ **C6**（跨队共享）。
放实现仓会导致两个后果——电控组要实现自己那侧得去读算法组的仓（权限边界失效）；
协议改动会藏在一次「平台层重构」的 PR 里无人审查（违反 **D2**）。

---

## 1. 物理层

| 项 | 取值 |
|---|---|
| 接口 | **USB CDC**（虚拟串口 / `ttyACM`） |
| 宿主设备节点 | `/dev/ttyACM*` → 用 udev 固定为 `/dev/foray_lower`（见 §2.2） |
| 速率 | USB 全速 12 Mbps 或高速 480 Mbps（取决于 MCU USB 外设配置，见 §9） |
| 传输方式 | Bulk（CDC ACM） |
| 流控 | **不使用 RTS/CTS**——靠应用层速率约束（见 §5.3） |

### 1.1 为什么帧界定仍然必需

USB 链路层自带 CRC16，**线路噪声导致的位翻转基本不会传到应用层**。
但 USB CDC 对应用呈现的是**字节流**而非消息流：

- 一次 `read()` 可能拿到半帧，也可能拿到三帧半
- MCU 复位、USB 枚举中断都会打断流

所以 **`SOF + LEN` 帧界定不能省**。CRC 的作用从「防线路噪声」变为「防帧同步丢失」。

> **保留 CRC 的理由不是 USB 需要，而是可移植性**：同一套帧格式将来要复用到
> CAN（对电调）与 UART（遥控器 SBUS）——`ControllerCode/Libraries/Protocol/` 已有这两条。
> 保留 CRC 让帧格式在三条链路上通用，成本是每帧 2 B。

---

## 2. Linux 宿主侧必须做的三件事

### 2.1 `latency_timer` 必须设为 1

**这是最容易漏、后果最严重的一项。**

`cdc_acm` 驱动默认 `latency_timer = 16`（ms），读方向最多攒 16 ms 才上交内核。
**不改它，实时预算当场归零。**

```bash
echo 1 | sudo tee /sys/bus/usb-serial/devices/ttyACM0/latency_timer
```

### 2.2 udev 规则固定设备名

`/dev/ttyACM0` 的编号会随插拔顺序漂移，多台车/多个 USB 串口设备时必然踩坑。按 USB serial 绑定：

```
# /etc/udev/rules.d/99-foray-lower.rules
SUBSYSTEM=="tty", ATTRS{idVendor}=="<VID>", ATTRS{idProduct}=="<PID>", \
  ATTRS{serial}=="<MCU_SN>", SYMLINK+="foray_lower", MODE="0666"
```

### 2.3 热插拔必须当常态

MCU 复位、线松、供电抖动都会让设备消失再出现。HAL 需要状态机：

```
OPEN → HANDSHAKE → RUNNING → (设备消失) → LOST → 重试 OPEN
```

**`LOST` 期间必须进安全态**——上位机不再发指令，安全由下位机自主保证（见 §6.2）。

---

## 3. 帧格式

```
┌──────────┬───────┬───────┬────────┬─────────────┬────────┐
│   SOF    │  LEN  │  SEQ  │ MSG_ID │   PAYLOAD   │  CRC16 │
│  2 bytes │ 1 B   │ 1 B   │  1 B   │  0–250 B    │ 2 bytes│
│  A5 5A   │       │       │        │             │        │
└──────────┴───────┴───────┴────────┴─────────────┴────────┘
```

| 字段 | 宽度 | 说明 |
|---|---|---|
| `SOF` | 2 B | 固定 `0xA5 0x5A`，用于失步后重新定位帧头 |
| `LEN` | 1 B | PAYLOAD 字节数，0–250 |
| `SEQ` | 1 B | 发送序号，**每帧 +1 回绕**；接收侧用于检测丢帧 |
| `MSG_ID` | 1 B | 消息号，见 §4 |
| `PAYLOAD` | 0–250 B | 按 `MSG_ID` 解释 |
| `CRC16` | 2 B | CRC-16/CCITT-FALSE，**覆盖 `LEN` 至 `PAYLOAD`**（不含 SOF），小端 |

**数据表示约定**

| 项 | 规定 |
|---|---|
| 字节序 | **全部小端**（ARM 原生，零转换开销） |
| 浮点 | **一律 IEEE 754 单精度**；禁用 `double`（MCU 侧无双精度 FPU） |
| 结构体对齐 | `#pragma pack(1)`，无隐式填充 |
| 角度 | `float` 弧度 |
| 帧总长上限 | **257 B** |

> 候选替代：**COBS** 封装（无 SOF 逃逸问题，额外开销更低）。
> 未采用的原因——团队对 SOF+LEN+CRC 更熟悉，且该格式可复用到 CAN/UART。

---

## 4. 消息表

> ⚠️ **v0.1 提案，待电控组逐条确认。** 消息号按「方向 + 功能」分段。

### 4.1 消息号分配

| 段 | 用途 |
|---|---|
| `0x00–0x0F` | 控制类（上→下） |
| `0x10–0x1F` | 状态类（下→上） |
| `0x20–0x2F` | 透传 / 转发 |
| `0x30–0x3F` | 配置 / 标定 |
| `0x70–0x7F` | 链路管理（双向） |

### 4.2 控制类（上→下）

| ID | 名称 | 周期 | 载荷 |
|---|---|---|---|
| `0x01` | `CHASSIS_CMD` | 100 Hz | `vx` `vy` `wz`（float32，m/s、rad/s，**车体坐标系**） |
| `0x02` | `GIMBAL_CMD` | 200 Hz | `yaw` `pitch`（float32，rad，绝对角）· `yaw_rate` `pitch_rate`（float32，rad/s） |
| `0x03` | `SHOOTER_CMD` | 事件 + 20 Hz 心跳 | `fire_authorized`（bool）· `trigger_count`（uint8）· `friction_level`（uint8） |

**安全约定**

- `fire_authorized = false` 时下位机**必须拒绝拨弹**，而不是仅在 UI 上体现
- `SHOOTER_CMD` 带 20 Hz 心跳，**超时即撤销授权**（见 §5.2）
- 实弹发射能力必须可由下位机**独立切断**（见 §6.3）

### 4.3 状态类（下→上）

| ID | 名称 | 周期 | 载荷 |
|---|---|---|---|
| `0x11` | `CHASSIS_STATE` | 200 Hz | 里程计 `vx` `vy` `wz` · IMU `roll` `pitch` `yaw` |
| `0x12` | `GIMBAL_STATE` | 200 Hz | 实际 `yaw` `pitch` · 角速度 `yaw_rate` |
| `0x13` | `ACTUATOR_STATE` | 50 Hz | 各电机电流 / 温度 / 使能位 · 拨弹机构状态 |
| `0x14` | `POWER_STATE` | 10 Hz | 电压 · 电流 · 剩余能量（热量）· 底盘功率 |

### 4.4 透传（下→上）

| ID | 名称 | 触发 | 载荷 |
|---|---|---|---|
| `0x20` | `REFEREE_RAW` | 裁判系统帧到达即转发 | 裁判系统原始帧 |
| `0x21` | `REMOTE_RAW` | 遥控器帧到达即转发 | SBUS 原始帧（备用通道） |

> ⚠️ **待确认**：裁判系统接在下位机还是上位机直连？若由下位机转发，
> 转发延迟与带宽需计入 §5.3。

### 4.5 链路管理（双向）

| ID | 名称 | 方向 | 周期 | 载荷 |
|---|---|---|---|---|
| `0x70` | `HEARTBEAT` | 双向 | 10 Hz | `seq`（uint8）· `uptime_ms`（uint32）· `status_bits`（uint16） |
| `0x71` | `HANDSHAKE_REQ` | 上→下 | 事件 | `host_protocol_version`（uint16） |
| `0x72` | `HANDSHAKE_ACK` | 下→上 | 事件 | `mcu_protocol_version`（uint16）· `capability_bits`（uint32） |
| `0x73` | `LINK_ERROR` | 下→上 | 事件 | `error_code`（uint8）· `detail`（uint32） |

---

## 5. 时序

### 5.1 频率

| 链路 | 频率 |
|---|---|
| 底盘指令 | 100 Hz |
| 云台指令 | 200 Hz |
| 状态回传 | 200 Hz |
| 心跳 | 10 Hz |

### 5.2 超时

| 条件 | 阈值 | 动作 |
|---|---|---|
| 未收到 `CHASSIS_CMD` | 100 ms | 下位机底盘归零 |
| 未收到 `GIMBAL_CMD` | 100 ms | 下位机云台保持当前位置 |
| 未收到 `SHOOTER_CMD` 心跳 | 200 ms | **撤销开火授权** |
| 未收到 `HEARTBEAT` | 500 ms | 判定链路 `LOST` |
| 连续 3 帧 `SEQ` 跳变 | — | 记警告 |
| 连续 10 帧 `SEQ` 跳变 | — | 上报 `LINK_ERROR` |

### 5.3 带宽预算

当前消息表满载约 **20 KB/s**（不含裁判系统转发）：

| 消息 | 估算 |
|---|---|
| `CHASSIS_CMD` 100 Hz × 21 B | 2.1 KB/s |
| `GIMBAL_CMD` 200 Hz × 25 B | 5.0 KB/s |
| `CHASSIS_STATE` 200 Hz × 33 B | 6.6 KB/s |
| `GIMBAL_STATE` 200 Hz × 17 B | 3.4 KB/s |
| `ACTUATOR_STATE` 50 Hz × 40 B | 2.0 KB/s |
| 其余 | ~1 KB/s |

占 USB 全速（1.5 MB/s）约 **1.3%**。

> **USB 不是瓶颈。瓶颈是调度延迟**——见 §1 与 §2.1。

---

## 6. 异常与失效

### 6.1 上位机侧（`foray_platform`）

| 异常 | 处置 |
|---|---|
| CRC 错 | 丢帧，计数上报 X4 |
| `SEQ` 跳变 | 丢帧计数 |
| 设备消失 | 状态机 → `LOST`，进安全态，重连 |
| 重连成功 | 重新握手；**不自动恢复上一状态**，回到 `IDLE` |

### 6.2 下位机侧（`ControllerCode`）—— **硬路径**

> **链路失联后的安全必须由下位机自主保证，不得依赖上位机。**

| 失联时长 | 动作 |
|---|---|
| 100 ms | 底盘速度归零 |
| 200 ms | 撤销开火授权，摩擦轮停 |
| 500 ms | 云台停止接受指令，保持当前位置 |

这些定时器跑在 MCU 上，**与 USB 中断无关**——USB 死了它们照常触发。

> 对应 X1 的「**急停必须有硬路径**」：最终安全降级不依赖任何上层。

### 6.3 开火的安全边界（三层独立）

| 层 | 约束 |
|---|---|
| 上位机 | 操作手授权；**目标身份切换 ⇒ 授权失效**（见 `algorithm_structure.md` §5） |
| 链路 | `fire_authorized` 带 20 Hz 心跳，超时即撤销 |
| 下位机 | **独立的硬上限**（单次连发数上限、发射间隔下限），不接受任何来源的覆盖 |

任一层失效都不会导致失控发射。

---

## 7. 版本与兼容

- 协议语义版本：`MAJOR.MINOR`
- 握手交换版本：**`MAJOR` 不一致 ⇒ 拒绝进入 `RUNNING`**，进 `LOST` 并报错
- `MINOR` 不一致 ⇒ 允许运行，按**较低版本的能力集**工作
- 新增消息号不视为破坏性变更；**修改已有消息的字段布局必须升 `MAJOR`**
- 破坏性变更走 **D2**：≥2 人评审 + 兼容性影响评估

---

## 8. 单一事实来源

```
foray_interfaces/
├── protocol/
│   ├── lower_link.md          本文件（人读）
│   ├── lower_link.yaml        机器可读定义（**唯一事实来源**）
│   └── generated/             由 gen_lower_link.py 生成——禁止手写
│       ├── lower_link.hpp     → ControllerCode（裸机 C++，无 ROS 依赖）
│       ├── msg/*.msg          → foray_platform（ROS 2 侧类型）
│       └── message_table.md   → 消息表（自动生成，防止文档漂移）
└── scripts/gen_lower_link.py  生成器
```

**改协议 = 改 `lower_link.yaml` + 重新生成 + 提交。** 两侧实现不允许手写编解码。

**CI 校验**：重新生成后 `git diff --exit-code`，不一致即失败。

> 关键点：`lower_link.hpp` 是**裸机 C++**（POD 结构体 + 常量 + 编解码函数），
> 不引入任何 ROS 依赖——因此 `ControllerCode` 可以直接包含它。
> ROS 侧类型（`msg/*.msg`）从同一份 YAML 生成，两边不可能不一致。

---

## 9. 待确认项

| # | 问题 | 影响 |
|---|---|---|
| 1 | **裁判系统接在下位机还是上位机？** | `REFEREE_RAW` 是否进消息表；转发延迟是否计入实时预算 |
| 2 | **MCU USB 外设是全速还是高速？** | 决定调度延迟量级（1 ms vs 125 µs） |
| 3 | `ControllerCode` 是否已有在用的帧格式？ | 若有，§3 应改为兼容现有格式而非新造 |
| 4 | 云台是否需要前馈角速度？ | `GIMBAL_CMD` 载荷字段 |
| 5 | 拨弹机构是位置控制还是速度控制？ | `SHOOTER_CMD` 载荷字段 |
| 6 | 硬实时边界归属 | 见下 |

### 关于硬实时边界

`algorithm_structure.md` §7.1 把「云台控制环、发射机构」列为**上位机硬实时域（1–10 ms）**。
走 USB CDC 后这个划分需要修正：

```
上位机（100–200 Hz 目标流）  ──USB CDC──►  MCU（1 kHz 电流/位置环）
   软实时：10–100 ms                        硬实时：本地闭环
```

- **电流环与位置环在下位机**，不在上位机——上位机送的是**目标**，不是每周期指令
- 上位机侧 1–10 ms 的要求只对**进程内**算法路径（图像 → 检测 → 角度）成立，
  对**跨 USB 的路径不成立**（`latency_timer` 1 ms + USB 帧调度）

这条要回写进 `algorithm_structure.md`。
