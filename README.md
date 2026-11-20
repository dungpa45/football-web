# Football Web

A Flask app for football statistics powered by FotMob, with MongoDB-backed caching and honours data.

## Features

- Standings and season statistics for Europe's Top 5 leagues.
- Top scorers, assists, G+A, and player ratings.
- League-only or all-club-competitions rankings, with explicit data-coverage notices.
- Player and team profiles, plus admin-managed honours.

## Quick start

1. Copy [`.env.example`](./.env.example) to `.env`, configure your MongoDB Atlas connection, and replace all placeholder credentials and secrets.
2. Set `COOKIE_SECURE=false` for local HTTP.
3. Start the app:

   ```bash
   docker compose up --build
   ```

4. Open [http://127.0.0.1:5001](http://127.0.0.1:5001).

Docker runs only the app; the code reads the Atlas configuration supplied through `.env`. For production, configure HTTPS, Atlas network access, and restricted admin access before exposing the app.

## Documentation

See [GUIDE.md](./GUIDE.md) for:

- [Statistics, ratings, competition coverage, and caching](./GUIDE.md#statistics-and-competition-coverage)
- [Docker and MongoDB Atlas setup](./GUIDE.md#run-with-docker-compose-and-mongodb-atlas), or [running without Docker](./GUIDE.md#run-without-docker)
- [Separate VPS staging](./GUIDE.md#prepare-a-separate-vps-staging-deployment)
- [Production, HTTPS, admin access, and backups](./GUIDE.md#production-notes)
- [Running tests](./GUIDE.md#tests)

## License

[MIT](./LICENSE)
