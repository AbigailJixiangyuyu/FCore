# 原始数据归档

`email-Eu-core-temporal-Dept3.txt.gz` 是 SNAP 官方提供的 Email 部门 3 子网原始压缩包，下载后完整保存，不修改或重新压缩。其他真实数据仍默认不纳入版本控制。

- [直接下载](https://snap.stanford.edu/data/email-Eu-core-temporal-Dept3.txt.gz)
- [数据集说明](https://snap.stanford.edu/data/email-Eu-core-temporal.html)
- SHA-256：`b1f92288e855044bbc74bacac39d42b12e59ec2a0130ad8df419786eb46a7bff`
- 解压后每行为 `源成员ID 目标成员ID 相对秒`；时间从零开始，供应方未提供真实日历起点。

数据来源引用：Ashwin Paranjape, Austin R. Benson, Jure Leskovec. *Motifs in Temporal Networks*. WSDM 2017。

持久社区参考论文使用完整 Email 网络；这里选择的是该网络的官方 Dept3 子网。转换命令与时间口径见 [处理后数据说明](../email-eu-core-dept3/README.md)。

此归档仍完整包含 12,216 条原始记录。当前 v2 数据包仅使用 `0 ≤ t < 45,310,384` 的 12,099 条记录，舍弃 273 天长空白之后的 117 条；截断只作用于输出，不改变此压缩包或其指纹。
