#
# Copyright (c) SAS Institute Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


import generateds_job
from generateds_base import Base

class Job(generateds_job.jobType, Base):
    defaultNamespace = "http://www.rpath.com/permanent/jobs/job-1.0.xsd"
    xmlSchemaLocation = defaultNamespace
    RootNode = 'job'

    def setErrorResponse(self, faultCode, faultString, tracebackData=None,
                         productCodeData=None):
        fault = generateds_job.faultType()
        fault.set_code(faultCode)
        fault.set_message(faultString)
        if tracebackData is not None:
            fault.set_traceback(tracebackData)
        if productCodeData is not None:
            productCode = generateds_job.productCodeType()
            productCode.setAnyAttributes_(productCodeData)
            fault.set_productCode(productCode)
        errorResponse = generateds_job.errorType(fault = fault)
        self.set_errorResponse(errorResponse)

class Jobs(generateds_job.jobsType, Base):
    defaultNamespace = "http://www.rpath.com/permanent/jobs/job-1.0.xsd"
    xmlSchemaLocation = defaultNamespace
    RootNode = 'jobs'

    def addJobs(self, jobs):
        self.set_job(jobs)

    def __iter__(self):
        return self.job.__iter__()

ResultResource = generateds_job.resultResourceType
System = generateds_job.systemType

class HistoryEntry(generateds_job.historyEntryType):
    def __init__(self, content, timestamp = None):
        if isinstance(timestamp, float):
            timestamp = "%.3f" % timestamp
        generateds_job.historyEntryType.__init__(self, content=content,
            timestamp=timestamp)
