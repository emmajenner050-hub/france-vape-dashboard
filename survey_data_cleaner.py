import pandas as pd
import re
import numpy as np

def clean_survey_data(raw_df):
    """
    对原始调研DataFrame进行清洗，返回五个清洗后的DataFrame：
    shops_df, brands_df, flavors_df, prices_df, local_brands_df
    """
    df = raw_df.copy()

    # 基础清洗
    df['date'] = pd.to_datetime(df['date']).dt.date
    city_mapping = {"巴黎": "巴黎市区"}  # 可扩展
    df['city'] = df['city'].replace(city_mapping)
    df['is_chain'] = df['is_chain'].map({'是': True, '否': False})
    df['accept_return_commission'] = df['accept_return_commission'].map({'是': True, '否': False})
    df = df.replace(r'^\s*$', np.nan, regex=True)

    # ----- 1. 店铺主表 -----
    shop_cols = [
        'date', 'investigator', 'city', 'shop_name', 'shop_address',
        'shop_scale', 'is_chain', 'recommended_eliquid', 'recommend_reason',
        'top_device_type', 'local_brands', 'key_taste_point', 'key_taste_goodpoint',
        'product_trial_comment', 'competitive_advantage', 'sales_incentive',
        'incentive_details', 'accept_return_commission', 'commission_range',
        'sales_restrictions', 'regulation_accuracy', 'additional_notes'
    ]
    existing_shop_cols = [col for col in shop_cols if col in df.columns]
    shops_df = df[existing_shop_cols].copy()
    shops_df.insert(0, 'shop_id', range(1, len(shops_df)+1))

    # 将 shop_scale 转换为整数（支持空值）
    shops_df['shop_scale'] = pd.to_numeric(shops_df['shop_scale'], errors='coerce').astype('Int64')

    # 布尔字段处理
    bool_cols = ['is_chain', 'accept_return_commission']
    for col in bool_cols:
        if col in shops_df.columns:
            shops_df[col] = shops_df[col].where(pd.notna(shops_df[col]), None)

    # ----- 2. 品牌表 -----
    brand_type_mapping = {
        'open': 'brands_open',
        'disposable': 'brands_disposable',
        'pod': 'brands_pod',
        'eliquid': 'brands_eliquid'
    }
    brand_records = []
    for idx, row in df.iterrows():
        shop_id = idx + 1
        for prod_type, col_name in brand_type_mapping.items():
            if col_name not in df.columns:
                continue
            brands_str = row[col_name]
            if pd.isna(brands_str):
                continue
            # 支持多种分隔符：逗号、分号、中文逗号
            brands = re.split(r'[;,，]+', str(brands_str))
            brands = [b.strip() for b in brands if b.strip()]
            for brand in brands:
                brand_records.append({
                    'shop_id': shop_id,
                    'product_type': prod_type,
                    'brand': brand
                })
    brands_df = pd.DataFrame(brand_records)

    # ----- 3. 口味表 -----
    flavor_records = []
    for idx, row in df.iterrows():
        shop_id = idx + 1
        # 畅销口味
        if 'top_flavors' in df.columns:
            flavors_str = row['top_flavors']
            if pd.notna(flavors_str):
                flavors = re.split(r'[;,，]+', str(flavors_str))
                flavors = [f.strip() for f in flavors if f.strip()]
                for flavor in flavors:
                    flavor_records.append({
                        'shop_id': shop_id,
                        'flavor': flavor,
                        'source': 'top_flavors'
                    })
        # 店员喜好口味
        if 'staff_fav_brand_flavor' in df.columns:
            staff_str = row['staff_fav_brand_flavor']
            if pd.notna(staff_str):
                # 可能包含品牌:口味格式，这里提取口味部分
                items = re.split(r'[;,，]+', str(staff_str))
                for item in items:
                    item = item.strip()
                    if ':' in item:
                        flavor = item.split(':', 1)[1].strip()
                    else:
                        flavor = item
                    if flavor:
                        flavor_records.append({
                            'shop_id': shop_id,
                            'flavor': flavor,
                            'source': 'staff_favorite'
                        })
    flavors_df = pd.DataFrame(flavor_records)

    # ----- 4. 价格表 -----
    def parse_price(price_str):
        """解析价格字符串，返回 (price, low, high)"""
        cleaned = price_str.replace('欧', '').replace('€', '').strip()
        # 移除千分位逗号（如 1,234.56 -> 1234.56）
        cleaned = re.sub(r'(\d),(\d)', r'\1\2', cleaned)
        # 处理范围
        range_match = re.search(r'(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)', cleaned)
        if range_match:
            low = float(range_match.group(1))
            high = float(range_match.group(2))
            return None, low, high
        # 单个价格
        single_match = re.search(r'(\d+(?:\.\d+)?)', cleaned)
        if single_match:
            return float(single_match.group(1)), None, None
        return None, None, None

    price_records = []
    for idx, row in df.iterrows():
        shop_id = idx + 1
        if 'price_range' not in df.columns:
            continue
        price_str = row['price_range']
        if pd.isna(price_str):
            continue
        specs = str(price_str).split(';')
        for spec in specs:
            spec = spec.strip()
            if not spec:
                continue
            if ':' in spec:
                size_part, price_part = spec.split(':', 1)
                size_part = size_part.strip()
                price_part = price_part.strip()
                # 提取容量（ml）
                ml_match = re.search(r'(\d+)\s*ml', size_part)
                mg_match = re.search(r'(\d+)\s*mg', size_part)
                ml = int(ml_match.group(1)) if ml_match else None
                mg = int(mg_match.group(1)) if mg_match else None
                price, low, high = parse_price(price_part)
                price_records.append({
                    'shop_id': shop_id,
                    'size_ml': ml,
                    'nicotine_mg': mg,
                    'price': price,
                    'price_low': low,
                    'price_high': high,
                    'original_text': spec
                })
            else:
                # 没有规格说明，仅价格
                price, low, high = parse_price(spec)
                if price is not None or low is not None:
                    price_records.append({
                        'shop_id': shop_id,
                        'size_ml': None,
                        'nicotine_mg': None,
                        'price': price,
                        'price_low': low,
                        'price_high': high,
                        'original_text': spec
                    })
    prices_df = pd.DataFrame(price_records)

    # ----- 5. 本地品牌表 -----
    local_brand_records = []
    for idx, row in df.iterrows():
        shop_id = idx + 1
        if 'local_brands' not in df.columns:
            continue
        local_str = row['local_brands']
        if pd.isna(local_str):
            continue
        # 格式可能是 "是:品牌1,品牌2" 或直接 "品牌1,品牌2"
        if ':' in local_str:
            flag_part, brands_part = local_str.split(':', 1)
            flag = flag_part.strip()
            brands = re.split(r'[;,，]+', brands_part)
            brands = [b.strip() for b in brands if b.strip()]
            for brand in brands:
                local_brand_records.append({
                    'shop_id': shop_id,
                    'brand': brand,
                    'is_local': True if flag == '是' else False
                })
        else:
            brands = re.split(r'[;,，]+', local_str)
            brands = [b.strip() for b in brands if b.strip()]
            for brand in brands:
                local_brand_records.append({
                    'shop_id': shop_id,
                    'brand': brand,
                    'is_local': True
                })
    local_brands_df = pd.DataFrame(local_brand_records)

    return shops_df, brands_df, flavors_df, prices_df, local_brands_df