import unittest
import os
import helper
import logging
import re
import jetpack.util
import time
import shutil
import subprocess


jetpack.util.setup_logging()

logger = logging.getLogger()

STATUS_NOTREADY = 'notready'
STATUS_SUCCESS = 'success'
STATUS_FAILURE = 'failed'

CLUSTER_USER = jetpack.config.get("cyclecloud.cluster.user.name")


def readfile(filename):
    with open(filename) as f:
        content = f.read()
    return content


def line_has_error(line):
    errno_marker = r"^.*\(errno=\d:.*?\).*$"
    return re.match(errno_marker, line)


def has_error(content):
    if 'Error from' not in content:
        return False
    
    lines = content.split('\n')
    return any(map(line_has_error, lines))


def joblog_has_error(joblog):
    content = readfile(joblog)
    return has_error(content)


def joblog_read_error(joblog):
    content = readfile(joblog)
    lines = content.split('\n')
    return "".join([l for l in lines if line_has_error(l)])


def get_job_status(joblog):
    content = readfile(joblog)
    if 'Job executing on host' not in content:
        return STATUS_NOTREADY

    if 'Normal termination (return value 0)' in content:
        return STATUS_SUCCESS

    if has_error(content):
        return STATUS_FAILURE

    return STATUS_NOTREADY


def is_condor_schedd_ready():
    p = subprocess.Popen(['/opt/condor/current/bin/condor_q'], stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE)
    _, stderr = p.communicate()
    succeeded = True
    if p.returncode != 0:
        succeeded = False

    return succeeded, stderr


def wait_for_condor_schedd_ready():
    '''Wait for up to one minute for condor to become ready'''
    timeout = 60
    deadline = timeout + time.time()

    while deadline > time.time():
        succeeded, stderr = is_condor_schedd_ready()
        if succeeded:
            return

    raise RuntimeError("Condor services still not ready after one minute. Error message is:\n%s"
                       % stderr)


class TestSleep(unittest.TestCase):

    def setUp(self):
        self.userhome = "/shared/home/" + CLUSTER_USER

        # create results directory
        self.resultsdir = os.path.join(self.userhome, 'results')
        if not os.path.exists(self.resultsdir):
                os.makedirs(self.resultsdir)
        uid, gid, _ = helper.get_user_profile(CLUSTER_USER)
        os.chown(self.resultsdir, uid, gid)

        # copy over submission file
        submission_file_src = os.path.join(os.path.dirname(__file__), 'sleep.sub')
        submission_file_dst = os.path.join(self.userhome, 'sleep.sub') 
        if not os.path.exists(submission_file_dst):
            shutil.copyfile(submission_file_src, submission_file_dst)

        os.chown(submission_file_dst, uid, gid)

        wait_for_condor_schedd_ready()

    def test_sleep(self):
        output = helper.sudo_check_output(['/opt/condor/current/bin/condor_submit', '-verbose', 'sleep.sub'],
                                          CLUSTER_USER, cwd=self.userhome)
                
        log_file_regex = r'^UserLog = ".*\.log"$'
        
        def match_log_file(line):
            return re.match(log_file_regex, line)
    
        def parse_filename(line):
            return line.split('=')[-1].strip().strip('"')

        lines = output.split('\n')
        job_logs = [parse_filename(l) for l in lines if match_log_file(l)]
        if len(job_logs) < 1:
            raise RuntimeError("Unable to parse output of sleep job submission")

        # wait for up to 30 minutes for the jobs to either succeed or fail
        # why so long? linux execute nodes can join the Condor cluster several minutes (or more!)
        # before they are ready to execute jobs
        timeout = (60 * 30)
        deadline = timeout + time.time()

        while deadline > time.time():
            statuses = [get_job_status(j) for j in job_logs]
            if any([s == STATUS_NOTREADY for s in statuses]):
                continue
            else:
                break

        all_jobs_passed = all([s == STATUS_SUCCESS for s in statuses])

        failure_message = "Job submission failed." 
        timed_out_jobs = [s for s in statuses if s == STATUS_NOTREADY]
        failed_jobs = [s for s in statuses if s == STATUS_FAILURE]
        if len(timed_out_jobs) > 0:
            failure_message = failure_message + " %d jobs failed to complete." % len(timed_out_jobs)
            
        if len(failed_jobs) > 0:
            failure_message = failure_message + " %d jobs failed." % len(failed_jobs)
            logs_with_errors = filter(lambda l: joblog_has_error(l), job_logs)
            err_content = "\n".join([joblog_read_error(l) for l in logs_with_errors])
            failure_message = failure_message + " Error messages from logs:\n" + err_content
            
        self.assertTrue(all_jobs_passed, msg=failure_message)
