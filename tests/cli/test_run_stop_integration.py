import json
from types import SimpleNamespace

from click.testing import CliRunner

from context_cleaner.cli.main import main as cli_main


def test_run_status_only_json_and_stop(monkeypatch):
    created_orchestrators = []

    class StubOrchestrator:
        def __init__(self, config=None, verbose=False):
            self.verbose = verbose
            self.shutdown_called = False
            self.services = {}
            self.service_states = {}
            self.discovery_engine = SimpleNamespace(discover_all_processes=lambda: [])
            self.process_registry = SimpleNamespace(
                get_all_processes=lambda: [],
                unregister_process=lambda pid: True,
                register_process=lambda entry: True,
                update_process_metadata=lambda pid, **fields: True,
            )
            self.port_registry = SimpleNamespace(deallocate_port=lambda *args, **kwargs: False)
            created_orchestrators.append(self)

        def get_service_status(self):
            return {
                "orchestrator": {
                    "running": True,
                    "services_running": 0,
                    "uptime_seconds": 0.0,
                    "shutdown_initiated": False,
                },
                "services": {},
                "services_summary": {
                    "total": 0,
                    "by_status": {},
                    "required_failed": [],
                    "optional_failed": [],
                    "transitioning": {"starting": [], "stopping": []},
                    "running": [],
                },
            }

        async def shutdown_all(self, *, docker_only=False, processes_only=False, services=None, include_dependents=True):
            self.shutdown_called = True
            return {
                "success": True,
                "failed": [],
                "invalid": [],
                "requested": [],
            }

    class StubSupervisorClient:
        def __init__(self, endpoint=None):
            self.endpoint = endpoint

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def send(self, request):
            return SimpleNamespace(
                status="ok",
                result={
                    "watchdog": {
                        "running": False,
                        "restart_attempts": 0,
                        "restart_history": [],
                    }
                },
            )

    monkeypatch.setattr("context_cleaner.services.ServiceOrchestrator", StubOrchestrator)
    monkeypatch.setattr("context_cleaner.ipc.client.SupervisorClient", StubSupervisorClient)

    runner = CliRunner()

    result = runner.invoke(cli_main, ["run", "--status-only", "--json"])
    assert result.exit_code == 0, result.output
    json_start = result.output.find("{")
    payload = json.loads(result.output[json_start:])
    assert payload["orchestrator"]["running"] is True
    assert payload["watchdog"]["running"] is False

    result = runner.invoke(
        cli_main,
        ["stop", "--force", "--no-discovery"],
        input="y\n",
    )
    assert result.exit_code == 0, result.output
    assert any(getattr(inst, "shutdown_called", False) for inst in created_orchestrators)
