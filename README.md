# Financial AI Agent — PDF 代码副本

来源：工作区内《3、Agent项目-基于LLM的金融分析AI+Agent.pdf》（92 页）。

按照“文档中已经有代码，就直接复制一份”的要求，本目录保存 PDF 中的全部代码及配置片段，保留原示例逻辑。它是原文代码副本，并不表示文档中描述的所有功能已经完成或可直接运行。

## 已复制内容

- `backend/app/`：23 个 Python 文件，包括配置、LLM 接口、数据模型、四类 Agent、编排器、RAG、LLMOps、DataOps 和 API。
- `frontend/`：18 个 Vue / TypeScript / CSS / JSON 文件，包括五个页面、路由、状态管理及 API 封装。
- `infra/init.sql`：数据库建表脚本。
- `docker-compose.yml`、`.env.example`、`infra/nginx.conf`、`infra/alert_rules.yml`：原文部署与监控配置。

共 46 个代码及配置文件。逐文件章节、页码及原代码行数见 [来源索引](docs/SOURCE_MAP.md)。

## 复制时的排版处理

移除 PDF 的代码行号，按照原行号合并页面自动折行，保留原代码缩进，移除行尾排版空格。将 PDF 使用的兼容部首字形还原为常用汉字。第 32、42 页开头的“代码块”标签与三引号重叠，已去除标签并恢复三引号。未改写业务逻辑。

文档中的提示词只是项目代码内容，部署命令仅作为文档保存，没有执行。

## 原文已有的缺失与限制

以下是阅读源码时发现的情况，保留原样，未做运行验证：

- 文档目录提到 `backend/requirements.txt`、`backend/Dockerfile`、`frontend/index.html`，但正文未给出内容。Compose 引用的前端 Dockerfile、`infra/prometheus.yml`，以及 TypeScript 配置引用的 `tsconfig.node.json` 也没有提供。因此本副本不具备完整的安装、构建和部署文件。
- `LLMService.chat()` 返回调用日志，没有返回模型正文和工具调用结果；`BaseAgent.execute()` 使用日志错误字段或 `done` 作为输出，工具调用循环尚未实现。
- 股票、财务、新闻和风险工具以及 Wind / Tushare 抽取器使用示例数据；`db_loader()` 只统计记录数，没有实际入库。
- 向量库统一接口的 Chroma / Milvus 方法是占位实现；知识库管理器中另有 Chroma 实现。混合检索没有完整实现文档架构中的 BM25、RRF，查询改写也没有读取真实模型正文。
- 看板、报告中心和知识库页面包含固定演示数据或占位交互；监控页面柱状图模板存在未闭合的 `div`，原文第 76 页亦如此。
- ORM 使用 `metadata` 属性名，与 SQLAlchemy 声明式模型保留名称冲突。SQL 与 ORM 也存在字段差异，数据库会话与持久化链路未完整接入。
- 原文的鉴权、限流、Prefect 调度、Prometheus 指标暴露等架构项没有完整对应实现；告警规则和模型费用常量按原文保留，未核实其适用性。
- 环境变量中的密钥和仓库地址是占位值，Embedding 模型与服务地址的匹配需要后续确认。

## 操作范围

本次仅阅读 PDF、提取和整理文件、核对代码块行号与文件清单。未安装项目依赖，未执行项目代码、测试、类型检查、编译、构建、SQL、容器启动或外部模型调用。未验证可运行性。

[原始项目目录](docs/PDF_PROJECT_TREE.md) 和 [原始部署命令](docs/PDF_DEPLOYMENT.md) 单独保留，便于与 PDF 对照；部署命令不代表已经验证可用。
