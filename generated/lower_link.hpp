// 本文件由 scripts/gen_lower_link.py 自动生成，禁止手写。
// 改协议请改 protocol/lower_link.yaml。
#pragma once

#include <cstddef>
#include <cstdint>
#include <cstring>

namespace foray::lower_link {

// MAJOR 不一致时拒绝进入 RUNNING（见 protocol/lower_link.md §7）
constexpr uint16_t kProtocolVersion = 0x0001;
constexpr uint8_t kProtocolMajor = 0;
constexpr uint8_t kProtocolMinor = 1;

// ---- 帧格式 ----
constexpr uint8_t kSof0 = 0xA5;
constexpr uint8_t kSof1 = 0x5A;
// sof(2) + len(1) + seq(1) + msg_id(1)
constexpr size_t kHeaderBytes = 5;
constexpr size_t kTrailerBytes = 2; // crc16
constexpr size_t kMaxPayload = 250;
constexpr size_t kMaxFrame = kHeaderBytes + kMaxPayload + kTrailerBytes;

// ---- 消息号 ----
enum class MsgId : uint8_t {
};

// ---- 超时（ms）----

#pragma pack(push, 1)

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
inline size_t encode_frame(MsgId id, const void *payload, uint8_t payload_len, uint8_t seq,
                          uint8_t *out) {
    if (payload_len > kMaxPayload) {
        return 0;
    }
    out[0] = kSof0;
    out[1] = kSof1;
    out[2] = payload_len;
    out[3] = seq;
    out[4] = static_cast<uint8_t>(id);
    if (payload_len > 0) {
        std::memcpy(out + kHeaderBytes, payload, payload_len);
    }
    // CRC 覆盖 len..payload，不含 SOF
    const uint16_t crc = crc16(out + 2, static_cast<size_t>(payload_len) + 3);
    const size_t tail = kHeaderBytes + payload_len;
    out[tail] = static_cast<uint8_t>(crc & 0xFF);
    out[tail + 1] = static_cast<uint8_t>(crc >> 8);
    return tail + kTrailerBytes;
}

}  // namespace foray::lower_link
