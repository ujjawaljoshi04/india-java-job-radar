import os
import re
import requests

from datetime import datetime, timedelta, timezone
from dateutil import parser
from dotenv import load_dotenv


# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv()


APP_ID = os.getenv(
    "ADZUNA_APP_ID"
)

APP_KEY = os.getenv(
    "ADZUNA_APP_KEY"
)


if not APP_ID:

    raise ValueError(
        "ADZUNA_APP_ID not found"
    )


if not APP_KEY:

    raise ValueError(
        "ADZUNA_APP_KEY not found"
    )


# =========================================================
# API CONFIG
# =========================================================

ADZUNA_URL = (
    "https://api.adzuna.com/"
    "v1/api/jobs/in/search/1"
)


SEARCH_QUERIES = [

    "Java Developer",

    "Java Backend",

    "Spring Boot",

    "Java Microservices"

]


# =========================================================
# TITLE FILTER
# =========================================================

EXCLUDED_TITLE_TERMS = [

    "senior",
    "sr ",
    "sr.",
    "lead",
    "architect",
    "principal",
    "staff engineer",
    "manager",
    "director",
    "head",
    "avp",
    "vice president",

    # Higher engineering levels
    "software engineer iii",
    "engineer iii",
    "developer iii",
    "software engineer iv",
    "engineer iv",
    "developer iv",

    # Usually mid-level+
    "intermediate"

]


def is_excluded_title(title):

    title = (
        title
        or ""
    ).lower()


    return any(

        term in title

        for term
        in EXCLUDED_TITLE_TERMS

    )


# =========================================================
# JAVA DETECTION
# =========================================================

def contains_java_signal(text):

    text = (
        text
        or ""
    ).lower()


    patterns = [

        r"\bjava\b",

        r"\bspring boot\b",

        r"\bspring framework\b",

        r"\bj2ee\b",

        r"\bjvm\b",

        r"\bhibernate\b",

        r"\bjpa\b"

    ]


    return any(

        re.search(
            pattern,
            text
        )

        for pattern
        in patterns

    )


# =========================================================
# JAVA ROLE MATCH
# =========================================================

def is_java_role(
    title,
    description
):

    title = (
        title
        or ""
    )


    description = (
        description
        or ""
    )


    # Java directly mentioned in title
    if contains_java_signal(
        title
    ):

        return True


    generic_titles = [

        "backend developer",
        "backend engineer",
        "software developer",
        "software engineer",
        "full stack",
        "fullstack",
        "microservice",
        "microservices"

    ]


    title_lower = (
        title.lower()
    )


    generic_role = any(

        value in title_lower

        for value
        in generic_titles

    )


    java_required = (
        contains_java_signal(
            description
        )
    )


    return (

        generic_role

        and

        java_required

    )


# =========================================================
# EXPERIENCE PARSER
# =========================================================

def extract_experience(text):

    text = (
        text
        or ""
    ).lower()


    # Normalize dash characters
    text = (
        text
        .replace("–", "-")
        .replace("—", "-")
    )


    # -----------------------------------------------------
    # NUMBER HELPER
    # -----------------------------------------------------

    def parse_number(value):

        number = float(
            value
        )


        if number.is_integer():

            return int(
                number
            )


        return number


    # -----------------------------------------------------
    # FRESHER / ENTRY LEVEL
    # -----------------------------------------------------

    fresher_terms = [

        "fresher",
        "freshers",
        "entry level",
        "entry-level",
        "new grad",
        "new graduate",
        "graduate trainee",
        "graduate engineer trainee",
        "0 years experience",
        "0 year experience"

    ]


    for term in fresher_terms:

        if term in text:

            return (
                0,
                0
            )


    # -----------------------------------------------------
    # 0-2 YEARS
    # 1-3 YEARS
    # 1 TO 3 YEARS
    # 1.5-3 YEARS
    # 2-4 YOE
    # -----------------------------------------------------

    match = re.search(

        r"\b"
        r"(\d+(?:\.\d+)?)"
        r"\s*(?:-|to)\s*"
        r"(\d+(?:\.\d+)?)"
        r"\s*"
        r"(?:years?|yrs?|yoe)"
        r"\b",

        text

    )


    if match:

        minimum = parse_number(
            match.group(1)
        )


        maximum = parse_number(
            match.group(2)
        )


        return (
            minimum,
            maximum
        )


    # -----------------------------------------------------
    # BETWEEN 1 AND 3 YEARS
    # -----------------------------------------------------

    match = re.search(

        r"\bbetween\s+"
        r"(\d+(?:\.\d+)?)"
        r"\s+and\s+"
        r"(\d+(?:\.\d+)?)"
        r"\s*"
        r"(?:years?|yrs?|yoe)"
        r"\b",

        text

    )


    if match:

        minimum = parse_number(
            match.group(1)
        )


        maximum = parse_number(
            match.group(2)
        )


        return (
            minimum,
            maximum
        )


    # -----------------------------------------------------
    # 2+ YEARS
    # 2.5+ YEARS
    # 3+ YOE
    # -----------------------------------------------------

    match = re.search(

        r"\b"
        r"(\d+(?:\.\d+)?)"
        r"\s*\+\s*"
        r"(?:years?|yrs?|yoe)"
        r"\b",

        text

    )


    if match:

        minimum = parse_number(
            match.group(1)
        )


        return (
            minimum,
            99
        )


    # -----------------------------------------------------
    # MINIMUM 2 YEARS
    # MIN 2 YEARS
    # AT LEAST 2 YEARS
    # -----------------------------------------------------

    match = re.search(

        r"\b"
        r"(?:minimum|min\.?|at least)"
        r"\s*"
        r"(\d+(?:\.\d+)?)"
        r"\s*"
        r"(?:years?|yrs?|yoe)"
        r"\b",

        text

    )


    if match:

        minimum = parse_number(
            match.group(1)
        )


        return (
            minimum,
            99
        )


    # -----------------------------------------------------
    # MORE THAN 2 YEARS
    # OVER 2 YEARS
    # -----------------------------------------------------

    match = re.search(

        r"\b"
        r"(?:more than|over)"
        r"\s*"
        r"(\d+(?:\.\d+)?)"
        r"\s*"
        r"(?:years?|yrs?|yoe)"
        r"\b",

        text

    )


    if match:

        minimum = parse_number(
            match.group(1)
        )


        return (
            minimum,
            99
        )


    # -----------------------------------------------------
    # UP TO 2 YEARS
    # MAXIMUM 2 YEARS
    # MAX 2 YEARS
    # -----------------------------------------------------

    match = re.search(

        r"\b"
        r"(?:up to|maximum|max\.?)"
        r"\s*"
        r"(\d+(?:\.\d+)?)"
        r"\s*"
        r"(?:years?|yrs?|yoe)"
        r"\b",

        text

    )


    if match:

        maximum = parse_number(
            match.group(1)
        )


        return (
            0,
            maximum
        )


    # -----------------------------------------------------
    # 2 YEARS EXPERIENCE
    # 2 YEARS OF EXPERIENCE
    # 1.5 YRS EXPERIENCE
    # -----------------------------------------------------

    match = re.search(

        r"\b"
        r"(\d+(?:\.\d+)?)"
        r"\s*"
        r"(?:years?|yrs?)"
        r"\s*(?:of\s*)?"
        r"(?:relevant\s*)?"
        r"(?:professional\s*)?"
        r"(?:work\s*)?"
        r"(?:experience|exp)"
        r"\b",

        text

    )


    if match:

        years = parse_number(
            match.group(1)
        )


        return (
            years,
            years
        )


    # -----------------------------------------------------
    # EXPERIENCE: 2 YEARS
    # EXPERIENCE OF 2 YEARS
    # EXP - 2 YEARS
    # -----------------------------------------------------

    match = re.search(

        r"\b"
        r"(?:experience|exp)"
        r"\s*(?:of|:|-)?\s*"
        r"(\d+(?:\.\d+)?)"
        r"\s*"
        r"(?:years?|yrs?)"
        r"\b",

        text

    )


    if match:

        years = parse_number(
            match.group(1)
        )


        return (
            years,
            years
        )


    # -----------------------------------------------------
    # 2 YOE
    # 1.5 YOE
    # -----------------------------------------------------

    match = re.search(

        r"\b"
        r"(\d+(?:\.\d+)?)"
        r"\s*yoe"
        r"\b",

        text

    )


    if match:

        years = parse_number(
            match.group(1)
        )


        return (
            years,
            years
        )


    # No reliable experience requirement found

    return (
        None,
        None
    )


# =========================================================
# EXPERIENCE MATCH
# =========================================================

def experience_matches(
    text,
    user_min,
    user_max
):

    minimum, maximum = (
        extract_experience(
            text
        )
    )


    # Unknown experience should not be discarded
    if minimum is None:

        return True


    return (

        minimum <= user_max

        and

        maximum >= user_min

    )


# =========================================================
# EXPERIENCE LABEL
# =========================================================

def experience_label(text):

    minimum, maximum = (
        extract_experience(
            text
        )
    )


    if minimum is None:

        return "Not specified"


    if (
        minimum == 0
        and
        maximum == 0
    ):

        return "Fresher"


    if maximum == 99:

        return (
            f"{minimum}+ years"
        )


    if minimum == maximum:

        return (
            f"{minimum} years"
        )


    return (
        f"{minimum}-{maximum} years"
    )


# =========================================================
# DATE PARSER
# =========================================================

def parse_date(value):

    if not value:

        return None


    try:

        date = parser.parse(
            value
        )


        if date.tzinfo is None:

            date = date.replace(
                tzinfo=timezone.utc
            )


        return date.astimezone(
            timezone.utc
        )


    except Exception:

        return None


# =========================================================
# RECENCY FILTER
# =========================================================

def is_recent(
    value,
    max_age_hours
):

    created = parse_date(
        value
    )


    if not created:

        return False


    cutoff = (

        datetime.now(
            timezone.utc
        )

        -

        timedelta(
            hours=max_age_hours
        )

    )


    return (
        created >= cutoff
    )


# =========================================================
# ADZUNA JOB KEY
# =========================================================

def create_key(job):

    job_id = str(

        job.get(
            "id"
        )

        or ""

    ).strip()


    if job_id:

        return job_id


    return (

        (
            job.get(
                "redirect_url"
            )

            or ""

        )

        .strip()
        .lower()

    )


# =========================================================
# FETCH ADZUNA JOBS
# =========================================================

def fetch_adzuna_jobs(
    max_age_hours=24,
    user_min_exp=0,
    user_max_exp=2
):

    collected = {}


    rejected_by_experience = 0

    rejected_by_title = 0

    rejected_by_age = 0


    print(
        "\n[Adzuna] Starting search"
    )


    for query in SEARCH_QUERIES:


        print(

            f"\n[Adzuna] Searching: "
            f"{query}"

        )


        params = {

            "app_id":
                APP_ID,

            "app_key":
                APP_KEY,

            "results_per_page":
                50,

            "what":
                query,

            "sort_by":
                "date",

            "content-type":
                "application/json"

        }


        try:

            response = requests.get(

                ADZUNA_URL,

                params=params,

                headers={

                    "Accept":
                        "application/json"

                },

                timeout=30

            )


        except requests.RequestException as error:

            print(

                "[Adzuna] Request failed:",

                error

            )

            continue


        print(

            "[Adzuna] Status:",

            response.status_code

        )


        if response.status_code != 200:

            print(

                "[Adzuna] Response:",

                response.text[:300]

            )

            continue


        data = response.json()


        jobs = data.get(
            "results",
            []
        )


        print(

            "[Adzuna] Received:",

            len(
                jobs
            )

        )


        for job in jobs:


            title = (

                job.get(
                    "title"
                )

                or ""

            )


            description = (

                job.get(
                    "description"
                )

                or ""

            )


            created = (
                job.get(
                    "created"
                )
            )


            # ---------------------------------------------
            # LAST 24 HOURS
            # ---------------------------------------------

            if not is_recent(

                created,

                max_age_hours

            ):

                rejected_by_age += 1

                continue


            # ---------------------------------------------
            # HIGH LEVEL / SENIOR TITLES
            # ---------------------------------------------

            if is_excluded_title(
                title
            ):

                rejected_by_title += 1

                continue


            # ---------------------------------------------
            # JAVA RELEVANCE
            # ---------------------------------------------

            if not is_java_role(

                title,

                description

            ):

                continue


            combined_text = (

                title

                + " "

                + description

            )


            # ---------------------------------------------
            # EXPERIENCE
            # ---------------------------------------------

            if not experience_matches(

                combined_text,

                user_min_exp,

                user_max_exp

            ):

                rejected_by_experience += 1

                continue


            company_data = (

                job.get(
                    "company"
                )

                or {}

            )


            location_data = (

                job.get(
                    "location"
                )

                or {}

            )


            company = (

                company_data.get(
                    "display_name"
                )

                or

                "Unknown Company"

            )


            location = (

                location_data.get(
                    "display_name"
                )

                or

                "India"

            )


            apply_link = (
                job.get(
                    "redirect_url"
                )
            )


            normalized = {

                "title":
                    title,

                "company":
                    company,

                "location":
                    location,

                "experience":
                    experience_label(
                        combined_text
                    ),

                "updated":
                    created,

                "source":
                    "adzuna",

                "apply_link":
                    apply_link,

                "snippet":
                    description[:1000],

                "adzuna_id":
                    str(

                        job.get(
                            "id"
                        )

                        or ""

                    ),

                "date_basis":
                    "created"

            }


            key = create_key(
                job
            )


            if key:

                collected[
                    key
                ] = normalized


    matching_jobs = list(
        collected.values()
    )


    matching_jobs.sort(

        key=lambda job:

            parse_date(
                job.get(
                    "updated"
                )
            )

            or

            datetime.min.replace(
                tzinfo=timezone.utc
            ),

        reverse=True

    )


    print(

        "\n[Adzuna] Unique matching jobs:",

        len(
            matching_jobs
        )

    )


    print(

        "[Adzuna] Rejected by experience:",

        rejected_by_experience

    )


    print(

        "[Adzuna] Rejected by title:",

        rejected_by_title

    )


    return matching_jobs


# =========================================================
# STANDALONE TEST
# =========================================================

if __name__ == "__main__":


    jobs = fetch_adzuna_jobs(

        max_age_hours=24,

        user_min_exp=0,

        user_max_exp=2

    )


    for index, job in enumerate(

        jobs,

        start=1

    ):


        print(
            "\n" + "=" * 70
        )


        print(

            f"{index}. "
            f"{job['title']}"

        )


        print(

            "Company:",

            job["company"]

        )


        print(

            "Location:",

            job["location"]

        )


        print(

            "Experience:",

            job["experience"]

        )


        print(

            "Created:",

            job["updated"]

        )


        print(

            "Source:",

            job["source"]

        )


        print(

            "Apply:",

            job["apply_link"]

        )