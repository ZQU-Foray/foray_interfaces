// 本文件由 scripts/gen_lower_link.py 自动生成，禁止手写。
// 改协议请改 protocol/lower_link.yaml。
#pragma once

#include <cstddef>
#include <cstdint>
#include <cstring>

namespace foray::lower_link {

// MAJOR 不一致时拒绝进入 RUNNING（见 protocol/lower_link.md 的「版本」）
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

// 帧内头部字段偏移——由 frame 段推导，勿手写。
// 编解码一律引用这些常量，代码里不应再出现字面量偏移。
constexpr size_t kLenOffset = 2;
constexpr size_t kSeqOffset = 3;
constexpr size_t kMsgIdOffset = 4;

// CRC 覆盖范围，由 frame.crc_covers 推导：len + seq + msg_id + payload
constexpr size_t kCrcOffset = 2;
constexpr size_t kCrcRegionBytes = 3; // 固定部分，payload 另按 LEN 计入
static_assert(kCrcOffset + kCrcRegionBytes == kHeaderBytes,
              "CRC 覆盖范围未延伸到载荷起点——帧结构与 crc_covers 不一致");

// ---- 消息号 ----
enum class MsgId : uint8_t {
};

// ---- 超时（ms）----

#pragma pack(push, 1)

#pragma pack(pop)

// ---- 消息载荷长度 ----
// 消息号 -> 期望载荷字节数；未定义的消息号返回 0。
// LEN 与 ID 对不上说明两侧版本不一致——必须丢弃，不能按猜测解释。
// 必须放在消息结构体之后：sizeof 需要完整的类型。
// 消息表为空：暂无已知消息号，一切 ID 都返回 0。
constexpr size_t expected_payload_size(MsgId) { return 0; }

// ---- CRC-16/CCITT-FALSE ----
// 标准 check value：CRC("123456789") == 0x29B1
// （init 0xFFFF、poly 0x1021、不反转、不异或）
// 下面的 static_assert 是这套方案的锚点。上位机与下位机包含同一份生成代码，
// 「生成物一致 + 编译通过」并不能证明它是对的——实现对不上标准时，两侧会
// 一致地错下去，直到跟 CAN 上的电调、跟裁判系统对接才暴露。这里让它在编译期暴露。
inline constexpr uint8_t kCrcCheckVector[9] = {'1', '2', '3', '4', '5', '6', '7', '8', '9'};

constexpr uint16_t crc16(const uint8_t *data, size_t len) {
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

static_assert(crc16(kCrcCheckVector, 9) == 0x29B1,
              "CRC-16/CCITT-FALSE 实现与标准 check value 不符");

// ---- 组帧 ----
// 返回写入 out 的字节数；out 容量须 >= kHeaderBytes + payload_len + kTrailerBytes。
// 参数非法（payload 与长度不匹配、超限、out 为空）时返回 0。
// 优先用下面每个消息的强类型 encode()——它把长度锁成 sizeof。
inline size_t encode_frame(MsgId id, const void *payload, uint8_t payload_len, uint8_t seq,
                          uint8_t *out) {
    if (out == nullptr || payload_len > kMaxPayload) {
        return 0;
    }
    if (payload == nullptr && payload_len > 0) {
        return 0;
    }
    out[0] = kSof0;
    out[1] = kSof1;
    out[kLenOffset] = payload_len;
    out[kSeqOffset] = seq;
    out[kMsgIdOffset] = static_cast<uint8_t>(id);
    if (payload_len > 0) {
        std::memcpy(out + kHeaderBytes, payload, payload_len);
    }
    // CRC 覆盖范围由 kCrcOffset / kCrcRegionBytes 给出，不含 SOF
    const uint16_t crc = crc16(out + kCrcOffset, kCrcRegionBytes + payload_len);
    const size_t tail = kHeaderBytes + payload_len;
    out[tail] = static_cast<uint8_t>(crc & 0xFF);
    out[tail + 1] = static_cast<uint8_t>(crc >> 8);
    return tail + kTrailerBytes;
}

// ---- 解帧 ----
// 一帧的视图。payload 指向输入缓冲内部，生命周期与输入缓冲一致。
struct FrameView {
    MsgId id;
    uint8_t seq;
    const uint8_t *payload;
    uint8_t payload_len;
};

// 从 buf 中定位一帧。
// USB CDC 对应用层是字节流——一次 read() 可能拿到半帧，也可能拿到三帧半，
// 所以解帧必须是「喂多少都能处理」的增量形态，不能假设一次读到一个整帧。
//   成功   -> 返回 true，view / frame_len 有效，调用方消费 frame_len 字节
//   未找到 -> 返回 false，调用方丢弃 keep_from 字节（其前都成不了帧）
// CRC 不通过的候选帧会被跳过并按字节滑动重同步——丢帧优于错帧。
inline bool decode_frame(const uint8_t *buf, size_t len, FrameView &view, size_t &frame_len,
                         size_t &keep_from) {
    size_t i = 0;
    while (i + kHeaderBytes + kTrailerBytes <= len) {
        if (buf[i] != kSof0 || buf[i + 1] != kSof1) {
            ++i;
            continue;
        }
        const uint8_t payload_len = buf[i + kLenOffset];
        if (payload_len > kMaxPayload) {
            // 不可能成帧，按垃圾滑动，不等它把缓冲撑满
            ++i;
            continue;
        }
        const size_t total = kHeaderBytes + payload_len + kTrailerBytes;
        if (i + total > len) {
            break; // 半帧：等后续数据，不得当作垃圾丢弃
        }
        // CRC 小端落在帧尾
        const uint16_t got = static_cast<uint16_t>(buf[i + total - 2]) |
                             static_cast<uint16_t>(buf[i + total - 1] << 8);
        if (crc16(buf + i + kCrcOffset, kCrcRegionBytes + payload_len) != got) {
            ++i;
            continue;
        }
        view.id = static_cast<MsgId>(buf[i + kMsgIdOffset]);
        view.seq = buf[i + kSeqOffset];
        view.payload = buf + i + kHeaderBytes;
        view.payload_len = payload_len;
        frame_len = i + total;
        keep_from = frame_len;
        return true;
    }
    keep_from = i;
    return false;
}

// ---- 强类型编解码 ----
// encode_frame 只认 void* + 长度：调用方手填长度，就能写出「ID 是 A、载荷是 B」
// 这种编译期查不出的错配，两侧在场上静默错位。下面每个消息一对包装——
// 长度由 sizeof 决定（编译期锁死），解码侧校验 LEN 与结构体一致后才解释。

}  // namespace foray::lower_link
