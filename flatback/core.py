import subprocess
import yaml
import shutil
import tarfile
import tempfile
from pathlib import Path

from . import __version__


class FlatpakRef:
    def __init__(self, app_id, arch="x86_64", branch="stable", origin="flathub", installation="user"):
        self.app_id = app_id
        self.arch = arch
        self.branch = branch
        self.origin = origin
        self.installation = installation

    @property
    def ref(self):
        return f"{self.app_id}/{self.arch}/{self.branch}"

    def as_dict(self):
        return {
            "app_id": self.app_id,
            "arch": self.arch,
            "branch": self.branch,
            "origin": self.origin,
            "installation": self.installation,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


class FlatpakQuery:
    def __init__(self, installation="user"):
        self._install_flag = f"--{installation}"

    def _run(self, args):
        result = subprocess.run(
            ["flatpak"] + args,
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()

    def app_info(self, app_id):
        raw = self._run(["info", self._install_flag, app_id])
        info = {}
        for line in raw.splitlines():
            if ":" in line:
                key, _, val = line.partition(":")
                info[key.strip()] = val.strip()
        return info

    def app_ref(self, app_id):
        info = self.app_info(app_id)
        ref_str = info.get("Ref", "")
        parts = ref_str.split("/")
        return FlatpakRef(
            app_id=parts[1] if len(parts) > 1 else app_id,
            arch=parts[2] if len(parts) > 2 else "x86_64",
            branch=parts[3] if len(parts) > 3 else "stable",
            origin=info.get("Origin", "flathub"),
            installation="user" if self._install_flag == "--user" else "system",
        )

    def runtime_ref(self, app_id):
        raw = self._run(["info", self._install_flag, "--show-runtime", app_id])
        parts = raw.split("/")
        return FlatpakRef(
            app_id=parts[0],
            arch=parts[1] if len(parts) > 1 else "x86_64",
            branch=parts[2] if len(parts) > 2 else "stable",
            origin="flathub",
            installation="user" if self._install_flag == "--user" else "system",
        )

    def repo_path(self, installation="user"):
        if installation == "user":
            return Path.home() / ".local/share/flatpak/repo"
        return Path("/var/lib/flatpak/repo")


class BundleBuilder:
    def __init__(self, query: FlatpakQuery):
        self.query = query

    def build_bundle(self, ref: FlatpakRef, output_path: Path, is_runtime=False):
        repo = self.query.repo_path(ref.installation)
        args = [
            "flatpak", "build-bundle",
            str(repo), str(output_path),
            ref.app_id, ref.branch,
            f"--arch={ref.arch}",
        ]
        if is_runtime:
            args.append("--runtime")
        subprocess.run(args, check=True)


class Backup:
    MANIFEST = "flatback.yml"
    DATA_DIR = "data"

    def __init__(self, app_id, installation="user"):
        self.app_id = app_id
        self.installation = installation
        self.query = FlatpakQuery(installation)
        self.builder = BundleBuilder(self.query)

    def _bundle_name(self, ref: FlatpakRef, is_runtime=False):
        prefix = "runtime" if is_runtime else "app"
        return f"{prefix}_{ref.app_id}_{ref.arch}_{ref.branch}.flatpak"

    def _user_data_path(self):
        return Path.home() / ".var" / "app" / self.app_id

    def create(self, output_path=None, as_tar=True, include_data=False):
        app_ref = self.query.app_ref(self.app_id)
        runtime_ref = self.query.runtime_ref(self.app_id)
        app_info = self.query.app_info(self.app_id)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)

            app_bundle = self._bundle_name(app_ref)
            runtime_bundle = self._bundle_name(runtime_ref, is_runtime=True)

            print(f"Bundling app: {app_ref.ref}")
            self.builder.build_bundle(app_ref, tmp_dir / app_bundle)

            print(f"Bundling runtime: {runtime_ref.ref}")
            self.builder.build_bundle(runtime_ref, tmp_dir / runtime_bundle, is_runtime=True)

            has_data = False
            if include_data:
                has_data = self._copy_user_data(tmp_dir)

            manifest = {
                "app": app_ref.as_dict(),
                "runtime": runtime_ref.as_dict(),
                "app_bundle": app_bundle,
                "runtime_bundle": runtime_bundle,
                "version": app_info.get("Version", "unknown"),
                "flatback_version": __version__,
                "has_data": has_data,
            }

            with open(tmp_dir / self.MANIFEST, "w") as f:
                yaml.dump(manifest, f, default_flow_style=False)

            default_name = self.app_id
            if as_tar:
                out = Path(output_path or f"{default_name}.tar.gz")
                self._pack_tar(tmp_dir, out)
            else:
                out = Path(output_path or default_name)
                if out.exists():
                    shutil.rmtree(out)
                shutil.copytree(tmp_dir, out)

            print(f"Backup saved to: {out}")
            return out

    def _copy_user_data(self, tmp_dir):
        src = self._user_data_path()
        if not src.exists():
            print(f"No user data found at: {src}")
            return False
        dst = tmp_dir / self.DATA_DIR
        print(f"Copying user data: {src}")
        shutil.copytree(src, dst, symlinks=True)
        return True

    def _pack_tar(self, source_dir, tar_path):
        with tarfile.open(tar_path, "w:gz") as tar:
            for item in source_dir.iterdir():
                tar.add(item, arcname=item.name)


class Restore:
    MANIFEST = "flatback.yml"
    DATA_DIR = "data"

    def __init__(self, installation="user", restore_data=None):
        self.installation = installation
        self._install_flag = f"--{installation}"
        self._restore_data = restore_data

    def load(self, source_path):
        source = Path(source_path)
        if source.is_file() and (source.suffix == ".gz" or source.name.endswith(".tar.gz")):
            self._load_from_tar(source)
        elif source.is_dir():
            self._load_from_dir(source)
        else:
            raise ValueError(f"Unsupported source: {source}")

    def _load_from_tar(self, tar_path):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            with tarfile.open(tar_path, "r:gz") as tar:
                tar.extractall(tmp_dir, filter="data")
            self._load_from_dir(tmp_dir)

    def _load_from_dir(self, directory):
        manifest_path = directory / self.MANIFEST
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")

        with open(manifest_path) as f:
            manifest = yaml.safe_load(f)

        runtime_bundle = directory / manifest["runtime_bundle"]
        app_bundle = directory / manifest["app_bundle"]

        runtime_ref = FlatpakRef.from_dict(manifest["runtime"])
        app_ref = FlatpakRef.from_dict(manifest["app"])

        print(f"Installing runtime: {runtime_ref.ref}")
        self._install_bundle(runtime_bundle)

        print(f"Installing app: {app_ref.ref}")
        self._install_bundle(app_bundle)

        if manifest.get("has_data"):
            self._handle_user_data(directory, app_ref.app_id)

        print(f"Restore complete: {app_ref.app_id}")

    def _handle_user_data(self, directory, app_id):
        data_dir = directory / self.DATA_DIR
        if not data_dir.exists():
            return

        should_restore = self._restore_data
        if should_restore is None:
            answer = input("Backup contains user data. Restore it? [y/N] ").strip().lower()
            should_restore = answer in ("y", "yes")

        if not should_restore:
            print("Skipping user data restore")
            return

        dst = Path.home() / ".var" / "app" / app_id
        if dst.exists():
            print(f"Replacing existing user data: {dst}")
            shutil.rmtree(dst)
        print(f"Restoring user data to: {dst}")
        shutil.copytree(data_dir, dst, symlinks=True)

    def _install_bundle(self, bundle_path):
        result = subprocess.run(
            ["flatpak", "install", self._install_flag, "--bundle", "-y", str(bundle_path)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            if "already installed" in result.stderr:
                print(f"Already installed, skipping: {bundle_path.name}")
            else:
                print(result.stderr)
                raise subprocess.CalledProcessError(result.returncode, result.args)
