# 目录结构说明

## 目录结构

```
.
├── README.md                本仓定位、接口、上下游
├── AGENTS.md                AI 协作规范
├── plan.md                  开发计划与进度
├── decision.md              关键工程决策日志
├── tree.md                  本文件
├── CODEOWNERS               Review 自动分派
├── .foray-layer             所属层与依赖边界（CI 校验）
├── .gitignore
├── protocol/                协议契约
│   ├── lower_link.md            上位机 ↔ 下位机通讯协议（人读 · 内容层）
│   └── lower_link.yaml          机器可读定义（唯一事实来源）
├── scripts/
│   └── gen_lower_link.py    内容层代码生成器
├── generated/               由生成器产出——禁止手写
│   ├── lower_link.hpp           裸机 C++：MsgId + POD 结构体 + 载荷编解码
│   ├── msg/*.msg                ROS 2 消息类型
│   └── message_table.md         消息表（防文档漂移）
├── tests/                   测试
│   ├── lower_link_test.cpp      生成物的契约测试（CI 编译并运行）
│   ├── test_gen.py              生成器测试（CI 的 test-python 作业跑）
│   └── fixtures/sample.yaml     生成器测试的样例定义——**非真实协议**
├── requirements.txt         Python 依赖（仅 PyYAML，供 CI 的 test-python 作业）
└── .github/
    └── workflows/
        └── ci.yml           组织 CI 模板 + 本仓特有的 gen-check
```

> 目前只有协议契约与它的生成器；帧格式（怎么发送与接收）不在本仓。
> **禁止直接修改 `generated/` 下的任何文件**——改 `lower_link.yaml` 后重新生成。

## 记录约束

MUST NOT 记录以下内容：

- `build/`、`install/`、`log/`、`.git/` 等依赖与产物目录
- 临时文件、缓存文件、日志文件
