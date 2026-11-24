# 环境配置设计说明

## 1. 文档目标

本文档用于说明账户系统自动升级平台的环境配置设计。

该文档不是最终运行配置文件，而是用于指导 Codex 生成：

config/environments.example.yaml

以及配置读取模块：

core/config_manager.py

最终实际运行时使用：

config/environments.yaml

---

## 2. 设计原则

业务代码不得硬编码环境参数。

以下内容必须从配置文件读取：

1. 服务器 IP
2. 端口
3. 协议
4. 用户名
5. 密码
6. 远程目录
7. 本地目录
8. 执行命令
9. 超时时间

---

## 3. 配置文件位置

示例配置文件：

config/environments.example.yaml

真实配置文件：

config/environments.yaml

说明：

1. environments.example.yaml 可提交代码仓库。
2. environments.yaml 用于本地真实运行。
3. environments.yaml 不建议提交代码仓库。
4. 示例不含凭据。启用环境可使用 password_env、username_env 指定环境变量名。

---

## 4. 环境结构

系统至少支持：

1. uat1
2. uat2

后续可扩展：

1. sit
2. dev
3. prod

---

## 5. 三系统配置结构

配置路径为 `systems.<system>.<env>`，包含布尔 `enabled` 和 `package`，老账户原 SO/database/UFX 等块仍与 package 并列。完整六套配置见 [示例 YAML](../config/environments.example.yaml)。

- legacy_account：UAT1 小远期、UAT2 生产包，分别配置完整父目录，使用 GBK。
- bus：两环境允许共用远端来源，但必须分别配置 local_root；编码现场核实。
- xinchuang_account：UTF-8，UAT1 开放；UAT2 enabled=false，直接 skipped，不读取凭据、不连接其他环境。
- 每个组合使用独立 local_root，隔离 snapshot、latest.txt 和 diff；category_profile 与 system 一致。缺少配置返回 failed/config，不回退。
- Dify 无需传 year。路径中的年份是实际目录名的一部分，由运维按需维护。

## 6. Package 配置说明

package 用于取包功能。

字段说明：

### host

升级包服务器 IP。

### port

SSH 端口。

### protocol

连接协议。

当前固定为 ssh。

### username

SSH 用户名。

### password

SSH 密码。

### remote_root

升级包根目录。

例如：

/home/hundsun/10-账户系统远期包/2026

### package_name_template

升级包目录名称模板。

例如：

账户升级包V{version_date}-小远期

### remote_temp_dir

远程临时压缩文件目录。

例如：

/tmp

### local_root

本地升级包保存根目录。

例如：

D:/账户系统UAT1升级包

### connect_timeout

连接超时时间。

### command_timeout

远程命令执行超时时间。

---

## 7. SO 配置说明

so 用于 SO 升级功能。

字段说明：

### host

SO 目标服务器 IP。

### port

SSH 端口。

### remote_appcom_dir

远程 SO 文件目录。

### remote_workspace_dir

远程启动目录。

### pre_command

升级后执行的预处理命令。

例如：

ks

### start_command

启动命令。

例如：

./runall

---

## 8. Environment Manager 要求

Codex 需要实现：

core/config_manager.py

提供以下能力：

### load()

读取 config/environments.yaml。

如果文件不存在，提示用户复制 environments.example.yaml。

### get_environment(system, env) / get_package_config(system, env)

前者检查配置与启用状态，后者校验选中环境的取包字段。本期不读取执行模块配置。

## 9. 凭据

支持 YAML 中原有 username/password 或显式的 username_env/password_env。设置变量名后，必须从对应环境变量取得非空值，缺失即报错，不回退。不要将真实配置提交到仓库。

## 10. 错误处理

当 env 不存在时，返回明确错误：

指定环境不存在：{env}

当配置字段缺失时，返回明确错误：

环境配置缺少字段：{field_name}
