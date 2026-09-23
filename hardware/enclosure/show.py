#!/usr/bin/env python3
"""Send the model to a running OCP viewer (over a local websocket; the viewer is a separate app).

Start a viewer first, either:
  - standalone, in a browser:  ~/.venvs/cad/bin/python -m ocp_viewer   (then open http://127.0.0.1:3939/viewer)
  - in VSCode: the "OCP CAD Viewer" extension's pane
Then:
    ~/.venvs/cad/bin/python hardware/enclosure/show.py            # everything
    ~/.venvs/cad/bin/python hardware/enclosure/show.py printed    # printed parts only
Re-running updates the open view in place.
"""

import json
import os
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _live_viewer_port():
    """First candidate port with something listening. Viewers register in ~/.ocpvscode, but
    entries go stale when a viewer exits, so every candidate is actually probed."""
    candidates = [os.environ.get("OCP_PORT")]
    try:
        candidates += list(json.loads((Path.home() / ".ocpvscode").read_text())["services"])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    candidates.append("3939")
    for port in candidates:
        if not port:
            continue
        with socket.socket() as s:
            s.settimeout(0.3)
            if s.connect_ex(("127.0.0.1", int(port))) == 0:
                return port
    return None


port = _live_viewer_port()
if port is None:
    sys.exit(__doc__.split("Then:")[0] + "\nNo viewer found - start one as above, or open "
             "hardware/enclosure/out/assembly.step in FreeCAD.")
os.environ["OCP_PORT"] = port  # skip ocp_vscode's own discovery, which trips on stale entries

from ocp_vscode import show  # noqa: E402

import model  # noqa: E402
from render import COLORS  # noqa: E402

printed, components = model.build()
parts = printed if sys.argv[1:] == ["printed"] else {**printed, **components}
show(*parts.values(), names=list(parts), colors=[COLORS[n][0] for n in parts],
     alphas=[COLORS[n][1] for n in parts])
