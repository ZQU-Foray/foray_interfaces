// 生成物 vision.hpp 的契约测试。CI 的 gen-check 作业编译并运行本文件。
//
// 它测的是**仓库里真实那份**生成物（由 protocol/vision.yaml 生成），
// 与 tests/test_gen_vision.py 互补——后者测生成器本身。
//
// 重点锁住三件事：
//   1) 枚举与字符串一一往返，改枚举必须同步改 spec；
//   2) 固定容量上限存在且与 spec 的 caps 一致（后端硬实时不许动态分配）；
//   3) 每条消息都带 stamp 与 frame_id（的组织规范）。

#include "vision.hpp"

#include <cstdint>
#include <cstdio>
#include <string_view>

using namespace diesel_vision;

namespace {

int g_failures = 0;

void check(bool ok, const char* what) {
    if (!ok) {
        ++g_failures;
    }
    std::printf("%s  %s\n", ok ? "ok  " : "FAIL", what);
}

void test_time_layout() {
    // 与 lower_link 的 time 表示一致：int32 秒 + uint32 纳秒 = 8 字节
    check(sizeof(Time) == 8, "Time 是 8 字节");
}

void test_caps() {
    check(kVisionMaxObservations == 32, "一帧最多 32 个观测");
    check(kVisionMaxTracks == 8, "快照最多 8 条轨迹");
}

void test_enum_roundtrip() {
    for (std::size_t i = 0; i < kTargetClassCount; ++i) {
        const auto value = static_cast<TargetClass>(i);
        const std::string_view name = to_string(value);
        const auto parsed = target_class_from_string(name);
        check(parsed.has_value() && *parsed == value, "TargetClass 往返");
    }
    check(!target_class_from_string("laser").has_value(), "未知类别返回 nullopt");
    for (std::size_t i = 0; i < kObservationSourceCount; ++i) {
        const auto value = static_cast<ObservationSource>(i);
        check(observation_source_from_string(to_string(value)) == value, "ObservationSource 往返");
    }
    for (std::size_t i = 0; i < kTrackStateCount; ++i) {
        const auto value = static_cast<TrackState>(i);
        check(track_state_from_string(to_string(value)) == value, "TrackState 往返");
    }
}

void test_messages_carry_stamp_and_frame() {
    const Observation observation{};
    check(observation.stamp.sec == 0 && observation.stamp.nanosec == 0, "Observation 有 stamp");
    check(observation.frame_id.empty(), "Observation 有 frame_id");
    check(observation.armor_id == -1, "Observation.armor_id 默认 -1 表示未编号");

    const ObservationArray frame{};
    check(frame.observation_count == 0, "ObservationArray 自带计数");
    check(frame.observations.size() == kVisionMaxObservationItems, "ObservationArray 容量固定");

    const WorldSnapshot snapshot{};
    check(snapshot.tracks.size() == kVisionMaxTrackedTargetItems, "WorldSnapshot 轨迹容量固定");

    const GimbalCommand command{};
    check(!command.valid && command.target_id == -1, "GimbalCommand 默认无效且无轨迹");
}

} // namespace

int main() {
    test_time_layout();
    test_caps();
    test_enum_roundtrip();
    test_messages_carry_stamp_and_frame();
    if (g_failures == 0) {
        std::printf("\n全部通过\n");
        return 0;
    }
    std::printf("\n%d 项失败\n", g_failures);
    return 1;
}
