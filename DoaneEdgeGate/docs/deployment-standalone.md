# Deploy as a standalone Kestrel service

Run DoaneEdgeGate as its own process (a Windows Service or a console app) listening
on a port, with traffic pointed at it and forwarding to the Colleague Web API. No
IIS module involved.

## Publish
    dotnet publish src/DoaneEdgeGate/DoaneEdgeGate.csproj -c Release -o C:\doane\publish\edge-gate

## Run (console, for a quick test)
    cd C:\doane\publish\edge-gate
    set EdgeGate__Mode=Off
    set EdgeGate__Downstream__BaseUrl=https://colleague-webapi.internal.doane.edu
    set EdgeGate__Match__PathPatterns__0=/<IE person-create path>
    set ASPNETCORE_URLS=http://0.0.0.0:5058
    dotnet DoaneEdgeGate.dll

## Run as a Windows Service
Use sc.exe or New-Service to register the published DoaneEdgeGate.exe. Set the same
environment variables at the service or machine level. The app binds 0.0.0.0:5058 by
default (override with ASPNETCORE_URLS). Put a reverse-terminating TLS front (IIS,
a load balancer, or a Kestrel HTTPS binding with the wildcard cert) ahead of it if
clients speak HTTPS.

## TLS
Kestrel can terminate TLS directly if you configure a certificate, but at Doane it
is usually simpler to let IIS or the load balancer terminate and forward HTTP to the
service on an internal port. See docs/deployment-iis.md for the IIS-fronted variant.

## Roll out
Same Off -> Shadow -> Active lifecycle as the IIS guide. Flip the mode via the
environment variable and restart the service.
