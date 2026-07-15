# Deploy behind IIS (primary Doane topology)

IIS hosts DoaneEdgeGate via the ASP.NET Core Module, and the proxy forwards to the
Colleague Web API. The Self-Service client (or whatever calls the Web API) is
pointed at the proxy's IIS site instead of directly at the Web API.

## Prerequisites
- Windows Server with IIS.
- .NET 8 Hosting Bundle installed (provides the ASP.NET Core Module v2).
  Download: the "ASP.NET Core Runtime 8.x - Windows Hosting Bundle".
- The published output of this app (see below).

## 1. Publish
From the repo root:

    dotnet publish src/DoaneEdgeGate/DoaneEdgeGate.csproj -c Release -o C:\doane\publish\edge-gate

This produces a framework-dependent deployment. The included deploy/iis/web.config
configures the ASP.NET Core Module; publish will merge/emit a web.config, so verify
the final one in the publish folder matches deploy/iis/web.config (in-process
hosting, stdout logging optional).

## 2. Create the IIS site or application
- Point a site (or an app under an existing site) at C:\doane\publish\edge-gate.
- Use a dedicated Application Pool set to "No Managed Code" (the ASP.NET Core Module
  runs the app out of IIS's managed pipeline).
- Bind HTTPS with the wildcard Doane certificate. IIS terminates TLS; the proxy can
  forward to the Web API over HTTP internally or HTTPS as you prefer.

## 3. Configure
Settings come from appsettings.json plus environment variables. For IIS, set the
environment variables on the Application Pool or via web.config
<environmentVariables>. Minimum:

    EdgeGate__Mode=Off                         (start dark; flip to Shadow then Active)
    EdgeGate__Downstream__BaseUrl=https://colleague-webapi.internal.doane.edu
    EdgeGate__Match__PathPatterns__0=/<the IE person-create path from Phase 0>

The proxy preserves the incoming path and query when forwarding, so
Downstream:BaseUrl is just the scheme://host[:port] of the Web API.

## 4. Point traffic at the proxy
Repoint whatever currently calls the Web API (the Self-Service configuration, a
load balancer rule, or a DNS/host entry) at the proxy's IIS binding. The proxy then
relays to Downstream:BaseUrl. Confirm GET /health returns ok through the new path.

## 5. Roll out
1. Deploy with Mode=Off. Confirm registrations still work end to end (pure passthrough).
2. Switch Mode=Shadow. Watch /api/v1/rewrites/recent and the shadow_would_rewrite
   counter over real traffic. Confirm it would touch only the intended field(s).
3. Once Phase 0 confirms the UTC instant and Shadow looks clean, switch Mode=Active.
4. Verify a test registration with a known DOB from an Eastern-spoofed browser now
   stores the correct date.

## Notes
- To bypass the gate for a support case, set Mode=Off and recycle the pool.
- Re-verify Match rules and check the rewrite log after any Self-Service or Web API
  upgrade; a field rename would make the gate a silent no-op (fail-safe, but no
  longer protecting you).
