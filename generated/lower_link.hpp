// 本文件由 scripts/gen_lower_link.py 自动生成，禁止手写。
// 改协议请改 protocol/lower_link.yaml。
#pragma once

#include <cstddef>
#include <cstdint>
#include <cstring>

namespace foray::lower_link {

// 内容层的 schema 版本——两侧不一致说明字段布局已经不同。
// 至于不一致时怎么办（拒绝 / 降级），属链路层，不在本文件表态。
constexpr uint16_t kProtocolVersion = 0x0001;
constexpr uint8_t kProtocolMajor = 0;
constexpr uint8_t kProtocolMinor = 1;

constexpr size_t kMaxPayload = 250;

// ---- 消息号 ----
enum class MsgId : uint8_t {
};

#pragma pack(push, 1)

#pragma pack(pop)

// ---- 消息载荷长度 ----
// 消息号 -> 载荷字节数。链路层据此知道每帧该带多少字节。
// 未定义的消息号返回 0——必须丢弃，不能按猜测解释。
// 消息表为空：暂无已知消息号，一切 ID 都返回 0。
constexpr size_t expected_payload_size(MsgId) { return 0; }

// ---- 载荷编解码 ----
// 结构体是 packed 的，编码本身就是一次 memcpy——用函数包起来是为了把长度
// 锁成 sizeof：调用方手填长度就能写出「ID 是 A、载荷是 B」这种编译期查不出的
// 错配，两侧会在场上静默错位。
}  // namespace foray::lower_link
