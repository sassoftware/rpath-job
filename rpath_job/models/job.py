
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

class HistoryEntry(generateds_job.historyEntryType):
    def __init__(self, content, timestamp = None):
        if isinstance(timestamp, float):
            timestamp = "%.3f" % timestamp
        generateds_job.historyEntryType.__init__(self, content=content,
            timestamp=timestamp)
