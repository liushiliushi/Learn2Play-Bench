from games.patch_reality.patch_reality import PatchRealityGame
from games.patch_reality.solve import canonical_oracle


def _wait_out_level(game):
    level_index = game._level_idx
    last_obs = ""
    while not game.done and game._level_idx == level_index:
        last_obs, _reward, _done, _info = game.step("wait")
    return last_obs


def test_legacy_oracles_and_failure_behavior_are_unchanged():
    assert canonical_oracle(seed=42, mode="easy").score == 1266
    assert canonical_oracle(seed=42, mode="hard").score == 853

    hard = PatchRealityGame(seed=42, mode="hard", lang="en")
    _wait_out_level(hard)
    assert hard.done
    assert hard._failed_at == "hard_01"


def test_moderate_has_eight_levels_ten_focus_and_public_help():
    game = PatchRealityGame(seed=42, mode="moderate", lang="en")
    intro, info = game.reset()

    assert len(game._levels) == 8
    assert game._focus_limit == 10
    assert "TUTORIAL 1/2" in intro
    assert "source: where the anomaly originates" in intro
    assert "help" in info["valid"]

    before = (game.score, game.turn_count, game._focus_remaining, game._steps)
    help_text, reward, done, _info = game.step("help")
    after = (game.score, game.turn_count, game._focus_remaining, game._steps)
    assert "PATCH REALITY · MODERATE" in help_text
    assert reward == 0
    assert not done
    assert before == after


def test_moderate_tutorial_fades_after_level_two():
    game = PatchRealityGame(seed=42, mode="moderate", lang="en")
    obs, *_ = game.step("observe coin")
    assert "symptom need not be the source" in obs

    _wait_out_level(game)
    assert game._level_idx == 1
    obs, *_ = game.step("observe residual_patch")
    assert "Audit residual_patch" in obs

    _wait_out_level(game)
    assert game._level_idx == 2
    assert "TUTORIAL" not in game._scene_intro(game._level)


def test_wrong_complete_diagnosis_gives_generic_recovery_feedback():
    game = PatchRealityGame(seed=42, mode="moderate", lang="en")
    for action in ("observe coin", "observe pavement", "observe drain"):
        game.step(action)
    for action in (
        "diagnose source=object",
        "diagnose type=record_conflict",
        "diagnose strategy=audit_first",
    ):
        obs, *_ = game.step(action)

    assert "inconsistent with the evidence" in obs
    assert "source=environment" not in obs
    assert game._focus_remaining == 4
    assert not any(a.startswith("patch ") for a in game.get_valid_actions())


def test_correct_diagnosis_and_evidence_unlock_patch():
    game = PatchRealityGame(seed=42, mode="moderate", lang="en")
    for action in (
        "observe coin",
        "observe pavement",
        "observe drain",
        "diagnose source=environment",
        "diagnose type=physics_conflict",
        "diagnose strategy=environment_cover",
    ):
        game.step(action)

    assert "patch pavement.friction +15%" in game.get_valid_actions()


def test_ordinary_failure_debriefs_and_continues():
    game = PatchRealityGame(seed=42, mode="moderate", lang="en")
    for action in (
        "diagnose source=environment",
        "diagnose type=record_conflict",
        "diagnose strategy=audit_first",
    ):
        game.step(action)
    obs = _wait_out_level(game)

    assert not game.done
    assert game._level_idx == 1
    assert game._failed_levels == ["hard_01"]
    assert "source=environment (matched the evidence)" in obs
    assert "type=record_conflict (did not match the evidence)" in obs
    assert "Level 2/8" in obs


def test_moderate_oracle_completes_multiple_generated_episodes():
    for seed in (1, 7, 42):
        for episode in (0, 1, 2):
            result = canonical_oracle(
                seed=seed, episode=episode, mode="moderate")
            assert result.completed
            assert result.levels_cleared == 8
            assert 850 <= result.score <= 858


def test_moderate_chinese_onboarding_and_labels():
    game = PatchRealityGame(seed=42, mode="moderate", lang="zh")
    intro, info = game.reset()
    assert "补丁现实 · 适中模式" in intro
    assert "教学 1/2" in intro
    assert game.get_action_label("help") == "玩法说明"
    assert game.get_action_label("diagnose source=environment") == "诊断 来源=环境"
    assert "help" in info["valid"]


def test_zh_labels_replay_identically_under_en_after_language_switch():
    # webplay stores the localized labels the user clicked and replays them
    # verbatim after a lobby language switch — zh-recorded history must be
    # valid input under lang="en" and reproduce the exact same trajectory.
    script = (
        "observe coin",
        "observe pavement",
        "observe drain",
        "diagnose source=environment",
        "diagnose type=physics_conflict",
        "diagnose strategy=environment_cover",
        "help",
        "patch pavement.friction +15%",
    )

    zh = PatchRealityGame(seed=42, mode="moderate", lang="zh")
    replayed = []
    for action in script:
        label = zh.get_action_label(action)
        replayed.append(label)
        obs, *_ = zh.step(label)
        assert "未知行动" not in obs

    en = PatchRealityGame(seed=42, mode="moderate", lang="en")
    for command in replayed:
        obs, *_ = en.step(command)
        assert "Unknown action" not in obs
        assert "未知行动" not in obs

    assert en.score == zh.score
    assert en._level_idx == zh._level_idx
    assert en._focus_remaining == zh._focus_remaining
    assert en._steps == zh._steps

    # The reverse direction (canonical English under zh) must keep working.
    zh2 = PatchRealityGame(seed=42, mode="moderate", lang="zh")
    for action in script:
        obs, *_ = zh2.step(action)
        assert "未知行动" not in obs
    assert zh2.score == zh.score


def test_moderate_removes_literal_answer_sentence_only_from_moderate():
    moderate = PatchRealityGame(seed=42, mode="moderate", lang="en")
    hard = PatchRealityGame(seed=42, mode="hard", lang="en")
    moderate_text = moderate._base_levels[-1].objects["name_anchor"].observe_text
    hard_text = hard._base_levels[-1].objects["name_anchor"].observe_text
    assert "correct repair" not in moderate_text
    assert "correct repair" in hard_text
