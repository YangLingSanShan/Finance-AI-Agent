# PDF 原始部署命令

以下命令仅复制留档，未执行；其中仓库地址是 PDF 中的占位地址，且原文缺失部分构建文件。

## 9.1 Docker Compose 一键部署（第 87–88 页）

```bash
# 1. 克隆代码
git clone https://github.com/your-repo/Financial-AI-Agent.git
cd Financial-AI-Agent

# 2. 配置环境变量
cp .env.example .env
vim .env  # 填写 LLM_API_KEY

# 3. 一键启动所有服务
docker-compose up -d

# 4. 检查服务状态
docker-compose ps

# 5. 查看后端日志
docker-compose logs -f backend

# 6. 停止服务
docker-compose down
```

## 9.4 本地开发启动（第 90–91 页）

```bash
# ===== 后端 =====
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example ../.env
uvicorn app.main:app --reload --port 8000

# ===== 前端 =====
cd frontend
npm install
npm run dev
# 访问 http://localhost:5173
```
