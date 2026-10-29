from fastapi import APIRouter

from app.routers.deps import Conn
from app.schemas import Envelope, SourcesData, StateRef
from app.services import registrations as reg
from app.services import sources
from app.services.common import meta

router = APIRouter(tags=["sources"])


@router.get("/sources", response_model=Envelope[SourcesData], summary="Data sources, rules, methodology, last ETL run")
def get_sources(conn: Conn):
    return {"data": sources.sources(conn), "meta": meta(conn, None, ["fuel", "maker", "category", "chargers_state", "chargers_omc"])}


@router.get("/meta/states", response_model=Envelope[list[StateRef]], summary="States and union territories")
def get_states_ref(conn: Conn):
    return {"data": reg.state_list(conn), "meta": meta(conn, None, [])}
