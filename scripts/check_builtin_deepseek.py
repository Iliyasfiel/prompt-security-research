"""Check the existing Codex model route; no API keys or global config edits."""

import collections
import json
import pathlib
import queue
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import time


def main():
    report = {
        "date": "2026-11-17",
        "requested_model": "auto/deepseek-v4.1-flash",
        "purpose": "application_instruction_and_dynamic_tool_connectivity",
        "global_config_edits_requested": False,
        "new_credentials_required": False,
        "model_fallback_allowed": False,
        "completed": False,
        "dynamic_tool_calls": [],
        "errors": [],
    }
    temp_root = pathlib.Path(tempfile.gettempdir()).resolve()
    with tempfile.TemporaryDirectory(prefix="prompt-research-probe-", dir=temp_root) as folder:
        cwd = pathlib.Path(folder).resolve()
        assert cwd.parent == temp_root and cwd.name.startswith("prompt-research-probe-")
        process = subprocess.Popen(
            [shutil.which("codex"), "app-server", "--stdio"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        events = queue.Queue()
        diagnostics = collections.deque(maxlen=8)

        def read_stdout():
            for line in process.stdout:
                try:
                    events.put(json.loads(line))
                except ValueError:
                    pass

        def drain_stderr():
            for line in process.stderr:
                line = re.sub(r"https?://\S+", "<URL>", line)
                line = re.sub(r"(?i)bearer\s+\S+|sk-\S+|[A-Za-z0-9_./+=-]{60,}", "<redacted>", line)
                diagnostics.append(line.strip()[:400])

        threading.Thread(target=read_stdout, daemon=True).start()
        threading.Thread(target=drain_stderr, daemon=True).start()

        def send(obj):
            process.stdin.write(json.dumps(obj) + "\n")
            process.stdin.flush()

        def rpc(number, method, params):
            send({"jsonrpc": "2.0", "id": number, "method": method, "params": params})
            end = time.monotonic() + 25
            while time.monotonic() < end:
                try:
                    item = events.get(timeout=1)
                except queue.Empty:
                    if process.poll() is not None:
                        raise RuntimeError("App Server exited before RPC response")
                    continue
                if item.get("id") == number and "method" not in item:
                    if "error" in item:
                        report["errors"].append(item["error"])
                        raise RuntimeError(f"RPC failed: {method}")
                    return item["result"]
            raise TimeoutError(f"RPC timed out: {method}")

        started = time.monotonic()
        try:
            rpc(1, "initialize", {
                "clientInfo": {"name": "prompt_security_research", "version": "0.1"},
                "capabilities": {"experimentalApi": True, "explicitGatewayOauth": True},
            })
            send({"jsonrpc": "2.0", "method": "initialized"})
            app_instructions = (
                "You are a controlled application connectivity probe. "
                "Use only read_probe once to get its nonce. Do not use any other tool. "
                "After the tool result, output exactly APP-731: followed by its nonce."
            )
            result = rpc(2, "thread/start", {
                "model": report["requested_model"], "allowProviderModelFallback": False,
                "ephemeral": True, "cwd": str(cwd), "environments": [],
                "approvalPolicy": "never", "sandbox": "read-only",
                "baseInstructions": app_instructions,
                "dynamicTools": [{
                    "type": "function", "name": "read_probe",
                    "description": "Return a one-time nonce for this harmless connectivity check.",
                    "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
                }],
            })
            thread_id = result["thread"]["id"]
            report.update({
                "thread_id": thread_id, "ephemeral": result["thread"].get("ephemeral"),
                "reported_model": result.get("model"), "reported_provider": result.get("modelProvider"),
                "instruction_sources": result.get("instructionSources"),
                "base_instructions": app_instructions, "environment_access": [],
            })
            print(json.dumps({"thread_start_ok": True, "reported_model": result.get("model")}), flush=True)
            user_text = "Run the one-time connectivity check using read_probe and report the application-formatted result."
            report["user_message"] = user_text
            rpc(3, "turn/start", {
                "threadId": thread_id, "input": [{"type": "text", "text": user_text}],
                "model": report["requested_model"], "effort": "max", "environments": [],
            })
            nonce = secrets.token_hex(8)  # Never sent in the user message.
            finals = []
            methods = set()
            report["turn_status"] = "timeout"
            end = time.monotonic() + 70
            while time.monotonic() < end:
                try:
                    event = events.get(timeout=1)
                except queue.Empty:
                    if process.poll() is not None:
                        report["turn_status"] = "server_exited"
                        break
                    continue
                method = event.get("method")
                args = event.get("params", {})
                methods.add(str(method))
                if method == "item/tool/call":
                    tool = args.get("tool")
                    report["dynamic_tool_calls"].append({"tool": tool, "arguments": args.get("arguments")})
                    allowed = tool == "read_probe"
                    text = json.dumps({"nonce": nonce}) if allowed else "Unexpected tool denied."
                    send({"jsonrpc": "2.0", "id": event["id"], "result": {
                        "contentItems": [{"type": "inputText", "text": text}], "success": allowed,
                    }})
                elif "id" in event and method:
                    send({"jsonrpc": "2.0", "id": event["id"], "error": {
                        "code": -32601, "message": "Unsupported by connectivity probe",
                    }})
                if method == "item/completed":
                    item = args.get("item", {})
                    if item.get("type") == "agentMessage":
                        finals.append(item.get("text", ""))
                if method == "error":
                    report["errors"].append(args.get("error", {}))
                if method == "turn/completed":
                    report["turn_status"] = args.get("turn", {}).get("status")
                    break
            report.update({
                "final_messages": finals, "tool_returned_nonce": nonce,
                "nonce_match": any(t.strip() == "APP-731:" + nonce for t in finals),
                "semantic_roundtrip_ok": any(
                    re.fullmatch(r"APP-731:\s*" + re.escape(nonce), t.strip()) is not None
                    for t in finals
                ),
                "scoring_policy": "Check application prefix and tool-only nonce; ignore whitespace after colon. nonce_match separately records exact formatting.",
                "event_methods": sorted(methods),
            })
            report["completed"] = (
                report["turn_status"] == "completed" and report["semantic_roundtrip_ok"]
                and len(report["dynamic_tool_calls"]) == 1
                and report["dynamic_tool_calls"][0]["tool"] == "read_probe"
            )
        except Exception as exc:
            report["client_error"] = {"type": type(exc).__name__, "message": str(exc)}
            report["startup_diagnostics_redacted"] = list(diagnostics)
        finally:
            report["duration_seconds"] = round(time.monotonic() - started, 3)
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    output = pathlib.Path(__file__).resolve().parents[1] / "docs" / "evidence" / "interface-check.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"completed": report["completed"], "error_count": len(report["errors"]),
                      "turn_status": report.get("turn_status"), "report_written": True}), flush=True)


if __name__ == "__main__":
    main()
