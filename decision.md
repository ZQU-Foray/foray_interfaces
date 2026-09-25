# 关键工程决策日志

> 记录 fork patch、换版本、**破坏性接口变更**、架构取舍。
> 格式见 `foray_docs/repository_structure.md` §7.2。

---

## Decision

Date: 2026-02-19

Context: 本仓从 0 初始化。需要确定它在整体架构中的位置与依赖边界。

Decision: 本仓定位为 **X2** 层，owner 角色为「架构」，
依赖层级 无。

Reason:
- 切分判据 C1–C6 见 `foray_docs/repository_structure.md` §1
- 粒度结论：**一个仓 = 一个团队角色 + 一个变更率档位**
- 被所有仓依赖，**不依赖任何自研仓**。变更代价全组织最高

Alternatives:
- 并入相邻仓（减少仓库数量，但违反团队边界或变更率差异）

Rejected:
- 按 ROS 2 package 粒度切仓 —— 会导致版本矩阵地狱
- 按分层机械切仓 —— 会切断团队边界（Conway）

---

## Decision

Date: 2026-02-19

Context: 上位机与下位机之间的通讯协议需要确定归属。直觉方案是放进 `foray_platform`
（下行 HAL 所在仓），但这条链路是**算法组与电控组之间的跨队契约**。

Decision:
1. 协议规范、机器可读定义与生成物**放本仓**（X2 契约仓）
2. 物理层采用 **USB CDC**（虚拟串口）
3. 两侧代码由 `scripts/gen_lower_link.py` 从 `protocol/lower_link.yaml` **生成**，禁止手写

Reason:
- **判据 C1**（接口不得被实现私有化）：规范若与 HAL 实现同仓，会随实现漂移
- **判据 C6**（跨队共享）：`foray_platform` 电控组没有 Write；放本仓则两组都能提 PR
- 放实现仓会导致协议改动藏在一次「平台层重构」的 PR 里无人审查，违反 **D2**
- 手写两份编解码必然在字节序 / 字段偏移 / CRC 上漂移——生成是唯一可靠解法

Alternatives:
- 放 `foray_platform` —— 被 C1 / C6 否决
- 放 `ControllerCode`（电控组仓）—— 对称地被同一理由否决
- 只写文档，两侧各自手写编解码 —— 无强制一致性，否决

Rejected:
- 每侧各自维护一份 `.hpp` / `.msg` —— 漂移风险不可接受
- 在 USB CDC 上省略 CRC —— USB 链路层确有 CRC，但同一帧格式要复用到 CAN/UART，
  保留 CRC 换取格式可移植性（每帧成本 2 B）

---

## Decision

Date: 2026-09-25

Context: v0.1 草案落地后审查发现三处「生成物与定义会静默脱节」的地方：

1. CRC 覆盖范围在生成器里写死为 `crc16(out + 2, payload_len + 3)`，与 YAML 的
   `crc_covers` / `header_bytes` 没有任何关联
2. `encode_frame` 只接受 `void* + payload_len`，把生成期已知的消息长度丢到运行时
   由调用方手填
3. CI 只做「重新生成 + diff + 编译」，没有任何外部锚点

Decision:

1. 帧内字段偏移与 CRC 覆盖范围由 `frame` 段推导。`crc_covers` 必须是**连续区间、
   以 `payload` 结尾**；`header_bytes` 与推导结果不一致直接报错
2. 每条消息生成一对强类型 `encode` / `decode`，长度由 `sizeof` 决定；解码侧校验
   `LEN == sizeof` 后才解释。新增 `expected_payload_size(id)` 长度表
3. 补两层测试：`tests/lower_link_test.cpp` 对生成物做契约测试（CRC 标准 check
   value、固定帧字节序列、组帧解帧往返、失步重同步、半帧保留）；
   `tests/test_gen.py` 用 fixture 覆盖「逐条消息」的生成路径

Reason:

- 偏移与 CRC 范围手写时，改 `header_bytes` 不会改变 CRC 覆盖区间——静默错位，
  且两侧一致地错，直到跟 CAN 上的电调、跟裁判系统对接才暴露
- 强类型包装把「ID 是 A、载荷是 B」这类错配从运行期提前到编译期。本仓声称
  「布局由编译器兜底」，但 `static_assert(sizeof(X) == N)` 只兜住了结构体内部布局，
  兜不住 ID ↔ 长度 ↔ 类型的对应关系
- **「重新生成 + diff + 编译通过」证明不了实现对。** 生成式方案最大的盲区是两侧
  包含同一份错误实现——必须用标准 check value 这类**外部锚点**钉住
- 消息表为空时，生成器里「逐条消息」的路径一次都不会执行；那是「第一条消息落地时
  才第一次运行」的代码。fixture 测试把它提前覆盖（本次即靠它抓到
  `expected_payload_size` 生成在结构体定义之前、`sizeof` 无法解析的缺陷）

Alternatives:

- 把 CRC 起始偏移作为 YAML 字段显式写出 —— 多一处需要手改同步的地方，与
  「唯一事实来源」相悖

Rejected:

- 生成 CRC 查表版本（512 B Flash）—— 当前位运算实现在 1 kHz 下够用，
  等实测出瓶颈再换，避免过早优化
- 内置链路管理消息（握手 / 心跳）—— 审查认定的结构缺口，但改动面涉及消息表内容
  与两侧状态机，留待与电控组共同确定后再做（见 `plan.md`）
- 补 Python 侧生成物 —— 同理留待消息表冻结后（目前 `msg/*.msg` 里也没有消息号）

---

## Decision

Date: 2026-09-25

Context: `protocol/lower_link.md` 写到 484 行：四种职责混在一个文件（规范 / 设计说明 /
操作手册 / 仓库结构），「怎么写消息」在 YAML 注释、§4.3、§10.2 三处重复，而
「为什么这么设计」的大段引用块与硬约束混排——读者分不清哪些是必须遵守的。
§5「时序」三节全是「待填写」空表，占 36 行零信息量。

Decision: 协议文档**只写规范**——线上跑什么字节、两侧各自必须做什么。
设计理由、操作流程、YAML schema、仓库结构一律不写。

Reason:

- 读者是在工作，不是在学习。文档是对照表，不是教程
- 可推导的内容放在代码里更不易漂移：字段类型在生成器的 `TYPES` 表、解帧契约在
  生成的 `lower_link.hpp` 注释、改协议流程在 YAML 头部注释
- 「约定」与「理由」混排，会让实现者分不清优先级；安全约束尤其不能被理由淹没

Alternatives:

- 另设「设计说明」一章集中放理由 —— 读者要在两处之间跳，且该章必然继续膨胀

Rejected:

- 把删掉的操作性内容搬进 README —— 会制造第二份需要同步维护的副本；
  YAML 头部注释是更好的落点（那段「数组类型必须加引号」的坑已移入其中）
- 协议文档按 RFC 风格保留 normative / informative 分区 —— 对 6 节的文档是过度设计

结果：484 → 110 行。**跨文件引用章节一律改用章节名而非编号**
（`见 protocol/lower_link.md 的「版本」`）——编号会随增删章节静默失效，
且失效点分散在 `ControllerCode`、`foray_docs` 等其他仓，本仓 grep 不到。
