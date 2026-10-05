# SilkReel-01 · 江口缫丝坞

缫丝盆环状作业台。登录后看到的是沿汤池围成一圈的盆位，点盆登记汤温并改状态——不是侧栏双列表 CRUD。

## 技术栈

| 层 | 技术 |
| --- | --- |
| Web API | Quart（异步 Flask 族）· Hypercorn |
| 结构 | `repositories.py` 仓储 + `services.py` 门槛，路由不直接拼 SQL |
| 数据 | SQLAlchemy 2 async · asyncpg · PostgreSQL 15 |
| 前端 | Preact 10 · Vite |
| 部署 | Docker Compose |

## 路径与端口

- 前端：http://localhost:4760
- API：http://localhost:8760
- PostgreSQL：localhost:6160

## 演示账号

| 用户名 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `123456` | 管理员 |
| `worker` | `123456` | 缫丝工 |

## 业务规则

- 盆状态不可标成「已缫完」，除非该盆**最近一条**汤温记录落在 **38～42℃**。规则在 `backend/app/services.py`。
- 坞内已有盆「缫丝中」时，另一口「浸茧」要改成「缫丝中」，须与坞内各缫丝中盆比较**茧粒**：差的绝对值超过 **120 粒**即中文挡住；坞内没有缫丝中盆则不比。茧粒差不参与「已缫完」判定。
- 同一盆的重复状态、并发抢改只入库一笔（同坞状态变更在坞行锁内串行）。
- 顶栏可进「环盆作业台」与「茧粒台」；茧粒台只读，列出各盆茧粒与最近缫丝中盆的差，可按坞筛。

## 快速启动

```bash
cd SilkReel/SilkReel-01
docker compose up --build
```
