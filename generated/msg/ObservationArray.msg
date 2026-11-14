# 本文件由 scripts/gen_vision.py 自动生成，禁止手写。
# 改协议请改 protocol/vision.yaml。
# 单帧观测集合；一帧一条，保持检测输出顺序

# 图像采集时刻
builtin_interfaces/Time stamp
# 相机光学系
string frame_id
# 本帧全部观测
Observation[] observations
