import os
import re
import json
import requests

from datetime import datetime, timedelta, timezone


# =========================================================
# CONFIG
# =========================================================

LEVER_SITES = [

    {
        "company": "Lingaro",
        "site": "lingarogroup"
    },

    {
        "company": "3Pillar",
        "site": "3pillarglobal"
    },

    {
        "company": "Azul",
        "site": "azul"
    },

    {
        "company": "Saviynt",
        "site": "saviynt"
    },

    {
        "company": "Zimperium",
        "site": "zimperium"
    },

    {
        "company": "Hevo Data",
        "site": "hevodata"
    },

    {
        "company": "Veeva Systems",
        "site": "veeva",
        "exclude_title_terms": [
            "test automation",
            "release engineer",
            "infra",
            "test infrastructure"
        ]
    },

   {
        "company": "Brillio",
        "site": "brillio-2"
    },

        {
        "company": "Sonatype",
        "site": "sonatype"
    },

    {
        "company": "RapidAI",
        "site": "rapidai"
    },

    {
        "company": "Turvo",
        "site": "turvo"
    },

    {
        "company": "ValGenesis",
        "site": "valgenesis"
    }

]


SEEN_FILE = "data/lever_seen.json"


# =========================================================
# JAVA ROLE CONFIG
# =========================================================

DIRECT_JAVA_KEYWORDS = [
    "java",
    "spring",
    "spring boot",
    "j2ee",
    "jvm"
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


JAVA_DESCRIPTION_KEYWORDS = [
    "java",
    "spring",
    "spring boot",
    "hibernate",
    "jpa",
    "j2ee",
    "jvm"
]


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


    # 1-3 years
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


    return None, None


# =========================================================
# EXPERIENCE MATCH
# =========================================================

def experience_matches(
    text,
    user_min,
    user_max
):

    minimum, maximum = extract_experience(
        text
    )


    if minimum is None:
        return True


    return (
        minimum <= user_max
        and
        maximum >= user_min
    )


def experience_label(text):

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
# TITLE FILTER
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
        for keyword in DIRECT_JAVA_KEYWORDS
    ):
        return True


    # Generic developer / engineer titles

    generic_role = any(
        keyword in title_lower
        for keyword in GENERIC_DEV_TITLES
    )


    # SDE I / SDE II
    # Do NOT match SDE III / IV / higher levels

    sde_role = bool(
        re.search(
            r"\bsde\s*[-]?\s*(?:i|1|ii|2)\b",
            title_lower
        )
    )


    java_required = any(
        keyword in description_lower
        for keyword in JAVA_DESCRIPTION_KEYWORDS
    )


    return (
        (
            generic_role
            or
            sde_role
        )
        and
        java_required
    )


# =========================================================
# INDIA FILTER
# =========================================================

def is_india_job(job):

    country = (
        job.get("country")
        or ""
    ).lower()


    categories = (
        job.get("categories")
        or {}
    )


    location = (
        categories.get("location")
        or ""
    ).lower()


    all_locations = (
        categories.get("allLocations")
        or []
    )


    locations_text = " ".join(
        [
            location
        ]
        +
        [
            str(value).lower()
            for value in all_locations
        ]
    )


    if country == "in":
        return True


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
        "gandhinagar",
        "thane"
    ]


    return any(
        term in locations_text
        for term in india_terms
    )


# =========================================================
# LOAD STATE
# =========================================================

def load_seen_jobs():

    if not os.path.exists(
        SEEN_FILE
    ):
        return {}


    try:

        with open(
            SEEN_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)


        if isinstance(
            data,
            dict
        ):
            return data


    except Exception as error:

        print(
            "[Lever] State load error:",
            error
        )


    return {}


# =========================================================
# SAVE STATE
# =========================================================

def save_seen_jobs(data):

    os.makedirs(
        "data",
        exist_ok=True
    )


    with open(
        SEEN_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False
        )


# =========================================================
# DATE PARSER
# =========================================================

def parse_seen_time(value):

    if not value:
        return None


    try:

        dt = datetime.fromisoformat(
            value
        )


        if dt.tzinfo is None:

            dt = dt.replace(
                tzinfo=timezone.utc
            )


        return dt.astimezone(
            timezone.utc
        )


    except Exception:

        return None


# =========================================================
# FETCH LEVER
# =========================================================

def fetch_lever_jobs(
    max_age_hours=24,
    user_min_exp=0,
    user_max_exp=2
):

    now = datetime.now(
        timezone.utc
    )


    cutoff = now - timedelta(
        hours=max_age_hours
    )


    seen_jobs = load_seen_jobs()


    # =====================================================
    # MIGRATE OLD STATE
    # =====================================================

    meta = seen_jobs.get(
        "__meta__"
    )


    # You already ran an older seed.
    # Mark all of those jobs as baseline jobs.
    if meta is None and len(seen_jobs) > 0:

        print(
            "[Lever] Migrating previous seed state..."
        )


        for key, value in list(
            seen_jobs.items()
        ):

            if not isinstance(
                value,
                dict
            ):
                continue


            value["baseline"] = True


        seen_jobs["__meta__"] = {

            "initialized":
                True,

            "initialized_at":
                now.isoformat()
        }


        first_run = False


    # Brand new installation
    elif meta is None:

        print(
            "[Lever] Initial baseline seed..."
        )


        seen_jobs["__meta__"] = {

            "initialized":
                False,

            "initialized_at":
                now.isoformat()
        }


        first_run = True


    else:

        first_run = not bool(
            meta.get(
                "initialized",
                False
            )
        )


    print(
        "[Lever] First run:",
        first_run
    )


    matching_jobs = []


    # =====================================================
    # SCAN BOARDS
    # =====================================================

    for site_config in LEVER_SITES:


        company = site_config[
            "company"
        ]


        site = site_config[
            "site"
        ]

        company_excluded_title_terms = [
            term.lower()
            for term in site_config.get(
                "exclude_title_terms",
                []
            )
        ]


        print(
            f"\n[Lever] Scanning {company}"
        )


        url = (
            "https://api.lever.co/"
            f"v0/postings/{site}"
        )


        try:

            response = requests.get(

                url,

                params={
                    "mode":
                        "json"
                },

                timeout=30

            )


            print(
                "[Lever] Status:",
                response.status_code
            )


            if response.status_code != 200:
                continue


            jobs = response.json()


            if not isinstance(
                jobs,
                list
            ):
                continue


        except requests.RequestException as error:


            print(
                "[Lever] Request error:",
                error
            )


            continue


        print(
            "[Lever] Board jobs:",
            len(jobs)
        )


        board_matches = 0


        for job in jobs:


            job_id = str(
                job.get("id")
                or ""
            )


            if not job_id:
                continue


            state_key = (
                f"{site}:{job_id}"
            )


            title = (
                job.get("text")
                or ""
            )


            description_parts = [
                job.get("descriptionPlain") or "",
                job.get("descriptionBodyPlain") or "",
                job.get("additionalPlain") or ""
            ]


            for item in job.get(
                "lists",
                []
            ):

                description_parts.append(
                    str(
                        item.get(
                            "content",
                            ""
                        )
                    )
                )


            description = " ".join(
                description_parts
            )

            categories = (
                job.get("categories")
                or {}
            )


            location = (
                categories.get(
                    "location"
                )
                or ""
            )


            # =============================================
            # FIRST TIME THIS JOB HAS EVER BEEN SEEN
            # =============================================

            if state_key not in seen_jobs:


                # Initial scan jobs = baseline.
                # Future new jobs = genuine newly discovered job.
                baseline = first_run


                seen_jobs[
                    state_key
                ] = {

                    "first_seen":
                        now.isoformat(),

                    "company":
                        company,

                    "title":
                        title,

                    "baseline":
                        baseline
                }


            state = seen_jobs[
                state_key
            ]


            # =============================================
            # FILTERS
            # =============================================

            if not is_india_job(
                job
            ):
                continue


            if is_excluded_title(
                title
            ):
                continue

            title_lower = (
                title
                or ""
            ).lower()


            if any(
                term in title_lower
                for term in company_excluded_title_terms
            ):
                continue


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


            if not experience_matches(

                combined_text,

                user_min_exp,

                user_max_exp

            ):
                continue


            # =============================================
            # BASELINE JOBS ARE NEVER CALLED NEW
            # =============================================

            if state.get(
                "baseline",
                False
            ):

                continue


            first_seen = parse_seen_time(
                state.get(
                    "first_seen"
                )
            )


            if not first_seen:
                continue


            # =============================================
            # LAST 24 HOURS BASED ON FIRST DISCOVERY
            # =============================================

            if first_seen < cutoff:
                continue


            apply_link = (
                job.get("applyUrl")
                or
                job.get("hostedUrl")
            )


            matching_jobs.append({

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
                    first_seen.isoformat(),

                "source":
                    "lever",

                "apply_link":
                    apply_link,

                "snippet":
                    description[:1000],

                "lever_id":
                    job_id,

                "date_basis":
                    "first_seen"
            })


            board_matches += 1


        print(
            f"[Lever] "
            f"{company} recent matches: "
            f"{board_matches}"
        )


    # =====================================================
    # MARK INITIAL SEED COMPLETE
    # =====================================================

    if first_run:

        seen_jobs[
            "__meta__"
        ] = {

            "initialized":
                True,

            "initialized_at":
                now.isoformat()
        }


    # =====================================================
    # SAVE
    # =====================================================

    save_seen_jobs(
        seen_jobs
    )


    print(
        "\n[Lever] Total recent matches:",
        len(matching_jobs)
    )


    if first_run:

        print(
            "[Lever] Baseline seed complete."
        )


    return matching_jobs


# =========================================================
# TEST
# =========================================================

if __name__ == "__main__":


    jobs = fetch_lever_jobs(

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
            "First seen:",
            job["updated"]
        )


        print(
            "Apply:",
            job["apply_link"]
        )