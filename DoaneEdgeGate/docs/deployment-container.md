# Deploy as a container (secondary option)

CAVEAT: This only makes sense if the Colleague Web API request path can be routed
through your container platform. For an on-prem IIS-hosted Web API that is usually
NOT the case, so this is a secondary option. On-prem IIS (docs/deployment-iis.md) is
the primary path for Doane.

If you do containerize, route a dedicated host to the proxy and do NOT strip any
path prefix - the proxy must forward the original Web API path downstream.

## Docker
Build (see deploy/docker/Dockerfile):

    docker build -t doaneu/edge-gate:1.0.0 -f deploy/docker/Dockerfile .

Run:

    docker run -p 5058:5058 \
      -e EdgeGate__Mode=Off \
      -e EdgeGate__Downstream__BaseUrl=https://colleague-webapi.internal.doane.edu \
      -e EdgeGate__Match__PathPatterns__0=/<IE person-create path> \
      doaneu/edge-gate:1.0.0

## Kubernetes
deploy/k8s/edge-gate.yaml follows the Doane cluster conventions (ns=prod, wildcard
TLS, prod-letsencrypt issuer, regcred pull secret, doaneu image org). It routes a
dedicated host to the proxy with NO stripPrefix so downstream paths are preserved.
This differs from the standard /prod/service-name pattern precisely because a
transparent proxy must not rewrite the path it forwards.

Adjust the host and the EdgeGate__Downstream__BaseUrl to your environment, and make
sure the Self-Service client is pointed at the proxy's ingress rather than at the
Web API directly - otherwise the gate is never in the path and does nothing.
