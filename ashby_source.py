import re
import requests

from datetime import datetime, timedelta, timezone
from dateutil import parser


# =========================================================
# ASHBY BOARDS
# =========================================================

ASHBY_BOARDS = [

    {
        "company": "Ema",
        "board": "ema"
    },

    {
        "company": "Tekion",
        "board": "tekion"
    },

    {
        "company": "Certa",
        "board": "certa"
    },

    {
        "company": "Mem0",
        "board": "mem0"
    },

    {
        "company": "Gradera",
        "board": "gradera"
    },

    {
        "company": "Netspend",
        "board": "Netspend-Careers-Page"
    },

    {
        "company": "AiPrise",
        "board": "aiprise"
    },

   {
        "company": "Ontic",
        "board": "ontic"
    }

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
    "principal",
    "staff engineer",
    "manager",
    "director",
    "head"
]


# =========================================================
# GENERIC DEVELOPER TITLES
# =========================================================

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


# =========================================================
# JAVA DETECTION
# =========================================================

def contains_java_technology(text):

    text = (
        text
        or ""
    ).lower()


    patterns = [
        r"\bjava\b",
        r"\bspring boot\b",
        r"\bspring framework\b",
        r"\bj2ee\b",
        r"\bhibernate\b",
        r"\bjpa\b",
        r"\bjvm\b"
    ]


    return any(
        re.search(pattern, text)
        for pattern in patterns
    )


# =========================================================
# JAVA ROLE MATCH
# =========================================================

def is_java_role(
    title,
    description
):

    title_lower = (
        title
        or ""
    ).lower()


    # Direct Java technology in title
    if contains_java_technology(
        title_lower
    ):
        return True


    # Generic backend/software role
    generic_role = any(
        term in title_lower
        for term in GENERIC_DEV_TITLES
    )


    # Description must actually require Java technology
    java_required = contains_java_technology(
        description
    )


    return (
        generic_role
        and
        java_required
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
# INDIA FILTER
# =========================================================

def is_india_job(job):

    location = (
        job.get("location")
        or ""
    ).lower()


    secondary_locations = (
        job.get("secondaryLocations")
        or []
    )


    address = (
        job.get("address")
        or {}
    )


    postal_address = (
        address.get("postalAddress")
        or {}
    )


    country = (
        postal_address.get(
            "addressCountry"
        )
        or ""
    ).lower()


    secondary_text = " ".join(

        str(
            item.get(
                "location",
                ""
            )
        ).lower()

        for item
        in secondary_locations

    )


    combined = (
        location
        + " "
        + secondary_text
        + " "
        + country
    )


    india_terms = [
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
        "ahmedabad",
        "indore",
        "coimbatore",
        "vadodara",
        "thane",
        "gandhinagar"
    ]


    return any(
        term in combined
        for term in india_terms
    )


# =========================================================
# DATE FILTER
# =========================================================

def is_recent(
    published_at,
    max_age_hours
):

    if not published_at:
        return False


    try:

        published_time = parser.parse(
            published_at
        )


        if published_time.tzinfo is None:

            published_time = (
                published_time.replace(
                    tzinfo=timezone.utc
                )
            )


        published_time = (
            published_time.astimezone(
                timezone.utc
            )
        )


        cutoff = (
            datetime.now(timezone.utc)
            -
            timedelta(
                hours=max_age_hours
            )
        )


        return (
            published_time >= cutoff
        )


    except Exception:

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
    text,
    user_min,
    user_max
):

    minimum, maximum = (
        extract_experience(
            text
        )
    )


    # Keep unknown experience
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
# FETCH ASHBY
# =========================================================

def fetch_ashby_jobs(
    max_age_hours=24,
    user_min_exp=0,
    user_max_exp=2
):

    matching_jobs = []


    for board_config in ASHBY_BOARDS:


        company = (
            board_config["company"]
        )


        board = (
            board_config["board"]
        )


        print(
            f"\n[Ashby] Scanning "
            f"{company}"
        )


        url = (
            "https://api.ashbyhq.com/"
            "posting-api/job-board/"
            f"{board}"
        )


        try:

            response = requests.get(
                url,
                timeout=30
            )


            print(
                "[Ashby] Status:",
                response.status_code
            )


            if response.status_code != 200:

                continue


            data = response.json()


            jobs = data.get(
                "jobs",
                []
            )


        except requests.RequestException as error:

            print(
                "[Ashby] Request error:",
                error
            )

            continue


        print(
            "[Ashby] Board jobs:",
            len(jobs)
        )


        board_matches = 0


        for job in jobs:


            # -----------------------------------------
            # Only listed/public postings
            # -----------------------------------------

            if (
                job.get("isListed")
                is False
            ):

                continue


            title = (
                job.get("title")
                or ""
            )


            description = (
                job.get(
                    "descriptionPlain"
                )
                or ""
            )


            published_at = (
                job.get(
                    "publishedAt"
                )
            )


            location = (
                job.get("location")
                or ""
            )


            # -----------------------------------------
            # INDIA
            # -----------------------------------------

            if not is_india_job(
                job
            ):

                continue


            # -----------------------------------------
            # SENIOR
            # -----------------------------------------

            if is_excluded_title(
                title
            ):

                continue


            # -----------------------------------------
            # JAVA
            # -----------------------------------------

            if not is_java_role(
                title,
                description
            ):

                continue


            # -----------------------------------------
            # LAST 24 HOURS
            # -----------------------------------------

            if not is_recent(
                published_at,
                max_age_hours
            ):

                continue


            combined_text = (
                title
                + " "
                + description
            )


            # -----------------------------------------
            # EXPERIENCE
            # -----------------------------------------

            if not experience_matches(

                combined_text,

                user_min_exp,

                user_max_exp

            ):

                continue


            # -----------------------------------------
            # DIRECT APPLY LINK
            # -----------------------------------------

            apply_link = (
                job.get("applyUrl")
                or
                job.get("jobUrl")
            )


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
                    published_at,

                "source":
                    "ashby",

                "apply_link":
                    apply_link,

                "snippet":
                    description[:1000],

                "date_basis":
                    "publishedAt"
            }


            matching_jobs.append(
                normalized_job
            )


            board_matches += 1


        print(
            f"[Ashby] "
            f"{company} matches: "
            f"{board_matches}"
        )


    print(
        "\n[Ashby] Total matches:",
        len(matching_jobs)
    )


    return matching_jobs


# =========================================================
# TEST MODE
# =========================================================

if __name__ == "__main__":


    jobs = fetch_ashby_jobs(

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
            "Published:",
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