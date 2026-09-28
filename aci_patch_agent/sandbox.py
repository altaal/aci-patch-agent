"""Execute generated functions in disposable containers; grade outputs on the host."""

import json
from pathlib import Path
import subprocess
import tempfile
import time
import uuid


DEFAULT_IMAGE = "python@sha256:da047cb8f9d1d98e5c070f5300ba9f7274e33b8fc0e5be5ed88740aed1b95ba9"


class DockerSandbox:
    def __init__(self, image=DEFAULT_IMAGE, timeout=10):
        self.image, self.timeout = image, timeout

    def preflight(self):
        for args in (["docker", "info"], ["docker", "image", "inspect", self.image]):
            try:
                result = subprocess.run(args, capture_output=True, timeout=15)
            except (OSError, subprocess.TimeoutExpired) as error:
                raise RuntimeError("Docker is unavailable. Start Docker and pull the documented image.") from error
            if result.returncode:
                raise RuntimeError(f"Docker or image {self.image} is unavailable. See README setup.")
        data = json.loads(result.stdout)
        return {"image": self.image, "image_id": data[0]["Id"], "repo_digests": data[0].get("RepoDigests", []),
                "architecture": data[0]["Architecture"]}

    def check(self, task, source, *, final=False):
        cases = task.examples + task.evaluation if final else task.examples
        # Only inputs go into the container. Expected values stay in the host evaluator.
        inputs = repr([c.args for c in cases])
        driver = (
            "import contextlib, io, json, runpy\n"
            "with contextlib.redirect_stdout(io.StringIO()):\n"
            "    namespace = runpy.run_path('/work/solution.py')\n"
            f"    function = namespace[{task.function!r}]\n"
            "results = []\n"
            f"for args in {inputs}:\n"
            "    try:\n"
            "        with contextlib.redirect_stdout(io.StringIO()):\n"
            "            actual = function(*args)\n"
            "        results.append({'value': actual, 'exception': None})\n"
            "    except Exception as error:\n"
            "        results.append({'exception': type(error).__name__})\n"
            "print(json.dumps(results, allow_nan=False))\n"
        )
        output, error = self._execute(source, driver)
        if error:
            return {"passed": False, "checks": len(cases), "failures": [], "error": error}
        try:
            values = json.loads(output)
            if not isinstance(values, list) or len(values) != len(cases):
                raise ValueError("wrong result count")
            failures = []
            for index, (case, actual) in enumerate(zip(cases, values), 1):
                if not isinstance(actual, dict):
                    raise ValueError("invalid result")
                if case.raises:
                    ok = actual.get("exception") == case.raises
                else:
                    value = actual.get("value")
                    ok = actual.get("exception") is None and type(value) is type(case.expected) and value == case.expected
                if not ok:
                    failures.append({"case": index, "input": repr(case.args),
                                     "expected": case.raises or repr(case.expected), "actual": actual})
            return {"passed": not failures, "checks": len(cases), "failures": failures, "error": None}
        except (ValueError, TypeError):
            return {"passed": False, "checks": len(cases), "failures": [], "error": "invalid_evaluator_output"}

    def _execute(self, source, driver):
        name = f"aci-patch-{uuid.uuid4().hex}"
        with tempfile.TemporaryDirectory(prefix="aci-patch-") as directory:
            root = Path(directory)
            root.chmod(0o755)
            (root / "solution.py").write_text(source)
            (root / "driver.py").write_text(driver)
            (root / "solution.py").chmod(0o644)
            (root / "driver.py").chmod(0o644)
            command = ["docker", "run", "--rm", "--name", name, "--network", "none",
                       "--user", "65534:65534", "--read-only", "--cap-drop", "ALL",
                       "--security-opt", "no-new-privileges", "--pids-limit", "32",
                       "--memory", "128m", "--cpus", "1", "--log-driver", "none",
                       "-v", f"{root}:/work:ro", "-w", "/work", self.image,
                       "python", "-I", "-B", "-S", "/work/driver.py"]
            with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as stderr:
                process = None
                error = None
                try:
                    process = subprocess.Popen(command, stdout=output, stderr=stderr)
                    deadline = time.monotonic() + self.timeout
                    while process.poll() is None:
                        if time.monotonic() >= deadline:
                            error = "execution_timeout"
                            break
                        if output.tell() + stderr.tell() > 65_536:
                            error = "output_limit"
                            break
                        time.sleep(0.05)
                    if error:
                        process.kill()
                    process.wait(timeout=5)
                    output.seek(0)
                    text = output.read(65_537).decode("utf-8", errors="replace")
                    if len(text.encode()) > 65_536:
                        error = "output_limit"
                    return text, error or ("execution_error" if process.returncode else None)
                except (OSError, subprocess.TimeoutExpired):
                    return "", "sandbox_error"
                finally:
                    if process is not None and process.poll() is None:
                        process.kill()
                        process.wait()
                    # Kill the container too: killing the Docker client alone does not stop it.
                    try:
                        subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=15)
                    except (OSError, subprocess.TimeoutExpired):
                        raise RuntimeError("Container cleanup failed; check Docker for aci-patch containers.") from None
