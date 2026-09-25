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
