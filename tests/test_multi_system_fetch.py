import io
import json
import os
import shlex
import tarfile
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from unittest.mock import MagicMock, patch

import yaml
from fastapi.testclient import TestClient

from app import app
from core.config_manager import ConfigManager
from core.file_manifest import categorize_file
from dify.parse_fetch_result import main as parse_result


DATE = "20261120"
XC = "xinchuang_account"


class FetchTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enter_tempdir())
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        config = yaml.safe_load(Path("config/environments.example.yaml").read_text(encoding="utf-8"))
        self.settings = config["systems"]
        for system, environments in self.settings.items():
            for env, settings in environments.items():
                settings["package"].update(host="fixture.invalid", username="fixture",
                                           password_env="FETCH_TEST_PASSWORD",
                                           local_root=str(self.root / system / env))
        config_path = self.root / "config.yaml"
        config_path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
        self.config = ConfigManager(config_path)
        self.patcher(patch.dict(os.environ, FETCH_TEST_PASSWORD="test-only"))
        self.patcher(patch("services.package_service.ConfigManager", return_value=self.config))
        ssh_class = self.patcher(patch("core.ssh_manager.paramiko.SSHClient"))
        self.ssh = ssh_class.return_value
        self.ssh.exec_command.side_effect = self.remote_command
        scp = self.patcher(patch("core.ssh_manager.SCPClient"))
        scp.return_value.__enter__.return_value.get.side_effect = self.download
        self.files = {}
        self.commands = []
        self.use_remote(XC)

    def enter_tempdir(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        return temp.name

    def patcher(self, obj):
        result = obj.start()
        self.addCleanup(obj.stop)
        return result

    def use_remote(self, system, env="uat1"):
        package = self.settings[system][env]["package"]
        self.encoding = package["encoding"]
        self.parent = package["remote_root"]
        self.name = package["package_name_template"].format(version_date=DATE)
        self.listing = ["./" + self.name]

    def remote_command(self, command, timeout):
        command = command.decode(self.encoding)
        self.commands.append(command)
        output = ""
        if "find ." in command:
            self.assertIn("cd " + shlex.quote(self.parent) + " && find", command)
            output = "\n".join(self.listing)
        elif "tar -czf" in command:
            self.assertIn("cd " + shlex.quote(self.parent + "/" + self.name), command)
        else:
            self.assertTrue(command.startswith("rm -f "))
        stdout = MagicMock()
        stdout.read.return_value = output.encode(self.encoding)
        stdout.channel.recv_exit_status.return_value = 0
        return MagicMock(), stdout, io.BytesIO()

    def download(self, source, target):
        with tarfile.open(target, "w:gz", encoding=self.encoding, format=tarfile.GNU_FORMAT) as archive:
            for name, data in self.files.items():
                entry = tarfile.TarInfo(name)
                entry.size = len(data)
                entry.mtime = 1234567890
                archive.addfile(entry, io.BytesIO(data))

    def fetch(self, system=XC, env="uat1", **kwargs):
        body = dict(env=env, version_date=DATE, force=True)
        if system is not None:
            body["system"] = system
        body.update(kwargs)
        return self.client.post("/fetch-package", json=body)

    def success(self, *args, **kwargs):
        response = self.fetch(*args, **kwargs)
        self.assertEqual(response.status_code, 200)
        obj = response.json()
        self.assertEqual(obj["status"], "success", obj)
        return obj["data"]

    def metadata(self, data, key):
        return json.loads(Path(data[key]).read_text(encoding="utf-8"))

    def test_health_validation_and_disabled(self):
        self.assertEqual(self.client.get("/health").json()["status"], "success")
        for kwargs in (dict(system="unknown"), dict(env="uat3"), dict(version_date="2026xxxx")):
            response = self.fetch(**kwargs)
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json()["step"], "request_validation")
        disabled = self.fetch(env="uat2").json()
        self.assertEqual((disabled["status"], disabled["system"]), ("skipped", XC))
        self.assertFalse((self.root / XC / "uat2").exists())
        self.ssh.connect.assert_not_called()

    def test_bad_configuration_no_fallback(self):
        cfg = self.config.load()["systems"]
        cfg["bus"]["uat1"]["package"]["local_root"] = cfg[XC]["uat1"]["package"]["local_root"]
        self.assertIn("local_root", self.fetch().json()["error"])
        del cfg["bus"]["uat1"]
        self.assertEqual(self.fetch("bus").json()["step"], "config")
        del cfg["bus"]
        self.assertIn("bus", self.fetch("bus").json()["error"])
        with patch.dict(os.environ, FETCH_TEST_PASSWORD=""):
            self.assertIn("password", self.fetch().json()["error"])
        self.ssh.connect.assert_not_called()

    def test_legacy_old_request_and_categories(self):
        categories = {
            "appcom/核心.so": "so", "sql/补丁.sql": "sql", "其他程序/ufx/业务.xml": "ufx",
            "微服务/服务.zip": "microservice", "账户定时任务/版本/定时任务/a.zip": "schedule_task",
            "账户定时任务/版本/工作流/a.zip": "workflow", "账户定时任务/版本/项目配置/a.zip": "project_config",
            "账户定时任务/版本/说明.zip": "other",
        }
        self.files = dict.fromkeys(categories, b"data")
        for env in ("uat1", "uat2"):
            self.use_remote("legacy_account", env)
            self.name = self.name.replace(" ", "") + " "
            self.listing = ["./账户升级包V" + DATE + "-大远期", "./" + self.name]
            data = self.success(None, env, year="1999")
            self.assertEqual(data["encoding"], "gbk")
            self.assertEqual(data["actual_remote_dir"], self.parent + "/" + self.name)
            self.assertEqual(data["mode"], "full")
            manifest = self.metadata(data, "manifest_file")
            self.assertEqual({f["relative_path"]: f["category"] for f in manifest["files"]}, categories)
            self.assertEqual(data["summary"]["microservice_changed"], 1)

    def test_xinchuang_incremental_and_presence(self):
        categories = {
            "Config/参数.ini": "config", "AcctDsrw/job.zip": "schedule_task", "Sql/子目录/a.sql": "sql",
            "特殊插件/a.so": "plugin", "路由配置文件/a.xml": "route_config", "微服务/s.zip": "microservice",
            "升级说明/本次.txt": "documentation", "Config.txt": "other", "x/Config/a.ini": "other",
        }
        self.files = dict.fromkeys(categories, b"v1")
        self.listing.insert(0, "./" + self.name + "_master")
        full = self.success(debug=True)
        self.assertEqual(full["mode"], "full")
        self.assertEqual(len(full["candidates"]), 2)
        manifest = self.metadata(full, "manifest_file")
        self.assertEqual({f["relative_path"]: f["category"] for f in manifest["files"]}, categories)
        self.assertEqual(categorize_file(r"Config\参数.ini", XC), "config")
        self.assertEqual(categorize_file("Config", XC), "other")
        self.files["Config/参数.ini"] = b"v2"
        del self.files["微服务/s.zip"]
        incremental = self.success()
        self.assertFalse(incremental["candidates"])
        self.assertEqual(incremental["mode"], "incremental")
        plan = self.metadata(incremental, "upgrade_plan_file")
        self.assertEqual(plan["system"], XC)
        self.assertEqual(plan["tasks"]["config"], {"need_run": True, "files": ["Config/参数.ini"]})
        self.assertTrue(plan["tasks"]["sql"]["need_manual_confirm"])
        self.assertFalse(plan["tasks"]["microservice"]["need_notify"])
        self.assertTrue(plan["tasks"]["documentation"]["need_notify"])
        self.assertEqual(incremental["summary"]["upgrade_notes_files"], ["升级说明/本次.txt"])
        self.assertEqual(incremental["summary"]["deleted_count"], 1)
        self.assertEqual(self.metadata(incremental, "diff_file")["base_snapshot"], full["snapshot_time"])
        self.assertEqual(self.metadata(full, "manifest_file"), manifest)
        self.ssh.connect.reset_mock()
        cached = self.success(force=False)
        self.assertEqual(cached["summary"], incremental["summary"])
        self.ssh.connect.assert_not_called()
        del self.files["升级说明/本次.txt"]
        final = self.success()
        self.assertFalse(final["summary"]["upgrade_notes_present"])
        self.assertEqual(self.metadata(final, "upgrade_plan_file")["tasks"]["documentation"],
                         {"need_notify": False, "files": []})

    def test_master_only(self):
        self.listing = ["./" + self.name + "_master"]
        result = self.fetch().json()
        self.assertEqual(result["status"], "not_found")
        self.assertEqual(len(self.commands), 1)

    def test_bus_snapshot_isolation(self):
        self.files = {"微服务/组件.ZIP": b"zip", "版本.txt": b"notes"}
        parents = set()
        for env in ("uat1", "uat2"):
            self.use_remote("bus", env)
            parents.add(self.parent)
            data = self.success("bus", env)
            self.assertEqual(data["mode"], "full")
            self.assertEqual(Path(data["snapshot_dir"]).parents[1], self.root / "bus" / env)
            self.assertEqual(Path(data["version_dir"], "latest.txt").read_text(), str(Path(data["snapshot_dir"]).resolve()))
            self.assertEqual(data["summary"]["bus_component_changed"], 1)
            self.assertEqual(data["summary"]["microservice_changed"], 0)
            self.assertEqual(self.metadata(data, "upgrade_plan_file")["tasks"],
                             {"bus_component": {"need_notify": True, "files": ["微服务/组件.ZIP"]}})
        self.assertEqual(len(parents), 1)
        self.use_remote(XC)
        self.assertEqual(self.success()["mode"], "full")

    def test_concurrent_fetch_does_not_touch_inflight_snapshot(self):
        entered, finish = Event(), Event()
        def slow_connect(**kwargs):
            entered.set()
            self.assertTrue(finish.wait(5))
        self.ssh.connect.side_effect = slow_connect
        with ThreadPoolExecutor(1) as pool:
            first = pool.submit(self.fetch)
            try:
                self.assertTrue(entered.wait(5))
                self.assertEqual(self.fetch().json()["status"], "skipped")
            finally:
                finish.set()
            self.assertEqual(first.result().json()["status"], "success")
        self.assertEqual(len(list(self.root.rglob("manifest.json"))), 1)

    def test_old_legacy_snapshot_and_misdirected_latest(self):
        self.use_remote("legacy_account")
        full = self.success(None)
        path = Path(full["manifest_file"])
        old = self.metadata(full, "manifest_file")
        del old["system"]
        path.write_text(json.dumps(old), encoding="utf-8")
        self.assertEqual(self.success(None, force=False)["snapshot_time"], full["snapshot_time"])
        self.assertEqual(self.success(None)["mode"], "incremental")
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), old)
        other = self.root / "bus" / "uat1" / DATE
        other.mkdir(parents=True)
        (other / "latest.txt").write_text(full["snapshot_dir"], encoding="utf-8")
        self.ssh.connect.reset_mock()
        self.assertEqual(self.fetch("bus", force=False).json()["status"], "failed")
        self.ssh.connect.assert_not_called()

    def test_dify_parser(self):
        for status in ("failed", "skipped", "not_found"):
            for obj in ({"status": status, "data": None}, json.dumps({"status": status})):
                out = parse_result(obj)
                self.assertEqual(out["status"], status)
                self.assertIs(out["upgrade_notes_present"], False)
                self.assertEqual(out["config_changed"], 0)
        self.assertEqual(parse_result("bad JSON")["status"], "failed")
        self.files = {"升级说明/一.txt": b"1", "升级说明/二.txt": b"2"}
        out = parse_result(self.fetch().text)
        self.assertEqual(out["upgrade_notes_count"], 2)
        self.assertEqual(set(out["upgrade_notes_files_text"].splitlines()), set(self.files))
