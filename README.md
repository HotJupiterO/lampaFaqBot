# jpa-fetch-benchmark

A small benchmark that compares ways of loading a one-to-many association with Spring Data JPA / Hibernate, and measures **how many SQL queries each one issues and how long it takes** as the data grows.

The goal is a practical answer to: *"which fetch strategy should I use, and when does it stop mattering?"*

## Model

Synthetic data only: `Author 1 — N Book`. Each author gets 5–10 books (fixed random seed, so every run uses the same data).

## Strategies compared

| Name | What it does |
|---|---|
| `N+1` | Lazy loading: load authors, then touch `author.getBooks()` in a loop. Baseline. |
| `Join Fetch` | `select distinct a from Author a join fetch a.books` |
| `BatchSize50` | Same code as N+1, but with `Session.setFetchBatchSize(50)` |
| `DTO` | Interface projection: author name + book count, no entities loaded |
| `JoinFetch+page` | Join fetch with `setFirstResult/setMaxResults` (first 50 authors) |
| `TwoQuery+page` | Query 1: ids of the first 50 authors (ordered). Query 2: join fetch `where id in :ids` |

## Method

- Postgres 16 in Docker, Spring Boot 4.1, Hibernate ORM 7.4, JDK 21
- Dataset sizes: 100 / 1 000 / 5 000 authors
- 5 warm-up runs, then 20 measured runs per scenario; **median** reported
- Query count taken from Hibernate `Statistics.getPrepareStatementCount()`
- Every full-scan scenario returns the same book total (731 / 7 395 / 37 667), used as a correctness check
- Database is on `localhost`, so network latency is close to zero (see limitations)

## Results

Median time, `requests` = SQL statements per run.

**100 authors**

| Strategy | Books | Requests | Median |
|---|---:|---:|---:|
| N+1 | 731 | 101 | 72 ms |
| BatchSize50 | 731 | 3 | 7 ms |
| Join Fetch | 731 | 1 | 4 ms |
| DTO | 731 | 1 | 2 ms |
| JoinFetch+page | 358 | 1 | 3 ms |
| TwoQuery+page | 358 | 2 | 4 ms |

**1 000 authors**

| Strategy | Books | Requests | Median |
|---|---:|---:|---:|
| N+1 | 7 395 | 1 001 | 887 ms |
| BatchSize50 | 7 395 | 21 | 49 ms |
| Join Fetch | 7 395 | 1 | 23 ms |
| DTO | 7 395 | 1 | 7 ms |
| JoinFetch+page | 370 | 1 | 3 ms |
| TwoQuery+page | 370 | 2 | 4 ms |

**5 000 authors**

| Strategy | Books | Requests | Median |
|---|---:|---:|---:|
| N+1 | 37 667 | 5 001 | 8 251 ms |
| BatchSize50 | 37 667 | 101 | 414 ms |
| Join Fetch | 37 667 | 1 | 186 ms |
| DTO | 37 667 | 1 | 35 ms |
| JoinFetch+page | 386 | 1 | 8 ms |
| TwoQuery+page | 386 | 2 | 6 ms |

## Findings

1. **N+1 gets worse faster than the data grows.** Queries are exactly `authors + 1`. Time grows 72 → 887 → 8 251 ms (data ×10, then ×5), so the cost per query also rises (≈0.7 → 0.9 → 1.65 ms), most likely because the persistence context keeps growing. N+1 is roughly 18× slower than join fetch at 100 authors and roughly 40× at 5 000.
2. **Batch fetching is the cheapest fix.** It needs no query changes: queries drop to `1 + ceil(authors / 50)`, and it is 10–20× faster than N+1. It still loses to join fetch by about 2×, because it makes more round trips.
3. **Join fetch collapses everything into 1 query**, but it returns one row per book with the author columns repeated, and needs `distinct` to avoid duplicate authors in the result.
4. **DTO projection is fastest** (about 5× faster than join fetch at 5 000 authors) because no entities are materialized. It is not an equal comparison: it returns only a name and a count. Use it for read-only reports, not when you need to work with entities.
5. **Pagination with join fetch was safe in this setup.** Contrary to the common advice ("collection fetch + `setMaxResults` is applied in memory"), the SQL log shows Hibernate 7 wraps the author selection in a subquery with `offset ? rows fetch first ? rows only` and joins books to it. Time stayed flat (3–8 ms) regardless of table size, while a full join fetch grew to 186 ms. This was checked by turning on `logging.level.org.hibernate.SQL=debug`, not assumed. Older Hibernate versions may behave differently.
6. **Two-query pagination matches join fetch pagination here** (6 ms vs 8 ms at 5 000 authors, same books returned), at the cost of one extra query. Whichever you use, an explicit `order by` is required, otherwise the page is not deterministic.

## Limitations

- Database on localhost: real network latency per query would hurt N+1 and batch fetching far more than shown here.
- Synthetic data, one simple model, no concurrency, no second-level cache.
- Single benchmark run per configuration. Individual numbers vary between runs (full join fetch at 5 000 authors measured 132–221 ms across runs), so treat them as orders of magnitude, not exact multipliers.
- Not a JMH benchmark: the bottleneck here is the database and the ORM, not JIT behaviour, so a plain warm-up + median approach was used.

## Run it

```bash
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=admin -e POSTGRES_DB=bench postgres:16
```

Credentials in `src/main/resources/application.properties` must match. Then run `Application` (JDK 21). The runner generates data, executes every scenario for each dataset size and prints the result table to the console.

To see the SQL of a scenario, set `logging.level.org.hibernate.SQL=debug` and keep only that scenario enabled.

## Project layout

```
entity       Author, Book
repository   AuthorRepository, AuthorStats (projection)
data         DataGenerator
scenario     FetchScenario + one class per strategy
bench        BenchmarkRunner (warm-up, measurement, table output)
```
