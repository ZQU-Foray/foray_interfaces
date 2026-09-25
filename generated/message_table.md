<!-- 本文件由 scripts/gen_lower_link.py 自动生成，禁止手写。 改协议请改 protocol/lower_link.yaml。 -->

# 消息表（自动生成）

协议版本 `0.1.0` · 状态 `draft`

| ID | 名称 | 方向 | 周期 | 载荷 | 状态 |
|---|---|---|---|---|---|
| `0x01` | `CHASSIS_CMD` | host_to_mcu | 100 Hz | 12 B | proposed |
| `0x02` | `GIMBAL_CMD` | host_to_mcu | 200 Hz | 16 B | proposed |
| `0x03` | `SHOOTER_CMD` | host_to_mcu | 20 Hz | 3 B | proposed |
| `0x11` | `CHASSIS_STATE` | mcu_to_host | 200 Hz | 24 B | proposed |
| `0x12` | `GIMBAL_STATE` | mcu_to_host | 200 Hz | 12 B | proposed |
| `0x13` | `ACTUATOR_STATE` | mcu_to_host | 50 Hz | 25 B | proposed |
| `0x14` | `POWER_STATE` | mcu_to_host | 10 Hz | 14 B | proposed |
| `0x20` | `REFEREE_RAW` | mcu_to_host | 事件 | 129 B | unconfirmed |
| `0x21` | `REMOTE_RAW` | mcu_to_host | 事件 | 33 B | optional |
| `0x70` | `HEARTBEAT` | bidirectional | 10 Hz | 7 B | proposed |
| `0x71` | `HANDSHAKE_REQ` | host_to_mcu | 事件 | 2 B | proposed |
| `0x72` | `HANDSHAKE_ACK` | mcu_to_host | 事件 | 6 B | proposed |
| `0x73` | `LINK_ERROR` | mcu_to_host | 事件 | 5 B | proposed |

## 字段明细

### `CHASSIS_CMD` (0x01)

底盘速度指令，车体坐标系

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `vx` | `float` | m/s |  |
| `vy` | `float` | m/s |  |
| `wz` | `float` | rad/s |  |

### `GIMBAL_CMD` (0x02)

云台目标角与角速度，绝对角

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `yaw` | `float` | rad | 向左为正 |
| `pitch` | `float` | rad | 向下为正 |
| `yaw_rate` | `float` | rad/s |  |
| `pitch_rate` | `float` | rad/s |  |

### `SHOOTER_CMD` (0x03)

发射指令 + 授权心跳。超时即撤销授权（见规范 §5.2）

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `fire_authorized` | `bool` | - | false 时下位机必须拒绝拨弹 |
| `trigger_count` | `uint8_t` | - | 请求拨弹次数 |
| `friction_level` | `uint8_t` | - | 摩擦轮档位 |

### `CHASSIS_STATE` (0x11)

底盘里程计与 IMU 姿态

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `vx` | `float` | m/s |  |
| `vy` | `float` | m/s |  |
| `wz` | `float` | rad/s |  |
| `roll` | `float` | rad |  |
| `pitch` | `float` | rad |  |
| `yaw` | `float` | rad |  |

### `GIMBAL_STATE` (0x12)

云台实际角与角速度

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `yaw` | `float` | rad |  |
| `pitch` | `float` | rad |  |
| `yaw_rate` | `float` | rad/s |  |

### `ACTUATOR_STATE` (0x13)

执行机构状态汇总

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `enabled_bits` | `uint16_t` | - | 各机构使能位 |
| `motor_current` | `float[4]` | A | 4 路电机电流 |
| `motor_temp` | `uint8_t[4]` | degC | 4 路电机温度 |
| `trigger_state` | `uint8_t` | - | 拨弹机构状态枚举 |
| `friction_rpm` | `uint16_t` | rpm |  |

### `POWER_STATE` (0x14)

电源与热量

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `voltage` | `float` | V |  |
| `current` | `float` | A |  |
| `energy_buffer` | `uint16_t` | J | 剩余能量 |
| `chassis_power` | `float` | W |  |

### `REFEREE_RAW` (0x20)

裁判系统原始帧，帧到达即转发。【待确认：裁判系统接在哪一侧】

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `len` | `uint8_t` | - |  |
| `data` | `uint8_t[128]` | - | 裁判系统原始帧 |

### `REMOTE_RAW` (0x21)

SBUS 原始帧，备用通道

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `len` | `uint8_t` | - |  |
| `data` | `uint8_t[32]` | - |  |

### `HEARTBEAT` (0x70)

链路心跳

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `seq` | `uint8_t` | - |  |
| `uptime_ms` | `uint32_t` | ms |  |
| `status_bits` | `uint16_t` | - |  |

### `HANDSHAKE_REQ` (0x71)

上位机握手请求

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `host_protocol_version` | `uint16_t` | - |  |

### `HANDSHAKE_ACK` (0x72)

下位机握手应答

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `mcu_protocol_version` | `uint16_t` | - |  |
| `capability_bits` | `uint32_t` | - |  |

### `LINK_ERROR` (0x73)

下位机上报链路错误

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `error_code` | `uint8_t` | - |  |
| `detail` | `uint32_t` | - |  |

## 分段

| 段 | 用途 |
|---|---|
| `0x00-0x0F` | 控制类（上→下） |
| `0x10-0x1F` | 状态类（下→上） |
| `0x20-0x2F` | 透传 / 转发 |
| `0x30-0x3F` | 配置 / 标定 |
| `0x70-0x7F` | 链路管理（双向） |
