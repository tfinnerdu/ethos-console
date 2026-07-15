# DoaneEdgeGate - Pilot Plan and Phase 0 Checklist

Standalone runbook for piloting the Instant Enrollment DOB edge gate (PD0002124)
without touching production. Covers the deployment decision (repoint), the
dev -> sandbox -> prod sequence, and the Phase 0 capture that decides whether the
gate is even the right fix.

Keep this next to the config it governs. Whoever runs the pilot should be able to
work top to bottom from this one file.

---

## 0. The decision on record: repoint, not takeover

Two ways to insert the gate in front of the Colleague Web API:

- Repoint (chosen): point each environment's Self-Service API URL at that
  environment's gate app. The gate is a distinct host; the real Web API binding
  never changes.
- Takeover (rejected): the gate assumes the Web API's own address and the real Web
  API moves to an internal-only binding.

Why repoint won:

1. Only Instant Enrollment has this bug (it is a browser date-picker issue).
   Server-to-server callers (Conductor, Ethos, batch) send clean dates and gain
   nothing from the gate. Repoint scopes the gate to exactly the population that
   benefits; takeover drags every blameless caller behind it for risk and no upside.
2. Reversibility. If the gate misbehaves, repoint reverts one SS URL and only SS
   blipped. Takeover makes the gate a mandatory availability dependency in front of
   a critical shared service - fail-open covers a transform bug, not a dead process.
3. Bypass for support stays trivial. "Ellucian, reproduce against the Web API" is a
   30-second SS-URL revert, not a production re-bind under support pressure.
4. It does not touch the thing we are protecting. Repoint changes a setting;
   takeover re-binds the production Web API.

The one gate on this decision: the Web API auth model.
- Bearer / token (stateless): repoint is clearly correct.
- Windows Integrated / Kerberos: stop and design the auth path first; repointing SS
  to a different host can trip SPN/host validation, and a proxy in a Kerberos path
  has a delegation problem regardless of approach. Confirm this before wiring.

This runbook assumes bearer/token auth. If it turns out to be Kerberos, pause here.

---

## 1. Precheck: confirm the isolation boundary

dev / sandbox / prod live as separate IIS applications on the same UI host. That is
fine. The isolation boundary is NOT the host - it is each environment's own
Self-Service config, which names its own Web API URL. Prod cannot route through the
gate because prod's config never names it.

Before doing anything, confirm:

- [ ] Each environment's Web API URL lives in that environment's own Self-Service
      config, and is NOT inherited from a shared parent web.config.
- [ ] Each environment's Self-Service runs in its own app pool (so recycles are
      isolated per environment).
- [ ] You have a clean port/binding available on the host for a new gate app.

If the Web API URL is inherited from a shared parent, resolve that first - otherwise
a change meant for dev could bleed into another environment.

---

## 2. Phase 0: capture and decode (the go/no-go)

Purpose: prove the corruption mechanism and extract the two values the gate needs
(the endpoint path and the DOB field name). This is the single most important step.
If Phase 0 shows the browser already sends a bare date, the gate has nothing to
rewrite and you should escalate to Ellucian instead of deploying it.

Do this in sandbox or dev. Never in prod. It takes about 30 minutes.

### 2a. Set up the capture
- [ ] Open the IE registration flow in Chrome.
- [ ] Open DevTools. In the Sensors panel (More tools -> Sensors), set Location /
      timezone override to an Eastern zone (for example America/New_York). This
      reproduces the "client east of Central" condition that triggers the shift.
- [ ] Pick a known, memorable DOB to type in - for example 1980-04-03.
- [ ] Open the Network tab and clear it.

### 2b. Run it and grab the payload
- [ ] Complete the IE registration through the person-create step.
- [ ] In Network, find the person-create POST (the request that submits the
      applicant). Record:
      - Request path: ______________________________  (-> Match:PathPatterns)
      - Method (expect POST): _______________________  (-> Match:Methods)
      - DOB field name in the JSON body: ____________  (-> Rewrite:DateFieldNames)
      - Exact serialized DOB value: _________________

### 2c. Decode the DOB value (this is the fix decision)

Compare the captured DOB value against the date you typed (1980-04-03):

- Value is a morning-UTC instant, e.g. "1980-04-03T04:00:00Z"
  -> CONFIRMED. The browser sends a UTC instant; the server truncates it to the
     prior day. THE GATE APPLIES. Proceed to the pilot (section 3).

- Value is already a bare date "1980-04-03"
  -> The client is already sending date-only and the server is corrupting a clean
     date. The gate has nothing in the body to rewrite. Do NOT deploy Active.
     Escalate PD0002124 to Ellucian and pursue a server-side fix.

- Value is already the wrong date "1980-04-02"
  -> The shift happened client-side before serialization. The payload's date is
     already wrong and the gate cannot recover it. Different fix; escalate.

Only the first outcome greenlights the gate. Write down which one you got.

### 2d. Size the exposure (blast radius)
- [ ] Count IE-origin person records whose address is in an Eastern-timezone state.
      That is your rough exposure number: the population most likely already shifted,
      and the size of the win. Feed it to DoaneDOBReconcile to prioritize cleanup.

Note: the dev Shadow run in section 3 captures the same rewrite evidence through the
gate's own logging (/api/v1/rewrites/recent). Phase 0 via DevTools is the faster
pre-wiring go/no-go; Shadow is the post-wiring confirmation. Doing both is belt and
suspenders, and they should agree.

---

## 3. Pilot sequence: dev -> sandbox -> prod

The gate binary is identical across environments. Only Downstream:BaseUrl and the
repointed SS URL differ. One gate app maps to exactly one downstream environment so
you can never cross-wire a config.

Dev and sandbox do different jobs:
- Dev = functional shakeout. Does repoint break the flow, does CORS survive, does
  the Off -> Shadow -> Active flip behave. Nobody cares if dev hiccups.
- Sandbox = fidelity check. If sandbox is a recent prod refresh (same Web API
  build), a Shadow run there confirms the endpoint path and field names match what
  prod will actually send. Do not skip sandbox on the theory that dev proved it,
  unless dev and prod are confirmed to be on the same SS/Web API version. This gate
  is version-fragile: a field rename between builds turns it into a silent no-op.

### Step 1 - dev, Mode=Off (plumbing)
- [ ] Create edge-gate-dev: its own app pool, its own binding.
- [ ] Configure: Mode=Off, Downstream:BaseUrl = the real dev Web API,
      Match:PathPatterns = the path from Phase 0.
- [ ] Repoint dev Self-Service's API URL at edge-gate-dev.
- [ ] Run a dev IE registration end to end. Confirm it works with zero behavior
      change (pure passthrough). This proves plumbing, auth, and CORS safely.
- [ ] Verify a real CORS preflight (OPTIONS) round-trips, and that the person-create
      response carries no absolute URLs that would let the browser bypass the gate.

### Step 2 - dev, Mode=Shadow (validation + live Phase 0)
- [ ] Flip edge-gate-dev to Shadow.
- [ ] Run an IE registration with a DevTools Eastern timezone override and a known
      DOB.
- [ ] Check /api/v1/rewrites/recent. Confirm the gate WOULD rewrite exactly the DOB
      field to the correct date, and touch nothing else. Confirm shadow_would_rewrite
      incremented on /api/v1/status.

### Step 3 - dev, Mode=Active (prove the fix)
- [ ] Flip edge-gate-dev to Active.
- [ ] Re-run the registration. Confirm dev stored the correct date.

### Step 4 - sandbox, Mode=Shadow (prod-parity fidelity)
- [ ] Create edge-gate-sandbox (own pool/binding, downstream = sandbox Web API).
- [ ] Repoint sandbox Self-Service at it. Set Mode=Shadow.
- [ ] Run the same spoofed registration. Confirm the path and field names captured
      on dev match what sandbox sends. If they match, the dev-tuned config is
      prod-valid. If they do not, you just caught a version drift before prod.

### Step 5 - prod (only after 1-4 pass)
- [ ] Create edge-gate-prod (own pool/binding, downstream = prod Web API), Mode=Off.
- [ ] Repoint prod Self-Service. Confirm passthrough.
- [ ] Off -> Shadow (watch real traffic) -> Active.

Prod config is untouched through steps 1-4. Prod only enters the path at step 5.

---

## 4. Config quick reference

Values captured in Phase 0 map straight to these (env var form; ASP.NET uses __ as
the section separator):

    EdgeGate__Mode=Off | Shadow | Active
    EdgeGate__Downstream__BaseUrl=<the real Web API base for THIS environment>
    EdgeGate__Match__Methods__0=POST
    EdgeGate__Match__PathPatterns__0=<person-create path from Phase 0 2b>
    EdgeGate__Rewrite__Strategy=FieldAllowlist
    EdgeGate__Rewrite__DateFieldNames__0=<DOB field name from Phase 0 2b>
    EdgeGate__Rewrite__FailMode=Open

See the repo's docs/architecture.md and docs/deployment-iis.md for the full option
set and the YARP wiring.

---

## 5. Rollback

At any point, in any environment: revert that environment's Self-Service API URL to
the real Web API and recycle the pool. That single change removes the gate from the
path. Because each environment is repointed independently, a rollback in one never
affects another, and prod is never in the path until you explicitly put it there.
