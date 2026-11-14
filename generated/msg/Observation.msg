# 本文件由 scripts/gen_vision.py 自动生成，禁止手写。
# 改协议请改 protocol/vision.yaml。
# 单个目标的单帧观测（前端 → 后端）

# 图像采集时刻，绝对时间
builtin_interfaces/Time stamp
# 相机光学系（REP-105 约定，如 camera_optical_frame）
string frame_id
# 目标类别
TargetClass target_class
# 观测来源
ObservationSource source
# 装甲板编号 0-2；-1 表示未编号
int8 armor_id
# 像素四角 u0,v0..u3,v3，顺序为左上/右上/右下/左下
float32[8] corners
# 目标位置（相机光学系）；未解算时为 0
float32[3] xyz_camera
# 装甲板法向（相机光学系，单位向量）
float32[3] normal_camera
# 法向是否可信；PnP 镜像解或未标定时为 false
bool normal_valid
# 目标自转角；未知时为 0 且由 normal_valid 判定
float32 yaw
# 检测置信度 0-1
float32 confidence
# PnP 重投影误差；未解算时为 0
float32 reprojection_error
