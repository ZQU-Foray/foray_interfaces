// 生成物 lower_link.hpp 的契约测试。CI 的 gen-check 作业编译并运行本文件。
//
// 它测的是**仓库里真实那份**生成物（由 protocol/lower_link.yaml 生成），与
// tests/test_gen.py 互补——后者测生成器，用 fixture 造出消息来跑往返。
//
// ⚠️ 当前 protocol/lower_link.yaml 的 messages: 为空，所以下面能测的只有结构性
// 约束。消息表填上之后，这里应当补上每条消息的布局与往返断言——那时本文件才
// 真正开始干活。

#include "lower_link.hpp"

#include <cstdint>
#include <cstdio>

using namespace foray::lower_link;

namespace {

int g_failures = 0;

void check(bool ok, const char* what) {
    if (!ok) {
        ++g_failures;
    }
    std::printf("%s  %s\n", ok ? "ok  " : "FAIL", what);
}

// 载荷上限是内容层的自我约束，写在 protocol/lower_link.yaml 的 max_payload。
// 改动它必须连同生成物一起提交，否则这条会红。
void test_max_payload() {
    check(kMaxPayload == 250, "kMaxPayload 与 lower_link.yaml 的 max_payload 一致");
}

// 消息表填上后，未定义的消息号仍必须返回 0——链路层据此丢弃，
// 而不是按猜测解释。
void test_unknown_ids_have_no_length() {
    bool all_zero = true;
    for (int id = 0; id < 256; ++id) {
        if (expected_payload_size(static_cast<MsgId>(id)) != 0) {
            all_zero = false;
        }
    }
    check(all_zero, "当前消息表为空，任何 ID 的长度都是 0");
}

// 无论消息表怎么填，任何一条消息的载荷都不得超过 kMaxPayload——
// 否则链路层按 expected_payload_size 分配的缓冲会被写穿。
void test_no_message_exceeds_max_payload() {
    bool within = true;
    for (int id = 0; id < 256; ++id) {
        if (expected_payload_size(static_cast<MsgId>(id)) > kMaxPayload) {
            within = false;
        }
    }
    check(within, "没有任何消息的载荷超出 kMaxPayload");
}

} // namespace

int main() {
    test_max_payload();
    test_unknown_ids_have_no_length();
    test_no_message_exceeds_max_payload();

    if (g_failures != 0) {
        std::printf("\n%d 项失败\n", g_failures);
        return 1;
    }
    std::printf("\n全部通过\n");
    return 0;
}
