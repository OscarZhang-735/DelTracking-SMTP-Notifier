# DelTracking SMTP Notifier

基于 FastAPI、Vue 3、SQLite 和 NextSLS 的物流追踪与邮件通知管理系统。

当前重建分支已提供管理 API、Vue 管理后台、定时查询、变更检测和邮件 Outbox。服务器使用 Docker Compose 部署，宿主机仅开放回环入口 `127.0.0.1:8080`。

## Docker 部署

```sh
cp .env.example .env
# 编辑 .env 中的随机密钥、管理员密码和 TRACKING_APP_ID
docker compose up -d --build
```

完整的初始化、HTTPS 反向代理、备份恢复、升级和故障排查说明见 [服务器部署文档](docs/deployment.md)。

## 本地开发验证

后端：

```sh
cd backend
python -m pip install -e ".[dev]"
pytest
```

前端：

```sh
cd frontend
npm ci
npm run lint
npm run test
npm run build
```

旧版 `main.py`、`run.bat` 和 `config.json` 暂时保留，用于第 8 步旧数据迁移验证；服务器部署不再依赖这些文件。
