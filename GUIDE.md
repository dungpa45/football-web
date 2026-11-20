# Football Web Guide

[Back to project overview](./README.md)

A Flask app for football standings, player and team profiles, top scorers, assists, and honours. It reads football data from FotMob and uses MongoDB for cache and honours data.

## Statistics and competition coverage

In **League only** mode, Top All Leagues includes each player's average FotMob rating for the selected league season on the Scorers, Assists, and G+A tabs. Ratings use the shared league-stat cache, do not change the ranking, and exclude cup matches. Missing ratings are shown as `—`; rating request failures are logged without hiding the other statistics.
Ratings above 8 use a solid green badge; ratings above 7 up to 8 use a light green badge.
G+A shows the `(goals+assists)` breakdown only when both values are available, including actual zero values. If either is missing, only the total is displayed.

Use the **League only / All club competitions** switch in the Top All Leagues header to include official cup matches. The selected scope is preserved across the three tabs and the season selector. All-club mode includes only contributions for clubs in that season's Top 5 league tables, including cup-only scorers; national teams, friendlies, and contributions for clubs outside those tables are excluded.

Coverage includes domestic cups, league cups, supercups, UEFA competitions and their separately available qualifying rounds, the Club World Cup, and the FIFA Intercontinental Cup where FotMob provides player statistics. The page lists included competitions and explicitly warns about omitted or temporarily unavailable feeds; these are **partial totals**, not a guarantee of complete cup coverage. A competition with no matches played by eligible clubs is not counted yet. Supercups and calendar-year editions are assigned by the first fixture date within July–June; the whole Club World Cup edition belongs to the season in which it starts, even if its final is in July.

When a supercup has no competition-level player feed, completed eligible fixtures are read from FotMob's match-details API and cached individually. Goals, assists, minutes, and rated appearances are normalized into the same season totals without fetching player profiles or counting a match twice. Match identity, lineup coverage, and goals are validated against the final score. Unused substitutes do not add appearances; own goals and shootout goals do not add player goals. Missing xG/xA values remain unavailable rather than becoming zero. Failed or incomplete match data remains visible in the coverage warning and is retried rather than cached as a complete result.

All-club rating is an approximate weighted mean of published competition averages, using the number of rated appearances rather than an unweighted mean. Unrated matches are excluded. Minutes, appearances, xG, and xA show `—` when coverage cannot establish a full total. All three tabs share a season-total cache (15 minutes for the current season, 24 hours for past seasons); cold loads fetch competition datasets with at most five workers rather than fetching individual player profiles. Builds are serialized within each application worker to avoid duplicate cold-load fan-outs. Transiently incomplete aggregates are not cached, so a later visit can retry failed feeds while reusing successful datasets.

## Run with Docker Compose and MongoDB Atlas

1. Copy `.env.example` to `.env`.
2. Set `MONGO_URI` to your Atlas connection string and `MONGO_DB_NAME` to the intended database. URL-encode special characters in the connection string's username and password. Alternatively, for the existing `cluster0.wbx8bpm.mongodb.net` cluster, keep `username` and `password` and leave `MONGO_URI` and `MONGO_HOST` unset; the code constructs the Atlas URI and escapes credentials automatically, including in production. Replace the admin credentials and `FLASK_SECRET_KEY` placeholders with unique random values.
3. Set `COOKIE_SECURE=false` for local HTTP testing. Use `true` behind HTTPS in production.
4. Start the app:

   ```bash
   docker compose up --build
   ```

5. Open [http://127.0.0.1:5001](http://127.0.0.1:5001). `/healthz` reports process liveness; `/readyz` checks Atlas connectivity.

Compose starts only the app and loads `.env` as runtime environment variables with `env_file`. It does not construct or override a MongoDB URI; `mongo.py` resolves the Atlas configuration and selects the database. `.env` remains excluded from the image and Git. The former standalone Atlas Compose file is no longer needed.

Ensure the Atlas network access list permits the server's outbound IP and that its database user has the required access. Keep using the intended existing Atlas database; changing `MONGO_DB_NAME` or `MONGO_URI` does not move honours data automatically.

Removing local MongoDB and Mongo Express from Compose does not delete their existing data or stop already-running orphan containers. Review any old containers separately; do not delete database files or volumes without a verified backup.

## Prepare a separate VPS staging deployment

The staging override runs only the app on `127.0.0.1:5002`. Use a separate Atlas database and credentials restricted to that database; staging must not point at the production honours database. The override requires an explicit staging env file so it does not inherit the application's production `.env`.

1. Copy the project to a separate directory without overwriting the existing checkout or its `.env`. Create a private staging env file outside the repository from `.env.example`. Configure its staging Atlas connection, a distinct `MONGO_DB_NAME` such as `football_staging`, new admin credentials, and a new Flask secret. Set `COOKIE_SECURE=true` for HTTPS.
2. From the new directory, start only the staging project:

   ```bash
   STAGING_ENV_FILE="$HOME/.config/football-web/staging.env" docker compose --env-file "$HOME/.config/football-web/staging.env" -p football-web-staging -f docker-compose.yml -f docker-compose.staging.yml up -d --build
   ```

3. Check `http://127.0.0.1:5002/readyz` on the VPS, verify that staging uses the intended database, and configure HTTPS and restricted admin access before exposing it.

Staging starts with its own data. If honours are needed for testing, restore a verified backup into the separate staging database and verify the restored records. Never overwrite or drop production collections, and keep production available for rollback.

## Run without Docker

Configure the Atlas connection in `.env` and set `COOKIE_SECURE=false` for local HTTP, then run:

```bash
pip install -r requirements.txt
python app.py
```

The development server binds to `127.0.0.1:5001` and has debugging disabled.

The existing `username` and `password` configuration works in both development and production when neither `MONGO_URI` nor `MONGO_HOST` is set. It targets `cluster0.wbx8bpm.mongodb.net`; use `MONGO_URI` for another Atlas cluster. `MONGO_URI` always takes priority. `MONGO_USER` and `MONGO_PASS` belong to the separate host-based MongoDB configuration and are not needed for Atlas.

## Production notes

- Rotate any credentials or API keys that may have been exposed. Keep `.env` out of Git and Docker build contexts.
- Configure the intended Atlas connection using `MONGO_URI` or the existing `username`/`password` settings described above, and set `MONGO_DB_NAME`. Configure Atlas network access and a database user with only the required permissions. Changing a connection string does not copy data or rotate the database user's password.
- When running the image without Compose, inject configuration with a private runtime env file, including `APP_ENV=production`, `FLASK_SECRET_KEY`, `ADMIN_USER`, `ADMIN_PASS`, and the Atlas settings; use `COOKIE_SECURE=true` behind HTTPS.
- `docker compose` runs Gunicorn as an unprivileged user. The app port is bound to localhost; put Caddy or another HTTPS reverse proxy in front of it.
- Keep `COOKIE_SECURE=true` in production and protect `/admin` behind VPN or an IP allowlist in addition to its login.
- After 1 August UTC each year, the next visit to a player profile schedules a background Wikipedia check for individual awards. Verified profiles are not refreshed; for other profiles, only new awards and years are added, without deleting existing honours. For players without a saved Wikipedia page, a newly found page is used only if its birth date matches FotMob. Refresh is best effort: failures or a busy worker are retried on a later visit, and the visitor may need to reload to see completed updates. Awards announced after the annual check may not appear until the next check or a manual edit. The admin form still supports explicit seeding and can overwrite all honours.
- Individual awards include Premier League Player of the Season, Premier League Playmaker of the Season, and club Player/Players' Player of the Year or Season awards when listed on the player's Wikipedia honours page. Monthly awards, team-of-the-year selections and runners-up remain excluded. Updates to the supported award rules trigger one additional check on the next visit, even for an already-checked season; verified profiles remain protected.
- FotMob data is fetched from public pages/endpoints and may change or become unavailable. The app returns a temporary-unavailable response when upstream requests fail.
- Season selection uses FotMob's available seasons. If it is unavailable, the fallback assumes European seasons change in August.
- League pages and statistics are cached for 15 minutes for the current season and 24 hours for older seasons. If FotMob does not provide usable season metadata, the shorter TTL is used. G+A results are cached only when all supplemental requests succeed; requests after expiry trigger refresh rather than a background scheduler.

### HTTPS and admin access

For a server reached directly by clients, configure DNS to point to it, allow inbound ports 80/443, and use a reverse proxy such as Caddy. Replace the domain and documentation IP address below with your own:

```caddyfile
football.example.com {
    @admin_denied {
        path /admin /admin/*
        not remote_ip 203.0.113.10
    }
    respond @admin_denied 403
    reverse_proxy 127.0.0.1:5001
}
```

Caddy provisions HTTPS certificates when the domain and ports are reachable. The `remote_ip` check uses the direct peer; when another proxy or CDN is in front, configure trusted proxies and client-IP matching correctly or enforce the allowlist at that proxy. Verify admin access from both an allowed and a denied network before exposing the service. Keep the application and MongoDB ports private.

### Backups

Configure and verify an Atlas backup strategy supported by your cluster tier. Keep encrypted off-host exports where appropriate and test restoration to a separate database, not production. Treat connection strings and backup files as secrets; do not commit them or paste them into logs or command-line arguments.

## Tests

```bash
python -m unittest discover -s tests -v
```

Set `MONGO_TEST_URI` to an isolated disposable MongoDB instance to run the integration test. It creates and removes a uniquely named test database. GitHub Actions runs this test against a temporary MongoDB service.

## Features

- League standings and season statistics
- Player and team profiles
- Top scorers, assists, and goals-plus-assists
- Admin-managed player honours
- MongoDB-backed data cache with an in-memory fallback

## License

MIT
