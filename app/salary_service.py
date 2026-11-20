"""Salary logic: effective-dated pay. Old rows are never overwritten."""
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .models import SalaryRevision, SalaryStructure

CENT = Decimal("0.01")


def get_structure(db: Session, employee_id: str, on_date: date) -> list[SalaryStructure]:
    """Pay components valid on a date. Both the start and end date are inclusive."""
    stmt = (
        select(SalaryStructure)
        .where(
            SalaryStructure.employee_id == employee_id,
            SalaryStructure.effective_from <= on_date,
            or_(SalaryStructure.effective_to.is_(None), SalaryStructure.effective_to >= on_date),
        )
        .order_by(SalaryStructure.component_id)
    )
    return list(db.scalars(stmt))


def monthly_earnings(rows) -> Decimal:
    return sum((Decimal(r.monthly_amount) for r in rows if r.component_type == "EARNING"), Decimal("0"))


def _last_number(db: Session, column) -> int:
    last = db.scalar(select(func.max(column)))
    return int(last.split("-")[1]) if last else 0


def revise_salary(
    db: Session,
    employee_id: str,
    effective_from: date,
    new_annual_fixed,
    reason: str,
    approved_by: str | None = None,
    role_id_after: str | None = None,
) -> SalaryRevision:
    """Close the current rows the day before effective_from and open new rows on it."""
    new_annual = Decimal(str(new_annual_fixed))
    if new_annual <= 0:
        raise ValueError("new_annual_fixed must be greater than zero")

    open_rows = list(db.scalars(
        select(SalaryStructure)
        .where(SalaryStructure.employee_id == employee_id, SalaryStructure.effective_to.is_(None))
        .order_by(SalaryStructure.component_id)
    ))
    if not open_rows:
        raise ValueError("No current salary structure to revise")
    if effective_from <= max(r.effective_from for r in open_rows):
        raise ValueError("effective_from must be after the start of the current salary structure")

    old_annual = monthly_earnings(open_rows) * 12
    if old_annual <= 0:
        raise ValueError("Current salary has no earnings to scale")

    # Scale earning components in proportion; other components stay the same.
    ratio = new_annual / old_annual
    new_amounts = {}
    for r in open_rows:
        amount = Decimal(r.monthly_amount)
        if r.component_type == "EARNING":
            amount = (amount * ratio).quantize(CENT, ROUND_HALF_UP)
        new_amounts[r.structure_id] = amount

    # Make the earnings add up exactly to new_annual / 12 (put the rounding difference on the largest one).
    earning_ids = [r.structure_id for r in open_rows if r.component_type == "EARNING"]
    target = (new_annual / 12).quantize(CENT, ROUND_HALF_UP)
    diff = target - sum(new_amounts[i] for i in earning_ids)
    if diff != 0:
        largest = max(earning_ids, key=lambda i: new_amounts[i])
        new_amounts[largest] += diff

    revision_no = _last_number(db, SalaryRevision.revision_id) + 1
    structure_no = _last_number(db, SalaryStructure.structure_id)
    revision = SalaryRevision(
        revision_id=f"SR-{revision_no:05d}",
        employee_id=employee_id,
        effective_from=effective_from,
        revision_reason=reason,
        previous_annual_fixed=old_annual,
        new_annual_fixed=new_annual,
        pct_change=((new_annual - old_annual) / old_annual * 100).quantize(CENT, ROUND_HALF_UP),
        role_id_after=role_id_after,
        approved_by=approved_by,
        created_at=date.today(),
    )
    db.add(revision)
    db.flush()  # the revision must exist before the new rows point to it

    for r in open_rows:
        structure_no += 1
        r.effective_to = effective_from - timedelta(days=1)  # close the old row
        db.add(SalaryStructure(
            structure_id=f"SS-{structure_no:06d}",
            employee_id=employee_id,
            component_id=r.component_id,
            component_name=r.component_name,
            component_type=r.component_type,
            monthly_amount=new_amounts[r.structure_id],
            effective_from=effective_from,
            effective_to=None,
            revision_id=revision.revision_id,
        ))
    db.commit()
    db.refresh(revision)
    return revision