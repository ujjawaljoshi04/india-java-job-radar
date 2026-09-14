import os
import re
import json
import yaml
import requests
from adzuna_source import fetch_adzuna_jobs

from datetime import datetime, timedelta, timezone
from dateutil import parser
from dotenv import load_dotenv

from greenhouse_source import fetch_greenhouse_jobs
from lever_source import fetch_lever_jobs
from ashby_source import fetch_ashby_jobs


# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv()

API_KEY = os.getenv("JOOBLE_API_KEY")

if not API_KEY:
    raise ValueError("JOOBLE_API_KEY not found")


# =========================================================
# CONFIG
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
    value.lower()
    for value in search_config.get(
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

print("=" * 70)

print("INDIA JAVA JOB RADAR")

print("=" * 70)

print("\nConfigured roles:")

for role in roles:
    print("-", role)


print(
    f"\nTarget experience: "
    f"{USER_MIN_EXP}-{USER_MAX_EXP} years"
)

print(
    f"Maximum age: "
    f"{max_age_hours} hours"
)


# =========================================================
# DATE FUNCTIONS
# =========================================================

def parse_job_date(value):

    if not value:
        return None

    try:

        result = parser.parse(value)

        if result.tzinfo is None:
            result = result.replace(
                tzinfo=timezone.utc
            )

        return result.astimezone(
            timezone.utc
        )

    except Exception:
        return None


def is_within_last_hours(
    value,
    hours
):

    job_time = parse_job_date(
        value
    )

    if not job_time:
        return False


    cutoff = (
        datetime.now(timezone.utc)
        -
        timedelta(hours=hours)
    )


    return job_time >= cutoff


# =========================================================
# TITLE EXCLUSION
# =========================================================

def is_excluded_title(title):

    text = (
        title
        or ""
    ).lower()


    default_terms = [
        "senior",
        "sr ",
        "sr.",
        "lead",
        "architect",
        "manager",
        "principal",
        "staff engineer",
        "director",
        "head"
    ]


    for term in default_terms:

        if term in text:
            return True


    for term in exclude_keywords:

        if term in text:
            return True


    return False


# =========================================================
# EXPERIENCE PARSER
# =========================================================

def extract_experience(text):

    text = (
        text
        or ""
    ).lower()


    fresher_terms = [
        "fresher",
        "freshers",
        "entry level",
        "entry-level",
        "new grad",
        "graduate trainee"
    ]


    for term in fresher_terms:

        if term in text:
            return 0, 0


    # 1-3 years / 1 to 3 years
    match = re.search(
        r"(\d+)\s*(?:-|–|to)\s*(\d+)"
        r"\s*(?:years?|yrs?)",
        text
    )

    if match:

        return (
            int(match.group(1)),
            int(match.group(2))
        )


    # 3+ years
    match = re.search(
        r"(\d+)\s*\+\s*(?:years?|yrs?)",
        text
    )

    if match:

        return (
            int(match.group(1)),
            99
        )


    # minimum / at least 3 years
    match = re.search(
        r"(?:minimum|min\.?|at least)"
        r"\s*(\d+)\s*(?:years?|yrs?)",
        text
    )

    if match:

        return (
            int(match.group(1)),
            99
        )


    # 2 years experience
    match = re.search(
        r"(\d+)\s*(?:years?|yrs?)"
        r"\s*(?:of\s*)?(?:experience|exp)",
        text
    )

    if match:

        years = int(
            match.group(1)
        )

        return (
            years,
            years
        )


    return None, None


# =========================================================
# EXPERIENCE MATCH
# =========================================================

def experience_matches(
    title,
    snippet
):

    text = (
        f"{title or ''} "
        f"{snippet or ''}"
    )


    minimum, maximum = extract_experience(
        text
    )


    # If experience is unknown, keep it.
    if minimum is None:
        return True


    return (
        minimum <= USER_MAX_EXP
        and
        maximum >= USER_MIN_EXP
    )


# =========================================================
# EXPERIENCE LABEL
# =========================================================

def experience_label(
    title,
    snippet
):

    text = (
        f"{title or ''} "
        f"{snippet or ''}"
    )


    minimum, maximum = extract_experience(
        text
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
# NORMALIZE JOOBLE JOB
# =========================================================

def normalize_jooble_job(job):

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
            "jooble",

        "original_source":
            job.get("source"),

        "apply_link":
            job.get("link"),

        "snippet":
            job.get("snippet"),

        "date_basis":
            "updated"
    }


# =========================================================
# NORMALIZE TEXT FOR DEDUPLICATION
# =========================================================

def normalize_text(value):

    value = (
        value
        or ""
    ).lower().strip()


    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value
    )


    value = re.sub(
        r"\s+",
        " ",
        value
    )


    return value.strip()


# =========================================================
# JOB KEY
# =========================================================

def create_job_key(job):

    title = normalize_text(
        job.get("title")
    )

    company = normalize_text(
        job.get("company")
    )

    location = normalize_text(
        job.get("location")
    )


    if title and company:

        return (
            f"{title}|"
            f"{company}|"
            f"{location}"
        )


    link = (
        job.get("apply_link")
        or ""
    ).strip().lower()


    return link


# =========================================================
# SOURCE PRIORITY
# =========================================================

def source_priority(source):

    priority = {
        "greenhouse": 4,
        "lever": 4,
        "ashby": 4,

        "adzuna": 2,
        "jooble": 2
    }


    return priority.get(
        source,
        1
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


        if key not in unique:

            unique[key] = job

            continue


        existing = unique[key]


        existing_source = (
            existing.get("source")
        )

        incoming_source = (
            job.get("source")
        )


        # Prefer direct ATS source
        if (
            source_priority(
                incoming_source
            )
            >
            source_priority(
                existing_source
            )
        ):

            unique[key] = job

            continue


        # If source priority same,
        # keep the newest record
        existing_date = parse_job_date(
            existing.get("updated")
        )

        incoming_date = parse_job_date(
            job.get("updated")
        )


        if (
            incoming_date
            and
            (
                not existing_date
                or
                incoming_date > existing_date
            )
        ):

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

            data = json.load(
                file
            )


        if isinstance(
            data,
            list
        ):

            return data


    except Exception as error:

        print(
            "Existing jobs load error:",
            error
        )


    return []


# =========================================================
# LOAD + CLEAN EXISTING JOBS
# =========================================================

existing_jobs = load_existing_jobs()


print(
    "\nExisting jobs loaded:",
    len(existing_jobs)
)


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
    "Existing jobs still valid:",
    len(valid_existing_jobs)
)


# =========================================================
# SOURCE 1: JOOBLE
# =========================================================

print(
    "\n" + "=" * 70
)

print("SOURCE 1: JOOBLE")

print("=" * 70)


JOOBLE_URL = (
    f"https://in.jooble.org/api/"
    f"{API_KEY}"
)


jooble_jobs = []

jooble_rejected_experience = 0


for role in roles:


    print(
        f"\n[Jooble] Searching: "
        f"{role}"
    )


    payload = {

        "keywords":
            role,

        "location":
            "India",

        "page":
            "1"

    }


    try:

        response = requests.post(

            JOOBLE_URL,

            json=payload,

            timeout=20

        )


    except requests.RequestException as error:

        print(
            "[Jooble] Request failed:",
            error
        )

        continue


    print(
        "[Jooble] Status:",
        response.status_code
    )


    if response.status_code != 200:
        continue


    jobs = (
        response
        .json()
        .get(
            "jobs",
            []
        )
    )


    print(
        "[Jooble] Received:",
        len(jobs)
    )


    for job in jobs:


        if not is_within_last_hours(

            job.get("updated"),

            max_age_hours

        ):

            continue


        if is_excluded_title(
            job.get("title")
        ):

            continue


        if not experience_matches(

            job.get("title"),

            job.get("snippet")

        ):

            jooble_rejected_experience += 1

            continue


        jooble_jobs.append(

            normalize_jooble_job(
                job
            )

        )


jooble_jobs = deduplicate_jobs(
    jooble_jobs
)


print(
    "\n[Jooble] Unique matching jobs:",
    len(jooble_jobs)
)


# =========================================================
# SOURCE 2: GREENHOUSE
# =========================================================

print(
    "\n" + "=" * 70
)

print("SOURCE 2: GREENHOUSE")

print("=" * 70)


greenhouse_jobs = fetch_greenhouse_jobs(

    max_age_hours=
        max_age_hours,

    user_min_exp=
        USER_MIN_EXP,

    user_max_exp=
        USER_MAX_EXP

)


greenhouse_jobs = deduplicate_jobs(
    greenhouse_jobs
)


print(
    "\n[Greenhouse] Unique matching jobs:",
    len(greenhouse_jobs)
)


# =========================================================
# SOURCE 3: LEVER
# =========================================================

print(
    "\n" + "=" * 70
)

print("SOURCE 3: LEVER")

print("=" * 70)


lever_jobs = fetch_lever_jobs(

    max_age_hours=
        max_age_hours,

    user_min_exp=
        USER_MIN_EXP,

    user_max_exp=
        USER_MAX_EXP

)


lever_jobs = deduplicate_jobs(
    lever_jobs
)


print(
    "\n[Lever] Unique recent jobs:",
    len(lever_jobs)
)


# =========================================================
# SOURCE 4: ASHBY
# =========================================================

print(
    "\n" + "=" * 70
)

print("SOURCE 4: ASHBY")

print("=" * 70)


ashby_jobs = fetch_ashby_jobs(

    max_age_hours=
        max_age_hours,

    user_min_exp=
        USER_MIN_EXP,

    user_max_exp=
        USER_MAX_EXP

)


ashby_jobs = deduplicate_jobs(
    ashby_jobs
)


print(
    "\n[Ashby] Unique matching jobs:",
    len(ashby_jobs)
)

# =========================================================
# SOURCE 5: ADZUNA
# =========================================================

print(
    "\n" + "=" * 70
)

print("SOURCE 5: ADZUNA")

print("=" * 70)


adzuna_jobs = fetch_adzuna_jobs(

    max_age_hours=
        max_age_hours,

    user_min_exp=
        USER_MIN_EXP,

    user_max_exp=
        USER_MAX_EXP

)


adzuna_jobs = deduplicate_jobs(
    adzuna_jobs
)


print(
    "\n[Adzuna] Unique matching jobs:",
    len(adzuna_jobs)
)

# =========================================================
# MERGE ALL NEW SOURCES
# =========================================================

new_jobs = (

    jooble_jobs

    +

    greenhouse_jobs

    +

    lever_jobs

    +

    ashby_jobs

    +

    adzuna_jobs

)


new_jobs = deduplicate_jobs(
    new_jobs
)


print(
    "\nTotal new jobs across sources:",
    len(new_jobs)
)


# =========================================================
# MERGE OLD + NEW
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
# FINAL CLEANUP
# =========================================================

final_jobs = []


for job in merged_jobs:


    if not is_within_last_hours(

        job.get("updated"),

        max_age_hours

    ):

        continue


    if is_excluded_title(
        job.get("title")
    ):

        continue


    final_jobs.append(
        job
    )


# =========================================================
# SORT NEWEST FIRST
# =========================================================

def sorting_date(job):

    value = parse_job_date(
        job.get("updated")
    )


    if value:
        return value


    return datetime.min.replace(
        tzinfo=timezone.utc
    )


final_jobs.sort(

    key=sorting_date,

    reverse=True

)


# =========================================================
# SAVE JOB DATA
# =========================================================

os.makedirs(
    "data",
    exist_ok=True
)


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
# SOURCE COUNTS IN FINAL DATA
# =========================================================

final_source_counts = {}


for job in final_jobs:

    source = (
        job.get("source")
        or "unknown"
    )


    final_source_counts[source] = (
        final_source_counts.get(
            source,
            0
        )
        +
        1
    )


# =========================================================
# METADATA
# =========================================================

refresh_metadata = {


    "refreshed_at":

        datetime.now(
            timezone.utc
        ).isoformat(),


    "total_jobs":

        len(final_jobs),


    "existing_recent_jobs":

        len(valid_existing_jobs),


    "jooble_new_jobs":

        len(jooble_jobs),


    "greenhouse_new_jobs":

        len(greenhouse_jobs),


    "lever_new_jobs":

        len(lever_jobs),


   "ashby_new_jobs":

    len(ashby_jobs),


"adzuna_new_jobs":

    len(adzuna_jobs),
        


    "total_new_jobs":

        len(new_jobs),


    "final_source_counts":

        final_source_counts,


    "jooble_rejected_by_experience":

        jooble_rejected_experience,


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
# FINAL SUMMARY
# =========================================================

print(
    "\n" + "=" * 70
)

print("FINAL SUMMARY")

print("=" * 70)


print(
    "Existing valid jobs:",
    len(valid_existing_jobs)
)


print(
    "Jooble new jobs:",
    len(jooble_jobs)
)


print(
    "Greenhouse new jobs:",
    len(greenhouse_jobs)
)


print(
    "Lever new jobs:",
    len(lever_jobs)
)


print(
    "Ashby new jobs:",
    len(ashby_jobs)
)

print(
    "Adzuna new jobs:",
    len(adzuna_jobs)
)


print(
    "New jobs across sources:",
    len(new_jobs)
)


print(
    "Final jobs after merge:",
    len(final_jobs)
)


print(
    "Final source counts:",
    final_source_counts
)


print(
    "Saved to:",
    output_file
)


print(
    "Metadata:",
    meta_file
)


print("=" * 70)


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
        "Source:",
        job.get("source")
    )


    print(
        "Updated:",
        job.get("updated")
    )


    print(
        "Apply:",
        job.get("apply_link")
    )