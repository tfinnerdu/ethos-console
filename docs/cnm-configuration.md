# CNM service — configuration reference

Analog of `console/.env.example` for the C# CNM service. Every config key the
service reads, where it's used, what the default is, and how to set it per
environment.

## Where settings come from (layered)

Loaded in order; later layers override earlier ones:

1. **`appsettings.json`** — committed defaults. Has the right *shape*, mostly empty values.
2. **`appsettings.{ASPNETCORE_ENVIRONMENT}.json`** — environment overlay.
   `appsettings.Development.json` is committed (safe local defaults).
   `appsettings.Production.json` is **gitignored** — copy
   `appsettings.Production.json.example` and fill in, or mount it from a
   k8s secret, or skip it entirely and use env vars.
3. **Environment variables** with `__` (double underscore) replacing `:`.
   Example: `ColleagueWebApi:Username` → `ColleagueWebApi__Username`.
   `cnm/k8s/secret-template.yaml` and `cnm/k8s/configmap.yaml` use this form.

## Every key the service reads

### Runtime / host

| Key | Default | Purpose |
|---|---|---|
| `ASPNETCORE_ENVIRONMENT` | `Production` | `Development` enables Swagger UI, `DevAuthHandler` (no Azure AD), `FileAuditRepository`, the SQLite default below, and `EnsureCreated`. `Production` requires Azure AD + a real DB. |
| `ASPNETCORE_URLS` | `http://localhost:5000` | Bind address. k8s configmap sets `http://+:8080`. |

### Database

| Key | Default | Purpose |
|---|---|---|
| `ConnectionStrings:CnmDb` | empty | SQL Server connection string in prod. **Leave empty in Development** — the service auto-creates a SQLite database at `<repo>/console/instance/cnm.db` and runs `EnsureCreated`. |
| `Cnm:UseSqlite` | `false` | Force the SQLite provider even when `ConnectionStrings:CnmDb` is set or `ASPNETCORE_ENVIRONMENT=Production`. Intended for the integration test factory; do not set in production. |

### Authentication (Production only)

| Key | Default | Purpose |
|---|---|---|
| `AzureAd:Authority` | empty | OIDC authority — `https://login.microsoftonline.com/<tenant>/v2.0`. |
| `AzureAd:Audience` | empty | App-registration client ID. |

Development bypasses Azure AD entirely via `DevAuthHandler`.

### Colleague Web API client (`ColleagueWebApiOptions`)

| Key | Default | Purpose |
|---|---|---|
| `ColleagueWebApi:BaseUrl` | empty | Host URL. Refit client falls back to `http://localhost` so DI doesn't throw when unset. |
| `ColleagueWebApi:Username` | empty | Basic-auth username (service account). |
| `ColleagueWebApi:Password` | empty | Basic-auth password. |
| `ColleagueWebApi:Timeout` | `00:00:30` | HTTP timeout (TimeSpan). |

### DAS — Data Access System (`DasOptions`)

| Key | Default | Purpose |
|---|---|---|
| `Das:BaseUrl` | empty | DAS host. |
| `Das:Username` | empty | DAS service-account username. |
| `Das:Password` | empty | DAS service-account password. |

### Colleague SQL — read-only direct queries (`ColleagueSqlOptions`)

| Key | Default | Purpose |
|---|---|---|
| `ColleagueSql:ConnectionString` | empty | Read-only connection string to the Colleague SQL primary store. |

### CORS

| Key | Default | Purpose |
|---|---|---|
| `Cors:AllowedOrigins` | `["http://localhost:5010", "http://rmw01tfinner.doane.local:5010"]` | Trusted origins. Add the Ethos Dev Console host (and any others) in prod. |

### Logging (Serilog)

`Serilog:*` keys configure level and sinks. See `appsettings.json` for the
default shape. Override `Serilog:MinimumLevel:Default` to change verbosity.

## Setting configs per environment

### Local dev (no Colleague)

Nothing required. `cnm/start-local.ps1` exports `ASPNETCORE_ENVIRONMENT=Development`,
the SQLite default kicks in, `DevAuthHandler` provides a fake admin user, and the
file audit repo writes to `.hub-logs/`. Optionally drop credentials into a repo-root
`.env` if you want to point at a real Colleague Web API.

### Local dev (with Colleague)

Add to a repo-root `.env` (loaded by `start-local.ps1`):

```
ColleagueWebApi__BaseUrl=https://colleague-webapi.doane.edu
ColleagueWebApi__Username=...
ColleagueWebApi__Password=...
Das__BaseUrl=https://...
Das__Username=...
Das__Password=...
ColleagueSql__ConnectionString=Server=...;Database=...;...
```

Leave `ConnectionStrings__CnmDb` unset to keep the SQLite default; set it to a
SQL Server string if you need to test against SQL Server locally.

### Production / k8s

Two ways:

**Option A — `appsettings.Production.json`.** Copy
`cnm/src/EthosCn.Api/appsettings.Production.json.example` to
`appsettings.Production.json` in the same directory, fill in, mount as a secret
volume at `/app/appsettings.Production.json`. Gitignored by
`**/appsettings.*.json`.

**Option B — env vars from a k8s secret.** `cnm/k8s/secret-template.yaml`
shows the env var names. Copy to `secret.yaml`, base64-encode each value
(`echo -n 'plaintext' | base64`), apply with `kubectl apply -f`. Mount via
`envFrom: secretRef:` in the deployment. This is what the current k8s
manifests use.

Option B is preferred (secrets stay in k8s; image is config-free).

## Adding a new config key

1. Add a strongly-typed `Options` class under `cnm/src/EthosCn.Infrastructure/<Area>/<Area>Options.cs` with `SectionName`.
2. `services.AddOptions<MyOptions>().Bind(configuration.GetSection(MyOptions.SectionName))` in `ServiceRegistration.cs`. Add `.ValidateDataAnnotations().ValidateOnStart()` if values are required.
3. Add the section to `appsettings.json` with safe defaults.
4. Add a placeholder entry to `cnm/k8s/secret-template.yaml` if it's a secret, or `configmap.yaml` if it's not.
5. Add the row to the table in this doc.
6. Add the section to `appsettings.Production.json.example`.
