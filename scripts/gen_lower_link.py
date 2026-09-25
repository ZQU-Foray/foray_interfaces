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


def frame_layout(fr) -> dict:
    """推导帧内各头部字段的偏移与宽度。

    偏移由 sof / len / seq / msg_id 的顺序推导，`header_bytes` 是 YAML 里手写的
    声明。两者必须一致——否则 `crc_region()` 会算出一个与 `encode_frame()` 实际
    写入位置脱节的覆盖范围，CRC 静默地校验错误的字节区间。
    """
    order = [("sof", len(fr["sof"])), ("len", 1), ("seq", 1), ("msg_id", 1)]
    layout = {}
    offset = 0
    for name, size in order:
        layout[name] = (offset, size)
        offset += size
    if offset != int(fr["header_bytes"]):
        names = " + ".join(name for name, _ in order)
        sys.exit(
            f"frame.header_bytes = {fr['header_bytes']}，但按 {names} 推导为 {offset}"
        )
    layout["payload"] = (offset, None)  # 宽度可变，上限是 frame.max_payload
    return layout


def crc_region(fr, layout) -> tuple:
    """由 `frame.crc_covers` 推导 CRC 的起始偏移与固定字节数。

    只支持「从某个头部字段起、连续覆盖到 payload 末尾」——这是唯一不需要长度
    前缀就能算出来的形态，也是本协议采用的形态。其他写法直接报错，不静默降级。
    """
    covers = fr.get("crc_covers") or []
    if not covers or covers[-1] != "payload":
        sys.exit("frame.crc_covers 必须非空，且最后一项是 payload")
    start = layout[covers[0]][0]
    fixed = 0
    for name in covers:
        offset, size = layout[name]
        if offset != start + fixed:
            sys.exit(f"frame.crc_covers 必须是连续区间：{name} 与前一项之间有空洞")
        if size is not None:
            fixed += size
    if start + fixed != layout["payload"][0]:
        sys.exit("frame.crc_covers 的固定部分没有覆盖到 payload 起点")
    return start, fixed, covers


def validate(spec) -> None:
    """生成前的结构校验。

    这些问题漏到生成物里，会变成难懂的编译错误（重复的 case 标签、重名的结构体），
    或者更糟——编译通过但语义错的代码。在这里拦住，报错才指向 YAML 的那一行。
    """
    max_payload = int(spec["frame"]["max_payload"])
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
            sys.exit(f"{name} 没有任何字段——空载荷请走链路管理机制，不要占用消息号")
        size = payload_size(m)
        if size > max_payload:
            sys.exit(f"{name} 载荷 {size} B 超出 frame.max_payload = {max_payload}")


def gen_hpp(spec) -> str:
    fr = spec["frame"]
    layout = frame_layout(fr)
    crc_off, crc_fixed, covers = crc_region(fr, layout)
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
    a("// MAJOR 不一致时拒绝进入 RUNNING（见 protocol/lower_link.md 的「版本」）")
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
    a("// 帧内头部字段偏移——由 frame 段推导，勿手写。")
    a("// 编解码一律引用这些常量，代码里不应再出现字面量偏移。")
    a(f"constexpr size_t kLenOffset = {layout['len'][0]};")
    a(f"constexpr size_t kSeqOffset = {layout['seq'][0]};")
    a(f"constexpr size_t kMsgIdOffset = {layout['msg_id'][0]};")
    a("")
    a(f"// CRC 覆盖范围，由 frame.crc_covers 推导：{' + '.join(covers)}")
    a(f"constexpr size_t kCrcOffset = {crc_off};")
    a(
        f"constexpr size_t kCrcRegionBytes = {crc_fixed}; // 固定部分，payload 另按 LEN 计入"
    )
    a("static_assert(kCrcOffset + kCrcRegionBytes == kHeaderBytes,")
    a('              "CRC 覆盖范围未延伸到载荷起点——帧结构与 crc_covers 不一致");')
    a("")
    a("// ---- 消息号 ----")
    a("enum class MsgId : uint8_t {")
    for m in msgs:
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
    a("// 消息号 -> 期望载荷字节数；未定义的消息号返回 0。")
    a("// LEN 与 ID 对不上说明两侧版本不一致——必须丢弃，不能按猜测解释。")
    a("// 必须放在消息结构体之后：sizeof 需要完整的类型。")
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
    a("// ---- CRC-16/CCITT-FALSE ----")
    a('// 标准 check value：CRC("123456789") == 0x29B1')
    a("// （init 0xFFFF、poly 0x1021、不反转、不异或）")
    a("// 下面的 static_assert 是这套方案的锚点。上位机与下位机包含同一份生成代码，")
    a("// 「生成物一致 + 编译通过」并不能证明它是对的——实现对不上标准时，两侧会")
    a(
        "// 一致地错下去，直到跟 CAN 上的电调、跟裁判系统对接才暴露。这里让它在编译期暴露。"
    )
    a(
        "inline constexpr uint8_t kCrcCheckVector[9] = {'1', '2', '3', '4', '5', '6', '7', '8', '9'};"
    )
    a("")
    a("constexpr uint16_t crc16(const uint8_t *data, size_t len) {")
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
    a("static_assert(crc16(kCrcCheckVector, 9) == 0x29B1,")
    a('              "CRC-16/CCITT-FALSE 实现与标准 check value 不符");')
    a("")
    a("// ---- 组帧 ----")
    a(
        "// 返回写入 out 的字节数；out 容量须 >= kHeaderBytes + payload_len + kTrailerBytes。"
    )
    a("// 参数非法（payload 与长度不匹配、超限、out 为空）时返回 0。")
    a("// 优先用下面每个消息的强类型 encode()——它把长度锁成 sizeof。")
    a(
        "inline size_t encode_frame(MsgId id, const void *payload, uint8_t payload_len, uint8_t seq,"
    )
    a("                          uint8_t *out) {")
    a("    if (out == nullptr || payload_len > kMaxPayload) {")
    a("        return 0;")
    a("    }")
    a("    if (payload == nullptr && payload_len > 0) {")
    a("        return 0;")
    a("    }")
    a("    out[0] = kSof0;")
    a("    out[1] = kSof1;")
    a("    out[kLenOffset] = payload_len;")
    a("    out[kSeqOffset] = seq;")
    a("    out[kMsgIdOffset] = static_cast<uint8_t>(id);")
    a("    if (payload_len > 0) {")
    a("        std::memcpy(out + kHeaderBytes, payload, payload_len);")
    a("    }")
    a("    // CRC 覆盖范围由 kCrcOffset / kCrcRegionBytes 给出，不含 SOF")
    a(
        "    const uint16_t crc = crc16(out + kCrcOffset, kCrcRegionBytes + payload_len);"
    )
    a("    const size_t tail = kHeaderBytes + payload_len;")
    a("    out[tail] = static_cast<uint8_t>(crc & 0xFF);")
    a("    out[tail + 1] = static_cast<uint8_t>(crc >> 8);")
    a("    return tail + kTrailerBytes;")
    a("}")
    a("")
    a("// ---- 解帧 ----")
    a("// 一帧的视图。payload 指向输入缓冲内部，生命周期与输入缓冲一致。")
    a("struct FrameView {")
    a("    MsgId id;")
    a("    uint8_t seq;")
    a("    const uint8_t *payload;")
    a("    uint8_t payload_len;")
    a("};")
    a("")
    a("// 从 buf 中定位一帧。")
    a("// USB CDC 对应用层是字节流——一次 read() 可能拿到半帧，也可能拿到三帧半，")
    a("// 所以解帧必须是「喂多少都能处理」的增量形态，不能假设一次读到一个整帧。")
    a("//   成功   -> 返回 true，view / frame_len 有效，调用方消费 frame_len 字节")
    a("//   未找到 -> 返回 false，调用方丢弃 keep_from 字节（其前都成不了帧）")
    a("// CRC 不通过的候选帧会被跳过并按字节滑动重同步——丢帧优于错帧。")
    a(
        "inline bool decode_frame(const uint8_t *buf, size_t len, FrameView &view, size_t &frame_len,"
    )
    a("                         size_t &keep_from) {")
    a("    size_t i = 0;")
    a("    while (i + kHeaderBytes + kTrailerBytes <= len) {")
    a("        if (buf[i] != kSof0 || buf[i + 1] != kSof1) {")
    a("            ++i;")
    a("            continue;")
    a("        }")
    a("        const uint8_t payload_len = buf[i + kLenOffset];")
    a("        if (payload_len > kMaxPayload) {")
    a("            // 不可能成帧，按垃圾滑动，不等它把缓冲撑满")
    a("            ++i;")
    a("            continue;")
    a("        }")
    a("        const size_t total = kHeaderBytes + payload_len + kTrailerBytes;")
    a("        if (i + total > len) {")
    a("            break; // 半帧：等后续数据，不得当作垃圾丢弃")
    a("        }")
    a("        // CRC 小端落在帧尾")
    a("        const uint16_t got = static_cast<uint16_t>(buf[i + total - 2]) |")
    a("                             static_cast<uint16_t>(buf[i + total - 1] << 8);")
    a(
        "        if (crc16(buf + i + kCrcOffset, kCrcRegionBytes + payload_len) != got) {"
    )
    a("            ++i;")
    a("            continue;")
    a("        }")
    a("        view.id = static_cast<MsgId>(buf[i + kMsgIdOffset]);")
    a("        view.seq = buf[i + kSeqOffset];")
    a("        view.payload = buf + i + kHeaderBytes;")
    a("        view.payload_len = payload_len;")
    a("        frame_len = i + total;")
    a("        keep_from = frame_len;")
    a("        return true;")
    a("    }")
    a("    keep_from = i;")
    a("    return false;")
    a("}")
    a("")
    a("// ---- 强类型编解码 ----")
    a(
        "// encode_frame 只认 void* + 长度：调用方手填长度，就能写出「ID 是 A、载荷是 B」"
    )
    a("// 这种编译期查不出的错配，两侧在场上静默错位。下面每个消息一对包装——")
    a("// 长度由 sizeof 决定（编译期锁死），解码侧校验 LEN 与结构体一致后才解释。")
    a("")
    for m in msgs:
        name = m["name"]
        a(f"// {name}  0x{m['id']:02X}  {m['direction']}  {m.get('doc', '')}")
        a(f"inline size_t encode(const {name} &msg, uint8_t seq, uint8_t *out) {{")
        a(
            f'    static_assert(sizeof({name}) <= kMaxPayload, "{name} 载荷超出 kMaxPayload");'
        )
        a(
            f"    return encode_frame(MsgId::{name}, &msg, static_cast<uint8_t>(sizeof({name})),"
        )
        a("                       seq, out);")
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
