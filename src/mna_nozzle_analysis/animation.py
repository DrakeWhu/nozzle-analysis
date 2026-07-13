from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter, FuncAnimation
import numpy as np

from .fields import FieldFrame
from .geometry import NozzleGeometry


def write_ez_animation(
    frames: list[FieldFrame],
    geometry: NozzleGeometry,
    output: str | Path,
    *,
    fps: int = 8,
    dpi: int = 150,
) -> Path:
    if not frames:
        raise ValueError("cannot animate an empty field series")
    reference = frames[0]
    for frame in frames[1:]:
        if frame.ez_v_m.shape != reference.ez_v_m.shape:
            raise ValueError("animation frames do not share one grid")
        if not np.allclose(frame.z_m, reference.z_m) or not np.allclose(
            frame.transverse_m, reference.transverse_m
        ):
            raise ValueError("animation frame coordinates changed")

    try:
        import imageio_ffmpeg

        matplotlib.rcParams["animation.ffmpeg_path"] = imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass
    if not FFMpegWriter.isAvailable():
        raise RuntimeError(
            "MP4 requested but ffmpeg is unavailable; install mna-nozzle-analysis[animation]"
        )

    samples = np.concatenate(
        [np.abs(frame.ez_v_m[np.isfinite(frame.ez_v_m)]).ravel() for frame in frames]
    )
    vmax = max(float(np.percentile(samples, 99.5)), np.finfo(float).tiny)
    extent = [
        float(reference.z_m.min() * 1.0e6),
        float(reference.z_m.max() * 1.0e6),
        float(reference.transverse_m.min() * 1.0e6),
        float(reference.transverse_m.max() * 1.0e6),
    ]
    fig, ax = plt.subplots(figsize=(9, 5))
    image = ax.imshow(
        reference.ez_v_m * 1.0e-12,
        origin="lower",
        extent=extent,
        aspect="auto",
        interpolation="nearest",
        cmap="RdBu_r",
        vmin=-vmax * 1.0e-12,
        vmax=vmax * 1.0e-12,
    )
    z = np.linspace(geometry.z_head, geometry.z_exit, 800)
    inner = geometry.inner_radius(z)
    outer = inner + geometry.d_paper
    ax.plot(z * 1.0e6, inner * 1.0e6, "k--", linewidth=0.8)
    ax.plot(z * 1.0e6, outer * 1.0e6, "k-", linewidth=0.8)
    if np.nanmin(reference.transverse_m) < 0.0:
        ax.plot(z * 1.0e6, -inner * 1.0e6, "k--", linewidth=0.8)
        ax.plot(z * 1.0e6, -outer * 1.0e6, "k-", linewidth=0.8)
    ax.set(xlabel="z [um]", ylabel=f"{reference.transverse_name} [um]")
    title = ax.set_title("")
    fig.colorbar(image, ax=ax, label="Ez [TV/m]")

    def update(index: int):
        frame = frames[index]
        image.set_data(frame.ez_v_m * 1.0e-12)
        title.set_text(
            f"Ez, all RZ modes at theta=0 | {frame.time_s * 1.0e15:.2f} fs"
        )
        return image, title

    animation = FuncAnimation(fig, update, frames=len(frames), blit=False)
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    animation.save(target, writer=FFMpegWriter(fps=fps), dpi=dpi)
    plt.close(fig)
    return target

