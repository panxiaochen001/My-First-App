import streamlit as st
import datetime
from google import genai
from google.genai import types

# ==========================================
# ⚡️ 1. 页面配置
# ==========================================
st.set_page_config(page_title="机构级避雷 Agent (官方版)", layout="wide")

st.title("🛡️ 机构级股票避雷 Agent (Google官方内核)")
st.caption("内核：Gemini 2.0 Flash | 数据源：Google Search 原生实时索引")

# ==========================================
# 🔐 2. 安全加载官方 Key
# ==========================================
try:
    # 必须是 AIza 开头的官方 Key
    api_key = st.secrets["GEMINI_API_KEY"]
except:
    st.error("❌ 未检测到密钥！请在 Secrets 中配置 GEMINI_API_KEY。")
    st.stop()

# 初始化官方客户端
client = genai.Client(api_key=api_key)

# ==========================================
# 🖥️ 3. 界面交互
# ==========================================
col1, col2 = st.columns([3, 1])
with col1:
    stock_name = st.text_input("请输入股票名称/代码", "生益电子", help="支持 A股/港股/美股")
with col2:
    # 允许切换模型 (防 429 限流)
    model_choice = st.selectbox("选择模型", ["gemini-2.0-flash", "gemini-1.5-flash"], index=0)

if st.button("🚀 启动深度风控核查"):
    today = datetime.date.today().strftime("%Y年%m月%d日")
    st.info(f"正在调用 Google Search 检索【{stock_name}】全网舆情 (基准日: {today})...")
    
    # ==========================================
    # 🧠 4. 机构级 Prompt (植入硬性风控标准)
    # ==========================================
    prompt = f"""
    今天是 {today}。
    你是一名机构交易员的合规风控助手。请利用自带的 Google Search 工具，查询股票【{stock_name}】的最新实时数据。
    
    请严格针对以下4个维度进行事实核查，并以 JSON 格式返回：

        1. 【reduction】(近半年减持)：
           - 搜索指令：搜索“{stocks} 减持公告 股东减持计划 2025 2026”。
           - 核心：检查近半年是否有股东减持或发布减持计划？
           - 输出：**必须写出具体公告日期**（如“2025-12-10 公告...”）。若无，填“无”。
        
        2. 【fraud】(财务造假/立案)：
           - 搜索指令：搜索“{stocks} 证监会 立案 处罚 财务造假 警示函 违规担保”。
           - 核心：近3年是否有行政处罚或立案调查？
           - 输出：简述违规原因。
        
        3. 【delisting】(退市风险 - 严格对照新规红线)：
           - 搜索指令：搜索“{stocks} 股价 市值 营收 净利润 净资产 审计意见 ST”。
           - **必须逐项核对以下【直接退市】与【财务退市】红线**：
             A. **交易类强制退市**：
                - 股价指标：是否连续20个交易日收盘价低于 1 元？
                - 市值指标：总市值是否低于 5亿元（主板）？
                - 成交量：是否连续120个交易日累计成交量低于500万股？
             B. **财务类强制退市**：
                - 组合指标：是否“净利润为负 且 营收 < 3亿元”？
                - 净资产：最新会计年度期末净资产是否为负值？
                - 审计意见：是否被出具“无法表示意见”或“否定意见”？
           - 输出：明确指出是否触及上述任意一条红线。

        4. 【monitoring】(监管监控 - 严重异常波动硬指标)：
           - 搜索指令：搜索“{stocks} 严重异常波动 重点监控 异动公告 停牌核查 10天100% 30天200% 换手率”。
           - **必须核查以下交易所硬性标准**：
             A. **严重异动（时间与空间红线）**：
                - 是否触发“连续10个交易日偏离值累计 +100%”？
                - 是否触发“连续30个交易日偏离值累计 +200%”？
             B. **短期极端情绪**：
                - 是否出现“日换手率 > 30% 且连续涨停”？
                - 是否有尾盘剧烈拉升/打压行为（3分钟异动）？
             C. **名单与行为**：
                - 近期是否被交易所正式列入“重点监控证券名单”？
                - 是否因“对倒”、“虚假申报”等账户操纵行为被通报？
           - 输出：若触发以上任意硬性指标，请务必详细列出。

        请严格输出为纯 JSON 数组格式，不要包含 ```json 等标记，格式如下：
        [{{"name": "股票名", "reduction": "具体日期及内容...", "fraud": "造假详情...", "delisting": "退市红线详情...", "monitoring": "监控硬性指标详情..."}}]
        

        最后，请用一段简短的【交易员综述】总结该股当前的风险等级（低风险/关注/高危）。
    """

    # ==========================================
    # 📡 5. 调用官方 API (带搜索插件)
    # ==========================================
    with st.spinner("正在穿透搜索监管公告与财经新闻..."):
        try:
            # 启用 Google Search 工具
            response = client.models.generate_content(
                model=model_choice,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearchRetrieval())]
                )
            )
            
            # ==========================================
            # 📊 6. 展示结果
            # ==========================================
            st.success("核查完成！")
            
            # 显示主要内容
            st.markdown("### 📝 深度风控报告")
            st.write(response.text)
            
            # 显示搜索来源 (这是官方版独有的优势，能看到引用源)
            if response.candidates and response.candidates[0].grounding_metadata:
                with st.expander("🔍 查看原始数据来源 (Grounding Sources)"):
                    # 获取搜索建议生成的 HTML 片段
                    sources_html = response.candidates[0].grounding_metadata.search_entry_point.rendered_content
                    st.write(sources_html, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"核查中断: {e}")
            if "429" in str(e):
                st.warning("⚠️ 触发了免费版频率限制。建议：\n1. 等待 1 分钟后再试。\n2. 在上方下拉框切换为 gemini-1.5-flash 模型。")
            elif "API key" in str(e):
                st.error("⚠️ API Key 无效。请确认你使用的是 Google AI Studio 申请的 AIza 开头的官方 Key。")
