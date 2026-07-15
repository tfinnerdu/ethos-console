# Multi-stage build. Framework-dependent, no third-party packages.
# Build context is the repo root: docker build -f deploy/docker/Dockerfile .
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY src/DoaneEdgeGate.Core/ ./src/DoaneEdgeGate.Core/
COPY src/DoaneEdgeGate/ ./src/DoaneEdgeGate/
RUN dotnet publish src/DoaneEdgeGate/DoaneEdgeGate.csproj -c Release -o /app

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app
COPY --from=build /app ./
ENV ASPNETCORE_URLS=http://0.0.0.0:5058
ENV EdgeGate__Mode=Off
EXPOSE 5058
ENTRYPOINT ["dotnet", "DoaneEdgeGate.dll"]
