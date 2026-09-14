import json
import os


JOBS_FILE = "data/jobs.json"


# =========================================================
# CHECK FILE
# =========================================================

if not os.path.exists(JOBS_FILE):
    raise FileNotFoundError(
        f"{JOBS_FILE} not found"
    )


# =========================================================
# LOAD JOBS
# =========================================================

with open(
    JOBS_FILE,
    "r",
    encoding="utf-8"
) as file:

    jobs = json.load(file)


if not isinstance(jobs, list):
    raise ValueError(
        "jobs.json must contain a list"
    )


print(
    "Jobs loaded:",
    len(jobs)
)


# =========================================================
# MIGRATE LEGACY JOOBLE SOURCES
# =========================================================

updated_count = 0


for job in jobs:

    source = (
        job.get("source")
        or ""
    ).strip()


    apply_link = (
        job.get("apply_link")
        or ""
    ).lower()


    # Job came through Jooble but older version
    # stored provider name as the main source.
    if (
        "in.jooble.org/jdp/" in apply_link
        and
        source.lower() != "jooble"
    ):

        print(
            f"Migrating: "
            f"{job.get('title')} "
            f"[{source} -> jooble]"
        )


        # Preserve original provider
        if source:

            job["original_source"] = source


        # Main source should be Jooble
        job["source"] = "jooble"


        updated_count += 1


# =========================================================
# SAVE
# =========================================================

with open(
    JOBS_FILE,
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        jobs,
        file,
        indent=2,
        ensure_ascii=False
    )


# =========================================================
# SUMMARY
# =========================================================

source_counts = {}


for job in jobs:

    source = (
        job.get("source")
        or "unknown"
    )


    source_counts[source] = (
        source_counts.get(
            source,
            0
        )
        +
        1
    )


print("\n" + "=" * 60)

print(
    "Migration complete"
)

print(
    "Jobs updated:",
    updated_count
)

print(
    "Source counts:",
    source_counts
)

print("=" * 60)