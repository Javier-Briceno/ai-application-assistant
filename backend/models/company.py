from pydantic import BaseModel


class CompanyExtractorOutput(BaseModel):
    company_name: str | None = None
    search_name: str | None = None
    job_city: str | None = None


class CompanyResearchResult(BaseModel):
    """Final output of the company research pipeline, fed into Analyzer and Anschreiben."""
    company_name: str = ""
    search_name: str = ""
    company_profile: str = ""
    company_address: str = ""
