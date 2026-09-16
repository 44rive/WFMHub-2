from ortools.sat.python import cp_model


def build_minimum_coverage_model(required: list[int], agent_count: int) -> cp_model.CpModel:
    """Seed CP-SAT model for future shift/interval optimization."""
    model = cp_model.CpModel()
    assigned = [model.new_int_var(0, agent_count, f"assigned_{i}") for i in range(len(required))]
    shortage = [model.new_int_var(0, agent_count, f"shortage_{i}") for i in range(len(required))]
    for i, need in enumerate(required):
        model.add(assigned[i] + shortage[i] >= need)
    model.minimize(sum(shortage))
    return model
