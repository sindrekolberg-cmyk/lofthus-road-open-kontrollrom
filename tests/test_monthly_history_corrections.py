from pathlib import Path

from lro_history import HistoryStore


def store() -> HistoryStore:
    return HistoryStore(Path(__file__).resolve().parents[1] / "data")


def test_february_2022_podium_is_complete():
    df = store().monthly_podiums()
    feb = df[(df["season"] == "2021/22") & (df["month"] == "Februar")]
    by_place = {int(row.place): row.manager for row in feb.itertuples()}
    assert by_place[1] == "Adrian Johansen"
    assert by_place[2] == "Nickolai Macpherson"
    assert by_place[3] == "Mats Arntzen"


def test_september_2022_tied_second_has_no_bronze():
    calendar = store().monthly_calendar(season="2022/23")
    september = calendar[calendar["month"] == "September"].iloc[0]
    assert september["winner"] == "Sindre Jakobsen"
    assert set(september["runner_up"].split(" / ")) == {"Lars Arnold Nermark", "Lars Egil Karlsen Furebotten"}
    assert september["third"] == ""

    medals = store().monthly_medals(season="2022/23")
    for manager in ("Lars Arnold Nermark", "Lars Egil Karlsen Furebotten"):
        row = medals[medals["manager"] == manager].iloc[0]
        assert int(row["silver"]) >= 1
        assert int(row["bronze"]) == 0
