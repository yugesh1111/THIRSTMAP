"""Questions and answer key, computed from the scene script.

Each question lists the image styles that contain enough evidence to answer
it. Example: comparing elevations needs contour lines, so Q4 is map-only.
"""
import math

from .terrain import rc

COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def bisect_index(seed, n):
    return int(seed) % n


def flow_direction(s):
    """Compass direction of the stream just below O; None if too close to a sector edge."""
    O = s["O"]
    for k in range(6, 13):
        (r0, c0), (r1, c1) = rc(O), rc(s["path"][min(k, len(s["path"]) - 1)])
        ang = math.degrees(math.atan2(c1 - c0, -(r1 - r0))) % 360   # 0 = north, clockwise
        if 7 <= (ang + 22.5) % 45 <= 38:
            return COMPASS[int(((ang + 22.5) % 360) // 45)]
    return None


def names(p):
    sit = p.get("siting") or {"sites": []}
    return dict(
        village={v: f"V{k + 1}" for k, v in enumerate(p["villages"])},
        wetland={w: "ABCD"[k] for k, w in enumerate(p["wet"])},
        farm={f: f"F{k + 1}" for k, f in enumerate(p["farms"])},
        site={x: f"S{k + 1}" for k, x in enumerate(sit["sites"])},
        monitor={x: f"M{k + 1}" for k, x in enumerate((p.get("plume") or {}).get("points", []))},
    )


def answer_key(s, p):
    nm = names(p)
    pos = {i: k for k, i in enumerate(s["path"])}
    hit = sorted([v for v in p["villages"] if v in pos], key=lambda v: pos[v])
    pe = s["disp"].flat[p["pond"]]
    lower = sorted(nm["farm"][f] for f in p["farms"] if s["disp"].flat[f] < pe)
    both = ["map", "satellite"]
    qs = [
        dict(id="Q1", skill="trace_downstream", styles=both,
             question="Cooling-tower wastewater from DC-1 enters the stream at outfall O. "
                      "Which villages would receive this water downstream? List all.",
             answer=sorted(nm["village"][v] for v in hit)),
        dict(id="Q2", skill="order_along_flow", styles=both,
             question="Which village would receive the wastewater first?",
             answer=nm["village"][hit[0]] if hit else "none"),
        dict(id="Q3", skill="nature_based_filtering", styles=both,
             question="A constructed wetland must clean ALL of the wastewater from O before it "
                      "reaches ANY village. Which candidate site (A-D) works?",
             answer=nm["wetland"][p["good"]]),
        dict(id="Q4", skill="read_elevation", styles=["map"],
             question=f"Treated water is stored in pond P (spot height {pe:.0f} m). Which farms can be "
                      "supplied by a gravity pipe, i.e. lie LOWER than the pond? List all.",
             answer=lower, margin_m=3),
    ]
    fdir = flow_direction(s)
    if fdir:
        qs.append(dict(id="Q5", skill="read_flow_direction", styles=both,
                       question="In which compass direction does the stream flow just below outfall O?",
                       answer=fdir))
    sit = p.get("siting")
    if sit:
        k = sit["sites"].index(sit["clean_site"])
        qs.append(dict(id="Q6", skill="siting_downstream_impact", styles=both,
                       question="Three sites S1-S3 are proposed for a new data centre. Each would discharge "
                                "wastewater at its marked outfall (dashed line). Whose wastewater would "
                                "reach NO village before leaving the area?",
                       answer=f"S{k + 1}"))
    itk = p.get("intake")
    if itk:
        qs.append(dict(id="Q7", skill="trace_upstream_catchment", styles=both,
                       question="DC-1 pumps its cooling water from intake I. Which villages draw water "
                                "upstream of I, on streams that flow into I (and so share that water)? List all.",
                       answer=sorted(nm["village"][v] for v in itk["upstream"])))
    pl = p.get("plume")
    if pl:
        warm_pts = [i for i, t in pl["point_dT"].items() if t > 3.0]
        qs.append(dict(id="Q8", skill="read_colour_scale_threshold", styles=["thermal"],
                       question="The thermal image shows how much warmer than normal the water is. "
                                "At which monitoring points (M1-M4) is the water MORE than 3 °C warmer "
                                "than normal? List all.",
                       answer=sorted(nm["monitor"][i] for i in warm_pts), margin_c=0.8))
        probe = sorted(warm_pts)[bisect_index(s["seed"], len(warm_pts))]
        qs.append(dict(id="Q9", skill="read_colour_scale_value", styles=["thermal"],
                       question=f"About how many °C warmer than normal is the water at monitoring point "
                                f"{nm['monitor'][probe]}?",
                       answer=round(pl["point_dT"][probe], 1), tolerance=1.5, point=probe))
    # answer options (for prompts and the random baseline) and trap labels (for error diagnosis)
    V = sorted(nm["village"].values(), key=lambda x: int(x[1:]))
    opts = {"Q1": V, "Q2": V, "Q7": V, "Q3": sorted(nm["wetland"].values()),
            "Q4": sorted(nm["farm"].values(), key=lambda x: int(x[1:])), "Q5": COMPASS,
            "Q6": sorted(nm["site"].values()), "Q8": sorted(nm["monitor"].values()), "Q9": [0, 15]}
    vl = lambda xs: [nm["village"][v] for v in xs]
    traps = {"Q1": {"upstream_same_stream": vl(p["trap_up"]), "near_but_other_stream": vl(p["trap_near"])},
             "Q2": {"upstream_same_stream": vl(p["trap_up"]), "near_but_other_stream": vl(p["trap_near"]),
                    "later_village": [nm["village"][v] for v in hit[1:]]},
             "Q3": {"too_late_after_village": [nm["wetland"][w] for w in p["wet_late"]],
                    "upstream_of_outfall": [nm["wetland"][w] for w in p["wet_up"]]},
             "Q7": {"downstream_not_upstream": vl([v for v in hit])}}
    if pl:
        by_kind = {}
        for i, kd in pl["point_kind"].items():
            by_kind.setdefault(kd, []).append(nm["monitor"][i])
        traps["Q8"] = {k: sorted(v) for k, v in by_kind.items() if k != "warm"}
    for q in qs:
        q["options"] = opts[q["id"]]
        if q["id"] in traps:
            q["traps"] = traps[q["id"]]
    truth = dict(hit=hit, lower=lower,
                 clean_site=sit["clean_site"] if sit else None,
                 upstream=itk["upstream"] if itk else [])
    return qs, nm, truth
