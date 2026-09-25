// 本文件由 scripts/gen_lower_link.py 自动生成，禁止手写。
// 改协议请改 protocol/lower_link.yaml。
#pragma once

#include <cstddef>
#include <cstdint>
#include <cstring>

namespace foray::lower_link {

constexpr uint16_t kProtocolVersion = 0x010;

// ---- 帧格式 ----
constexpr uint8_t  kSof0        = 0xA5;
constexpr uint8_t  kSof1        = 0x5A;
constexpr size_t   kHeaderBytes = 5;  // sof(2)+len(1)+seq(1)+msg_id(1)
constexpr size_t   kTrailerBytes= 2;  // crc16
constexpr size_t   kMaxPayload  = 250;
constexpr size_t   kMaxFrame    = kHeaderBytes + kMaxPayload + kTrailerBytes;

// ---- 消息号 ----
enum class MsgId : uint8_t {
    CHASSIS_CMD        = 0x01,
    GIMBAL_CMD         = 0x02,
    SHOOTER_CMD        = 0x03,
    CHASSIS_STATE      = 0x11,
    GIMBAL_STATE       = 0x12,
    ACTUATOR_STATE     = 0x13,
    POWER_STATE        = 0x14,
    REFEREE_RAW        = 0x20,
    REMOTE_RAW         = 0x21,
    HEARTBEAT          = 0x70,
    HANDSHAKE_REQ      = 0x71,
    HANDSHAKE_ACK      = 0x72,
    LINK_ERROR         = 0x73,
};

// ---- 超时（ms）----
constexpr uint32_t kTimeoutChassisCmdMs = 100;
constexpr uint32_t kTimeoutGimbalCmdMs = 100;
constexpr uint32_t kTimeoutShooterCmdMs = 200;
constexpr uint32_t kTimeoutHeartbeatMs = 500;

#pragma pack(push, 1)

// CHASSIS_CMD  0x01  host_to_mcu  底盘速度指令，车体坐标系
struct CHASSIS_CMD {
    static constexpr MsgId kId = MsgId::CHASSIS_CMD;
    float vx;                         // , m/s
    float vy;                         // , m/s
    float wz;                         // , rad/s
};
static_assert(sizeof(CHASSIS_CMD) == 12, "CHASSIS_CMD 布局与定义不符");

// GIMBAL_CMD  0x02  host_to_mcu  云台目标角与角速度，绝对角
struct GIMBAL_CMD {
    static constexpr MsgId kId = MsgId::GIMBAL_CMD;
    float yaw;                        // 向左为正, rad
    float pitch;                      // 向下为正, rad
    float yaw_rate;                   // , rad/s
    float pitch_rate;                 // , rad/s
};
static_assert(sizeof(GIMBAL_CMD) == 16, "GIMBAL_CMD 布局与定义不符");

// SHOOTER_CMD  0x03  host_to_mcu  发射指令 + 授权心跳。超时即撤销授权（见规范 §5.2）
struct SHOOTER_CMD {
    static constexpr MsgId kId = MsgId::SHOOTER_CMD;
    bool fire_authorized;             // false 时下位机必须拒绝拨弹
    uint8_t trigger_count;            // 请求拨弹次数
    uint8_t friction_level;           // 摩擦轮档位
};
static_assert(sizeof(SHOOTER_CMD) == 3, "SHOOTER_CMD 布局与定义不符");

// CHASSIS_STATE  0x11  mcu_to_host  底盘里程计与 IMU 姿态
struct CHASSIS_STATE {
    static constexpr MsgId kId = MsgId::CHASSIS_STATE;
    float vx;                         // , m/s
    float vy;                         // , m/s
    float wz;                         // , rad/s
    float roll;                       // , rad
    float pitch;                      // , rad
    float yaw;                        // , rad
};
static_assert(sizeof(CHASSIS_STATE) == 24, "CHASSIS_STATE 布局与定义不符");

// GIMBAL_STATE  0x12  mcu_to_host  云台实际角与角速度
struct GIMBAL_STATE {
    static constexpr MsgId kId = MsgId::GIMBAL_STATE;
    float yaw;                        // , rad
    float pitch;                      // , rad
    float yaw_rate;                   // , rad/s
};
static_assert(sizeof(GIMBAL_STATE) == 12, "GIMBAL_STATE 布局与定义不符");

// ACTUATOR_STATE  0x13  mcu_to_host  执行机构状态汇总
struct ACTUATOR_STATE {
    static constexpr MsgId kId = MsgId::ACTUATOR_STATE;
    uint16_t enabled_bits;            // 各机构使能位
    float motor_current[4];           // 4 路电机电流, A
    uint8_t motor_temp[4];            // 4 路电机温度, degC
    uint8_t trigger_state;            // 拨弹机构状态枚举
    uint16_t friction_rpm;            // , rpm
};
static_assert(sizeof(ACTUATOR_STATE) == 25, "ACTUATOR_STATE 布局与定义不符");

// POWER_STATE  0x14  mcu_to_host  电源与热量
struct POWER_STATE {
    static constexpr MsgId kId = MsgId::POWER_STATE;
    float voltage;                    // , V
    float current;                    // , A
    uint16_t energy_buffer;           // 剩余能量, J
    float chassis_power;              // , W
};
static_assert(sizeof(POWER_STATE) == 14, "POWER_STATE 布局与定义不符");

// REFEREE_RAW  0x20  mcu_to_host  裁判系统原始帧，帧到达即转发。【待确认：裁判系统接在哪一侧】
struct REFEREE_RAW {
    static constexpr MsgId kId = MsgId::REFEREE_RAW;
    uint8_t len;                      // 
    uint8_t data[128];                // 裁判系统原始帧
};
static_assert(sizeof(REFEREE_RAW) == 129, "REFEREE_RAW 布局与定义不符");

// REMOTE_RAW  0x21  mcu_to_host  SBUS 原始帧，备用通道
struct REMOTE_RAW {
    static constexpr MsgId kId = MsgId::REMOTE_RAW;
    uint8_t len;                      // 
    uint8_t data[32];                 // 
};
static_assert(sizeof(REMOTE_RAW) == 33, "REMOTE_RAW 布局与定义不符");

// HEARTBEAT  0x70  bidirectional  链路心跳
struct HEARTBEAT {
    static constexpr MsgId kId = MsgId::HEARTBEAT;
    uint8_t seq;                      // 
    uint32_t uptime_ms;               // , ms
    uint16_t status_bits;             // 
};
static_assert(sizeof(HEARTBEAT) == 7, "HEARTBEAT 布局与定义不符");

// HANDSHAKE_REQ  0x71  host_to_mcu  上位机握手请求
struct HANDSHAKE_REQ {
    static constexpr MsgId kId = MsgId::HANDSHAKE_REQ;
    uint16_t host_protocol_version;   // 
};
static_assert(sizeof(HANDSHAKE_REQ) == 2, "HANDSHAKE_REQ 布局与定义不符");

// HANDSHAKE_ACK  0x72  mcu_to_host  下位机握手应答
struct HANDSHAKE_ACK {
    static constexpr MsgId kId = MsgId::HANDSHAKE_ACK;
    uint16_t mcu_protocol_version;    // 
    uint32_t capability_bits;         // 
};
static_assert(sizeof(HANDSHAKE_ACK) == 6, "HANDSHAKE_ACK 布局与定义不符");

// LINK_ERROR  0x73  mcu_to_host  下位机上报链路错误
struct LINK_ERROR {
    static constexpr MsgId kId = MsgId::LINK_ERROR;
    uint8_t error_code;               // 
    uint32_t detail;                  // 
};
static_assert(sizeof(LINK_ERROR) == 5, "LINK_ERROR 布局与定义不符");

#pragma pack(pop)

// ---- CRC-16/CCITT-FALSE ----
inline uint16_t crc16(const uint8_t *data, size_t len) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < len; ++i) {
        crc ^= static_cast<uint16_t>(data[i]) << 8;
        for (int b = 0; b < 8; ++b) {
            crc = (crc & 0x8000) ? static_cast<uint16_t>((crc << 1) ^ 0x1021)
                                  : static_cast<uint16_t>(crc << 1);
        }
    }
    return crc;
}

// ---- 组帧 ----
// 返回写入 out 的字节数；out 容量须 >= kHeaderBytes + payload_len + kTrailerBytes。
inline size_t encode_frame(MsgId id, const void *payload, uint8_t payload_len,
                          uint8_t seq, uint8_t *out) {
    if (payload_len > kMaxPayload) return 0;
    out[0] = kSof0;
    out[1] = kSof1;
    out[2] = payload_len;
    out[3] = seq;
    out[4] = static_cast<uint8_t>(id);
    if (payload_len) std::memcpy(out + kHeaderBytes, payload, payload_len);
    const uint16_t crc = crc16(out + 2, static_cast<size_t>(payload_len) + 3);  // len..payload
    const size_t tail = kHeaderBytes + payload_len;
    out[tail]     = static_cast<uint8_t>(crc & 0xFF);
    out[tail + 1] = static_cast<uint8_t>(crc >> 8);
    return tail + kTrailerBytes;
}

}  // namespace foray::lower_link
