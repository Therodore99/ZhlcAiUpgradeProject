# Upgrade Plan 设计说明

## 1. 文档目标

本文档说明取包完成后如何生成 manifest、diff 和 upgrade_plan。

当前阶段只生成本地计划文件，不执行 SO 升级、SQL 升级、UFX 替换、微服务发布、定时任务发布或工作流发布。

---

## 2. manifest 是什么

manifest 是一次 snapshot 中 package 目录的完整文件清单。

生成时机：

1. tar.gz 下载成功。
2. 本地按 package.encoding 解压成功。
3. 扫描 {snapshot_dir}/package 下全部文件。

manifest 文件：

```text
{snapshot_dir}/manifest.json
```

manifest 记录每个文件的：

1. relative_path
2. category
3. file_name
4. size
5. mtime
6. mtime_epoch
7. sha256

relative_path 相对 package 目录，统一使用 / 分隔。

category 根据路径和后缀判断：

1. appcom 下 .so 为 so。
2. sql 下 .sql 为 sql。
3. 其他程序/ufx 下 .xml 为 ufx。
4. 账户定时任务/.../定时任务 下 .zip 为 schedule_task。
5. 账户定时任务/.../工作流 下 .zip 为 workflow。
6. 账户定时任务/.../项目配置 下 .zip 为 project_config。
7. 其他文件为 other。

---

## 3. diff 如何判断

diff 用于比较当前 snapshot 与同一 version_date 下最近一次历史 snapshot。

历史 snapshot 查找规则：

1. version_dir = {package.local_root}/{version_date}
2. 列出 version_dir 下所有目录。
3. 排除当前 snapshot_time。
4. 按目录名倒序排序。
5. 找到最近一个包含 manifest.json 的目录。

如果找到历史 manifest：

mode = incremental

如果找不到历史 manifest：

mode = full

比较规则：

1. added：当前 manifest 有，历史 manifest 没有。
2. deleted：历史 manifest 有，当前 manifest 没有。
3. modified：两边都有相同 relative_path，但 size、mtime_epoch、sha256 任一字段变化。
4. unchanged：两边都有相同 relative_path，且 size、mtime_epoch、sha256 均未变化。

diff 文件：

```text
{snapshot_dir}/diff_from_previous.json
```

---

## 4. upgrade_plan 如何生成

upgrade_plan 根据 diff_from_previous.json 生成。

需要处理的文件：

```text
added + modified
```

按 category 分组：

1. so -> tasks.so.files
2. sql -> tasks.sql.files
3. ufx -> tasks.ufx.files
4. schedule_task -> tasks.schedule_task.files
5. workflow -> tasks.workflow.files
6. project_config -> tasks.project_config.files
7. other -> tasks.other.files

need_run 规则：

1. so/sql/ufx 只要 files 非空，need_run=true。
2. files 为空，need_run=false。

need_manual_confirm 规则：

1. sql 默认 need_manual_confirm=true。
2. 后续再扩展 SQL AI 分析和自动确认策略。

need_notify 规则：

1. schedule_task/workflow/project_config 只要 files 非空，need_notify=true。
2. other 暂时 need_notify=false。

upgrade_plan 文件：

```text
{snapshot_dir}/upgrade_plan.json
```

---

## 5. 后续功能如何使用 upgrade_plan

后续 SO 升级、SQL 升级、UFX 替换等接口不再重新扫描升级包目录，而是读取 latest.txt 指向的 snapshot，再读取 upgrade_plan.json。

### SO 升级

读取：

```text
tasks.so.files
```

如果 need_run=true，则基于 package_dir 下的相对路径找到 .so 文件并执行 SO 升级。

### SQL 升级

读取：

```text
tasks.sql.files
```

如果 need_run=true 且 need_manual_confirm=true，则先提示人工确认，再执行 SQL。

### UFX 替换

读取：

```text
tasks.ufx.files
```

如果 need_run=true，则基于 package_dir 下的 XML 文件执行 UFX 配置替换。

### 定时任务、工作流、项目配置

读取：

```text
tasks.schedule_task.files
tasks.workflow.files
tasks.project_config.files
```

当前阶段只生成 need_notify 标记，后续再接入对应平台发布能力。

---

## 6. 当前阶段边界

当前阶段只做：

1. snapshot 目录管理。
2. manifest 生成。
3. diff 生成。
4. upgrade_plan 生成。

当前阶段不做：

1. SO 实际升级。
2. SQL 实际执行。
3. UFX 实际替换。
4. 微服务发布。
5. 定时任务发布。
6. 工作流发布。
