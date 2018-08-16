import unittest
import jetpack.util
import time
import subprocess


def get_hostname():
    if jetpack.util.is_linux():
        hostname = subprocess.check_output(['hostname', '-s']).strip()
    else:
        # We use shell here because the command fails for unknown reasons otherwise
        # condor only reports only the first 12 chars of the computername in lowercase so we shorten it here
        hostname = subprocess.check_output('echo %COMPUTERNAME%', shell=True).strip()[:12]
        
    return hostname


class TestExecute(unittest.TestCase):

    @unittest.skipIf(not(jetpack.util.is_linux()), "This test only runs on linux execute nodes")
    def test_execute_nfs_mounts_present(self):
        output = subprocess.check_output(['mount', '-l', '-t', 'nfs'])
        self.assertTrue('/shared type nfs' in output, 'NFS mount for /shared missing')
        self.assertTrue('/sched type nfs' in output, 'NFS mount for /sched missing')
    
    def test_execute_node_condor_status(self):
        # This simple test checks if the node can communicate w/ master
        if jetpack.util.is_linux():
            condor_status_cmd = ['/opt/condor/current/bin/condor_status']
        else:
            # forward slashed are required here, the same command will fail
            # when \'s are used, even though this string is single-quoted
            condor_status_cmd = ['c:/condor/bin/condor_status.exe']
            
        hostname = get_hostname()

        timeout = (60 * 5)
        deadline = timeout + time.time()

        # wait until
        #  1) we can connect to the condor master
        #  2) this execute node registers itself w/ the master, this can take a couple minutes
        hostname_found = False
        while deadline > time.time() and not(hostname_found):
            p = subprocess.Popen(condor_status_cmd, stderr=subprocess.PIPE,
                                 stdout=subprocess.PIPE)
            stdout, stderr = p.communicate()
            error_message = 'Not able to connect to condor master.' + \
                            'Return code was %d\nStdout: %s\nStderr:%s' % (p.returncode, stdout, stderr)
            if p.returncode == 0:
                # converting to lowercase, because windows hostnames randomly are upper case or
                # lowercase the status output
                hostname_found = hostname.lower() in stdout.lower()
                if hostname_found:
                    break

        self.assertEqual(0, p.returncode, error_message)
        self.assertTrue(hostname_found,
                        'Current hostname %s not found in condor_status\nStdout: %s'
                        % (hostname, stdout))
