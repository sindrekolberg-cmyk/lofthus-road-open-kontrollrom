from api.deep_analysis import DeepFPLProjectionProvider


def bootstrap():
    return {
        "teams": [
            {
                "id": 1,
                "name": "Alpha",
                "short_name": "ALP",
                "strength_defence_home": 1350,
                "strength_defence_away": 1320,
                "strength_attack_home": 1360,
                "strength_attack_away": 1300,
            },
            {
                "id": 2,
                "name": "Beta",
                "short_name": "BET",
                "strength_defence_home": 1000,
                "strength_defence_away": 980,
                "strength_attack_home": 1030,
                "strength_attack_away": 990,
            },
            {
                "id": 3,
                "name": "Gamma",
                "short_name": "GAM",
                "strength_defence_home": 1180,
                "strength_defence_away": 1160,
                "strength_attack_home": 1200,
                "strength_attack_away": 1170,
            },
        ]
    }


def player():
    return {
        "element_id": 99,
        "position_id": 3,
        "minutes": 720,
        "starts": 8,
        "xg": 4.0,
        "xa": 2.0,
        "goals_scored": 4,
        "assists": 3,
        "points_per_game": 6.1,
        "form": 7.2,
        "threat": 420,
        "creativity": 330,
        "influence": 350,
        "ict_index": 255,
        "total_points": 63,
        "selected_by_pct": 9.0,
        "transfers_in_event": 180000,
        "transfers_out_event": 30000,
        "raw": {
            "expected_goals_per_90": "0.50",
            "expected_assists_per_90": "0.25",
            "expected_goal_involvements_per_90": "0.75",
            "penalties_order": 1,
            "direct_freekicks_order": 2,
            "corners_and_indirect_freekicks_order": 1,
        },
    }


def test_deep_projection_uses_role_fixture_and_set_pieces():
    provider = DeepFPLProjectionProvider(bootstrap())
    fixtures = [
        {"event": 1, "home": True, "opponent_id": 2, "difficulty": 2},
        {"event": 2, "home": False, "opponent_id": 3, "difficulty": 3},
        {"event": 3, "home": True, "opponent_id": 2, "difficulty": 2},
        {"event": 4, "home": False, "opponent_id": 2, "difficulty": 2},
        {"event": 5, "home": True, "opponent_id": 1, "difficulty": 4},
    ]
    score = provider.score(player(), fixtures, 5)
    detail = provider.details[99]

    assert score["source"] == "fpl_deep_v2"
    assert score["projection"] > 0.55
    assert detail["stats"]["xgi_per90"] == 0.75
    assert detail["stats"]["next_fixture_count"] == 5
    assert detail["stats"]["weaker_defence_fixtures"] >= 3
    assert any("Førstevalg på straffer" in line for line in detail["evidence"])
    assert any("neste 5" in line for line in detail["evidence"])
