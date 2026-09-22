# Phase [NN]: [Phase Name]

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | [TBD] | [TBD] |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |

## 1. Objective

### Goal
[Precisely describe what this phase must accomplish.]

### Expected Outcome
- [Observable outcome 1]
- [Observable outcome 2]

### Parent Requirement
[Reference to the overall project requirement/specification.]

---

## 2. Scope Boundaries

### In Scope
- [Specific capability, behavior, or architectural responsibility]
- [Specific capability, behavior, or architectural responsibility]

### Explicitly Out of Scope
- [Feature not implemented in this phase]
- [Unrelated refactoring]
- [Future enhancements]

### Must Not Change
- [Existing behavior/invariant]
- [Public contract]
- [Protected subsystem behavior]

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- [Previous phase completed]
- [Required capability or infrastructure exists]
- [Required contract is available]

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| [Dependency] | [Required state/version/capability] | [How to verify] |

---

## 4. Existing-System Discovery

The agent MUST inspect the existing system before deciding
where or how to implement the changes.

### Required Discovery
- Identify the subsystem(s) responsible for the relevant behavior.
- Locate the existing implementation of related capabilities.
- Identify existing interfaces, contracts, schemas, and boundaries.
- Identify relevant tests and verification mechanisms.
- Identify architectural conventions that must be followed.
- Confirm that the current system supports the proposed change.

### Discovery Output
Before implementation, the agent must report:

- Relevant subsystems identified
- Existing implementation approach
- Relevant contracts/interfaces
- Existing test coverage
- Architectural constraints discovered
- Assumptions confirmed
- Assumptions contradicted
- Questions requiring clarification

### Repository Adaptation Rule
The agent must determine the concrete implementation locations
from the actual repository. The plan does not prescribe file paths,
class names, module names, or directory structures unless they
are explicitly part of an externally required contract.

---

## 5. Implementation Specification

### Task 1: [Task Name]

#### Intent
[What this task accomplishes.]

#### Required Capability or Behavior
[What the system must be capable of doing after implementation.]

#### Architectural Responsibility
[Which logical subsystem, layer, boundary, or responsibility
must own this behavior.]

#### Required Changes
1. [Behavioral or architectural change]
2. [Contract or integration change]
3. [Validation or error-handling change]

#### Implementation Constraints
- [Constraint]
- [Constraint]


#### Expected Result
[Observable result.]

### Task 2: [Task Name]

[Repeat structure as needed.]

### Implementation Freedom
The agent may choose the concrete implementation structure,
file locations, naming, and internal design provided that:
- The required behavior is satisfied.
- Architectural boundaries are respected.
- Existing contracts are preserved.
- All acceptance criteria pass.
- No prohibited changes are introduced.

---

## 6. Agent Execution Rules

### Allowed Actions
- Inspect and modify the repository as required to implement
  the in-scope capabilities.
- Add or update implementation components where appropriate.
- Add or update tests required to verify the behavior.
- Refactor locally when necessary to implement the specified
  capability without changing unrelated behavior.

### Forbidden Actions
- Change public contracts without approval.
- Delete or bypass tests.
- Disable security controls.
- Introduce unrelated features.
- Perform unrelated broad refactoring.
- Upgrade dependencies without approval.
- Commit secrets.
- Claim completion without evidence.

### Agent Decision Boundary
The agent may decide:
- Concrete file/module/class placement.
- Internal implementation structure.
- Local refactoring required for the phase.
- Test organization.
- Non-breaking implementation details.

The agent must request approval for:
- Architecture changes beyond the stated scope.
- Breaking API or data-contract changes.
- Security-sensitive policy decisions.
- Destructive data operations.
- Changes affecting downstream phase assumptions.

### Mandatory Stop Conditions
Stop and report if:
- Requirements are ambiguous.
- Repository facts contradict the plan.
- Required dependencies are missing.
- Scope expansion is required.
- A destructive migration is necessary but unspecified.
- Existing architecture cannot support the intended behavior
  without an unapproved structural change.
- Correctness cannot be verified.

---

## 7. Security Constraints

### Required Controls
- [Authorization requirement]
- [Input validation requirement]
- [Data protection requirement]
- [Trust-boundary requirement]

### Sensitive Data Rules
- Never log [sensitive data]
- Never commit secrets
- Use [approved secret/configuration mechanism]

### Security Acceptance Conditions
- [Security condition 1]
- [Security condition 2]

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests
- [ ] Integration tests
- [ ] Contract tests
- [ ] End-to-end tests
- [ ] Regression tests
- [ ] Security tests
- [ ] Failure-mode tests

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T-01 | [Normal case] | [Expected result] |
| T-02 | [Edge case] | [Expected result] |
| T-03 | [Invalid/failure case] | [Expected result] |

### Negative Testing
Verify that:
- Invalid input is rejected.
- Unauthorized actions are blocked.
- Partial failures are handled safely.
- Duplicate/retry behavior is correct.
- Existing behavior remains intact.
- Failure does not leave invalid state.

### Verification Rule
Implementation claims must be supported by actual test output,
inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-01 | [Observable criterion] | [Test/inspection] | [Evidence] |
| AC-02 | [Observable criterion] | [Test/inspection] | [Evidence] |

### Definition of Done
- [ ] All in-scope behavior is implemented.
- [ ] All acceptance criteria pass.
- [ ] Required tests pass.
- [ ] No unauthorized changes were introduced.
- [ ] Existing behavior remains intact.
- [ ] Security checks pass.
- [ ] Documentation is updated where required.
- [ ] Evidence is collected.
- [ ] Verification is completed.
- [ ] Required approval is obtained.

### Completion Evidence
- Implementation summary
- Discovered/affected architectural components
- Changed-component summary
- Test execution output
- Relevant screenshots or recordings
- API/schema/migration evidence, if applicable
- Verification report
- Known limitations

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| [Failure] | [Signal] | [Action] |

### Rollback Strategy
[How this phase can be safely reverted.]

### Partial Completion Policy
If only part of the phase is complete:
- Do not claim full completion.
- Record completed and incomplete work separately.
- Document remaining work.
- Do not leave undocumented broken state.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| REQ-001 | Task 1 | T-01 | AC-01 |
| REQ-002 | Task 2 | T-02 | AC-02 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

Every acceptance criterion must be traceable.

---

## 12. Phase Exit Contract

### Outputs Produced
- [Capability or artifact]
- [Capability or artifact]

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- [Guarantee 1]
- [Guarantee 2]

### Known Limitations
- [Limitation]

### Downstream Prerequisites
- [What the next phase may rely on]

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: [Name/Agent]
- Verifier: [Name/Agent]
- Human Approver: [Name, if required]
- Date: [YYYY-MM-DD]