# Hardware Lab card

## Raspberry Pi RFID Room-card System

双 RC522 房卡管理教学原型，包含树莓派 Python 服务、MariaDB、Qt/C++ 管理端、角色权限、房态与审计记录。

- **平台：** Raspberry Pi · Python · Qt/C++ · MariaDB · RC522 · SG90
- **构建证据：** Python 单元测试与 Qt 5/6 qmake 构建通过；公开后绑定精确 commit 与 Actions run
- **真机状态：** Source-confirmed · Python tests passed · Qt 5/6 client build-verified · Historical UI demonstrated on 2026-04-03 · Current Raspberry Pi/end-to-end hardware re-test not run
- **公开范围：** 四张去元数据并遮盖私网 IP/UID 的历史界面截图、BOM、接线边界图、服务端、Qt 客户端和数据库 schema；当前没有实物照片、演示视频、EDA 或制造文件
- **边界：** 自定义 TCP 无 TLS，RC522 UID 可复制，SG90 无位置反馈；仅限隔离可信局域网教学原型，不是生产门禁系统

- **历史媒体 / EDA：** 已加入经脱敏的历史衍生材料；范围和版本差异见 [`MEDIA_EVIDENCE.md`](MEDIA_EVIDENCE.md)。它们不证明当前公开提交已完成真机复测。
