"""The scorer must accept every reasonable way a model writes a correct answer, and reject wrong ones."""
from thirstmap.scoring import score

T_SET = dict(scoring="set", answer=["V2", "V6"], options=["V1", "V2", "V3", "V4", "V5", "V6"],
             traps={"upstream_same_stream": ["V5"], "near_but_other_stream": ["V3"]})
T_CHOICE = dict(scoring="choice", answer="S2", options=["S1", "S2", "S3"], traps={})
T_DIR = dict(scoring="compass", answer="SE", options=["N", "NE", "E", "SE", "S", "SW", "W", "NW"], traps={})
T_NUM = dict(scoring="number", answer=5.0, tolerance=1.5, options=[0, 15], traps={})


def test_set_formats():
    for raw in ['{"answer": ["V2", "V6"]}', '```json\n{"answer": ["V6","V2"]}\n```',
                'Looking at the image... {"answer": "V2, V6"}', '{"answer": ["v2", "V6."]}']:
        assert score(T_SET, raw)["correct"], raw


def test_set_partial_credit_and_trap_diagnosis():
    r = score(T_SET, '{"answer": ["V2", "V5"]}')
    assert not r["correct"] and 0 < r["credit"] < 1
    assert "trap:upstream_same_stream" in r["tags"] and "missed_some" in r["tags"]
    r = score(T_SET, '{"answer": ["V2", "V3", "V6"]}')
    assert "trap:near_but_other_stream" in r["tags"]


def test_choice_and_direction():
    assert score(T_CHOICE, '{"answer": "S2"}')["correct"]
    assert score(T_CHOICE, '{"answer": "Site S2"}')["correct"]
    assert not score(T_CHOICE, '{"answer": "S2 or S3"}')["correct"]          # hedging is not an answer
    assert score(T_DIR, '{"answer": "south-east"}')["correct"]
    assert score(T_DIR, '{"answer": "NW"}')["tags"] == ["reversed_direction"]
    assert score(T_DIR, '{"answer": "S"}')["tags"] == ["off_by_one_sector"]


def test_number_tolerance():
    assert score(T_NUM, '{"answer": 6.2}')["correct"]
    assert score(T_NUM, '{"answer": "about 4 °C"}')["correct"]
    r = score(T_NUM, '{"answer": 9}')
    assert not r["correct"] and r["tags"] == ["overestimate"]


def test_unparseable():
    r = score(T_CHOICE, "I cannot determine this from the image.")
    assert not r["correct"] and r["tags"]


def test_cut_off_json_still_states_answer():
    # a reply cut off by the token limit, as a real small model produced it
    raw = ' {\n    "answer": "SE",\n    "city": "V3",\n    "country": "VILLAGE",\n    "sub_city'
    assert score(T_DIR, raw)["correct"]
    assert not score(T_DIR, ' {\n    "answer": "NW",\n    "note": "upstr')["correct"]
