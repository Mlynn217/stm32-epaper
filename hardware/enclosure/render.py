"""Headless PNG renders (matplotlib) - for reviewing the model without a GUI.

Plot axes: device X -> plot x, device thickness Z -> plot -y (so the front faces the viewer at
azim=-90), device Y (up) -> plot z.
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

from build123d import Box, Pos  # noqa: E402

COLORS = {
    "front_shell": ("#c9ccd1", 1.0), "back_cover": ("#8d9299", 1.0), "panel_backer": ("#d8c7a0", 1.0),
    "knob": ("#3a3d42", 1.0), "panel": ("#e9eee4", 1.0), "panel_fpc_fold": ("#d9a441", 1.0),
    "battery_zone": ("#e38b3c", 1.0), "hat": ("#3f6fb5", 1.0), "pcb": ("#2f8f4e", 1.0),
    "encoder_body": ("#707070", 1.0), "encoder_bushing": ("#9a9a9a", 1.0),
    "encoder_shaft": ("#b0b0b0", 1.0), "usb_c": ("#d0d0d0", 1.0),
    "usb_plug": ("#d64545", 0.35), "sd_socket": ("#b8b8b8", 1.0), "sd_card_path": ("#d64545", 0.35),
    "power_switch": ("#505050", 1.0), "electrode_board_L": ("#c08a2e", 1.0),
    "electrode_board_R": ("#c08a2e", 1.0), "electrode_conn_L": ("#f2f2f2", 1.0),
    "electrode_conn_R": ("#f2f2f2", 1.0),
}
LIGHT = np.array([-0.4, -0.7, 0.6])
LIGHT = LIGHT / np.linalg.norm(LIGHT)


def _mesh(shape, tol=0.15):
    verts, tris = shape.tessellate(tol, 0.3)
    v = np.array([(p.X, -p.Z, p.Y) for p in verts])
    return _subdivide(v[np.array(tris)]) if tris else np.zeros((0, 3, 3))


def _subdivide(tri, max_edge=6.0):
    """Split big triangles 4-ways until every edge is short: matplotlib sorts by triangle centroid,
    and the two triangles covering a large flat face sort wrongly against small nearby parts."""
    for _ in range(8):
        edge = np.linalg.norm(tri - np.roll(tri, 1, axis=1), axis=2).max(axis=1)
        big = edge > max_edge
        if not big.any():
            break
        t = tri[big]
        a, b, c = t[:, 0], t[:, 1], t[:, 2]
        ab, bc, ca = (a + b) / 2, (b + c) / 2, (c + a) / 2
        split = np.concatenate([np.stack(s, axis=1) for s in
                                ((a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca))])
        tri = np.concatenate([tri[~big], split])
    return tri


def _draw(ax, named, offsets=None):
    offsets = offsets or {}
    # One collection for everything: matplotlib depth-sorts per collection's polygons, so separate
    # collections per part get painted in the wrong order.
    pts, colors = [], []
    for name, shape in named.items():
        tri = _mesh(shape)
        if not len(tri):
            continue
        tri = tri + np.array(offsets.get(name, (0, 0, 0)))
        n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
        shade = 0.45 + 0.55 * np.abs(n @ LIGHT)
        base, alpha = COLORS.get(name, ("#999999", 1.0))
        rgb = np.array(matplotlib.colors.to_rgb(base))
        fc = np.clip(rgb[None, :] * shade[:, None], 0, 1)
        colors.append(np.concatenate([fc, np.full((len(fc), 1), alpha)], axis=1))
        pts.append(tri)
    tris = np.concatenate(pts)
    ax.add_collection3d(Poly3DCollection(tris, facecolors=np.concatenate(colors), edgecolors="none",
                                         linewidths=0))
    pts = tris.reshape(-1, 3)
    lo, hi = pts.min(0), pts.max(0)
    mid, r = (lo + hi) / 2, (hi - lo).max() / 2
    ax.set_xlim(mid[0] - r, mid[0] + r)
    ax.set_ylim(mid[1] - r, mid[1] + r)
    ax.set_zlim(mid[2] - r, mid[2] + r)
    ax.set_box_aspect((1, 1, 1))
    ax.set_axis_off()


def _figure(title, named, elev, azim, path, offsets=None):
    fig = plt.figure(figsize=(9, 9), dpi=130)
    ax = fig.add_subplot(111, projection="3d", computed_zorder=True)
    _draw(ax, named, offsets)
    ax.view_init(elev=elev, azim=azim)
    ax.set_title(title, fontsize=11)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def render_all(printed, components, out_dir):
    everything = {**printed, **components}
    paths = []

    p = out_dir / "render_front.png"
    _figure("Assembled - front 3/4", {k: everything[k] for k in
            ("front_shell", "back_cover", "knob", "panel")}, 18, -62, p)
    paths.append(p)

    p = out_dir / "render_interior.png"
    inside = {k: v for k, v in everything.items() if k not in ("back_cover", "usb_plug", "sd_card_path")}
    _figure("Interior - back cover removed", inside, -25, 110, p)
    paths.append(p)

    p = out_dir / "render_exploded.png"
    order = ["knob", "front_shell", "panel", "panel_backer", "hat", "battery_zone", "pcb",
             "encoder_body", "encoder_bushing", "encoder_shaft", "usb_c", "sd_socket", "power_switch", "electrode_board_L",
             "electrode_board_R", "electrode_conn_L", "electrode_conn_R", "back_cover"]
    lift = {"knob": 60, "front_shell": 30, "panel": 12, "panel_backer": 0, "hat": -15, "battery_zone": -15,
            "pcb": -15, "encoder_body": -15, "encoder_bushing": -15, "encoder_shaft": -15, "usb_c": -15, "sd_socket": -15,
            "power_switch": -15, "electrode_board_L": -15, "electrode_board_R": -15,
            "electrode_conn_L": -15, "electrode_conn_R": -15, "back_cover": -45}
    _figure("Exploded", {k: everything[k] for k in order}, 20, -55, p,
            offsets={k: (0, -v, 0) for k, v in lift.items()})
    paths.append(p)

    p = out_dir / "render_bottom.png"
    _figure("Bottom edge - power button tab, microSD, USB-C", {k: everything[k] for k in
            ("front_shell", "back_cover", "knob", "panel")}, -75, -90, p)
    paths.append(p)

    # Section through the encoder axis (X = 0), viewed from the right side.
    p = out_dir / "render_section.png"
    half = Pos(-500, 0, 0) * Box(1000, 1000, 1000)
    cut = {}
    for k, v in everything.items():
        if k in ("usb_plug", "sd_card_path"):
            continue
        c = v & half
        if c is not None and c.volume > 1e-6:
            cut[k] = c
    _figure("Section at X = 0 (encoder axis), from the right", cut, 0, 0, p)
    paths.append(p)
    return paths
