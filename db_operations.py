import streamlit as st
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
import traceback

def get_engine():
    return create_engine(st.secrets["database_url"])

def load_data_from_db(engine):
    shops = pd.read_sql("SELECT * FROM shops ORDER BY date DESC", engine)
    brands = pd.read_sql("SELECT * FROM brands", engine)
    flavors = pd.read_sql("SELECT * FROM flavors", engine)
    prices = pd.read_sql("SELECT * FROM prices", engine)
    local_brands = pd.read_sql("SELECT * FROM local_brands", engine)
    return shops, brands, flavors, prices, local_brands

def upload_to_db(engine, shops_df, brands_df, flavors_df, prices_df, local_brands_df):
    """
    将清洗后的数据写入数据库（先删旧数据再插入新数据）
    """
    # 将所有 NaN 替换为 None
    shops_df = shops_df.replace({np.nan: None})
    for df in [brands_df, flavors_df, prices_df, local_brands_df]:
        if not df.empty:
            df.replace({np.nan: None}, inplace=True)

    # 打印调试信息（在终端可见）
    print("开始写入数据库...")
    print(f"shops_df 形状: {shops_df.shape}")
    print(f"brands_df 形状: {brands_df.shape}")
    print(f"flavors_df 形状: {flavors_df.shape}")
    print(f"prices_df 形状: {prices_df.shape}")
    print(f"local_brands_df 形状: {local_brands_df.shape}")

    # 1. 删除旧数据
    with engine.connect() as conn:
        for _, shop_row in shops_df.iterrows():
            date = shop_row['date']
            shop_name = shop_row['shop_name']
            result = conn.execute(
                text("SELECT id FROM shops WHERE date = :date AND shop_name = :shop_name"),
                {"date": date, "shop_name": shop_name}
            ).fetchone()
            if result:
                old_id = result[0]
                print(f"删除旧记录: id={old_id}, date={date}, shop_name={shop_name}")
                conn.execute(text("DELETE FROM shops WHERE id = :shop_id"), {"shop_id": old_id})
        conn.commit()
        print("旧数据删除完成")

    # 2. 插入新 shops 记录，获取新 ID
    new_ids = []
    with engine.connect() as conn:
        for _, row in shops_df.iterrows():
            # 构建插入语句（列名应与表结构一致）
            insert_stmt = text("""
                INSERT INTO shops (
                    date, investigator, city, shop_name, shop_address, shop_scale, is_chain,
                    recommended_eliquid, recommend_reason, top_device_type, local_brands,
                    key_taste_point, key_taste_goodpoint, product_trial_comment,
                    competitive_advantage, sales_incentive, incentive_details,
                    accept_return_commission, commission_range, sales_restrictions,
                    regulation_accuracy, additional_notes
                ) VALUES (
                    :date, :investigator, :city, :shop_name, :shop_address, :shop_scale, :is_chain,
                    :recommended_eliquid, :recommend_reason, :top_device_type, :local_brands,
                    :key_taste_point, :key_taste_goodpoint, :product_trial_comment,
                    :competitive_advantage, :sales_incentive, :incentive_details,
                    :accept_return_commission, :commission_range, :sales_restrictions,
                    :regulation_accuracy, :additional_notes
                )
                RETURNING id
            """)
            row_dict = row.drop(labels=['shop_id']).to_dict()
            # 确保布尔字段的值是 Python bool 或 None
            for key, val in row_dict.items():
                if isinstance(val, pd.BooleanDtype):
                    row_dict[key] = bool(val) if pd.notna(val) else None
            try:
                result = conn.execute(insert_stmt, row_dict)
                new_id = result.fetchone()[0]
                new_ids.append(new_id)
                print(f"插入新店铺成功，获得ID: {new_id}")
            except Exception as e:
                print(f"插入店铺失败: {e}")
                print("失败的记录:", row_dict)
                raise e
        conn.commit()
        print("新店铺插入完成")

    # 3. 建立临时ID到真实ID的映射
    id_map = {old: new for old, new in zip(shops_df['shop_id'], new_ids)}

    # 4. 插入关联表
    for df, table_name in [
        (brands_df, 'brands'),
        (flavors_df, 'flavors'),
        (prices_df, 'prices'),
        (local_brands_df, 'local_brands')
    ]:
        if not df.empty:
            df['shop_id'] = df['shop_id'].map(id_map)
            print(f"正在插入 {table_name} 表，共 {len(df)} 条记录...")
            try:
                df.to_sql(table_name, engine, if_exists='append', index=False)
                print(f"{table_name} 插入完成")
            except Exception as e:
                print(f"{table_name} 插入失败: {e}")
                raise e

    print("所有数据写入完成")