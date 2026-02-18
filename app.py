import streamlit as st
import datetime
import json
import re
from google import genai
from google.genai import types

# ==========================================
# 🎨 1. V6.0 仪表盘样式配置
# ==========================================
st.set_page_config(
    page_title="RiskShield | 机构风控终端",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 注入自定义 CSS：让指标卡更立体，背景更专业
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border: 1px solid #e0e0e0;
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# ⚙️ 2. 侧边栏配置 (Sidebar)
# ==========================================
with st.sidebar:
    st.title("🛡️ RiskShield Pro")
    st.caption("机构级股票避雷终端 (Google官方内核)")
    st.divider()
    
    st.subheader("🔑 系统鉴权")
    # 安全加载 Key
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        st.success("✅ 官方 API Key 已连接")
    except:
        st.error("❌ 未检测到密钥！请在 Secrets 中配置 GEMINI_API_KEY。")
        st.stop()
        
    st.subheader("🧠 模型配置")
    # 允许切换模型
    model_choice = st.selectbox(
        "核心分析引擎", 
        ["gemini-2.0-flash", "gemini-1.5-flash"], 
        index=0,
        help="2.0 支持实时搜索，1.5 仅支持逻辑分析"
    )
    
    st.divider()
    st.info("数据源：Google Search 原生实时索引")

# 初始化客户端
client = genai.Client(api_key=api_key)

# ==========================================
# 🖥️ 3. 主界面交互 (搜索区)
# ==========================================
st.title("⚖️ 股票合规排雷预警终端")
current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
st.caption(f"基准排查时间：{current_time}")

# 使用容器包裹输入框，增加仪式感
with st.container(border=True):
    col_input, col_btn = st.columns([4, 1])
    with col_input:
        stock_name = st.text_input("请输入标的名称/代码", value="生益电子", placeholder="例如：贵州茅台 / 600519", label_visibility="collapsed")
    with col_btn:
        run_btn = st.button("🚀 启动深度扫描", use_container_width=True)

# ==========================================
# 🧠 4. 核心逻辑 (点击运行后)
# ==========================================
if run_btn:
    today = datetime.date.today().strftime("%Y年%m月%d日")
    
    # ---------------------------------------------------------
    # 📝 机构级 Prompt (融合了你的详细指令 + 仪表盘评分逻辑)
    # ---------------------------------------------------------
    prompt = f"""
    今天是 {today}。
    你是一名机构交易员的合规风控助手。请利用 Google Search 工具，查询股票【{stock_name}】的最新实时数据。
    
    请严格针对以下 4 个核心维度进行事实核查，并评估风险分数（0=安全，100=极度高危）。
    
    1. 【reduction】(近半年减持)：
       - 搜索指令：搜索“{stock_name} 减持公告 股东减持计划 2025 2026”。
       - 核心：近半年是否有大股东减持？是否有未执行完毕的减持计划？
       - 输出要求：**必须写出具体公告日期**。
       
    2. 【fraud】(财务造假/立案)：
       - 搜索指令：搜索“{stock_name} 证监会 立案 处罚 财务造假 警示函 违规担保”。
       - 核心：近3年是否有行政处罚或立案调查？
       
    3. 【delisting】(退市风险 - 严格对照新规红线)：
       - 搜索指令：搜索“{stock_name} 股价 市值 营收 净利润 净资产 审计意见 ST”。
       - 核查红线：股价<1元？市值<5亿？营收<3亿且亏损？净资产为负？审计意见非标？
       
    4. 【monitoring】(监管监控 - 严重异常波动)：
       - 搜索指令：搜索“{stock_name} 严重异常波动 重点监控 异动公告 停牌核查 10天100%”。
       - 核查红线：是否触发10天100%或30天200%偏离值？是否被列入重点监控名单？

    ━━━━━━━━━━━━━━━━━━━━━━━━━━
    ⬇️ 输出格式要求 (严格遵守) ⬇️
    ━━━━━━━━━━━━━━━━━━━━━━━━━━
    请仅输出一个标准的 JSON 数组，不要包含 ```json 或 Markdown 标记。格式如下：
    [
      {{
        "status": "高危/关注/低风险",
        "summary": "一句简短的交易员综述（例如：存在立案风险，建议规避）",
        "scores": {{
            "reduction": 0-100 (减持风险分),
            "fraud": 0-100 (造假/立案风险分),
            "delisting": 0-100 (退市风险分),
            "monitoring": 0-100 (监管监控风险分)
        }},
        "details": {{
            "reduction": "详细的核查结果，包含日期...",
            "fraud": "详细的核查结果...",
            "delisting": "详细的核查结果...",
            "monitoring": "详细的核查结果..."
        }}
      }}
    ]
    """

    # ==========================================
    # 📡 5. 调用 API & 渲染仪表盘
    # ==========================================
    st.info(f"🔍 正在穿透全网监管公告与财经新闻，深度核查【{stock_name}】...")
    
    try:
        # 智能工具配置：只有 2.0 模型才启用搜索
        my_tools = [types.Tool(google_search=types.GoogleSearchRetrieval())] if "2.0" in model_choice else None
        
        response = client.models.generate_content(
            model=model_choice,
            contents=prompt,
            config=types.GenerateContentConfig(tools=my_tools)
        )

        # --- JSON 清洗与解析 (防止 AI 输出 Markdown 包裹) ---
        raw_text = response.text.strip()
        # 使用正则去除可能存在的 ```json ... ```
        clean_json = re.sub(r'```json\s*|\s*```', '', raw_text)
        
        data_list = json.loads(clean_json)
        if isinstance(data_list, list) and len(data_list) > 0:
            data = data_list[0]
            scores = data.get("scores", {"reduction":0, "fraud":0, "delisting":0, "monitoring":0})
            details = data.get("details", {})
            
            # ------------------------------------------------
            # 📊 第一行：风险仪表盘 (Metrics)
            # ------------------------------------------------
            st.markdown("### 🚦 风险雷达")
            m1, m2, m3, m4 = st.columns(4)
            
            m1.metric("减持风险", f"{scores['reduction']}", delta="存在减持" if scores['reduction']>0 else "安全", delta_color="inverse")
            m2.metric("合规立案", f"{scores['fraud']}", delta="严重违规" if scores['fraud']>50 else "暂无立案", delta_color="inverse")
            m3.metric("退市红线", f"{scores['delisting']}", delta="触及红线" if scores['delisting']>80 else "财务安全", delta_color="inverse")
            m4.metric("监管监控", f"{scores['monitoring']}", delta="重点监控" if scores['monitoring']>60 else "交易正常", delta_color="inverse")

            # ------------------------------------------------
            # 📢 第二行：综合结论 Banner
            # ------------------------------------------------
            status = data.get('status', '未知')
            summary = data.get('summary', '')
            
            if status == "高危":
                st.error(f"🚫 **综合评估：{status}** | {summary}", icon="🚨")
            elif status == "关注":
                st.warning(f"⚠️ **综合评估：{status}** | {summary}", icon="⚠️")
            else:
                st.success(f"✅ **综合评估：{status}** | {summary}", icon="🛡️")

            # ------------------------------------------------
            # 📑 第三行：深度详情 (Tabs 布局)
            # ------------------------------------------------
            tab_analysis, tab_sources = st.tabs(["📝 维度详情 (Deep Dive)", "🌐 原始来源 (Sources)"])
            
            with tab_analysis:
                c1, c2 = st.columns(2)
                with c1:
                    with st.expander("📉 减持与抛压 (Reduction)", expanded=True):
                        st.write(details.get('reduction', '无数据'))
                    with st.expander("⚖️ 立案与造假 (Fraud)", expanded=True):
                        st.write(details.get('fraud', '无数据'))
                with c2:
                    with st.expander("❌ 退市硬指标 (Delisting)", expanded=True):
                        st.write(details.get('delisting', '无数据'))
                    with st.expander("👁️ 异动监控 (Monitoring)", expanded=True):
                        st.write(details.get('monitoring', '无数据'))

            with tab_sources:
                if response.candidates and response.candidates[0].grounding_metadata:
                    sources_html = response.candidates[0].grounding_metadata.search_entry_point.rendered_content
                    st.write(sources_html, unsafe_allow_html=True)
                else:
                    st.caption("本次分析主要基于模型内建知识库，未触发大量外部链接引用。")
        else:
            st.error("解析数据失败：AI 返回格式不符合预期。")
            st.write(raw_text)

    except Exception as e:
        st.error(f"运行中断: {str(e)}")
        if "429" in str(e):
            st.warning("提示：触发频率限制，请稍候再试。")
