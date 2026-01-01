# 📈 金融顾问RAG代理 (financial-agent)
基于LangChain构建的智能金融问答助手，适配2019-2021年基金数据+招股说明书，底层数据来源于「金融千问14B」，嵌入模型采用M3E-Base，支持可视化Web交互。

## 📋 项目简介
本项目实现了一个专业的金融问答RAG（检索增强生成）系统，核心能力包括：
- 📊 支持2019-2021年基金数据查询（持仓、规模、行情等）
- 📄 招股说明书智能问答（基于金融千问14B数据集）
- 💻 Gradio可视化Web界面，支持多轮对话、历史记忆
- 🧠 基于M3E-Base嵌入模型的高效向量检索

## 🎯 核心依赖
| 组件 | 名称/地址 | 说明 |
|------|-----------|------|
| 数据集 | [金融千问14B](https://www.modelscope.cn/datasets/BJQW14B/bs_challenge_financial_14b_dataset.git) | 金融领域问答核心数据 |
| 嵌入模型 | [M3E-Base](https://www.modelscope.cn/models/AI-ModelScope/m3e-base/summary) | 中文通用嵌入模型，适配金融文本 |
| 框架 | LangChain | RAG核心流程编排 |
| 前端 | Gradio | 轻量化Web可视化界面 |
| LLM | DeepSeek-Chat | 金融专业问答生成 |

## 🚀 快速开始
### 1. 克隆仓库
```bash
git clone https://github.com/zheng1114567/financial-agent.git
cd financial-agent
```
### 2. 安装依赖
```bash
pip install -r requirements.txt
```
### 3. 下载数据集&模型
```bash
# 下载金融千问14B数据集
git clone https://www.modelscope.cn/datasets/BJQW14B/bs_challenge_financial_14b_dataset.git ./data/financial_14b

# 下载M3E-Base嵌入模型（ModelScope）
from modelscope.hub.snapshot_download import snapshot_download
snapshot_download("AI-ModelScope/m3e-base", cache_dir="./models")
```
### 4. 将文件中的路径修改为自己的
### 5. 启动web服务
```bash
python app/web.py
