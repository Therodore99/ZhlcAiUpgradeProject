import codecs
import os
from pathlib import Path
from typing import Any, Optional, Union

import yaml


class ConfigError(Exception):
    """Raised when runtime configuration is missing or invalid."""


class EnvironmentDisabled(ConfigError):
    pass


class ConfigManager:
    def __init__(self, config_path: Union[str, Path] = "config/environments.yaml"):
        self.config_path = Path(config_path)
        self._config: Optional[dict[str, Any]] = None

    def load(self) -> dict[str, Any]:
        if self._config is not None:
            return self._config

        if not self.config_path.exists():
            raise ConfigError(
                "缺少运行配置文件 config/environments.yaml，请先复制 "
                "config/environments.example.yaml 生成 config/environments.yaml，"
                "并填写对应环境的服务器、路径、用户名和密码。"
            )

        try:
            with self.config_path.open("r", encoding="utf-8") as file:
                config = yaml.safe_load(file) or {}
        except yaml.YAMLError:
            raise ConfigError("配置文件 YAML 解析失败，请检查缩进和字段格式。") from None
        except OSError as exc:
            raise ConfigError(f"配置文件读取失败: {exc}") from exc

        if not isinstance(config, dict) or not isinstance(config.get("systems"), dict):
            raise ConfigError("配置缺少 systems 对象，请按 environments.example.yaml 迁移旧配置。")

        self._config = config
        return config

    def get_environment(self, system: str, env: str) -> dict[str, Any]:
        environments = self.load()["systems"].get(system)
        if not isinstance(environments, dict):
            raise ConfigError(f"未找到系统配置: {system}")
        env_config = environments.get(env)
        if not isinstance(env_config, dict):
            raise ConfigError(f"未找到环境配置: {system}/{env}")
        if not isinstance(env_config.get("enabled"), bool):
            raise ConfigError(f"{system}/{env} 的 enabled 需为布尔值。")
        if not env_config["enabled"]:
            raise EnvironmentDisabled(f"{system}/{env} 暂未开放取包。")
        return env_config

    def get_package_config(self, system: str, env: str) -> dict[str, Any]:
        env_config = self.get_environment(system, env)
        package_config = env_config.get("package")
        if not isinstance(package_config, dict):
            raise ConfigError(f"环境 {env} 缺少 package 配置。")
        package_config = dict(package_config)
        for key in ("username", "password"):
            if key + "_env" in package_config:
                name = package_config[key + "_env"]
                if not isinstance(name, str) or not name:
                    raise ConfigError(f"{system}/{env} 的 {key}_env 必须为环境变量名。")
                package_config[key] = os.getenv(name)

        required_fields = [
            "host",
            "port",
            "protocol",
            "username",
            "password",
            "category_profile",
            "encoding",
            "remote_root",
            "package_name_template",
            "remote_temp_dir",
            "local_root",
            "connect_timeout",
            "command_timeout",
        ]
        missing_fields = [
            field
            for field in required_fields
            if field not in package_config or package_config.get(field) in (None, "")
        ]
        if missing_fields:
            raise ConfigError(f"环境 {env} 的 package 配置缺少必填项: {', '.join(missing_fields)}")

        for key in required_fields:
            value = package_config[key]
            if key in ("port", "connect_timeout", "command_timeout"):
                if not str(value).isascii() or not str(value).isdigit() or int(value) < 1:
                    raise ConfigError(f"{system}/{env} 的 {key} 必须为正整数。")
            elif not isinstance(value, str):
                raise ConfigError(f"{system}/{env} 的 {key} 必须为字符串。")
        if package_config.get("protocol") != "ssh":
            raise ConfigError(f"环境 {env} 的 package.protocol 当前仅支持 ssh。")

        if package_config["category_profile"] != system:
            raise ConfigError(f"{system}/{env} 的 category_profile 必须与 system 一致。")
        template = package_config["package_name_template"]
        if not package_config["remote_root"].startswith("/") or "{" in package_config["remote_root"]:
            raise ConfigError("remote_root 必须是无模板的远程绝对路径。")
        if ("{version_date}" not in template or "/" in template
                or any(c in template.replace("{version_date}", "") for c in "{}")):
            raise ConfigError("package_name_template 必须为只包含 {version_date} 占位符的目录名。")
        if system == "xinchuang_account" and template != "V{version_date}":
            raise ConfigError("信创只支持正常版本目录 V{version_date}。")
        root = Path(package_config["local_root"]).resolve()
        for other_system, environments in self.load()["systems"].items():
            if not isinstance(environments, dict):
                continue
            for other_env, settings in environments.items():
                if (other_system, other_env) == (system, env) or not isinstance(settings, dict):
                    continue
                other_package = settings.get("package")
                other_root = other_package.get("local_root") if isinstance(other_package, dict) else None
                if isinstance(other_root, str) and other_root and Path(other_root).resolve() == root:
                    raise ConfigError(f"{system}/{env} 与 {other_system}/{other_env} 的 local_root 重复。")
        try:
            codecs.lookup(package_config["encoding"])
        except LookupError as exc:
            raise ConfigError(
                f"环境 {env} 的 package.encoding 无效: {package_config['encoding']}"
            ) from exc

        return package_config
