# 三系统取包与 Dify 接入

## 配置迁移

运行时只读 `config/environments.yaml`。新安装从 [示例](../config/environments.example.yaml) 复制；**已有配置不要覆盖**。将原 environments.uat1/uat2 整块移到 systems.legacy_account 下，各加 enabled: true，保留原连接参数、凭据、local_root 以及 so/database/ufx 等块。仅将 remote_root 更新成版本目录的直接父目录，添加 category_profile 和 encoding，再按示例加入另外两个系统。不会自动迁移目录、改写历史 manifest 或计算年份。

| system / env | remote_root（以现场为准） | 目录模板 | 编码 |
| --- | --- | --- | --- |
| legacy_account / uat1 | /home/hundsun/10-账户系统远期包/2026 | 账户升级包V{version_date} - 小远期 | gbk |
| legacy_account / uat2 | /home/hundsun/01-账户系统升级/2026升级包 | 账户升级包V{version_date} | gbk |
| bus / uat1、uat2 | /home/hundsun/02-总线升级包/2026总线升级包 | 总线升级包V{version_date} | 示例 gbk，现场确认 |
| xinchuang_account / uat1、uat2 | /home/hundsun/21-2025账户信创升级 | V{version_date} | utf-8 |

信创 UAT2 禁用。各组合分别填写 host、port、protocol、凭据、remote_temp_dir、超时和独占的 local_root。启用环境使用 SSH 密码认证；可用 password_env 引用服务进程环境变量。不要将凭据传入 Dify。三系统共用 Paramiko/SCP；命令和归档名使用对应编码。

## 接口和快照

`POST /fetch-package` 请求示例：

```json
{"system":"xinchuang_account","env":"uat1","version_date":"20261120","force":true,"debug":false}
```

system 省略为 legacy_account，env 必选，version_date 为八位数字；旧 year 可传但不影响路径。force/debug 默认 false。列出父目录后，精确匹配模板；仅老账户允许唯一的空格差异，使用远程真实名称压缩。信创不存在正常版就 not_found，即使有 _master；不会匹配相近日或其他后缀。

版本目录仍为 local_root/version_date。其下按秒分配快照并保留 package、原始 tar.gz 和三个 JSON；latest.txt 记录最新成功目录的绝对路径。每个版本有独立文件锁，同时取同一版本返回 skipped；不同环境即使共享升级包服务器也使用不同临时归档名。force=false 可复用当前组合最近成功的快照。旧 manifest 缺 system 时仅视为老账户。第一次 full，后续按 relative_path 比较 size、mtime_epoch、sha256，deleted 只记差异。

## 策略和返回

| 系统 | 分类与计划 |
| --- | --- |
| 老账户 | 保持原 so/sql/ufx、微服务 ZIP 和账户定时任务下三类 ZIP 的规则；其余 other。 |
| 总线 | ZIP（不区分后缀大小写）为 bus_component，仅 need_notify；非 ZIP 为 other，不发通知。 |
| 信创 | 一级目录 AcctDsrw、Config、Sql、微服务、特殊插件、路由配置文件分别对应 schedule_task、config、sql、microservice、plugin、route_config。所有后缀参与；其他未匹配文件为 other，不执行。 |

除信创升级说明外，任务文件来自 added + modified；Config 和 SQL 使用 need_run，SQL 还须人工确认；信创其他任务只通知。一级目录“升级说明”归 documentation，以**当前 manifest 的全部说明文件**决定 need_notify，包括未变化文件。只列路径，不读取指令或调用大模型。各系统的计划独立，无任何执行器。

例如信创第二次取包只有 Config/a.ini 变化，但仍含说明，upgrade_plan.json 的两个任务节选：

```json
{
  "config":{"need_run":true,"files":["Config/a.ini"]},
  "documentation":{"need_notify":true,"files":["升级说明/升级说明.txt"]}
}
```

响应顶层：status、step、system、env、version_date、message、data、warnings、error。success 的 data 保留快照、目录、归档、三个 JSON 路径及 mode；summary 包含下表全部 Number 字段及 upgrade_notes_present、upgrade_notes_files（字符串数组）。不适用字段为 0、false 或空数组。debug=true 时可看候选；false 不附带目录名称列表。

not_found 表示版本未到；skipped 表示该环境未开放或同版本正在取包；failed 保留失败阶段和 error（含缺配置、连接、下载、解压或元数据失败）。非法请求返回 HTTP 422 的统一失败结构。不得把 HTTP 200 等同于业务成功。

## Dify 手动配置

仓库没有 Dify DSL。以下配置在公司平台的工作流副本中完成，再验证并发布。三个系统共用以下节点：

1. **开始**：system 下拉（legacy_account 默认、bus、xinchuang_account），env 下拉（uat1、uat2），version_date 字符串，force/debug 布尔默认 false。移除必填 years/year；预留 dry_run_so、execute_so 不接取包节点。
2. **HTTP_取包并生成升级计划**：POST 到现有服务的 /fetch-package，Content-Type 为 application/json。用变量选择器绑定上述五个变量，字符串为 JSON 字符串，布尔值不要加引号。请求形状见上面的 JSON。配置能覆盖取包耗时的 HTTP 超时。HTTP 节点自身超时或不可达另走失败输出。
3. **代码节点_解析取包结果**：Python 输入 body 绑定 HTTP.body。使用 [完整独立代码](../dify/parse_fetch_result.py)，支持字符串或对象，按下表声明输出。仓库无线上自定义输出清单；若现场还有专用字段，保留原提取表达式、返回键和声明，再合入新增字段，不要删除下游绑定。
4. **条件分支_取包状态**：success 进入说明判断；not_found 输出版本未到和 message；skipped 输出环境与跳过原因；failed/其他输出 step、message、error。
5. **条件分支_是否存在升级说明**：在 success 下比较 Boolean upgrade_notes_present == true。true 的“输出_发现升级说明”绑定 system、env、version_date、snapshot_time、upgrade_notes_count、upgrade_notes_files_text、package_dir，并显示“本次升级包包含升级说明文件，请在后续升级前人工查看相关内容。”false 不显示提醒。两条路径都输出取包结果与变化统计；若平台的输出节点会结束运行，在 true 的最终输出一并展示提醒与统计。无需外部插件。

| 输出类型 | 精确变量名 |
| --- | --- |
| String | status, step, system, env, version_date, message, error, mode, snapshot_time, snapshot_dir, version_dir, package_dir, archive_file, manifest_file, diff_file, upgrade_plan_file, local_dir, remote_dir, actual_remote_dir, expected_remote_dir, parent_dir, encoding, warnings_text, upgrade_notes_files_text |
| Number | file_count, added_count, modified_count, deleted_count, unchanged_count, so_changed, sql_changed, ufx_changed, microservice_changed, schedule_task_changed, workflow_changed, project_config_changed, other_changed, config_changed, bus_component_changed, plugin_changed, route_config_changed, upgrade_notes_count |
| Boolean | upgrade_notes_present |

## 验收顺序

1. 运行服务安装 requirements.txt；本地验收安装 requirements-test.txt，再运行 `python -m compileall app.py api core schemas services` 与 `python -m unittest discover -s tests -v`。
2. 启动 `python -m uvicorn app:app`，检查 GET /health。验证五个启用组合的实际父目录、中文名称、编码、凭据、临时目录可写及本地磁盘权限。信创 UAT2 须直接 skipped。
3. 同一组合 force=true 两次，确认独立快照、首次 full（全新版本目录）、随后 incremental；force=false 复用 latest。其他系统或环境不能成为基线。
4. 检查总线 ZIP、信创 Config 和说明清单；只有 _master 时须 not_found。即使第二次零变化，说明仍提醒；包内无说明则不提醒。
5. 在 Dify 副本分别验证四个状态和有/无说明两条成功分支；确认最终输出包含统计后再发布工作流。本验收不执行任何升级。
