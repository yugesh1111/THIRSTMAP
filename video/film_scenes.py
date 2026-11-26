"""Rebuild, from their seeds, only the dataset scenes the films show, so the films can be remade from a fresh clone
without downloading the 2.1 GB dataset release.

    python video/film_scenes.py     # -> video/build/dataset/scenes/<scene>/ and .../variants/level1_seed14596/

The films show dataset v1.0 scenes. Each is rebuilt from its seed with the v1.0 checks (generate(strict=False)) and
the build job that verify_results.recover_jobs finds for it, which is how docs/AUDIT.md rebuilds v1.0 byte for byte.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from generate import generate  # noqa: E402
from verify_results import recover_jobs  # noqa: E402

SCENES = ["level4_seed48947", "level2_seed21111", "level1_seed100250", "level3_seed31409", "level4_seed101214",
          "level5_seed111221", "level1_seed14596", "real_navi_mumbai_seed31312", "real_hyderabad_seed31312",
          "real_pune_seed31021", "real_chennai_seed31021"]
VARIANT_SCENE = "level1_seed14596"


def main():
    ds = ROOT / "video/build/dataset"
    for name in SCENES:
        if (ds / "scenes" / name / "answer_key.json").exists():
            print(f"have  {name}")
            continue
        real = name.split("_seed")[0][5:] if name.startswith("real_") else None
        level, seed = (3 if real else int(name[5])), int(name.split("_seed")[1])
        (k, _), = recover_jobs({"level": level, "seed": seed}, k_max=50)   # v1.0: 50 jobs per level, 15 per city
        folder = generate(level, seed, str(ds / "scenes"), max_tries=1, bi=k, real=real, strict=False)[0]
        assert folder.name == name, f"rebuilt {folder.name}, expected {name}"
        print(f"built {name}")

    import json
    from thirstmap import render_sat
    from variants import VARIANTS, rebuild
    vdir = ds / "variants" / VARIANT_SCENE
    if all((vdir / f"{v}.png").exists() for v in VARIANTS):
        print(f"have  variants of {VARIANT_SCENE}")
        return
    key = json.loads((ds / "scenes" / VARIANT_SCENE / "answer_key.json").read_text())
    s, p, nm, P = rebuild(key, VARIANT_SCENE, ds)
    vdir.mkdir(parents=True, exist_ok=True)
    for v, kw in VARIANTS.items():
        render_sat.render(s, p, nm, P, title=f"{key.get('scene_id', VARIANT_SCENE)} | satellite-style | "
                          f"{v} | {s['drain_note'].lower()}", **kw).save(vdir / f"{v}.png")
    print(f"built variants of {VARIANT_SCENE}")


if __name__ == "__main__":
    main()
