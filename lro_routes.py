from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode
from typing import Any, Mapping


PUBLIC_PAGES = {"Forside", "Ligaen", "Rivalradar", "Hall of Fame", "Manager", "Spiller"}
LEAGUE_VIEWS = {"Tabell", "Måneden", "Sammenlign", "Sesongen"}


@dataclass(frozen=True)
class Route:
    page: str = "Forside"
    view: str = "Tabell"
    manager: int = 0
    player: int = 0
    me: int = 0
    rival: int = 0
    compare: tuple[int, ...] = ()
    debug: bool = False


def _first(params: Mapping[str, Any], key: str) -> str:
    value = params.get(key, "")
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return str(value or "")


def _int(value: Any) -> int:
    try:
        return int(str(value))
    except Exception:
        return 0


def parse_route(params: Mapping[str, Any]) -> Route:
    page = _first(params, "page") or "Forside"
    if page not in PUBLIC_PAGES:
        page = "Forside"
    view = _first(params, "view") or _first(params, "league_view") or "Tabell"
    if view not in LEAGUE_VIEWS:
        view = "Tabell"
    compare = []
    for item in _first(params, "compare").split(","):
        eid = _int(item.strip())
        if eid and eid not in compare:
            compare.append(eid)
    return Route(
        page=page,
        view=view,
        manager=_int(_first(params, "manager")),
        player=_int(_first(params, "player")),
        me=_int(_first(params, "me")),
        rival=_int(_first(params, "rival")),
        compare=tuple(compare[:8]),
        debug=_first(params, "debug") == "1",
    )


def href(page: str, *, view: str = "", manager: int = 0, player: int = 0, me: int = 0, rival: int = 0, compare: list[int] | tuple[int, ...] = (), debug: bool = False) -> str:
    query: dict[str, str] = {"page": page}
    if view:
        query["view"] = view
    if manager:
        query["manager"] = str(int(manager))
    if player:
        query["player"] = str(int(player))
    if me:
        query["me"] = str(int(me))
    if rival:
        query["rival"] = str(int(rival))
    if compare:
        query["compare"] = ",".join(str(int(x)) for x in compare if int(x))
    if debug:
        query["debug"] = "1"
    return "?" + urlencode(query)


def home_href(me: int = 0) -> str:
    return href("Forside", me=me)


def league_href(view: str = "Tabell", me: int = 0) -> str:
    return href("Ligaen", view=view, me=me)


def manager_href(entry: int, me: int = 0) -> str:
    return href("Manager", manager=int(entry), me=me)


def player_href(element: int, me: int = 0) -> str:
    return href("Spiller", player=int(element), me=me)


def rival_href(me: int, rival: int = 0) -> str:
    return href("Rivalradar", me=int(me), rival=int(rival))


def compare_href(entries: list[int] | tuple[int, ...], me: int = 0) -> str:
    return href("Ligaen", view="Sammenlign", compare=entries, me=me)
