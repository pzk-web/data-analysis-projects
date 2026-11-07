# -*- coding: utf-8 -*-
"""
将抽样 CSV 导入 MySQL 的 taobao_analysis.user_behavior_new 表。
运行前：在 MySQL 中已创建数据库 taobao_analysis，并把数据放到 data/user_action.csv。
"""
import os
import pandas as pd
import pymysql

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, 'data', 'user_action.csv')

# 数据库连接配置（按本地环境修改）
DB_CONF = dict(host='localhost', port=3306, user='root',
               password='539258', database='taobao_analysis', charset='utf8mb4')

# 1. 读取 CSV（抽样前 10 万行）
df = pd.read_csv(CSV_PATH, nrows=100000)
print(f'读取了 {len(df)} 行数据')

# 2. 连接 MySQL
conn = pymysql.connect(**DB_CONF)
cursor = conn.cursor()

# 3. 删旧表建新表
cursor.execute("DROP TABLE IF EXISTS user_behavior_new")
cursor.execute("""
CREATE TABLE user_behavior_new (
    user_id INT,
    item_id INT,
    behavior_type INT,
    item_category INT,
    time VARCHAR(50)
)
""")

# 4. 批量插入
cols = ','.join(df.columns)
values = ','.join(['%s'] * len(df.columns))
sql = f"INSERT INTO user_behavior_new ({cols}) VALUES ({values})"
data = [tuple(row) for row in df.values]
cursor.executemany(sql, data)
conn.commit()

print(f'导入成功，共 {len(df)} 行')

cursor.close()
conn.close()
