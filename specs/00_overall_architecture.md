# 账户系统自动升级平台总体架构设计

## 1. 项目名称

账户系统自动升级平台

---

## 2. 项目背景

账户系统升级涉及多个环境、多台服务器、多类操作，包括取包、SO 文件升级、SQL 执行、UFX 配置替换、微服务发布、定时任务发布、工作流发布等。

当前升级流程主要依赖人工操作，存在以下问题：

1. 步骤多，容易遗漏。
2. 版本包频繁更新，需要重复检查和取包。
3. 多环境机器信息不同，人工切换容易出错。
4. 升级过程缺少统一日志和标准化结果。
5. 后续自动化升级能力需要可持续扩展。

因此建设基于 Dify + FastAPI 的账户系统自动升级平台。

---

## 3. 项目目标

通过 Dify + Python FastAPI 实现账户系统升级流程自动化。

### 3.1 当前阶段目标

当前阶段优先实现：

1. 取包功能。
2. 为后续 SO 升级预留架构。

### 3.2 后续阶段目标

后续逐步扩展：

1. SO 升级。
2. SQL 升级。
3. UFX 配置替换。
4. 微服务发布。
5. 定时任务发布。
6. 工作流发布。
7. 一键串联完整升级流程。

---

## 4. 总体架构

整体调用链路如下：

```text
Dify Workflow
    ↓ HTTP Request
Account Upgrade Server（FastAPI）
    ↓
API Layer
    ↓
Service Layer
    ↓
Core Layer
    ↓
目标服务器 / 数据库 / 平台接口
```

---

## 5. 系统职责划分

### 5.1 Dify 职责

Dify 负责：

1. 用户交互。
2. 参数收集。
3. 定时触发。
4. 工作流编排。
5. 调用 FastAPI 接口。
6. 展示执行结果。

Dify 不直接执行 SSH、SCP、SQL、文件替换等底层操作。

---

### 5.2 FastAPI 服务职责

FastAPI 服务负责：

1. 接收 Dify 请求。
2. 校验请求参数。
3. 读取环境配置。
4. 执行升级逻辑。
5. 记录执行日志。
6. 返回标准化执行结果。

---

## 6. 功能模块规划

### 6.1 Package Manager

负责升级包获取。

接口规划：

```text
POST /fetch-package
```

当前阶段实现。

---

### 6.2 SO Upgrade Manager

负责 SO 文件升级。

接口规划：

```text
POST /upgrade-so
```

后续阶段实现。

---

### 6.3 SQL Upgrade Manager

负责 SQL 文件执行。

接口规划：

```text
POST /upgrade-sql
```

后续阶段实现。

---

### 6.4 UFX Manager

负责 UFX 配置文件替换。

接口规划：

```text
POST /replace-ufx
```

后续阶段实现。

---

### 6.5 Microservice Manager

负责微服务发布。

接口规划：

```text
POST /publish-microservice
```

后续阶段实现。

---

### 6.6 Schedule Task Manager

负责定时任务或项目配置发布。

接口规划：

```text
POST /publish-schedule-task
```

后续阶段实现。

---

### 6.7 Workflow Manager

负责工作流发布。

接口规划：

```text
POST /publish-workflow
```

后续阶段实现。

---

## 7. 分层设计

### 7.1 API Layer

目录：

```text
api/
```

职责：

1. 定义 FastAPI 路由。
2. 接收请求参数。
3. 调用 Service Layer。
4. 返回统一响应。

API Layer 不编写具体业务逻辑。

---

### 7.2 Service Layer

目录：

```text
services/
```

职责：

1. 编排具体业务流程。
2. 调用 Core Layer 完成 SSH、SCP、文件处理等底层动作。
3. 处理业务异常。
4. 生成业务执行结果。

---

### 7.3 Core Layer

目录：

```text
core/
```

职责：

1. 配置读取。
2. SSH/SCP 封装。
3. 日志封装。
4. 统一响应封装。
5. 通用基础能力。

---

### 7.4 Schema Layer

目录：

```text
schemas/
```

职责：

1. 定义请求参数模型。
2. 定义响应数据模型。
3. 进行基础参数校验。

---

### 7.5 Config Layer

目录：

```text
config/
```

职责：

1. 保存环境配置。
2. 管理不同环境的 IP、端口、路径、命令等信息。
3. 避免业务代码硬编码环境参数。

---

### 7.6 Specs Layer

目录：

```text
specs/
```

职责：

1. 保存项目设计文档。
2. 为 Codex 开发提供明确上下文。
3. 为后续维护提供依据。

---

## 8. 统一接口公共参数

所有业务接口尽量统一支持以下参数。

### 8.1 env

环境名称。

示例：

```text
uat1
uat2
```

---

### 8.2 version_date

版本日期。

格式：

```text
yyyymmdd
```

示例：

```text
20260529
```

---

### 8.3 force

是否强制执行。

```text
true
false
```

说明：

1. true 表示即使本地已有结果，也重新执行。
2. false 表示如果本地已有可用结果，可直接复用或返回已存在状态。

---

## 9. 统一返回格式

所有接口返回统一 JSON 结构。

### 9.1 成功返回

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

---

### 9.2 未满足执行条件

```json
{
  "status": "not_found",
  "step": "fetch_package",
  "env": "uat1",
  "version_date": "20260529",
  "message": "未发现目标资源",
  "data": {},
  "warnings": [],
  "error": null
}
```

---

### 9.3 失败返回

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

## 10. 配置管理原则

禁止在业务代码中硬编码以下内容：

1. IP 地址。
2. 端口。
3. 用户名。
4. 密码。
5. 远程目录。
6. 本地目录。
7. 执行命令。
8. 超时时间。

所有环境相关配置统一放在：

```text
config/environments.yaml
```

配置文件结构和规则详见：

```text
specs/01_environment_design.md
```

---

## 11. 项目目录结构

当前阶段采用以下 V1 项目结构：

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
│   └── health_api.py
├── core/
│   ├── config_manager.py
│   ├── ssh_manager.py
│   ├── logger.py
│   └── response.py
├── services/
│   └── package_service.py
├── schemas/
│   ├── package_schema.py
│   └── common_schema.py
└── logs/
```

---

## 12. 目录和文件说明

### 12.1 app.py

FastAPI 应用入口。

负责：

1. 创建 FastAPI app。
2. 注册 API 路由。
3. 提供服务启动入口。

---

### 12.2 requirements.txt

项目 Python 依赖文件。

用于安装运行依赖。

---

### 12.3 config/environments.example.yaml

环境配置示例文件。

可以提交代码仓库。

不建议包含真实密码。

---

### 12.4 config/environments.yaml

真实环境配置文件。

用于本地实际运行。

不建议提交代码仓库。

---

### 12.5 specs/

项目设计文档目录。

当前包含：

1. 总体架构设计。
2. 环境配置设计。
3. 取包功能设计。

---

### 12.6 api/package_api.py

取包接口路由文件。

负责定义：

```text
POST /fetch-package
```

---

### 12.7 api/health_api.py

健康检查接口路由文件。

负责定义：

```text
GET /health
```

用于验证 FastAPI 服务是否正常。

---

### 12.8 core/config_manager.py

环境配置读取模块。

负责：

1. 读取 environments.yaml。
2. 根据 env 获取对应环境配置。
3. 校验必要配置是否存在。

---

### 12.9 core/ssh_manager.py

SSH/SCP 基础能力封装。

负责：

1. 建立 SSH 连接。
2. 执行远程命令。
3. 下载文件。
4. 上传文件。
5. 关闭连接。

---

### 12.10 core/logger.py

日志模块。

负责：

1. 初始化日志。
2. 输出统一格式日志。
3. 按模块记录日志文件。

---

### 12.11 core/response.py

统一响应封装模块。

负责生成标准 JSON 返回结构。

---

### 12.12 services/package_service.py

取包业务逻辑模块。

负责：

1. 读取取包配置。
2. 拼接远程目录。
3. 检查远程目录。
4. 远程压缩升级包。
5. 下载压缩包。
6. 本地解压。
7. 返回执行结果。

---

### 12.13 schemas/package_schema.py

取包接口请求参数模型。

负责定义：

1. env。
2. year。
3. version_date。
4. force。

---

### 12.14 schemas/common_schema.py

公共 Schema 定义。

后续可用于统一响应、公共字段校验等。

---

### 12.15 logs/

日志目录。

用于保存运行日志。

---

## 13. 当前阶段开发范围

当前阶段只实现：

1. GET /health。
2. POST /fetch-package。
3. 环境配置读取。
4. SSH/SCP 封装。
5. 日志记录。
6. 统一响应格式。

当前阶段不实现：

1. SO 升级。
2. SQL 升级。
3. UFX 替换。
4. 微服务发布。
5. 定时任务发布。
6. 工作流发布。

---

## 14. 开发原则

1. 先实现可运行的最小闭环。
2. 每个功能独立设计 spec。
3. 所有功能复用统一配置、统一日志、统一返回格式。
4. 不同环境通过 env 参数切换。
5. 业务代码不直接写死机器信息。
6. 优先保证可验证、可回滚、可追踪。
7. 后续扩展功能时，优先新增 service 和 spec，不随意改动已有接口。
