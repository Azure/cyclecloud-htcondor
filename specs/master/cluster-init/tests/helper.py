from jetpack import config
import subprocess
import os
import logging
import platform

if platform.system() != 'Windows':
    import pwd


logger = logging.getLogger(__name__)


def get_user_profile(user_name, cwd=None):
    '''Get user id, group id, and environment variables for specified user'''
    pw_record = pwd.getpwnam(user_name)
    user_name = pw_record.pw_name
    user_home_dir = pw_record.pw_dir
    user_uid = pw_record.pw_uid
    user_gid = pw_record.pw_gid
    env = os.environ.copy()
    env['HOME'] = user_home_dir
    env['LOGNAME'] = user_name
    env['PWD'] = cwd or user_home_dir
    env['USER'] = user_name
    return user_uid, user_gid, env


def demote_to_user(user_uid, user_gid):
    '''Demote current process to given user and group'''
    def result():
        os.setgid(user_gid)
        os.setuid(user_uid)
    return result


def sudo_check_call(cmd_args, username, cwd=None):
    uid, gid, env = get_user_profile(username, cwd=cwd)
    subprocess.check_call(cmd_args, cwd=cwd, env=env, preexec_fn=demote_to_user(uid, gid))
    return True


def sudo_check_output(cmd_args, username, cwd=None):
    uid, gid, env = get_user_profile(username, cwd=cwd)
    return subprocess.check_output(cmd_args, cwd=cwd, env=env, preexec_fn=demote_to_user(uid, gid))


def get_chef_role(role_name):
    return role_name in config.get('roles', [])
