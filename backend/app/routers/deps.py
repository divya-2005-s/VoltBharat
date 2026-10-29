from dataclasses import dataclass
from typing import Annotated, Optional

from fastapi import Depends, Query
from sqlalchemy.engine import Connection

from app.db import get_conn
from app.services.common import MONTH_PATTERN, Period, resolve_period, resolve_state

StartQ = Annotated[Optional[str], Query(pattern=MONTH_PATTERN, description="First month, YYYY-MM (default: first available)",
                                        examples=["2024-01"])]
EndQ = Annotated[Optional[str], Query(pattern=MONTH_PATTERN, description="Last month, YYYY-MM (default: latest available)",
                                      examples=["2026-09"])]
StateQ = Annotated[Optional[str], Query(max_length=80, description="State/UT name (case-insensitive), e.g. Karnataka")]

Conn = Annotated[Connection, Depends(get_conn)]


@dataclass
class Filters:
    conn: Connection
    period: Period
    state: Optional[str]


def filters(conn: Conn, start: StartQ = None, end: EndQ = None, state: StateQ = None) -> Filters:
    return Filters(conn, resolve_period(conn, start, end), resolve_state(conn, state))


def period_only(conn: Conn, start: StartQ = None, end: EndQ = None) -> Filters:
    return Filters(conn, resolve_period(conn, start, end), None)


FiltersDep = Annotated[Filters, Depends(filters)]
PeriodDep = Annotated[Filters, Depends(period_only)]
