import os
import re
import json
import yaml
import requests

from datetime import datetime, timedelta, timezone
from dateutil import parser
from dotenv import load_dotenv


# =========================================================
# LOAD ENVIRONMENT
# =========================================================

load_dotenv()

API_KEY = os.getenv("JOOBLE_API_KEY")

if not API_KEY:
    raise ValueError("JOOBLE_API_KEY not found")


# =========================================================
# LOAD CONFIG
# =========================================================

with open("config.yml", "r", encoding="utf-8") as file:
    config = yaml.safe_load(file)


search_config = config["search"]

roles = search_config["roles"]

max_age_hours = search_config.get(
    "max_age_hours",
    24
)

experience_config = search_config.get(
    "experience",
    {}
)

USER_MIN_EXP = experience_config.get(
    "min_years",
    0
)

USER_MAX_EXP = experience_config.get(
    "max_years",
    2
)

exclude_keywords = [
    word.lower()
    for word in search_config.get(
        "exclude_keywords",
        []
    )
]

output_file = config["output"].get(
    "json_file",
    "data/jobs.json"
)

meta_file = "data/meta.json"


# =========================================================
# START INFO
# =========================================================

print("Configured roles:")

for role in roles:
    print("-", role)

print(
    f"\nTarget experience: "
    f"{USER_MIN_EXP}-{USER_MAX_EXP} years"
)


# =========================================================
# DATE FUNCTIONS
# =========================================================

def parse_job_date(date_value):

    if not date_value:
        return None

    try:
        job_time = parser.parse(date_value)

        if job_time.tzinfo is None:
            job_time = job_time.replace(
                tzinfo=timezone.utc
            )

        return job_time.astimezone(
            timezone.utc
        )

    except Exception:
        return None


def is_within_last_hours(
    date_value,
    hours
):

    job_time = parse_job_date(
        date_value
    )

    if not job_time:
        return False

    now = datetime.now(
        timezone.utc
    )

    cutoff = now - timedelta(
        hours=hours
    )

    return job_time >= cutoff


# =========================================================
# TITLE EXCLUSION
# =========================================================

def is_excluded_title(title):

    title = (
        title
        or ""
    ).lower()

    senior_terms = [
        "senior",
        "sr ",
        "sr.",
        "lead",
        "architect",
        "manager",
        "principal",
        "staff engineer"
    ]

    for term in senior_terms:

        if term in title:
            return True

    for keyword in exclude_keywords:

        if keyword in title:
            return True

    return False


# =========================================================
# EXPERIENCE PARSER
# =========================================================

def extract_experience_from_text(text):

    text = (
        text
        or ""
    ).lower()


    # Fresher / entry level
    fresher_terms = [
        "fresher",
        "freshers",
        "entry level",
        "entry-level",
        "new grad",
        "graduate trainee",
        "0 year",
        "0 years"
    ]

    for term in fresher_terms:

        if term in text:
            return 0, 0


    # 1-3 years / 1 to 3 years
    range_match = re.search(
        r"(\d+)\s*(?:-|–|to)\s*(\d+)\s*(?:years?|yrs?)",
        text
    )

    if range_match:

        minimum = int(
            range_match.group(1)
        )

        maximum = int(
            range_match.group(2)
        )

        return minimum, maximum


    # 3+ years
    plus_match = re.search(
        r"(\d+)\s*\+\s*(?:years?|yrs?)",
        text
    )

    if plus_match:

        minimum = int(
            plus_match.group(1)
        )

        return minimum, 99


    # minimum 3 years / at least 3 years
    minimum_match = re.search(
        r"(?:minimum|min\.?|at least)\s*(\d+)\s*(?:years?|yrs?)",
        text
    )

    if minimum_match:

        minimum = int(
            minimum_match.group(1)
        )

        return minimum, 99


    # 2 years experience
    exact_match = re.search(
        r"(\d+)\s*(?:years?|yrs?)\s*(?:of\s*)?(?:experience|exp)",
        text
    )

    if exact_match:

        years = int(
            exact_match.group(1)
        )

        return years, years


    return None, None


# =========================================================
# EXPERIENCE MATCHING
# =========================================================

def experience_matches(
    title,
    snippet
):

    combined_text = (
        f"{title or ''} "
        f"{snippet or ''}"
    )

    job_min, job_max = (
        extract_experience_from_text(
            combined_text
        )
    )

    # Experience not mentioned:
    # keep the job
    if job_min is None:
        return True

    return (
        job_min <= USER_MAX_EXP
        and
        job_max >= USER_MIN_EXP
    )


def experience_label(
    title,
    snippet
):

    combined_text = (
        f"{title or ''} "
        f"{snippet or ''}"
    )

    minimum, maximum = (
        extract_experience_from_text(
            combined_text
        )
    )

    if minimum is None:
        return "Not specified"

    if minimum == 0 and maximum == 0:
        return "Fresher"

    if maximum == 99:
        return f"{minimum}+ years"

    if minimum == maximum:
        return f"{minimum} years"

    return f"{minimum}-{maximum} years"


# =========================================================
# NORMALIZE JOB
# =========================================================

def normalize_job(job):

    return {

        "title":
            job.get("title"),

        "company":
            job.get("company"),

        "location":
            job.get("location"),

        "experience":
            experience_label(
                job.get("title"),
                job.get("snippet")
            ),

        "updated":
            job.get("updated"),

        "source":
            job.get("source"),

        "apply_link":
            job.get("link"),

        "snippet":
            job.get("snippet")
    }


# =========================================================
# JOB UNIQUE KEY
# =========================================================

def create_job_key(job):

    link = (
        job.get("apply_link")
        or ""
    ).strip().lower()

    if link:
        return link


    title = (
        job.get("title")
        or ""
    ).strip().lower()

    company = (
        job.get("company")
        or ""
    ).strip().lower()

    location = (
        job.get("location")
        or ""
    ).strip().lower()


    return (
        f"{title}|"
        f"{company}|"
        f"{location}"
    )


# =========================================================
# DEDUPLICATION
# =========================================================

def deduplicate_jobs(jobs):

    unique = {}

    for job in jobs:

        key = create_job_key(
            job
        )

        if not key:
            continue

        unique[key] = job

    return list(
        unique.values()
    )


# =========================================================
# LOAD EXISTING JOBS
# =========================================================

def load_existing_jobs():

    if not os.path.exists(
        output_file
    ):
        return []

    try:

        with open(
            output_file,
            "r",
            encoding="utf-8"
        ) as file:

            jobs = json.load(
                file
            )

        if not isinstance(
            jobs,
            list
        ):
            return []

        return jobs

    except Exception as error:

        print(
            "Could not load existing jobs:",
            error
        )

        return []


existing_jobs = load_existing_jobs()

print(
    "\nExisting jobs loaded:",
    len(existing_jobs)
)


# =========================================================
# CLEAN EXISTING JOBS
# =========================================================

valid_existing_jobs = []

for job in existing_jobs:

    if not is_within_last_hours(
        job.get("updated"),
        max_age_hours
    ):
        continue

    if is_excluded_title(
        job.get("title")
    ):
        continue

    valid_existing_jobs.append(
        job
    )


print(
    "Existing jobs still within 24h:",
    len(valid_existing_jobs)
)


# =========================================================
# JOOBLE API
# =========================================================

URL = (
    f"https://in.jooble.org/api/"
    f"{API_KEY}"
)

new_jobs = []

rejected_experience = 0


# =========================================================
# FETCH JOBS
# =========================================================

for role in roles:

    print(
        f"\nSearching: {role}"
    )

    payload = {
        "keywords": role,
        "location": "India",
        "page": "1"
    }

    try:

        response = requests.post(
            URL,
            json=payload,
            timeout=20
        )

    except requests.RequestException as error:

        print(
            "Request failed:",
            error
        )

        continue


    print(
        "Status:",
        response.status_code
    )


    if response.status_code != 200:

        print(
            "API error:",
            response.text
        )

        continue


    data = response.json()

    jobs = data.get(
        "jobs",
        []
    )

    print(
        "Received:",
        len(jobs)
    )


    for job in jobs:


        # -----------------------------
        # LAST 24 HOURS
        # -----------------------------

        if not is_within_last_hours(
            job.get("updated"),
            max_age_hours
        ):
            continue


        # -----------------------------
        # SENIOR / LEAD FILTER
        # -----------------------------

        if is_excluded_title(
            job.get("title")
        ):
            continue


        # -----------------------------
        # EXPERIENCE FILTER
        # -----------------------------

        if not experience_matches(
            job.get("title"),
            job.get("snippet")
        ):

            rejected_experience += 1

            continue


        new_jobs.append(
            normalize_job(job)
        )


# =========================================================
# REMOVE DUPLICATES FROM NEW JOBS
# =========================================================

new_jobs = deduplicate_jobs(
    new_jobs
)


print(
    "\nNew unique jobs found:",
    len(new_jobs)
)


# =========================================================
# MERGE EXISTING + NEW
# =========================================================

merged_jobs = (
    valid_existing_jobs
    +
    new_jobs
)

merged_jobs = deduplicate_jobs(
    merged_jobs
)


# =========================================================
# FINAL STALE CLEANUP
# =========================================================

final_jobs = []

for job in merged_jobs:

    if is_within_last_hours(
        job.get("updated"),
        max_age_hours
    ):

        final_jobs.append(
            job
        )


# =========================================================
# SORT NEWEST FIRST
# =========================================================

def sorting_date(job):

    parsed = parse_job_date(
        job.get("updated")
    )

    if parsed:
        return parsed

    return datetime.min.replace(
        tzinfo=timezone.utc
    )


final_jobs.sort(
    key=sorting_date,
    reverse=True
)


# =========================================================
# CREATE DATA DIRECTORY
# =========================================================

os.makedirs(
    "data",
    exist_ok=True
)


# =========================================================
# SAVE JOBS.JSON
# =========================================================

with open(
    output_file,
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        final_jobs,
        file,
        indent=2,
        ensure_ascii=False
    )


# =========================================================
# SAVE REFRESH METADATA
# =========================================================

refresh_metadata = {

    "refreshed_at":
        datetime.now(
            timezone.utc
        ).isoformat(),

    "total_jobs":
        len(final_jobs),

    "new_jobs_found":
        len(new_jobs),

    "existing_recent_jobs":
        len(valid_existing_jobs),

    "rejected_by_experience":
        rejected_experience,

    "max_age_hours":
        max_age_hours,

    "experience_min":
        USER_MIN_EXP,

    "experience_max":
        USER_MAX_EXP
}


with open(
    meta_file,
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        refresh_metadata,
        file,
        indent=2,
        ensure_ascii=False
    )


# =========================================================
# SUMMARY
# =========================================================

print(
    "\n" + "=" * 70
)

print(
    "Existing recent jobs:",
    len(valid_existing_jobs)
)

print(
    "New unique jobs:",
    len(new_jobs)
)

print(
    "Rejected by experience:",
    rejected_experience
)

print(
    "Final jobs after merge:",
    len(final_jobs)
)

print(
    "Saved jobs to:",
    output_file
)

print(
    "Refresh metadata saved to:",
    meta_file
)

print(
    "=" * 70
)


# =========================================================
# PRINT FINAL JOBS
# =========================================================

for index, job in enumerate(
    final_jobs,
    start=1
):

    print(
        f"\n{index}. "
        f"{job.get('title')}"
    )

    print(
        "Company:",
        job.get("company")
    )

    print(
        "Location:",
        job.get("location")
    )

    print(
        "Experience:",
        job.get("experience")
    )

    print(
        "Updated:",
        job.get("updated")
    )

    print(
        "Apply:",
        job.get("apply_link")
    )