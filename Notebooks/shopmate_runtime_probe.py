"""Read-only helper for inspecting an already-running Jupyter kernel.

Usage:
    python shopmate_runtime_probe.py CONNECTION_FILE BASE64_CODE

The helper exists so ShopMate's loaded notebook namespace can be inspected
without rerunning the full authoritative notebook.  It prints stream output,
the final expression result, or a traceback returned by the kernel.
"""

from __future__ import annotations

import base64
import sys

from jupyter_client import BlockingKernelClient


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: shopmate_runtime_probe.py CONNECTION_FILE BASE64_CODE")

    connection_file, encoded_code = sys.argv[1:]
    code = base64.b64decode(encoded_code).decode("utf-8")
    client = BlockingKernelClient(connection_file=connection_file)
    client.load_connection_file()
    client.start_channels()
    try:
        if code == "__INTERRUPT__":
            client.control_channel.send(
                client.session.msg("interrupt_request", content={})
            )
            print("INTERRUPT_REQUEST_SENT")
            return 0
        client.wait_for_ready(timeout=10)
        message_id = client.execute(code, store_history=False, allow_stdin=False)
        while True:
            message = client.get_iopub_msg(timeout=300)
            if message.get("parent_header", {}).get("msg_id") != message_id:
                continue
            message_type = message["header"]["msg_type"]
            content = message["content"]
            if message_type == "stream":
                print(content.get("text", ""), end="")
            elif message_type in {"execute_result", "display_data"}:
                print(content.get("data", {}).get("text/plain", ""))
            elif message_type == "error":
                print("\n".join(content.get("traceback", [])))
            elif message_type == "status" and content.get("execution_state") == "idle":
                break
    finally:
        client.stop_channels()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
