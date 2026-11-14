#!/usr/bin/env python3
"""从 protocol/vision.yaml 生成视觉前后端共用的契约代码与消息表。

生成物（全部禁止手写）：
    generated/vision.hpp              C++：枚举 + POD 结构体 + 固定容量
    generated/msg/<Name>.msg           ROS 2 消息类型
    generated/vision_table.md          字段表（防文档漂移）

约定：
  * 只生成「字段与语义」；话题名、QoS、周期归装配根与各仓运行时配置。
  * C++ 侧数组一律固定容量（见 caps），避免后端跟踪环里的动态分配。
  * 时间统一 int32 秒 + uint32 纳秒，与 lower_link 的 time 表示一致。

用法:
    python3 scripts/gen_vision.py

CI 校验：重新生成后 `git diff --exit-code`，不一致即失败。
"""

from __future__ import annotations

import os
import sys

try:
    import yaml
except ImportError:  # pragma: no cover - 环境问题直说，不静默
    sys.exit("需要 PyYAML：pip install pyyaml")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SPEC = os.path.join(ROOT, "protocol", "vision.yaml")
OUT = os.path.join(ROOT, "generated")
MSG_OUT = os.path.join(OUT, "msg")

BANNER = (
    "本文件由 scripts/gen_vision.py 自动生成，禁止手写。\n"
    "改协议请改 protocol/vision.yaml。"
)

# 标量类型: (C++ 类型, ROS 类型)
SCALARS = {
    "float32": ("float", "float32"),
    "uint8": ("std::uint8_t", "uint8"),
    "int8": ("std::int8_t", "int8"),
    "uint16": ("std::uint16_t", "uint16"),
    "int16": ("std::int16_t", "int16"),
    "bool": ("bool", "bool"),
    "time": ("Time", "builtin_interfaces/Time"),
    "string": ("std::string", "string"),
}

ROS_INCLUDE = {"time": "builtin_interfaces/msg/time.hpp"}


def snake(name: str) -> str:
    """CamelCase → snake_case（生成的函数名与前端命名保持一致）。"""
    out = []
    for index, char in enumerate(name):
        if char.isupper() and index:
            out.append("_")
        out.append(char.lower())
    return "".join(out)


def banner(prefix: str) -> str:
    """把生成物声明逐行加上注释前缀，避免多行 banner 只有第一行被注释。"""
    return "\n".join((prefix + " " + line).strip() for line in BANNER.splitlines())


def load_spec(path=SPEC):
    """读定义并按生成器需要做基本校验。"""
    with open(path, encoding="utf-8") as handle:
        spec = yaml.safe_load(handle)

    protocol = spec["protocol"]
    for key in ("name", "version", "status"):
        if key not in protocol:
            raise ValueError(f"protocol.{key} 缺失")
    if not protocol["name"].replace("_", "").isalnum():
        raise ValueError("protocol.name 只允许字母数字与下划线")

    names = set()
    for message in spec["messages"]:
        name = message["name"]
        if not name or not name[0].isupper():
            raise ValueError(f"消息名必须以大写字母开头: {name!r}")
        if name in names:
            raise ValueError(f"消息名重复: {name}")
        names.add(name)

    caps = spec.get("caps", {})
    for message in spec["messages"]:
        if not message.get("doc"):
            raise ValueError(f"消息缺 doc: {message['name']}")
        fields = message["fields"]
        if not fields:
            raise ValueError(f"消息没有字段: {message['name']}")
        seen = set()
        for field in fields:
            unknown = set(field) - {"name", "type", "unit", "doc", "cap", "default"}
            if unknown:
                # 未加引号的逗号会把 doc 拆成多余键——这里直接报错，不静默吞掉
                raise ValueError(f"{message['name']} 字段有未知键: {sorted(unknown)}")
            for key in ("name", "type"):
                if key not in field:
                    raise ValueError(f"{message['name']} 的字段缺 {key}")
            if field["name"] in seen:
                raise ValueError(f"{message['name']} 字段重复: {field['name']}")
            seen.add(field["name"])
            base, _size = parse_type(field["type"])
            if (
                base not in SCALARS
                and base not in names
                and base not in spec.get("enums", {})
            ):
                raise ValueError(
                    f"{message['name']}.{field['name']} 未知类型: {field['type']}"
                )
            if field["type"].endswith("[]"):
                if "cap" not in field:
                    raise ValueError(
                        f"{message['name']}.{field['name']} 引用消息数组时必须给 cap"
                    )
                if field["cap"] not in caps:
                    raise ValueError(
                        f"{message['name']}.{field['name']} 的 cap 未在 caps 中定义"
                    )
    return spec


def parse_type(text):
    """把 'float32[8]' 拆成 ('float32', 8)；'Observation[]' 拆成 ('Observation', None)。"""
    if "[" not in text:
        return text, None
    base, rest = text.split("[", 1)
    if not rest.endswith("]"):
        raise ValueError(f"类型写法错误: {text}")
    inner = rest[:-1]
    if inner == "":
        return base, None
    if not inner.isdigit():
        raise ValueError(f"数组长度必须是正整数: {text}")
    return base, int(inner)


def cpp_field(field, spec):
    """返回 (C++ 声明, 结构体内所有额外成员, ROS 声明)。"""
    base, size = parse_type(field["type"])
    name = field["name"]
    if base in SCALARS:
        cpp, ros = SCALARS[base]
        if size is None:
            init = f"{{{field['default']}}}" if "default" in field else ""
            return f"{cpp} {name}{init};", [], f"{ros} {name}"
        return f"std::array<{cpp}, {size}> {name};", [], f"{ros}[{size}] {name}"
    if base in spec.get("enums", {}):
        return f"{base} {name};", [], f"{base} {name}"
    # 嵌套消息
    cap = field.get("cap")
    if not cap:
        raise ValueError(f"{name} 引用消息 {base} 时必须给 cap")
    count = f"{name.removesuffix('s')}_count"
    return (
        f"std::array<{base}, kVisionMax{base}Items> {name};",
        [f"std::uint8_t {count}{{0}};"],
        f"{base}[] {name}",
    )


def enum_block(spec):
    lines = []
    for name, enum in spec["enums"].items():
        state = enum.get("state", name)
        doc = enum.get("doc")
        if doc:
            lines.append(f"/// {doc}")
        lines.append(f"enum class {name} : std::uint8_t {{")
        values = enum["values"]
        for value in values:
            comma = ","
            comment = f"  ///< {value['doc']}" if value.get("doc") else ""
            lines.append(f"  {value['name']} = {value['value']}{comma}{comment}")
        lines.append("};")
        lines.append("")
        lines.append(f"inline constexpr std::size_t k{name}Count = {len(values)};")
        lines.append(f"inline constexpr std::string_view k{name}Names[] = {{")
        for value in values:
            lines.append(f'    "{value["name"]}",')
        lines.append("};")
        lines.append("")
        lines.append(f"inline std::string_view to_string({name} value) {{")
        lines.append(
            f"  return k{name}Names[static_cast<std::size_t>(value) % k{name}Count];"
        )
        lines.append("}")
        lines.append("")
        lines.append(f"inline std::optional<{name}> {snake(name)}_from_string(")
        lines.append("    std::string_view text) {")
        lines.append(f"  for (std::size_t i = 0; i < k{name}Count; ++i) {{")
        lines.append(f"    if (k{name}Names[i] == text) {{")
        lines.append(f"      return static_cast<{name}>(i);")
        lines.append("    }")
        lines.append("  }")
        lines.append("  return std::nullopt;")
        lines.append("}")
        lines.append("")
        del state
    return lines


def cpp_header(spec):
    protocol = spec["protocol"]
    caps = spec.get("caps", {})
    lines = [
        banner("//"),
        f"// 协议 {protocol['name']} {protocol['version']}（{protocol['status']}）",
        "#ifndef DIESEL_VISION_GENERATED_VISION_HPP",
        "#define DIESEL_VISION_GENERATED_VISION_HPP",
        "",
        "#include <array>",
        "#include <cstddef>",
        "#include <cstdint>",
        "#include <optional>",
        "#include <string>",
        "#include <string_view>",
        "",
        "namespace diesel_vision {",
        "",
        f'inline constexpr char kVisionProtocolVersion[] = "{protocol["version"]}";',
    ]
    for name, cap in caps.items():
        lines.append(
            f"inline constexpr std::size_t kVisionMax{name.capitalize()} = {cap};"
        )
    for message in spec["messages"]:
        item_cap = next(
            (
                caps[field["cap"]]
                for other in spec["messages"]
                for field in other["fields"]
                if field["type"].startswith(message["name"] + "[")
            ),
            1,
        )
        lines.append(
            f"inline constexpr std::size_t kVisionMax{message['name']}Items = {item_cap};"
        )
    lines += [
        "",
        "/// 绝对时间（Unix 纪元），与 lower_link 的 time 表示一致。",
        "struct Time {",
        "  std::int32_t sec{0};",
        "  std::uint32_t nanosec{0};",
        "};",
        "",
    ]
    lines += enum_block(spec)
    for message in spec["messages"]:
        lines.append(f"/// {message['doc']}")
        lines.append(f"struct {message['name']} {{")
        for field in message["fields"]:
            if field.get("doc"):
                lines.append(f"  /// {field['doc']}")
            decl, extra, _ros = cpp_field(field, spec)
            lines.append(f"  {decl}")
            for member in extra:
                lines.append(f"  {member}")
        lines.append("};")
        lines.append("")
    lines.append("}  // namespace diesel_vision")
    lines.append("")
    lines.append("#endif  // DIESEL_VISION_GENERATED_VISION_HPP")
    lines.append("")
    return "\n".join(lines)


def ros_message(spec, message):
    lines = [banner("#"), f"# {message['doc']}", ""]
    for field in message["fields"]:
        _decl, _extra, ros = cpp_field(field, spec)
        if field.get("doc"):
            lines.append(f"# {field['doc']}")
        lines.append(ros)
    lines.append("")
    return "\n".join(lines)


def table(spec):
    protocol = spec["protocol"]
    lines = [
        "<!-- " + banner("").replace("\n", " -->\n<!-- ") + " -->",
        "",
        "# 视觉契约字段表（自动生成）",
        "",
        f"协议版本 `{protocol['version']}` · 状态 `{protocol['status']}`",
        "",
        "| 消息 | 字段 | 类型 | 单位 | 语义 |",
        "|---|---|---|---|---|",
    ]
    for message in spec["messages"]:
        for field in message["fields"]:
            lines.append(
                f"| `{message['name']}` | `{field['name']}` | `{field['type']}` | "
                f"{field.get('unit', '—')} | {field.get('doc', '—')} |"
            )
    lines.append("")
    return "\n".join(lines)


def main():
    spec = load_spec()
    os.makedirs(MSG_OUT, exist_ok=True)
    with open(os.path.join(OUT, "vision.hpp"), "w", encoding="utf-8") as handle:
        handle.write(cpp_header(spec))
    for message in spec["messages"]:
        path = os.path.join(MSG_OUT, message["name"] + ".msg")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(ros_message(spec, message))
    with open(os.path.join(OUT, "vision_table.md"), "w", encoding="utf-8") as handle:
        handle.write(table(spec))
    print(f"generated {len(spec['messages'])} messages from {SPEC}")


if __name__ == "__main__":
    main()
