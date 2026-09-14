import os
import re
import yaml
import requests
import json

from datetime import datetime, timedelta, timezone
from dateutil import parser
from dotenv import load_dotenv


# =========================================================
# LOAD ENVIRONMENT VARIABLES
# =========================================================

load_dotenv()

API_KEY = os.getenv("JOOBLE_API_KEY")

if not API_KEY:
    raise ValueError("JOOBLE_API_KEY .env file me nahi mila")


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

exclude_keywords = [
    word.lower()
    for word in search_config.get(
        "exclude_keywords",
        []
    )
]


# =========================================================
# EXPERIENCE CONFIG
# =========================================================

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


print("Configured roles:")

for role in roles:
    print("-", role)

print(
    f"\nTarget experience: "
    f"{USER_MIN_EXP}-{USER_MAX_EXP} years"
)


# =========================================================
# DATE FILTER
# =========================================================

def is_within_last_hours(updated_time, hours):

    if not updated_time:
        return False

    try:
        job_time = parser.parse(
            updated_time
        )

        if job_time.tzinfo is None:
            job_time = job_time.replace(
                tzinfo=timezone.utc
            )

        now = datetime.now(
            timezone.utc
        )

        cutoff_time = now - timedelta(
            hours=hours
        )

        return job_time >= cutoff_time

    except Exception as error:
        print(
            "Date parse error:",
            updated_time,
            error
        )

        return False


# =========================================================
# SENIOR / LEAD FILTER
# =========================================================

def is_excluded(job):

    title = (
        job.get("title")
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

def extract_experience(job):

    title = (
        job.get("title")
        or ""
    )

    snippet = (
        job.get("snippet")
        or ""
    )

    text = (
        title + " " + snippet
    ).lower()


    # ---------------------------------------
    # Fresher / entry level
    # ---------------------------------------

    fresher_terms = [
        "fresher",
        "freshers",
        "entry level",
        "entry-level",
        "graduate",
        "new grad",
        "0 year",
        "0 years"
    ]

    for term in fresher_terms:

        if term in text:
            return 0, 0


    # ---------------------------------------
    # Example:
    # 1-3 years
    # 1 - 3 years
    # 1 to 3 years
    # ---------------------------------------

    range_pattern = re.search(
        r"(\d+)\s*(?:-|–|to)\s*(\d+)\s*(?:years?|yrs?)",
        text
    )

    if range_pattern:

        minimum = int(
            range_pattern.group(1)
        )

        maximum = int(
            range_pattern.group(2)
        )

        return minimum, maximum


    # ---------------------------------------
    # Example:
    # 5+ years
    # 3+ yrs
    # ---------------------------------------

    plus_pattern = re.search(
        r"(\d+)\s*\+\s*(?:years?|yrs?)",
        text
    )

    if plus_pattern:

        minimum = int(
            plus_pattern.group(1)
        )

        return minimum, 99


    # ---------------------------------------
    # Example:
    # minimum 3 years
    # at least 3 years
    # ---------------------------------------

    minimum_pattern = re.search(
        r"(?:minimum|min\.?|at least)\s*(\d+)\s*(?:years?|yrs?)",
        text
    )

    if minimum_pattern:

        minimum = int(
            minimum_pattern.group(1)
        )

        return minimum, 99


    # ---------------------------------------
    # Example:
    # experience: 2 years
    # 2 years experience
    # ---------------------------------------

    exact_pattern = re.search(
        r"(\d+)\s*(?:years?|yrs?)\s*(?:of\s*)?(?:experience|exp)",
        text
    )

    if exact_pattern:

        years = int(
            exact_pattern.group(1)
        )

        return years, years


    # Experience not mentioned
    return None, None


# =========================================================
# EXPERIENCE MATCHING
# =========================================================

def experience_matches(job):

    job_min, job_max = extract_experience(
        job
    )


    # Experience not specified.
    # Keep the job so we don't miss suitable jobs.
    if job_min is None:
        return True


    # Check if required experience range
    # overlaps with user's experience range
    if (
        job_min <= USER_MAX_EXP
        and job_max >= USER_MIN_EXP
    ):
        return True


    return False


# =========================================================
# EXPERIENCE LABEL
# =========================================================

def get_experience_label(job):

    minimum, maximum = extract_experience(
        job
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
# DEDUPLICATION
# =========================================================

def deduplicate_jobs(jobs):

    unique_jobs = []

    seen = set()

    for job in jobs:

        link = (
            job.get("link")
            or ""
        ).strip().lower()

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


        if link:

            key = link

        else:

            key = (
                f"{title}|"
                f"{company}|"
                f"{location}"
            )


        if key not in seen:

            seen.add(key)

            unique_jobs.append(job)


    return unique_jobs


# =========================================================
# JOOBLE API
# =========================================================

URL = f"https://in.jooble.org/api/{API_KEY}"

all_jobs = []

rejected_by_experience = 0


# =========================================================
# SEARCH EVERY ROLE
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
            "API Error:",
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


    # =====================================================
    # FILTER JOBS
    # =====================================================

    for job in jobs:


        # -----------------------------
        # 24 HOURS
        # -----------------------------

        if not is_within_last_hours(
            job.get("updated"),
            max_age_hours
        ):
            continue


        # -----------------------------
        # SENIOR FILTER
        # -----------------------------

        if is_excluded(job):
            continue


        # -----------------------------
        # EXPERIENCE FILTER
        # -----------------------------

        if not experience_matches(job):

            rejected_by_experience += 1

            continue


        all_jobs.append(job)


# =========================================================
# DEDUPLICATE
# =========================================================

before_deduplication = len(
    all_jobs
)

all_jobs = deduplicate_jobs(
    all_jobs
)

after_deduplication = len(
    all_jobs
)


# =========================================================
# SUMMARY
# =========================================================

print(
    "\n" + "=" * 70
)

print(
    "Target experience:",
    f"{USER_MIN_EXP}-{USER_MAX_EXP} years"
)

print(
    "Rejected because of experience:",
    rejected_by_experience
)

print(
    "Jobs before duplicate removal:",
    before_deduplication
)

print(
    "Jobs after duplicate removal:",
    after_deduplication
)

print(
    "Total matching jobs:",
    len(all_jobs)
)

print(
    "=" * 70
)


# =========================================================
# PRINT FINAL JOBS
# =========================================================

for index, job in enumerate(
    all_jobs,
    start=1
):

    print(
        "\n" + "=" * 70
    )

    print(
        f"{index}. {job.get('title')}"
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
        get_experience_label(job)
    )

    print(
        "Updated:",
        job.get("updated")
    )

    print(
        "Source:",
        job.get("source")
    )

    print(
        "Apply Link:",
        job.get("link")
    )


print(
    "\n" + "=" * 70
)
# =========================================================
# SAVE RESULTS TO JSON
# =========================================================

output_file = config["output"].get(
    "json_file",
    "data/jobs.json"
)

json_jobs = []

for job in all_jobs:

    json_jobs.append({
        "title": job.get("title"),
        "company": job.get("company"),
        "location": job.get("location"),
        "experience": get_experience_label(job),
        "updated": job.get("updated"),
        "source": job.get("source"),
        "apply_link": job.get("link")
    })


with open(
    output_file,
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        json_jobs,
        file,
        indent=2,
        ensure_ascii=False
    )


print(
    f"\nSaved {len(json_jobs)} jobs to {output_file}"
)