from fastapi.templating import Jinja2Templates

from app.client import client_context
from app.config import ROOT
from app.catalogs import (
    ADDICTION_TYPES,
    AGE_GROUPS,
    CANDIDATE_ACTIONS,
    CONFIDENCE,
    COST_TYPES,
    DISTRICTS,
    GENDERS,
    OFFICIAL_AUTHORITIES,
    OPERATOR_TYPES,
    ORG_TYPES,
    RATINGS,
    SECTORS,
    SERVICE_KINDS,
    SERVICE_TYPES,
    label,
)

templates = Jinja2Templates(
    directory=str(ROOT / "app" / "templates"),
    context_processors=[client_context],
)
templates.env.globals.update(
    {
        "ORG_TYPES": ORG_TYPES,
        "ADDICTION_TYPES": ADDICTION_TYPES,
        "SERVICE_KINDS": SERVICE_KINDS,
        "SERVICE_TYPES": SERVICE_TYPES,
        "OPERATOR_TYPES": OPERATOR_TYPES,
        "DISTRICTS": DISTRICTS,
        "RATINGS": RATINGS,
        "CONFIDENCE": CONFIDENCE,
        "COST_TYPES": COST_TYPES,
        "AGE_GROUPS": AGE_GROUPS,
        "GENDERS": GENDERS,
        "SECTORS": SECTORS,
        "CANDIDATE_ACTIONS": CANDIDATE_ACTIONS,
        "OFFICIAL_AUTHORITIES": OFFICIAL_AUTHORITIES,
        "label": label,
    }
)
