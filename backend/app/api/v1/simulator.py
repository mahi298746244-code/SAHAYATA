"""Impact simulator endpoints (clearly labelled planning estimates)."""
from fastapi import APIRouter

from app.api.deps import AdminUser, AuthorityUser, DbDep, role_name
from app.schemas.misc import SimulatorRun, SimulatorParams
from app.services import simulator
from app.services.audit import record_audit

router = APIRouter(prefix="/simulator", tags=["simulator"])


@router.post("/run")
def run(payload: SimulatorRun, db: DbDep, user: AuthorityUser):
    return simulator.run_simulation(db, payload.budget, payload.sectors)


@router.get("/parameters")
def get_parameters(db: DbDep, user: AuthorityUser):
    return {"parameters": simulator.get_params(db),
            "disclaimer": "Simulation / Planning Estimate assumptions"}


@router.put("/parameters")
def set_parameters(payload: SimulatorParams, db: DbDep, user: AdminUser):
    before = simulator.get_params(db)
    params = {
        "cost_per_problem": {k: float(v) for k, v in payload.cost_per_problem.items()},
        "beneficiaries_per_problem": {k: int(v) for k, v in payload.beneficiaries_per_problem.items()},
    }
    simulator.save_params(db, params, str(user.id))
    record_audit(str(user.id), role_name(user), "simulator.parameters_update",
                 "simulation_parameters", "simulator.defaults",
                 before=before, after=params, reason="admin update")
    return {"ok": True, "parameters": params}
