# Fetch Package 取包功能规格说明

## 1. 功能名称

fetch_package

## 2. 功能目标

从账户系统升级包服务器获取指定版本升级包，将远程升级包目录下的全部文件压缩打包下载，并解压到本地目录。

该功能是账户系统自动升级流程的第一步。

后续 SO 升级、SQL 升级、UFX 替换等功能均依赖本功能生成的本地升级包目录。

---

## 3. 触发方式

当前支持 Dify Workflow 通过 HTTP Request 主动触发。

后续支持 Dify 定时任务触发。

---

## 4. 接口定义

接口地址：

POST /fetch-package

---

## 5. 输入参数

### env

环境名称。

示例：

uat1

uat2

---

### year

年份。

格式：

yyyy

示例：

2026

---

### version_date

版本日期。

格式：

yyyymmdd

示例：

20260529

---

### force

是否强制重新下载。

true：重新下载并覆盖已有压缩包和解压结果。

false：如果本地目录已存在，可返回已存在状态或跳过重复下载。

---

## 6. 请求示例

```json
{
  "env": "uat1",
  "year": "2026",
  "version_date": "20260529",
  "force": true
}
```

---

## 7. 配置依赖

取包功能不得硬编码以下信息：

1. 升级包服务器 IP
2. SSH 端口
3. 用户名
4. 密码
5. 远程根目录
6. 本地保存目录
7. 临时文件目录

以上内容必须通过 Environment Manager 从 config/environments.yaml 获取。

---

## 8. 远程目录拼接规则

从环境配置读取：

package.remote_root

从接口参数读取：

year

version_date

从环境配置读取：

package.package_name_template

最终远程目录规则：

{package.remote_root}/{year}/{package.package_name_template}

其中：

package_name_template 中的 {version_date} 替换为接口参数 version_date。

示例：

remote_root：

/home/hundsun/10-账户系统远期包

year：

2026

package_name_template：

账户升级包V{version_date}-小远期

version_date：

20260529

最终远程目录：

/home/hundsun/10-账户系统远期包/2026/账户升级包V20260529-小远期

---

## 9. 本地目录拼接规则

从环境配置读取：

package.local_root

从接口参数读取：

version_date

第二阶段起，本地目录采用版本目录 + 快照目录结构。

版本目录：

{package.local_root}/{version_date}

快照目录：

{package.local_root}/{version_date}/{snapshot_time}

其中 snapshot_time 格式为：

YYYYMMDD_HHMMSS

示例：

D:/账户系统UAT1升级包/20260529/20260629_190000

快照目录内部结构：

```text
{snapshot_dir}/
├── package/
├── account_upgrade_{version_date}.tar.gz
├── manifest.json
├── diff_from_previous.json
└── upgrade_plan.json
```

压缩包下载到 snapshot_dir 下，解压内容放入 snapshot_dir/package 下。

version_dir 下维护 latest.txt，内容为最新 snapshot_dir 的绝对路径。

---

## 10. 版本排期规则

账户系统每两周一个版本排期。

版本发布日期通常为排期第二周周五。

例如：

2026-06-29 至 2026-07-10 为一个版本排期，对应版本 V20260710。

后续版本例如：

V20260724

---

## 11. 自动取包计划

从每个版本排期的第一个工作日晚上 19:00 开始检查。

检查逻辑：

1. 如果远程目录已存在，则执行取包。
2. 如果远程目录不存在，则返回 not_found。
3. not_found 不视为系统异常。
4. Dify 后续在下一个工作日继续触发检查。
5. 第一次取包成功后，当前排期内每个工作日仍可继续执行取包，确保获取最新更新内容。

---

## 12. 执行流程

### 12.1 参数校验

校验 env 不为空。

校验 year 为 4 位数字。

校验 version_date 为 8 位数字。

校验 force 为布尔值。

---

### 12.2 读取环境配置

通过 Environment Manager 读取 env 对应配置。

---

### 12.3 拼接路径

拼接远程升级包目录。

拼接本地保存目录。

拼接远程临时压缩包路径。

拼接本地压缩包路径。

---

### 12.4 建立 SSH 连接

连接 package.host:package.port。

连接失败返回 failed。

失败 step：

ssh_connect

---

### 12.5 检查远程目录是否存在

远程执行：

test -d "{remote_dir}" && echo OK || echo NOT_FOUND

如果返回 NOT_FOUND，则返回：

status = not_found

---

### 12.6 远程压缩

远程执行：

cd "{remote_dir}" && tar -czf "{remote_archive}" .

remote_archive 示例：

/tmp/account_upgrade_{env}_{version_date}.tar.gz

失败 step：

remote_tar

---

### 12.7 下载压缩包

通过 SCP 下载 remote_archive 到本地。

本地压缩包示例：

D:/账户系统UAT1升级包/20260529/20260629_190000/account_upgrade_20260529.tar.gz

失败 step：

scp_download

---

### 12.8 清理远程临时文件

远程执行：

rm -f "{remote_archive}"

如果清理失败，不影响主流程，但需要写入 warnings。

---

### 12.9 本地解压

将本地压缩包解压到：

{snapshot_dir}/package

tar.gz 内中文文件名按 package.encoding 解码。

失败 step：

extract_archive

---

### 12.10 统计文件

统计 package 目录下文件数量。

检查关键目录是否存在：

1. appcom
2. sql
3. 其他程序

关键目录不存在时，不直接失败，但写入 warnings。

---

## 13. 成功返回

```json
{
  "status": "success",
  "step": "fetch_package",
  "env": "uat1",
  "version_date": "20260529",
  "message": "取包完成",
  "data": {
    "remote_dir": "/home/hundsun/10-账户系统远期包/2026/账户升级包V20260529-小远期",
    "local_dir": "D:/账户系统UAT1升级包/20260529",
    "archive_file": "D:/账户系统UAT1升级包/20260529/account_upgrade_20260529.tar.gz",
    "file_count": 100
  },
  "warnings": [],
  "error": null
}
```

---

## 14. 未发现升级包返回

```json
{
  "status": "not_found",
  "step": "fetch_package",
  "env": "uat1",
  "version_date": "20260529",
  "message": "未发现当前版本升级包目录，等待下次触发",
  "data": {
    "remote_dir": "/home/hundsun/10-账户系统远期包/2026/账户升级包V20260529-小远期"
  },
  "warnings": [],
  "error": null
}
```

---

## 15. 失败返回

```json
{
  "status": "failed",
  "step": "scp_download",
  "env": "uat1",
  "version_date": "20260529",
  "message": "取包失败",
  "data": {},
  "warnings": [],
  "error": "具体错误信息"
}
```

---

## 16. 日志要求

日志文件：

logs/fetch_package.log

每次执行记录：

1. 请求参数
2. 环境名称
3. 远程目录
4. 本地目录
5. SSH 连接结果
6. 远程目录检查结果
7. 压缩结果
8. 下载结果
9. 解压结果
10. 文件数量
11. warnings
12. 异常信息
13. 开始时间
14. 结束时间
15. 总耗时

---

## 17. 幂等要求

同一个 env + version_date 可以重复执行。

当 force = false 且本地目录已存在时：

1. 如果本地目录下已有文件，可返回 success。
2. 返回信息中需要说明本次未重新下载。

当 force = true 时：

1. 重新下载压缩包。
2. 重新解压。
3. 覆盖已有同名文件。

---

## 18. 后续功能依赖

取包成功后必须返回 package_dir。

SO 升级功能将根据 local_dir 查找：

{package_dir}/appcom

并获取其中所有 .so 文件。

---

## 19. Snapshot 目录设计

每次 force=true 执行取包时，创建新的 snapshot_time 目录，避免覆盖历史取包结果。

目录规则：

```text
version_dir = {package.local_root}/{version_date}
snapshot_dir = {version_dir}/{snapshot_time}
package_dir = {snapshot_dir}/package
```

snapshot_time 使用本地服务时间，格式为 YYYYMMDD_HHMMSS。

latest.txt 写入 version_dir/latest.txt，内容为最新 snapshot_dir 的绝对路径。

当 force=false 且 latest.txt 指向的快照可用时，可以直接返回 success，并说明本次未重新下载。

---

## 20. manifest.json 设计

解压完成后扫描 package_dir 下全部文件，生成：

```text
{snapshot_dir}/manifest.json
```

结构：

```json
{
  "env": "uat1",
  "version_date": "20260626",
  "snapshot_time": "20260629_190000",
  "package_dir": "D:/账户系统UAT1升级包/20260626/20260629_190000/package",
  "file_count": 128,
  "files": [
    {
      "relative_path": "appcom/client.so",
      "category": "so",
      "file_name": "client.so",
      "size": 2389120,
      "mtime": "2026-06-29 18:22:11",
      "mtime_epoch": 1782738131,
      "sha256": "xxx"
    }
  ]
}
```

relative_path 统一使用 / 分隔。

分类规则：

1. 路径包含 appcom 且后缀为 .so，category=so。
2. 路径包含 sql 且后缀为 .sql，category=sql。
3. 路径包含 其他程序/ufx 且后缀为 .xml，category=ufx。
4. 路径包含 账户定时任务 和 定时任务 且后缀为 .zip，category=schedule_task。
5. 路径包含 账户定时任务 和 工作流 且后缀为 .zip，category=workflow。
6. 路径包含 账户定时任务 和 项目配置 且后缀为 .zip，category=project_config。
7. 其他文件 category=other。

如果路径包含 账户定时任务，但不属于定时任务、工作流、项目配置三类目录，也归类为 other。

---

## 21. diff_from_previous.json 设计

生成当前 manifest 后，在同一个 version_dir 下查找上一个包含 manifest.json 的 snapshot。

查找规则：

1. 列出 version_dir 下所有目录。
2. 排除当前 snapshot_time。
3. 按目录名倒序排序。
4. 找到最近一个包含 manifest.json 的 snapshot。

如果找到上一个 snapshot，则 mode=incremental。

如果找不到，则 mode=full。

diff 文件路径：

```text
{snapshot_dir}/diff_from_previous.json
```

比较规则：

1. added：新 manifest 有，旧 manifest 没有。
2. deleted：旧 manifest 有，新 manifest 没有。
3. modified：relative_path 相同，但 size、mtime_epoch、sha256 任一字段变化。
4. unchanged：relative_path 相同，且 size、mtime_epoch、sha256 均未变化。

---

## 22. upgrade_plan.json 设计

根据 diff_from_previous.json 生成：

```text
{snapshot_dir}/upgrade_plan.json
```

需要处理的文件为 added + modified。

按 category 分组生成 tasks：

1. so/sql/ufx：files 非空则 need_run=true。
2. sql：need_manual_confirm 固定为 true。
3. schedule_task/workflow/project_config：files 非空则 need_notify=true。
4. other：暂不通知，need_notify=false。

upgrade_plan 只生成计划，不执行 SO、SQL、UFX 或平台发布。

---

## 23. 返回结果增强

保持统一返回格式不变，在 data 中增加：

```json
{
  "version_dir": "...",
  "snapshot_dir": "...",
  "snapshot_time": "20260629_190000",
  "package_dir": "...",
  "archive_file": "...",
  "manifest_file": "...",
  "diff_file": "...",
  "upgrade_plan_file": "...",
  "mode": "full",
  "summary": {
    "file_count": 128,
    "added_count": 1,
    "modified_count": 1,
    "deleted_count": 0,
    "unchanged_count": 126,
    "so_changed": 1,
    "sql_changed": 1,
    "ufx_changed": 0,
    "schedule_task_changed": 1,
    "workflow_changed": 1,
    "project_config_changed": 1,
    "other_changed": 0
  }
}
```

---

## 24. 日志增强

fetch_package.log 增加记录：

1. version_dir
2. snapshot_dir
3. package_dir
4. manifest_file
5. diff_file
6. upgrade_plan_file
7. mode
8. added_count
9. modified_count
10. deleted_count
11. so_changed/sql_changed/ufx_changed/schedule_task_changed/workflow_changed/project_config_changed
