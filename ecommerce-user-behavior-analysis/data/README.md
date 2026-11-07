# 数据说明

## 数据来源

阿里淘宝用户行为公开数据集（User Behavior Data），包含用户的浏览、加购、收藏、购买四类行为记录。本项目从原始数据中抽样前 10 万行用于分析。

## 字段结构

| 字段 | 类型 | 含义 |
|---|---|---|
| user_id | INT | 用户 ID |
| item_id | INT | 商品 ID |
| behavior_type | INT | 行为类型：1 浏览 pv / 2 加购 cart / 3 收藏 fav / 4 购买 buy |
| item_category | INT | 商品类目 ID |
| time | VARCHAR(50) | 行为时间，格式 `YYYY-MM-DD HH`（精确到小时） |

## 导入方式

原始 CSV 未纳入仓库（体积较大）。本地复现时：

1. 下载公开数据集，将前 10 万行保存为 `data/user_action.csv`，列顺序与上表一致；
2. 在 MySQL 创建数据库：

   ```sql
   CREATE DATABASE IF NOT EXISTS taobao_analysis DEFAULT CHARSET utf8mb4;
   ```

3. 运行导入脚本：

   ```bash
   python scripts/import_data.py
   ```

> 导入脚本中的数据库账号、密码、端口按本地环境修改。
