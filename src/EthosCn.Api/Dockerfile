FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS base
WORKDIR /app
EXPOSE 8080

FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY ["src/CNM.Api/CNM.Api.csproj", "src/CNM.Api/"]
COPY ["src/CNM.Application/CNM.Application.csproj", "src/CNM.Application/"]
COPY ["src/CNM.Domain/CNM.Domain.csproj", "src/CNM.Domain/"]
COPY ["src/CNM.Contracts/CNM.Contracts.csproj", "src/CNM.Contracts/"]
COPY ["src/CNM.Infrastructure/CNM.Infrastructure.csproj", "src/CNM.Infrastructure/"]
RUN dotnet restore "src/CNM.Api/CNM.Api.csproj"
COPY . .
WORKDIR "/src/src/CNM.Api"
RUN dotnet build "CNM.Api.csproj" -c Release -o /app/build

FROM build AS publish
RUN dotnet publish "CNM.Api.csproj" -c Release -o /app/publish /p:UseAppHost=false

FROM base AS final
WORKDIR /app
COPY --from=publish /app/publish .
ENV ASPNETCORE_URLS=http://+:8080
ENTRYPOINT ["dotnet", "CNM.Api.dll"]
