"""S2 — container Docker (08 §4.1, §4.3, §4.4). SOMENTE ESPECIFICAÇÃO na 2.2.

`DockerSpec` monta, como dados, os argumentos exigidos pela arquitetura (`--rm`, `--network none` fora da
etapa de instalação, usuário não root, `--memory`, `--cpus`, só o worktree montado, sem `docker.sock`,
rótulo `appfactory.task`). Endurecimentos extras e política de imagem estão pendentes (P-10).
`DockerSandbox.run` sempre lança SandboxUnavailable: o Docker não é usado nesta fase (KI-0011)."""
from __future__ import annotations

import os
from dataclasses import dataclass

from appfactory.security.sandbox import SandboxUnavailable, limits_for

UNAVAILABLE_REASON = "S2 indisponível na Fase 2.2: Docker não é usado nesta fase (KI-0011; fatia 2.6)"
NON_ROOT_USER = "1000:1000"


@dataclass(frozen=True)
class DockerSpec:
    args: tuple[str, ...]
    network: str
    memory_bytes: int
    cpus: float

    def validate(self) -> None:
        joined = " ".join(self.args)
        if "docker.sock" in joined:
            raise ValueError("montar o socket do Docker é proibido")
        if "--privileged" in self.args:
            raise ValueError("--privileged é proibido")
        if "--rm" not in self.args:
            raise ValueError("--rm é obrigatório")
        if self.args.count("--mount") != 1:
            raise ValueError("somente o worktree pode ser montado")
        user = self.args[self.args.index("--user") + 1] if "--user" in self.args else ""
        if not user or user.split(":")[0] in ("0", "root"):
            raise ValueError("o container deve rodar como usuário não root")


def docker_spec(task_id: str, worktree: str | os.PathLike, mode: str, install_step: bool, image: str,
                argv: tuple[str, ...] = (), cpu_count: int | None = None, timeout_s: int = 600) -> DockerSpec:
    if not image or any(c in image for c in " \t\n"):
        raise ValueError("imagem inválida (política de imagem pendente, P-10)")
    lim = limits_for(mode, timeout_s)
    cpus = round((cpu_count or os.cpu_count() or 1) * lim.cpu_rate_pct / 100, 1)
    network = "bridge" if install_step else "none"
    args = ("docker", "run", "--rm", "--network", network, "--user", NON_ROOT_USER,
            "--memory", f"{lim.memory_bytes}b", "--cpus", f"{cpus}", "--label", f"appfactory.task={task_id}",
            "--mount", f"type=bind,source={os.fspath(worktree)},target=/work", "-w", "/work", image, *argv)
    spec = DockerSpec(args=args, network=network, memory_bytes=lim.memory_bytes, cpus=cpus)
    spec.validate()
    return spec


class DockerSandbox:
    kind = "S2"

    def available(self) -> tuple[bool, str]:
        return False, UNAVAILABLE_REASON

    def run(self, argv, cwd, env, limits, cancel):  # noqa: ARG002 - contrato 12 §6
        raise SandboxUnavailable(UNAVAILABLE_REASON)
