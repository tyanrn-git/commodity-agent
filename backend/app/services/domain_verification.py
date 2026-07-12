import re
from urllib.parse import urlparse


def extract_domain(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip().lower()
    if "@" in value:
        value = value.split("@", 1)[1]
    if "://" in value:
        value = urlparse(value).netloc or value.split("://", 1)[1]
    value = value.split("/", 1)[0]
    value = value.split(":", 1)[0]
    if value.startswith("www."):
        value = value[4:]
    return value or None


def domains_match(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    return extract_domain(left) == extract_domain(right)


def check_mx_records(domain: str) -> dict:
    domain = extract_domain(domain)
    if not domain:
        return {"domain": domain, "mx_valid": False, "mx_hosts": [], "error": "invalid_domain"}

    try:
        import dns.resolver

        answers = dns.resolver.resolve(domain, "MX")
        hosts = sorted(str(r.exchange).rstrip(".") for r in answers)
        return {"domain": domain, "mx_valid": len(hosts) > 0, "mx_hosts": hosts, "error": None}
    except Exception as exc:
        return {"domain": domain, "mx_valid": False, "mx_hosts": [], "error": str(exc)}


def verify_counterparty_domain(
    *,
    primary_domain: str | None,
    website: str | None,
    contact_email: str | None = None,
) -> dict:
    declared_domain = extract_domain(primary_domain) or extract_domain(website)
    website_domain = extract_domain(website)
    email_domain = extract_domain(contact_email)

    mx_report = check_mx_records(declared_domain) if declared_domain else {
        "domain": None,
        "mx_valid": False,
        "mx_hosts": [],
        "error": "no_domain",
    }

    website_matches = domains_match(declared_domain, website_domain) if website_domain else None
    email_matches = domains_match(declared_domain, email_domain) if email_domain else None

    checks = {
        "declared_domain": declared_domain,
        "website_domain": website_domain,
        "email_domain": email_domain,
        "mx": mx_report,
        "website_domain_matches": website_matches,
        "email_domain_matches": email_matches,
    }

    auto_pass = bool(
        declared_domain
        and mx_report.get("mx_valid")
        and (website_matches is not False)
        and (email_matches is not False if email_domain else True)
    )
    checks["ready_for_user_confirmation"] = auto_pass
    return checks
