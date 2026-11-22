"""The adaptive eye exam must rank a perfect model above a guesser and a model that fails above level 2."""
import random

from staircase import staircase


class Fake:
    name = "fake"

    def __init__(self, rule):
        self.rule = rule

    def ask(self, task, with_image=True):
        ok = self.rule(task["level"])
        ans = task["answer"] if ok else "WRONG"
        return dict(raw='{"answer": "%s"}' % ans, input_tokens=0, output_tokens=0)


def pool():
    return {lv: [dict(task_id=f"t{lv}_{k}", level=lv, scoring="choice", answer="A", options=["A", "B"],
                      traps={}) for k in range(30)] for lv in range(1, 6)}


def test_perfect_model_never_breaks():
    assert staircase(Fake(lambda lv: True), pool(), 16, random.Random(0))["threshold"] == 5.5


def test_model_breaking_above_level_2_is_located():
    r = staircase(Fake(lambda lv: lv <= 2), pool(), 24, random.Random(0))
    assert 2.0 <= r["threshold"] <= 3.0


def test_always_wrong_model_sinks():
    assert staircase(Fake(lambda lv: False), pool(), 16, random.Random(0))["threshold"] == 0.5
