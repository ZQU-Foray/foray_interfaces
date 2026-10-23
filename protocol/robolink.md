# 上下位机链路协议（v0.2）

> 候选稿：由电控仓 `controller_code/.docs` 三份文档压编而成（协议草案 v0.2 2026-09-20 冻结，
> 决议记录 v0.3 2026-09-30 修订，组件实施方案 v1.0）。本文为 RoboLink 的**全栈契约**：
> 帧层 + 槽位层 + 消息层。实现状态见 §9。
>
> 标注【补注】的条目为源文档未明确、本文按组织约定补写的语义，**待 review 冻结**。
>
> v0.2 修订（2026-10-23）：云台角统一为世界系 rad、不区分圈数；`gimbal_yaw_rate` /
> `gimbal_pitch_rate` 改为角速度前馈；冻结 `safety_state` 取值与各模式可驱动的子系统；
> 新增云台姿态反馈 `GIMBAL_ATTITUDE`（0x30），携带 IMU 就绪状态。

## 与 lower_link 契约的关系（三个待裁决点）

本仓已有 [`lower_link.md`](lower_link.md)（PR #1 合入，仅内容层、YAML 单源、消息表留白）。
RoboLink 与其在以下三点上立场不同，PR 讨论时需先裁决收编方向：

| # | 冲突点 | lower_link 立场 | RoboLink 立场 |
| --- | --- | --- | --- |
| 1 | 帧层归属 | 帧格式不属契约仓，归链路实现 | 帧层（魔数/CRC/定界）已冻结且双端逐位对账（黄金向量），作为契约一并登记 |
| 2 | 时间戳 | 每消息必须带绝对时间 stamp（int32 秒 + uint32 纳秒，Unix 纪元） | 帧级 u32 单调微秒，仅单端测量；跨端时延一律用序号匹配（四序号法），明确不做跨端时钟同步 |
| 3 | 消息号分段 | 按方向分段：0x00-0x0F 上→下 · 0x10-0x1F 下→上 · 0x70-0x7F 链路管理 | 按功能分段：0x01-0x05 链路管理 · 0x10 状态 · 0x20 控制 · 0x30 模块状态 · 0x21-0x6F 预留 |

v0.2 新增的 `GIMBAL_ATTITUDE` 按 RoboLink 现行立场定义（单端微秒时间戳、功能分段编号 0x30）；
若裁决改走 lower_link 立场，其时间字段与编号随之调整。

## 0. 定位与边界

| 项 | 规定 |
| --- | --- |
| 链路两端 | STM32H723 下位机 ↔ PC 上位机；PC 负责感知/规划/目标生成，MCU 负责实时闭环/执行器/安全 |
| 传输介质 | USB CDC（Full-Speed，端点包 64 B，主机 1 ms 帧调度） |
| 字节序 | 全部小端 |
| 浮点 | IEEE 754 单精度（float32）；禁用 double |
| 单位 | 全 SI：m/s、rad、rad/s、s |
| 坐标系 | 遵循 REP-103 / REP-105；底盘速度为机体系（x 前、y 左、z 上），`chassis_wz` 绕 z 轴逆时针为正 |
| 云台角 | 全队统一：**yaw 向左为正、pitch 向下为正**（与 DJI NED 约定不同）。云台目标与反馈均为**世界系角度，单位 rad，不区分圈数**（π 与 3π 等价）：MCU 按最短路径跟踪，偏差达到 150° 后锁定当前转向、回到 150° 以内再按最短路径，避免目标在正后方附近时原地来回抖动。需要连续 yaw（预测、滤波）时由 PC 自行展开，不进协议 |
| 云台系与世界系 | 云台系：x 沿枪管向前、y 向左、z 向上。世界系：z 轴竖直向上，yaw 零点为 **MCU 本次启动时**云台的水平朝向，没有绝对航向，并随陀螺零偏缓慢漂移。MCU 每次启动都会重置 yaw 零点：PC 以 `SYSTEM_STATUS.uptime_ms` 回退或重新进入 READY 判定，并作废全部世界系目标与缓存。云台姿态由 `GIMBAL_ATTITUDE` 以四元数上报（§4.8），ZYX 分解所得 yaw/pitch 与控制目标同一口径 |
| 变长字段 | 单条消息载荷内禁止变长字段（ERROR 的 detail 为唯一例外，见 §4.5）；载荷长度为编译期常量 |
| 控制权 | 遥控器始终先进 MCU；PC 指令仅在当前模式允许的控制路径内生效，由 MCU 本地状态机裁决；不采用租约/令牌 |

## 1. 帧层

### 1.1 帧布局

```text
 Magic 0xD3 0x91          2 B                        
 Version                  1 B   = 0x02               
 Frame Flags              1 B                        
 Frame Length             2 B   整帧字节数（含头与CRC）
 Frame Sequence           2 B                        
 Timestamp                4 B   发送端单调微秒        
 Slot Count               1 B                       
 Reserved                 1 B   = 0                 

 Slot[0] … Slot[N-1]      变长                       

 CRC-32                   4 B                        

帧头 14 B；整帧长度 ∈ [18, 512] B。
```

### 1.2 帧头字段

| 字段 | 语义 | 类型/单位 | 取值范围 | 缺失/无效语义 |
| --- | --- | --- | --- | --- |
| Magic | 帧同步字，两字节均 ≥ 0x80，避开 ASCII 调试命令与圈内常用首字节 | u8[2] | `0xD3 0x91` | 不匹配即丢弃并重扫 |
| Version | 协议主版本 | u8 | `0x02` | ≠ 0x02 判头错，整候选头重扫 |
| Frame Flags | bit0 ACK_PRESENT：帧内含 ACK 槽位；bit1 KEEPALIVE：零槽保活帧；其余位保留 | u8 | 已知掩码 `0x03` | 未知位非 0 判头错 |
| Frame Length | 整帧字节数，含 14 B 头与 4 B CRC | u16 / B | [18, 512] | 越界判头错 |
| Frame Sequence | 每帧 +1，u16 回绕，仅用于丢帧检测，不重传 | u16 | 全域 | 回绕差值运算，跨连接不可比较 |
| Timestamp | 发送端单调时钟 | u32 / µs | 全域，约 71.6 min 回绕 | 仅单端测量用；跨端时延用四序号法（§5.3），必须按回绕安全差值运算 |
| Slot Count | 本帧槽位数 | u8 | 0 仅允许 KEEPALIVE 帧，>0 时不得置 KEEPALIVE | 违反判头错 |
| Reserved | 保留 | u8 | `0` | ≠ 0 判头错 |

### 1.3 CRC-32

| 参数 | 值 |
| --- | --- |
| 算法 | CRC-32/ISO-HDLC（zlib / IEEE 802.3 同款） |
| 多项式 / init | 0x04C11DB7（反射 0xEDB88320）/ 0xFFFFFFFF |
| refin / refout / xorout | true / true / 0xFFFFFFFF |
| 校验值（"123456789"） | 0xCBF43926 |
| 覆盖范围 | Magic 首字节至 CRC 字段前一字节（含全部槽位） |
| 线上字节序 | 小端 |

### 1.4 定界与解析状态机

- 字节流状态机 `SCAN_MAGIC → HEADER → BODY → VERIFY`，容忍半帧、粘包、多帧连发；
- 任一失败（魔数/版本/长度边界/保留位）从候选头第二字节起重扫，一次假同步的代价上界为一个候选头（≤ 14 B）；
- CRC 失败丢弃整帧、`crc_errors` 计数 +1，从帧尾后继续扫描；USB bulk 自带硬件 CRC，常态该计数应为 0；
- 不做帧头独立 CRC：变长帧已由 Length + CRC-32 + Magic 重扫覆盖；
- 单轮解析工作量有限制（建议 ≤ 8 帧），避免高优先级任务被突发流量长占。

## 2. 槽位层

### 2.1 槽位头（6 B）

| 字段 | 语义 | 类型 | 取值范围 | 缺失/无效语义 |
| --- | --- | --- | --- | --- |
| Message Type | 消息类型编号，见 §3 | u8 | 号段表 | 未注册类型整帧丢弃并计数 |
| Slot Flags | bit0 ACK_REQ；bit1 LATEST_ONLY；bit2 EVENT；bit3 RESPONSE | u8 | 已知掩码 `0x0F` | 未知位非 0 拒收；与注册表类属性不一致视为协议错误，整帧丢弃 |
| Message Seq | 该消息独立序号，u16 回绕 | u16 | 全域 | 跨连接无意义（进 READY 时归零） |
| Payload Length | 载荷字节数 | u16 | [0, 486] | 越界拒收；短于注册表最小长度整帧丢弃并计数 |

### 2.2 类属性与调度

| 类 | 覆盖语义 | 投递方式 |
| --- | --- | --- |
| LATEST | 最新值覆盖，允许被同类新消息覆盖 | 每类型一格的最新值快照邮箱 |
| EVENT | 事件类，不得被覆盖 | 独立有界队列（满则丢弃最旧并计数） |
| STATUS | 状态类，按频率预算发送 | 状态缓存 |

调度优先级由类派生：`EVENT(ACK_REQ) > LATEST(控制) > STATUS(按预算)`。优先级不在线上传输。

## 3. 消息表与号段

### 3.1 第一版消息集（8 条）

| Type | 名称 | 方向 | 类 | 载荷 | 频率预算 |
| --- | --- | --- | --- | --- | --- |
| 0x01 | HELLO | 双向 | EVENT | 26 B（§4.1） | 10 Hz |
| 0x02 | HELLO_ACK | 双向 | EVENT + RESPONSE | 8 B（§4.2） | 10 Hz |
| 0x03 | HEARTBEAT | 双向 | STATUS | 0 B | 50 Hz |
| 0x04 | ACK | 双向 | STATUS + RESPONSE | 7 B（§4.4） | 事件驱动 |
| 0x05 | ERROR | 双向 | EVENT | 2 B + ≤64 B（§4.5） | 事件驱动 |
| 0x10 | SYSTEM_STATUS | MCU → PC | STATUS | 28 B 核心 + 24 B 可选诊断（§4.6） | 200 Hz |
| 0x20 | CONTROL_SNAPSHOT | PC → MCU | LATEST | 48 B（§4.7） | 1 kHz（开发起步值，阶段 3 实测后冻结） |
| 0x30 | GIMBAL_ATTITUDE | MCU → PC | STATUS | 36 B（§4.8） | 1 kHz（开发起步值，阶段 3 实测后冻结）；仅当 PC 的 HELLO 声明支持时发送 |

### 3.2 号段预留

| 号段 | 用途 |
| --- | --- |
| 0x21–0x2F | 控制类扩展：FIRE_REQUEST(0x22) 等；PC→MCU 决策类长帧（≤2 条、Latest 类，配额见 §6）；CONTROL_ENABLE(0x21) 不再引入，使能语义统一走 CONTROL_SNAPSHOT.flags |
| 0x30–0x3F | 模块状态：GIMBAL_ATTITUDE(0x30)；底盘/射击/电源/裁判系统待定 |
| 0x40–0x4F | 参数读写 |
| 0x50–0x5F | 调试与日志（含调试用原始数据流，启用前必须实测带宽） |
| 0x60–0x6F | 视觉 |

## 4. 字段级定义（全部显式小端编码，禁止结构体直传）

### 4.1 HELLO（26 B）

| 偏移 | 字段 | 语义 | 类型/单位 | 取值范围 | 缺失/无效语义 |
| --- | --- | --- | --- | --- | --- |
| 0 | proto_ver_major | 协议主版本 | u8 | = 2 | 不匹配进入降级协商（§7.2） |
| 1 | proto_ver_minor | 消息集能力小版本 | u8 | ≥ 0 | — |
| 2 | device_type | 0=MCU 下位机，1=PC | u8 | {0, 1} | 其它值拒收【补注】 |
| 3..5 | fw_version | 固件 主.次.修订 | u8[3] | 全域 | 全 0 表示未 burnt 版本信息【补注】 |
| 6..9 | git_short | 固件 commit 摘要低 32 bit | u8[4] | 全域 | 全 0 表示未知【补注】 |
| 10..17 | capabilities | 支持的 MsgType 位图 | u64 | bit n ⇔ Type n，Type 必须 < 64 | 位图无交集则停留 HELLO 阶段，不进 READY；v0.2 起新增的 MCU→PC 消息（GIMBAL_ATTITUDE）只在对端声明支持时发送，因为接收方遇到未注册类型会丢弃整帧 |
| 18..19 | heartbeat_period_ms | 本端心跳周期 | u16 / ms | > 0 | 0 视为非法，按默认 50 处理【补注】 |
| 20..21 | max_frame_bytes | 本端**可接收**的最大帧 | u16 / B | MCU 报 512；PC 报 ≥ 96 | 对端声明不足以覆盖本端最长发送帧时禁用长帧并计数，不阻塞进入 READY |
| 22..25 | device_id_digest | 设备标识非敏感摘要 | u32 | 全域 | 0 表示未提供【补注】 |

### 4.2 HELLO_ACK（8 B）

| 偏移 | 字段 | 语义 | 类型 | 取值范围 | 缺失/无效语义 |
| --- | --- | --- | --- | --- | --- |
| 0..1 | acked_msg_seq | 被确认的 HELLO 的 Message Seq | u16 | 全域 | — |
| 2 | negotiated_major | 协商出的主版本 | u8 | = min(双方 major) | — |
| 3 | status | 0=OK；1=版本不兼容；2=能力无交集 | u8 | {0, 1, 2} | 非 0 不进入 READY |
| 4..5 | heartbeat_period_ms | 本端心跳周期 | u16 / ms | > 0 | 同 HELLO |
| 6..7 | reserved | 保留 | u16 | = 0 | ≠ 0 拒收【补注】 |

### 4.3 HEARTBEAT（0 B）

零载荷，仅靠帧头（Frame Sequence + Timestamp）承载活性。判活门限见 §5.1。

### 4.4 ACK（7 B）

| 偏移 | 字段 | 语义 | 类型 | 取值范围 | 缺失/无效语义 |
| --- | --- | --- | --- | --- | --- |
| 0 | acked_msg_type | 被确认消息的类型 | u8 | §3 号段 | — |
| 1..2 | acked_msg_seq | 被确认消息的 Message Seq | u16 | 全域 | — |
| 3 | ack_state | 0=RECEIVED；1=ACCEPTED；2=APPLIED；3=REJECTED（停在哪一步） | u8 | {0..3} | — |
| 4..5 | error_code | 0=无；1=UNSUPPORTED；2=LENGTH_MISMATCH；3=CLASS_MISMATCH；4=DIRECTION_VIOLATION；5=EXEC_FAILED（为什么） | u16 | {0..5} | — |
| 6 | reserved | 保留 | u8 | = 0 | ≠ 0 拒收【补注】 |

无超时重发与幂等去重；发送方对"未收到 ACK"的恢复按优先级：等下一周期 SYSTEM_STATUS 观测效果 → 重发 HELLO/等心跳判活 → 断链重连全量重建。唯一不可重复执行的操作类（如 FIRE_REQUEST）由发送方自律：收到 ACCEPTED 级 ACK 或链路断开前不重复发送。

### 4.5 ERROR（2 B + N，N ≤ 64）

| 偏移 | 字段 | 语义 | 类型 | 取值范围 | 缺失/无效语义 |
| --- | --- | --- | --- | --- | --- |
| 0..1 | error_code | 错误码，取值同 ACK.error_code | u16 | {0..5} | — |
| 2..2+N-1 | detail | 人类可读详情 | u8[N] | N ∈ [0, 64] | N=0 表示无详情；超长由发送侧截断 |

### 4.6 SYSTEM_STATUS（28 B 核心 + 24 B 可选诊断尾部）

常态只发核心（整帧 52 B）；诊断尾部低频附加（整帧 76 B）。接收侧按"剩余 ≥ 24 B"判定尾部是否存在。

核心（偏移相对载荷起点）：

| 偏移 | 字段 | 语义 | 类型/单位 | 取值范围 | 缺失/无效语义 |
| --- | --- | --- | --- | --- | --- |
| 0..3 | uptime_ms | MCU 开机时长 | u32 / ms | 全域 | — |
| 4 | mode | 当前生效模式（裁决结果，非期望） | u8 | 0 MANUAL · 1 AUTO_NAV · 2 VISION_TRACK · 3 PATROL · 4 GIMBAL_ONLY · 5 SHOOTER_ONLY · 6 SAFETY · 7 IDLE | 未知值按 SAFETY 处理并计数【补注】 |
| 5 | control_source | 当前控制源 | u8 | 0 NONE · 1 REMOTE · 2 PC · 3 AUTO · 4 SAFETY | 未知值按 NONE 处理【补注】 |
| 6 | safety_state | 控制权安全状态 | u8 | 0 未收到快照 · 1 快照有效（PC 控制中）· 2 控制失联 · 3 急停 | 未知值按 2 处理【补注】 |
| 7 | reserved | 保留 | u8 | = 0 | ≠ 0 拒收【补注】 |
| 8..11 | last_rx_control_seq | 最近**收到**的 control_seq | u32 | 全域 | 从未收到过为 0 |
| 12..15 | last_accepted_control_seq | 最近通过权限与参数检查的 control_seq | u32 | 全域 | 同上 |
| 16..19 | last_applied_control_seq | 最近下发给控制器的 control_seq | u32 | 全域 | 同上 |
| 20..21 | control_msg_age_ms | 距上次接受快照的时长 | u16 / ms | [0, 65535] | 失联后持续增长，不冻结【补注】 |
| 22 | link_state | 0 DISCONNECTED · 1 USB_CONNECTED · 2 READY · 3 ACTIVE | u8 | {0..3} | — |
| 23 | reserved | 保留 | u8 | = 0 | — |
| 24..27 | fault_flags | 故障位图，位定义归各模块 | u32 | 全域 | 0 = 无故障 |

诊断尾部（可选）：

| 偏移 | 字段 | 语义 | 类型 | 缺失/无效语义 |
| --- | --- | --- | --- | --- |
| 28..31 | rx_frames | 累计接受帧数 | u32 | 尾部不附带即视为本拍不上报 |
| 32..35 | tx_frames | 累计发送帧数 | u32 | 同上 |
| 36..39 | crc_errors | 累计 CRC 失败数 | u32 | 常态应为 0 |
| 40..41 | rx_overflow | 接收环形缓冲溢出计数 | u16 | — |
| 42..43 | tx_busy_drop | 发送忙丢帧计数 | u16 | 控制类必须为 0 |
| 44..45 | queue_drop | 事件队列丢弃计数 | u16 | — |
| 46 | event_queue_depth | 事件队列当前深度 | u8 | — |
| 47 | reserved | 保留 | u8 | — |
| 48..51 | reserved_wide | 保留 | u32 | — |

### 4.7 CONTROL_SNAPSHOT（48 B）

| 偏移 | 字段 | 语义 | 类型/单位 | 取值范围 | 缺失/无效语义 |
| --- | --- | --- | --- | --- | --- |
| 0..3 | control_seq | 控制快照序号，单调递增 | u32 | 全域 | — |
| 4 | source | 目标来源声明 | u8 | 0 NONE · 1 REMOTE · 2 PC · 3 AUTO · 4 SAFETY | 2 PC、3 AUTO 生效；4 SAFETY 视为急停请求；0 NONE、1 REMOTE 只记账不生效（遥控器始终直连 MCU）；未知值按 NONE |
| 5 | mode | 期望模式（是否生效由 MCU 裁决，经 SYSTEM_STATUS.mode 回读），决定 PC 可驱动的子系统，见下表 | u8 | 同 §4.6 mode 枚举 | 未知值按 IDLE 处理并计数【补注】 |
| 6..7 | flags | bit0 底盘使能 · bit1 云台使能 · bit2 射击使能 · bit3 急停请求；其余保留 | u16 | 已知掩码 `0x000F` | 对应位清零时该子系统字段视为缺失（忽略）；保留位非 0 拒收；bit3 置位时全部子系统按失联行为处理（§5.2），`SYSTEM_STATUS.mode` 报 SAFETY |
| 8..11 | chassis_vx | 机体系纵向速度（x 前） | f32 / (m/s) | 物理上限由车型限幅 | bit0=0 时忽略 |
| 12..15 | chassis_vy | 机体系横向速度（y 左） | f32 / (m/s) | 同上 | bit0=0 时忽略 |
| 16..19 | chassis_wz | 机体系绕 z 角速度，逆时针为正 | f32 / (rad/s) | 同上 | bit0=0 时忽略 |
| 20..23 | gimbal_yaw | 云台世界系 yaw 目标角，向左为正，不区分圈数（§0） | f32 / rad | 有限值 | bit1=0 时忽略 |
| 24..27 | gimbal_pitch | 云台世界系 pitch 目标角，向下为正 | f32 / rad | MCU 按机械范围钳位 | bit1=0 时忽略 |
| 28..31 | gimbal_yaw_rate | yaw 目标角速度前馈：`gimbal_yaw` 对时间的导数（世界系） | f32 / (rad/s) | MCU 按云台最大轨迹速度限幅 | 0 表示目标静止；bit1=0 时忽略 |
| 32..35 | gimbal_pitch_rate | pitch 目标角速度前馈：`gimbal_pitch` 对时间的导数 | f32 / (rad/s) | 同上 | 同上 |
| 36..39 | friction_rads | 摩擦轮目标角速度（左右轮同速） | f32 / (rad/s) | 0 = 停转 | bit2=0 时忽略 |
| 40..43 | feeder_rads | 拨弹盘连续目标速度；单发请求走 FIRE_REQUEST 事件 | f32 / (rad/s) | 0 = 停转 | bit2=0 时忽略 |
| 44..45 | validity_hint_ms | 有效期提示，仅允许收紧本地硬超时 | u16 / ms | [0, 50] | 0 表示无提示（按本地硬超时）；≥ 50 按 50 处理 |
| 46..47 | reserved | 保留 | u16 | = 0 | ≠ 0 拒收【补注】 |

云台目标的跟踪方式：角度是目标，角速度是前馈。MCU 用跟踪微分器生成平滑的参考轨迹，
参考受云台最大速度与最大加速度约束；给出前馈时按"运动目标"跟踪，匀速目标无稳态滞后。
下一份快照到来之前，MCU 按前馈角速度外推目标角；快照过期、急停或当前模式不再驱动云台时
停止外推，保持已到达的目标。只给角度、前馈填 0 时，目标被当作静止终点平滑趋近。
需要角加速度前馈时，按 §7.1 在载荷末尾追加 `gimbal_yaw_accel` / `gimbal_pitch_accel`。

各模式下 PC 可驱动的子系统（生效子系统 = 本表 ∩ flags 使能位）：

| mode | 底盘 | 云台 | 射击 |
| --- | --- | --- | --- |
| 0 MANUAL、6 SAFETY、7 IDLE | — | — | — |
| 1 AUTO_NAV | ✓ | ✓ | — |
| 2 VISION_TRACK | — | ✓ | ✓ |
| 3 PATROL | ✓ | ✓ | ✓ |
| 4 GIMBAL_ONLY | — | ✓ | — |
| 5 SHOOTER_ONLY | — | — | ✓ |

### 4.8 GIMBAL_ATTITUDE（36 B）

云台 IMU 的姿态与角速度，MCU 每产出一份新的 IMU 解算结果更新一次，按频率预算发送。

| 偏移 | 字段 | 语义 | 类型/单位 | 取值范围 | 缺失/无效语义 |
| --- | --- | --- | --- | --- | --- |
| 0..3 | sample_time_us | IMU 采样时刻 | u32 / µs | 与帧头 Timestamp **同一 MCU 单调时钟**，回绕安全差值运算 | — |
| 4..19 | q_w, q_x, q_y, q_z | 云台系到世界系的单位四元数，标量在前 | 4 × f32 | 模长 1 | flags bit0 = 0 时不可用 |
| 20..31 | gyro_x, gyro_y, gyro_z | 云台系角速度，已扣除陀螺零偏 | 3 × f32 / (rad/s) | — | 同上 |
| 32 | imu_state | 0 SETTLING · 1 READY · 2 DEGRADED，见下 | u8 | {0, 1, 2} | 未知值按 SETTLING 处理【补注】 |
| 33 | flags | bit0 ATTITUDE_VALID：姿态解算有效；其余保留 | u8 | 已知掩码 `0x01` | 保留位非 0 时忽略保留位【补注】 |
| 34..35 | reserved | 保留 | u16 | = 0 | 接收侧忽略【补注】 |

- **imu_state**：
  - SETTLING：恒温或上电零偏标定进行中。冷启动约需 30 s；MCU 系统复位（调试器复位、看门狗、烧录）后沿用复位前的标定，温度未变时约 0.2 s 即转 READY，烧录期间加热停摆而降温时回到恒温后约 5–10 s。roll/pitch 已可用，yaw 零偏未定；**MCU 不接受世界系云台目标**（`last_applied_control_seq` 不前进），云台不做世界系稳定；
  - READY：零偏已标定，世界系目标正常执行；
  - DEGRADED：零偏标定超时（标定期间持续晃动），按未标定运行，yaw 漂移明显偏大，世界系目标仍执行。
- **欧拉角**：`yaw = atan2(2(q_w q_z + q_x q_y), 1 − 2(q_y² + q_z²))`，`pitch = asin(2(q_w q_y − q_z q_x))`，
  即 ZYX 分解，yaw 左转为正、pitch 低头为正，与 CONTROL_SNAPSHOT 的云台目标同一口径。
- **时间对齐**（PC 侧建议做法，协议不承担跨端时钟同步）：PC 记录每帧帧头 Timestamp 与本机接收时刻，
  取一段时间内"接收时刻 − Timestamp"的最小值作为 MCU 时钟到本机时钟的偏移，再把 `sample_time_us`
  换算到本机时间，与图像时间戳插值。样本在 MCU 内的停留时间（帧头 Timestamp − sample_time_us）常态小于 2 ms。
- **发送条件**：仅当 PC 的 HELLO `capabilities` 声明了 0x30（bit 48）时发送；未声明的旧 PC 收不到本消息。

## 5. 连接状态机与失联保护

### 5.1 状态机

```text
DISCONNECTED ──USB 枚举成功──▶ USB_CONNECTED
USB_CONNECTED ──HELLO 发出且 HELLO_ACK 校验通过──▶ READY
READY ──首次有效控制或状态帧收发──▶ ACTIVE
任意状态 ──USB 断开 或 心跳超时──▶ DISCONNECTED
```

- 链路判活：任一方向 500 ms 内无任何合法帧 → LINK_DOWN；
- 序号重置：进入 READY 时双方 Frame Sequence 与全部 Message Seq 归零，事件队列清空；序号只在单次连接内有意义；
- 重连重建：进入 READY 后 MCU 立即发送一次完整 SYSTEM_STATUS，PC 以之为基准重建状态，此前缓存作废；
- 控制失联独立判活：距上次**接受**的 CONTROL_SNAPSHOT 超过本地硬超时（当前 50 ms；v0.3 计划收紧至 20–30 ms，可配置）即控制失联，与链路判活相互独立。

### 5.2 失联后行为

1. 底盘运动目标立即归零；
2. 云台保持最后目标并切入本地稳定模式（不回中、不锁电），目标停止按前馈外推；
3. 摩擦轮与拨弹立即关闭；
4. 链路恢复后**不自动恢复任何危险动作**：射击与自主移动需重新收到带对应使能位的快照且本地状态机允许。

### 5.3 六段延迟分解（四序号法）

以 `sent（PC 生成）/ received（MCU 收到）/ accepted（通过检查）/ applied（下发执行器）` 四个 control_seq + 单端时间戳区分六种情况；**跨端指标一律序号法，时间戳不做跨端同步**。

## 6. 配额护栏与带宽预算

| 项 | 值 |
| --- | --- |
| 高频通道整帧上限 | ≤ 72 B（CONTROL_SNAPSHOT 常态帧；STATUS/LATEST 类常态不得超过） |
| MCU 发送路径整帧上限 | ≤ 96 B（发送缓冲与组帧按此收敛；MCU 不发长帧） |
| 长帧 | 仅 PC→MCU、Latest 类、≤ 2 条消息、合计 ≤ 20 Hz、任一 50 ms 窗口 ≤ 1 帧、单帧 ≤ 512 B |
| 决策通道有效带宽 | 20 Hz × 512 B = 10.24 KB/s（将来行为链消息必须在此预算内设计） |
| 队头阻塞量化 | 单个 512 B 长帧线上占用 512 ÷ 690 KB/s ≈ 0.74 ms；受影响控制帧占比 1.48%（20 Hz 下） |

常态带宽预算（设计值，阶段 3 实测后冻结频率）：下行 CONTROL_SNAPSHOT 1 kHz × 72 B ≈ 72 KB/s；上行 GIMBAL_ATTITUDE 1 kHz × 60 B ≈ 60 KB/s（与 SYSTEM_STATUS 同帧时省去 18 B 帧头与 CRC），SYSTEM_STATUS 200 Hz × 52 B（常态）/ 76 B（含诊断）≈ 10.4–15.2 KB/s，上行合计约 75 KB/s；HEARTBEAT 50 Hz × 18 B ≈ 0.9 KB/s × 2（有其它帧时不单独发送）；ACK/ERROR 事件驱动忽略不计。相对实测 690 KB/s 余量约 9 倍。**禁止任何消息以全帧 512 B 常态发送。**

## 7. 演进规则与版本协商

### 7.1 载荷演进

- **优先用既有 `reserved` 字段原地扩展**；无法原地扩展时才末尾追加字段；
- 旧接收方按 Payload Length 截断读取，超长字段忽略；
- 字段语义、单位、编码方式变更**必须启用新 MsgType 编号**；
- 载荷短于注册表最小长度视为协议错误，整帧丢弃并计数。

### 7.2 版本协商

双方取 `min(major)`；major 不同时仅使用双方 capabilities 交集内的消息，无交集则停留 HELLO 阶段周期重试，不进入 READY。

## 8. 性能验收指标

| 指标 | 目标 |
| --- | --- |
| 控制端到端（PC 生成 → MCU 应用） | 中位 ≤ 3 ms，p99 ≤ 10 ms（校准后 stretch：≤ 2 / ≤ 8 ms） |
| 长帧负载下的控制恶化 | 叠加 20 Hz × 512 B 合成长帧后 p99 恶化 ≤ 1 ms 且单次额外等待 ≤ 1 ms |
| 高负载下控制延迟恶化 | 叠加状态与日志满载时 p99 ≤ 15 ms |
| 30 min 浸泡 | crc_errors = 0；rx_overflow = tx_busy_drop = 0（控制类）；事件类零丢失 |
| 断连恢复 | 检出 ≤ 500 ms；HELLO 到 READY ≤ 2 s |
| 链路占用 | 稳态每方向 ≤ 100 KB/s |
| MCU 资源 | 解析+通信任务 CPU ≤ 5%；栈余量 ≥ 25%；无堆分配 |

## 9. 实现与验证状态（登记用）

| 端 | 状态 |
| --- | --- |
| MCU 协议栈（帧/槽位/消息/交付邮箱） | 已实现于 `controller_code/Libraries/Protocol/robolink/`，含 v0.2 的 GIMBAL_ATTITUDE；主机测试全绿，黄金帧由独立 Python 生成器产出，CRC 与 zlib 逐位一致 |
| MCU 链路任务（CDC 消费者/HELLO/心跳/控制快照/姿态反馈） | 阶段 0b/1 已实现，握手、拔线重连、30 分钟浸泡板级通过（2026-10-23）；阶段 2 控制快照与 v0.2 改动主机测试全绿，板级验收待做 |
| PC 侧实现 | `foray_platform` 分支 `feat/usb-cdc` 有候选编解码（v0.1 口径，云台角按 deg）；改用 rad 与 GIMBAL_ATTITUDE 解码见分支 `feat/robolink-v0.2` |
| 双端上线 | 从未上线，无兼容性负担 |
