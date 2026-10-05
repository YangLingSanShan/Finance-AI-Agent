# PDF 原始项目结构（第 6–8 页）

这是文档中的设计目录，部分文件只在目录中出现，正文没有给出代码。实际复制文件见 SOURCE_MAP.md。

```text
Financial-AI-Agent/
├── docs/
│   └── 项目技术文档.md
├── INTEGRATED.md
├── backend/                    ← FastAPI 后端
│   ├── app/
│   │   ├── main.py               FastAPI入口
│   │   ├── config.py             全局配置
│   │   ├── core/
│   │   │   ├── llm.py            LLM统一接口
│   │   │   ├── redis_client.py   Redis连接
│   │   │   └── vectorstore.py    向量库接口
│   │   ├── models/
│   │   │   ├── schemas.py        Pydantic模型
│   │   │   └── database.py       SQLAlchemy ORM
│   │   ├── agents/
│   │   │   ├── base.py           Agent基类
│   │   │   ├── orchestrator.py   编排器
│   │   │   ├── researcher.py     投研Agent
│   │   │   ├── risk_agent.py     ⻛控Agent
│   │   │   ├── strategist.py     策略Agent
│   │   │   └── report_agent.py   报告Agent
│   │   ├── rag/
│   │   │   ├── knowledge_base.py 知识库
│   │   │   ├── retriever.py      混合检索
│   │   │   └── query_rewrite.py  查询改写
│   │   ├── llmops/
│   │   │   └── monitor.py        监控核心
│   │   ├── dataops/
│   │   │   └── pipeline.py       数据管道
│   │   └── api/
│   │       ├── chat.py           对话API
│   │       ├── agent.py          AgentAPI
│   │       ├── rag.py            RAG API
│   │       ├── llmops.py         LLMOps API
│   │       └── data.py           数据API
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                   ← Vue3 前端
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.ts
│       ├── App.vue
│       ├── router.ts
│       ├── style.css
│       ├── api/
│       │   ├── index.ts
│       │   ├── chat.ts
│       │   ├── agent.ts
│       │   └── llmops.ts
│       ├── stores/
│       │   ├── chat.ts
│       │   └── llmops.ts
│       └── views/
│           ├── ChatView.vue
│           ├── DashboardView.vue
│           ├── ReportView.vue
│           ├── KnowledgeView.vue
│           └── LLMOpsView.vue
├── docker-compose.yml
└── .env.example
```
