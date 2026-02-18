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
    page_icon="🛡️"
)

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        border: 1px solid #eee;
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# ⚙️ 2. 侧边栏配置
# ==========================================
with st.sidebar:
    st.title("🛡️ RiskShield Pro")
    st.caption("v6.6 机构级防崩版")
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
        index=0
    )
    st.divider()
    st.info("💡 提示：支持批量输入股票代码，以逗号、空格或换行分隔。")

client = genai.Client(api_key=api_key)

# ==========================================
# 🛠️ 3. 核心功能函数 (增强版)
# ==========================================

def analyze_stock(stock_name, model_name):
    """调用 Gemini 对单个股票进行全维度风控排查"""
    today = datetime.date.today().strftime("%Y年%m月%d日")
    
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
    不要输出 Markdown 标记，不要解释，仅输出 JSON 数组：
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
    """增强版清洗：自动寻找 JSON 数组的首尾，防止解析失败"""
    try:
        # 1. 尝试直接解析
        if not raw_text: return None
        clean = re.sub(r'```json\s*|\s*```', '', raw_text.strip())
        
        # 2. 如果包含了非 JSON 的废话，尝试提取 [] 之间的内容
        start_idx = clean.find('[')
        end_idx = clean.rfind(']')
        if start_idx != -1 and end_idx != -1:
            clean = clean[start_idx : end_idx+1]
            
        return json.loads(clean)
    except:
        return None

def convert_df_to_excel(df):
    """安全的 Excel 转换函数，防止崩溃"""
    try:
        import xlsxwriter # 延迟导入，检测是否存在
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='风控报告')
            workbook = writer.book
            worksheet = writer.sheets['风控报告']
            
            # 简单美化
            header_fmt = workbook.add_format({'bold': True, 'fg_color': '#4285F4', 'font_color': 'white', 'border': 1})
            
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_fmt)
            
            worksheet.set_column('A:A', 15) # 股票名
            worksheet.set_column('C:C', 40) # 综述
            worksheet.set_column('D:K', 25) # 详情列

        return output.getvalue()
    except ImportError:
        st.error("⚠️ 系统缺少 `xlsxwriter` 库，无法生成 Excel。请在 requirements.txt 中添加 `xlsxwriter`。")
        return None
    except Exception as e:
        st.error(f"⚠️ Excel 生成失败: {str(e)}")
        return None

# ==========================================
# 🖥️ 4. 主界面交互
# ==========================================
st.title("⚖️ 股票合规排雷预警终端 (Multi-Stock)")
st.caption(f"基准排查时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")

with st.container(border=True):
    col1, col2 = st.columns([5, 1])
    with col1:
        raw_input = st.text_area(
            "请输入股票名称/代码 (支持批量)", 
            height=68, 
            placeholder="例如：生益电子, 嘉美包装, 600519 (可用逗号或回车分隔)"
        )
    with col2:
        st.write("") 
        st.write("")
        run_btn = st.button("🚀 启动深度扫描", use_container_width=True, type="primary")

# ==========================================
# 🧠 5. 执行逻辑
# ==========================================
if run_btn and raw_input:
    stock_list = [s.strip() for s in re.split(r'[,\s\n]+', raw_input) if s.strip()]
    
    if not stock_list:
        st.warning("⚠️ 请输入有效的股票代码")
        st.stop()

    results_data = []      
    raw_results = []       
    
    progress_bar = st.progress(0)
    status_text = st.empty()

    # --- 循环处理 ---
    for i, stock in enumerate(stock_list):
        status_text.text(f"🔍 ({i+1}/{len(stock_list)}) 正在穿透核查：{stock} ...")
        
        raw_resp = analyze_stock(stock, model_choice)
        parsed_data = clean_json_response(raw_resp)
        
        if parsed_data and isinstance(parsed_data, list):
            item = parsed_data[0]
            details = item.get("details", {})
            scores = item.get("scores", {})
            
            # 构建表格数据
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
            st.error(f"❌ {stock} 数据解析失败 (AI 可能未返回标准 JSON)，请重试。")
            
        progress_bar.progress((i + 1) / len(stock_list))

    status_text.text("✅ 核查完成！")
    
    # ==========================================
    # 📊 6. 结果展示
    # ==========================================
    if results_data:
        st.divider()
        df = pd.DataFrame(results_data)
        
        # 6.1 下载按钮 (带安全检查)
        # 只有在数据生成完毕，且 DataFrame 存在时，才尝试准备 Excel 数据
        # 这样不会在没点击时就崩溃
        excel_data = convert_df_to_excel(df)
        
        col_dl, col_blank = st.columns([1, 4])
        with col_dl:
            if excel_data:
                st.download_button(
                    label="📥 下载专业风控报告 (.xlsx)",
                    data=excel_data,
                    file_name=f"RiskShield_{datetime.date.today()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            else:
                st.warning("Excel 生成服务不可用 (缺少依赖)")

        # 6.2 概览表
        st.subheader("📋 风险概览")
        st.dataframe(
            df[['股票名称', '综合风险', '风险综述']], 
            use_container_width=True,
            hide_index=True
        )

        # 6.3 详情卡片
        st.divider()
        st.subheader("🔍 深度详情")
        for idx, item in enumerate(raw_results):
            with st.expander(f"📌 {item.get('stock_name')} - {item.get('status')}", expanded=(idx==0)):
                scores = item.get("scores", {})
                details = item.get("details", {})
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("减持", scores.get('reduction',0))
                c2.metric("立案", scores.get('fraud',0))
                c3.metric("退市", scores.get('delisting',0))
                c4.metric("监控", scores.get('monitoring',0))
                
                t1, t2 = st.tabs(["核心详情", "财务与资金"])
                with t1:
                    st.write(f"**减持**：{details.get('reduction')}")
                    st.write(f"**立案**：{details.get('fraud')}")
                    st.write(f"**退市**：{details.get('delisting')}")
                    st.write(f"**监控**：{details.get('monitoring')}")
                with t2:
                    st.write(f"**质押**：{details.get('pledge')}")
                    st.write(f"**解禁**：{details.get('unlocking')}")
                    st.write(f"**商誉**：{details.get('goodwill')}")
                    st.write(f"**财务**：{details.get('abnormal_finance')}")
