"""生成器测试（CI 的 test-python 作业运行本文件）。

`protocol/lower_link.yaml` 的 messages: 为空时，生成器里「逐条消息」的生成路径一次
都不会执行——那是「第一条消息落地时才第一次运行」的代码。本文件用
`tests/fixtures/sample.yaml` 把它提前覆盖，并锁住每一条生成期校验规则。

生成物本身在 CI 里由 `tests/lower_link_test.cpp` 单独验证（gen-check 作业编译并运行），
它测的是**真实那份**生成物；本文件测的是生成器。
"""

from __future__ import annotations

import copy
import os
import shutil
import subprocess
import sys

import pytest
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import gen_lower_link  # 需先把 scripts/ 放进 sys.path

FIXTURE = os.path.join(HERE, "fixtures", "sample.yaml")

# 用 fixture 定义生成的 API 跑一遍完整往返：只断言生成文本是不够的，
# 生成的东西必须真的能编译、能编解码。
DRIVER = """
#include "lower_link.hpp"

#include <cstdio>

using namespace foray::lower_link;

int main() {
    int fails = 0;

    // 布局：stamp(8) + 3×float(12) = 20；stamp(8) + float(4) + uint8(1) + int16[4](8) = 21
    if (sizeof(Time) != 8) {
        ++fails;
    }
    if (sizeof(CHASSIS_CMD) != 20 || sizeof(CHASSIS_STATE) != 21) {
        ++fails;
    }
    if (kProtocolVersion != 0x0104 || kProtocolMajor != 1 || kProtocolMinor != 4) {
        ++fails;
    }

    // 长度表：链路层靠它知道每帧该带多少字节
    if (expected_payload_size(MsgId::CHASSIS_CMD) != 20) {
        ++fails;
    }
    if (expected_payload_size(MsgId::CHASSIS_STATE) != 21) {
        ++fails;
    }
    if (expected_payload_size(static_cast<MsgId>(0x7F)) != 0) {
        ++fails;
    }

    // 编解码往返——长度由 sizeof 决定，调用方不填
    CHASSIS_CMD cmd{};
    cmd.stamp.sec = 1774000000;
    cmd.stamp.nanosec = 123456789;
    cmd.vx = 1.5f;
    cmd.vy = -2.5f;
    cmd.wz = 0.25f;

    uint8_t buf[kMaxPayload] = {};
    const size_t n = encode(cmd, buf);
    // 绝对时间戳的小端前 4 字节：0x69BD1780 → 80 17 BD 69
    if (n != sizeof(CHASSIS_CMD) || buf[0] != 0x80 || buf[1] != 0x17 || buf[2] != 0xBD ||
        buf[3] != 0x69) {
        ++fails;
    }

    CHASSIS_CMD back{};
    if (!decode(buf, static_cast<uint8_t>(n), back)) {
        ++fails;
    }
    if (back.stamp.sec != cmd.stamp.sec || back.stamp.nanosec != cmd.stamp.nanosec) {
        ++fails;
    }
    if (back.vx != cmd.vx || back.vy != cmd.vy || back.wz != cmd.wz) {
        ++fails;
    }

    // 数组字段与有符号时间戳
    CHASSIS_STATE st{};
    st.stamp.sec = -1;
    st.flags = 0x5A;
    for (int i = 0; i < 4; ++i) {
        st.enc[i] = static_cast<int16_t>(i - 2);
    }
    const size_t n2 = encode(st, buf);
    CHASSIS_STATE st2{};
    if (!decode(buf, static_cast<uint8_t>(n2), st2)) {
        ++fails;
    }
    if (st2.stamp.sec != -1 || st2.flags != st.flags || st2.enc[3] != st.enc[3]) {
        ++fails;
    }

    // 长度对不上、空指针必须拒绝
    if (decode(buf, static_cast<uint8_t>(n2 - 1), st2)) {
        ++fails;
    }
    if (decode(nullptr, static_cast<uint8_t>(sizeof(CHASSIS_CMD)), back)) {
        ++fails;
    }

    std::printf("generated api: %s\\n", fails == 0 ? "ok" : "FAILED");
    return fails == 0 ? 0 : 1;
}
"""


@pytest.fixture()
def sample():
    with open(FIXTURE, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@pytest.fixture()
def hpp(sample):
    gen_lower_link.validate(sample)
    return gen_lower_link.gen_hpp(sample)


def test_fixture_is_valid(sample):
    """fixture 自身必须能过校验——否则下面的断言测的是坏输入。"""
    gen_lower_link.validate(sample)
    assert len(sample["messages"]) == 2


# ---- 生成的内容 ----


def test_typed_wrappers_are_generated(hpp):
    for name in ("CHASSIS_CMD", "CHASSIS_STATE"):
        assert f"inline size_t encode(const {name} &msg, uint8_t *out)" in hpp
        assert f"case MsgId::{name}:" in hpp
        assert f"return sizeof({name});" in hpp


def test_encode_carries_no_frame_concepts(hpp):
    """生成物里不该有任何帧格式的东西——帧归链路实现。"""
    for banned in (
        "SOF",
        "kSof",
        "crc",
        "CRC",
        "encode_frame",
        "decode_frame",
        "FrameView",
    ):
        assert banned not in hpp, f"生成物里出现了帧概念：{banned}"


def test_time_is_a_struct_not_a_scalar(hpp):
    assert "struct Time {" in hpp
    assert "int32_t sec;" in hpp
    assert "uint32_t nanosec;" in hpp
    assert "static_assert(sizeof(Time) == 8" in hpp


def test_version_comes_from_the_spec(hpp):
    assert "constexpr uint16_t kProtocolVersion = 0x0104;" in hpp
    assert "constexpr uint8_t kProtocolMajor = 1;" in hpp
    assert "constexpr uint8_t kProtocolMinor = 4;" in hpp


def test_max_payload_is_emitted(hpp):
    assert "constexpr size_t kMaxPayload = 250;" in hpp


def test_time_struct_is_omitted_when_unused(sample):
    """没有消息用到 time 时不该发射 struct Time——不留死代码。

    这里直接调 gen_hpp、不过 validate：后者要求 stamp 必须是 time，而本测试
    恰恰要构造「没有任何消息用 time」的定义。
    """
    for m in sample["messages"]:
        for f in m["fields"]:
            if f["type"] == "time":
                f.update(name="tick", type="uint32")
    assert "struct Time {" not in gen_lower_link.gen_hpp(sample)


# ---- 端到端：编译并运行 ----


def test_generated_api_roundtrips(tmp_path, hpp):
    gpp = shutil.which("g++")
    if gpp is None:
        pytest.skip("环境无 g++，跳过编译验证")

    (tmp_path / "lower_link.hpp").write_text(hpp, encoding="utf-8")
    (tmp_path / "driver.cpp").write_text(DRIVER, encoding="utf-8")

    build = subprocess.run(
        [
            gpp,
            "-std=c++17",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-I",
            str(tmp_path),
            str(tmp_path / "driver.cpp"),
            "-o",
            str(tmp_path / "driver"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert build.returncode == 0, f"生成物编译失败：\n{build.stderr}"

    run = subprocess.run(
        [str(tmp_path / "driver")], capture_output=True, text=True, check=False
    )
    assert run.returncode == 0, f"往返测试失败：\n{run.stdout}\n{run.stderr}"


def test_empty_message_table_still_compiles(tmp_path):
    """消息表为空是当前的真实状态——生成物必须照样编译通过。"""
    gpp = shutil.which("g++")
    if gpp is None:
        pytest.skip("环境无 g++，跳过编译验证")

    spec = {
        "protocol": {"version": "0.1.0", "status": "draft"},
        "max_payload": 250,
        "messages": [],
    }
    gen_lower_link.validate(spec)
    (tmp_path / "lower_link.hpp").write_text(
        gen_lower_link.gen_hpp(spec), encoding="utf-8"
    )
    (tmp_path / "smoke.cpp").write_text(
        '#include "lower_link.hpp"\nint main() { return 0; }\n', encoding="utf-8"
    )

    build = subprocess.run(
        [
            gpp,
            "-std=c++17",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-I",
            str(tmp_path),
            str(tmp_path / "smoke.cpp"),
            "-o",
            str(tmp_path / "smoke"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert build.returncode == 0, f"空消息表下编译失败：\n{build.stderr}"


# ---- 生成期校验：这些错误必须在这里拦住，而不是漏进生成物 ----


def _rejects(mutate, sample):
    spec = copy.deepcopy(sample)
    mutate(spec)
    with pytest.raises(SystemExit):
        gen_lower_link.validate(spec)


def test_missing_stamp_is_rejected(sample):
    _rejects(lambda s: s["messages"][0]["fields"].pop(0), sample)


def test_stamp_of_wrong_type_is_rejected(sample):
    _rejects(lambda s: s["messages"][0]["fields"][0].update(type="uint32"), sample)


def test_duplicate_field_name_is_rejected(sample):
    _rejects(lambda s: s["messages"][0]["fields"][1].update(name="stamp"), sample)


def test_duplicate_message_id_is_rejected(sample):
    _rejects(lambda s: s["messages"][1].update(id=0x01), sample)


def test_duplicate_message_name_is_rejected(sample):
    _rejects(lambda s: s["messages"][1].update(name="CHASSIS_CMD"), sample)


def test_message_id_must_fit_in_one_byte(sample):
    _rejects(lambda s: s["messages"][0].update(id=0x100), sample)


def test_fieldless_message_is_rejected(sample):
    _rejects(lambda s: s["messages"][0].update(fields=[]), sample)


def test_oversize_payload_is_rejected(sample):
    _rejects(
        lambda s: s["messages"][0]["fields"].append(
            {"name": "big", "type": "uint8[250]"}
        ),
        sample,
    )


def test_unknown_type_is_rejected(sample):
    _rejects(
        lambda s: s["messages"][0]["fields"].append({"name": "x", "type": "float64"}),
        sample,
    )
