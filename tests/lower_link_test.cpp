// 生成物 lower_link.hpp 的契约测试。CI 构建并运行本文件（见 ci.yml 的 gen-check）。
//
// 生成式方案最大的盲区是「两侧包含同一份错误实现」：编译通过、生成物一致、两侧
// 自洽，但与标准实现对不上——直到跟 CAN 上的电调、跟裁判系统对接才暴露。所以这里
// 用**外部锚点**把结果钉死，而不是拿生成代码跟它自己比：
//
//   - CRC-16/CCITT-FALSE 的标准 check value（0x29B1）
//   - 一条完整帧的固定字节序列
//   - 组帧 / 解帧往返，以及 CRC 损坏、半帧、前导垃圾、超限 LEN 的处置

#include "lower_link.hpp"

#include <cstdint>
#include <cstdio>
#include <cstring>

using namespace foray::lower_link;

namespace {

int g_failures = 0;

void check(bool ok, const char* what) {
    if (!ok) {
        ++g_failures;
    }
    std::printf("%s  %s\n", ok ? "ok  " : "FAIL", what);
}

// CRC-16/CCITT-FALSE 的标准 check value：init 0xFFFF、poly 0x1021、不反转、不异或
void test_crc_check_value() {
    const uint8_t v[9] = {'1', '2', '3', '4', '5', '6', '7', '8', '9'};
    check(crc16(v, 9) == 0x29B1, "CRC-16/CCITT-FALSE(\"123456789\") == 0x29B1");
}

// 空载荷帧的固定字节序列。
// 帧结构或 CRC 覆盖范围一旦改动，这里立刻红灯——而不是等两侧都按新格式改了，
// 却忘了通知第三处（复用同一帧格式的 CAN / UART 链路）。
void test_golden_empty_frame() {
    uint8_t buf[kMaxFrame] = {};
    const size_t n = encode_frame(static_cast<MsgId>(0x01), nullptr, 0, 0x00, buf);
    const uint8_t expect[] = {0xA5, 0x5A, 0x00, 0x00, 0x01, 0xBD, 0xDC};
    check(n == sizeof(expect), "空载荷帧长度 == 7");
    check(std::memcmp(buf, expect, sizeof(expect)) == 0, "空载荷帧字节序列未变");
}

// 每个头部字段必须落在生成期推导出的偏移上——偏移写错是「能编译、能跑、
// 数据全错」的那类问题。
void test_encode_field_layout() {
    const uint8_t payload[4] = {0x01, 0x02, 0x03, 0x04};
    uint8_t buf[kMaxFrame] = {};
    const size_t n = encode_frame(static_cast<MsgId>(0x10), payload, 4, 0x2A, buf);

    check(n == kHeaderBytes + 4 + kTrailerBytes, "帧长 == 头 + 载荷 + 尾");
    check(buf[0] == kSof0 && buf[1] == kSof1, "SOF 落在帧首");
    check(buf[kLenOffset] == 4, "LEN 落在 kLenOffset");
    check(buf[kSeqOffset] == 0x2A, "SEQ 落在 kSeqOffset");
    check(buf[kMsgIdOffset] == 0x10, "MSG_ID 落在 kMsgIdOffset");
    check(std::memcmp(buf + kHeaderBytes, payload, 4) == 0, "载荷从 kHeaderBytes 起");

    // CRC 覆盖区间恰好止于帧尾 CRC 字段之前，且小端落在帧尾
    check(kCrcOffset + kCrcRegionBytes + 4 == n - kTrailerBytes,
          "CRC 覆盖区间止于帧尾 CRC 字段之前");
    const uint16_t got = static_cast<uint16_t>(buf[n - 2]) | static_cast<uint16_t>(buf[n - 1] << 8);
    check(got == crc16(buf + kCrcOffset, kCrcRegionBytes + 4), "CRC 小端落在帧尾");
}

void test_roundtrip() {
    const uint8_t payload[6] = {1, 2, 3, 4, 5, 6};
    uint8_t buf[kMaxFrame] = {};
    const size_t n = encode_frame(static_cast<MsgId>(0x11), payload, 6, 0x07, buf);

    FrameView view{};
    size_t frame_len = 0;
    size_t keep_from = 0;
    check(decode_frame(buf, n, view, frame_len, keep_from), "整帧解出");
    check(frame_len == n, "frame_len == 帧长");
    check(keep_from == n, "keep_from == 帧长");
    check(view.id == static_cast<MsgId>(0x11), "ID 还原");
    check(view.seq == 0x07, "SEQ 还原");
    check(view.payload_len == 6 && std::memcmp(view.payload, payload, 6) == 0, "载荷还原");
    check(view.payload == buf + kHeaderBytes, "payload 指向输入缓冲内部，不发生拷贝");
}

void test_crc_corruption_rejected() {
    uint8_t buf[kMaxFrame] = {};
    const uint8_t payload[4] = {1, 2, 3, 4};
    const size_t n = encode_frame(static_cast<MsgId>(0x12), payload, 4, 0x00, buf);
    buf[n - 1] ^= 0x01; // 破坏 CRC 高字节

    FrameView view{};
    size_t frame_len = 0;
    size_t keep_from = 0;
    check(!decode_frame(buf, n, view, frame_len, keep_from), "CRC 损坏的帧被拒绝");
}

void test_payload_corruption_rejected() {
    uint8_t buf[kMaxFrame] = {};
    const uint8_t payload[4] = {1, 2, 3, 4};
    const size_t n = encode_frame(static_cast<MsgId>(0x12), payload, 4, 0x00, buf);
    buf[kHeaderBytes] ^= 0x80; // 破坏载荷

    FrameView view{};
    size_t frame_len = 0;
    size_t keep_from = 0;
    check(!decode_frame(buf, n, view, frame_len, keep_from), "载荷损坏的帧被拒绝");
}

// 一帧坏掉不能连累后面的好帧——丢帧优于错帧，但也不能把链路卡死。
void test_resync_after_bad_frame() {
    uint8_t buf[2 * kMaxFrame] = {};
    const uint8_t p1[4] = {1, 2, 3, 4};
    const size_t n1 = encode_frame(static_cast<MsgId>(0x12), p1, 4, 0x00, buf);
    buf[n1 - 1] ^= 0x01; // 第一帧损坏

    const uint8_t p2[3] = {9, 8, 7};
    const size_t n2 = encode_frame(static_cast<MsgId>(0x13), p2, 3, 0x01, buf + n1);

    FrameView view{};
    size_t frame_len = 0;
    size_t keep_from = 0;
    check(decode_frame(buf, n1 + n2, view, frame_len, keep_from), "坏帧之后的第二帧仍被找到");
    check(view.id == static_cast<MsgId>(0x13), "第二帧 ID 正确");
    check(view.payload_len == 3 && std::memcmp(view.payload, p2, 3) == 0, "第二帧载荷正确");
}

// USB CDC 一次 read() 拿到半帧是常态：半帧必须留在缓冲里等后续数据。
void test_partial_frame_is_kept() {
    uint8_t buf[kMaxFrame] = {};
    const uint8_t payload[8] = {1, 2, 3, 4, 5, 6, 7, 8};
    const size_t n = encode_frame(static_cast<MsgId>(0x14), payload, 8, 0x00, buf);

    FrameView view{};
    size_t frame_len = 0;
    size_t keep_from = 0;
    check(!decode_frame(buf, n - 3, view, frame_len, keep_from), "半帧不返回成功");
    check(keep_from == 0, "半帧必须留在缓冲里，不得丢弃");
}

void test_leading_garbage_is_skipped() {
    uint8_t buf[64] = {};
    const uint8_t junk[3] = {0x11, 0x22, 0x33};
    std::memcpy(buf, junk, sizeof(junk));
    const uint8_t payload[2] = {0xAA, 0xBB};
    const size_t n = encode_frame(static_cast<MsgId>(0x15), payload, 2, 0x00, buf + sizeof(junk));

    FrameView view{};
    size_t frame_len = 0;
    size_t keep_from = 0;
    check(decode_frame(buf, sizeof(junk) + n, view, frame_len, keep_from), "跳过前导垃圾找到帧");
    check(frame_len == sizeof(junk) + n, "frame_len 覆盖前导垃圾与帧体");
    check(std::memcmp(view.payload, payload, 2) == 0, "载荷未受前导垃圾影响");
}

// LEN 超出 kMaxPayload 的候选帧不可能成帧：按垃圾滑动，而不是等 251 字节来凑齐。
void test_oversize_len_is_skipped() {
    uint8_t buf[16] = {};
    buf[0] = kSof0;
    buf[1] = kSof1;
    buf[2] = static_cast<uint8_t>(kMaxPayload + 1);

    FrameView view{};
    size_t frame_len = 0;
    size_t keep_from = 0;
    check(!decode_frame(buf, sizeof(buf), view, frame_len, keep_from), "LEN 超限的候选帧被跳过");
    check(keep_from > 0, "LEN 超限的候选帧被丢弃而非等待");
}

void test_encode_rejects_bad_args() {
    uint8_t buf[kMaxFrame] = {};
    const uint8_t one = 0;

    check(encode_frame(static_cast<MsgId>(0x16), nullptr, 4, 0, buf) == 0,
          "payload 为空但长度非零 -> 拒绝");
    check(encode_frame(static_cast<MsgId>(0x16), &one, 0, 0, nullptr) == 0, "out 为空 -> 拒绝");
    check(encode_frame(static_cast<MsgId>(0x16), &one, 255, 0, buf) == 0,
          "载荷超出 kMaxPayload -> 拒绝");
}

} // namespace

int main() {
    test_crc_check_value();
    test_golden_empty_frame();
    test_encode_field_layout();
    test_roundtrip();
    test_crc_corruption_rejected();
    test_payload_corruption_rejected();
    test_resync_after_bad_frame();
    test_partial_frame_is_kept();
    test_leading_garbage_is_skipped();
    test_oversize_len_is_skipped();
    test_encode_rejects_bad_args();

    if (g_failures != 0) {
        std::printf("\n%d 项失败\n", g_failures);
        return 1;
    }
    std::printf("\n全部通过\n");
    return 0;
}
