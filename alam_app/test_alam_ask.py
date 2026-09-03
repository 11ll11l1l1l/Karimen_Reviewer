"""Regression tests for deterministic, evidence-only Ask ALAM retrieval."""
from alam_ask import grounded_answer, grounded_perspectives, grounded_sources, rank_records, relevance_score

VISA={"id":"visa-fee","_category":"practical","title":"Japan visa renewal fees change in October","summary":"Residence renewal costs rise from October.","why_it_matters":"Foreign residents may pay more.","tags":["Japan","Visa Renewal","Immigration"],"importance":98,"confidence":99,"content":{"key_message":"File only when your residence application is genuinely ready.","reading_levels":{"30 sec":{"bottom_line":"Check the official filing window."}}},"sources":[{"publisher":"Immigration Services Agency of Japan","title":"Official fee notice","url":"https://www.moj.go.jp/isa/example.html","source_type":"official"},{"publisher":"Duplicate","title":"Duplicate URL","url":"https://www.moj.go.jp/isa/example.html"},{"publisher":"Unsafe","title":"Unsafe","url":"javascript:alert(1)"}]}
QUAKE={"id":"quake-science","_category":"discover","title":"Japan maps earthquake plate locking more clearly","summary":"Researchers combined seismic and deformation observations.","tags":["Earthquake","Science"],"importance":86,"confidence":94,"content":{"key_message":"Better plate-locking maps are not an exact earthquake countdown."}}

def test_relevant_record_ranks_first():
    ranked=rank_records([QUAKE,VISA],"visa renewal fee");assert ranked;assert ranked[0][1]["id"]=="visa-fee"
def test_unrelated_high_quality_record_does_not_match():
    assert relevance_score(VISA,"penguin habitat antarctica")==0;assert rank_records([VISA,QUAKE],"penguin habitat antarctica")==[]
def test_grounded_answer_reuses_record_text_exactly():
    answer=grounded_answer(QUAKE);assert answer==QUAKE["content"]["key_message"];assert "countdown" in answer
def test_quality_score_cannot_create_relevance():
    unrelated=dict(VISA);unrelated["importance"]=100;unrelated["confidence"]=100;assert relevance_score(unrelated,"ocean salinity")==0
def test_v5_semantic_and_nested_quality_scores_rank_safely():
    low=dict(VISA);low["id"]="a-low";low["importance"]=10;low["confidence"]=10
    high=dict(VISA);high["id"]="z-high";high["importance"]={"score":"92"};high["confidence"]="HIGH"
    ranked=rank_records([low,high],"visa renewal fee");assert ranked[0][1]["id"]=="z-high";assert relevance_score(high,"visa renewal fee")>relevance_score(low,"visa renewal fee")
def test_grounded_sources_are_safe_and_deduplicated():
    sources=grounded_sources(VISA);assert len(sources)==1;assert sources[0]["publisher"]=="Immigration Services Agency of Japan";assert sources[0]["source_type"]=="official";assert sources[0]["url"].startswith("https://")
def test_grounded_perspectives_are_same_story_and_challenge_first():
    comments=[
        {"story_id":"visa-fee","persona_id":"kiko-kuryoso","stance":"SUPPORT","body":"Check the filing window.","created_at":"2026-09-03T07:00:00+09:00"},
        {"story_id":"visa-fee","persona_id":"mara-teka","stance":"CHALLENGE","body":"Do not assume every applicant pays the maximum.","created_at":"2026-09-03T07:01:00+09:00"},
        {"story_id":"quake-science","persona_id":"other","stance":"CHALLENGE","body":"Wrong story."},
        {"story_id":"visa-fee","persona_id":"bad","stance":"UNKNOWN","body":"Invalid stance."},
    ]
    items=grounded_perspectives(comments,"visa-fee");assert len(items)==2;assert items[0]["stance"]=="CHALLENGE";assert items[0]["persona"]=="Mara Teka";assert all("Wrong story" not in item["body"] for item in items)

if __name__=="__main__":
    tests=[value for name,value in globals().items() if name.startswith("test_") and callable(value)]
    for test in tests:test()
    print(f"Ask ALAM retrieval regression passed ({len(tests)} tests)")
