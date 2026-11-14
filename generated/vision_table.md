<!-- 本文件由 scripts/gen_vision.py 自动生成，禁止手写。 -->
<!-- 改协议请改 protocol/vision.yaml。 -->

# 视觉契约字段表（自动生成）

协议版本 `0.1.0` · 状态 `draft`

| 消息 | 字段 | 类型 | 单位 | 语义 |
|---|---|---|---|---|
| `Observation` | `stamp` | `time` | — | 图像采集时刻，绝对时间 |
| `Observation` | `frame_id` | `string` | — | 相机光学系（REP-105 约定，如 camera_optical_frame） |
| `Observation` | `target_class` | `TargetClass` | — | 目标类别 |
| `Observation` | `source` | `ObservationSource` | — | 观测来源 |
| `Observation` | `armor_id` | `int8` | — | 装甲板编号 0-2；-1 表示未编号 |
| `Observation` | `corners` | `float32[8]` | — | 像素四角 u0,v0..u3,v3，顺序为左上/右上/右下/左下 |
| `Observation` | `xyz_camera` | `float32[3]` | m | 目标位置（相机光学系）；未解算时为 0 |
| `Observation` | `normal_camera` | `float32[3]` | 1 | 装甲板法向（相机光学系，单位向量） |
| `Observation` | `normal_valid` | `bool` | — | 法向是否可信；PnP 镜像解或未标定时为 false |
| `Observation` | `yaw` | `float32` | rad | 目标自转角；未知时为 0 且由 normal_valid 判定 |
| `Observation` | `confidence` | `float32` | 1 | 检测置信度 0-1 |
| `Observation` | `reprojection_error` | `float32` | px | PnP 重投影误差；未解算时为 0 |
| `ObservationArray` | `stamp` | `time` | — | 图像采集时刻 |
| `ObservationArray` | `frame_id` | `string` | — | 相机光学系 |
| `ObservationArray` | `observations` | `Observation[]` | — | 本帧全部观测 |
| `TrackedTarget` | `id` | `uint8` | — | 轨号，仓内唯一且单调递增 |
| `TrackedTarget` | `target_class` | `TargetClass` | — | 目标类别 |
| `TrackedTarget` | `xyz_world` | `float32[3]` | m | 世界系位置（REP-105） |
| `TrackedTarget` | `velocity_world` | `float32[3]` | m/s | 世界系速度 |
| `TrackedTarget` | `armor_id` | `int8` | — | 当前瞄准的装甲板编号；-1 表示未选板 |
| `TrackedTarget` | `confidence` | `float32` | 1 | 轨迹置信度 0-1 |
| `TrackedTarget` | `age_s` | `float32` | s | 轨迹自建立以来的时长 |
| `TrackedTarget` | `missed_frames` | `uint16` | — | 连续未命中帧数 |
| `TrackedTarget` | `state` | `TrackState` | — | 轨迹状态 |
| `WorldSnapshot` | `stamp` | `time` | — | 快照生成时刻 |
| `WorldSnapshot` | `frame_id` | `string` | — | 世界系（REP-105，通常为 map） |
| `WorldSnapshot` | `tracks` | `TrackedTarget[]` | — | 当前全部轨迹 |
| `GimbalCommand` | `stamp` | `time` | — | 指令生成时刻 |
| `GimbalCommand` | `frame_id` | `string` | — | 指令坐标系（通常为 gimbal） |
| `GimbalCommand` | `yaw` | `float32` | rad | 目标 yaw，向左为正 |
| `GimbalCommand` | `pitch` | `float32` | rad | 目标 pitch，向下为正 |
| `GimbalCommand` | `distance_m` | `float32` | m | 目标距离，用于弹道解算与开火门限 |
| `GimbalCommand` | `target_id` | `int16` | — | 目标轨迹号；-1 表示直瞄无轨迹 |
| `GimbalCommand` | `valid` | `bool` | — | 指令是否有效；false 时上层必须保持当前姿态 |
