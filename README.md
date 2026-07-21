# Synthetic RWE Diabetes Treatment Study

> **Portfolio demo:** [RWE Evidence Report (PDF)](reports/RWE_Evidence_Report.pdf) · [HTML](reports/RWE_Evidence_Report.html) · [Table 1](reports/Table1_Baseline.xlsx) · [Table 2](reports/Table2_Outcome.xlsx) · [Table 3](reports/Table3_Treatment_Effect.xlsx)  
> **Stack:** Python · pandas · statsmodels · lifelines · scikit-learn · dowhy · econml · Jinja2 · openpyxl  
> **Note:** Synthea **synthetic** data — end-to-end **RWE methods** pipeline; not a clinical efficacy claim.

基于 **Synthea 合成 EHR 数据**的糖尿病药物 **真实世界证据（RWE）** 观察性研究项目。  
完整实现从数据质控、队列定义、基线特征、暴露/outcome 分析，到倾向性评分与高级因果推断，最终生成制药行业风格的 RWE 证据报告。

## 可视化预览

![Cohort Flow](reports/figures/figure_cohort_flow.png)

*队列筛选流程：全库患者 → T2DM 诊断 → 用药暴露 → 最终分析队列 N=69*

---

**优先打开：**

1. `reports/RWE_Evidence_Report.pdf` — 完整证据报告  
2. `reports/Table1_Baseline.xlsx` — 基线 + SMD  
3. `reports/Table3_Treatment_Effect.xlsx` — 因果效应  
4. `reports/figures/figure_cohort_flow.png` — 队列流程图  



## 研究问题

**糖尿病药物治疗对临床结局的因果/比较效应是什么？**

| 项目 | 定义 |
| --- | --- |
| **Treatment A** | Metformin users（二甲双胍） |
| **Treatment B** | Other diabetes medication users（胰岛素、GLP-1 等其他降糖药） |
| **主要结局** | 糖尿病相关并发症或住院/急诊的复合事件 |
| **研究设计** | 回顾性观察性队列研究 |
| **最终分析队列** | N = 69（Metformin 49 / Other 20） |

> 数据为 Synthea 合成数据，用于方法论演示；结果不可直接外推至真实临床人群。

---

## 项目结构

```
rwe-project/
├── data/
│   └── synthea_csv/          # Synthea 导出的 CSV（patients, conditions, medications, encounters 等）
├── notebooks/                # 分步骤 Jupyter Notebook（Step 1–8）
├── reports/                  # 各步骤输出报告、表格、图表
│   └── figures/              # 可视化图片
├── src/
│   ├── data_profile.py         # 数据集描述性概览（记录数、时间范围、关键字段分布）
│   ├── cohort_definition.py
│   ├── data_quality.py
│   ├── baseline_characteristics.py
│   ├── baseline_analysis.py
│   ├── baseline_observations.py
│   ├── treatment_exposure.py
│   ├── outcome_analysis.py
│   ├── causal_inference.py
│   ├── advanced_causal_inference.py
│   ├── rwe_report_generation.py
│   └── templates/            # RWE 报告 Jinja2 模板
├── requirements.txt
└── README.md
```

---

## 分析流程（Step 0–8）

| Step | 模块 | Notebook | 主要输出 |
| --- | --- | --- | --- |
| **0** 数据概览（可选） | `data_profile.py` | — | `synthea_data_profile.md`（各表记录数、字段分布、主外键关系） |
| **1** 数据质控 | `data_quality.py` | `01_data_quality_assessment.ipynb` | `data_quality_report.html` |
| **2** 队列定义 | `cohort_definition.py` | `02_cohort_definition.ipynb` | `study_population.csv`, `cohort_flow.csv` |
| **3** 基线特征 | `baseline_analysis.py` | `03_baseline_characteristics.ipynb` | `baseline_characteristics_table.csv`, Table 1 |
| **4** 治疗暴露 | `treatment_exposure.py` | `04_treatment_exposure.ipynb` | `exposure_dataset.csv`, `treatment_exposure_summary.csv` |
| **5** 结局分析 | `outcome_analysis.py` | `05_outcome_analysis.ipynb` | `outcome_summary.csv`, KM / logistic 结果 |
| **6** 倾向性评分 | `causal_inference.py` | `06_propensity_score_analysis.ipynb` | `matched_cohort.csv`, `treatment_effect_results.csv` |
| **7** 高级因果推断 | `advanced_causal_inference.py` | `07_causal_inference.ipynb` | `causal_effect_estimates.csv`, DoWhy / EconML |
| **8** RWE 证据报告 | `rwe_report_generation.py` | `08_rwe_evidence_generation.ipynb` | `RWE_Evidence_Report.html/.pdf`, Table1–3 xlsx |

各步骤按顺序依赖前序输出；Step 8 汇总 Step 1–7 的全部结果。  
**Step 0** 为可选的数据探索步骤，在正式质控前快速了解 Synthea CSV 的规模与结构。

---

## 环境配置

### 要求

- Python 3.10+
- Windows / macOS / Linux

### 安装依赖

```powershell
cd e:\rwe-project
pip install -r requirements.txt
```

主要依赖：`pandas`, `numpy`, `scipy`, `statsmodels`, `scikit-learn`, `lifelines`, `matplotlib`, `seaborn`, `dowhy`, `econml`, `jinja2`, `openpyxl`, `xhtml2pdf`

---

## 快速开始

### 方式一：逐步运行 CLI（推荐首次复现）

在 `src/` 目录下按顺序执行：

```powershell
cd e:\rwe-project\src

python data_profile.py          # 可选：生成数据集概览报告
python data_quality.py
python cohort_definition.py
python baseline_analysis.py
python treatment_exposure.py
python outcome_analysis.py
python causal_inference.py
python advanced_causal_inference.py
python rwe_report_generation.py
```

### 方式二：Jupyter Notebook

```powershell
cd e:\rwe-project\notebooks
jupyter notebook
```

依次打开 `01` … `08` 号 notebook 运行。

---

## 最终交付物（Step 8）

| 文件 | 说明 |
| --- | --- |
| `reports/synthea_data_profile.md` | Step 0 数据集概览（记录数、字段分布、表间关系） |
| `reports/RWE_Evidence_Report.html` | 完整 RWE 证据报告（HTML） |
| `reports/RWE_Evidence_Report.pdf` | PDF 版报告 |
| `reports/Table1_Baseline.xlsx` | 基线特征表（含 SMD） |
| `reports/Table2_Outcome.xlsx` | 结局事件、随访、KM 结果 |
| `reports/Table3_Treatment_Effect.xlsx` | PSM / IPTW / 回归调整因果效应 |
| `reports/figures/figure_cohort_flow.png` | 队列筛选流程图 |

---

## 统计方法概要

- **基线比较**：Table 1（含 pre-index HbA1c、BMI）、t 检验 / Mann-Whitney、卡方 / Fisher、SMD、Love plot  
- **结局分析**：事件率（/100 patient-years）、Kaplan-Meier、log-rank、未调整 logistic  
- **因果推断（Step 6）**：Logistic PS（含 HbA1c、BMI）、1:1 最近邻匹配、IPTW、匹配后 logistic、风险差  
- **高级因果（Step 7）**：多变量回归、IPTW ATE/ATT、双重稳健 AIPW、Bootstrap CI、DoWhy、EconML LinearDML、敏感性分析、亚组效应  
- **因果假设**：可交换性（无未测量混杂）、positivity（重叠性）、一致性  

---

## 关键结果摘要（当前 Synthea 队列）

| 分析 | 结果（方向性） |
| --- | --- |
| 未调整 | Other 组复合结局事件率更高（log-rank p ≈ 0.01） |
| 多变量 logistic OR（Other vs Metformin） | 1.20（95% CI 宽，p = 0.89） |
| IPTW ATE（风险差） | +0.11（Metformin − Other，p = 0.34） |
| PSM 匹配（8 对） | 样本量小，估计不稳定 |

> 宽置信区间与小样本（N=69）符合合成数据预期；因果解读需满足无未测量混杂等假设。

---

## 数据说明

- **来源**：`data/synthea_csv/` 下的 Synthea 合成 EHR CSV  
- **不生成假数据**：所有分析基于现有 CSV 与 pipeline 中间产物  
- **索引日期（index date）**：T2DM 诊断后首次糖尿病用药日期  
- **随访**：index 起最长 730 天，截尾于末次就诊或死亡  

---

## 局限性

1. **合成数据**：不代表真实世界治疗路径与编码习惯  
2. **样本量小**：匹配、IPTW、亚组分析精度有限  
3. **残余混杂**：已纳入基线 HbA1c 与 BMI（`observations.csv`），但胰岛素抵抗、依从性、生活方式等仍可能未测量  
4. **依从性**：用药处方 ≠ 实际服药  
5. **外推性**：单队列结果需外部验证  

---

## 开发说明

- **随机种子**：各模块统一 `RANDOM_SEED = 42`，保证可复现  
- **报告目录**：默认 `reports/`，可通过各脚本 `--report-dir` 修改  
- **数据目录**：默认 `data/synthea_csv/`，可通过 `--data-dir` 修改  
- **代码风格**：模块化函数 + CLI 入口 + 对应 notebook，便于制药 RWE 文档化  

---

## 引用与许可

本项目为 **Synthetic RWE Diabetes Treatment Study** 的方法论演示代码库，采用 [MIT License](LICENSE)。  
使用 Synthea 数据请遵循 [Synthea 项目](https://github.com/synthetichealth/synthea) 的相关许可。

---
