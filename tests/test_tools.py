"""Tools around the benchmark: batched frontier prompts, the human-test scorer, well-formed replies."""
import json
from argparse import Namespace

from frontier import batch_prompt, parse_batch
from human_eval import score_files

HEAD = "This is a topographic map of a 4 km x 4 km area. North is up.\n\n"
T1 = dict(task_id="s__Q1__map", qid="Q1", question="Which villages receive the water?", scoring="set",
          options=["V1", "V2", "V3"], answer=["V2"], traps={}, skill="trace_downstream",
          prompt=HEAD + 'Question: Which villages receive the water?\n\nReply with ONLY a JSON object of the form '
                        '{"answer": ...} where the answer is a JSON list of labels, e.g. ["V1"].')
T2 = dict(task_id="s__Q5__map", qid="Q5", question="Which way does the stream flow?", scoring="compass",
          options=["N", "NE", "E", "SE", "S", "SW", "W", "NW"], answer="S", traps={}, skill="read_flow_direction",
          prompt=HEAD + 'Question: Which way does the stream flow?\n\nReply with ONLY a JSON object of the form '
                        '{"answer": ...} where the answer is one of N, NE, E, SE, S, SW, W, NW.')


def test_batch_prompt_keeps_header_questions_and_formats_once():
    p = batch_prompt([T1, T2])
    assert p.count("North is up") == 1                       # shared header sent once
    assert "Q1: Which villages receive the water?" in p and "Q5: Which way" in p
    assert "a JSON list of labels" in p and "one of N, NE" in p
    assert p.rstrip().endswith('{"Q1": ..., "Q5": ...}')


def test_parse_batch_tolerates_fences_and_text():
    assert parse_batch('```json\n{"Q1": ["V2"], "Q5": "S"}\n```') == {"Q1": ["V2"], "Q5": "S"}
    assert parse_batch('Sure. {"Q1": []} Hope that helps') == {"Q1": []}
    assert parse_batch("no json here") == {}


def test_human_scorer_accepts_pasted_text(tmp_path):
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "tasks.jsonl").write_text("".join(json.dumps(t) + "\n" for t in (T1, T2)))
    sheet = tmp_path / "answers_a.txt"
    sheet.write_text('my answers: {"name": "A", "answers": [{"id": "s__Q1__map", "answer": ["V2"], "seconds": 9},'
                     ' {"id": "s__Q5__map", "answer": "N", "seconds": 5}]} thanks')
    score_files(Namespace(files=[str(sheet)], dataset=str(ds), run=str(tmp_path / "none"), out=str(tmp_path / "o")))
    text = (tmp_path / "o" / "HUMAN_RESULTS.md").read_text()
    assert "Overall human accuracy: 50%" in text


def test_zero_count_pick_returns_nothing_in_checks_v2():
    import numpy as np
    from thirstmap import scene
    pool, rng = [0, 50, 5000, 12000, 20000], np.random.default_rng(0)
    old = scene._ZERO_PICKS_NONE
    try:
        scene._ZERO_PICKS_NONE = True
        assert scene._pick_spaced(rng, pool, 0, []) == []
        scene._ZERO_PICKS_NONE = False                  # v1.0 behaviour, kept so the dataset rebuilds exactly
        assert len(scene._pick_spaced(rng, pool, 0, [])) > 1
    finally:
        scene._ZERO_PICKS_NONE = old


def test_label_occlusions():
    from thirstmap.validate import label_occlusions
    labels = [("V1", (10, 10, 30, 20)), ("V2", (100, 100, 120, 110))]
    assert label_occlusions(labels, [(0, 0, 25, 25)]) == {"V1"}
    assert label_occlusions(labels, []) == set()


def test_cli_lists_and_dispatches(capsys, tmp_path, monkeypatch):
    import pytest
    from thirstmap import cli
    assert cli.main([]) == 0 and "generate" in capsys.readouterr().out
    assert cli.main(["nope"]) == 2
    with pytest.raises(SystemExit) as e:                 # argparse --help exits 0 after printing the options
        cli.main(["generate", "--help"])
    assert e.value.code == 0 and "--level" in capsys.readouterr().out


def test_demo_results_without_open_models(tmp_path):
    """run_all.sh passes results/offline_baselines (mock models only) to build_demo.py; that must not crash."""
    from build_demo import results_html
    vc = {"correct": 5, "n": 10, "chance": 0.1, "p_value": 0.01}
    (tmp_path / "summary.json").write_text(json.dumps({"models": ["mock:oracle", "mock:random"],
                                                       "vs_chance": {"mock:oracle": vc, "mock:random": vc}}))
    assert "Open models, main run: 0 questions" in results_html(tmp_path, None)
