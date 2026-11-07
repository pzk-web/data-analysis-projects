# -*- coding: utf-8 -*-
"""
电商用户行为分析 —— 报表生成脚本
数据库: taobao_analysis / 表: user_behavior_new
运行: python scripts/build_report.py
输出: images/ 下的全部图表
"""
import os
import pymysql
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ---------- 全局配置 ----------
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = os.path.join(BASE_DIR, 'images')
os.makedirs(IMG_DIR, exist_ok=True)

DB_CONF = dict(host='localhost', port=3306, user='root',
               password='539258', database='taobao_analysis', charset='utf8mb4')

BEHAVIOR_MAP = {1: '浏览pv', 2: '加购cart', 3: '收藏fav', 4: '购买buy'}


def get_conn():
    return pymysql.connect(**DB_CONF)


def save(fig, name):
    path = os.path.join(IMG_DIR, name)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'已保存: {path}')


# ========== 1. 行为次数分布 ==========
def behavior_distribution():
    conn = get_conn()
    sql = """
    SELECT behavior_type, COUNT(*) AS cnt
    FROM user_behavior_new
    GROUP BY behavior_type ORDER BY behavior_type
    """
    df = pd.read_sql(sql, conn)
    conn.close()

    df['label'] = df['behavior_type'].map(BEHAVIOR_MAP)
    df['pct'] = (df['cnt'] / df['cnt'].sum() * 100).round(1)

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(df['label'], df['cnt'],
                  color=['#4e79a7', '#f28e2b', '#e15759', '#76b7b2'])
    ax.set_title('各行为类型次数分布', fontsize=14, pad=15)
    ax.set_ylabel('行为次数')
    for b, c, p in zip(bars, df['cnt'], df['pct']):
        ax.text(b.get_x() + b.get_width()/2, b.get_height(),
                f'{c}\n({p}%)', ha='center', va='bottom', fontsize=10)
    ax.set_ylim(0, df['cnt'].max() * 1.15)
    save(fig, 'behavior_distribution.png')
    return df


# ========== 2. 标准转化漏斗（层层包含） ==========
def funnel():
    conn = get_conn()
    sql = """
    SELECT
      COUNT(DISTINCT CASE WHEN behavior_type=1 THEN user_id END) AS pv_users,
      COUNT(DISTINCT CASE WHEN behavior_type=2 AND user_id IN
        (SELECT user_id FROM user_behavior_new WHERE behavior_type=1)
        THEN user_id END) AS pv_cart,
      COUNT(DISTINCT CASE WHEN behavior_type=3 AND user_id IN
        (SELECT user_id FROM user_behavior_new WHERE behavior_type=1)
        AND user_id IN (SELECT user_id FROM user_behavior_new WHERE behavior_type=2)
        THEN user_id END) AS pv_cart_fav,
      COUNT(DISTINCT CASE WHEN behavior_type=4 AND user_id IN
        (SELECT user_id FROM user_behavior_new WHERE behavior_type=1)
        AND user_id IN (SELECT user_id FROM user_behavior_new WHERE behavior_type=2)
        AND user_id IN (SELECT user_id FROM user_behavior_new WHERE behavior_type=3)
        THEN user_id END) AS pv_cart_fav_buy
    FROM user_behavior_new
    """
    df = pd.read_sql(sql, conn)
    conn.close()

    stages = ['浏览pv', '加购cart', '收藏fav', '购买buy']
    users = [int(df['pv_users'][0]), int(df['pv_cart'][0]),
             int(df['pv_cart_fav'][0]), int(df['pv_cart_fav_buy'][0])]
    # 逐级转化率（相对上一层）
    rates = ['']
    for i in range(1, 4):
        rates.append(f'{users[i]/users[i-1]*100:.0f}%')

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(stages, users, color=['#4e79a7', '#f28e2b', '#e15759', '#76b7b2'])
    ax.set_title('用户行为转化漏斗（层层包含）', fontsize=14, pad=15)
    ax.set_xlabel('用户数')
    ax.invert_yaxis()
    for i, (v, r) in enumerate(zip(users, rates)):
        ax.text(v + 10, i, f'{v}人  {r}', va='center', fontsize=11)
    save(fig, 'funnel.png')

    overall = users[-1] / users[0] * 100
    print(f'整体转化率(浏览->购买): {overall:.1f}%')
    return pd.DataFrame({'阶段': stages, '用户数': users, '逐级转化率': rates})


# ========== 3. RF 用户分层 ==========
def rf_segmentation():
    conn = get_conn()
    buy_sql = """
    SELECT user_id, COUNT(*) AS F,
           MAX(DATE(STR_TO_DATE(time, '%Y-%m-%d %H'))) AS last_buy
    FROM user_behavior_new WHERE behavior_type=4 GROUP BY user_id
    """
    buy_df = pd.read_sql(buy_sql, conn)
    all_df = pd.read_sql("SELECT DISTINCT user_id FROM user_behavior_new", conn)
    conn.close()

    buy_df['last_buy'] = pd.to_datetime(buy_df['last_buy'])
    base_date = buy_df['last_buy'].max()
    buy_df['R'] = (base_date - buy_df['last_buy']).dt.days

    r_med = buy_df['R'].median()
    f_med = buy_df['F'].median()
    buy_df['R_high'] = (buy_df['R'] <= r_med).astype(int)
    buy_df['F_high'] = (buy_df['F'] >= f_med).astype(int)

    def seg(row):
        if row['R_high'] == 1 and row['F_high'] == 1:
            return '重要价值用户'
        if row['R_high'] == 1 and row['F_high'] == 0:
            return '新客待发展'
        if row['R_high'] == 0 and row['F_high'] == 1:
            return '重要挽留用户'
        return '流失用户'

    buy_df['segment'] = buy_df.apply(seg, axis=1)

    buy_users = set(buy_df['user_id'])
    non_buy_n = len(all_df) - len(buy_users)

    order = ['重要价值用户', '新客待发展', '重要挽留用户', '流失用户', '潜在未转化用户']
    counts = buy_df['segment'].value_counts().to_dict()
    counts['潜在未转化用户'] = non_buy_n
    seg_df = pd.DataFrame({'分层': order, '人数': [counts[s] for s in order]})

    # 图3: 分层人数条形图
    fig, ax = plt.subplots(figsize=(10, 5.5))
    colors = ['#59a14f', '#4e79a7', '#f28e2b', '#e15759', '#b0b0b0']
    bars = ax.barh(seg_df['分层'], seg_df['人数'], color=colors)
    ax.invert_yaxis()
    ax.set_title('用户分层结果（RF模型）', fontsize=14, pad=15)
    ax.set_xlabel('用户数')
    for b, v in zip(bars, seg_df['人数']):
        ax.text(v + 5, b.get_y() + b.get_height()/2, str(v), va='center')
    save(fig, 'rf_segment.png')

    # 图4: R-F 四象限散点
    fig, ax = plt.subplots(figsize=(9, 7))
    seg_colors = {'重要价值用户': '#59a14f', '新客待发展': '#4e79a7',
                  '重要挽留用户': '#f28e2b', '流失用户': '#e15759'}
    for name, g in buy_df.groupby('segment'):
        ax.scatter(g['R'], g['F'], s=40, alpha=0.7, label=name, color=seg_colors[name])
    ax.axvline(r_med, color='gray', ls='--', lw=1)
    ax.axhline(f_med, color='gray', ls='--', lw=1)
    ax.set_xlabel('R: 距最近购买天数（越近越好）')
    ax.set_ylabel('F: 购买次数（越多越好）')
    ax.set_title('购买用户 R-F 四象限分布', fontsize=14, pad=15)
    ax.legend()
    save(fig, 'rf_quadrant.png')

    print(f'基准日: {base_date.date()} | R中位数={r_med} | F中位数={f_med}')
    return seg_df, buy_df, base_date, r_med, f_med


# ========== 4. 类目效率分析 ==========
def category_efficiency():
    conn = get_conn()
    sql = """
    SELECT item_category,
           COUNT(DISTINCT CASE WHEN behavior_type=1 THEN user_id END) AS pv_users,
           COUNT(DISTINCT CASE WHEN behavior_type=4 THEN user_id END) AS buy_users
    FROM user_behavior_new GROUP BY item_category
    """
    df = pd.read_sql(sql, conn)
    conn.close()

    df['conv'] = np.where(df['pv_users'] > 0, df['buy_users'] / df['pv_users'], 0)
    # 过滤小样本：浏览用户 >= 50，避免个位数样本造成转化率失真
    big = df[df['pv_users'] >= 50].copy()

    high = big.sort_values('conv', ascending=False).head(8)
    # 零成交类目中，按浏览人数取 TOP8（高曝光零购买的问题类目）
    low = big[big['buy_users'] == 0].sort_values('pv_users', ascending=False).head(8)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    axes[0].barh(high['item_category'].astype(str), high['conv']*100, color='#59a14f')
    axes[0].set_title('高转化类目 TOP8（浏览≥50人）', fontsize=12)
    axes[0].set_xlabel('购买转化率(%)')
    axes[0].invert_yaxis()

    axes[1].barh(low['item_category'].astype(str), low['pv_users'], color='#e15759')
    axes[1].set_title('高曝光零购买类目 TOP8（浏览≥50人）', fontsize=12)
    axes[1].set_xlabel('浏览用户数')
    axes[1].invert_yaxis()
    save(fig, 'category_conversion.png')

    print(f'类目总数: {len(df)} | 有购买类目: {(df["buy_users"]>0).sum()} | 零购买: {(df["buy_users"]==0).sum()}')
    return df, high, low


if __name__ == '__main__':
    print('=== 1. 行为分布 ===')
    print(behavior_distribution())
    print('\n=== 2. 转化漏斗 ===')
    print(funnel())
    print('\n=== 3. RF 分层 ===')
    seg_df, _, _, _, _ = rf_segmentation()
    print(seg_df)
    print('\n=== 4. 类目效率 ===')
    _, high, low = category_efficiency()
    print('高转化:\n', high)
    print('低转化:\n', low)
