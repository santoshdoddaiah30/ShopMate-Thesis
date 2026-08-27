from __future__ import annotations

import base64
import json
import zlib
from pathlib import Path

from jupyter_client import BlockingKernelClient


NOTEBOOK = Path("Notebooks/Thesis_clean.ipynb")
RUNTIME_DIR = Path(r"C:\Users\santo\AppData\Roaming\jupyter\runtime")
REQUIRED = [
    "build_runtime_outfit_recommendations",
    "n18i_run_outfit_service",
    "n18h_build_base_outfits",
    "n18h_build_complete_outfits",
]


def kernel_source() -> str:
    connection = max(RUNTIME_DIR.glob("kernel-*.json"), key=lambda item: item.stat().st_mtime)
    client = BlockingKernelClient(connection_file=str(connection))
    client.load_connection_file()
    client.start_channels()
    try:
        message_id = client.execute("print(src)", store_history=False)
        chunks: list[str] = []
        while True:
            message = client.get_iopub_msg(timeout=120)
            if message["parent_header"].get("msg_id") != message_id:
                continue
            if message["msg_type"] == "stream":
                chunks.append(message["content"]["text"])
            elif message["msg_type"] == "error":
                raise RuntimeError(message["content"]["evalue"])
            elif message["msg_type"] == "status" and message["content"]["execution_state"] == "idle":
                break
        return "".join(chunks)
    finally:
        client.stop_channels()


source = kernel_source()
for name in REQUIRED:
    if f"def {name}(" not in source and f"{name} = " not in source:
        raise RuntimeError(f"Captured bundle is missing {name}.")
if ") in itertools.product(" not in source:
    raise RuntimeError("Captured bundle does not contain the required safe itertools.product call.")

bundle = base64.b64encode(zlib.compress(source.encode("utf-8"), 9)).decode("ascii")
loader_source = [
    "# SECTION 153E7N18H — RUNTIME OUTFIT IMPLEMENTATION — RESTORED FOR COLD START\n",
    "# Exact tested live-kernel N13–N18 source; includes explicit itertools.product calls.\n",
    "import base64\n",
    "import zlib\n",
    "\n",
    f"_n18h_runtime_source_bundle = {bundle!r}\n",
    "_n18h_runtime_source = zlib.decompress(base64.b64decode(_n18h_runtime_source_bundle)).decode('utf-8')\n",
    "exec(compile(_n18h_runtime_source, '<shopmate_n18h_restored>', 'exec'), globals())\n",
    "print('Restored the N13–N18 runtime outfit implementation for cold start.')\n",
]
validation_source = [
    "# SECTION 153E7N18H1 — COLD-START RUNTIME OUTFIT VALIDATION\n",
    "import dis\n",
    f"_n18h_required_runtime_functions = {REQUIRED!r}\n",
    "_n18h_missing_runtime_functions = [name for name in _n18h_required_runtime_functions if not callable(globals().get(name))]\n",
    "assert not _n18h_missing_runtime_functions, _n18h_missing_runtime_functions\n",
    "assert not any(instruction.opname == 'LOAD_GLOBAL' and instruction.argval == 'product' for name in ['n18h_build_base_outfits', 'n18h_build_complete_outfits'] for instruction in dis.get_instructions(globals()[name]))\n",
    "print('N18H cold-start definitions and safe itertools.product bindings verified.')\n",
]

notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
ids = {cell.get("id") for cell in notebook["cells"]}
if "n18h-restored-runtime" not in ids:
    notebook["cells"].append({"cell_type": "code", "execution_count": None, "id": "n18h-restored-runtime", "metadata": {}, "outputs": [], "source": loader_source})
if "n18h-cold-start-validation" not in ids:
    notebook["cells"].append({"cell_type": "code", "execution_count": None, "id": "n18h-cold-start-validation", "metadata": {}, "outputs": [], "source": validation_source})

temporary = NOTEBOOK.with_suffix(".ipynb.tmp")
temporary.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
os_check = json.loads(temporary.read_text(encoding="utf-8"))
saved_loader = next(cell for cell in os_check["cells"] if cell.get("id") == "n18h-restored-runtime")
saved_source = zlib.decompress(base64.b64decode(next(line for line in saved_loader["source"] if line.startswith("_n18h_runtime_source_bundle = ")).split("= ", 1)[1].strip().strip("'"))).decode("utf-8")
for name in REQUIRED:
    if f"def {name}(" not in saved_source and f"{name} = " not in saved_source:
        raise RuntimeError(f"Saved bundle validation failed for {name}.")
if ") in product(" in saved_source or ") in itertools.product(" not in saved_source:
    raise RuntimeError("Saved bundle validation failed for product namespace safety.")
temporary.replace(NOTEBOOK)
print(f"Saved {len(source.splitlines())} exact runtime source lines into {NOTEBOOK}.")
