import streamlit as st
import json
import datetime
from google import genai
from google.genai import types

# ==========================================
# ⚡️ 1. 页面配置 (不需要 HTML)
# ==========================================
st.set_page_config(page_title="机构级避雷 Agent", layout="wide")

st.title("🛡️ 机构级股票避雷 Agent (v5.0)")
st.caption("基于 Google Gemini 2.0 Flash + 实时联网搜索")

# ==========================================
# 🔐 2. 安全获取 API Key (关键！)
# ==========================================
# 代码里不再出现真实的 Key，而是让它去系统的“保险柜”里找
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except:
    st.error("未检测到 API Key，请在 Streamlit Secrets 中配置！")
    st.stop()

# 初始化客户端
client = genai.Client(api_key=api_key)

# ==========================================
# 🖥️ 3. 界面交互
# ==========================================
# 输入框
stocks = st.text_input("请输入股票名称/代码 (例如: 贵州茅台)", "贵州茅台")

# 按钮
if st.button("🚀 开始核查"):
    today = datetime.date.today().strftime("%Y年%m月%d日")
    st.info(f"正在核查: {stocks} (基准日: {today})，请稍候...")
    
    # ==========================================
    # 🧠 4. 核心逻辑 (你的 Prompt)
    # ==========================================
    prompt = f"""
    今天是 {today}。
    你是一名机构交易员的合规风控助手。请利用 Google Search 工具，查询股票【{stocks}】的最新实时数据。
    
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
    
    请严格输出为纯 JSON 数组格式，不要包含 markdown 标记。
    格式参考：[
        {{"name": "{stocks}", "reduction": "内容...", "fraud": "内容...", "delisting": "内容...", "monitoring": "内容..."}}
    ]
    """

    try:
        # 调用 Gemini (不需要代理设置，云端直连)
        response = client.models.generate_content(
            model='gemini-2.0-flash', # 建议用 2.0-flash，速度快
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearchRetrieval())]
            )
        )
        
        # 数据清洗
        text = response.text
        # 去掉可能的 ```json 包裹
        if '```' in text:
            text = text.replace('```json', '').replace('```', '')
        
        # 解析 JSON
        result_json = json.loads(text.strip())
        
        # ==========================================
        # 📊 5. 展示结果
        # ==========================================
        # 直接把 JSON 变成漂亮的表格或卡片
        if isinstance(result_json, list) and len(result_json) > 0:
            data = result_json[0]
            
            col1, col2 = st.columns(2)
            with col1:
                st.error(f"📉 减持情况: {data.get('reduction')}")
                st.warning(f"⚠️ 造假/立案: {data.get('fraud')}")
            with col2:
                st.error(f"❌ 退市风险: {data.get('delisting')}")
                st.info(f"👁️ 监管监控: {data.get('monitoring')}")
                
            with st.expander("查看原始 JSON 数据"):
                st.json(result_json)
        else:
            st.write(text)

    except Exception as e:
        st.error(f"运行出错: {e}")
