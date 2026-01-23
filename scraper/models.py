# Copyright (C) 2026 swanserquack
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

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
    description: str
    aims: str

class CourseList(BaseModel):
    """
    This is what should be output from the course list method.
    everything is implied to be Required[] so it does not need to be
    explicitly stated
    """
    name: str
    course_code: str
    url: str