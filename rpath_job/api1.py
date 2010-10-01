#!/usr/bin/python2.4
#
# Copyright (c) 2009-2010 rPath, Inc.
#

import os
import sys
import time

from rpath_storage import api1 as storage

from rpath_job.models import job as jobmodels

HistoryEntry = jobmodels.HistoryEntry
ResultResource = jobmodels.ResultResource

class Field(object):
    @classmethod
    def fromString(cls, value):
        if value is None:
            return ''
        return value

    @classmethod
    def toString(cls, value):
        if value is None:
            return None
        return str(value)

class FieldString(Field):
    pass

class FieldTimestamp(Field):
    @classmethod
    def fromString(cls, value):
        if value is None or value == '':
            return None
        return float(value)

    @classmethod
    def toString(cls, value):
        if value is None:
            return None
        return "%.3f" % value

class FieldInteger(Field):
    @classmethod
    def fromString(cls, value):
        if value is None or value == '':
            return None
        return int(value)

    @classmethod
    def toString(cls, value):
        if value is None:
            return None
        return "%d" % value

class BaseJob(object):
    __slots__ = [ 'id', 'jobId', '_store', '_fields', '_commitAfterChange',
        '_readOnly']
    _fieldTypes = dict(
        createdBy = FieldString,
        type = FieldString,
        status = FieldString,
        message = FieldString,
        created = FieldTimestamp,
        modified = FieldTimestamp,
        expiration = FieldTimestamp,
        ttl = FieldInteger,
        # Result, if the job's status is COMPLETED. Multiple results may be
        # supported, they are saved newline-separated.
        result = FieldString,
        # Error response, if the job's status is FAILED.
        errorResponse = FieldString,
        pid = FieldInteger,
        restUri = FieldString,
        restMethod = FieldString,
        restArgs = FieldString,
    )
    _defaultTTL = 7200
    _DEFAULT = object()
    STATUS_QUEUED = "Queued"
    STATUS_RUNNING = "Running"
    STATUS_FAILED = "Failed"
    STATUS_COMPLETED = "Completed"

    def __init__(self, store, jobId, **kwargs):
        self._readOnly = kwargs.pop('readOnly', False)
        self._commitAfterChange = kwargs.pop('commitAfterChange', False)
        self._store = store
        self._fields = dict()
        self.id = store._sanitizeKey(jobId)
        self.jobId = store._extractId(self.id)
        self._load(**kwargs)

    def _loadDefaults(self, toSet):
        now = self._getCurrentTimestamp()
        modified = toSet.get('modified', self._fields.get('modified'))
        if modified is None:
            modified = toSet['modified'] = now
        ttl = toSet.get('ttl', self._fields.get('ttl'))
        if ttl is None:
            ttl = self._defaultTTL
            if ttl is not None:
                toSet['ttl'] = ttl
        expiration = toSet.get('expiration', self._fields.get('expiration'))
        if ttl is not None and 'expiration' not in toSet:
            # Is there an expiration in the persisted instance?
            expiration = self._fields.get('expiration')
            if expiration is None or expiration != modified + ttl:
                toSet['expiration'] = modified + ttl
        fieldMap = [ ('created', now), ('status', self.STATUS_QUEUED),
            ('message', '') ]
        for fieldName, newVal in fieldMap:
            if toSet.get(fieldName, self._fields.get(fieldName)) is None:
                toSet[fieldName] = newVal
        return toSet

    def setStatus(self, status):
        self._set('status', status)

    def updateModified(self):
        self.setFields(self._updateModified())

    def commit(self):
        self._store.commit()

    def _load(self, **kwargs):
        toSet = dict()
        for fname, ftype in self._fieldTypes.items():
            # Load value from the database
            fval = self._getField(fname, ftype)
            self._fields[fname] = fval
            kwval = kwargs.get(fname, None)
            if kwval is not None:
                # Only set it if the provided value has changed
                nval = ftype.fromString(kwval)
                if fval != nval:
                    toSet[fname] = kwval
        if self._readOnly:
            return
        self._loadDefaults(toSet)
        self.setFields(toSet.items())

    def setFields(self, fieldVals, updateModified = True):
        if self._readOnly:
            return
        if isinstance(fieldVals, dict):
            fieldVals = fieldVals.iteritems()
        toSet = dict()
        for fname, fval in fieldVals:
            if isinstance(fname, tuple):
                fname = fname[-1]
            if fname not in self._fieldTypes:
                continue
            ftype = self._fieldTypes[fname]
            val = ftype.fromString(fval)
            self._fields[fname] = val
            if val is not None:
                # Convert it back to string
                val = ftype.toString(val)
            toSet[(self.id, fname)] = val
        if toSet and updateModified and (self.id, 'modified') not in toSet:
            self._updateModified(toSet)
        self._store.setFields(toSet.items())
        if toSet and self._commitAfterChange:
            self._store.commit()

    def _getField(self, field, fieldType, default = _DEFAULT):
        if default is self._DEFAULT:
            default = None
        value = self._store.get((self.id, field), default = default)
        if value is None:
            if field == 'result':
                return []
            return None
        if value and field == 'result':
            if isinstance(value, basestring):
                return value.split('\n')
            return value
        return fieldType.fromString(value)

    def _deleteField(self, field):
        return self._store.delete((self.id, field))

    def _set(self, field, value, updateModified = True):
        toSet = {field : value}
        if field != 'modified' and updateModified:
            self._updateModified(toSet)
        elif field == 'modified':
            self._addExpiration(value, toSet)
        self.setFields(toSet)
        return value

    def _addExpiration(self, modified, toSet):
        ttl = toSet.get('ttl', self._fields.get('ttl'))
        if ttl is None:
            return
        toSet[(self.id, 'expiration')] = modified + ttl

    def _updateModified(self, toSet = None):
        modified = self._getCurrentTimestamp()
        if toSet is None:
            toSet = {}
        toSet[(self.id, 'modified')] = modified
        self._addExpiration(modified, toSet)
        return toSet

    @classmethod
    def _getCurrentTimestamp(cls):
        return float("%.3f" % time.time())

    def _get(self, field, default = _DEFAULT):
        ftype = self._fieldTypes.get(field)
        if ftype is None:
            if default is self._DEFAULT:
                raise AttributeError(field)
            return default
        if default is self._DEFAULT:
            default = None
        return self._fields.get(field, default)

    def __getattr__(self, field):
        return self._get(field)

    def __setattr__(self, field, value):
        if field in self._fieldTypes:
            return self._set(field, value)
        return object.__setattr__(self, field, value)

class HistoryBaseJob(BaseJob):
    __slots__ = [ '_history' ]
    historyEntryClass = jobmodels.HistoryEntry

    def __init__(self, *args, **kwargs):
        BaseJob.__init__(self, *args, **kwargs)
        self._history = []
        self._readHistory()

    def _getHistory(self):
        return sorted(self._history, key = lambda x: x.timestamp)

    def addHistoryEntry(self, entry):
        if isinstance(entry, basestring):
            entry = self.historyEntryClass(entry)
        self._history.append(entry)
        timestamp = entry.timestamp
        if timestamp is None:
            timestamp = self._getCurrentTimestamp()
        if isinstance(timestamp, float):
            timestamp = "%.3f" % timestamp
        self._store.writeHistoryEntry(self.id, timestamp, entry.content)
        self.updateModified()

    def addResults(self, entries):
        self._store.addResults(self.id, entries)
        self.updateModified()

    def getResults(self):
        return self._store.getResults(self.id)

    history = property(_getHistory)

    def _readHistory(self):
        del self._history[:]
        self._history.extend(self.historyEntryClass(data, ts)
            for data, ts in self._store.enumerateHistory(self.id))

class DiskStorage(storage.DiskStorage):
    def enumerateHistory(self, jobId):
        for ts in self.enumerate((jobId, "history")):
            yield self.get(ts), os.path.basename(ts)

    def writeHistoryEntry(self, jobId, timestamp, content):
        self.set((jobId, "history", timestamp), content)

    def _extractId(self, key):
        if not isinstance(key, basestring):
            raise InvalidKeyError(key)
        # Preserve type if present
        return '/'.join(key.split('/')[-2:])

    def addResults(self, jobId, results):
        oldResults = self.getResults(jobId)
        oldResults.extend(results)
        return self.set((jobId, "result"), "\n".join(oldResults))

    def getResults(self, jobId):
        results = self.get((jobId, "result"))
        if not results:
            results = []
        else:
            results = results.split('\n')
        return results

class JobStore(object):
    __slots__ = [ '_store' ]

    storageFactory = DiskStorage
    jobFactory = BaseJob
    jobType = None

    _storageSubdir = "jobs"

    def __init__(self, storePath):
        self._store = self.storageFactory(storage.StorageConfig(
            os.path.join(storePath, self._storageSubdir)))

    def create(self, **kwargs):
        """Create a new job"""
        if kwargs.get('modified') is None:
            modified = kwargs['modified'] = time.time()
        if kwargs.get('created') is None:
            kwargs['created'] = modified
        jobType = self.jobType
        kwargs['type'] = jobType
        jobId = self._newJob(kwargs)
        job = self.jobFactory(self._store, jobId, **kwargs)
        return job

    def get(self, jobId, commitAfterChange=False, readOnly=False):
        store = self._store
        jobId = self._store._extractId(jobId)
        if not store.exists(jobId):
            return None
        job = self.jobFactory(store, jobId, commitAfterChange=commitAfterChange,
            readOnly=readOnly)
        return job

    def enumerate(self, readOnly=False):
        """Emumerate available jobs"""
        now = time.time()
        store = self._store
        for job in self._enumerate(self.jobType, readOnly=readOnly):
            if job.expiration is not None and job.expiration < now:
                store.delete(job.id)
                continue
            yield job

    def commit(self):
        self._store.commit()

    def _newJob(self, kvdict):
        jobType = kvdict.get('type')
        jobId = self._store.newCollection(keyPrefix = jobType)
        return jobId

    def _enumerate(self, jobType, readOnly=False):
        jobIds = self._store.enumerate(keyPrefix = self.jobType)
        for jobId in jobIds:
            job = self.get(jobId, readOnly=readOnly)
            if job is None:
                # Race condition, the job went away after we enumerated it
                continue
            yield job

class SQLBacking(object):
    __slots__ = [ '_db', '_jobTypes', '_jobStates', '_jobsCache',
        '_restMethods',  ]
    extra_fields = ""
    extra_joins = ""
    extra_fields_insert = []

    _fieldMap = dict(restUri = 'rest_uri', restArgs = 'rest_args',
        errorResponse = 'error_response')

    def __init__(self, db):
        self._db = db
        self.initCaches()

    def initCaches(self):
        self._jobTypes = None
        self._jobStates = None
        self._jobsCache = {}
        self._restMethods = None

    def newCollection(self, kvdict):
        cu = self._db.cursor()
        jobType = kvdict['type']
        jobTypeId = self.jobTypes[jobType]
        jobStateId = self.jobStates['Queued']
        now = time.time()
        created = kvdict.setdefault('created', now)
        modified = kvdict.setdefault('modified', now)
        ttl = kvdict.setdefault('ttl', None)
        if ttl:
            expiration = modified + ttl
        else:
            expiration = None

        extraCreateArgs = self._extraCreateArgs(kvdict)
        args = (jobTypeId, jobStateId, self._db.auth.userId, created,
            modified, expiration, ttl) + extraCreateArgs
        assert len(self.extra_fields_insert) == len(extraCreateArgs)
        if self.extra_fields_insert:
            extra_fields = ", " + ', '.join(self.extra_fields_insert)
            extra_bind_args = ", " + ', '.join('?'
                for x in self.extra_fields_insert)
        else:
            extra_fields = ""
            extra_bind_args = ""
        sql = """
            INSERT INTO jobs
                (job_type_id, job_state_id, created_by, created,
                modified, expiration, ttl%(extra_fields)s)
            VALUES (?, ?, ?, ?, ?, ?, ?%(extra_bind_args)s)""" % dict(
                extra_fields = extra_fields,
                extra_bind_args = extra_bind_args)
        cu.execute(sql, *args)
        jobId = cu.lastid()
        self._postNewCollection(jobId, kvdict)
        return jobId

    def exists(self, jobId):
        jobDict = self._getJob(jobId)
        return jobDict is not None

    def get(self, (key, field), default = None):
        jobDict = self._getJob(key)
        if jobDict is None:
            return None
        return jobDict[field]

    def set(self, (key, field), value):
        return self.setFields([ ((key, field), value) ])

    def delete(self, val):
        if isinstance(val, tuple):
            # Removing specific field
            return self.setFields([ (val, None) ])
        # XXX job removal will have to be thought out, to avoid deadlocks
        return
        cu = self._db.cursor()
        cu.execute("DELETE FROM jobs WHERE job_id = ?", val)

    def setFields(self, kvlist):
        entries = {}
        for (keyId, field), value in kvlist:
            entries.setdefault(keyId, {})[field] = value
        for jobId, kvdict in entries.items():
            jobDict = self._getJob(jobId)
            if jobDict is None:
                raise Exception
            updates = []
            for fname, fval in kvdict.items():
                jobDict[fname] = fval
                if fname in ['cloudName', 'cloudType']:
                    # You can't change these
                    continue
                if fname == 'status':
                    fname = 'job_state_id'
                    fval = self.jobStates[fval]
                if fname == 'type':
                    fname = 'job_type_id'
                    fval = self.jobTypes[fval]
                if fname == 'restMethod':
                    fname = 'rest_method_id'
                    fval = self.restMethods[fval]
                if fname in self._fieldMap:
                    fname = self._fieldMap[fname]
                updates.append((fname, fval))
            if not updates:
                continue
            cu = self._db.cursor()
            sql = "UPDATE jobs SET %s WHERE job_id = ?"
            sql = sql % ', '.join("%s=?" % x[0] for x in updates)
            uvals = [ x[1] for x in updates ]
            uvals.append(jobId)
            cu.execute(sql, *uvals)
        return entries

    def enumerate(self, keyPrefix):
        self._jobsCache.clear()
        cu = self._getJobsCursor(jobType = keyPrefix)
        jobIds = []
        while 1:
            d = cu.fetchone_dict()
            if d is None or d == {}:
                break
            jobId = d['id']
            d['result'] = self.getResults(jobId)
            self._jobsCache[jobId] = d
            jobIds.append(jobId)
        return sorted(jobIds)

    def _sanitizeKey(self, key):
        if isinstance(key, (int, long)):
            return key
        return int(os.path.basename(key))

    _extractId = _sanitizeKey

    @property
    def jobStates(self):
        if self._jobStates is None:
            cu = self._db.cursor()
            cu.execute("SELECT name, job_state_id FROM job_states")
            self._jobStates = dict(cu)
        return self._jobStates

    @property
    def jobTypes(self):
        if self._jobTypes is None:
            cu = self._db.cursor()
            cu.execute("SELECT name, job_type_id FROM job_types")
            self._jobTypes = dict(cu)
        return self._jobTypes

    @property
    def restMethods(self):
        if self._restMethods is None:
            cu = self._db.cursor()
            cu.execute("SELECT name, rest_method_id FROM rest_methods")
            self._restMethods = dict(cu)
        return self._restMethods

    def _getJobsCursor(self, jobId = None, jobType = None):
        now = time.time()
        args = ( now, )
        if jobId is None:
            whereClause = "AND job_types.name = ?"
            args += (jobType, )
        else:
            whereClause = "AND jobs.job_id = ?"
            args += (jobId, )
        sql = """
            SELECT jobs.job_id AS id,
                   jobs.job_id AS jobId,
                   jobs.created,
                   jobs.modified,
                   jobs.ttl,
                   jobs.pid,
                   rest_methods.name AS restMethod,
                   jobs.rest_uri as restUri,
                   jobs.rest_args as restArgs,
                   jobs.expiration,
                   jobs.message,
                   jobs.error_response AS errorResponse,
                   Users.username AS createdBy,
                   job_types.name AS type,
                   job_states.name AS status%(extra_fields)s
              FROM jobs
              JOIN job_states USING (job_state_id)
              JOIN job_types ON (jobs.job_type_id = job_types.job_type_id)
              JOIN Users ON (jobs.created_by = Users.userId)
              LEFT JOIN rest_methods ON
                    (jobs.rest_method_id = rest_methods.rest_method_id)
              %(extra_joins)s
              WHERE jobs.expiration IS NULL OR jobs.expiration >= ?
              %(where_clause)s""" % dict(
                extra_fields = self.extra_fields,
                extra_joins = self.extra_joins,
                where_clause = whereClause)
        cu = self._db.cursor()
        cu.execute(sql, *args)
        return cu

    def _getJob(self, jobId):
        if jobId in self._jobsCache:
            return self._jobsCache[jobId]
        cu = self._getJobsCursor(jobId)
        # fetchone_dict returns an empty dict if no data is found
        d = cu.fetchone_dict() or None
        if d is not None:
            d['result'] = self.getResults(jobId)
            d['history'] = self.enumerateHistory(jobId)
        self._jobsCache[jobId] = d
        # Returns None if not found
        return d

    def getResults(self, jobId):
        sql = """
            SELECT data
              FROM job_results
             WHERE job_id = ?
             ORDER BY job_result_id
        """
        cu = self._db.cursor()
        cu.execute(sql, jobId)
        return [ x[0] for x in cu ]

    def addResults(self, jobId, entries):
        sql = "INSERT INTO job_results (job_id, data) VALUES (?, ?)"
        cu = self._db.cursor()
        data = [ (jobId, entry.encode('ascii')) for entry in entries ]
        cu.executemany(sql, data)
        self._invalidateCache(jobId)

    def enumerateHistory(self, jobId):
        sql = """
            SELECT content, timestamp
              FROM job_history
             WHERE job_id = ?
             ORDER BY timestamp
        """
        cu = self._db.cursor()
        cu.execute(sql, jobId)
        return [ x for x in cu ]

    def writeHistoryEntry(self, jobId, timestamp, content):
        sql = """INSERT into job_history (job_id, timestamp, content)
            VALUES (?, ?, ?)"""
        cu = self._db.cursor()
        cu.execute(sql, jobId, timestamp, content)
        self._invalidateCache(jobId)

    def commit(self):
        self._jobsCache.clear()
        self._db.commit()

    def _extraCreateArgs(self, kvdict):
        return ()

    def _postNewCollection(self, jobId, kvdict):
        pass

    def _invalidateCache(self, jobId):
        self._jobsCache.pop(jobId, None)

class TargetSqlBacking(SQLBacking):
    __slots__ = [ '_targetsCache' ]

    extra_fields = ", Targets.targetType AS cloudType, Targets.targetName AS cloudName, inventory_system_job.system_id AS system"
    extra_joins = """JOIN job_target ON (jobs.job_id = job_target.job_id)
              JOIN Targets ON (job_target.targetId = Targets.targetId)
              LEFT OUTER JOIN inventory_system_job ON (inventory_system_job.job_id = jobs.job_id)"""
    extra_fields_insert = []

    def initCaches(self):
        SQLBacking.initCaches(self)
        self._targetsCache = None

    def _postNewCollection(self, jobId, kvdict):
        cloudType = kvdict['cloudType']
        cloudName = kvdict['cloudName']
        targetId = self.targets[(cloudType, cloudName)]
        cu = self._db.cursor()
        cu.execute("INSERT INTO job_target (job_id, targetId) VALUES (?,?)",
            jobId, targetId)

    @property
    def targets(self):
        if self._targetsCache is None:
            cu = self._db.cursor()
            cu.execute("""
                SELECT targetType, targetName, targetId
                  FROM Targets""")
            self._targetsCache = dict(((x[0], x[1]), x[2])
                for x in cu)
        return self._targetsCache

    def setFields(self, kvlist):
        entries = {}
        for (keyId, field), value in kvlist:
            entries.setdefault(keyId, {})[field] = value
        for jobId, kvdict in entries.items():
            system_id = kvdict.get('system', None)
            if kvdict.has_key('system'):
                index = kvlist.index(((jobId, 'system'), system_id))
                kvlist.pop(index)
            if system_id:
                eventUuid = str(uuid.uuid4())
                cu = self._db.cursor()
                cu.execute("INSERT INTO inventory_system_job "
                    "(job_id, system_id, event_uuid) "
                    "VALUES (?, ?)", jobId, system_id, eventUuid)
        SQLBacking.setFields(self, kvlist)

class ManagedSystemsSqlBacking(TargetSqlBacking):
    __slots__ = []

    extra_fields = TargetSqlBacking.extra_fields + """, inventory_system_target.target_system_id AS instanceId"""
    extra_joins = """ JOIN job_managed_system
                    ON (jobs.job_id = job_managed_system.job_id)
              JOIN inventory_system_target
                    ON (job_managed_system.managed_system_id = inventory_system_target.managed_system_id)
              JOIN Targets ON (inventory_system_target.target_id = Targets.targetId)
              LEFT OUTER JOIN inventory_system_job 
                ON (inventory_system_job.job_id = jobs.job_id)"""

    def _postNewCollection(self, jobId, kvdict):
        cloudType = kvdict['cloudType']
        cloudName = kvdict['cloudName']
        instanceId = kvdict['instanceId']
        targetId = self.targets[(cloudType, cloudName)]
        cu = self._db.cursor()
        cu.execute("""SELECT managed_system_id FROM inventory_system_target
            WHERE target_id = ? AND target_system_id = ?""", targetId, instanceId)
        row = cu.fetchone()
        managedSystemId = row[0]

        cu.execute("INSERT INTO job_managed_system (job_id, managed_system_id) VALUES (?,?)",
            jobId, managedSystemId)

class SqlJobStore(JobStore):
    __slots__ = [ '_store' ]
    BackingStore = SQLBacking

    def __init__(self, db):
        self._store = self.BackingStore(db)

    def _newJob(self, kvdict):
        jobId = self._store.newCollection(kvdict)
        return jobId

class BackgroundRunner(object):

    def __init__(self, function):
        self.function = function

    def __call__(self, *args, **kw):
        return self.backgroundRun(*args, **kw)

    def preFork(self):
        return

    def postFork(self):
        return

    def handleError(self, ei):
        return

    def log_error(self, msg, ei):
        return

    def backgroundRun(self, *args, **kw):
        self.preFork()
        pid = os.fork()
        if pid:
            os.waitpid(pid, 0)
            return
        try:
            try:
                pid = os.fork()
                if pid:
                    # The first child exits and is waited by the parent
                    # the finally part will do the os._exit
                    return
                self.postFork()
                fd = os.open(os.devnull, os.O_RDWR)
                os.close(fd)

                os.chdir('/')
                self.function(*args, **kw)
            except Exception:
                try:
                    ei = sys.exc_info()
                    self.log_error('Daemonized process exception', ei)
                    self.handleError(ei)
                finally:
                    os._exit(1)
        finally:
            os._exit(0)
