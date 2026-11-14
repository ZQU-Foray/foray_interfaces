"""视觉契约生成器测试（CI 的 test-python 作业运行本文件）。

tests/vision_test.cpp 验证的是**仓库里真实那份**生成物；本文件验证生成器本身：
spec 校验规则、生成物形状，以及「改 spec 必须重新生成」这条纪律。

这里不依赖 fixture 文件——视觉 spec 已经有 5 条真实消息，逐条生成路径天然被覆盖。
"""

from __future__ import annotations

import copy
import os
import sys

import pytest
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import gen_vision


def base_spec():
    with open(gen_vision.SPEC, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def write_and_load(tmp_path, spec):
    path = tmp_path / "vision.yaml"
    with open(path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(spec, handle, allow_unicode=True)
    return gen_vision.load_spec(str(path))


def test_real_spec_is_valid():
    spec = gen_vision.load_spec()
    names = [message["name"] for message in spec["messages"]]
    assert names == [
        "Observation",
        "ObservationArray",
        "TrackedTarget",
        "WorldSnapshot",
        "GimbalCommand",
    ]


def test_every_top_level_message_carries_stamp_and_frame_id():
    # 组织规范：所有消息必须带 stamp 与 frame_id。TrackedTarget 是嵌在
    # WorldSnapshot 里的子结构，不算独立消息，因此不要求自带。
    spec = gen_vision.load_spec()
    nested = {
        field["type"].split("[")[0]
        for message in spec["messages"]
        for field in message["fields"]
        if "[" in field["type"]
    }
    for message in spec["messages"]:
        if message["name"] in nested:
            continue
        fields = {field["name"]: field["type"] for field in message["fields"]}
        assert fields.get("stamp") == "time", message["name"]
        assert fields.get("frame_id") == "string", message["name"]


def test_generated_header_has_fixed_caps_and_no_duplicate_symbols():
    header = gen_vision.cpp_header(gen_vision.load_spec())
    defines = [
        line.split("=")[0].strip()
        for line in header.splitlines()
        if line.startswith("inline constexpr std::size_t")
    ]
    assert len(defines) == len(set(defines)), f"常量名重复: {defines}"
    assert "kVisionMaxObservationItems = 32;" in header
    assert "kVisionMaxTrackedTargetItems = 8;" in header


def test_defaults_are_rendered_into_the_struct():
    header = gen_vision.cpp_header(gen_vision.load_spec())
    # armor_id / target_id 用 -1 表示「未编号/无轨迹」，不能默默当 0 用
    assert "std::int8_t armor_id{-1};" in header
    assert "std::int16_t target_id{-1};" in header


def test_duplicate_message_name_is_rejected(tmp_path):
    spec = base_spec()
    spec["messages"].append(copy.deepcopy(spec["messages"][0]))
    with pytest.raises(ValueError, match="重复"):
        write_and_load(tmp_path, spec)


def test_unknown_type_is_rejected(tmp_path):
    spec = base_spec()
    spec["messages"][0]["fields"][0]["type"] = "float64"
    with pytest.raises(ValueError, match="未知类型"):
        write_and_load(tmp_path, spec)


def test_unquoted_comma_doc_is_rejected_instead_of_silently_truncated(tmp_path):
    # 这条规则来自一次真实事故：doc 里没加引号的逗号把字段拆成了多余键
    spec = base_spec()
    spec["messages"][0]["fields"][0]["oops"] = "truncated"
    with pytest.raises(ValueError, match="未知键"):
        write_and_load(tmp_path, spec)


def test_nested_message_without_cap_is_rejected(tmp_path):
    spec = base_spec()
    frame = spec["messages"][1]
    for field in frame["fields"]:
        field.pop("cap", None)
    with pytest.raises(ValueError, match="必须给 cap"):
        write_and_load(tmp_path, spec)


def test_msg_output_uses_ros_types():
    spec = gen_vision.load_spec()
    observation = gen_vision.ros_message(spec, spec["messages"][0])
    assert "builtin_interfaces/Time stamp" in observation
    assert "string frame_id" in observation
    assert "float32[8] corners" in observation
    frame = gen_vision.ros_message(spec, spec["messages"][1])
    assert "Observation[] observations" in frame


def test_table_lists_every_field():
    spec = gen_vision.load_spec()
    text = gen_vision.table(spec)
    for message in spec["messages"]:
        for field in message["fields"]:
            assert f"`{message['name']}` | `{field['name']}`" in text
