# 服务器部署

DelTracking 使用两个容器：`backend` 运行 FastAPI、调度器和 SQLite，`web` 运行 Nginx 并提供 SPA 与反向代理。宿主机只监听 `127.0.0.1:8080`，应由宿主机上的 Nginx、Caddy、宝塔或 Cloudflare Tunnel 提供域名和 HTTPS。

## 准备环境

服务器需要 Docker Engine 和 Docker Compose v2。复制环境示例：

```sh
cp .env.example .env
chmod 600 .env
```

生成两个独立随机密钥：

```sh
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
python3 -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

第一行填入 `SESSION_SECRET`，第二行填入 `SMTP_ENCRYPTION_KEY`。同时设置强管理员密码和 NextSLS `TRACKING_APP_ID`。`.env` 不得提交或发送给他人。

通过 HTTPS 访问时保持 `COOKIE_SECURE=true`。只有直接访问本机 HTTP 入口进行临时测试时才改为 `false`。

## 启动与检查

```sh
docker compose up -d --build
docker compose ps
curl --fail http://127.0.0.1:8080/health/live
curl --fail http://127.0.0.1:8080/health/ready
```

后端容器每次启动会先执行 Alembic 升级，然后以单个 Uvicorn worker 启动。单 worker 是内嵌调度器的运行约束，不应在同一数据库上横向扩展多个后端实例。

查看日志：

```sh
docker compose logs -f --tail=200 backend web
```

首次登录后应立即在“系统设置”中确认调度和 SMTP 配置，并发送测试邮件。

## HTTPS 反向代理

- Nginx 示例：[reverse-proxy/nginx.conf.example](reverse-proxy/nginx.conf.example)
- Caddy 示例：[reverse-proxy/Caddyfile.example](reverse-proxy/Caddyfile.example)

宝塔中可创建一个已启用 HTTPS 的反向代理站点，目标填写 `http://127.0.0.1:8080`，并保留 Host 与 `X-Forwarded-*` 请求头。

Cloudflare Tunnel 可将公开主机名指向 `http://localhost:8080`。不要把 Compose 端口改成 `0.0.0.0:8080`，除非另有防火墙和访问控制。

## 备份

先通过 SQLite 在线备份 API 在数据卷内创建一致性快照：

```sh
docker compose exec -T backend python -c "from pathlib import Path; import sqlite3; Path('/data/backups').mkdir(exist_ok=True); source=sqlite3.connect('/data/deltracking.db'); target=sqlite3.connect('/data/backups/deltracking-backup.db'); source.backup(target); target.close(); source.close()"
mkdir -p backups
docker compose cp backend:/data/backups/deltracking-backup.db ./backups/deltracking-backup.db
```

备份文件包含管理员摘要、SMTP 密文、运单和运行记录，应作为敏感数据加密保存。

## 恢复

恢复会替换当前数据库。先保留当前备份并停止服务：

```sh
docker compose down
docker compose run --rm --no-deps --entrypoint sh -v "$PWD/backups:/backup:ro" backend -c "cp /backup/deltracking-backup.db /data/deltracking.db"
docker compose up -d
curl --fail http://127.0.0.1:8080/health/ready
```

恢复后检查登录、设置和最近运行记录。数据库版本较旧时，启动过程会自动执行缺失的 Alembic 迁移。

## 升级

1. 创建并下载最新备份。
2. 获取经过审核的新版本代码或发布包。
3. 运行 `docker compose build --pull`。
4. 运行 `docker compose up -d`，启动过程会先升级数据库。
5. 检查 `docker compose ps`、两个健康端点和容器日志。
6. 验证后台登录、下一次调度时间和测试邮件。

若升级失败，保存日志，停止容器，切回原版本镜像，并按恢复步骤还原升级前备份。

## 常见问题

- `SESSION_SECRET is required`：尚未创建 `.env`，或变量为空。
- 登录后仍返回未认证：使用 HTTPS 时确认 `COOKIE_SECURE=true`；直接用 HTTP 测试时设为 `false`。
- `backend` 不健康：查看迁移和配置错误：`docker compose logs backend`。
- 邮件发送失败：在运行记录中查看错误，修正 SMTP 后手动重试，不需要重新查询运单。
- 端口不可从外网直连：这是预期行为，入口只绑定回环地址，应通过反向代理访问。
