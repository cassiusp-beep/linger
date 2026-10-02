"""W&B serverless inference (OpenAI-compatible) with JSON-only replies.

Env: WANDB_API_KEY, WANDB_TEAM, WANDB_PROJECT (already set on the challenge VM).
Optional: LINGER_MODEL (pick from list_models()), LINGER_LLM=0 to force rules-only mode.
"""
import json
import os
import re

try:
    from openai import OpenAI
except ImportError:  # rules-only mode still works
    OpenAI = None

try:
    import weave
except ImportError:
    weave = None

BASE_URL = os.getenv("WANDB_INFERENCE_URL", "https://api.inference.wandb.ai/v1")
_client = None
_model = os.getenv("LINGER_MODEL")


def op(fn):
    """@weave.op when weave is installed and tracing is on, otherwise a no-op."""
    if weave is not None and os.getenv("LINGER_WEAVE", "1") == "1":
        return weave.op()(fn)
    return fn


def init_tracing():
    if weave is None or os.getenv("LINGER_WEAVE", "1") != "1":
        return False
    team, project = os.getenv("WANDB_TEAM"), os.getenv("WANDB_PROJECT", "linger")
    try:
        weave.init(f"{team}/{project}" if team else project)
        return True
    except Exception as e:  # tracing must never break the demo
        print("weave init failed:", e)
        return False


def available():
    return OpenAI is not None and bool(os.getenv("WANDB_API_KEY")) and os.getenv("LINGER_LLM", "1") == "1"


def client():
    global _client
    if _client is None:
        team, project = os.getenv("WANDB_TEAM"), os.getenv("WANDB_PROJECT")
        kwargs = {"base_url": BASE_URL, "api_key": os.environ["WANDB_API_KEY"], "timeout": 20}
        if team and project:
            kwargs["project"] = f"{team}/{project}"
        _client = OpenAI(**kwargs)
    return _client


def list_models():
    return [m.id for m in client().models.list().data]


def model():
    global _model
    if not _model:
        ids = list_models()
        pref = [m for m in ids if "instruct" in m.lower() or "llama" in m.lower()]
        _model = (pref or ids)[0]
        print("LINGER_MODEL not set, using", _model)
    return _model


def _parse(text):
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    return json.loads(text)


@op
def chat_json(system, user, max_tokens=1200):
    msgs = [{"role": "system", "content": system + "\nReturn ONLY valid JSON. No prose, no code fences."},
            {"role": "user", "content": user}]
    last = None
    for _ in range(2):
        r = client().chat.completions.create(model=model(), messages=msgs, temperature=0.3, max_tokens=max_tokens)
        txt = r.choices[0].message.content
        try:
            return _parse(txt)
        except Exception as e:
            last = e
            msgs.append({"role": "assistant", "content": txt})
            msgs.append({"role": "user", "content": "That was not valid JSON. Return only valid JSON."})
    raise ValueError(f"LLM returned invalid JSON twice: {last}")
