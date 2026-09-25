#!/usr/bin/env python3
"""从 protocol/lower_link.yaml 生成两侧共用的代码与文档。

生成物（全部禁止手写）：
    generated/lower_link.hpp     裸机 C++（POD + 常量 + 编解码）→ ControllerCode / foray_platform
    generated/msg/<Name>.msg     ROS 2 消息类型                  → foray_platform
    generated/message_table.md   消息表（防止文档与定义漂移）

用法:
    python3 scripts/gen_lower_link.py

CI 校验：重新生成后 `git diff --exit-code`，不一致即失败。
"""

from __future__ import annotations

import os
import re
import sys

try:
    import yaml
except ImportError:
    sys.exit("需要 PyYAML：pip install pyyaml")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SPEC = os.path.join(ROOT, "protocol", "lower_link.yaml")
OUT = os.path.join(ROOT, "generated")

BANNER = "本文件由 scripts/gen_lower_link.py 自动生成，禁止手写。\n改协议请改 protocol/lower_link.yaml。"

# 类型表： (C++ 类型, ROS 类型, 字节数)
TYPES = {
    "float32": ("float", "float32", 4),
    "uint8": ("uint8_t", "uint8", 1),
    "uint16": ("uint16_t", "uint16", 2),
    "uint32": ("uint32_t", "uint32", 4),
    "int16": ("int16_t", "int16", 2),
    "bool": ("bool", "bool", 1),
}

ARRAY_RE = re.compile(r"^(\w+)\[(\d+)\]$")


def parse_type(t: str):
    """-> (cpp, ros, count, bytes_each, bytes_total)"""
    m = ARRAY_RE.match(t)
    if m:
        base, n = m.group(1), int(m.group(2))
        if base not in TYPES:
            sys.exit(f"未知类型: {base}")
        cpp, ros, size = TYPES[base]
        return cpp, ros, n, size, size * n
    if t not in TYPES:
        sys.exit(f"未知类型: {t}")
    cpp, ros, size = TYPES[t]
    return cpp, ros, 1, size, size


def payload_size(msg) -> int:
    return sum(parse_type(f["type"])[4] for f in msg["fields"])


def gen_hpp(spec) -> str:
    fr = spec["frame"]
    L = []
    a = L.append

    a("// " + BANNER.replace("\n", "\n// "))
    a("#pragma once")
    a("")
    a("#include <cstddef>")
    a("#include <cstdint>")
    a("#include <cstring>")
    a("")
    a("namespace foray::lower_link {")
    a("")
    major, minor = (int(x) for x in spec["protocol"]["version"].split(".")[:2])
    a("// MAJOR 不一致时拒绝进入 RUNNING（见 protocol/lower_link.md §7）")
    a(f"constexpr uint16_t kProtocolVersion = 0x{major:02X}{minor:02X};")
    a(f"constexpr uint8_t kProtocolMajor = {major};")
    a(f"constexpr uint8_t kProtocolMinor = {minor};")
    a("")
    a("// ---- 帧格式 ----")
    a(f'constexpr uint8_t kSof0 = 0x{fr["sof"][0]:02X};')
    a(f'constexpr uint8_t kSof1 = 0x{fr["sof"][1]:02X};')
    a("// sof(2) + len(1) + seq(1) + msg_id(1)")
    a(f'constexpr size_t kHeaderBytes = {fr["header_bytes"]};')
    a(f'constexpr size_t kTrailerBytes = {fr["trailer_bytes"]}; // crc16')
    a(f'constexpr size_t kMaxPayload = {fr["max_payload"]};')
    a("constexpr size_t kMaxFrame = kHeaderBytes + kMaxPayload + kTrailerBytes;")
    a("")
    a("// ---- 消息号 ----")
    a("enum class MsgId : uint8_t {")
    for m in spec["messages"]:
        a(f'    {m["name"]} = 0x{m["id"]:02X},')
    a("};")
    a("")
    a("// ---- 超时（ms）----")
    to = spec["timing"]["timeouts_ms"]
    for k, v in to.items():
        a(
            f"constexpr uint32_t kTimeout{''.join(w.capitalize() for w in k.split('_'))}Ms = {v};"
        )
    a("")
    a("#pragma pack(push, 1)")
    a("")
    for m in spec["messages"]:
        a(f'// {m["name"]}  0x{m["id"]:02X}  {m["direction"]}  {m.get("doc", "")}')
        a(f'struct {m["name"]} {{')
        a(f'    static constexpr MsgId kId = MsgId::{m["name"]};')
        for f in m["fields"]:
            cpp, _, n, _, _ = parse_type(f["type"])
            decl = f"{cpp} {f['name']}[{n}];" if n > 1 else f"{cpp} {f['name']};"
            bits = [
                b
                for b in (f.get("note", ""), f.get("unit", ""), f.get("frame", ""))
                if b
            ]
            a(f"    {decl} // {', '.join(bits)}" if bits else f"    {decl}")
        a("};")
        a(
            f'static_assert(sizeof({m["name"]}) == {payload_size(m)}, "{m["name"]} 布局与定义不符");'
        )
        a("")
    a("#pragma pack(pop)")
    a("")
    a("// ---- CRC-16/CCITT-FALSE ----")
    a("inline uint16_t crc16(const uint8_t *data, size_t len) {")
    a("    uint16_t crc = 0xFFFF;")
    a("    for (size_t i = 0; i < len; ++i) {")
    a("        crc ^= static_cast<uint16_t>(data[i]) << 8;")
    a("        for (int b = 0; b < 8; ++b) {")
    a("            crc = (crc & 0x8000) ? static_cast<uint16_t>((crc << 1) ^ 0x1021)")
    a("                                  : static_cast<uint16_t>(crc << 1);")
    a("        }")
    a("    }")
    a("    return crc;")
    a("}")
    a("")
    a("// ---- 组帧 ----")
    a(
        "// 返回写入 out 的字节数；out 容量须 >= kHeaderBytes + payload_len + kTrailerBytes。"
    )
    a(
        "inline size_t encode_frame(MsgId id, const void *payload, uint8_t payload_len, uint8_t seq,"
    )
    a("                          uint8_t *out) {")
    a("    if (payload_len > kMaxPayload) {")
    a("        return 0;")
    a("    }")
    a("    out[0] = kSof0;")
    a("    out[1] = kSof1;")
    a("    out[2] = payload_len;")
    a("    out[3] = seq;")
    a("    out[4] = static_cast<uint8_t>(id);")
    a("    if (payload_len > 0) {")
    a("        std::memcpy(out + kHeaderBytes, payload, payload_len);")
    a("    }")
    a("    // CRC 覆盖 len..payload，不含 SOF")
    a("    const uint16_t crc = crc16(out + 2, static_cast<size_t>(payload_len) + 3);")
    a("    const size_t tail = kHeaderBytes + payload_len;")
    a("    out[tail] = static_cast<uint8_t>(crc & 0xFF);")
    a("    out[tail + 1] = static_cast<uint8_t>(crc >> 8);")
    a("    return tail + kTrailerBytes;")
    a("}")
    a("")
    a("}  // namespace foray::lower_link")
    a("")
    return "\n".join(L)


def gen_msg(msg) -> str:
    L = [f"# {BANNER}", ""]
    for f in msg["fields"]:
        _, ros, n, _, _ = parse_type(f["type"])
        typ = f"{ros}[{n}]" if n > 1 else ros
        L.append(f"{typ} {f['name']}")
    L.append("")
    return "\n".join(L)


def gen_table(spec) -> str:
    L = [
        "<!-- " + BANNER.replace("\n", " ") + " -->",
        "",
        "# 消息表（自动生成）",
        "",
        f'协议版本 `{spec["protocol"]["version"]}` · 状态 `{spec["protocol"]["status"]}`',
        "",
        "| ID | 名称 | 方向 | 周期 | 载荷 | 状态 |",
        "|---|---|---|---|---|---|",
    ]
    for m in spec["messages"]:
        hz = f'{m["period_hz"]} Hz' if m.get("period_hz") else "事件"
        L.append(
            f'| `0x{m["id"]:02X}` | `{m["name"]}` | {m["direction"]} | {hz} '
            f'| {payload_size(m)} B | {m.get("status", "-")} |'
        )
    L.append("")
    L.append("## 字段明细")
    L.append("")
    for m in spec["messages"]:
        L.append(f'### `{m["name"]}` (0x{m["id"]:02X})')
        L.append("")
        if m.get("doc"):
            L.append(m["doc"])
            L.append("")
        L.append("| 字段 | 类型 | 单位 | 说明 |")
        L.append("|---|---|---|---|")
        for f in m["fields"]:
            cpp, _, n, _, _ = parse_type(f["type"])
            typ = f"{cpp}[{n}]" if n > 1 else cpp
            L.append(
                f'| `{f["name"]}` | `{typ}` | {f.get("unit", "-")} | {f.get("note", "")} |'
            )
        L.append("")
    L.append("## 分段")
    L.append("")
    L.append("| 段 | 用途 |")
    L.append("|---|---|")
    for r in spec["id_ranges"]:
        L.append(f'| `{r["range"]}` | {r["purpose"]} |')
    L.append("")
    return "\n".join(L)


def main() -> None:
    with open(SPEC, encoding="utf-8") as fh:
        spec = yaml.safe_load(fh)

    os.makedirs(os.path.join(OUT, "msg"), exist_ok=True)

    written = []

    p = os.path.join(OUT, "lower_link.hpp")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(gen_hpp(spec))
    written.append(p)

    for m in spec["messages"]:
        p = os.path.join(OUT, "msg", f'{m["name"]}.msg')
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(gen_msg(m))
        written.append(p)

    p = os.path.join(OUT, "message_table.md")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(gen_table(spec))
    written.append(p)

    for p in written:
        print(f"  生成 {os.path.relpath(p, ROOT)}")
    print(f"\n共 {len(written)} 个文件，源自 protocol/lower_link.yaml")


if __name__ == "__main__":
    main()
