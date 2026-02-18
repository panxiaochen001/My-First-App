import streamlit as st
import datetime
import json
import re
import pandas as pd
import io
from google import genai
from google.genai import types

# ==========================================
# 🎨 1. 页面配置与样式
# ==========================================
st.set_page_config(
    page_title="RiskShield Pro | 机构风控终端",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="⚖️"
)

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    /* 卡片样式优化 */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        padding: 10px;
        border-radius: 8px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        border: 1px solid #e0e0e0;
    }
    /* 风险标签颜色 */
    .risk-high { color: #d32f2f; font-weight: 800; }
    .risk-warn { color: #f57c00; font-weight: 800; }
    .risk-safe { color: #388e3c; font-weight: 800; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# ⚙️ 2. 侧边栏：配置与标准公示
# ==========================================
with st.sidebar:
    st.title("🛡️ RiskShield Pro")
    st.caption("v7.0 机构全维度版")
    st.divider()
    
    # --- 鉴权 ---
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        st.success("✅ 官方 API Key 已连接")
    except:
        st.error("❌ 未配置 Secrets: GEMINI_API_KEY")
        st.stop()
        
    model_choice = st.selectbox("核心引擎", ["gemini-2.0-flash", "gemini-1.5-flash"], index=0)
    
    st.divider()
    
    # --- 🌟 新增：风险评判标准公示 ---
    with st.expander("📊 综合风险评判标准 (硬性)", expanded=True):
        st.markdown("""
        **🚨 高危 (High Risk)**
        * **立案/造假** 得分 > 0
        * **退市风险** 得分 > 80
        * **股权质押** 得分 > 80 (爆仓线)
        
        **⚠️ 关注 (Attention)**
        * **任意单项得分** > 60
        * **减持** 存在未执行计划
        * **监管监控** 有异动通报
        
        **🟢 低风险 (Safe)**
        * 所有维度得分 < 50
        * 无违规记录
        """)

client = genai.Client(api_key=api_key)

# ==========================================
# 🛠️ 3. 核心逻辑函数
# ==========================================

def calculate_overall_risk(scores):
    """
    【本地硬逻辑】强制计算综合风险，不依赖 AI 的主观判断
    这样可以保证标准的统一性。
    """
    # 1. 提取分数 (默认为0)
    s_fraud = scores.get('fraud', 0)
    s_delisting = scores.get('delisting', 0)
    s_pledge = scores.get('pledge', 0)
    
    max_score = max(scores.values()) if scores else 0
    
    # 2. 判定逻辑
    if s_fraud > 0 or s_delisting >= 80 or s_pledge >= 90:
        return "高危", "🚨"
    elif max_score >= 60:
        return "关注", "⚠️"
    else:
        return "低风险", "🟢"

def analyze_stock(stock_name, model_name):
    today = datetime.date.today().strftime("%Y年%m月%d日")
    
    # Prompt 重点：强调所有8个维度的 JSON 输出
    prompt = f"""
    今天是 {today}。请作为机构风控交易员，查询股票【{stock_name}】的实时数据。
    请对以下 **8个维度** 进行核查，并打分 (0=安全, 100=极度高危)。
    
    1. 【reduction】(减持): 近半年是否有减持或未完成计划？
    2. 【fraud】(立案): 近3年是否有立案、处罚、警示函？(有则直接100分)
    3. 【delisting】(退市): 股价<1元、市值<5亿、净资产负、营收<3亿且亏损？
    4. 【monitoring】(监控): 10天100%/30天200%异动、重点监控名单？
    5. 【pledge】(质押): 大股东质押率>80%？整体质押率>50%？
    6. 【unlocking】(解禁): 未来30天有>5%解禁？定增高浮盈？
    7. 【goodwill】(商誉): 商誉占净资产>30%？
    8. 【abnormal_finance】(财务): 存贷双高？有利润无现金流？

    ⬇️ 请严格仅输出以下 JSON 数组格式 (不要 Markdown):
    [
      {{
        "stock_name": "{stock_name}",
        "summary": "简短的一句话综述",
        "scores": {{
            "reduction": 0, "fraud": 0, "delisting": 0, "monitoring": 0,
            "pledge": 0, "unlocking": 0, "goodwill": 0, "abnormal_finance": 0
        }},
        "details": {{
            "reduction": "具体日期和内容...", "fraud": "内容...", "delisting": "内容...", "monitoring": "内容...",
            "pledge": "质押比例...", "unlocking": "解禁日期...", "goodwill": "内容...", "abnormal_finance": "内容..."
        }}
      }}
    ]
    """
    try:
        tools = [types.Tool(google_search=types.GoogleSearchRetrieval())] if "2.0" in model_name else None
        response = client.models.generate_content(
            model=model_name, contents=prompt, config=types.GenerateContentConfig(tools=tools)
        )
        return response.text
    except Exception as e:
        return None

def clean_json_response(raw_text):
    if not raw_text: return None
    try:
        clean = re.sub(r'```json\s*|\s*```', '', raw_text.strip())
        start = clean.find('[')
        end = clean.rfind(']')
        if start != -1 and end != -1:
            return json.loads(clean[start:end+1])
        return json.loads(clean)
    except:
        return None

def get_excel_download_link(df):
    """
    安全的 Excel 生成器
    修复了您截图中的 ModuleNotFoundError
    """
    try:
        import xlsxwriter  # 尝试导入
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='风控报告')
            workbook = writer.book
            worksheet = writer.sheets['风控报告']
            
            # 格式
            header_fmt = workbook.add_format({'bold': True, 'fg_color': '#4285F4', 'font_color': 'white', 'border': 1})
            warn_fmt = workbook.add_format({'bg_color': '#FFF3E0', 'border': 1})
            danger_fmt = workbook.add_format({'bg_color': '#FFEBEE', 'border': 1})
            
            for col, val in enumerate(df.columns):
                worksheet.write(0, col, val, header_fmt)
            
            # 根据风险等级给整行上色
            status_col_idx = 1 # "综合风险"列
            for row_idx, row_data in df.iterrows():
                row_fmt = None
                if row_data['综合风险'] == '高危':
                    row_fmt = danger_fmt
                elif row_data['综合风险'] == '关注':
                    row_fmt = warn_fmt
                
                if row_fmt:
                    worksheet.write_row(row_idx+1, 0, row_data, row_fmt)
                else:
                    worksheet.write_row(row_idx+1, 0, row_data)
                    
            worksheet.set_column('A:A', 15)
            worksheet.set_column('C:K', 25)

        return output.getvalue()
    except ImportError:
        return "MISSING_LIB"
    except Exception as e:
        return None

# ==========================================
# 🖥️ 4. 主界面
# ==========================================
st.title("⚖️ 股票合规排雷预警终端")
st.caption(f"基准排查时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")

with st.container(border=True):
    col1, col2 = st.columns([5, 1])
    with col1:
        raw_input = st.text_area("输入股票代码 (批量)", height=68, placeholder="例如：生益电子, 600519")
    with col2:
        st.write("")
        st.write("")
        run_btn = st.button("🚀 启动扫描", use_container_width=True, type="primary")

# ==========================================
# 🧠 5. 执行与展示
# ==========================================
if run_btn and raw_input:
    stock_list = [s.strip() for s in re.split(r'[,\s\n]+', raw_input) if s.strip()]
    
    results_data = []
    raw_results = []
    
    prog_bar = st.progress(0)
    status_text = st.empty()

    for i, stock in enumerate(stock_list):
        status_text.text(f"🔍 ({i+1}/{len(stock_list)}) 正在穿透核查：{stock}...")
        
        raw_resp = analyze_stock(stock, model_choice)
        parsed = clean_json_response(raw_resp)
        
        if parsed and isinstance(parsed, list):
            item = parsed[0]
            scores = item.get("scores", {})
            details = item.get("details", {})
            
            # --- 🔥 关键：使用本地 Python 逻辑覆盖 AI 的风险判定 ---
            risk_label, risk_icon = calculate_overall_risk(scores)
            
            # 存表数据
            row = {
                "股票名称": item.get("stock_name", stock),
                "综合风险": risk_label,
                "风险综述": item.get("summary", ""),
                "立案造假": details.get("fraud"),
                "退市红线": details.get("delisting"),
                "股权质押": details.get("pledge"),  # 新增
                "商誉雷": details.get("goodwill"),   # 新增
                "减持风险": details.get("reduction"),
                "异动监控": details.get("monitoring"),
                "解禁抛压": details.get("unlocking"), # 新增
                "财务异动": details.get("abnormal_finance") # 新增
            }
            results_data.append(row)
            
            # 存原始数据用于卡片展示
            # 强制把本地计算的风险塞回去，保证展示一致
            item['status_label'] = risk_label 
            item['status_icon'] = risk_icon
            raw_results.append(item)
        else:
            st.error(f"{stock} 数据获取失败")
            
        prog_bar.progress((i + 1) / len(stock_list))
    
    status_text.text("✅ 完成")

    # ==========================================
    # 📊 6. 结果渲染 (双行8列布局)
    # ==========================================
    if results_data:
        st.divider()
        df = pd.DataFrame(results_data)
        
        # --- 下载区 ---
        excel_bytes = get_excel_download_link(df)
        if excel_bytes == "MISSING_LIB":
            st.warning("⚠️ 无法生成 Excel：环境中缺少 `xlsxwriter` 库。但由于程序已做防崩处理，您可以继续查看下方网页结果。")
        elif excel_bytes:
            st.download_button("📥 下载详细排雷报告 (.xlsx)", excel_bytes, f"Report_{datetime.date.today()}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        # --- 概览表 ---
        st.subheader("📋 风险清单")
        st.dataframe(df[['股票名称', '综合风险', '风险综述']], use_container_width=True)

        # --- 深度详情 (关键修改：显示8个卡片) ---
        st.divider()
        st.subheader("🔍 深度全维透视")
        
        for idx, item in enumerate(raw_results):
            # 标题带颜色
            risk_color = "red" if item['status_label']=="高危" else "orange" if item['status_label']=="关注" else "green"
            
            with st.expander(f"📌 {item.get('stock_name')} | 综合评级：:{risk_color}[{item['status_label']}]", expanded=(idx==0)):
                s = item.get("scores", {})
                d = item.get("details", {})
                
                # 🔥 第一行：硬伤类 (4个)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("立案/造假", s.get('fraud',0), help="核心红线")
                c2.metric("退市风险", s.get('delisting',0), help="财务/交易退市")
                c3.metric("股权质押", s.get('pledge',0), help=">80%为高危")
                c4.metric("商誉/减值", s.get('goodwill',0), help="商誉占比过高")
                
                # 🔥 第二行：资金与交易类 (4个)
                c5, c6, c7, c8 = st.columns(4)
                c5.metric("减持计划", s.get('reduction',0))
                c6.metric("异动监控", s.get('monitoring',0))
                c7.metric("解禁抛压", s.get('unlocking',0))
                c8.metric("财务异动", s.get('abnormal_finance',0))
                
                st.markdown("---")
                # 详情文本
                t1, t2 = st.tabs(["🔴 核心风险详情", "🟠 资金面详情"])
                with t1:
                    st.write(f"**👮 立案**：{d.get('fraud')}")
                    st.write(f"**❌ 退市**：{d.get('delisting')}")
                    st.write(f"**🏦 质押**：{d.get('pledge')}")
                    st.write(f"**💣 商誉**：{d.get('goodwill')}")
                with t2:
                    st.write(f"**📉 减持**：{d.get('reduction')}")
                    st.write(f"**👁️ 监控**：{d.get('monitoring')}")
                    st.write(f"**🔓 解禁**：{d.get('unlocking')}")
                    st.write(f"**💸 财务**：{d.get('abnormal_finance')}")
