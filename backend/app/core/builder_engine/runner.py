"""Loop agent. Model hanya meminta tool; runner yang memutuskan dan menjalankan."""


def check_guardrails(guardrails: list[dict], tool: dict, args: dict) -> str | None:
    for g in guardrails:
        if g["type"] == "tool_call" and g["rule"] == "deny_effect_write" and tool["spec"]["effect"] != "read":
            return g["id"]
    return None


def run_agent(model, registry: dict, guardrails: list[dict], limits: dict, user_message: str, execute) -> dict:
    """model(messages, tool_specs) -> {"type": "text"|"tool_use", ...}.
    registry: nama -> {"status", "spec"}. execute(tool, args) -> dict."""
    messages = [{"role": "user", "content": user_message}]
    trace, tokens = [], 0
    for _ in range(limits["max_turns"]):
        visible = [t["spec"] for t in registry.values() if t["status"] == "published"]  # registry = allowlist
        out = model(messages, visible)
        tokens += out.get("tokens", 0)
        if tokens > limits["max_tokens"]:
            return {"status": "stopped", "reason": "token_limit", "trace": trace}
        if out["type"] == "text":
            return {"status": "done", "text": out["text"], "trace": trace}
        name, args = out["name"], out["input"]
        tool = registry.get(name)
        if tool is None or tool["status"] != "published":
            result = {"error": "tool_not_allowed"}
        elif (blocked := check_guardrails(guardrails, tool, args)):
            result = {"error": "blocked_by_guardrail", "guardrail": blocked}
        else:
            result = execute(tool, args)
        trace.append({"tool": name, "args": args, "result": result})
        messages.append({"role": "tool", "name": name, "content": result})
    return {"status": "stopped", "reason": "max_turns", "trace": trace}
