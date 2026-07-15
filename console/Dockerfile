FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Microsoft ODBC Driver for SQL Server — required for the DOB Repair SQL
# fetch source (app/dob_sql_source.py, pyodbc). Unlike uopy (the UniData
# driver, which this image deliberately ships WITHOUT its native driver,
# since Phase 3/UniData is a maybe-someday integration), this one gets
# installed here: the DOB Repair SQL fetch is an active production need,
# not an optional feature most deployments will leave off. See
# docs/test-coverage-classification.md's "Coverage Gaps (Accepted)" table.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gnupg2 \
    && curl -sSL -O https://packages.microsoft.com/config/debian/$(grep VERSION_ID /etc/os-release | cut -d '"' -f 2)/packages-microsoft-prod.deb \
    && dpkg -i packages-microsoft-prod.deb \
    && rm packages-microsoft-prod.deb \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends unixodbc-dev msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FLASK_ENV=production
ENV PORT=8080

EXPOSE 8080

# --workers is pinned to 1, not scaled up: BusMonitor, the GraphQL schema
# cache, and the resource caches (app/routes/graphql_routes.py,
# app/routes/resources.py, app/routes/dob_repair.py) are all process-local
# module/instance state with no shared backing store. With --preload absent,
# each gunicorn worker forks its own independent copy of this state and its
# own BusMonitor polling thread racing the same Ethos queue/credential —
# start/stop/pause API calls would only affect whichever worker served that
# request, and two workers could show different cached data to the same
# operator. Scale for HA with k8s replicas (pods), not in-process workers —
# concurrency within a pod already comes from --threads 4.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4", \
     "--worker-class", "gthread", "--timeout", "120", "run:app"]
