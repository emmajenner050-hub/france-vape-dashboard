import streamlit as st
import pandas as pd
import plotly.express as px
import matplotlib.pyplot as plt
import re
from db_operations import get_engine, load_data_from_db, upload_to_db
from survey_data_cleaner import clean_survey_data

# 设置 matplotlib 中文字体（可选）
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'WenQuanYi Zen Hei', 'Noto Sans CJK SC']
plt.rcParams['axes.unicode_minus'] = False

st.set_page_config(page_title="法国电子烟市场调研分析", layout="wide")
st.title("🇫🇷 法国电子烟市场调研分析看板")

# ------------------------------
# 初始化 session state
# ------------------------------
if "data_loaded" not in st.session_state:
    st.session_state.data_loaded = False
if "upload_processed" not in st.session_state:
    st.session_state.upload_processed = False

engine = get_engine()

def reload_data():
    """从数据库重新加载所有数据并存入 session state"""
    try:
        shops, brands, flavors, prices, local_brands = load_data_from_db(engine)
        st.session_state.shops = shops
        st.session_state.brands = brands
        st.session_state.flavors = flavors
        st.session_state.prices = prices
        st.session_state.local_brands = local_brands
        st.session_state.data_loaded = True
        print("数据加载成功，shops数量:", len(shops))
    except Exception as e:
        print("数据加载失败:", e)
        st.error(f"数据加载失败: {e}")

def normalize_brand(brand):
    """品牌名称标准化"""
    if pd.isna(brand):
        return brand
    brand = str(brand).strip()
    if brand.lower() in ['无', 'none', '']:
        return None
    mapping = {
        'vaporesso': 'Vaporesso',
        'geek vape': 'Geek Vape',
        'geekvape': 'Geek Vape',
        'oxva': 'Oxva',
        'voopoo': 'Voopoo',
        'aspire': 'Aspire',
        'lost vape': 'Lost Vape',
        'lost mary': 'Lost Mary',
        'elfbar': 'Elfbar',
        'vuse': 'Vuse',
        'jnr': 'JNR',
    }
    lower_brand = brand.lower()
    if lower_brand in mapping:
        return mapping[lower_brand]
    return brand

# 首次加载或数据库已有数据
if not st.session_state.data_loaded:
    reload_data()

if st.session_state.shops.empty:
    st.warning("数据库中暂无数据，请先上传 Excel 文件。")
    st.stop()

# ------------------------------
# 侧边栏：数据上传与全局筛选
# ------------------------------
with st.sidebar:
    st.header("📁 数据管理")
    
    uploaded_file = st.file_uploader("上传新调研数据 (Excel)", type=["xlsx"])
    if uploaded_file is not None and not st.session_state.upload_processed:
        try:
            raw_df = pd.read_excel(uploaded_file, header=1)
            st.success("✅ 文件读取成功，正在清洗...")
            
            shops_df, brands_df, flavors_df, prices_df, local_brands_df = clean_survey_data(raw_df)
            st.info("🔄 清洗完成，正在写入数据库...")
            
            with st.spinner("正在写入数据库，请稍候..."):
                upload_to_db(engine, shops_df, brands_df, flavors_df, prices_df, local_brands_df)
            
            st.session_state.upload_processed = True
            st.success("🎉 数据已成功导入数据库！")
            
            with st.spinner("正在刷新数据..."):
                reload_data()
            st.rerun()
        except Exception as e:
            st.error(f"❌ 处理失败：{e}")
            import traceback
            traceback.print_exc()
            st.session_state.upload_processed = False
    
    if st.session_state.upload_processed:
        if st.button("重置上传状态"):
            st.session_state.upload_processed = False
            st.rerun()
    
    # 全局筛选器
    st.header("🔍 筛选数据")
    shops_df = st.session_state.shops
    all_cities = shops_df['city'].dropna().unique()
    all_scales = shops_df['shop_scale'].dropna().unique()
    all_chain = shops_df['is_chain'].dropna().unique()

    selected_cities = st.multiselect("城区", all_cities, default=all_cities)
    selected_scales = st.multiselect("门店规模", all_scales, default=all_scales)
    selected_chain = st.multiselect("是否连锁", all_chain, default=all_chain)

    filtered_shops = shops_df[
        shops_df['city'].isin(selected_cities) &
        shops_df['shop_scale'].isin(selected_scales) &
        shops_df['is_chain'].isin(selected_chain)
    ]
    filtered_ids = filtered_shops['id'].tolist()

    # 过滤关联表
    filtered_brands = st.session_state.brands[st.session_state.brands['shop_id'].isin(filtered_ids)]
    filtered_flavors = st.session_state.flavors[st.session_state.flavors['shop_id'].isin(filtered_ids)]
    filtered_prices = st.session_state.prices[st.session_state.prices['shop_id'].isin(filtered_ids)]
    filtered_local_brands = st.session_state.local_brands[st.session_state.local_brands['shop_id'].isin(filtered_ids)]

    # 品牌名称标准化（全局应用）
    filtered_brands['brand'] = filtered_brands['brand'].apply(normalize_brand)
    filtered_brands = filtered_brands.dropna(subset=['brand'])

# ------------------------------
# 主体：多标签页
# ------------------------------
tabs = st.tabs([
    "📈 数据概览",
    "🏆 畅销品牌",
    "🍭 口味与口感",
    "💰 定价与包装",
    "🌍 区域差异",
    "⚖️ 销售法规",
    "📝 调研总结",
    "💡 行动建议"
])

# ---------- 1. 数据概览 ----------
with tabs[0]:
    st.subheader("调研数量统计")
    col1, col2, col3 = st.columns(3)
    col1.metric("总店铺数", len(filtered_shops))
    col2.metric("调研城区数", filtered_shops['city'].nunique())
    col3.metric("调研人数", filtered_shops['investigator'].nunique())

    daily = filtered_shops['date'].value_counts().sort_index()
    fig = px.bar(x=daily.index, y=daily.values, labels={'x':'日期', 'y':'店铺数'}, title="每日调研店铺数")
    st.plotly_chart(fig, use_container_width=True)

    city_counts = filtered_shops['city'].value_counts()
    fig = px.pie(values=city_counts.values, names=city_counts.index, title="城区分布")
    st.plotly_chart(fig, use_container_width=True)

# ---------- 2. 畅销品牌 ----------
with tabs[1]:
    st.subheader("畅销品牌排行榜")
    prod_type = st.selectbox("产品类型", filtered_brands['product_type'].unique())
    
    brand_counts = filtered_brands[filtered_brands['product_type'] == prod_type]['brand'].value_counts().head(10).reset_index()
    brand_counts.columns = ['brand', 'count']
    brand_counts = brand_counts.sort_values('count', ascending=False)
    fig = px.bar(brand_counts, x='count', y='brand', orientation='h',
                 labels={'count':'提及次数', 'brand':'品牌'}, title=f"Top 10 {prod_type} 品牌",
                 category_orders={'brand': brand_counts['brand'].tolist()})
    st.plotly_chart(fig, use_container_width=True)

    show_local_only = st.checkbox("仅显示本地品牌")
    if show_local_only:
        local_brand_names = filtered_local_brands[filtered_local_brands['is_local'] == True]['brand'].unique()
        brand_counts_local = brand_counts[brand_counts['brand'].isin(local_brand_names)]
        if not brand_counts_local.empty:
            brand_counts_local = brand_counts_local.sort_values('count', ascending=False)
            fig = px.bar(brand_counts_local, x='count', y='brand', orientation='h', title="本地品牌排行榜",
                         category_orders={'brand': brand_counts_local['brand'].tolist()})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("没有本地品牌数据")

    st.subheader("品牌竞争优势")
    advantages = filtered_shops['competitive_advantage'].dropna()
    if not advantages.empty:
        all_adv = []
        for adv in advantages:
            parts = re.split(r'[;,，]+', str(adv))
            for p in parts:
                p = p.strip()
                if p:
                    all_adv.append(p)
        adv_series = pd.Series(all_adv)
        adv_counts = adv_series.value_counts().reset_index()
        adv_counts.columns = ['竞争优势', '提及次数']
        adv_counts = adv_counts.sort_values('提及次数', ascending=False).head(10)
        fig = px.bar(adv_counts, x='提及次数', y='竞争优势', orientation='h', title="竞争优势关键词 Top 10",
                     category_orders={'竞争优势': adv_counts['竞争优势'].tolist()})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("暂无竞争优势数据")

# ---------- 3. 口味与口感 ----------
with tabs[2]:
    st.subheader("热门口味分析")
    source = st.radio("口味来源", ['全部', '店铺推荐 (top_flavors)', '店员喜好 (staff_favorite)'])
    if source == '全部':
        flavor_data = filtered_flavors
    elif source == '店铺推荐 (top_flavors)':
        flavor_data = filtered_flavors[filtered_flavors['source'] == 'top_flavors']
    else:
        flavor_data = filtered_flavors[filtered_flavors['source'] == 'staff_favorite']

    flavor_counts = flavor_data['flavor'].value_counts().head(15).reset_index()
    flavor_counts.columns = ['flavor', 'count']
    flavor_counts = flavor_counts.sort_values('count', ascending=False)
    fig = px.bar(flavor_counts, x='count', y='flavor', orientation='h',
                 labels={'count':'提及次数', 'flavor':'口味'}, title="畅销/喜好口味 Top 15",
                 category_orders={'flavor': flavor_counts['flavor'].tolist()})
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("口感关注点")
    taste_points = filtered_shops['key_taste_point'].dropna()
    if not taste_points.empty:
        taste_counts = taste_points.value_counts()
        fig = px.pie(values=taste_counts.values, names=taste_counts.index, title="最在意的口感点")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("暂无口感关注点数据")

    st.subheader("口感优点分析")
    taste_good = filtered_shops['key_taste_goodpoint'].dropna()
    if not taste_good.empty:
        good_counts = taste_good.value_counts().head(10).reset_index()
        good_counts.columns = ['口感优点', '提及次数']
        good_counts = good_counts.sort_values('提及次数', ascending=False)
        fig = px.bar(good_counts, x='提及次数', y='口感优点', orientation='h', title="口感优点 Top 10",
                     category_orders={'口感优点': good_counts['口感优点'].tolist()})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("暂无口感优点数据")

# ---------- 4. 定价与包装 ----------
with tabs[3]:
    st.subheader("包装规格与价格分析")

    if not filtered_prices.empty:
        size_counts = filtered_prices['size_ml'].value_counts().reset_index()
        size_counts.columns = ['规格(ml)', '次数']
        fig = px.bar(size_counts, x='规格(ml)', y='次数', title="包装规格出现频次")
        fig.update_xaxes(type='category')
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("不同规格价格区间（分城区）")
        price_with_city = filtered_prices.merge(filtered_shops[['id', 'city']], left_on='shop_id', right_on='id')
        if not price_with_city.empty:
            cities = sorted(price_with_city['city'].unique())
            for city in cities:
                city_data = price_with_city[price_with_city['city'] == city]
                st.markdown(f"**{city}**")
                sizes = sorted(city_data['size_ml'].dropna().unique())
                nics = sorted(city_data['nicotine_mg'].dropna().unique())
                table_data = []
                for size in sizes:
                    row = {'规格(ml)': size}
                    for nic in nics:
                        spec_data = city_data[(city_data['size_ml'] == size) & (city_data['nicotine_mg'] == nic)]
                        if not spec_data.empty:
                            min_price = spec_data['price'].min()
                            max_price = spec_data['price'].max()
                            if min_price == max_price:
                                price_str = f"{min_price:.2f}欧"
                            else:
                                price_str = f"{min_price:.2f}-{max_price:.2f}欧"
                        else:
                            price_str = "-"
                        row[f'{nic}mg'] = price_str
                    table_data.append(row)
                df_table = pd.DataFrame(table_data)
                st.dataframe(df_table, use_container_width=True)
        else:
            st.info("暂无价格数据")

        st.subheader("包装规格与尼古丁含量组合分析")
        combo_counts = filtered_prices.groupby(['size_ml', 'nicotine_mg']).size().reset_index(name='出现次数')
        combo_counts = combo_counts.sort_values('出现次数', ascending=False)
        st.markdown("**主要组合：**")
        for _, row in combo_counts.head(5).iterrows():
            st.markdown(f"- {int(row['size_ml'])}ml + {int(row['nicotine_mg'])}mg：出现 {int(row['出现次数'])} 次")
    else:
        st.info("暂无价格数据")

# ---------- 5. 区域差异 ----------
with tabs[4]:
    st.subheader("不同城区对比分析")
    cities = filtered_shops['city'].unique()
    for i in range(0, len(cities), 2):
        cols = st.columns(2)
        for j, col in enumerate(cols):
            if i+j < len(cities):
                city = cities[i+j]
                with col:
                    st.markdown(f"### {city}")
                    if not filtered_prices.empty:
                        price_with_city = filtered_prices.merge(filtered_shops[['id', 'city']], left_on='shop_id', right_on='id')
                        city_price = price_with_city[price_with_city['city'] == city]
                        city_price = city_price.dropna(subset=['price', 'size_ml'])
                        if not city_price.empty:
                            st.markdown("**价格区间**")
                            size_stats = city_price.groupby('size_ml')['price'].agg(['min', 'max'])
                            for size, row_stats in size_stats.iterrows():
                                if row_stats['min'] == row_stats['max']:
                                    st.markdown(f"- {size}ml：{row_stats['min']:.2f}欧")
                                else:
                                    st.markdown(f"- {size}ml：{row_stats['min']:.2f}欧 - {row_stats['max']:.2f}欧")
                        else:
                            st.info("无价格数据")
                    st.markdown("**热销品牌**")
                    city_shop_ids = filtered_shops[filtered_shops['city'] == city]['id'].tolist()
                    for prod_type in ['open', 'disposable', 'eliquid']:
                        city_brands = filtered_brands[(filtered_brands['product_type'] == prod_type) & 
                                                      (filtered_brands['shop_id'].isin(city_shop_ids))]
                        if not city_brands.empty:
                            top3 = city_brands['brand'].value_counts().head(3).index.tolist()
                            st.markdown(f"- {prod_type.upper()}: {', '.join(top3)}")
                        else:
                            st.markdown(f"- {prod_type.upper()}: 无数据")
                    st.markdown("**热门口味**")
                    city_flavors = filtered_flavors[filtered_flavors['shop_id'].isin(city_shop_ids)]
                    if not city_flavors.empty:
                        top5 = city_flavors['flavor'].value_counts().head(5).index.tolist()
                        st.markdown(f"- {', '.join(top5)}")
                    else:
                        st.info("无口味数据")
                    st.markdown("---")

# ---------- 6. 销售法规 ----------
with tabs[5]:
    st.subheader("法规解释准确性")
    if 'regulation_accuracy' in filtered_shops.columns:
        reg_counts = filtered_shops['regulation_accuracy'].value_counts().reset_index()
        fig = px.pie(reg_counts, values='count', names='regulation_accuracy', title="法规解释准确性分布")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("暂无法规准确性字段")

    # 其他重要信息总结：自动识别城区
    st.subheader("其他重要信息总结")
    
    # 定义浓缩文本及其匹配规则（关键词列表）
    # 每条浓缩文本对应一组关键词，只要补充信息包含任一关键词即匹配
    summary_config = [
        ("50ml 0mg 的卖的很好，都是额外添加尼古丁", ["50ml", "0mg", "额外添加尼古丁", "添加尼古丁"]),
        ("电子烟不需要证明，香烟需要烟草许可证。AFNOR：客户拿产品去化验，官方给一个证明文件", ["AFNOR", "烟草许可证", "电子烟不需要证明"]),
        ("不卖10ml的，认为利润太低且卖的油均是0mg，需要额外添加尼古丁", ["不卖10ml", "利润太低", "10ml", "0mg", "额外添加尼古丁"]),
        ("每家连锁店都在推自己的品牌，口感要细腻无残留", ["连锁店", "自己的品牌", "推自己的品牌", "细腻无残留"]),
        ("10ml份额下降严重", ["10ml份额", "份额下降"]),
        ("所调研的区比较下沉，销量却很好，谷歌评价很多，平均价格低蛮多", ["下沉", "谷歌评价", "平均价格低"]),
        ("莓果类口味在这边卖的好", ["莓果", "莓果类"]),
        ("连锁大店好像都没有返点激励", ["返点激励", "没有返点"]),
    ]
    
    # 获取所有有补充信息的店铺（城区 + 补充信息原始文本）
    notes_data = filtered_shops[['city', 'additional_notes']].dropna(subset=['additional_notes'])
    
    # 初始化：每条浓缩文本对应的城区集合
    from collections import defaultdict
    text_to_cities = defaultdict(set)
    
    # 对每条补充信息，判断它匹配哪些浓缩文本
    for _, row in notes_data.iterrows():
        city = row['city']
        note = str(row['additional_notes']).lower()
        for text, keywords in summary_config:
            # 如果任意关键词出现在补充信息中，则认为匹配
            if any(keyword.lower() in note for keyword in keywords):
                text_to_cities[text].add(city)
    
    # 显示结果
    for text, cities in text_to_cities.items():
        if cities:
            city_str = "、".join(sorted(cities))
            st.write(f"（{city_str}）{text}")
        else:
            # 如果没有匹配到任何城区，仍然显示文本（不标注）
            st.write(f"{text}")
    
    # 如果没有任何匹配，给出提示
    if not text_to_cities:
        st.info("暂无匹配的重要信息")

    st.subheader("销售限制要求")
    restrictions = filtered_shops['sales_restrictions'].dropna().unique()
    if len(restrictions) > 0:
        res_summary = []
        if any('tpd' in str(r).lower() for r in restrictions):
            res_summary.append("- 产品需符合 TPD 标准（10ml 及以下含尼古丁，50ml 及以上为 0mg 需额外添加）。")
        if any('20mg' in str(r) for r in restrictions):
            res_summary.append("- 尼古丁含量最高不超过 20mg/ml。")
        if any('18' in str(r) for r in restrictions):
            res_summary.append("- 购买者需年满 18 周岁。")
        if any('包装' in str(r) for r in restrictions):
            res_summary.append("- 对包装设计无特殊要求。")
        if any('文件' in str(r) or '申请' in str(r) for r in restrictions):
            res_summary.append("- 开店需向官方申请相关文件（如烟草许可证）。")
        if not res_summary:
            for res in restrictions:
                res_summary.append(f"- {res}")
        for res in res_summary:
            st.write(res)
    else:
        st.info("无销售限制记录")

    st.subheader("销售激励调研情况")
    incentives = filtered_shops['sales_incentive'].dropna()
    if not incentives.empty:
        incentive_counts = incentives.value_counts()
        fig = px.pie(values=incentive_counts.values, names=incentive_counts.index, title="销售激励分布")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("无销售激励数据")

# ---------- 7. 调研总结 ----------
with tabs[6]:
    st.subheader("调研结论摘要")
    total = len(filtered_shops)
    cities = filtered_shops['city'].nunique()
    top_brand_open = filtered_brands[filtered_brands['product_type']=='open']['brand'].value_counts().head(3).index.tolist() if not filtered_brands[filtered_brands['product_type']=='open'].empty else ['无']
    top_brand_disposable = filtered_brands[filtered_brands['product_type']=='disposable']['brand'].value_counts().head(3).index.tolist() if not filtered_brands[filtered_brands['product_type']=='disposable'].empty else ['无']
    top_brand_eliquid = filtered_brands[filtered_brands['product_type']=='eliquid']['brand'].value_counts().head(3).index.tolist() if not filtered_brands[filtered_brands['product_type']=='eliquid'].empty else ['无']
    top_flavors_all = filtered_flavors['flavor'].value_counts().head(5).index.tolist() if not filtered_flavors.empty else ['无']
    top_taste = filtered_shops['key_taste_point'].value_counts().head(1).index[0] if not filtered_shops['key_taste_point'].dropna().empty else '无'
    taste_good_summary = filtered_shops['key_taste_goodpoint'].value_counts().head(3).index.tolist() if not filtered_shops['key_taste_goodpoint'].dropna().empty else []
    price_summary = {}
    if not filtered_prices.empty:
        for size in sorted(filtered_prices['size_ml'].dropna().unique()):
            avg_price = filtered_prices[filtered_prices['size_ml'] == size]['price'].mean()
            if pd.notna(avg_price):
                price_summary[f"{size}ml"] = f"{avg_price:.2f}欧"

    advantages_text = filtered_shops['competitive_advantage'].dropna()
    all_adv_words = []
    for adv in advantages_text:
        parts = re.split(r'[;,，]+', str(adv))
        all_adv_words.extend([p.strip() for p in parts if p.strip()])
    top_advantages = pd.Series(all_adv_words).value_counts().head(3).index.tolist() if all_adv_words else []

    st.markdown(f"""
    - **调研覆盖**：共调研 {total} 家店铺，覆盖 {cities} 个城区。
    - **热门品牌（开放式）**：{', '.join(top_brand_open)}
    - **热门品牌（一次性）**：{', '.join(top_brand_disposable)}
    - **热门品牌（烟油）**：{', '.join(top_brand_eliquid)}
    - **热门口味**：{', '.join(top_flavors_all)}
    - **主要口感关注点**：{top_taste}
    - **最在意的口感优点**：{', '.join(taste_good_summary) if taste_good_summary else '无数据'}
    """)
    if price_summary:
        st.markdown("**常见规格均价总结**")
        for spec, price in price_summary.items():
            st.markdown(f"- {spec}：{price}")
    if top_advantages:
        st.markdown(f"**核心竞争优势**：{', '.join(top_advantages)}")

# ---------- 8. 行动建议 ----------
with tabs[7]:
    st.subheader("数据质量提示")
    missing_fields = []
    if filtered_shops['key_taste_goodpoint'].isna().sum() > len(filtered_shops) * 0.5:
        missing_fields.append("口感优点记录不足，建议业务多询问店员的具体评价。")
    if filtered_prices.empty:
        missing_fields.append("价格数据缺失较多，建议在调研时重点记录价格信息。")
    if filtered_flavors.empty:
        missing_fields.append("口味数据缺失较多，建议加强口味字段的记录。")
    if missing_fields:
        for m in missing_fields:
            st.write(f"- {m}")
    else:
        st.write("数据质量良好，继续保持！")

    st.subheader("业务改进建议")
    top_flavors = filtered_flavors['flavor'].value_counts().head(3).index.tolist() if not filtered_flavors.empty else []
    top_taste_advantage = filtered_shops['key_taste_goodpoint'].value_counts().head(1).index[0] if not filtered_shops['key_taste_goodpoint'].dropna().empty else None
    popular_sizes = filtered_prices['size_ml'].value_counts().head(2).index.tolist() if not filtered_prices.empty else []
    popular_nic = filtered_prices['nicotine_mg'].value_counts().head(2).index.tolist() if not filtered_prices.empty else []

    flavor_str = "、".join(top_flavors) if top_flavors else "主流口味"
    size_str = "、".join([f"{int(s)}ml" for s in popular_sizes]) if popular_sizes else "主流规格"
    nic_str = "、".join([f"{int(n)}mg" for n in popular_nic]) if popular_nic else "主流浓度"

    product_advice = f"- **产品研发**：重点关注{flavor_str}等热门口味，以及{top_taste_advantage or '核心口感'}等优点，开发符合{size_str}包装和{nic_str}尼古丁含量的产品。"
    st.markdown(product_advice)

    chain_incentive = filtered_shops[filtered_shops['is_chain'] == True]['sales_incentive'].value_counts()
    nonchain_incentive = filtered_shops[filtered_shops['is_chain'] == False]['sales_incentive'].value_counts()
    if not chain_incentive.empty and not nonchain_incentive.empty:
        chain_mode = chain_incentive.index[0] if len(chain_incentive) > 0 else "未知"
        nonchain_mode = nonchain_incentive.index[0] if len(nonchain_incentive) > 0 else "未知"
        sales_advice = f"- **销售策略**：连锁店偏好激励方式为“{chain_mode}”，独立店偏好“{nonchain_mode}”，可针对性制定方案；同时关注本地品牌合作与性价比产品。"
    else:
        sales_advice = "- **销售策略**：针对连锁店可提供返点激励，针对独立店可加强本地品牌合作；下沉市场可主打性价比产品。"
    st.markdown(sales_advice)

    reg_acc = filtered_shops['regulation_accuracy'].value_counts()
    if '准确' in reg_acc.index and reg_acc['准确'] / len(filtered_shops) > 0.8:
        reg_advice = "- **法规合规**：多数门店法规解释准确，但仍需确保产品符合TPD标准，避免灰色操作风险。"
    else:
        reg_advice = "- **法规合规**：确保产品符合TPD标准，规避合规风险。"
    st.markdown(reg_advice)

    gray_notes = filtered_shops['additional_notes'].dropna()
    if len(gray_notes) > 0:
        st.markdown("- **灰色操作提示**：部分门店存在额外添加尼古丁等操作，需关注合规风险，操作标准。")
