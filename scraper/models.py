"""
This module defines the data structures (TypedDicts) used across the scraping application
to ensure a consistent format for course information.
"""
from pydantic import BaseModel

class CourseData(BaseModel):
    """
    This is our base output format, the 'standard' if you want
    every university should output this data
    this allows for easy later additions to the output data
    everything is implied to be Required[] so it does not need to be
    explicitly stated
    """
    name: str
    course_code: str
    semester: str
    aims: str
    ilos: str

class CourseList(BaseModel):
    """
    This is what should be output from the course list method.
    everything is implied to be Required[] so it does not need to be
    explicitly stated
    """
    name: str
    course_code: str
    url: str