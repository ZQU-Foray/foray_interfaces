// 本文件由 scripts/gen_vision.py 自动生成，禁止手写。
// 改协议请改 protocol/vision.yaml。
// 协议 vision 0.1.0（draft）
#ifndef DIESEL_VISION_GENERATED_VISION_HPP
#define DIESEL_VISION_GENERATED_VISION_HPP

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>

namespace diesel_vision {

inline constexpr char kVisionProtocolVersion[] = "0.1.0";
inline constexpr std::size_t kVisionMaxObservations = 32;
inline constexpr std::size_t kVisionMaxTracks = 8;
inline constexpr std::size_t kVisionMaxObservationItems = 32;
inline constexpr std::size_t kVisionMaxObservationArrayItems = 1;
inline constexpr std::size_t kVisionMaxTrackedTargetItems = 8;
inline constexpr std::size_t kVisionMaxWorldSnapshotItems = 1;
inline constexpr std::size_t kVisionMaxGimbalCommandItems = 1;

/// 绝对时间（Unix 纪元），与 lower_link 的 time 表示一致。
struct Time {
  std::int32_t sec{0};
  std::uint32_t nanosec{0};
};

/// 目标类别；前端按类别装配检测器，后端按类别选解算策略
enum class TargetClass : std::uint8_t {
  Armor = 0,  ///< 装甲板
  EnergyMechanism = 1,  ///< 能量机关
  Outpost = 2,  ///< 前哨站
  Base = 3,  ///< 基地
  Unknown = 4,  ///< 未识别
};

inline constexpr std::size_t kTargetClassCount = 5;
inline constexpr std::string_view kTargetClassNames[] = {
    "Armor",
    "EnergyMechanism",
    "Outpost",
    "Base",
    "Unknown",
};

inline std::string_view to_string(TargetClass value) {
  return kTargetClassNames[static_cast<std::size_t>(value) % kTargetClassCount];
}

inline std::optional<TargetClass> target_class_from_string(
    std::string_view text) {
  for (std::size_t i = 0; i < kTargetClassCount; ++i) {
    if (kTargetClassNames[i] == text) {
      return static_cast<TargetClass>(i);
    }
  }
  return std::nullopt;
}

/// 观测来源；用于后端融合时区分自车与他车
enum class ObservationSource : std::uint8_t {
  OwnCamera = 0,  ///< 自车相机
  AllyShared = 1,  ///< 友军共享
};

inline constexpr std::size_t kObservationSourceCount = 2;
inline constexpr std::string_view kObservationSourceNames[] = {
    "OwnCamera",
    "AllyShared",
};

inline std::string_view to_string(ObservationSource value) {
  return kObservationSourceNames[static_cast<std::size_t>(value) % kObservationSourceCount];
}

inline std::optional<ObservationSource> observation_source_from_string(
    std::string_view text) {
  for (std::size_t i = 0; i < kObservationSourceCount; ++i) {
    if (kObservationSourceNames[i] == text) {
      return static_cast<ObservationSource>(i);
    }
  }
  return std::nullopt;
}

/// 轨迹状态机
enum class TrackState : std::uint8_t {
  Lost = 0,
  Detecting = 1,
  Tracking = 2,
  TempLost = 3,
};

inline constexpr std::size_t kTrackStateCount = 4;
inline constexpr std::string_view kTrackStateNames[] = {
    "Lost",
    "Detecting",
    "Tracking",
    "TempLost",
};

inline std::string_view to_string(TrackState value) {
  return kTrackStateNames[static_cast<std::size_t>(value) % kTrackStateCount];
}

inline std::optional<TrackState> track_state_from_string(
    std::string_view text) {
  for (std::size_t i = 0; i < kTrackStateCount; ++i) {
    if (kTrackStateNames[i] == text) {
      return static_cast<TrackState>(i);
    }
  }
  return std::nullopt;
}

/// 单个目标的单帧观测（前端 → 后端）
struct Observation {
  /// 图像采集时刻，绝对时间
  Time stamp;
  /// 相机光学系（REP-105 约定，如 camera_optical_frame）
  std::string frame_id;
  /// 目标类别
  TargetClass target_class;
  /// 观测来源
  ObservationSource source;
  /// 装甲板编号 0-2；-1 表示未编号
  std::int8_t armor_id{-1};
  /// 像素四角 u0,v0..u3,v3，顺序为左上/右上/右下/左下
  std::array<float, 8> corners;
  /// 目标位置（相机光学系）；未解算时为 0
  std::array<float, 3> xyz_camera;
  /// 装甲板法向（相机光学系，单位向量）
  std::array<float, 3> normal_camera;
  /// 法向是否可信；PnP 镜像解或未标定时为 false
  bool normal_valid;
  /// 目标自转角；未知时为 0 且由 normal_valid 判定
  float yaw;
  /// 检测置信度 0-1
  float confidence;
  /// PnP 重投影误差；未解算时为 0
  float reprojection_error;
};

/// 单帧观测集合；一帧一条，保持检测输出顺序
struct ObservationArray {
  /// 图像采集时刻
  Time stamp;
  /// 相机光学系
  std::string frame_id;
  /// 本帧全部观测
  std::array<Observation, kVisionMaxObservationItems> observations;
  std::uint8_t observation_count{0};
};

/// 后端维护的单条目标轨迹
struct TrackedTarget {
  /// 轨号，仓内唯一且单调递增
  std::uint8_t id;
  /// 目标类别
  TargetClass target_class;
  /// 世界系位置（REP-105）
  std::array<float, 3> xyz_world;
  /// 世界系速度
  std::array<float, 3> velocity_world;
  /// 当前瞄准的装甲板编号；-1 表示未选板
  std::int8_t armor_id{-1};
  /// 轨迹置信度 0-1
  float confidence;
  /// 轨迹自建立以来的时长
  float age_s;
  /// 连续未命中帧数
  std::uint16_t missed_frames;
  /// 轨迹状态
  TrackState state;
};

/// 后端输出的世界模型快照；决策层与自瞄共用同一份
struct WorldSnapshot {
  /// 快照生成时刻
  Time stamp;
  /// 世界系（REP-105，通常为 map）
  std::string frame_id;
  /// 当前全部轨迹
  std::array<TrackedTarget, kVisionMaxTrackedTargetItems> tracks;
  std::uint8_t track_count{0};
};

/// 云台角指令（后端 → 链路）；yaw 左正、pitch 下正，全队统一
struct GimbalCommand {
  /// 指令生成时刻
  Time stamp;
  /// 指令坐标系（通常为 gimbal）
  std::string frame_id;
  /// 目标 yaw，向左为正
  float yaw;
  /// 目标 pitch，向下为正
  float pitch;
  /// 目标距离，用于弹道解算与开火门限
  float distance_m;
  /// 目标轨迹号；-1 表示直瞄无轨迹
  std::int16_t target_id{-1};
  /// 指令是否有效；false 时上层必须保持当前姿态
  bool valid;
};

}  // namespace diesel_vision

#endif  // DIESEL_VISION_GENERATED_VISION_HPP
