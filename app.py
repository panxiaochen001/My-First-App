import streamlit as st
import datetime
import json
import re
import pandas as pd
import io
from google import genai
from google.genai import types

# ==========================================
# 🎨 1. 页面样式配置
# ==========================================
st.set_page_config(
    page_title="RiskShield Pro | 机构风控终端",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🛡️"
)

# 注入自定义 CSS：优化表格和指标卡视觉
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    /* 指标卡样式 */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        border: 1px solid #eee;
    }
    /* 风险等级标签颜色 */
    .risk-high { color: #d32f2f; font-weight: bold; }
    .risk-medium { color: #f57c00; font-weight: bold; }
    .risk-safe { color: #388e3c; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# ⚙️ 2. 侧边栏配置
# ==========================================
with st.sidebar:
    st.title("🛡️ RiskShield Pro")
    st.caption("v6.5 机构级多股排雷版")
    st.divider()
    
    st.subheader("🔑 系统鉴权")
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        st.success("✅ 官方 API Key 已连接")
    except:
        st.error("❌ 未配置 GEMINI_API_KEY！")
        st.stop()
        
    st.subheader("🧠 模型配置")
    model_choice = st.selectbox(
        "核心分析引擎", 
        ["gemini-2.0-flash", "gemini-1.5-flash"], 
        index=0,
        help="2.0 支持实时搜索，速度更快；1.5 逻辑能力强。"
    )
    
    st.divider()
    st.info("💡 提示：支持批量输入股票代码，以逗号、空格或换行分隔。")

# 初始化客户端
client = genai.Client(api_key=api_key)

# ==========================================
# 🛠️ 3. 核心功能函数
# ==========================================

def analyze_stock(stock_name, model_name):
    """调用 Gemini 对单个股票进行全维度风控排查"""
    today = datetime.date.today().strftime("%Y年%m月%d日")
    
    # --- 机构级 8 维 Prompt ---
    prompt = f"""
    今天是 {today}。你是一名专业的机构交易员风控助手。
    请利用 Google Search，查询股票【{stock_name}】的最新数据，进行 **8个维度** 的深度排雷。

    请严格针对以下维度核查，并评估风险分 (0=安全, 100=极度高危)：

    1. 【reduction】(减持): 近半年是否有大股东减持或未完成计划？(必须写具体日期)
    2. 【fraud】(立案/造假): 近3年是否有证监会立案、处罚、警示函？
    3. 【delisting】(退市风险): 股价<1元？市值<5亿？营收<3亿且亏损？净资产为负？审计非标？
    4. 【monitoring】(监管监控): 是否触发10天100%/30天200%异动？是否重点监控？
    5. 【pledge】(股权质押): 大股东质押率是否>80%？是否有平仓/补充质押公告？
    6. 【unlocking】(解禁抛压): 未来30天是否有>5%的大额解禁？定增是否大幅浮盈？
    7. 【goodwill】(商誉雷): 商誉/净资产是否>30%？是否有业绩承诺期满减值风险？
    8. 【abnormal_finance】(财务异动): 是否存贷双高？有利润无现金流？多年不分红？

    ━━━━━━━━━━━━━━━━━━━━━━━━━━
    ⬇️ 输出格式要求 (纯 JSON 数组) ⬇️
    ━━━━━━━━━━━━━━━━━━━━━━━━━━
    不要输出 Markdown 标记，仅输出 JSON：
    [
      {{
        "stock_name": "{stock_name}",
        "status": "高危/关注/低风险",
        "summary": "简短综述（如：存在高比例质押及立案风险，建议规避）",
        "scores": {{
            "reduction": 0, "fraud": 0, "delisting": 0, "monitoring": 0,
            "pledge": 0, "unlocking": 0, "goodwill": 0, "abnormal_finance": 0
        }},
        "details": {{
            "reduction": "详情...", "fraud": "详情...", "delisting": "详情...", "monitoring": "详情...",
            "pledge": "详情...", "unlocking": "详情...", "goodwill": "详情...", "abnormal_finance": "详情..."
        }}
      }}
    ]
    """
    
    try:
        tools = [types.Tool(google_search=types.GoogleSearchRetrieval())] if "2.0" in model_name else None
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(tools=tools)
        )
        return response.text
    except Exception as e:
        return f"Error: {str(e)}"

def clean_json_response(raw_text):
    """清洗 AI 返回的 JSON 文本"""
    try:
        clean = re.sub(r'```json\s*|\s*```', '', raw_text.strip())
        return json.loads(clean)
    except:
        return None

def convert_df_to_excel(df):
    """将 DataFrame 转换为美观的 Excel 字节流"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='风控报告')
        workbook = writer.book
        worksheet = writer.sheets['风控报告']
        
        # 样式格式
        header_fmt = workbook.add_format({'bold': True, 'fg_color': '#4285F4', 'font_color': 'white', 'border': 1})
        cell_fmt = workbook.add_format({'border': 1, 'text_wrap': True, 'valign': 'top'})
        high_risk_fmt = workbook.add_format({'bg_color': '#FFCDD2', 'border': 1, 'text_wrap': True}) # 红底
        
        # 应用表头
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_fmt)
        
        # 设置列宽
        worksheet.set_column('A:A', 15) # 股票名
        worksheet.set_column('B:B', 10) # 状态
        worksheet.set_column('C:C', 40) # 综述
        worksheet.set_column('D:K', 30) # 详情列
        
        # 写入数据并标记高危
        for row_idx, row in df.iterrows():
            row_fmt = cell_fmt
            if row['综合风险'] == '高危':
                row_fmt = high_risk_fmt
            worksheet.write_row(row_idx + 1, 0, row, row_fmt)
            
    return output.getvalue()

# ==========================================
# 🖥️ 4. 主界面交互
# ==========================================
st.title("⚖️ 股票合规排雷预警终端 (Multi-Stock)")
st.caption(f"基准排查时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")

# 输入区域
with st.container(border=True):
    col1, col2 = st.columns([5, 1])
    with col1:
        raw_input = st.text_area(
            "请输入股票名称/代码 (支持批量)", 
            height=68, 
            placeholder="例如：贵州茅台, 600519, 宁德时代 (可用逗号或回车分隔)",
            help="输入多个股票可生成对比报表"
        )
    with col2:
        st.write("") # Spacer
        st.write("")
        run_btn = st.button("🚀 启动深度扫描", use_container_width=True, type="primary")

# ==========================================
# 🧠 5. 执行逻辑
# ==========================================
if run_btn and raw_input:
    # 1. 解析股票列表
    stock_list = [s.strip() for s in re.split(r'[,\s\n]+', raw_input) if s.strip()]
    
    if not stock_list:
        st.warning("⚠️ 请至少输入一个有效的股票名称或代码。")
        st.stop()

    results_data = []      # 用于存放处理后的数据，做表格展示
    raw_results = []       # 存放原始 JSON，用于详情展示
    
    progress_bar = st.progress(0)
    status_text = st.empty()

    # 2. 循环处理
    for i, stock in enumerate(stock_list):
        status_text.text(f"🔍 ({i+1}/{len(stock_list)}) 正在穿透核查：{stock} ...")
        
        # 调用 AI
        raw_resp = analyze_stock(stock, model_choice)
        parsed_data = clean_json_response(raw_resp)
        
        if parsed_data and isinstance(parsed_data, list):
            item = parsed_data[0]
            scores = item.get("scores", {})
            details = item.get("details", {})
            
            # 存入列表用于 Excel 和 表格
            row = {
                "股票名称": item.get("stock_name", stock),
                "综合风险": item.get("status", "未知"),
                "风险综述": item.get("summary", ""),
                "减持风险": details.get("reduction", ""),
                "立案造假": details.get("fraud", ""),
                "退市红线": details.get("delisting", ""),
                "异动监控": details.get("monitoring", ""),
                "股权质押": details.get("pledge", ""),
                "解禁抛压": details.get("unlocking", ""),
                "商誉雷": details.get("goodwill", ""),
                "财务异动": details.get("abnormal_finance", "")
            }
            results_data.append(row)
            raw_results.append(item)
        else:
            st.error(f"❌ {stock} 核查失败，API 返回异常。")
            
        progress_bar.progress((i + 1) / len(stock_list))

    status_text.text("✅ 所有标的核查完成！")
    
    # ==========================================
    # 📊 6. 结果展示 (表格 + Excel 下载)
    # ==========================================
    if results_data:
        st.divider()
        df = pd.DataFrame(results_data)
        
        # 6.1 功能区：下载按钮
        col_dl, col_blank = st.columns([1, 4])
        with col_dl:
            excel_data = convert_df_to_excel(df)
            st.download_button(
                label="📥 下载专业风控报告 (.xlsx)",
                data=excel_data,
                file_name=f"RiskShield_Report_{datetime.date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        # 6.2 宏观概览 (Table)
        st.subheader("📋 风险概览表")
        
        # 使用颜色高亮“综合风险”列
        def color_risk(val):
            color = 'red' if val == '高危' else 'orange' if val == '关注' else 'green'
            return f'color: {color}; font-weight: bold'
            
        st.dataframe(
            df[['股票名称', '综合风险', '风险综述']], 
            use_container_width=True,
            hide_index=True,
            column_config={
                "综合风险": st.column_config.TextColumn(help="基于8大维度综合判定"),
            }
        )

        # 6.3 详细卡片视图 (逐个展示)
        st.divider()
        st.subheader("🔍 深度排查详情")
        
        for idx, item in enumerate(raw_results):
            with st.expander(f"📌 {item.get('stock_name')} - 风险等级：{item.get('status')}", expanded=(idx==0)):
                scores = item.get("scores", {})
                details = item.get("details", {})
                
                # 仪表盘第一行 (原有4维)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("减持风险", scores.get('reduction',0), delta_color="inverse", help="近半年股东减持情况")
                c2.metric("立案造假", scores.get('fraud',0), delta_color="inverse", help="证监会处罚与立案")
                c3.metric("退市风险", scores.get('delisting',0), delta_color="inverse", help="触及财务或交易退市红线")
                c4.metric("异动监控", scores.get('monitoring',0), delta_color="inverse", help="严重异动与重点监控")
                
                # 仪表盘第二行 (新增4维)
                c5, c6, c7, c8 = st.columns(4)
                c5.metric("股权质押", scores.get('pledge',0), delta_color="inverse", help="大股东质押率警戒线")
                c6.metric("解禁抛压", scores.get('unlocking',0), delta_color="inverse", help="大额定增解禁压力")
                c7.metric("商誉暴雷", scores.get('goodwill',0), delta_color="inverse", help="高商誉与业绩承诺")
                c8.metric("财务异动", scores.get('abnormal_finance',0), delta_color="inverse", help="存贷双高/铁公鸡")

                st.markdown("---")
                
                # 详情文本展示
                t1, t2 = st.tabs(["🔴 核心硬伤 (Hard Risks)", "🟠 资金与财务 (Soft Risks)"])
                with t1:
                    st.markdown(f"**📉 减持详情**：\n{details.get('reduction')}")
                    st.markdown(f"**⚖️ 立案详情**：\n{details.get('fraud')}")
                    st.markdown(f"**❌ 退市详情**：\n{details.get('delisting')}")
                    st.markdown(f"**👁️ 监控详情**：\n{details.get('monitoring')}")
                with t2:
                    st.markdown(f"**🏦 质押详情**：\n{details.get('pledge')}")
                    st.markdown(f"**🔓 解禁详情**：\n{details.get('unlocking')}")
                    st.markdown(f"**💣 商誉详情**：\n{details.get('goodwill')}")
                    st.markdown(f"**💸 财务详情**：\n{details.get('abnormal_finance')}")
