# Care Plans, Goals & Service Requests

## CarePlan

- **Status**: draft, active, on-hold, revoked, completed, entered-in-error
- **Intent**: proposal, plan, order, option
- **Categories**: assess-plan, longitudinal, encounter-specific
- Include `CarePlan.activity` with detail (scheduled procedures, medication reviews, referrals)
- Link to Conditions via `CarePlan.addresses[]`
- Link to Goals via `CarePlan.goal[]`

## Goal

- **lifecycleStatus**: proposed, planned, accepted, active, on-hold, completed, cancelled
- **achievementStatus**: in-progress, improving, worsening, no-change, achieved, not-achieved
- Include `target` with `detailQuantity`, `dueDate`:
  - HbA1c < 7.0%, BP < 140/90, LDL < 100, BMI < 30, weight loss X lbs by date
- **Priority**: high-priority, medium-priority, low-priority

## ServiceRequest

- **Status**: draft, active, completed, revoked, entered-in-error
- **Intent**: order, plan, proposal, directive, reflex-order, filler-order
- **Categories**: laboratory, imaging, procedure, referral, counseling
- **Priority**: routine, urgent, asap, stat
- Common orders: Lab panels, imaging (X-ray, CT, MRI), specialist referrals, physical therapy, dietary counseling

