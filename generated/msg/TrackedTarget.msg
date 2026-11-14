# 本文件由 scripts/gen_vision.py 自动生成，禁止手写。
# 改协议请改 protocol/vision.yaml。
# 后端维护的单条目标轨迹

# 轨号，仓内唯一且单调递增
uint8 id
# 目标类别
TargetClass target_class
# 世界系位置（REP-105）
float32[3] xyz_world
# 世界系速度
float32[3] velocity_world
# 当前瞄准的装甲板编号；-1 表示未选板
int8 armor_id
# 轨迹置信度 0-1
float32 confidence
# 轨迹自建立以来的时长
float32 age_s
# 连续未命中帧数
uint16 missed_frames
# 轨迹状态
TrackState state
