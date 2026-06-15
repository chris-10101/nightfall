from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import csv
from datetime import date
from pathlib import Path

from core.monitoring import init_sentry
from core.paths import data_dir
from imports.import_hr_consultancies import HEADERS


PROSPECTS_PATH = data_dir() / "prospects.csv"
TODAY = date.today().isoformat()


ENRICHMENTS = {
    "Norton Loxley | Outsourced HR Consultants": {
        "website_url": "https://www.nortonloxley.com",
        "company_linkedin_url": "https://uk.linkedin.com/company/nortonloxley",
        "email": "sayhello@nortonloxley.com",
        "email_type": "generic",
        "email_confidence": "high",
        "email_source_url": "https://nortonloxley.com/services/",
        "linkedin_source_url": "https://uk.linkedin.com/company/nortonloxley",
        "estimated_headcount": "2-10",
        "headcount_source_url": "https://uk.linkedin.com/company/nortonloxley",
    },
    "Norton Loxley (Leeds)": {
        "website_url": "https://www.nortonloxley.com",
        "company_linkedin_url": "https://uk.linkedin.com/company/nortonloxley",
        "email": "sayhello@nortonloxley.com",
        "email_type": "generic",
        "email_confidence": "high",
        "email_source_url": "https://nortonloxley.com/services/",
        "linkedin_source_url": "https://uk.linkedin.com/company/nortonloxley",
        "estimated_headcount": "2-10",
        "headcount_source_url": "https://uk.linkedin.com/company/nortonloxley",
    },
    "Athena HR": {
        "website_url": "https://athena-hr.com/",
        "company_linkedin_url": "https://uk.linkedin.com/company/athena-hr",
        "decision_maker_name": "Denise Jennings",
        "decision_maker_linkedin_url": "https://uk.linkedin.com/in/denisejenningshr",
        "linkedin_source_url": "https://uk.linkedin.com/company/athena-hr",
        "estimated_headcount": "2-10",
        "headcount_source_url": "https://uk.linkedin.com/company/athena-hr",
    },
    "Culture Code | HR Consultant": {
        "website_url": "https://www.culture-code.co.uk/",
        "decision_maker_name": "Louise Demitriou",
        "decision_maker_role": "Founder",
        "email": "louise@culture-code.co.uk",
        "email_type": "named",
        "email_confidence": "high",
        "email_source_url": "https://www.culture-code.co.uk/",
    },
    "Gundog HR & Development": {
        "website_url": "https://gundoghrdevelopment.co.uk/",
        "decision_maker_name": "Simon",
        "email": "simon@gundoghrdevelopment.co.uk",
        "email_type": "named",
        "email_confidence": "high",
        "email_source_url": "https://www.york-professionals.co.uk/sectors/people/",
    },
    "Act HR Services & Consultancy Ltd": {
        "website_url": "https://www.acthr.co.uk/",
    },
    "Limelight HR": {
        "website_url": "https://limelighthr.co.uk/",
        "company_linkedin_url": "https://uk.linkedin.com/company/limelight-hr",
        "decision_maker_name": "Sally Bendtson",
        "decision_maker_role": "Founder",
        "decision_maker_linkedin_url": "https://uk.linkedin.com/in/sallybendtson",
        "email": "info@limelighthr.co.uk",
        "email_type": "generic",
        "email_confidence": "high",
        "email_source_url": "https://uk.linkedin.com/company/limelight-hr",
        "linkedin_source_url": "https://uk.linkedin.com/company/limelight-hr",
        "estimated_headcount": "2-10",
        "headcount_source_url": "https://uk.linkedin.com/company/limelight-hr",
    },
    "Candid HR": {
        "website_url": "https://www.candidhr.co.uk/",
        "company_linkedin_url": "https://uk.linkedin.com/company/candidhr",
        "decision_maker_name": "Emma Harvey",
        "email": "kelly@candidhr.com",
        "email_type": "named",
        "email_confidence": "medium",
        "email_source_url": "https://uk.linkedin.com/in/kelly-marks-132823185",
        "linkedin_source_url": "https://uk.linkedin.com/company/candidhr",
        "estimated_headcount": "2-10",
        "headcount_source_url": "https://uk.linkedin.com/company/candidhr",
    },
    "HR Dept Leeds South": {
        "website_url": "https://www.hrdept.co.uk/leeds-south",
        "company_linkedin_url": "https://www.linkedin.com/company/hr-dept-leeds-south",
        "decision_maker_name": "Sarah Bradley",
        "decision_maker_role": "Director",
        "linkedin_source_url": "https://www.linkedin.com/company/hr-dept-leeds-south",
        "estimated_headcount": "2-10",
        "headcount_source_url": "https://www.linkedin.com/company/hr-dept-leeds-south",
    },
    "Mint HR": {
        "website_url": "https://www.mint-hr.com/",
        "email": "tracy@mint-hr.com",
        "email_type": "named",
        "email_confidence": "high",
        "email_source_url": "https://www.mint-hr.com/location/wakefield/",
    },
    "HRoes": {
        "website_url": "https://www.hroes.co.uk",
        "company_linkedin_url": "https://uk.linkedin.com/company/hroes",
        "decision_maker_name": "Elissa Thursfield",
        "decision_maker_role": "Co-founder",
        "email": "hello@hroes.co.uk",
        "email_type": "generic",
        "email_confidence": "high",
        "email_source_url": "https://hroes.co.uk/wp-content/uploads/2024/12/Terms-and-Conditions-for-E-Learning.pdf",
        "linkedin_source_url": "https://uk.linkedin.com/company/hroes",
        "estimated_headcount": "11-50",
        "headcount_source_url": "https://uk.linkedin.com/company/hroes",
    },
    "apple HR support Ltd": {
        "website_url": "https://www.applehr.co.uk",
        "company_linkedin_url": "https://www.linkedin.com/company/apple-hr-support-ltd",
        "decision_maker_name": "Kate Appleyard",
        "decision_maker_role": "Founder",
        "decision_maker_linkedin_url": "https://uk.linkedin.com/in/kateappleyard",
        "email": "info@applehr.co.uk",
        "email_type": "generic",
        "email_confidence": "high",
        "email_source_url": "https://www.applehr.co.uk/about/",
        "linkedin_source_url": "https://uk.linkedin.com/in/kateappleyard",
        "estimated_headcount": "<10",
        "headcount_source_url": "https://open.endole.co.uk/insight/company/09728131-apple-hr-support-ltd",
    },
    "Aire Valley Consultancy Limited": {
        "website_url": "https://linktr.ee/airevalleyconsultancy",
        "decision_maker_name": "Angela Senior",
        "decision_maker_linkedin_url": "https://www.linkedin.com/in/angela-senior-avc",
        "linkedin_source_url": "https://bradfordbizfair.co.uk/aire-valley-consultancy/",
    },
    "The HR Dept Bradford": {
        "website_url": "https://www.hrdept.co.uk/bradford",
        "company_linkedin_url": "https://uk.linkedin.com/showcase/the-hr-dept-bradford/",
        "linkedin_source_url": "https://uk.linkedin.com/showcase/the-hr-dept-bradford/",
        "estimated_headcount": "11-50",
        "headcount_source_url": "https://uk.linkedin.com/showcase/the-hr-dept-bradford/",
    },
    "Positive People HR": {
        "website_url": "https://positivepeoplehr.co.uk/",
        "company_linkedin_url": "https://uk.linkedin.com/company/positive-people-hr",
        "email": "info@positivepeoplehr.co.uk",
        "email_type": "generic",
        "email_confidence": "high",
        "email_source_url": "https://positivepeoplehr.co.uk/contact-us/",
        "linkedin_source_url": "https://uk.linkedin.com/company/positive-people-hr",
        "estimated_headcount": "2-10",
        "headcount_source_url": "https://uk.linkedin.com/company/positive-people-hr",
    },
    "Optimal HR Services": {
        "website_url": "https://www.optimaloutsourcing.co.uk",
    },
    "FusionHR": {
        "website_url": "https://www.fusionbusiness.org.uk",
        "company_linkedin_url": "https://uk.linkedin.com/company/fusion-business-solutions-limited",
        "email": "queries@fusionbusiness.org.uk",
        "email_type": "generic",
        "email_confidence": "medium",
        "email_source_url": "https://www.bizseek.co.uk/fusionhr-part-of-fusion-business-01924-827869",
        "linkedin_source_url": "https://uk.linkedin.com/company/fusion-business-solutions-limited",
        "estimated_headcount": "11-50",
        "headcount_source_url": "https://uk.linkedin.com/company/fusion-business-solutions-limited",
    },
    "Black Kat HR Ltd": {
        "website_url": "https://blackkat-hr.com/",
        "company_linkedin_url": "https://uk.linkedin.com/company/black-kat-hr",
        "decision_maker_name": "Kat Derbyshire",
        "decision_maker_role": "Owner",
        "decision_maker_linkedin_url": "https://uk.linkedin.com/in/kat-derbyshire",
        "linkedin_source_url": "https://uk.linkedin.com/company/black-kat-hr",
        "estimated_headcount": "2-10",
        "headcount_source_url": "https://uk.linkedin.com/company/black-kat-hr",
    },
    "Sapphire HR": {
        "website_url": "https://www.sapphire-hr.co.uk",
        "company_linkedin_url": "https://uk.linkedin.com/company/sapphire-hr",
        "linkedin_source_url": "https://uk.linkedin.com/company/sapphire-hr",
        "estimated_headcount": "2-10",
        "headcount_source_url": "https://uk.linkedin.com/company/sapphire-hr",
    },
    "face2faceHR Newcastle": {
        "website_url": "https://face2facehr.com/hr-consultant-newcastle/",
        "decision_maker_name": "Kathryn Rodgers",
        "decision_maker_linkedin_url": "https://uk.linkedin.com/in/krodgershr",
        "linkedin_source_url": "https://uk.linkedin.com/in/krodgershr",
    },
    "Iona HR Consulting": {
        "website_url": "https://www.ionahr.co.uk",
        "company_linkedin_url": "https://uk.linkedin.com/company/iona-hr-consulting",
        "decision_maker_name": "Lisa Thompson",
        "decision_maker_role": "Founder",
        "linkedin_source_url": "https://uk.linkedin.com/company/iona-hr-consulting",
        "estimated_headcount": "2-10",
        "headcount_source_url": "https://uk.linkedin.com/company/iona-hr-consulting",
    },
    "Holgate HR": {
        "website_url": "https://www.holgatehr.co.uk",
        "company_linkedin_url": "https://uk.linkedin.com/company/holgate-hr",
        "decision_maker_name": "Andy Holgate",
        "decision_maker_linkedin_url": "https://uk.linkedin.com/in/andy-holgate-holgatehr",
        "email": "info@holgatehr.co.uk",
        "email_type": "generic",
        "email_confidence": "high",
        "email_source_url": "https://holgatehr.co.uk/contact",
        "linkedin_source_url": "https://uk.linkedin.com/company/holgate-hr",
        "estimated_headcount": "2-10",
        "headcount_source_url": "https://uk.linkedin.com/company/holgate-hr",
    },
    "The HR Dept Newcastle & Durham North": {
        "website_url": "https://www.hrdept.co.uk/newcastle-durham-northumberland-north/who-we-are/",
        "decision_maker_name": "Diane MacTavish",
        "decision_maker_role": "Director",
        "email": "diane.mactavish@hrdept.co.uk",
        "email_type": "named",
        "email_confidence": "high",
        "email_source_url": "https://www.hrdept.co.uk/newcastle-durham-northumberland-north/who-we-are/",
    },
    "Phoenix HR Consulting Ltd": {
        "website_url": "https://phoenix-hr.co.uk/",
    },
    "HR Dept - Durham & Newcastle South": {
        "website_url": "https://www.hrdept.co.uk/durham-newcastle-south/who-we-are",
        "decision_maker_name": "Alison Schreiber",
        "decision_maker_role": "Director",
    },
    "Cultura HR": {
        "website_url": "https://culturahr.co.uk/",
        "decision_maker_name": "Deb Tweedy",
        "decision_maker_linkedin_url": "https://uk.linkedin.com/in/deb-tweedy-76764961",
        "linkedin_source_url": "https://uk.linkedin.com/in/deb-tweedy-76764961",
    },
    "Npa Human Resources Consultancy": {
        "website_url": "https://www.npahumanresources.co.uk/",
        "decision_maker_name": "Nazia Aftab",
        "decision_maker_role": "MD",
        "decision_maker_linkedin_url": "https://uk.linkedin.com/in/nazia-aftab-45318015",
        "linkedin_source_url": "https://uk.linkedin.com/in/nazia-aftab-45318015",
    },
    "HR Alchemy": {
        "website_url": "https://hralchemy.co.uk/",
        "company_linkedin_url": "https://uk.linkedin.com/company/hr-alchemy-limited",
        "decision_maker_name": "Jo Davies",
        "email": "hello@hralchemy.co.uk",
        "email_type": "generic",
        "email_confidence": "high",
        "email_source_url": "https://hralchemy.co.uk/contact/",
        "linkedin_source_url": "https://uk.linkedin.com/company/hr-alchemy-limited",
        "estimated_headcount": "2-10",
        "headcount_source_url": "https://uk.linkedin.com/company/hr-alchemy-limited",
    },
    "Trusted HR Ltd": {
        "website_url": "https://trustedhr.co.uk/",
        "company_linkedin_url": "https://uk.linkedin.com/company/trustedhrltd",
        "linkedin_source_url": "https://uk.linkedin.com/company/trustedhrltd",
        "estimated_headcount": "2-10",
        "headcount_source_url": "https://uk.linkedin.com/company/trustedhrltd",
    },
    "Sereniti": {
        "website_url": "https://www.sereniti.co.uk",
        "company_linkedin_url": "https://uk.linkedin.com/company/sereniti-ltd",
        "email": "info@sereniti.co.uk",
        "email_type": "generic",
        "email_confidence": "high",
        "email_source_url": "https://uk.linkedin.com/company/sereniti-ltd",
        "linkedin_source_url": "https://uk.linkedin.com/company/sereniti-ltd",
        "estimated_headcount": "11-50",
        "headcount_source_url": "https://uk.linkedin.com/company/sereniti-ltd",
    },
    "Your HR Partners": {
        "website_url": "https://yourhrpartners.co.uk/",
        "decision_maker_name": "Rebecca Naylor",
        "decision_maker_linkedin_url": "https://uk.linkedin.com/in/rebecca-naylor-a858bb91",
        "email": "info@yourhrpartners.co.uk",
        "email_type": "generic",
        "email_confidence": "high",
        "email_source_url": "https://yourhrpartners.co.uk/",
        "linkedin_source_url": "https://uk.linkedin.com/in/rebecca-naylor-a858bb91",
    },
    "Clover HR Manchester": {
        "website_url": "https://www.cloverhr.co.uk",
        "email": "info@cloverhr.co.uk",
        "email_type": "generic",
        "email_confidence": "high",
        "email_source_url": "https://www.cloverhr.co.uk/contact/",
    },
    "Peninsula HR (Manchester HQ)": {
        "website_url": "https://www.peninsulagrouplimited.com/services/hr-services-manchester/",
    },
    "Avensure HR & H&S": {
        "website_url": "https://www.avensure.com",
        "company_linkedin_url": "https://uk.linkedin.com/company/avensure-ltd",
        "linkedin_source_url": "https://uk.linkedin.com/company/avensure-ltd",
        "estimated_headcount": "51-200",
        "headcount_source_url": "https://uk.linkedin.com/company/avensure-ltd",
    },
    "ComplexHR": {
        "website_url": "https://www.complexhr.co.uk",
        "company_linkedin_url": "https://uk.linkedin.com/company/complex-hr",
        "email": "helen@complexhr.co.uk",
        "email_type": "named",
        "email_confidence": "high",
        "email_source_url": "https://uk.linkedin.com/company/complex-hr",
        "linkedin_source_url": "https://uk.linkedin.com/company/complex-hr",
        "estimated_headcount": "2-10",
        "headcount_source_url": "https://uk.linkedin.com/company/complex-hr",
    },
    "Cornerstone Resources": {
        "website_url": "https://www.cornerstoneresources.co.uk",
        "company_linkedin_url": "https://uk.linkedin.com/company/cornerstoneresources",
        "email": "hello@cornerstoneresources.co.uk",
        "email_type": "generic",
        "email_confidence": "high",
        "email_source_url": "https://cornerstoneresources.co.uk/",
        "linkedin_source_url": "https://uk.linkedin.com/company/cornerstoneresources",
        "estimated_headcount": "11-50",
        "headcount_source_url": "https://uk.linkedin.com/company/cornerstoneresources",
    },
    "Solutions for HR": {
        "website_url": "https://www.solutionsforhr.co.uk",
        "company_linkedin_url": "https://uk.linkedin.com/company/solutions-for-hr",
        "email": "advice@solutionsforhr.co.uk",
        "email_type": "generic",
        "email_confidence": "high",
        "email_source_url": "https://www.solutionsforhr.co.uk/contact/",
        "linkedin_source_url": "https://uk.linkedin.com/company/solutions-for-hr",
        "estimated_headcount": "2-10",
        "headcount_source_url": "https://uk.linkedin.com/company/solutions-for-hr",
    },
    "PeoplePointHR": {
        "website_url": "https://peoplepointhr.co.uk",
        "email": "Enquiries@PeoplePointHR.co.uk",
        "email_type": "generic",
        "email_confidence": "medium",
        "email_source_url": "https://www.trustpilot.com/review/peoplepointhr.co.uk",
    },
    "HR Dept York & North Yorkshire": {
        "website_url": "https://www.hrdept.co.uk",
    },
    "Clarity HR": {
        "website_url": "https://www.clarityhrconsultancy.co.uk/",
    },
    "Affinity HR": {
        "website_url": "https://affinity-hr.co.uk/",
    },
}


def score_priority(row: dict[str, str]) -> tuple[str, str]:
    score = 0
    if row.get("segment"):
        score += 25
    if row.get("city_region"):
        score += 15
    if row.get("estimated_headcount"):
        score += 15
    if row.get("decision_maker_name"):
        score += 15 if row.get("decision_maker_role") else 10
    if row.get("notes") or row.get("subtype"):
        score += 15
    if row.get("email") and (row.get("company_linkedin_url") or row.get("decision_maker_linkedin_url")):
        score += 15
    elif row.get("email") or row.get("company_linkedin_url") or row.get("decision_maker_linkedin_url"):
        score += 10
    elif row.get("website_url"):
        score += 5

    score = min(score, 100)
    if score >= 80:
        priority = "high"
    elif score >= 60:
        priority = "medium"
    elif score >= 40:
        priority = "low"
    else:
        priority = "park"
    return str(score), priority


def main() -> None:
    init_sentry("daily-enrichment-known-values")
    with PROSPECTS_PATH.open(newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))

    updated_rows = 0
    updated_fields = 0

    for row in rows:
        enrichment = ENRICHMENTS.get(row["company_name"])
        if not enrichment:
            continue

        changed = False
        for field, value in enrichment.items():
            if value and not row.get(field):
                row[field] = value
                changed = True
                updated_fields += 1

        if changed:
            row["last_researched_at"] = TODAY
            row["fit_score"], row["priority"] = score_priority(row)
            if row.get("website_url") and (row.get("email") or row.get("company_linkedin_url") or row.get("decision_maker_linkedin_url")):
                row["status"] = "ready_to_review"
            elif row.get("website_url"):
                row["status"] = "enriched"
            updated_rows += 1

    with PROSPECTS_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Updated {updated_rows} rows; filled {updated_fields} fields.")


if __name__ == "__main__":
    main()
