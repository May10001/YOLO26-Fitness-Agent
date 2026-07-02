# 网站部署指南

> 部署完成后，用户打开浏览器即可使用，无需安装任何东西。

## 架构

```
用户浏览器 → [Vercel 托管前端] → WebSocket/HTTP → [云服务器后端]
                                                      ├── YOLO 姿态检测
                                                      └── PoseAnalyzer 评分
                         ↘ HTTP API ↘
                                    [百炼云端 7B 模型]
                                    健身教练 AI 回复
```

---

## 一、前端部署到 Vercel（免费，5 分钟）

### 1. 推送项目到 GitHub（在本地项目根目录执行）

```bash
git add -A
git commit -m "feat: 可部署的 Web 版本"
git push origin main
```

### 2. 连接 Vercel

1. 打开 [vercel.com](https://vercel.com) → 用 GitHub 账号登录
2. 点击 **「New Project」** → 选择你的仓库
3. 配置：
   - **Framework Preset**: Vite
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
4. **环境变量**（重要）：
   - Key: `VITE_API_URL`
   - Value: `https://你的后端服务器地址`（先不填，等后端部署好）
5. 点击 **「Deploy」**

部署后 Vercel 会给你一个 URL（如 `https://yolo26-fitness.vercel.app`）。

---

## 二、后端部署到云服务器

### 选项 A：阿里云 ECS（推荐，已有账号）

```bash
# 1. 登录服务器
ssh root@你的服务器IP

# 2. 安装依赖
apt update && apt install -y python3-pip
cd /opt
git clone https://github.com/你的用户名/YOLO26-Fitness-Agent.git
cd YOLO26-Fitness-Agent
pip install -r requirements.txt openai fastapi uvicorn

# 3. 配置 API（用你的实际值替换）
cat > data/api_config.json << 'EOF'
{
  "use_remote": true,
  "api_key": "sk-your-dashscope-api-key",
  "model_code": "qwen2.5-7b-instruct-d1a1cabf17c2-yzqr"
}
EOF

# 4. 启动后端（后台运行）
nohup uvicorn backend.main:app --host 0.0.0.0 --port 8002 > /var/log/fitness.log 2>&1 &

# 5. 开放防火墙端口
# 阿里云安全组入方向添加规则：TCP 8002
```

### 选项 B：快速测试用（本地 + 公网隧道）

如果暂时没有云服务器，可以用 cpolar/localtunnel 做隧道测试：

```bash
# 启动后端
uvicorn backend.main:app --host 0.0.0.0 --port 8002

# 另一个终端，启动隧道
npx localtunnel --port 8002
# 会得到一个公网 URL，如 https://xxx.loca.lt
```

---

## 三、串联

1. 后端部署好后，拿到公网地址（如 `http://123.45.67.89:8002`）
2. 回到 Vercel 项目设置 → Environment Variables
3. 设置 `VITE_API_URL` = `http://123.45.67.89:8002`
4. Vercel 自动重新部署
5. 打开 Vercel 给的域名，完成！

---

## 需要的最低配置

| 组件 | 规格 | 月费 |
|------|------|------|
| 前端托管 | Vercel 免费版 | ¥0 |
| 后端服务器 | 阿里云 ECS 2核4G + GPU（可选） | ¥200-500 |
| AI 模型推理 | 百炼按量 | ¥30-100 |

> 后端用 CPU 也能跑（帧率会低一些），可以先用低配 ECS 测试。
