"""生成器测试（CI 的 test-python 作业运行本文件）。

`protocol/lower_link.yaml` 的 messages: 为空时，`gen_lower_link.py` 里「逐条消息」
的生成路径一次都不会执行——那是「第一条消息落地时才第一次运行」的代码。本文件用
`tests/fixtures/sample.yaml` 把它提前覆盖，并锁住几处会静默出错的结构校验。

生成物本身的行为由 `tests/lower_link_test.cpp` 针对真实 header 验证，两者互补。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

import pytest
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import gen_lower_link

FIXTURE = os.path.join(HERE, "fixtures", "sample.yaml")

# 用 fixture 定义生成的 API 跑一遍完整往返：只断言生成文本是不够的，
# 生成的东西必须真的能编译、能编解码。
DRIVER = """
#include "lower_link.hpp"

#include <cstdio>

using namespace foray::lower_link;

int main() {
    int fails = 0;

    // 长度表必须与结构体一致；未定义的消息号返回 0，调用方据此丢弃
    if (expected_payload_size(MsgId::CHASSIS_CMD) != sizeof(CHASSIS_CMD)) {
        ++fails;
    }
    if (expected_payload_size(MsgId::CHASSIS_STATE) != sizeof(CHASSIS_STATE)) {
        ++fails;
    }
    if (expected_payload_size(static_cast<MsgId>(0x7F)) != 0) {
        ++fails;
    }

    // 强类型往返：长度由 sizeof 决定，调用方不需要填
    CHASSIS_CMD cmd{};
    cmd.vx = 1.5f;
    cmd.vy = -2.5f;
    cmd.wz = 0.25f;
    uint8_t buf[kMaxFrame] = {};
    const size_t n = encode(cmd, 0x33, buf);

    FrameView view{};
    size_t frame_len = 0;
    size_t keep_from = 0;
    if (!decode_frame(buf, n, view, frame_len, keep_from) || frame_len != n) {
        ++fails;
    }
    if (view.id != MsgId::CHASSIS_CMD || view.seq != 0x33) {
        ++fails;
    }
    CHASSIS_CMD back{};
    if (!decode(view.payload, view.payload_len, back)) {
        ++fails;
    }
    if (back.vx != cmd.vx || back.vy != cmd.vy || back.wz != cmd.wz) {
        ++fails;
    }

    // 长度对不上必须拒绝——这正是强类型包装要挡住的那类错配
    if (decode(view.payload, static_cast<uint8_t>(view.payload_len - 1), back)) {
        ++fails;
    }
    if (decode(nullptr, static_cast<uint8_t>(sizeof(CHASSIS_CMD)), back)) {
        ++fails;
    }

    // 数组字段与整型字段往返
    CHASSIS_STATE st{};
    st.vx = 3.25f;
    st.flags = 0x5A;
    for (int i = 0; i < 4; ++i) {
        st.enc[i] = static_cast<int16_t>(i - 2);
    }
    const size_t n2 = encode(st, 0x34, buf);
    if (!decode_frame(buf, n2, view, frame_len, keep_from)) {
        ++fails;
    }
    CHASSIS_STATE st2{};
    if (!decode(view.payload, view.payload_len, st2)) {
        ++fails;
    }
    if (st2.vx != st.vx || st2.flags != st.flags || st2.enc[3] != st.enc[3]) {
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


def test_typed_wrappers_are_generated(hpp):
    for name in ("CHASSIS_CMD", "CHASSIS_STATE"):
        assert (
            f"inline size_t encode(const {name} &msg, uint8_t seq, uint8_t *out)" in hpp
        )
        assert (
            f"inline bool decode(const uint8_t *payload, uint8_t payload_len, {name} &msg)"
            in hpp
        )
        assert f"case MsgId::{name}:" in hpp
        assert f"return sizeof({name});" in hpp


def test_frame_constants_come_from_the_spec(hpp):
    # 帧内偏移与 CRC 范围由 frame 段推导，不是手写的字面量
    assert "constexpr size_t kLenOffset = 2;" in hpp
    assert "constexpr size_t kSeqOffset = 3;" in hpp
    assert "constexpr size_t kMsgIdOffset = 4;" in hpp
    assert "constexpr size_t kCrcOffset = 2;" in hpp
    assert "constexpr size_t kCrcRegionBytes = 3;" in hpp


def test_version_and_timeouts_are_generated(hpp):
    assert "constexpr uint16_t kProtocolVersion = 0x0104;" in hpp
    assert "constexpr uint8_t kProtocolMajor = 1;" in hpp
    assert "constexpr uint8_t kProtocolMinor = 4;" in hpp
    assert "constexpr uint32_t kTimeoutChassisCmdMs = 100;" in hpp
    assert "constexpr uint32_t kTimeoutShooterCmdMs = 200;" in hpp


def test_crc_check_value_is_pinned(hpp):
    # 生成式方案的锚点：实现对不上标准时必须在编译期就红
    assert "static_assert(crc16(kCrcCheckVector, 9) == 0x29B1," in hpp


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


# ---- 结构校验：这些错误必须在这里拦住，而不是漏进生成物 ----


def test_header_bytes_must_match_the_layout(sample):
    # header_bytes 与实际字段布局脱节时，CRC 会静默覆盖错误的字节区间
    sample["frame"]["header_bytes"] = 4
    with pytest.raises(SystemExit):
        gen_lower_link.gen_hpp(sample)


def test_crc_covers_gap_is_rejected(sample):
    sample["frame"]["crc_covers"] = ["len", "msg_id", "payload"]
    with pytest.raises(SystemExit):
        gen_lower_link.gen_hpp(sample)


def test_crc_covers_must_end_at_payload(sample):
    sample["frame"]["crc_covers"] = ["len", "seq", "msg_id"]
    with pytest.raises(SystemExit):
        gen_lower_link.gen_hpp(sample)


def test_duplicate_message_id_is_rejected(sample):
    sample["messages"][1]["id"] = sample["messages"][0]["id"]
    with pytest.raises(SystemExit):
        gen_lower_link.validate(sample)


def test_duplicate_message_name_is_rejected(sample):
    sample["messages"][1]["name"] = sample["messages"][0]["name"]
    with pytest.raises(SystemExit):
        gen_lower_link.validate(sample)


def test_message_id_must_fit_in_one_byte(sample):
    sample["messages"][0]["id"] = 0x100
    with pytest.raises(SystemExit):
        gen_lower_link.validate(sample)


def test_fieldless_message_is_rejected(sample):
    sample["messages"][0]["fields"] = []
    with pytest.raises(SystemExit):
        gen_lower_link.validate(sample)


def test_oversize_payload_is_rejected(sample):
    sample["messages"][0]["fields"] = [{"name": "big", "type": "uint8[251]"}]
    with pytest.raises(SystemExit):
        gen_lower_link.validate(sample)
