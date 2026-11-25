# 多维指标分析与实验评估平台

面向业务指标口径管理、多维分析查询、AB实验评估、分群圈选和数据服务发布的分析应用平台

这是一个前后端分离的管理平台：前端 Vue 3 + Vite + TypeScript，后端 FastAPI（Python）。
两边各自独立启动，前端 dev server 已关掉自动打开页面，启动后按终端打印的地址手工打开。

## 目录结构

```text
.
├── frontend/                 Vue 3 + Vite + TypeScript 前端
│   ├── src/views/WorkbenchView.vue|tsx  全部模块共享工作台
│   ├── src/data/modules.ts              18个业务模块配置
│   ├── src/api/              统一请求封装
│   └── vite.config.ts        dev server 配置（open: false）
├── backend/                  FastAPI（Python） 后端
│   ├── app/routers/resource.py  通用查询/导出/登记/动作接口
│   ├── app/services/<key>.py    每个模块独立领域逻辑
│   ├── app/services/base.py     共享服务骨架
│   └── app/store.py          内存数据仓库与示例数据
├── .gitignore
└── docker-compose.yml
```

## 启动

### 后端

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./run.sh
```

健康检查：`curl http://127.0.0.1:8012/api/health`

### 前端

```bash
cd frontend
npm ci
npm run dev
```

前端默认监听 `http://127.0.0.1:5176/`，dev server 不会自动打开浏览器，
需要自己访问。`/api` 由 vite 代理到后端 `http://127.0.0.1:8012`。

## 业务模块

| 模块 | 目录 | 业务对象 | 主要字段 |
| --- | --- | --- | --- |
| 指标口径 | `metric_def` | 指标定义 | 指标标识、指标名称、计算公式 |
| 多维查询 | `dim_query` | 查询方案 | 方案标识、查询指标、维度行 |
| 实验管理 | `experiment` | 实验方案 | 方案标识、实验名称、对照组 |
| 显著性检验 | `significance` | 检验任务 | 任务标识、关联实验、检验方法 |
| 人群圈选 | `cohort` | 人群分群 | 分群标识、分群名称、圈选条件 |
| 数据服务 | `data_service` | 服务接口 | 接口标识、关联指标、接口路径 |
| 异常检测 | `anomaly_detect` | 检测规则 | 规则标识、关联指标、检测算法 |
| 分析图表 | `analysis_chart` | 图表配置 | 图表标识、数据来源、图表类型 |
| 预聚合任务 | `aggregate_job` | 聚合任务 | 任务标识、目标指标、聚合维度 |
| 下钻分析 | `drill_down` | 下钻路径 | 路径标识、起始指标、下钻维度 |
| 数据导出 | `data_export` | 导出任务 | 任务标识、查询方案、导出格式 |
| 数据时效 | `data_freshness` | 时效检查 | 检查标识、数据来源、期望时效 |
| 查询缓存 | `query_cache` | 缓存策略 | 策略标识、关联查询、缓存键 |
| 分群对比 | `segment_compare` | 对比方案 | 方案标识、分群A、分群B |
| 指标校准 | `metric_calibrate` | 校准记录 | 记录标识、校准指标、原口径值 |
| 查询日志 | `query_log` | 查询记录 | 记录标识、查询内容、查询用户 |
| 数据采样 | `data_sample` | 采样配置 | 配置标识、数据来源、采样方法 |
| 报告调度 | `report_schedule` | 报告任务 | 任务标识、报告内容、接收人 |

## 约定

- 全部模块共享`frontend/src/views/WorkbenchView.vue|tsx`和一套资源路由。
- 每个模块仍保留独立`backend/app/services/<模块>.py`；纯前端保留
  `frontend/src/domain/<模块>.ts`，用于承载真实业务差异并维持36题位容量。
- 列表接口统一返回 `{ items, total, page, size }`，动作接口统一返回 `{ ok, message }`。
- 状态流转只允许在 `app/services` 里改，路由层不做业务判断。

领域：数据工程
子方向：数据分析与数据应用

## 人群圈选成交贡献明细

在「人群圈选」模块旁新增「成交贡献」工作台（`/cohort-contribution`），
用于按两组圈选名单核对统计窗口内的成交金额。

- 贡献看板：分别展示 A、B 两组各自计入金额、独占金额、交叠计入金额，
  并用「两组计入合计」与窗口内去重订单金额对平。
- 交叠口径：同一订单同时命中两组时按交叠均分拆到两组，分位余数按 A→B 补齐，
  两组相加等于原金额；汇总时同一订单只计一次。
- 按组下钻：`GET /api/cohort-contribution/views/{view_id}/groups/{A|B}`
  从原始订单明细复算该组实际计入的订单与用户金额。
- 用户分析下钻：`GET /api/chains/cohort-analysis/{cohort_id}?view_id=` 的
  `contribution_orders` 读取成交贡献明细视图，按圈选组核对订单号、原金额和组内计入金额。
- 发布快照：发布视图时冻结两组名单版本；次日名单刷新后旧期视图仍按原快照复算，
  金额始终从原始订单数据重算，不复用发布时的汇总。

样例（2026-09-01 期）：A 独享 40 元、B 独享 20 元、共享 60 元，
A 组计入 70 元、B 组计入 50 元，两组合计 120 元，与去重订单 120 元对平；
交叠用户 U1003 的 60 元在 A 组实际计入 30 元。

接口一览：

```text
GET  /api/cohort-contribution/catalog
GET  /api/cohort-contribution/views
POST /api/cohort-contribution/views
GET  /api/cohort-contribution/preview
GET  /api/cohort-contribution/views/{view_id}
GET  /api/cohort-contribution/views/{view_id}/groups/{group_key}
POST /api/cohort-contribution/cohorts/{cohort_id}/membership/refresh
```
