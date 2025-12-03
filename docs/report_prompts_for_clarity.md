# 📘 每周网站使用情况分析报告

本周开始日期（Week Start Date）：2025-11-24
本周结束日期（Week End Date）：2025-11-30
对比周开始日期（Last Week Start Date）：2025-11-17
对比周结束日期（Last Week End Date）：2025-11-23

系统需使用以上日期来：

- 过滤原始数据
- 生成周度统计
- 创建 Week-over-Week（WoW）对比
- 在 PDF 和图表标题中显示日期范围

**目标：**
生成一份专业、高质量的**每周网站使用情况分析报告**，对本周网站的用户表现进行统计、可视化、对比和解读，并与上周做 Week-over-Week（WoW）对比。

---

## **一、需要包含的核心指标**

对**本周**与**上周**进行对比，指标包括：

- **滚动深度（Scroll Depth, %）**
- **停留时间**

  - *页面活跃时间（分钟）*
  - *页面总停留时间（分钟）*
- **单次会话浏览页数（Pages per Session）**
- **无效点击比例（Dead Clicks, %）**
- **快速后退比例（Quick Backs, %）**
- **暴躁点击（Rage Clicks，如有）**
- **过度滚动（Excessive Scrolling，如有）**
- **互动评分（Engagement Score，如有）**

---

## **二、可视化要求**

- 所有主要指标生成 **周对周（WoW）柱状图**
- 必须使用 **趋势箭头**（↑ 提升 / ↓ 下降 / → 持平）
- 必须使用 **颜色标记趋势**

  - 绿色：表现提升
  - 红色：表现下降
  - 黄色：持平或无明显变化
- 图表要求：

  - **300 DPI 高清 PNG**
  - 清晰坐标与标注
- 包含“Top 页面对比图”（柱状图或折线图）

---

## **三、报告结构要求**

### **1. 执行摘要（Executive Summary）**

总结本周的核心表现，包括：

- 主要指标总体趋势
- 明显提升或下降的关键点
- Top 表现页面和负面表现页面的小结

---

### **2. 本周详细指标分析**

逐项分析所有指标：

每个指标必须包含：

- 本周数据
- 上周数据
- 绝对变化值
- 百分比变化
- 趋势箭头（↑ ↓ →）
- 300 DPI 的 WoW 对比柱状图
- 对趋势的解释和可能原因

---

### **3. Top 5 页面分析**

本周访问量最高的 5 个页面：

对每个页面分析：

- 滚动深度
- 停留时间（活跃与总时间）
- 无效点击
- 快速后退
- Rage Clicks、Excessive Scrolling（如有）
- 与上周的 WoW 对比
- 趋势箭头与颜色标记

---

### **4. Top 页面对比表格**

一个并排对比表格：

| 页面 | 指标 | 本周 | 上周 | 变化值 | 趋势 |
| -- | -- | -- | -- | --- | -- |

趋势颜色：

- **绿色 → 改善**
- **红色 → 下降**
- **黄色 → 持平**

---

### **5. 其他附加指标（可选）**

如果有 Rage Clicks / Excessive Scrolling / Engagement Score：

对每项提供：

- WoW 对比
- 图表
- 指标范围解释
- 异常情况特别标注

---

### **6. 建议与下一步行动**

基于本周表现提出优化方向：

- 用户体验（UX）改进
- 内容布局调整
- 可改善的漏斗步骤
- 需要监控或修正的页面问题
- 下一阶段应重点分析的异常状况

---

### **7. 方法论说明**

需说明：

- 数据来源（API / 日志 / analytics 等）
- 指标定义
- 计算方法
- 周的起止日期（例如 周一至周日）

---

## **四、技术要求**

- 使用 **Python** 来处理数据与生成图表

- 需要的库：

  ```text
  pandas
  matplotlib
  reportlab
  requests
  ```

- 输出文件：

  - **A4 尺寸的专业 PDF**（带高清图表和排版良好的表格）
  - **Markdown 版本（.md）** 用于编辑或归档

All generated files should be saved in a dedicated folder, e.g., `reports/`:

`reports/Clarity_Report_[WEEK]_[YEAR].pdf` — Complete report with embedded charts
`reports/Clarity_Report_[WEEK]_[YEAR].md` — Markdown version for reference
`reports/Clarity_Report_[WEEK]_[YEAR]_*.png` — Individual chart files for presentations or client sharing

- PDF 要求：

  - 嵌入高清图表（全部 300 DPI）
  - 标题层级清晰
  - 表格整齐、边框明确
  - 合理的页边距和段落间距
