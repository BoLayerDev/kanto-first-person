# Risk Register

| ID | Risk | Severity | Control | Release condition |
|---|---|---:|---|---|
| R1 | Legacy orphan cleanup can delete host files | Critical | Never run legacy cleanup; require clean host reinstall before v2 | Upgrade test and documented sequence pass |
| R2 | Legacy release does not match its Git tag | High | Record immutable artifact hashes and treat archives as evidence only | Source registry complete |
| R3 | Creator permission is not durable or broad enough | High | Preserve private proof; separate rights; replace unapproved assets | Redistribution and modification grant confirmed |
| R4 | Host APIs diverge | High | One versioned contract and one conformance suite | Both released adapters pass |
| R5 | Broad `ctx.state` changes | High | Keep access inside host adapters and validate normalized views | Stable and dev matrices pass |
| R6 | LuaJIT local/upvalue limits return | Medium | Small modules and static checks | Syntax and complexity gates pass |
| R7 | Resource leaks across maps or hot reload | High | Explicit owners, idempotent disposal, bounded LRU | 100-transition and 30-minute soak pass |
| R8 | Low-power targets miss frame budgets | High | Fixed tiers, batching, bounded builds, real-device gates | Lowest supported device passes Low tier |
| R9 | Public CI accidentally contains ROM material | Critical | Synthetic fixtures, content scan, private corpus exclusion | ROM scan passes |
| R10 | A fast upstream release changes the contract | Medium | Pin exact SHAs and re-audit before RC | Latest release audit recorded |
