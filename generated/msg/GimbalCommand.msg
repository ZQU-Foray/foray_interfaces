# 本文件由 scripts/gen_vision.py 自动生成，禁止手写。
# 改协议请改 protocol/vision.yaml。
# 云台角指令（后端 → 链路）；yaw 左正、pitch 下正，全队统一

# 指令生成时刻
builtin_interfaces/Time stamp
# 指令坐标系（通常为 gimbal）
string frame_id
# 目标 yaw，向左为正
float32 yaw
# 目标 pitch，向下为正
float32 pitch
# 目标距离，用于弹道解算与开火门限
float32 distance_m
# 目标轨迹号；-1 表示直瞄无轨迹
int16 target_id
# 指令是否有效；false 时上层必须保持当前姿态
bool valid
