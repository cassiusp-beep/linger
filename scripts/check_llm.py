"""Laptop smoke test: lists W&B models, makes one JSON call, confirms Weave."""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from agent import llm

if not llm.available():
    sys.exit("No WANDB_API_KEY found (or LINGER_LLM=0, or openai not installed). Fill in .env first.")
ids = llm.list_models()
print(f"{len(ids)} models available:")
for m in ids:
    print("  ", m)
if "--models" in sys.argv:
    sys.exit(0)
print("tracing:", llm.init_tracing())
print("model:", llm.model())
print("reply:", llm.chat_json("You are a test.", 'Return {"ok": true, "word": "linger"}'))
