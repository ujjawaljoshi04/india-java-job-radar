import re
import html
import requests

from datetime import datetime, timedelta, timezone
from dateutil import parser
from bs4 import BeautifulSoup


# =========================================================
# GREENHOUSE BOARDS
# =========================================================

GREENHOUSE_BOARDS = [

    {
        "company": "Capco",
        "board": "capco"
    },

    {
        "company": "Hyreo",
        "board": "hyreo"
    },

    {
        "company": "AQR India",
        "board": "india"
    }

]


# =========================================================
# ROLE KEYWORDS
# =========================================================

DIRECT_JAVA_TITLE_KEYWORDS = [
    "java",
    "spring",
    "spring boot",
    "j2ee"
]


GENERIC_DEV_TITLES = [
    "backend developer",
    "backend engineer",
    "software engineer",
    "software developer",
    "full stack",
    "fullstack",
    "microservice",
    "microservices"
]


JAVA_TECH_KEYWORDS = [
    "java",
    "spring",
    "spring boot",
    "hibernate",
    "jpa",
    "j2ee"
]


# =========================================================
# INDIA LOCATIONS
# =========================================================

INDIA_LOCATIONS = [
    "india",
    "bengaluru",
    "bangalore",
    "hyderabad",
    "pune",
    "mumbai",
    "chennai",
    "gurugram",
    "gurgaon",
    "noida",
    "delhi",
    "kolkata",
    "kochi",
    "indore",
    "ahmedabad",
    "vadodara",
    "thane",
    "gandhinagar",
    "coimbatore"
]


# =========================================================
# SENIOR TERMS
# =========================================================

EXCLUDED_TITLE_TERMS = [
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


# =========================================================
# CLEAN HTML
# =========================================================

def clean_html(value):

    if not value:
        return ""

    decoded = html.unescape(value)

    soup = BeautifulSoup(
        decoded,
        "html.parser"
    )

    return soup.get_text(
        " ",
        strip=True
    )


# =========================================================
# DATE
# =========================================================

def is_recent(
    date_value,
    max_age_hours
):

    if not date_value:
        return False

    try:

        job_time = parser.parse(
            date_value
        )

        if job_time.tzinfo is None:

            job_time = job_time.replace(
                tzinfo=timezone.utc
            )

        job_time = job_time.astimezone(
            timezone.utc
        )

        cutoff = (
            datetime.now(timezone.utc)
            -
            timedelta(
                hours=max_age_hours
            )
        )

        return job_time >= cutoff

    except Exception:

        return False


# =========================================================
# INDIA FILTER
# =========================================================

def is_india_job(location):

    location = (
        location
        or ""
    ).lower()

    return any(
        place in location
        for place in INDIA_LOCATIONS
    )


# =========================================================
# SENIOR FILTER
# =========================================================

def is_excluded_title(title):

    title = (
        title
        or ""
    ).lower()

    return any(
        term in title
        for term in EXCLUDED_TITLE_TERMS
    )


# =========================================================
# JAVA ROLE FILTER
# =========================================================

def is_java_role(
    title,
    description
):

    title_lower = (
        title
        or ""
    ).lower()

    description_lower = (
        description
        or ""
    ).lower()


    # Java directly in title
    if any(
        keyword in title_lower
        for keyword
        in DIRECT_JAVA_TITLE_KEYWORDS
    ):

        return True


    generic_role = any(
        keyword in title_lower
        for keyword
        in GENERIC_DEV_TITLES
    )


    java_required = any(
        keyword in description_lower
        for keyword
        in JAVA_TECH_KEYWORDS
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


    # minimum 3 years
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


    # Unknown experience:
    # keep the job.
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


    if minimum == 0 and maximum == 0:

        return "Fresher"


    if maximum == 99:

        return f"{minimum}+ years"


    if minimum == maximum:

        return f"{minimum} years"


    return (
        f"{minimum}-{maximum} years"
    )


# =========================================================
# FETCH ALL GREENHOUSE JOBS
# =========================================================

def fetch_greenhouse_jobs(
    max_age_hours=24,
    user_min_exp=0,
    user_max_exp=2
):

    all_jobs = []


    for board_config in GREENHOUSE_BOARDS:


        company = board_config[
            "company"
        ]

        board = board_config[
            "board"
        ]


        print(
            f"\n[Greenhouse] "
            f"Scanning {company}"
        )


        url = (
            "https://boards-api.greenhouse.io/"
            f"v1/boards/{board}/jobs"
        )


        try:

            response = requests.get(

                url,

                params={
                    "content": "true"
                },

                timeout=30

            )


            print(
                "[Greenhouse] Status:",
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


        except requests.RequestException as error:

            print(
                "[Greenhouse] Error:",
                error
            )

            continue


        board_matches = 0


        for job in jobs:


            title = (
                job.get("title")
                or ""
            )


            location = (
                job.get(
                    "location",
                    {}
                )
                .get(
                    "name",
                    ""
                )
            )


            updated = (
                job.get(
                    "updated_at"
                )
            )


            description = clean_html(
                job.get(
                    "content"
                )
            )


            # INDIA
            if not is_india_job(
                location
            ):
                continue


            # SENIOR
            if is_excluded_title(
                title
            ):
                continue


            # JAVA
            if not is_java_role(
                title,
                description
            ):
                continue


            # LAST 24 HOURS
            if not is_recent(
                updated,
                max_age_hours
            ):
                continue


            combined_text = (
                title
                + " "
                + description
            )


            # EXPERIENCE
            if not experience_matches(
                combined_text,
                user_min_exp,
                user_max_exp
            ):
                continue


            normalized_job = {

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
                    updated,

                "source":
                    "greenhouse",

                "apply_link":
                    job.get(
                        "absolute_url"
                    ),

                "snippet":
                    description[:1000]
            }


            all_jobs.append(
                normalized_job
            )


            board_matches += 1


        print(
            f"[Greenhouse] "
            f"{company} matches: "
            f"{board_matches}"
        )


    print(
        "\n[Greenhouse] Total matches:",
        len(all_jobs)
    )


    return all_jobs


# =========================================================
# TEST MODE
# =========================================================

if __name__ == "__main__":

    jobs = fetch_greenhouse_jobs(
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
            "Updated:",
            job["updated"]
        )

        print(
            "Apply:",
            job["apply_link"]
        )