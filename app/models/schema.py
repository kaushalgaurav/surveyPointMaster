# from typing import List, Optional
# from pydantic import BaseModel, Field

# class SectorDetail(BaseModel):
#     sector_name: str = Field(..., alias="Sector Name")
#     # Curl mein 'reference' bhej rahe hain toh yahan wahi alias rakhein
#     reference: str = Field(..., alias="reference") 
#     description: Optional[str] = "General survey"
#     no_of_questions: int = 15
#     survey_type: Optional[str] = Field(None, alias="survey_type")
#     section_name: Optional[str] = Field(None, alias="section name")
#     section_qprefix: Optional[str] = Field(None, alias="section question prefix")
#     suggestion: Optional[List[str]]= Field(None, alias="List of Suggestion")

#     class Config:
#         populate_by_name = True

#     def with_survey_result(self, survey_result: dict) -> dict:
#         """Merge sector metadata with generated Section/Data for API response."""
#         return {**self.dict(by_alias=True, exclude_none=True), **survey_result}

# class SurveyRequest(BaseModel):
#     languages: List[str]
#     num_sectors: int
#     sectors: List[SectorDetail]
#     index: Optional[int] = 0

from typing import List, Optional
from pydantic import BaseModel, Field

class SectorDetail(BaseModel):
    sector_name: str = Field(..., alias="Sector Name")
    # Curl mein 'reference' bhej rahe hain toh yahan wahi alias rakhein
    reference: str = Field(..., alias="reference")
    description: Optional[str] = "General survey"
    no_of_questions: int = 15
    survey_type: Optional[str] = None
    section_name: Optional[str] = None
    section_qprefix: Optional[str] = None
    suggestion: Optional[List[str]] = None

    class Config:
        populate_by_name = True
        allow_population_by_field_name = True

class SurveyRequest(BaseModel):
    languages: List[str]
    num_sectors: int
    sectors: List[SectorDetail]
    index: Optional[int] = 0