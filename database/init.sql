-- 房卡管理系统数据库初始化脚本

-- 创建数据库
CREATE DATABASE IF NOT EXISTS room_card_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE room_card_system;

-- 房卡表
CREATE TABLE IF NOT EXISTS card (
    id INT PRIMARY KEY AUTO_INCREMENT,
    uid VARCHAR(50) UNIQUE NOT NULL COMMENT 'RFID卡唯一标识',
    room_id INT COMMENT '绑定房间ID',
    status TINYINT DEFAULT 0 COMMENT '0:正常 1:挂失 2:注销',
    expire_date DATE COMMENT '有效期',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_uid (uid),
    INDEX idx_room (room_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 房间表
CREATE TABLE IF NOT EXISTS room (
    id INT PRIMARY KEY AUTO_INCREMENT,
    room_number VARCHAR(20) NOT NULL UNIQUE COMMENT '房间号',
    floor INT COMMENT '楼层',
    status TINYINT DEFAULT 0 COMMENT '0:空闲 1:入住',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_room_number (room_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 操作日志表
CREATE TABLE IF NOT EXISTS operation_log (
    id INT PRIMARY KEY AUTO_INCREMENT,
    card_uid VARCHAR(50) COMMENT '卡UID',
    operation VARCHAR(20) NOT NULL COMMENT '操作类型:发行/挂失/注销/开门',
    operator VARCHAR(50) COMMENT '操作人',
    result TINYINT COMMENT '0:失败 1:成功',
    detail VARCHAR(255) COMMENT '详情',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_card_uid (card_uid),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 用户表
CREATE TABLE IF NOT EXISTS user (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(128) NOT NULL,
    role VARCHAR(20) DEFAULT 'operator' COMMENT 'admin/operator/viewer',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 为已存在的历史数据库补上外键之前，请先清理无效 room_id。
-- 新部署可安全执行；重复执行时先检查约束是否已经存在。
SET @constraint_exists := (
    SELECT COUNT(*)
    FROM information_schema.TABLE_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE()
      AND TABLE_NAME = 'card'
      AND CONSTRAINT_NAME = 'fk_card_room'
);
SET @constraint_sql := IF(
    @constraint_exists = 0,
    'ALTER TABLE card ADD CONSTRAINT fk_card_room FOREIGN KEY (room_id) REFERENCES room(id) ON DELETE SET NULL',
    'SELECT 1'
);
PREPARE constraint_statement FROM @constraint_sql;
EXECUTE constraint_statement;
DEALLOCATE PREPARE constraint_statement;

-- 不创建默认账号或默认密码。
-- 初始化后运行 scripts/create_user.py，在本机交互式创建第一个管理员。

-- 插入一些测试房间 (使用 IGNORE 防止重复运行脚本报错或产生多余记录)
INSERT IGNORE INTO room (room_number, floor) VALUES
('101', 1), ('102', 1), ('103', 1), ('104', 1),
('201', 2), ('202', 2), ('203', 2), ('204', 2),
('301', 3), ('302', 3), ('303', 3), ('304', 3);
