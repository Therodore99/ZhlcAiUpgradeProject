# 账户系统自动升级平台总体架构设计

## 1. 项目名称

账户系统自动升级平台

## 2. 项目目标

通过 Dify + Python FastAPI 实现账户系统升级流程自动化，减少人工重复操作，提升升级效率、准确性和可追溯性。

当前阶段优先实现：

1. 取包功能
2. SO 升级功能

后续逐步扩展：

1. SQL 升级
2. UFX 配置替换
3. 微服务发布
4. 定时任务发布
5. 工作流发布

---

## 3. 总体架构

整体架构如下：

Dify Workflow
→ HTTP Request
→ Account Upgrade Server（FastAPI）
→ Environment Manager
→ Upgrade Services
→ 目标服务器 / 数据库 / 平台接口

---

## 4. 系统职责划分

### 4.1 Dify 职责

Dify 负责：

1. 用户交互
2. 参数收集
3. 定时触发
4. 工作流编排
5. 调用 FastAPI 接口
6. 展示执行结果

Dify 不直接执行 SSH、SCP、SQL、文件替换等底层操作。

---

### 4.2 FastAPI 服务职责

FastAPI 服务负责：

1. 接收 Dify 请求
2. 校验请求参数
3. 读取环境配置
4. 执行升级逻辑
5. 记录日志
6. 返回标准化结果

---

## 5. 功能模块规划

### 5.1 Package Manager

负责升级包获取。

接口：

POST /fetch-package

---

### 5.2 SO Upgrade Manager

负责 SO 文件升级。

接口：

POST /upgrade-so

---

### 5.3 SQL Upgrade Manager

负责 SQL 文件执行。

接口：

POST /upgrade-sql

---

### 5.4 UFX Manager

负责 UFX 配置文件替换。

接口：

POST /replace-ufx

---

### 5.5 Microservice Manager

负责微服务发布。

接口：

POST /publish-microservice

---

### 5.6 Workflow Manager

负责工作流发布。

接口：

POST /publish-workflow

---

## 6. 统一接口参数

所有接口尽量统一使用以下公共参数：

### env

环境名称。

示例：

uat1

uat2

---

### version_date

版本日期。

格式：

yyyymmdd

示例：

20260529

---

### force

是否强制执行。

true：即使本地已有结果，也重新执行。

false：如果本地已有结果，可直接复用或返回已存在状态。

---

## 7. 统一返回格式

### 成功返回

```json
{
  "status": "success",
  "step": "fetch_package",
  "env": "uat1",
  "version_date": "20260529",
  "message": "执行成功",
  "data": {},
  "warnings": [],
  "error": null
}
```

### 未满足执行条件

```json
{
  "status": "not_found",
  "step": "fetch_package",
  "env": "uat1",
  "version_date": "20260529",
  "message": "未发现升级包目录",
  "data": {},
  "warnings": [],
  "error": null
}
```

### 失败返回

```json
{
  "status": "failed",
  "step": "fetch_package",
  "env": "uat1",
  "version_date": "20260529",
  "message": "执行失败",
  "data": {},
  "warnings": [],
  "error": "具体错误信息"
}
```

---

## 8. 配置管理原则

禁止在业务代码中硬编码：

1. IP 地址
2. 端口
3. 用户名
4. 密码
5. 远程目录
6. 本地目录
7. 执行命令

所有环境相关配置统一放在：

config/environments.yaml

配置文件结构和规则详见：

specs/01_environment_design.md

---

## 9. 建议项目结构

```text
account_upgrade_server/
├── app.py
├── requirements.txt
├── config/
│   ├── environments.example.yaml
│   └── environments.yaml
├── specs/
│   ├── 00_overall_architecture.md
│   ├── 01_environment_design.md
│   └── 02_fetch_package_spec.md
├── api/
│   ├── package_api.py
│   ├── so_api.py
│   └── health_api.py
├── core/
│   ├── config_manager.py
│   ├── response.py
│   └── logger.py
├── services/
│   ├── ssh_service.py
│   ├── package_service.py
│   └── so_service.py
├── schemas/
│   ├── package_schema.py
│   └── common_schema.py
├── utils/
│   ├── file_utils.py
│   └── date_utils.py
└── logs/
```

---

## 10. 开发原则

1. 先实现可运行的最小闭环。
2. 每个功能独立设计 spec。
3. 所有功能复用统一配置、统一日志、统一返回格式。
4. 不同环境通过 env 参数切换。
5. 业务代码不直接写死机器信息。
6. 优先保证可验证、可回滚、可追踪。
