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
4. 密码可为空，后续支持从环境变量读取。

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

## 5. 配置文件示例结构

```yaml
environments:
  uat1:
    description: "账户系统 UAT1 环境"

    package:
      host: "10.189.145.11"
      port: 10022
      protocol: "ssh"
      username: ""
      password: ""
      remote_root: "/home/hundsun/10-账户系统远期包"
      package_name_template: "账户升级包V{version_date}-小远期"
      remote_temp_dir: "/tmp"
      local_root: "D:/账户系统UAT1升级包"
      connect_timeout: 20
      command_timeout: 300

    so:
      host: "10.187.96.127"
      port: 10022
      protocol: "ssh"
      username: ""
      password: ""
      remote_appcom_dir: "/home/hundsun/appcom"
      remote_workspace_dir: "/home/hundsun/workspace"
      pre_command: "ks"
      start_command: "./runall"
      connect_timeout: 20
      command_timeout: 300

    database:
      host: "10.187.98.180"
      port: 1521
      username: ""
      password: ""
      service_name: ""

    ufx:
      host: "10.187.96.133"
      port: 445
      protocol: "smb"
      workspace_dir: "D:/fbase-ufx2/workspace"

    microservice:
      host: "10.187.128.52"
      port: 8081
      protocol: "http"

    schedule_task:
      host: "10.184.129.78"
      port: 8088
      protocol: "http"

    workflow:
      host: "10.187.128.143"
      port: 8088
      protocol: "http"

  uat2:
    description: "账户系统 UAT2 环境"

    package:
      host: "10.189.145.11"
      port: 10022
      protocol: "ssh"
      username: ""
      password: ""
      remote_root: "/home/hundsun/10-账户系统远期包"
      package_name_template: "账户升级包V{version_date}-小远期"
      remote_temp_dir: "/tmp"
      local_root: "D:/账户系统UAT2升级包"
      connect_timeout: 20
      command_timeout: 300

    so:
      host: "10.144.1.22"
      port: 10022
      protocol: "ssh"
      username: ""
      password: ""
      remote_appcom_dir: "/home/hundsun/appcom"
      remote_workspace_dir: "/home/hundsun/workspace"
      pre_command: "ks"
      start_command: "./runall"
      connect_timeout: 20
      command_timeout: 300

    database:
      host: "10.144.10.11"
      port: 1521
      username: ""
      password: ""
      service_name: ""

    ufx:
      host: "10.144.1.23"
      port: 445
      protocol: "smb"
      workspace_dir: "D:/fbase-ufx2/workspace"

    microservice:
      host: "10.144.1.25"
      port: 8081
      protocol: "http"

    schedule_task:
      host: "10.144.2.93"
      port: 8088
      protocol: "http"

    workflow:
      host: "10.144.1.28"
      port: 8088
      protocol: "http"
```

---

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

/home/hundsun/10-账户系统远期包

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

### load_config()

读取 config/environments.yaml。

如果文件不存在，提示用户复制 environments.example.yaml。

### get_env_config(env)

根据 env 获取完整环境配置。

### get_package_config(env)

获取取包配置。

### get_so_config(env)

获取 SO 升级配置。

---

## 9. 环境变量覆盖要求

后续可支持使用环境变量覆盖敏感信息。

示例：

PACKAGE_USERNAME

PACKAGE_PASSWORD

SO_USERNAME

SO_PASSWORD

优先级：

1. 环境变量
2. environments.yaml
3. 默认空值

---

## 10. 错误处理

当 env 不存在时，返回明确错误：

指定环境不存在：{env}

当配置字段缺失时，返回明确错误：

环境配置缺少字段：{field_name}
