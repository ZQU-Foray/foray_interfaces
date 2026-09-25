#!/usr/bin/env python3
"""从 protocol/lower_link.yaml 生成两侧共用的**内容层**代码与文档。

只生成包的内容——消息号、POD 结构体、载荷编解码。**帧格式（怎么发送与接收）
不在此生成**，它归链路实现；本文件里不含任何 SOF / LEN / SEQ / CRC。

生成物（全部禁止手写）：
    generated/lower_link.hpp     裸机 C++（POD + 常量 + 载荷编解码）
    generated/msg/<Name>.msg     ROS 2 消息类型
    generated/message_table.md   消息表（防止文档与定义漂移）

用法:
    python3 scripts/gen_lower_link.py

CI 校验：重新生成后 `git diff --exit-code`，不一致即失败。
"""

from __future__ import annotations

import glob
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
# time 不是标量：C++ 侧对应下面 hpp 里的 struct Time，ROS 侧是 builtin_interfaces/Time。
TYPES = {
    "float32": ("float", "float32", 4),
    "uint8": ("uint8_t", "uint8", 1),
    "uint16": ("uint16_t", "uint16", 2),
    "uint32": ("uint32_t", "uint32", 4),
    "int16": ("int16_t", "int16", 2),
    "bool": ("bool", "bool", 1),
    "time": ("Time", "builtin_interfaces/Time", 8),
}

# 时间戳字段名与类型。每条消息必须带它——两侧时钟域不同，没有绝对时间就无从
# 判断「这条数据多旧」。见 protocol/lower_link.md。
STAMP = "stamp"
STAMP_TYPE = "time"

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


def uses_time(msgs) -> bool:
    return any(parse_type(f["type"])[0] == "Time" for m in msgs for f in m["fields"])


def validate(spec) -> None:
    """生成前的结构校验。

    这些问题漏到生成物里会变成难懂的编译错误（重复的 case 标签、重名的成员），
    或者更糟——编译通过但语义错的代码。在这里拦住，报错才指向 YAML 的那一行。
    """
    max_payload = int(spec["max_payload"])
    seen_ids = {}
    seen_names = set()
    for m in spec["messages"]:
        name = m["name"]
        if name in seen_names:
            sys.exit(f"消息名重复：{name}")
        seen_names.add(name)
        if m["id"] in seen_ids:
            sys.exit(f"消息号 0x{m['id']:02X} 重复：{seen_ids[m['id']]} 与 {name}")
        seen_ids[m["id"]] = name
        if not 0 <= m["id"] <= 0xFF:
            sys.exit(f"{name} 的消息号 0x{m['id']:X} 超出 MSG_ID 的 1 字节范围")
        if not m.get("fields"):
            sys.exit(f"{name} 没有任何字段")

        seen_fields = set()
        for f in m["fields"]:
            fname = f["name"]
            if fname in seen_fields:
                sys.exit(f"{name} 的字段名重复：{fname}")
            seen_fields.add(fname)
            if fname == STAMP and f["type"] != STAMP_TYPE:
                sys.exit(
                    f"{name}.{STAMP} 的类型必须是 {STAMP_TYPE}，当前是 {f['type']}"
                )
        if STAMP not in seen_fields:
            sys.exit(f"{name} 缺少 {STAMP} 字段——每条消息必须带绝对时间戳")

        size = payload_size(m)
        if size > max_payload:
            sys.exit(f"{name} 载荷 {size} B 超出 max_payload = {max_payload}")


def gen_hpp(spec) -> str:
    msgs = spec["messages"]
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
    a("// 内容层的 schema 版本——两侧不一致说明字段布局已经不同。")
    a("// 至于不一致时怎么办（拒绝 / 降级），属链路层，不在本文件表态。")
    a(f"constexpr uint16_t kProtocolVersion = 0x{major:02X}{minor:02X};")
    a(f"constexpr uint8_t kProtocolMajor = {major};")
    a(f"constexpr uint8_t kProtocolMinor = {minor};")
    a("")
    a(f'constexpr size_t kMaxPayload = {int(spec["max_payload"])};')
    a("")
    a("// ---- 消息号 ----")
    a("enum class MsgId : uint8_t {")
    for m in msgs:
        a(f'    {m["name"]} = 0x{m["id"]:02X},')
    a("};")
    a("")
    a("#pragma pack(push, 1)")
    a("")
    if uses_time(msgs):
        a("// 绝对时间（Unix 纪元）。与 ROS builtin_interfaces/Time 逐字节同构。")
        a("struct Time {")
        a("    int32_t sec;")
        a("    uint32_t nanosec;")
        a("};")
        a('static_assert(sizeof(Time) == 8, "Time 布局与定义不符");')
        a("")
    for m in msgs:
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
    a("// ---- 消息载荷长度 ----")
    a("// 消息号 -> 载荷字节数。链路层据此知道每帧该带多少字节。")
    a("// 未定义的消息号返回 0——必须丢弃，不能按猜测解释。")
    if not msgs:
        a("// 消息表为空：暂无已知消息号，一切 ID 都返回 0。")
        a("constexpr size_t expected_payload_size(MsgId) { return 0; }")
    else:
        a("constexpr size_t expected_payload_size(MsgId id) {")
        a("    switch (id) {")
        for m in msgs:
            a(f'        case MsgId::{m["name"]}:')
            a(f'            return sizeof({m["name"]});')
        a("        default:")
        a("            return 0;")
        a("    }")
        a("}")
    a("")
    a("// ---- 载荷编解码 ----")
    a("// 结构体是 packed 的，编码本身就是一次 memcpy——用函数包起来是为了把长度")
    a("// 锁成 sizeof：调用方手填长度就能写出「ID 是 A、载荷是 B」这种编译期查不出的")
    a("// 错配，两侧会在场上静默错位。")
    for m in msgs:
        name = m["name"]
        a(f"// {name}  0x{m['id']:02X}  {m['direction']}  {m.get('doc', '')}")
        a(f"inline size_t encode(const {name} &msg, uint8_t *out) {{")
        a(
            f'    static_assert(sizeof({name}) <= kMaxPayload, "{name} 载荷超出 kMaxPayload");'
        )
        a(f"    std::memcpy(out, &msg, sizeof({name}));")
        a(f"    return sizeof({name});")
        a("}")
        a("")
        a(
            f"inline bool decode(const uint8_t *payload, uint8_t payload_len, {name} &msg) {{"
        )
        a(f"    if (payload == nullptr || payload_len != sizeof({name})) {{")
        a("        return false; // 长度对不上：ID 与载荷类型错配，拒绝解释")
        a("    }")
        a(f"    std::memcpy(&msg, payload, sizeof({name}));")
        a("    return true;")
        a("}")
        a("")
    a("}  // namespace foray::lower_link")
    a("")
    return "\n".join(L)


def gen_msg(msg) -> str:
    # BANNER 含换行——每一行都必须带 #，否则第二行会被 .msg 解析器当成字段定义
    L = ["# " + BANNER.replace("\n", "\n# "), ""]
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
        "| ID | 名称 | 方向 | 载荷 | 状态 |",
        "|---|---|---|---|---|",
    ]
    for m in spec["messages"]:
        # 不含周期：多久发一次归链路实现，本仓不定义（见 protocol/lower_link.md）
        L.append(
            f'| `0x{m["id"]:02X}` | `{m["name"]}` | {m["direction"]} '
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
    ranges = spec.get("id_ranges") or []
    if ranges:
        L.append("## 分段")
        L.append("")
        L.append("| 段 | 用途 |")
        L.append("|---|---|")
        for r in ranges:
            L.append(f'| `{r["range"]}` | {r["purpose"]} |')
        L.append("")
    return "\n".join(L)


def main() -> None:
    with open(SPEC, encoding="utf-8") as fh:
        spec = yaml.safe_load(fh)

    validate(spec)

    os.makedirs(os.path.join(OUT, "msg"), exist_ok=True)

    # 清理过期生成物：消息被删除时，对应的 .msg 必须一起消失，
    # 否则残留文件会让「生成物 == 定义」这个不变式失真。
    for stale in glob.glob(os.path.join(OUT, "msg", "*.msg")):
        os.remove(stale)

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
